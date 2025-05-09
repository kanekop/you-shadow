import openai
import os
import time
from flask import request, current_app
from models import db, User # Userモデルをインポート
from datetime import datetime, timezone # timezone をインポート

# --- OpenAI Client の取得 ---
_client = None # モジュールレベルのクライアント変数 (シングルトン的に使う)

def get_openai_client():
    """OpenAIクライアントを取得または初期化する関数"""
    global _client
    if _client:
        return _client

    try:
        from app import openai_client as client_from_app
        _client = client_from_app
        # ここでログを出したい場合は、標準の logging を使う
        # import logging
        # logging.getLogger(__name__).info("Using openai_client imported from app.")
    except ImportError:
        # ★ フォールバック時のログも標準 logging を使う
        import logging
        logger = logging.getLogger(__name__) # このモジュール用のロガーを取得
        logger.warning("Could not import openai_client from app. Falling back to direct initialization.")

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key (OPENAI_API_KEY) not found.") # エラーログ
            raise ValueError("OpenAI API key (OPENAI_API_KEY) not found in environment variables.")

        _client = openai.OpenAI(api_key=api_key, timeout=180.0)

    return _client

# --- 定数 ---
MAX_WHISPER_SIZE_MB = 25
MAX_WHISPER_SIZE_BYTES = MAX_WHISPER_SIZE_MB * 1024 * 1024




def check_and_log_api_call(replit_user_id: str) -> bool:
    """
    指定されたユーザーがAPIコールを実行できるか確認し、可能であればコール数を記録する。
    Returns:
        bool: APIコールが許可される場合はTrue、そうでない場合はFalse。
    Raises:
        ValueError: ユーザーが見つからない場合 (get_or_create_userで対応済みなら不要)
    """
    user = User.query.filter_by(replit_user_id=replit_user_id).first()
    if not user:
        # 通常、APIエンドポイントの@auth_requiredやget_or_create_userで処理されるはず
        current_app.logger.warning(f"APIコールチェック: ユーザーが見つかりません - {replit_user_id}")
        return False # またはエラーを発生させる

    now = datetime.now(timezone.utc)

    if user.is_special_free_account:
        current_app.logger.info(f"APIコール許可 (特別無料アカウント): {replit_user_id}")
        return True # 特別アカウントは常に許可

    # 1. トライアル期間のチェック
    if user.is_trial_period_active:
        if user.trial_expires_at and user.trial_expires_at > now:
            if user.trial_api_call_used < user.trial_api_call_limit:
                user.trial_api_call_used += 1
                db.session.commit()
                current_app.logger.info(f"APIコール許可 (トライアル): {replit_user_id}, 残り {user.trial_api_call_limit - user.trial_api_call_used}")
                return True
            else:
                user.is_trial_period_active = False # 上限に達したらトライアル終了
                db.session.commit()
                current_app.logger.info(f"APIコール拒否 (トライアル上限超過): {replit_user_id}")
        else: # トライアル期限切れ
            user.is_trial_period_active = False
            db.session.commit()
            current_app.logger.info(f"APIコール拒否 (トライアル期限切れ): {replit_user_id}")

    # 2. ワンタイムオプションのチェック
    if user.onetime_access_expires_at and user.onetime_access_expires_at > now:
        if user.api_calls_onetime_used < user.api_calls_onetime_limit:
            user.api_calls_onetime_used += 1
            db.session.commit()
            current_app.logger.info(f"APIコール許可 (ワンタイム): {replit_user_id}, 残り {user.api_calls_onetime_limit - user.api_calls_onetime_used}")
            return True
        else:
            current_app.logger.info(f"APIコール拒否 (ワンタイム上限超過): {replit_user_id}")
            # ワンタイム上限超過の場合、ここでreturn false せず、サブスクリプションのチェックに進んでも良い

    # 3. 月額サブスクリプションのチェック
    if user.current_subscription_id and user.subscription_status == 'active':
        if user.subscription_current_period_end and user.subscription_current_period_end > now:
            # リセット日の確認と処理 (Userモデルのget_active_api_limit_and_usedに集約しても良い)
            if user.api_calls_reset_date and user.api_calls_reset_date <= now:
                user.api_calls_monthly_used = 0
                user.api_calls_reset_date = user.subscription_current_period_end # 次の期間終了日にリセット
                current_app.logger.info(f"APIコール数リセット (サブスクリプション): {replit_user_id}")

            if user.api_calls_monthly_used < user.api_calls_monthly_limit:
                user.api_calls_monthly_used += 1
                db.session.commit()
                current_app.logger.info(f"APIコール許可 (サブスクリプション): {replit_user_id}, 残り {user.api_calls_monthly_limit - user.api_calls_monthly_used}")
                return True
            else:
                current_app.logger.info(f"APIコール拒否 (サブスクリプション上限超過): {replit_user_id}")
        else: # サブスクリプション期限切れ
            user.subscription_status = 'expired' # またはStripe Webhookに任せる
            db.session.commit()
            current_app.logger.info(f"APIコール拒否 (サブスクリプション期限切れ): {replit_user_id}")

    current_app.logger.info(f"APIコール拒否 (有効なプランなし): {replit_user_id}")
    return False




def transcribe_audio(filepath):
    """
    指定された音声ファイルをOpenAI Whisperで文字起こしする。
    (関数のdocstringは変更なし)
    """
    # --- ★ 関数内で Flask の logger を使う ---
    from flask import current_app # 関数内でインポートするか、関数の引数で logger を渡す
    logger = current_app.logger # アプリケーションコンテキスト内で取得
    # --------------------------------------

    client = get_openai_client() # クライアントを取得/初期化

    # 1. ファイル存在チェック
    if not os.path.exists(filepath):
        logger.error(f"Audio file not found: {filepath}") # ログ追加
        raise FileNotFoundError(f"音声ファイルが見つかりません: {filepath}")

    # 2. ファイルサイズチェック
    try:
        file_size = os.path.getsize(filepath)
    except OSError as e:
        logger.error(f"Failed to get file size: {filepath}", exc_info=e) # ログ追加
        raise RuntimeError(f"ファイルサイズの取得に失敗しました ({filepath}): {e}")

    if file_size == 0:
        logger.warning(f"Audio file is empty: {filepath}") # 警告ログ
        raise ValueError(f"音声ファイルが空です: {filepath}")

    if file_size > MAX_WHISPER_SIZE_BYTES:
        logger.error(f"File size exceeds limit ({MAX_WHISPER_SIZE_MB}MB): {filepath} ({file_size / (1024*1024):.1f}MB)") # ログ追加
        raise ValueError(f"ファイルサイズが上限 ({MAX_WHISPER_SIZE_MB}MB) を超えています: {filepath} ({file_size / (1024*1024):.1f}MB)")

    # 3. OpenAI API 呼び出し
    try:
        with open(filepath, "rb") as audio_file:
            start_time = time.time()
            logger.info(f"Starting OpenAI transcription for: {filepath}") # ログ追加

            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

            duration = time.time() - start_time
            logger.info(f"OpenAI transcription completed in {duration:.2f} seconds for: {filepath}") # ログ追加

    # 4. エラーハンドリング (ログは logger を使うように修正)
    except FileNotFoundError as e:
        logger.error(f"File not found during transcription process: {filepath}", exc_info=e)
        raise e
    except ValueError as e:
        logger.error(f"ValueError during transcription process: {filepath}", exc_info=e)
        raise e
    except openai.APITimeoutError as e:
        processing_time = time.time() - start_time
        logger.error(f"OpenAI API call timed out after {processing_time:.2f}s for {filepath}", exc_info=e)
        raise TimeoutError(f"OpenAI APIへの接続がタイムアウトしました ({filepath})")
    except openai.APIConnectionError as e:
        logger.error(f"OpenAI API connection error for {filepath}", exc_info=e)
        raise ConnectionError(f"OpenAI APIへの接続に失敗しました: {e}")
    except openai.RateLimitError as e:
        logger.warning(f"OpenAI API rate limit exceeded for {filepath}", exc_info=e)
        raise RuntimeError(f"OpenAI APIのレート制限を超えました。しばらくしてから再試行してください。")
    except openai.AuthenticationError as e:
        logger.error(f"OpenAI API authentication error for {filepath}", exc_info=e)
        raise PermissionError(f"OpenAI APIキーが無効または設定されていません: {e}")
    except openai.APIStatusError as e:
        logger.error(f"OpenAI API status error for {filepath} (Status: {e.status_code})", exc_info=e)
        raise RuntimeError(f"OpenAI APIエラー (ステータス: {e.status_code}): {e.message}")
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Unexpected error during transcription for {filepath}: {error_type}", exc_info=e)
        raise RuntimeError(f"文字起こし中に予期せぬエラーが発生しました ({error_type}): {str(e)}")

    # 5. 結果の検証と返却
    transcribed_text = transcript_response.text
    if not transcribed_text or transcribed_text.strip() == "":
        logger.warning(f"Transcription result for {filepath} was empty.")
        return ""

    return transcribed_text