# core/responses.py (確認・修正ポイント)
import logging
from flask import jsonify, current_app

def api_error_response(message, status_code=400, log_error=True, exception_info=None, log_prefix="API Error"):
    user_message = message

    if log_error:
        try:
            logger = current_app.logger # アプリケーションコンテキスト内で取得
            log_full_message = f"{log_prefix} (HTTP {status_code}): {message}"

            if status_code >= 500:
                # 500番台エラー: ユーザーには汎用メッセージ、ログには詳細
                user_message = "サーバー内部でエラーが発生しました。しばらくしてから再度お試しください。"
                # スタックトレースは exception_info があれば自動で記録される
                logger.error(log_full_message, exc_info=exception_info)
            else: # 400番台エラー
                # 400番台でも詳細なエラー原因をログに残すのは有益
                if status_code == 429: # RateLimitの場合など
                    logger.warning(log_full_message, exc_info=exception_info)
                else:
                    logger.warning(log_full_message, exc_info=exception_info) # 基本はwarningで
        except RuntimeError: # Flaskアプリケーションコンテキスト外など
            # 標準のloggingを使用
            std_logger = logging.getLogger(__name__) # このモジュール用のロガー
            log_full_message = f"(No App Context) {log_prefix} (HTTP {status_code}): {message}"
            if status_code >= 500:
                std_logger.error(log_full_message, exc_info=exception_info)
            else:
                std_logger.warning(log_full_message, exc_info=exception_info)

    return jsonify({"error": user_message}), status_code

# api_success_response はそのままで良いでしょう
def api_success_response(data, status_code=200):
    return jsonify(data), status_code