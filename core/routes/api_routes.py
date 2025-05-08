# routes/api_routes.py
from flask import Blueprint, jsonify, request, current_app
from ..models import db, AudioRecording, PracticeLog, Material # 必要に応じてモデルをインポート
from ..core.responses import api_success_response, api_error_response
from ..transcribe_utils import transcribe_audio # 例
from ..config import Config # 設定値を利用する場合
from ..utils import normalize_text, remove_fillers # 例
from ..wer_utils import calculate_wer # 例
from ..diff_viewer import diff_html # 例

api_bp = Blueprint('api', __name__, url_prefix='/api') # url_prefixで /api を共通化