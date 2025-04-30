from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from flask_cors import CORS
from functools import wraps
from flask import send_from_directory
import uuid
from datetime import datetime
from replit import db
from replit.database import database
from replit.object_storage import Client as ObjectStorageClient

def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get('X-Replit-User-Id')
        if not user_id:
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function
from transcribe_utils import transcribe_audio
import os
from werkzeug.utils import secure_filename
from pydub import AudioSegment
from wer_utils import wer, calculate_wer
from diff_viewer import diff_html
import json

import shutil  # ファイルコピー用のモジュールを追加
from youtube_utils import youtube_bp
from youtube_utils import check_captions
from diff_viewer import get_diff_html

from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import openai

# .env ファイルの読み込みを削除

#api_key = os.environ.get("YOUTUBE_API_KEY")
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# === Flask設定 ===
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev_key_only')  # Use environment variable
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Max 16MB upload
app.register_blueprint(youtube_bp)
CORS(app) # Enable CORS
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Object Storage client
storage_client = ObjectStorageClient()

from flask import session

#API化
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

# ジャンル×レベルごとの最小WERクロス表を生成する関数
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

#
def save_preset_log(data, log_path="preset_log.json"):
    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
        else:
            logs = []

        logs.append(data)

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        print(f"[ログ保存成功] {data}")  # 👈 この行を追加！
    except Exception as e:
        print(f"[ログ保存エラー] {e}")
        return jsonify({"error": str(e)}), 500      # ← 原因をそのまま返す



# === ルート画面 ===
@app.route('/__replauthlogout')
def logout():
    response = '', 200
    return response

@app.route('/')
def index():
    user_id = request.headers.get('X-Replit-User-Id')
    user_name = request.headers.get('X-Replit-User-Name')

    if not user_id:
        return render_template('index.html')

    return render_template('index.html',
                         user_id=user_id,
                         user_name=user_name)


from flask import render_template
from collections import defaultdict
import json
from datetime import datetime, timedelta


# /dashboard/<username> のルート定義
@app.route("/dashboard/<username>")
@auth_required
def dashboard(username):
    try:
        with open("preset_log.json", "r", encoding="utf-8") as f:
            logs = json.load(f)
    except Exception as e:
        return f"Error loading log: {e}"

    # 連続記録日数を計算
    user_logs = [log for log in logs if log.get("user", "").lower() == username.lower()]
    date_set = {datetime.fromisoformat(log["timestamp"]).date() for log in user_logs if "timestamp" in log}
    streak = 0
    today = datetime.utcnow().date()
    while today in date_set:
        streak += 1
        today -= timedelta(days=1)

    # WERマトリクスの取得（最小WER）
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

    # 該当ログだけ抽出
    user_logs = [
        log for log in logs
        if log.get("user", "").lower() == username.lower()
        and log.get("genre") == genre
        and log.get("level") == level
    ]

    # 新しいテンプレートに渡す
    return render_template("detail.html",
                           username=username,
                           genre=genre,
                           level=level,
                           logs=user_logs)



@app.route("/read-aloud", methods=["GET", "POST"])
def read_aloud():
    if request.method == "GET":
        return render_template("read_aloud.html")

    # === 正解テキストの取得 ===
    reference_text = request.form.get("reference_text", "").strip()
    reference_file = request.files.get("reference_file")
    if reference_file and reference_file.filename.endswith(".txt"):
        reference_text = reference_file.read().decode("utf-8").strip()

    # === 音声ファイルの取得 ===
    audio_file = request.files["audio_file"]
    audio_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(audio_file.filename))
    audio_file.save(audio_path)

    # === 音声の文字起こし ===
    recognized_text = transcribe_audio(audio_path)

    # === 精度チェック（WER & 差分） ===
    wer_score = wer(reference_text, recognized_text)
    diff_result = diff_html(reference_text, recognized_text)

    # === 結果ページに渡す ===
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
    from openai import OpenAI
    import tempfile
    from wer_utils import calculate_wer

    audio_file = request.files['audio']
    transcript_text = request.form['transcript']

    # Whisper 1.0 形式のクライアントを使う
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


#Flaskに「/presets/ は静的ファイルです」と教える
@app.route("/presets/<path:filename>")
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

    # 🔍 ログイン中ユーザー名をlocalStorageから取得して送る（JS側で取得→埋め込む方法にする）
    current_user = request.cookies.get("username", "anonymous")

    matched = [entry for entry in logs if entry["genre"] == genre and entry["level"] == level]
    sorted_entries = sorted(matched, key=lambda x: x["wer"])

    return render_template("ranking.html",
                           rankings=sorted_entries,
                           genre=genre, level=level,
                           current_user=current_user)

#Userのアンロックレベルを確認
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

    # セットをリストに変換
    result = {genre: sorted(list(levels)) for genre, levels in result.items()}
    return result


#
@app.route("/api/presets")
def api_presets():
    structure = get_presets_structure()
    return jsonify(structure)


# === 音声ファイルと入力の受信 ===
@app.route('/submit', methods=['POST'])
def submit():
    user_id = request.form['user_id']
    script = request.form['script']
    file = request.files['audio']

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # 🔄 static にコピー（上書き）
    static_path = os.path.join("static", "recorded.webm")
    shutil.copy(filepath, static_path)  # ← 変更ポイント！

    # 🔍 Whisperで文字起こし
    transcript = transcribe_audio(filepath)

    # 📊 WER計算
    wer_score, subs, dels, ins, word_count = wer(script, transcript)

    # HTML差分を生成
    diff_result = diff_html(script, transcript)

    # 📁 ログ情報
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


    # 結果を表示
    # 結果ページに必要な情報を渡す
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



@app.route("/check_subtitles", methods=["GET"])
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
    from openai import OpenAI
    import tempfile
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

        # Create temporary file
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
                # Clean up temp file
                import os
                if os.path.exists(tmp.name):
                    os.remove(tmp.name)

        wer_score = calculate_wer(transcribed, transcript_text)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # 差分をHTMLで生成
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
def upload_custom_audio():
    try:
        if 'audio' not in request.files:
            return jsonify({"error": "音声ファイルが選択されていません"}), 400

        audio_file = request.files['audio']
        if not audio_file.filename:
            return jsonify({"error": "ファイルが選択されていません"}), 400

        # Read file content to check if it's valid
        audio_content = audio_file.read()
        if len(audio_content) == 0:
            return jsonify({"error": "アップロードされたファイルが空です"}), 400
        audio_file.seek(0)  # Reset file pointer

        # Check file extension
        allowed_extensions = {'mp3', 'm4a', 'wav', 'webm'}  # Added webm support
        if not any(audio_file.filename.lower().endswith(ext) for ext in allowed_extensions):
            return jsonify({"error": "未対応のファイル形式です。MP3, M4A, WAV, WEBM形式のファイルを使用してください。"}), 400

        # Check file size (limit to 25MB)  ← 先ほど読み取った audio_content を再利用
        if len(audio_content) > 25 * 1024 * 1024:
            return jsonify({"error": "ファイルサイズが大きすぎます。25MB以下のファイルを使用してください。"}), 400
        audio_file.seek(0)  # ★ save() 前に必ずリセット

        # Save uploaded file
        filename = secure_filename(audio_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        audio_file.save(filepath)

        # Transcribe audio using existing utility
        try:
            transcription = transcribe_audio(filepath)
            session['custom_transcription'] = transcription
            return jsonify({
                "audio_url": f"/uploads/{filename}",
                "transcription": transcription
            })
        except Exception as e:
            print(f"Transcription error: {str(e)}")
            return jsonify({"error": str(e)}), 500      # ← 原因をそのまま返す

    except Exception as e:
        print(f"Upload error: {str(e)}")
        return jsonify({"error": str(e)}), 500      # ← 原因をそのまま返す

@app.route('/evaluate_custom_shadowing', methods=['POST'])
def evaluate_custom_shadowing():
    if 'recorded_audio' not in request.files:
        return jsonify({"error": "No recorded audio provided"}), 400

    if 'custom_transcription' not in session:
        return jsonify({"error": "Original transcription not found"}), 400

    # Known warm-up transcript
    WARMUP_TRANSCRIPT = "10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0"
    original_transcription = session['custom_transcription']
    recorded_audio = request.files['recorded_audio']

    # Save recorded audio
    tmp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'tmp_recording.webm')
    recorded_audio.save(tmp_path)

    # Process recorded audio (just remove initial silence)
    audio = AudioSegment.from_file(tmp_path)
    processed_path = tmp_path.replace('.webm', '_processed.wav')
    audio.export(processed_path, format="wav")

    # Transcribe user's full recording
    full_transcription = transcribe_audio(processed_path)

    # Generate all possible suffixes of the warm-up transcript
    numbers = WARMUP_TRANSCRIPT.split(", ")
    suffixes = [", ".join(numbers[i:]) for i in range(len(numbers))]
    suffixes.sort(key=len, reverse=True)  # Sort by length, longest first

    # Remove warm-up portion from transcription
    user_transcription = full_transcription.lower()
    matched_suffix = None

    # Find the longest matching suffix at the start of transcription
    for suffix in suffixes:
        if user_transcription.strip().startswith(suffix.lower()):
            matched_suffix = suffix
            break

    # Remove the matched suffix if found
    if matched_suffix:
        start_pos = user_transcription.find(matched_suffix.lower())
        if start_pos != -1:
            user_transcription = user_transcription[start_pos + len(matched_suffix):].strip()

    # Calculate WER and generate diff using main portion only
    # wer_score = calculate_wer(original_transcription, user_transcription)
    # diff_result = diff_html(original_transcription, user_transcription)
    wer_score = calculate_wer(user_transcription, original_transcription)
    diff_result = diff_html(user_transcription, original_transcription)

    # Cleanup temporary files
    os.remove(tmp_path)
    os.remove(processed_path)

    return jsonify({
        "wer": round(wer_score * 100, 2),
        "diff_html": diff_result
    })


@app.route('/evaluate_shadowing', methods=['POST'])
def evaluate_shadowing():
    from openai import OpenAI
    import tempfile
    from wer_utils import calculate_wer

    original_audio = request.files['original_audio']
    recorded_audio = request.files['recorded_audio']

    client = OpenAI()

    # === フォームから情報取得 ===
    genre = request.form.get("genre", "")
    level = request.form.get("level", "")
    username = request.form.get("username", "anonymous")

    # === 教材スクリプトを script.txt から取得（Whisperは使わない）
    script_path = os.path.join("presets", "shadowing", genre, level, "script.txt")
    if not os.path.exists(script_path):
        return jsonify({"error": f"Script not found at: {script_path}"}), 400
    if not os.path.exists(script_path):
        return jsonify({"error": f"Script not found at: {script_path}"}), 400

    with open(script_path, "r", encoding="utf-8") as f:
        original_transcribed = f.read().strip()

    # === 録音ファイルの先頭500msをカット ===
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_in:
        recorded_audio.save(tmp_in.name)

    # pydubで加工 → 一時ファイルへ保存
    audio = AudioSegment.from_file(tmp_in.name)
    trimmed_audio = audio[500:]  # 500msカット
    tmp_out_path = tmp_in.name.replace(".webm", "_cut.wav")
    trimmed_audio.export(tmp_out_path, format="wav")

    # Whisperで文字起こし
    with open(tmp_out_path, "rb") as f:
        user_result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f
        )
    user_transcribed = user_result.text
    # === 精度評価
    wer_score = calculate_wer(original_transcribed, user_transcribed)
    diff_user = get_diff_html(original_transcribed, user_transcribed, mode='user')
    diff_original = get_diff_html(original_transcribed, user_transcribed, mode='original')

    # ログを保存
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "user": request.form.get("username", "anonymous"),  # ←ここが動的に！
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

    log_entry = {
        "user": data["user"],
        "genre": data["genre"],
        "level": data["level"],
        "wer": float(data["wer"]),
        "original_transcribed": data["original_transcribed"],
        "user_transcribed": data["user_transcribed"],
        "timestamp": datetime.now().isoformat()
    }

    log_file = "preset_log.json"
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            logs = json.load(f)
    else:
        logs = []

    logs.append(log_entry)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

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

        # Generate unique ID and prepare storage key
        material_id = uuid.uuid4().hex
        file_ext = os.path.splitext(audio_file.filename)[1].lower()
        object_storage_key = f"user_audio/{user_id}/{material_id}{file_ext}"

        # Save audio to temporary path for transcription
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_{material_id}{file_ext}")
        audio_file.save(temp_path)

        # Upload to Object Storage
        with open(temp_path, 'rb') as f:
            storage_client.upload_file(object_storage_key, f)

        # Transcribe audio
        transcript = transcribe_audio(temp_path)

        # Clean up temporary file
        os.remove(temp_path)

        # Prepare and save material data
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
        return jsonify({"error": str(e)}), 500      # ← 原因をそのまま返す

@app.route('/api/my_materials', methods=['GET'])
@auth_required
def list_materials():
    try:
        user_id = request.headers.get('X-Replit-User-Id')
        if not user_id:
            return jsonify({"error": "User not authenticated"}), 401

        # Get all materials for this user
        prefix = f"material_{user_id}_"
        user_materials = []

        # Use prefix to find all materials for this user
        for key in database.prefix(prefix):
            material_data = db[key]
            material_id = key.replace(prefix, '')

            user_materials.append({
                "material_id": material_id,
                "material_name": material_data["material_name"],
                "upload_timestamp": material_data["upload_timestamp"]
            })

        # Sort by upload timestamp, newest first
        user_materials.sort(key=lambda x: x["upload_timestamp"], reverse=True)

        return jsonify({
            "materials": user_materials
        })

    except Exception as e:
        print(f"Error listing materials: {str(e)}")
        return jsonify({"error": str(e)}), 500      # ← 原因をそのまま返す

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


# === アプリ実行（Replitでは不要、ローカル用） ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use port 5000 for development
    app.run(host="0.0.0.0", port=port, debug=True)