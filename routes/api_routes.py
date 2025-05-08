
from flask import Blueprint, jsonify, request, session, current_app, url_for
from datetime import datetime
import os
import json
import uuid
from models import db, AudioRecording, PracticeLog, Material
from core.services.transcribe_utils import transcribe_audio
from core.wer_utils import calculate_wer
from core.diff_viewer import diff_html
from core.responses import api_error_response, api_success_response
from core.audio_utils import process_and_transcribe_audio, AudioProcessingError
from werkzeug.utils import secure_filename
from functools import wraps
from core.services.youtube_utils import check_captions

api_bp = Blueprint('api', __name__, url_prefix='/api')

def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get('X-Replit-User-Id')
        if not user_id:
            return api_error_response("ユーザー認証が必要です。", 401)
        return f(*args, **kwargs)
    return decorated_function

@api_bp.route('/presets')
def get_presets():
    structure = get_presets_structure()
    return jsonify(structure)

def get_presets_structure(practice_type="shadowing"):
    base_path = os.path.join("presets", practice_type)
    presets = {}
    if not os.path.exists(base_path):
        return presets

    for genre in sorted(os.listdir(base_path)):
        genre_path = os.path.join(base_path, genre)
        if os.path.isdir(genre_path):
            levels = sorted([
                d for d in os.listdir(genre_path)
                if os.path.isdir(os.path.join(genre_path, d))
            ])
            presets[genre] = levels

    return presets

@api_bp.route('/recordings/upload', methods=['POST'])
@auth_required
def upload_recording():
    user_id = request.headers.get('X-Replit-User-Id')
    filepath = None

    if 'audio' not in request.files:
        return api_error_response("音声ファイルが提供されていません。", 400)
    
    audio_file = request.files['audio']
    if not audio_file or not audio_file.filename:
        return api_error_response("無効な音声ファイルです。", 400)

    try:
        filename = f"{user_id}_{uuid.uuid4().hex}_{secure_filename(audio_file.filename)}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        audio_file.save(filepath)
        current_app.logger.info(f"Audio file saved to: {filepath}")

        transcript = transcribe_audio(filepath)
        if transcript is None:
            raise ValueError("文字起こしに失敗しました(結果がNone)。")

        file_hash_val = str(uuid.uuid4())

        recording = AudioRecording(
            user_id=user_id,
            filename=filename,
            transcript=transcript,
            file_hash=file_hash_val
        )
        db.session.add(recording)
        db.session.commit()

        return api_success_response({
            "id": recording.id,
            "filename": recording.filename,
            "transcript": recording.transcript,
            "created_at": recording.created_at.isoformat()
        })

    except Exception as e:
        db.session.rollback()
        return api_error_response(f"アップロード処理中にエラーが発生しました: {type(e).__name__}", 500, exception_info=e)

@api_bp.route('/recordings', methods=['GET'])
@auth_required
def get_recordings():
    user_id = request.headers.get('X-Replit-User-Id')
    recordings = AudioRecording.query.filter_by(user_id=user_id).all()
    return jsonify({
        "recordings": [{
            "id": r.id,
            "filename": r.filename,
            "transcript": r.transcript,
            "created_at": r.created_at.isoformat()
        } for r in recordings]
    })

@api_bp.route('/recordings/last', methods=['GET'])
@auth_required
def get_last_practice():
    user_id = request.headers.get('X-Replit-User-Id')
    last_practice = PracticeLog.query.filter_by(user_id=user_id).order_by(PracticeLog.practiced_at.desc()).first()

    if not last_practice:
        return '', 204

    recording = AudioRecording.query.get(last_practice.recording_id)
    if not recording:
        return '', 204

    return jsonify({
        "id": recording.id,
        "filename": recording.filename,
        "transcript": recording.transcript,
        "practiced_at": last_practice.practiced_at.isoformat()
    })

@api_bp.route('/practice/logs', methods=['POST'])
@auth_required
def log_practice():
    try:
        data = request.json
        if not data:
            return api_error_response("Invalid request data", 400)

        required_fields = ["user", "genre", "level", "wer", "original_transcribed", "user_transcribed"]
        if not all(field in data for field in required_fields):
            return api_error_response("Missing required fields", 400)

        wer_value = float(data["wer"])
        log_entry = PracticeLog(
            user_id=data["user"],
            wer=wer_value,
            original_text=data["original_transcribed"],
            user_text=data["user_transcribed"],
            practiced_at=datetime.utcnow()
        )

        db.session.add(log_entry)
        db.session.commit()

        return api_success_response({"message": "Logged successfully", "id": log_entry.id})

    except Exception as e:
        db.session.rollback()
        return api_error_response("ログの保存中にエラーが発生しました。", 500, exception_info=e)

@api_bp.route('/compare_passages', methods=['POST'])
def compare_passages():
    data = request.json
    passage1 = data.get('passage1', '')
    passage2 = data.get('passage2', '')

    wer_score = calculate_wer(passage1, passage2)
    diff_result = diff_html(passage1, passage2)

    return jsonify({
        'wer': wer_score * 100,
        'diff_html': diff_result
    })

@api_bp.route('/sentence_structure')
def get_sentence_structure():
    structure = {}
    base_path = 'presets/sentences'

    if os.path.exists(base_path):
        for genre in os.listdir(base_path):
            genre_path = os.path.join(base_path, genre)
            if os.path.isdir(genre_path):
                structure[genre] = []
                for level in os.listdir(genre_path):
                    level_path = os.path.join(genre_path, level)
                    if os.path.isdir(level_path):
                        structure[genre].append(level)

    return jsonify(structure)

@api_bp.route('/sentences/<genre>/<level>')
def get_sentences(genre, level):
    sentences = []
    base_path = os.path.join('presets/sentences', genre, level)

    if os.path.exists(base_path):
        script_files = sorted([f for f in os.listdir(base_path) if f.startswith('script_')])

        for script_file in script_files:
            index = script_file.split('_')[1].split('.')[0]
            audio_file = f'output_{index}.mp3'
            audio_path = os.path.join(base_path, audio_file)

            if os.path.exists(audio_path):
                with open(os.path.join(base_path, script_file), 'r', encoding='utf-8') as f:
                    text = f.read().strip()

                sentences.append({
                    'text': text,
                    'audio_file': f'/presets/sentences/{genre}/{level}/{audio_file}',
                    'index': index
                })

    return jsonify(sentences)

@api_bp.route('/unlocked_levels/<username>')
def get_unlocked_levels(username):
    with open("preset_log.json", "r") as f:
        logs = json.load(f)

    result = defaultdict(set)

    for entry in logs:
        if entry["user"].lower() != username.lower():
            continue
        if float(entry["wer"]) >= 30:
            continue

        genre = entry["genre"].strip().lower()
        level = entry["level"].strip().lower()
        result[genre].add(level)

    result = {genre: sorted(list(levels)) for genre, levels in result.items()}
    return jsonify(result)

@api_bp.route('/highest_levels/<username>')
def get_highest_levels(username):
    import re
    from collections import defaultdict

    def level_number(level_name):
        match = re.match(r"level(\d+)", level_name.lower())
        return int(match.group(1)) if match else -1

    log_file = "preset_log.json"
    if not os.path.exists(log_file):
        return jsonify({})

    with open(log_file, "r", encoding="utf-8") as f:
        logs = json.load(f)

    genre_max_level = defaultdict(int)

    for entry in logs:
        if entry["user"].lower() != username.lower():
            continue

        genre = entry.get("genre", "").strip().lower()
        level = entry.get("level", "").strip().lower()
        wer = float(entry.get("wer", 100))

        level_num = level_number(level)
        if wer < 30.0 and level_num > genre_max_level[genre]:
            genre_max_level[genre] = level_num

    result = {genre: f"level{num}" for genre, num in genre_max_level.items()}
    return jsonify(result)



@api_bp.route('/check_subtitles', methods=["GET"])
def check_subtitles():
    video_id = request.args.get("video_id")
    if not video_id:
        return api_error_response("Missing video_id", 400)

    result = check_captions(video_id)
    if result is None:
        return api_error_response("Failed to check captions", 500)

    return jsonify({
        "video_id": video_id,
        "has_subtitles": result
    })