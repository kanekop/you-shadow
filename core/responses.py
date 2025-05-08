# responses.py (修正案)
from flask import jsonify, current_app
import logging # logging をインポート

# モジュールレベルのロガーを取得 (current_app が利用できない場合に備える場合)
# logger = logging.getLogger(__name__)
# または、current_app.logger を直接使う想定でもOK

def api_error_response(message, status_code=400, log_error=True, exception_info=None, log_prefix="API Error"):
    """
    標準的なAPIエラーレスポンスを生成し、必要に応じてログに記録する。

    Args:
        message (str): クライアントに返すエラーメッセージ。
        status_code (int): HTTPステータスコード。
        log_error (bool): エラーをログに記録するかどうか。デフォルトはTrue。
        exception_info (Exception, optional): ログ記録用の例外情報。デフォルトはNone。
        log_prefix (str): ログメッセージのプレフィックス。
    Returns:
        Response: FlaskのJSONレスポンスオブジェクト。
    """
    user_message = message # デフォルトではそのまま表示

    if log_error:
        try:
            # current_app コンテキスト内で logger を取得
            logger = current_app.logger
            log_full_message = f"{log_prefix} (HTTP {status_code}): {message}"

            if status_code >= 500:
                # 500番台エラー: ユーザーには汎用メッセージ、ログには詳細
                user_message = "サーバー内部でエラーが発生しました。しばらくしてから再度お試しください。"
                if exception_info:
                    logger.error(log_full_message, exc_info=exception_info) # スタックトレース付き
                else:
                    logger.error(log_full_message)
            else: # 400番台エラー: ユーザーにもある程度具体的なメッセージ
                if exception_info:
                    # 400番台でも例外情報があればログレベルを上げるか検討 (ここではwarningのままスタックトレース追加)
                    logger.warning(log_full_message, exc_info=exception_info)
                else:
                    logger.warning(log_full_message)
        except RuntimeError:
            # Flaskのアプリケーションコンテキスト外で呼ばれた場合など
            # フォールバックとして標準のloggingを使用
            import logging as std_logging
            std_logger = std_logging.getLogger(__name__)
            log_full_message = f"(No App Context) {log_prefix} (HTTP {status_code}): {message}"
            if status_code >= 500:
                std_logger.error(log_full_message, exc_info=exception_info)
            else:
                 std_logger.warning(log_full_message, exc_info=exception_info)


    return jsonify({"error": user_message}), status_code

def api_success_response(data, status_code=200):
    """
    標準的なAPI成功レスポンスを生成します。(変更なし、既存のままでOK)
    Args:
        data (dict or any): クライアントに返すデータ。
        status_code (int): HTTPステータスコード。
    Returns:
        Response: FlaskのJSONレスポンスオブジェクト。
    """
    return jsonify(data), status_code