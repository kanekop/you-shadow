# app.py

# Standard library imports
import os
import uuid
import math
import json
import tempfile
from datetime import datetime, timedelta

# Third-party imports
import pandas as pd
import openai
from pydub import AudioSegment
from flask import (
    Flask, render_template, request, url_for, 
    jsonify, send_from_directory, session, current_app
)
from flask_cors import CORS
from sqlalchemy import desc # 降順ソート用
from flask_migrate import Migrate
from werkzeug.utils import secure_filename

# Local imports
from models import db, Material, PracticeLog
from core.services.transcribe_utils import transcribe_audio
from core.wer_utils import wer
from core.diff_viewer import diff_html
from core.services.youtube_utils import youtube_bp, check_captions
from config import config_by_name # config.pyから設定辞書をインポート
from core.responses import api_error_response
from core.auth import auth_required # ← これを追加
from routes.api_routes import api_bp
from routes.stripe_routes import stripe_bp
# (既存のimport)
from flask import jsonify, current_app, json # json をインポート
from sqlalchemy.exc import SQLAlchemyError
import openai
from werkzeug.exceptions import HTTPException
from models import db # db をインポート (SQLAlchemyErrorハンドラで使うため)
from core.audio_utils import AudioProcessingError # import を追加




# Constants
TARGET_CHUNK_SIZE_MB = 20
TARGET_CHUNK_SIZE_BYTES = TARGET_CHUNK_SIZE_MB * 1024 * 1024
CHUNK_OVERLAP_MS = 5000

# Flask app initialization
app = Flask(__name__)
app.register_blueprint(api_bp)
app.register_blueprint(stripe_bp)
app.config.from_object('config')
# 環境変数 FLASK_CONFIG (ReplitのSecretsで設定) に基づいて設定を読み込む
# Secretsに FLASK_CONFIG がなければ 'dev' (開発モード) をデフォルトとする
config_name = os.getenv('FLASK_CONFIG', 'dev')
app.config.from_object(config_by_name[config_name])

# Configクラスのinit_appメソッドを呼び出す (フォルダ作成などを行う場合)
# この呼び出しは、app.configに設定がロードされた後に行う
config_by_name[config_name].init_app(app)

# Stripe APIキーは stripe_routes.py の before_request で設定する形にしたので、
# ここでの明示的な stripe.api_key = ... は不要かもしれません。
# ただし、アプリ起動時にキーの存在チェックはしておくと良いでしょう。
if not app.config.get('STRIPE_SECRET_KEY'):
    app.logger.critical("STRIPE_SECRET_KEY is not configured. Billing will not work.")
if not app.config.get('STRIPE_WEBHOOK_SECRET'):
    app.logger.warning("STRIPE_WEBHOOK_SECRET is not configured. Webhook processing may fail.")

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
openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=180.0)

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


# --- エラーハンドラの定義 ---

@app.errorhandler(SQLAlchemyError)
def handle_database_error(error):
    db.session.rollback()
    log_prefix = "Database Error (Global Handler)"
    user_message = "データベース処理中にエラーが発生しました。管理者にご連絡ください。" # 少し変更
    current_app.logger.error(f"{log_prefix}: {str(error)}", exc_info=error)
    return api_error_response(user_message, 500, exception_info=error, log_prefix=log_prefix)

@app.errorhandler(openai.APITimeoutError)
def handle_openai_timeout_error(error):
    log_prefix = "OpenAI API Timeout (Global Handler)"
    user_message = "文字起こしサービスが時間内に応答しませんでした。しばらくしてから再試行してください。"
    current_app.logger.error(f"{log_prefix}: {str(error)}", exc_info=error)
    return api_error_response(user_message, 504, exception_info=error, log_prefix=log_prefix)

@app.errorhandler(openai.APIConnectionError)
def handle_openai_connection_error(error):
    log_prefix = "OpenAI API Connection Error (Global Handler)"
    user_message = "文字起こしサービスへの接続に失敗しました。ネットワーク環境を確認するか、しばらくしてから再試行してください。"
    current_app.logger.error(f"{log_prefix}: {str(error)}", exc_info=error)
    return api_error_response(user_message, 503, exception_info=error, log_prefix=log_prefix)

@app.errorhandler(ValueError)
def handle_value_error(error):
    log_prefix = "ValueError (Global Handler)"
    current_app.logger.warning(f"{log_prefix}: {str(error)}", exc_info=True) # exc_info=True でスタックトレースも記録
    # ユーザーにエラー詳細をそのまま見せるのはセキュリティリスクやUX低下の可能性があるため、慎重に。
    # 特定のValueErrorメッセージに基づいてユーザーフレンドリーなメッセージに振り分けるのが理想。
    user_message = "リクエストの内容に誤りがあります。"
    # 例: transcribe_audio からの具体的なメッセージはそのまま使っても良いかもしれない
    if "ファイルサイズが上限" in str(error) or \
       "音声ファイルが空です" in str(error) or \
       "サポートされていないファイル形式です" in str(error) or \
       "音声ファイルが無効です" in str(error): # audio_utils.py からの例外も考慮
        user_message = str(error)
    return api_error_response(user_message, 400, log_error=False, exception_info=error, log_prefix=log_prefix) # log_error=False で重複ログを避ける



@app.errorhandler(openai.RateLimitError)
def handle_openai_rate_limit_error(error):
    log_prefix = "OpenAI API Rate Limit (Global Handler)"
    user_message = "文字起こしサービスの利用が一時的に制限されています。しばらくしてから再試行してください。"
    current_app.logger.warning(f"{log_prefix}: {str(error)}", exc_info=error) # warningレベルでよいかも
    return api_error_response(user_message, 429, exception_info=error, log_prefix=log_prefix)

@app.errorhandler(openai.AuthenticationError)
def handle_openai_auth_error(error):
    log_prefix = "OpenAI API Authentication Error (Global Handler)"
    user_message = "文字起こしサービスの設定に誤りがあります。管理者にご連絡ください。" # ユーザーには詳細を伝えない
    current_app.logger.error(f"{log_prefix}: {str(error)}", exc_info=error)
    return api_error_response(user_message, 500, exception_info=error, log_prefix=log_prefix) # サーバー側の設定不備なので500

@app.errorhandler(openai.APIStatusError) # transcribe_utils で RuntimeError にラップする前のものを捕捉する場合
def handle_openai_status_error(error):
    log_prefix = f"OpenAI API Status Error {error.status_code} (Global Handler)"
    user_message = f"文字起こしサービスでエラーが発生しました(コード: {error.status_code})。管理者にご連絡ください。"
    current_app.logger.error(f"{log_prefix}: {error.message}", exc_info=error)
    # ステータスコードに応じてユーザーメッセージやHTTPステータスを調整可能
    return api_error_response(user_message, error.status_code if error.status_code else 500, exception_info=error, log_prefix=log_prefix)


@app.errorhandler(FileNotFoundError)
def handle_file_not_found_error(error):
    log_prefix = "FileNotFoundError (Global Handler)"
    current_app.logger.error(f"{log_prefix}: {str(error)}", exc_info=True)
    return api_error_response("必要なファイルが見つかりませんでした。", 404, log_error=False, exception_info=error, log_prefix=log_prefix)

@app.errorhandler(IOError) # ファイル保存時のエラーなど
def handle_io_error(error):
    log_prefix = "IOError (Global Handler)"
    current_app.logger.error(f"{log_prefix}: {str(error)}", exc_info=True)
    return api_error_response("ファイルの読み書き中にエラーが発生しました。", 500, log_error=False, exception_info=error, log_prefix=log_prefix)

# core.audio_utils.AudioProcessingError のハンドラ
@app.errorhandler(AudioProcessingError)
def handle_audio_processing_error(error):
    log_prefix = "AudioProcessingError (Global Handler)"
    current_app.logger.error(f"{log_prefix}: {str(error)}", exc_info=True)
    # エラーメッセージはユーザーに分かりやすいものになっている想定
    return api_error_response(f"音声ファイルの処理中にエラーが発生しました: {str(error)}", 500, log_error=False, exception_info=error, log_prefix=log_prefix)


@app.errorhandler(HTTPException) # Flask (Werkzeug) が投げるHTTPエラー
def handle_http_exception(error):
    log_prefix = f"HTTP Exception {error.code} (Global Handler)"
    current_app.logger.warning(f"{log_prefix}: {error.name} - {error.description}", exc_info=True) # ここも exc_info=True
    response = error.get_response()
    response.data = json.dumps({"error": error.description or error.name}) # よりシンプルなエラーメッセージ
    response.content_type = "application/json"
    return response

@app.errorhandler(Exception) # 全てのキャッチされなかった例外
def handle_generic_exception(error):
    # SQLAlchemyError など、より具体的なハンドラでキャッチされるべきだったものが
    # ここに来た場合、ロールバック漏れを防ぐ
    if isinstance(error, SQLAlchemyError):
        db.session.rollback()

    log_prefix = "Unhandled Exception (Global Handler)"
    current_app.logger.critical(f"{log_prefix}: {str(error)}", exc_info=True) # 重大なエラーなので critical
    return api_error_response("サーバー内部で重大なエラーが発生しました。管理者にご連絡ください。", 500, log_error=False, exception_info=error, log_prefix=log_prefix)




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


@app.route('/check_subtitles', methods=["GET"])
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



@app.route('/shadowing')
def shadowing_ui():
    return render_template('shadowing.html')


@app.route('/custom-shadowing')
@auth_required # カスタムシャドウイングは認証必須と想定
def custom_shadowing_ui():
    user_id = request.headers.get('X-Replit-User-Id')
    last_material_info = None

    try:
        # ユーザーの最後のカスタム練習ログを取得
        last_custom_log = PracticeLog.query.filter_by(
            user_id=user_id,
            practice_type='custom'
        ).order_by(desc(PracticeLog.practiced_at)).first()

        if last_custom_log and last_custom_log.material_id:
            # 対応する Material 情報を取得
            last_material = Material.query.get(last_custom_log.material_id)
            if last_material:
                # ★ storage_key からファイル名を抽出する処理が必要な場合がある
                #    storage_key が 'uploads/user_id_uuid_original_filename.mp3' のような形式の場合
                #    元のファイル名 (material_name) を使うのが良い
                material_display_name = last_material.material_name

                # ★ storage_key からアクセス可能なURLを生成
                #    現状の実装では uploads/<filename> でアクセス可能？
                #    storage_key が 'uploads/...' で始まっているか確認
                audio_url = None
                if last_material.storage_key and last_material.storage_key.startswith(current_app.config['UPLOAD_FOLDER'] + os.path.sep):
                     filename_for_url = os.path.basename(last_material.storage_key)
                     audio_url = url_for('serve_upload', filename=filename_for_url)
                elif last_material.storage_key: # storage_key がURLの場合など（将来的な拡張）
                     audio_url = last_material.storage_key # そのまま使う

                if audio_url:
                    last_material_info = {
                        "material_id": last_material.id,
                        "filename": material_display_name, # 表示用のファイル名
                        "script": last_material.transcript or "", # スクリプトがない場合は空文字
                        "audio_url": audio_url,
                        "last_practiced": last_custom_log.practiced_at.isoformat() # 参考情報
                    }
                    current_app.logger.info(f"Found last custom material for user {user_id}: Material ID {last_material.id}")
                else:
                    current_app.logger.warning(f"Could not generate audio URL from storage_key for Material ID {last_material.id}")

    except Exception as e:
        current_app.logger.error(f"Error fetching last custom material for user {user_id}", exc_info=e)
        # エラーが発生してもページの表示は試みる

    # ReplitユーザーIDをテンプレートに渡す
    # (JavaScriptからヘッダーを読むより、テンプレート経由の方が確実な場合がある)
    return render_template('custom_shadowing.html',
                           last_material_info=last_material_info,
                           replit_user_id=user_id) # ★ replit_user_id を渡す




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
        return api_error_response("User not authenticated", 401)

    if 'audio' not in request.files:
        return api_error_response("音声ファイルが選択されていません", 400)

    audio_file = request.files['audio']
    if not audio_file or audio_file.filename == '':
        return api_error_response("無効なファイルです", 400)

    # ファイル拡張子チェック
    file_ext = os.path.splitext(audio_file.filename)[1].lower()
    allowed_extensions = ['.mp3', '.m4a', '.wav', '.mpga', '.mpeg', '.webm']
    if file_ext not in allowed_extensions:
        return api_error_response(f"サポートされていないファイル形式です: {file_ext}", 400)

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

    # except openai.APIError as e: # ← 個別のopenai.APIErrorキャッチを追加するとより丁寧
    #     db.session.rollback()
    #     status_code = getattr(e, 'status_code', 502)
    #     user_message = f"文字起こしサービスでエラーが発生しました (Status: {status_code})。"
    #     log_prefix = "OpenAI Error in /upload_custom_audio"
    #     return api_error_response(user_message, status_code, exception_info=e, log_prefix=log_prefix)
    except ValueError as ve: # ファイル形式エラーやpydubでの処理エラーなど
         db.session.rollback()
         log_prefix="ValueError in /upload_custom_audio"
         return api_error_response(f"入力値またはファイル形式に問題があります: {str(ve)}", 400, exception_info=ve, log_prefix=log_prefix)
    except FileNotFoundError as fnf_err:
         db.session.rollback()
         log_prefix="FileNotFoundError in /upload_custom_audio"
         return api_error_response(f"処理に必要なファイルが見つかりません: {str(fnf_err)}", 404, exception_info=fnf_err, log_prefix=log_prefix)
    except Exception as e:
        # 上記以外の予期せぬエラー (DB接続エラーなどもここに該当する可能性あり)
        db.session.rollback()
        log_prefix = "Unexpected Error in /upload_custom_audio"
        # api_error_response が内部で500番台の時に汎用メッセージに置換 & 詳細ロギング
        return api_error_response(f"アップロード処理中に予期せぬエラーが発生しました: {type(e).__name__}", 500, exception_info=e, log_prefix=log_prefix)

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

# app.py (修正案)
# (TimeoutError, ConnectionError, PermissionError, RuntimeError は組み込み or transcribe_utilsでraiseされる)
# from sqlalchemy.exc import SQLAlchemyError # DBエラーを具体的に捕捉する場合
# ---------------------------

@app.route('/sentence-practice')
def sentence_practice():
    return render_template('sentence_practice.html')

@app.route('/compare')
def compare():
    return render_template('compare.html')


#############################
# app.pyの記述
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


