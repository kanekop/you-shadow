# core/auth.py

from functools import wraps
from flask import request
from .responses import api_error_response # core.responses からインポート

def auth_required(f):
    """
    リクエストヘッダーに 'X-Replit-User-Id' が存在するかどうかを確認するデコレータ。
    存在しない場合は 401 Unauthorized エラーを返す。
    APIエンドポイントでの使用を想定。
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get('X-Replit-User-Id')
        if not user_id:
            # api_error_response を使用してJSON形式のエラーを返す
            return api_error_response("ユーザー認証が必要です。", 401)
        return f(*args, **kwargs)
    return decorated_function

# もし将来的にWebページ用の認証デコレータ（例：ログインページへリダイレクトする）が必要になった場合は、
# 別名のデコレータ（例: web_auth_required）としてここに追加できます。