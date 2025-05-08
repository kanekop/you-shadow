import openai
import os
import time # タイムアウト処理用に追加
from flask import current_app # ロギング用に current_app をインポート

# --- OpenAI Client の取得 ---
# appからインポートを試みる
# transcribe_utils は app より先にロードされる可能性があるため、try-except を使う
try:
    # app.py 内で openai_client = openai.OpenAI(...) のように初期化されている想定
    from app import openai_client as client
    # ★ タイムアウト設定をクライアント初期化時に行うのがベスト
    # 例: client = openai.OpenAI(api_key=..., timeout=60.0) # 60秒
    # ただし、既存の初期化箇所 (app.py?) を変更する必要がある
except ImportError:
    # app.py 以外から直接使う場合やテストのためのフォールバック
    current_app.logger.warning("Could not import openai_client from app. Falling back to direct initialization.")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # ここで ImportError ではなく、より具体的な設定エラーを示す例外が良いかも
        raise ValueError("OpenAI API key (OPENAI_API_KEY) not found in environment variables.")
    # ★ ここでもタイムアウトを設定
    client = openai.OpenAI(api_key=api_key, timeout=180.0) # 例: 180秒タイムアウト

# --- 定数 ---
MAX_WHISPER_SIZE_MB = 25
MAX_WHISPER_SIZE_BYTES = MAX_WHISPER_SIZE_MB * 1024 * 1024

def transcribe_audio(filepath):
    """
    指定された音声ファイルをOpenAI Whisperで文字起こしする。

    Args:
        filepath (str): 文字起こし対象の音声ファイルパス。

    Returns:
        str: 文字起こし結果のテキスト。

    Raises:
        FileNotFoundError: ファイルが見つからない場合。
        ValueError: ファイルが空、サイズ超過、またはAPIキー未設定の場合。
        TimeoutError: OpenAI API呼び出しがタイムアウトした場合。
        ConnectionError: APIへの接続に失敗した場合。
        PermissionError: APIキーが無効な場合。
        RuntimeError: APIからの予期せぬエラー、またはその他の内部エラー。
    """
    # 1. ファイル存在チェック
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"音声ファイルが見つかりません: {filepath}")

    # 2. ファイルサイズチェック
    try:
        file_size = os.path.getsize(filepath)
    except OSError as e:
        # getsize でエラーになるケース (権限など)
        raise RuntimeError(f"ファイルサイズの取得に失敗しました ({filepath}): {e}")

    if file_size == 0:
        raise ValueError(f"音声ファイルが空です: {filepath}")

    if file_size > MAX_WHISPER_SIZE_BYTES:
        # ファイルサイズ超過は呼び出し元でハンドリングする想定だが、ここでもチェック
        raise ValueError(f"ファイルサイズが上限 ({MAX_WHISPER_SIZE_MB}MB) を超えています: {filepath} ({file_size / (1024*1024):.1f}MB)")

    # 3. OpenAI API 呼び出し
    try:
        with open(filepath, "rb") as audio_file:
            start_time = time.time()
            current_app.logger.info(f"Starting OpenAI transcription for: {filepath}")

            # client 初期化時にタイムアウトが設定されていることを期待
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
                # ここで追加のパラメータを指定可能 (例: language='en', prompt='...')
            )

            duration = time.time() - start_time
            current_app.logger.info(f"OpenAI transcription completed in {duration:.2f} seconds for: {filepath}")

    # 4. エラーハンドリング (より具体的に)
    except FileNotFoundError as e:
        # 基本的にここには来ないはずだが念のため
        current_app.logger.error(f"File not found during transcription process: {filepath}", exc_info=e)
        raise e # そのまま raise
    except ValueError as e: # ファイルが空、サイズ超過 (ここには来ないはず)、または client 初期化失敗など
        current_app.logger.error(f"ValueError during transcription process: {filepath}", exc_info=e)
        raise e # そのまま raise
    except openai.APITimeoutError as e:
        processing_time = time.time() - start_time
        current_app.logger.error(f"OpenAI API call timed out after {processing_time:.2f}s for {filepath}", exc_info=e)
        raise TimeoutError(f"OpenAI APIへの接続がタイムアウトしました ({filepath})")
    except openai.APIConnectionError as e:
        current_app.logger.error(f"OpenAI API connection error for {filepath}", exc_info=e)
        raise ConnectionError(f"OpenAI APIへの接続に失敗しました: {e}")
    except openai.RateLimitError as e:
        current_app.logger.warning(f"OpenAI API rate limit exceeded for {filepath}", exc_info=e)
        # RateLimitError は再試行可能な場合もあるため、Warningレベルでも良いかも
        raise RuntimeError(f"OpenAI APIのレート制限を超えました。しばらくしてから再試行してください。") # より汎用的な Runtime Error
    except openai.AuthenticationError as e:
        current_app.logger.error(f"OpenAI API authentication error for {filepath}", exc_info=e)
        raise PermissionError(f"OpenAI APIキーが無効または設定されていません: {e}")
    except openai.APIStatusError as e:
        # APIからの明確なエラーステータス (4xx, 5xx)
        current_app.logger.error(f"OpenAI API status error for {filepath} (Status: {e.status_code})", exc_info=e)
        raise RuntimeError(f"OpenAI APIエラー (ステータス: {e.status_code}): {e.message}")
    except Exception as e:
        # その他の予期せぬエラー (pydubのエラーなどもここに該当する可能性あり)
        error_type = type(e).__name__
        current_app.logger.error(f"Unexpected error during transcription for {filepath}: {error_type}", exc_info=e)
        raise RuntimeError(f"文字起こし中に予期せぬエラーが発生しました ({error_type}): {str(e)}")

    # 5. 結果の検証と返却
    transcribed_text = transcript_response.text
    if not transcribed_text or transcribed_text.strip() == "":
        current_app.logger.warning(f"Transcription result for {filepath} was empty.")
        # 空の結果を許容するか、エラーとするかは要件次第
        # ここでは空文字をそのまま返す
        return ""

    return transcribed_text