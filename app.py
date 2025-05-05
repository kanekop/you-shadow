import os
import uuid
import math
import json
import tempfile
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict

# Flask imports
from flask import (
    Flask, render_template, request, redirect, url_for, 
    jsonify, send_from_directory, session
)
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from functools import wraps
from werkzeug.utils import secure_filename

# Audio processing
from pydub import AudioSegment
from pydub.utils import make_chunks
import openai

# Local imports
from models import db, Material, AudioRecording, PracticeLog
from config import (
    SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS,
    UPLOAD_FOLDER, SECRET_KEY
)
from transcribe_utils import transcribe_audio
from wer_utils import wer, calculate_wer
from diff_viewer import diff_html, get_diff_html
from youtube_utils import youtube_bp, check_captions

# Constants
TARGET_CHUNK_SIZE_MB = 20
TARGET_CHUNK_SIZE_BYTES = TARGET_CHUNK_SIZE_MB * 1024 * 1024
CHUNK_OVERLAP_MS = 5000

# Authentication decorator
def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get('X-Replit-User-Id')
        if not user_id:
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function

# Flask app initialization
app = Flask(__name__)
migrate = Migrate(app, db)

# App configuration
app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    SECRET_KEY=SECRET_KEY,
    SQLALCHEMY_DATABASE_URI=SQLALCHEMY_DATABASE_URI,
    SQLALCHEMY_TRACK_MODIFICATIONS=SQLALCHEMY_TRACK_MODIFICATIONS,
    MAX_CONTENT_LENGTH=25 * 1024 * 1024  # 25MB upload limit
)

# Initialize extensions
db.init_app(app)
migrate.init_app(app, db)
app.register_blueprint(youtube_bp)
CORS(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# OpenAI configuration
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Utility functions
def generate_wer_matrix(username, logs):
    user_logs = [log for log in logs if log.get("user", "").lower() == username.lower()]
    wer_matrix = {}
    for log in user_logs:
        genre = log.get("genre", "")
        level = log.get("level", "")
        wer = log.get("wer", None)
        if not (genre and level and isinstance(wer, (int, float))):
            continue
        try:
            level_num = int(level.lower().replace("level", ""))
        except:
            continue
        key = (level_num, genre)
        wer_matrix[key] = wer
    df = pd.DataFrame([
        {"Level": level, "Genre": genre, "WER": wer}
        for (level, genre), wer in wer_matrix.items()
    ])
    pivot = df.pivot(index="Level", columns="Genre", values="WER").sort_index()
    return pivot.fillna("")

def generate_min_wer_matrix(username, logs):
    user_logs = [log for log in logs if log.get("user", "").lower() == username.lower()]
    wer_matrix = {}

    for log in user_logs:
        genre = log.get("genre", "")
        level = log.get("level", "")
        wer = log.get("wer", None)
        if not (genre and level and isinstance(wer, (int, float))):
            continue
        try:
            level_num = int(level.lower().replace("level", ""))
        except:
            continue
        key = (level_num, genre)
        if key not in wer_matrix or wer < wer_matrix[key]:
            wer_matrix[key] = wer

    df = pd.DataFrame([
        {"Level": level, "Genre": genre, "WER": wer}
        for (level, genre), wer in wer_matrix.items()
    ])
    pivot = df.pivot(index="Level", columns="Genre", values="WER").sort_index()
    return pivot.fillna("")

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

# Basic routes
@app.route('/__replauthlogout')
def logout():
    return '', 200

@app.route('/')
def index():
    user_id = request.headers.get('X-Replit-User-Id')
    user_name = request.headers.get('X-Replit-User-Name')
    return render_template('index.html', user_id=user_id, user_name=user_name)

# Dashboard routes
@app.route("/dashboard/<username>")
@auth_required
def dashboard(username):
    try:
        with open("preset_log.json", "r", encoding="utf-8") as f:
            logs = json.load(f)
    except Exception as e:
        return f"Error loading log: {e}"

    user_logs = [log for log in logs if log.get("user", "").lower() == username.lower()]
    date_set = {datetime.fromisoformat(log["timestamp"]).date() for log in user_logs if "timestamp" in log}

    streak = 0
    today = datetime.utcnow().date()
    while today in date_set:
        streak += 1
        today -= timedelta(days=1)

    wer_table = generate_min_wer_matrix(username, logs)
    genres = list(wer_table.columns)
    levels = list(wer_table.index)
    wer_values = wer_table.values.tolist()

    return render_template("dashboard.html",
                         username=username,
                         streak=streak,
                         genres=genres,
                         levels=levels,
                         wer_values=wer_values)

@app.route("/details/<username>/<genre>/<level>")
def detail_view(username, genre, level):
    with open("preset_log.json", "r", encoding="utf-8") as f:
        logs = json.load(f)

    user_logs = [
        log for log in logs
        if log.get("user", "").lower() == username.lower()
        and log.get("genre") == genre
        and log.get("level") == level
    ]

    return render_template("detail.html",
                           username=username,
                           genre=genre,
                           level=level,
                           logs=user_logs)


@app.route("/read-aloud", methods=["GET", "POST"])
def read_aloud():
    if request.method == "GET":
        return render_template("read_aloud.html")

    reference_text = request.form.get("reference_text", "").strip()
    reference_file = request.files.get("reference_file")
    if reference_file and reference_file.filename.endswith(".txt"):
        reference_text = reference_file.read().decode("utf-8").strip()

    audio_file = request.files["audio_file"]
    audio_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(audio_file.filename))
    audio_file.save(audio_path)

    recognized_text = transcribe_audio(audio_path)

    wer_score = wer(reference_text, recognized_text)
    diff_result = diff_html(reference_text, recognized_text)

    return render_template("result.html",
                           ref_text=reference_text,
                           hyp_text=recognized_text,
                           wer_score=wer_score,
                           diff_result=diff_result)

@app.route('/youtube')
def youtube_ui():
    return render_template('youtube.html')

@app.route('/evaluate_youtube', methods=['POST'])
def evaluate_youtube():
    import tempfile
    from openai import OpenAI
    from wer_utils import calculate_wer

    audio_file = request.files['audio']
    transcript_text = request.form['transcript']

    client = OpenAI()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        audio_file.save(tmp.name)
        with open(tmp.name, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        transcribed = response.text

    wer = calculate_wer(transcript_text, transcribed)

    diff_result = diff_html(transcript_text, transcribed)

    return jsonify({
        "transcribed": transcribed,
        "wer": round(wer * 100, 2),
        "diff_html": diff_result
    })

@app.route('/presets/<path:filename>')
def serve_presets(filename):
    return send_from_directory("presets", filename)

@app.route("/ranking")
def show_ranking():
    genre = request.args.get("genre")
    level = request.args.get("level")

    if not genre or not level:
        return render_template("ranking.html", rankings=None)

    log_path = "preset_log.json"
    if not os.path.exists(log_path):
        return render_template("ranking.html", rankings=[],
                               genre=genre, level=level)

    with open(log_path, "r", encoding="utf-8") as f:
        logs = json.load(f)

    current_user = request.cookies.get("username", "anonymous")

    matched = [entry for entry in logs if entry["genre"] == genre and entry["level"] == level]
    sorted_entries = sorted(matched, key=lambda x: x["wer"])

    return render_template("ranking.html",
                           rankings=sorted_entries,
                           genre=genre, level=level,
                           current_user=current_user)

@app.route("/api/unlocked_levels/<username>")
def get_unlocked_levels(username):
    import json
    from collections import defaultdict

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

@app.route("/api/presets")
def api_presets():
    structure = get_presets_structure()
    return jsonify(structure)

@app.route('/submit', methods=['POST'])
def submit():
    user_id = request.form['user_id']
    script = request.form['script']
    file = request.files['audio']

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    static_path = os.path.join("static", "recorded.webm")
    shutil.copy(filepath, static_path)

    transcript = transcribe_audio(filepath)

    wer_score, subs, dels, ins, word_count = wer(script, transcript)

    diff_result = diff_html(script, transcript)

    log_entry = {
        "user_id": user_id,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "script": script,
        "transcript": transcript,
        "wer": round(wer_score, 1),
        "substitutions": subs,
        "deletions": dels,
        "insertions": ins,
        "words": word_count,
        "note": ""
    }

    log_path = "log.json"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
    else:
        logs = []

    logs.append(log_entry)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

    return render_template(
        "result.html",
        user_id=user_id,
        filename=filename,
        script=script,
        transcript=transcript,
        wer_score=wer_score,
        subs=subs,
        dels=dels,
        ins=ins,
        word_count=word_count,
        diff_result=diff_result
    )

@app.route('/api/recordings/upload', methods=['POST'])
@auth_required
def upload_recording():
    try:
        user_id = request.headers.get('X-Replit-User-Id')
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        if 'audio' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400

        audio_file = request.files['audio']
        if not audio_file.filename:
            return jsonify({"error": "Invalid file"}), 400

        filename = secure_filename(audio_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        audio_file.save(filepath)
        transcript = transcribe_audio(filepath)

        recording = AudioRecording(
            user_id=user_id,
            filename=filename,
            transcript=transcript,
            file_hash=str(uuid.uuid4())
        )

        db.session.add(recording)
        db.session.commit()

        return jsonify({
            "id": recording.id,
            "filename": recording.filename,
            "transcript": recording.transcript
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/check_subtitles', methods=["GET"])
def check_subtitles():
    video_id = request.args.get("video_id")
    if not video_id:
        return jsonify({"error": "Missing video_id"}), 400

    result = check_captions(video_id)
    if result is None:
        return jsonify({"error": "Failed to check captions"}), 500

    return jsonify({
        "video_id": video_id,
        "has_subtitles": result
    })

@app.route('/evaluate_read_aloud', methods=['POST'])
def evaluate_read_aloud():
    import tempfile
    from openai import OpenAI
    from wer_utils import calculate_wer

    try:
        if 'audio' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400

        audio_file = request.files['audio']
        if not audio_file:
            return jsonify({"error": "Invalid audio file"}), 400

        transcript_text = request.form.get('transcript')
        if not transcript_text:
            return jsonify({"error": "No transcript provided"}), 400

        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
            audio_file.save(tmp.name)
            try:
                transcribed = transcribe_audio(tmp.name)
            except ValueError as e:
                return jsonify({"error": str(e)}), 500
            except Exception as e:
                print(f"Transcription error: {str(e)}")
                return jsonify({"error": "Failed to transcribe audio"}), 500
            finally:
                import os
                if os.path.exists(tmp.name):
                    os.remove(tmp.name)

        wer_score = calculate_wer(transcribed, transcript_text)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    diff_result = diff_html(transcribed, transcript_text)

    return jsonify({
        "transcribed": transcribed,
        "wer": round(wer_score * 100, 2),
        "diff_html": diff_result
    })

@app.route('/shadowing')
def shadowing_ui():
    return render_template('shadowing.html')

@app.route('/custom-shadowing')
def custom_shadowing_ui():
    return render_template('custom_shadowing.html')

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/upload_custom_audio', methods=['POST'])
@auth_required
def upload_custom_audio():
    user_id = request.headers.get('X-Replit-User-Id')
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401

    if 'audio' not in request.files:
        return jsonify({"error": "音声ファイルが選択されていません"}), 400

    audio_file = request.files['audio']
    if not audio_file or audio_file.filename == '':
        return jsonify({"error": "無効なファイルです"}), 400

    file_ext = os.path.splitext(audio_file.filename)[1].lower()
    allowed_extensions = ['.mp3', '.m4a', '.wav', '.mpga', '.mpeg', '.webm']
    if file_ext not in allowed_extensions:
        return jsonify({"error": f"サポートされていないファイル形式です: {file_ext}"}), 400

    filename_base = secure_filename(f"{user_id}_{uuid.uuid4().hex}")
    original_filename = f"{filename_base}_original{file_ext}"
    original_filepath = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
    audio_file.save(original_filepath)
    print(f"一時ファイル保存先: {original_filepath}")

    final_transcription = ""
    processed_chunk_paths = []

    try:
        file_size = os.path.getsize(original_filepath)
        print(f"ファイルサイズ: {file_size / (1024*1024):.2f} MB")

        if file_size > TARGET_CHUNK_SIZE_BYTES:
            print("ファイルサイズが上限を超えています。分割処理を開始します...")
            audio = AudioSegment.from_file(original_filepath)
            duration_ms = len(audio)
            print(f"音声の長さ: {duration_ms / 1000:.2f} 秒")

            chunk_length_ms = 600 * 1000 # 10分
            transcribed_parts = []
            num_chunks = math.ceil(duration_ms / (chunk_length_ms - CHUNK_OVERLAP_MS))
            print(f"推定チャンク数: {num_chunks}")

            current_pos_ms = 0
            chunk_index = 0
            while current_pos_ms < duration_ms:
                start_ms = max(0, current_pos_ms - CHUNK_OVERLAP_MS)
                end_ms = min(current_pos_ms + chunk_length_ms, duration_ms)
                print(f"チャンク {chunk_index + 1}/{num_chunks}: {start_ms/1000:.1f}s - {end_ms/1000:.1f}s")

                chunk = audio[start_ms:end_ms]

                with tempfile.NamedTemporaryFile(
                    prefix=f"{filename_base}_chunk_{chunk_index}_",
                    suffix=".mp3",
                    dir=app.config['UPLOAD_FOLDER'],
                    delete=False
                ) as tmp_chunk_file:
                    chunk_filepath = tmp_chunk_file.name
                    print(f"  チャンクファイル書き出し中: {chunk_filepath}")
                    chunk.export(chunk_filepath, format="mp3")
                    processed_chunk_paths.append(chunk_filepath)

                print(f"  チャンク {chunk_index + 1} 文字起こし中...")
                try:
                    transcript_part = transcribe_audio(chunk_filepath)
                    transcribed_parts.append(transcript_part)
                    print(f"  チャンク {chunk_index + 1} 文字起こし完了.")
                except Exception as transcribe_err:
                    print(f"!! チャンク {chunk_index + 1} の文字起こしエラー: {transcribe_err}")
                    raise transcribe_err

                current_pos_ms += chunk_length_ms
                chunk_index += 1

            final_transcription = " ".join(transcribed_parts).strip()
            print("全てのチャンクの文字起こしを結合しました。")

        else:
            print("ファイルサイズは上限内です。直接文字起こしします...")
            final_transcription = transcribe_audio(original_filepath)
            print("直接文字起こし完了。")

        print("データベースにMaterialを保存します...")
        new_material = Material(
            user_id=user_id,
            material_name=audio_file.filename,
            storage_key=original_filepath,
            transcript=final_transcription,
            upload_timestamp=datetime.utcnow()
        )
        db.session.add(new_material)
        db.session.commit()
        print(f"Material ID: {new_material.id} でデータベースに保存しました。")

        session['current_material_id'] = new_material.id
        session['custom_transcription'] = final_transcription

        return jsonify({
            "audio_url": url_for('serve_upload', filename=original_filename),
            "transcription": final_transcription,
            "material_id": new_material.id
        })

    except Exception as e:
        db.session.rollback()
        print(f"!! /upload_custom_audio でエラー発生: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"処理中にエラーが発生しました。詳細はサーバーログを確認してください。"}), 500

    finally:
        print("一時チャンクファイルを削除します...")
        for path in processed_chunk_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"  削除: {path}")
                except OSError as del_err:
                    print(f"!! 一時ファイル削除エラー ({path}): {del_err}")

        db.session.remove()

@app.route('/evaluate_custom_shadowing', methods=['POST'])
@auth_required
def evaluate_custom_shadowing():
    user_id = request.headers.get('X-Replit-User-Id')
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401

    if 'recorded_audio' not in request.files:
        return jsonify({"error": "No recorded audio provided"}), 400

    material_id = session.get('current_material_id')
    original_transcription = session.get('custom_transcription')

    if not material_id or not original_transcription:
        return jsonify({"error": "Original material information not found in session"}), 400

    recorded_audio = request.files['recorded_audio']

    tmp_path = os.path.join(app.config['UPLOAD_FOLDER'], f'tmp_recording_{user_id}_{uuid.uuid4().hex}.webm')
    processed_path = tmp_path.replace('.webm', '_processed.wav')
    try:
        recorded_audio.save(tmp_path)
        WARMUP_TRANSCRIPT = "10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0"
        audio = AudioSegment.from_file(tmp_path)
        audio.export(processed_path, format="wav")
        full_transcription = transcribe_audio(processed_path)
        user_transcription = full_transcription

        numbers = WARMUP_TRANSCRIPT.split(", ")
        suffixes = [", ".join(numbers[i:]) for i in range(len(numbers))]
        suffixes.sort(key=len, reverse=True)

        matched_suffix = None
        normalized_full_transcription = full_transcription.lower().strip()

        for suffix in suffixes:
            if normalized_full_transcription.startswith(suffix.lower()):
                matched_suffix = suffix
                break

        if matched_suffix:
            start_pos = normalized_full_transcription.find(matched_suffix.lower())
            if start_pos != -1:
                user_transcription = full_transcription[start_pos + len(matched_suffix):].strip()

        wer_score = calculate_wer(user_transcription, original_transcription)
        diff_result = diff_html(user_transcription, original_transcription)

        new_log = PracticeLog(
            user_id=user_id,
            practice_type='custom',
            material_id=material_id,
            recording_id=None,
            wer=round(wer_score * 100, 2),
            original_text=original_transcription,
            user_text=user_transcription
        )
        db.session.add(new_log)
        db.session.commit()

        return jsonify({
            "wer": round(wer_score * 100, 2),
            "diff_html": diff_result,
            "original_transcription": original_transcription,
            "user_transcription": user_transcription
        })

    except Exception as e:
        db.session.rollback()
        print(f"Evaluation error: {str(e)}")
        return jsonify({"error": f"評価処理中にエラーが発生しました: {str(e)}"}), 500
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if os.path.exists(processed_path):
            os.remove(processed_path)
        db.session.remove()

@app.route('/evaluate_shadowing', methods=['POST'])
def evaluate_shadowing():
    from openai import OpenAI
    import tempfile
    from wer_utils import calculate_wer

    original_audio = request.files['original_audio']
    recorded_audio = request.files['recorded_audio']

    client = OpenAI()

    genre = request.form.get("genre", "")
    level = request.form.get("level", "")
    username = request.form.get("username", "anonymous")

    script_path = os.path.join("presets", "shadowing", genre, level, "script.txt")
    if not os.path.exists(script_path):
        return jsonify({"error": f"Script not found at: {script_path}"}), 400

    with open(script_path, "r", encoding="utf-8") as f:
        original_transcribed = f.read().strip()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_in:
        recorded_audio.save(tmp_in.name)

    audio = AudioSegment.from_file(tmp_in.name)
    trimmed_audio = audio[500:]
    tmp_out_path = tmp_in.name.replace(".webm", "_cut.wav")
    trimmed_audio.export(tmp_out_path, format="wav")

    with open(tmp_out_path, "rb") as f:
        user_result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f
        )
    user_transcribed = user_result.text

    wer_score = calculate_wer(original_transcribed, user_transcribed)
    diff_user = get_diff_html(original_transcribed, user_transcribed, mode='user')
    diff_original = get_diff_html(original_transcribed, user_transcribed, mode='original')

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user": request.form.get("username", "anonymous"),
        "genre": request.form.get("genre", ""),
        "level": request.form.get("level", ""),
        "wer": round(wer_score * 100, 2),
        "original_transcribed": original_transcribed,
        "user_transcribed": user_transcribed,
        "script_excerpt": original_transcribed[:100]
    }

    save_preset_log(log_entry)

    return jsonify({
        "original_transcribed": original_transcribed,
        "user_transcribed": user_transcribed,
        "wer": round(wer_score * 100, 2),
        "diff_user": diff_user,
        "diff_original": diff_original
    })

@app.route("/api/highest_levels/<username>")
def get_highest_levels(username):
    import json
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


@app.route("/api/log_attempt", methods=["POST"])
def log_attempt():
    data = request.json

    required_fields = ["user", "genre", "level", "wer", "original_transcribed", "user_transcribed"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    log_entry = PracticeLog(
        user_id=data["user"],
        genre=data["genre"],
        level=data["level"],
        wer=float(data["wer"]),
        original_text=data["original_transcribed"],
        user_text=data["user_transcribed"],
        practiced_at=datetime.utcnow()
    )

    db.session.add(log_entry)
    db.session.commit()

    return jsonify({"message": "Logged successfully"})

@app.route('/api/save_material', methods=['POST'])
@auth_required
def save_material():
    try:
        user_id = request.headers.get('X-Replit-User-Id')
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        if 'audio' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400

        audio_file = request.files['audio']
        material_name = request.form.get('material_name', '').strip()

        if not material_name:
            return jsonify({"error": "Material name is required"}), 400

        if not audio_file.filename:
            return jsonify({"error": "No audio file selected"}), 400

        material_id = uuid.uuid4().hex
        file_ext = os.path.splitext(audio_file.filename)[1].lower()
        object_storage_key = f"user_audio/{user_id}/{material_id}{file_ext}"

        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{material_id}{file_ext}")
        audio_file.save(temp_path)

        with open(temp_path, 'rb') as f:
            storage_client.upload_file(object_storage_key, f)

        transcript = transcribe_audio(temp_path)

        os.remove(temp_path)

        material_data = {
            "user_id": user_id,
            "material_name": material_name,
            "object_storage_key": object_storage_key,
            "transcript": transcript,
            "upload_timestamp": datetime.now().isoformat()
        }

        db[f"material_{user_id}_{material_id}"] = material_data

        return jsonify({
            "success": True,
            "material_id": material_id,
            "material_name": material_name
        })

    except Exception as e:
        print(f"Error saving material: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/my_materials', methods=['GET'])
@auth_required
def list_materials():
    try:
        user_id = request.headers.get('X-Replit-User-Id')
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        prefix = f"material_{user_id}_"
        user_materials = []

        for key in database.prefix(prefix):
            material_data = db[key]
            material_id = key.replace(prefix, '')

            user_materials.append({
                "material_id": material_id,
                "material_name": material_data["material_name"],
                "upload_timestamp": material_data["upload_timestamp"]
            })

        user_materials.sort(key=lambda x: x["upload_timestamp"], reverse=True)

        return jsonify({
            "materials": user_materials
        })

    except Exception as e:
        print(f"Error listing materials: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/sentence-practice')
def sentence_practice():
    return render_template('sentence_practice.html')

@app.route('/compare')
def compare():
    return render_template('compare.html')

@app.route('/api/compare_passages', methods=['POST'])
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

@app.route('/api/sentence_structure')
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

@app.route('/api/sentences/<genre>/<level>')
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

@app.route('/api/practice/logs', methods=['POST'])
@auth_required
def log_practice():
    try:
        user_id = request.headers.get('X-Replit-User-Id')
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        data = request.json
        if not data or 'recording_id' not in data or 'wer' not in data:
            return jsonify({"error": "Missing required fields"}), 400

        log = PracticeLog(
            user_id=user_id,
            recording_id=data['recording_id'],
            wer=float(data['wer'])
        )

        db.session.add(log)
        db.session.commit()

        return jsonify({
            "status": "ok",
            "id": log.id
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/recordings', methods=['GET'])
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

@app.route('/api/recordings/last', methods=['GET'])
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