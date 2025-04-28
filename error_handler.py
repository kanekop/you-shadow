
from flask import jsonify
from functools import wraps

class APIError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code

def handle_api_error(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except APIError as e:
            return jsonify({'error': e.message}), e.status_code
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return decorated_function
