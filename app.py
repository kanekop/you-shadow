# Standard library imports
import os
import uuid
import math
import json
import tempfile
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps

# Third-party imports
import pandas as pd
import openai
from pydub import AudioSegment
from flask import (
    Flask, render_template, request, redirect, url_for, 
    jsonify, send_from_directory, session, current_app
)
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.utils import secure_filename

# Local imports
from models import db, Material, AudioRecording, PracticeLog
from transcribe_utils import transcribe_audio
from wer_utils import wer, calculate_wer
from diff_viewer import diff_html, get_diff_html
from youtube_utils import youtube_bp, check_captions
from config import config_by_name # config.pyから設定辞書をインポート
from core.responses import api_error_response # core/responses.py を作成した場合

import os # osモジュールのインポートを確認
import uuid # uuidモジュールのインポートを確認
from flask import jsonify, request, session # sessionをインポート
from pydub import AudioSegment # pydubのインポートを確認
# (他の必要なインポートも確認してください: app, db, PracticeLog, transcribe_audio, calculate_wer, diff_html, auth_required, handle_transcription_error など)

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
app.config.from_object('config')
# 環境変数 FLASK_CONFIG (ReplitのSecretsで設定) に基づいて設定を読み込む
# Secretsに FLASK_CONFIG がなければ 'dev' (開発モード) をデフォルトとする
config_name = os.getenv('FLASK_CONFIG', 'dev')
app.config.from_object(config_by_name[config_name])

# Configクラスのinit_appメソッドを呼び出す (フォルダ作成などを行う場合)
# この呼び出しは、app.configに設定がロードされた後に行う
config_by_name[config_name].init_app(app)


# APIキーの存在チェック (特に本番環境で重要)
if config_name == 'prod':
    if not app.config.get('OPENAI_API_KEY'):
        app.logger.error("FATAL: OPENAI_API_KEY is not set for production.")
        # ここでアプリケーションを停止させるか、エラー処理を行う
    if not app.config.get('SECRET_KEY') or app.config.get('SECRET_KEY') == 'a_very_secret_key_that_should_be_changed':
        app.logger.warning("WARNING: SECRET_KEY is not set or is using the default weak key in production.")

migrate = Migrate(app, db)

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

# 共通のエラーハンドリング用ヘルパー関数 (任意だが推奨)
def handle_transcription_error(e, context_message="文字起こしエラー"):
    error_message_detail = str(e)
    error_type_name = type(e).__name__
    status_code = 500  # デフォルトはサーバーエラー

    # エラーの型に応じたステータスコードとユーザー向けメッセージの調整
    user_friendly_message = f"{context_message}: 予期せぬエラーが発生しました。"

    if isinstance(e, FileNotFoundError):
        status_code = 404
        user_friendly_message = f"{context_message}: 指定されたファイルが見つかりません。"
    elif isinstance(e, ValueError):  # 例: ファイルが空、サイズ超過、不正な値など
        status_code = 400
        user_friendly_message = f"{context_message}: リクエスト内容が正しくありません ({error_message_detail})。"
    elif isinstance(e, PermissionError):  # 例: OpenAI APIキー関連など
        status_code = 401 # または 403 Forbidden
        user_friendly_message = f"{context_message}: 処理に必要な権限がありません。"
    elif isinstance(e, ConnectionError):  # 例: OpenAI API接続エラーなど
        status_code = 503  # Service Unavailable
        user_friendly_message = f"{context_message}: 外部サービスへの接続に失敗しました。しばらくしてから再度お試しください。"

    # 特定のライブラリのエラーに対する処理 (例: openai)
    # try:
    #     import openai
    #     if isinstance(e, openai.RateLimitError):
    #         status_code = 429 # Too Many Requests
    #         user_friendly_message = f"{context_message}: リクエストがレート制限を超えました。時間をおいて再試行してください。"
    #     elif isinstance(e, openai.AuthenticationError):
    #         status_code = 401
    #         user_friendly_message = f"{context_message}: API認証に失敗しました。設定を確認してください。"
    #     elif isinstance(e, openai.APIError): # その他のOpenAI APIエラー
    #         status_code = 502 # Bad Gateway (API側の問題)
    #         user_friendly_message = f"{context_message}: 外部APIでエラーが発生しました。"
    # except ImportError:
    #     pass # openai ライブラリがない場合はスキップ

    # 詳細なエラー情報をログに記録
    current_app.logger.error(
        f"Transcription Error Context: {context_message} | "
        f"Error Type: {error_type_name} | "
        f"Detail: {error_message_detail} | "
        f"Responding with Status: {status_code}"
    )

    # 500番台のエラーの場合、ユーザーにはより汎用的なメッセージを返すことを検討
    if status_code >= 500:
        user_friendly_message = "サーバー処理中に予期せぬエラーが発生しました。しばらくしてから再試行してください。"

    return api_error_response(user_friendly_message, status_code)

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
    # openai.OpenAI() の初期化はグローバルスコープで行われているのでここでは不要
    # from wer_utils import calculate_wer # 関数の先頭またはグローバルでインポート

    tmp_path = None # finally で参照できるように初期化
    try:
        if 'audio' not in request.files:
            return api_error_response('音声ファイルが提供されていません。', 400)
        if 'transcript' not in request.form or not request.form['transcript']:
            return api_error_response('文字起こしテキストが提供されていません。', 400)

        audio_file = request.files['audio']
        original_transcript_text = request.form['transcript']

        # 一時ファイルに保存
        # suffix はファイル形式に合わせて適切に（例: .webm, .mp3など Whisperが受け付けるもの）
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        # 文字起こし (transcribe_utils を利用)
        user_transcribed_text = transcribe_audio(tmp_path) # transcribe_audio内でエラーハンドリングされている

        # WER計算 (参照テキストと仮説テキストの順序に注意)
        wer_score_val = calculate_wer(original_transcript_text, user_transcribed_text)
        # 差分表示 (参照テキストと仮説テキストの順序に注意)
        diff_result_html = diff_html(original_transcript_text, user_transcribed_text)

        return jsonify({
            "transcribed": user_transcribed_text,
            "wer": round(wer_score_val * 100, 2), # WERは通常%表記
            "diff_html": diff_result_html
        })

    except openai.APIError as e: # OpenAI API特有のエラーを先にキャッチ
        # transcribe_utilsから伝播してきたOpenAIのエラーをここでハンドリング
        # または、transcribe_utils側でより汎用的な例外にラップして投げる
        return handle_transcription_error(e, "YouTube音声評価中の文字起こしエラー")
    except IOError as e:
        print(f"!! ファイル操作エラー (/evaluate_youtube): {e}")
        return api_error_response(f"ファイルの読み書き中にエラーが発生しました: {e}", 500)
    except Exception as e:
        # その他の予期せぬエラー
        print(f"!! 予期せぬエラー (/evaluate_youtube): {e}")
        # handle_transcription_error を使うか、api_error_response を使うかは一貫性を持たせる
        return api_error_response(f"評価処理中に予期せぬエラーが発生しました。", 500)
    finally:
        # 一時ファイルの削除
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError as e:
                print(f"!! 一時ファイル削除エラー ({tmp_path}): {e}")




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

# --- /upload_custom_audio の修正 ---
@app.route('/upload_custom_audio', methods=['POST'])
@auth_required
def upload_custom_audio():
    user_id = request.headers.get('X-Replit-User-Id')
    # user_id チェックは @auth_required が担当する想定だが、念のため
    if not user_id:
        # 通常 @auth_required で処理されるが、明示的に書く場合
        return jsonify({"error": "User not authenticated"}), 401

    if 'audio' not in request.files:
        return jsonify({"error": "音声ファイルが選択されていません"}), 400

    audio_file = request.files['audio']
    if not audio_file or audio_file.filename == '':
        return jsonify({"error": "無効なファイルです"}), 400

    # ファイル拡張子チェック
    file_ext = os.path.splitext(audio_file.filename)[1].lower()
    allowed_extensions = ['.mp3', '.m4a', '.wav', '.mpga', '.mpeg', '.webm']
    if file_ext not in allowed_extensions:
        return jsonify({"error": f"サポートされていないファイル形式です: {file_ext}"}), 400

    # 一意なファイル名を生成して保存
    filename_base = secure_filename(f"{user_id}_{uuid.uuid4().hex}")
    original_filename = f"{filename_base}_original{file_ext}"
    original_filepath = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)

    # 一時的なチャンクファイルのパスを保持するリスト
    processed_chunk_paths = []
    final_transcription = ""

    try:
        audio_file.save(original_filepath)
        print(f"一時ファイル保存先: {original_filepath}")

        file_size = os.path.getsize(original_filepath)
        print(f"ファイルサイズ: {file_size / (1024*1024):.2f} MB")

        # Whisperのサイズ制限 (transcribe_audio内でチェックされるが、ここでも事前チェック可能)
        MAX_WHISPER_SIZE = 25 * 1024 * 1024

        if file_size > MAX_WHISPER_SIZE:
            # サイズが大きい場合はチャンク処理 (既存ロジック)
            print("ファイルサイズが上限を超えています。分割処理を開始します...")
            audio = AudioSegment.from_file(original_filepath)
            duration_ms = len(audio)
            print(f"音声の長さ: {duration_ms / 1000:.2f} 秒")

            # チャンク設定 (例: 10分ごと、5秒オーバーラップ)
            TARGET_CHUNK_DURATION_MS = 10 * 60 * 1000
            CHUNK_OVERLAP_MS = 5000

            transcribed_parts = []
            num_chunks = math.ceil(duration_ms / (TARGET_CHUNK_DURATION_MS - CHUNK_OVERLAP_MS)) if (TARGET_CHUNK_DURATION_MS - CHUNK_OVERLAP_MS) > 0 else 1
            print(f"推定チャンク数: {num_chunks}")

            current_pos_ms = 0
            for chunk_index in range(num_chunks):
                start_ms = max(0, current_pos_ms - CHUNK_OVERLAP_MS)
                end_ms = min(current_pos_ms + TARGET_CHUNK_DURATION_MS, duration_ms)
                print(f"  チャンク {chunk_index + 1}/{num_chunks}: {start_ms/1000:.1f}s - {end_ms/1000:.1f}s")

                # メモリ上でチャンクを作成
                chunk = audio[start_ms:end_ms]

                # 一時ファイルにチャンクを書き出し
                with tempfile.NamedTemporaryFile(
                    prefix=f"{filename_base}_chunk_{chunk_index}_",
                    suffix=".mp3", # Whisperが扱いやすい形式で出力
                    dir=app.config['UPLOAD_FOLDER'],
                    delete=False # transcribe_audioに渡すため削除しない
                ) as tmp_chunk_file:
                    chunk_filepath = tmp_chunk_file.name
                    print(f"    チャンクファイル書き出し中: {chunk_filepath}")
                    chunk.export(chunk_filepath, format="mp3")
                    processed_chunk_paths.append(chunk_filepath) # 削除リストに追加

                print(f"    チャンク {chunk_index + 1} 文字起こし中...")
                # ここで transcribe_audio を呼び出し、エラーハンドリング
                try:
                    transcript_part = transcribe_audio(chunk_filepath)
                    transcribed_parts.append(transcript_part)
                    print(f"    チャンク {chunk_index + 1} 文字起こし完了.")
                except Exception as transcribe_err:
                    # チャンク処理中のエラーハンドリング
                    print(f"!! チャンク {chunk_index + 1} の文字起こしエラー: {transcribe_err}")
                    # エラーが発生したら、処理を中断してエラーレスポンスを返す
                    raise transcribe_err # 上位のtry...exceptで捕捉させる

                # 次のチャンクの開始位置を計算
                current_pos_ms += TARGET_CHUNK_DURATION_MS
                # ループの最後で current_pos_ms が duration_ms を超えてもループは終了する

            # 全てのチャンクの文字起こし結果を結合
            final_transcription = " ".join(transcribed_parts).strip()
            print("全てのチャンクの文字起こしを結合しました。")

        else:
            # ファイルサイズが小さい場合は直接文字起こし
            print("ファイルサイズは上限内です。直接文字起こしします...")
            # ここで transcribe_audio を呼び出し、エラーハンドリング
            final_transcription = transcribe_audio(original_filepath)
            print("直接文字起こし完了。")

        # データベースにMaterialを保存 (成功した場合のみ)
        print("データベースにMaterialを保存します...")
        new_material = Material(
            user_id=user_id,
            material_name=audio_file.filename, # 元のファイル名を使用
            storage_key=original_filepath, # 保存したファイルのパス
            transcript=final_transcription,
            upload_timestamp=datetime.utcnow()
        )
        db.session.add(new_material)
        db.session.commit()
        print(f"Material ID: {new_material.id} でデータベースに保存しました。")

        # セッションに情報を保存 (ただし、前述の通りIDのみをクライアントに返す方が堅牢)
        session['current_material_id'] = new_material.id
        session['custom_transcription'] = final_transcription # 評価時に使うなら保持

        return jsonify({
            "audio_url": url_for('serve_upload', filename=original_filename),
            "transcription": final_transcription,
            "material_id": new_material.id # Material ID を返す
        })

    except Exception as e:
        # 統一されたエラーハンドリング (DBロールバックも考慮)
        db.session.rollback() # エラー時はDBへの変更を取り消す
        # transcribe_audio 内で発生した特定のエラーもここで捕捉される
        return handle_transcription_error(e, "/upload_custom_audio でのエラー")

    finally:
        # チャンク処理で使用した一時ファイルを削除
        print("一時チャンクファイルを削除します...")
        for path in processed_chunk_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"  削除: {path}")
                except OSError as del_err:
                    print(f"!! 一時ファイル削除エラー ({path}): {del_err}")
        # DBセッションのクリーンアップ (リクエスト終了時に自動で行われることが多いが明示的に行う場合)
        # db.session.remove()

#AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA

# --- /evaluate_custom_shadowing の修正案 ---

@app.route('/evaluate_custom_shadowing', methods=['POST'])
@auth_required
def evaluate_custom_shadowing():
    user_id = request.headers.get('X-Replit-User-Id')
    if not user_id: # @auth_required があれば不要な場合もあるが、念のため
        return jsonify({"error": "User not authenticated"}), 401

    # --- 修正箇所：original_transcription と material_id を先に取得 ---
    material_id = session.get('current_material_id')
    original_transcription = session.get('custom_transcription')

    if not material_id:
        return jsonify({"error": "元の教材IDが見つかりません。再度アップロードからお試しください。"}), 400
    if not original_transcription:
        # material_id がある場合、DBから再取得を試みることも可能 (オプション)
        # current_material = Material.query.get(material_id)
        # if current_material and current_material.transcript:
        #    original_transcription = current_material.transcript
        # else:
        return jsonify({"error": "元の文字起こし情報が見つかりません。再度アップロードからお試しください。"}), 400
    # --- 修正箇所ここまで ---

    if 'recorded_audio' not in request.files:
        return jsonify({"error": "録音された音声ファイルが提供されていません"}), 400

    recorded_audio = request.files['recorded_audio']
    if not recorded_audio or recorded_audio.filename == '':
        return jsonify({"error": "無効な録音ファイルです"}), 400


    tmp_path = None
    processed_path = None
    # user_transcription = "" # tryブロック内で定義されるため、ここでは不要でも良い

    try:
        original_filename_for_log = recorded_audio.filename if recorded_audio.filename else "unknown_custom_audio"
        tmp_suffix = os.path.splitext(original_filename_for_log)[1].lower()
        if not tmp_suffix or tmp_suffix not in ['.webm', '.mp3', '.m4a', '.wav']: # 一般的な拡張子を想定
            tmp_suffix = '.webm' # デフォルト

        base_name = f'tmp_eval_recording_{user_id}_{uuid.uuid4().hex}'
        tmp_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{base_name}{tmp_suffix}')
        recorded_audio.save(tmp_path)
        print(f"Saved temporary recorded file to: {tmp_path}")

        processed_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{base_name}_processed.wav')
        print(f"Intended processed_path for evaluation: {processed_path}")

        print(f"Converting recorded audio {tmp_path} to {processed_path} for transcription")
        audio = AudioSegment.from_file(tmp_path)
        # ここで pydub の from_file が失敗する可能性も考慮 (例: 非対応フォーマット、壊れたファイル)
        # from_file が失敗した場合、FileNotFoundError ではなく pydub.exceptions.CouldntDecodeError などが発生する
        audio.export(processed_path, format="wav")
        print(f"Successfully converted recorded audio to {processed_path}")

        print(f"Transcribing processed recorded audio {processed_path}...")
        full_transcription = transcribe_audio(processed_path)
        # full_transcription が空文字列や予期せぬ値の場合のハンドリングも考慮するとより堅牢
        print(f"Full transcription of recorded audio (first 100 chars): {full_transcription[:100]}...")

        # ウォームアップ除去ロジック
        WARMUP_TRANSCRIPT = "10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0" # 定数として定義が良い
        user_transcription_for_eval = full_transcription # ウォームアップ除去前のものを保持

        # 修正されたウォームアップ除去ロジック (以前の会話で提案されたもの)
        numbers = WARMUP_TRANSCRIPT.split(", ")
        possible_warmup_suffixes = [", ".join(numbers[i:]) for i in range(len(numbers))]
        possible_warmup_suffixes.sort(key=len, reverse=True) # 長いものからマッチさせる

        matched_suffix_found = None
        normalized_full_recorded_transcription = full_transcription.lower().strip()

        for suffix_candidate in possible_warmup_suffixes:
            if normalized_full_recorded_transcription.startswith(suffix_candidate.lower()):
                # 除去するサフィックスの実際のテキスト (大文字・小文字を保持) を取得
                # full_transcription の先頭から suffix_candidate と同じ長さの部分文字列を取得
                actual_removed_part_length = len(suffix_candidate)
                user_transcription_for_eval = full_transcription[actual_removed_part_length:].lstrip(" ,") # 先頭の空白やコンマも除去
                matched_suffix_found = suffix_candidate
                print(f"Warm-up part '{matched_suffix_found}' removed. User transcription for eval: {user_transcription_for_eval[:100]}...")
                break

        if not matched_suffix_found:
            print("Warm-up part not clearly identified or not present in transcription.")
            # ウォームアップが見つからなかった場合、そのまま full_transcription を使う
            user_transcription_for_eval = full_transcription


        wer_score = calculate_wer(original_transcription, user_transcription_for_eval)
        diff_result_html = diff_html(original_transcription, user_transcription_for_eval) # diff_html にも修正版を渡す

        print(f"WER calculated: {wer_score*100:.2f}%")

        # データベースへの保存
        new_log = PracticeLog(
            user_id=user_id,
            practice_type='custom', # 明示的に 'custom'
            material_id=material_id, # session から取得した material_id
            recording_id=None, # カスタム練習では recording_id は通常使わない (使途による)
            wer=round(wer_score * 100, 2),
            original_text=original_transcription,
            user_text=user_transcription_for_eval, # ウォームアップ除去後
            practiced_at=datetime.utcnow() # タイムスタンプを追加すると良い
        )
        db.session.add(new_log)
        db.session.commit()
        print(f"PracticeLog saved with ID: {new_log.id}")

        return jsonify({
            "wer": round(wer_score * 100, 2),
            "diff_html": diff_result_html,
            "original_transcription": original_transcription, # 教材の文字起こし
            "user_transcription": user_transcription_for_eval # ユーザーの文字起こし（ウォームアップ除去後）
            # "full_user_transcription": full_transcription # 参考情報としてウォームアップ除去前のものも返すか検討
        })

    except FileNotFoundError as e:
        db.session.rollback()
        error_msg = f"ファイル処理中にエラーが発生しました (ファイルが見つからないか、アクセスできませんでした): {e}"
        print(f"!! FileNotFoundError in /evaluate_custom_shadowing: {e} (tmp: {tmp_path}, proc: {processed_path})")
        return jsonify({"error": error_msg }), 404 # or 500
    except openai.APIError as e: # transcribe_audio から来る可能性のある OpenAI API エラー
        db.session.rollback()
        print(f"!! OpenAI API Error in /evaluate_custom_shadowing: {e}")
        # handle_transcription_error があればそれを使う
        return handle_transcription_error(e, "文字起こし処理中にAPIエラーが発生しました。")
    except Exception as e:
        db.session.rollback()
        # 予期せぬエラーの詳細をログに出力
        import traceback
        print(f"!! Unexpected error in /evaluate_custom_shadowing (tmp: {tmp_path}, proc: {processed_path}): {e}\n{traceback.format_exc()}")
        # クライアントには汎用的なメッセージを返すか、handle_transcription_error を使う
        return jsonify({"error": f"評価処理中に予期せぬエラーが発生しました。管理者に連絡してください。"}), 500
    finally:
        # 一時ファイルの削除
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                print(f"Deleted temporary file: {tmp_path}")
            except OSError as e_os:
                print(f"!! Error deleting temporary file {tmp_path}: {e_os}")
        if processed_path and os.path.exists(processed_path):
            try:
                os.remove(processed_path)
                print(f"Deleted processed file: {processed_path}")
            except OSError as e_os:
                print(f"!! Error deleting processed file {processed_path}: {e_os}")
        # db.session.remove() # Flask-SQLAlchemyでは通常不要
#ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ
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

    user_transcribed = ""
    tmp_in_path = None
    tmp_out_path = None # finally で削除するために定義

    try:
        # --- 文字起こし部分 ---
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_in:
            recorded_audio.save(tmp_in.name)
            tmp_in_path = tmp_in.name # finallyで使うために保持

        audio = AudioSegment.from_file(tmp_in_path)
        trimmed_audio = audio[500:] # 冒頭500msカット (以前のロジック)
        tmp_out_path = tmp_in_path.replace(".webm", "_cut.wav")
        trimmed_audio.export(tmp_out_path, format="wav")

        # 統一された関数を呼び出す
        user_transcribed = transcribe_audio(tmp_out_path)
        # --- ここまで ---

        wer_score = calculate_wer(original_transcribed, user_transcribed)
        diff_user = get_diff_html(original_transcribed, user_transcribed, mode='user')
        diff_original = get_diff_html(original_transcribed, user_transcribed, mode='original')

        # ... (ログ保存処理: save_preset_log) ...

        return jsonify({
            "original_transcribed": original_transcribed,
            "user_transcribed": user_transcribed,
            "wer": round(wer_score * 100, 2),
            "diff_user": diff_user,
            "diff_original": diff_original
        })

    except Exception as e:
        # 統一されたエラーハンドリング
        return handle_transcription_error(e, "/evaluate_shadowing でのエラー")
    finally:
        # 一時ファイルの削除
        if tmp_in_path and os.path.exists(tmp_in_path):
            os.remove(tmp_in_path)
        if tmp_out_path and os.path.exists(tmp_out_path):
            os.remove(tmp_out_path)


    
    



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