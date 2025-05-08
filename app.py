# app.py

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
import pydub
from pydub import AudioSegment
from flask import (
    Flask, render_template, request, redirect, url_for, 
    jsonify, send_from_directory, session, current_app
)
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError # DBエラーを具体的に捕捉する場合
from sqlalchemy import desc # 降順ソート用
from flask_migrate import Migrate
from werkzeug.utils import secure_filename

# Local imports
from models import db, Material, AudioRecording, PracticeLog
from transcribe_utils import transcribe_audio
from wer_utils import wer, calculate_wer
from diff_viewer import diff_html, get_diff_html
from youtube_utils import youtube_bp, check_captions
from config import config_by_name # config.pyから設定辞書をインポート
from core.responses import api_error_response, api_success_response
from core.audio_utils import process_and_transcribe_audio, AudioProcessingError # インポート
#from core.evaluation_utils import generate_evaluation_metrics # 次の提案で使用




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
            # APIエンドポイント (@app.route('/api/...') など) で使うことが多い場合は、
            # リダイレクトではなくエラーを返す方がクライアント側で扱いやすいです。
            # Webページ用のルート (@app.route('/dashboard/...') など) ならリダイレクトでOK。
            # ここではAPIでの使用を想定し、api_error_response を使う例を示します。
            # import されていることが前提です: from core.responses import api_error_response
            return api_error_response("ユーザー認証が必要です。", 401)
            # もしWebページへのリダイレクトで良いなら元の redirect('/') のままでもOK
            # return redirect('/')
        return f(*args, **kwargs)
    return decorated_function # ★★★ 修正: ラップされた関数を返す ★★★
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

# app.py

@app.route('/evaluate_youtube', methods=['POST'])
def evaluate_youtube():
    tmp_path = None

    # 1. リクエスト検証
    if 'audio' not in request.files:
        return api_error_response('音声ファイルが提供されていません。', 400, log_prefix="/evaluate_youtube")
    if 'transcript' not in request.form or not request.form['transcript']:
        return api_error_response('比較対象の文字起こしテキストが提供されていません。', 400, log_prefix="/evaluate_youtube")

    audio_file = request.files['audio']
    original_transcript_text = request.form['transcript']

    try:
        # 2. 一時ファイルに保存
        #    process_and_transcribe_audio を使う場合は、この一時ファイル処理はそちらに内包される
        #    ここでは直接 transcribe_audio を使う想定で進めます
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm', dir=current_app.config.get('UPLOAD_FOLDER')) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name
            current_app.logger.info(f"Temporary audio file for YouTube evaluation saved to: {tmp_path}")

        # 3. 文字起こし
        user_transcribed_text = transcribe_audio(tmp_path) # transcribe_utils が各種エラーをraiseする想定

        # 4. WER計算とDiff生成
        wer_score_val = calculate_wer(original_transcript_text, user_transcribed_text)
        diff_result_html = diff_html(original_transcript_text, user_transcribed_text)

        return api_success_response({
            "transcribed": user_transcribed_text,
            "wer": round(wer_score_val * 100, 2),
            "diff_html": diff_result_html
        })

    except FileNotFoundError as e:
        return api_error_response("処理に必要な一時ファイルが見つかりません。", 404, exception_info=e, log_prefix="/evaluate_youtube")
    except ValueError as e: # transcribe_audio や calculate_wer から発生しうる
        return api_error_response(f"入力値エラーまたは評価計算エラー: {str(e)}", 400, exception_info=e, log_prefix="/evaluate_youtube")
    except IOError as e: # audio_file.save で発生
        return api_error_response("一時ファイルの保存に失敗しました。", 500, exception_info=e, log_prefix="/evaluate_youtube")
    except TimeoutError as e: # transcribe_audio (OpenAI API) から発生
        return api_error_response("文字起こし処理がタイムアウトしました。", 504, exception_info=e, log_prefix="/evaluate_youtube")
    except ConnectionError as e: # transcribe_audio (OpenAI API) から発生
        return api_error_response("外部サービスへの接続に失敗しました。", 503, exception_info=e, log_prefix="/evaluate_youtube")
    except openai.RateLimitError as e: # transcribe_utils から RateLimitError がそのまま来る場合
        return api_error_response("APIのレート制限を超えました。しばらくしてから再試行してください。", 429, exception_info=e, log_prefix="/evaluate_youtube")
    except openai.AuthenticationError as e: # transcribe_utils から AuthenticationError がそのまま来る場合
        return api_error_response("APIキーが無効または設定されていません。", 401, exception_info=e, log_prefix="/evaluate_youtube")
    except openai.APIStatusError as e: # その他のOpenAI APIエラー
         return api_error_response(f"文字起こしサービスでエラーが発生しました (Status: {e.status_code})。", e.status_code or 502, exception_info=e, log_prefix="/evaluate_youtube")
    except RuntimeError as e: # transcribe_audio 内のその他の予期せぬエラー
        return api_error_response("文字起こし処理中にランタイムエラーが発生しました。", 500, exception_info=e, log_prefix="/evaluate_youtube")
    except Exception as e: # その他の予期せぬエラー
        return api_error_response("YouTube音声評価中に予期せぬエラーが発生しました。", 500, exception_info=e, log_prefix="/evaluate_youtube")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                current_app.logger.info(f"Deleted temporary file: {tmp_path}")
            except OSError as e_os:
                current_app.logger.error(f"Error deleting temp file {tmp_path}", exc_info=e_os)





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


# /api/recordings/upload の修正
# app.py (api/recordings/upload の修正案 - 修正済みであれば確認のみ)

@app.route('/api/recordings/upload', methods=['POST'])
@auth_required
def upload_recording():
    user_id = request.headers.get('X-Replit-User-Id')
    filepath = None # finally で使うため

    # --- 1. リクエスト検証 ---
    if 'audio' not in request.files:
        return api_error_response("音声ファイルが提供されていません。", 400, log_prefix="/api/recordings/upload (Validation)")
    audio_file = request.files['audio']
    if not audio_file or not audio_file.filename:
        return api_error_response("無効な音声ファイルです。", 400, log_prefix="/api/recordings/upload (Validation)")

    # --- メイン処理ブロック ---
    try:
        # --- 2. ファイル保存 (一意なファイル名) ---
        original_filename_secure = secure_filename(audio_file.filename)
        _, file_ext = os.path.splitext(original_filename_secure)
        # filename = f"{user_id}_{uuid.uuid4().hex}{file_ext}" # シンプルなUUID
        filename = f"{user_id}_{uuid.uuid4().hex}_{original_filename_secure}" # 元ファイル名情報保持
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        audio_file.save(filepath)
        current_app.logger.info(f"Recording file saved to: {filepath} for user {user_id}")

        # --- 3. 文字起こし ---
        current_app.logger.info(f"Transcribing recording file: {filepath}...")
        # ここでは冒頭カットは不要と想定
        transcript = process_and_transcribe_audio(audio_file) # ★ process_and_transcribe_audio を使う方が一時ファイル管理が楽
        # transcript = transcribe_audio(filepath) # 直接呼ぶ場合
        current_app.logger.info("Transcription complete.")

        # --- 4. (オプション) ファイルハッシュ計算 ---
        # file_hash_val = calculate_file_hash(filepath) # 重複排除したい場合
        file_hash_val = str(uuid.uuid4()) # 今回はUUIDをダミーハッシュとして使用

        # --- 5. データベース保存 ---
        current_app.logger.info("Saving recording metadata to database...")
        recording = AudioRecording(
            user_id=user_id,
            filename=filename,
            transcript=transcript,
            file_hash=file_hash_val
        )
        db.session.add(recording)
        db.session.commit()
        current_app.logger.info(f"AudioRecording saved (ID: {recording.id}) for user {user_id}")

        # --- 6. 成功レスポンス ---
        return api_success_response({
            "id": recording.id,
            "filename": recording.filename,
            "transcript": recording.transcript,
            "created_at": recording.created_at.isoformat() # 追加情報
        })

    # --- エラーハンドリング (evaluate_custom_shadowing と同様) ---
    except FileNotFoundError as e:
        db.session.rollback()
        return api_error_response("処理に必要なファイルが見つかりません。", 404, exception_info=e, log_prefix="/api/recordings/upload")
    except ValueError as e:
        db.session.rollback()
        return api_error_response(f"入力値エラーまたはデータ処理エラー: {str(e)}", 400, exception_info=e, log_prefix="/api/recordings/upload")
    except AudioProcessingError as e: # process_and_transcribe_audio を使った場合
        db.session.rollback()
        return api_error_response(f"音声ファイルの処理中にエラーが発生しました: {str(e)}", 500, exception_info=e, log_prefix="/api/recordings/upload")
    except IOError as e: # audio_file.save など
         db.session.rollback()
         return api_error_response("ファイルの保存または読み込みに失敗しました。", 500, exception_info=e, log_prefix="/api/recordings/upload")
    except TimeoutError as e:
        db.session.rollback()
        return api_error_response("文字起こし処理がタイムアウトしました。", 504, exception_info=e, log_prefix="/api/recordings/upload")
    except ConnectionError as e:
        db.session.rollback()
        return api_error_response("外部サービスへの接続に失敗しました。", 503, exception_info=e, log_prefix="/api/recordings/upload")
    except openai.RateLimitError as e:
        db.session.rollback()
        return api_error_response("APIのレート制限を超えました。", 429, exception_info=e, log_prefix="/api/recordings/upload")
    except openai.AuthenticationError as e:
        db.session.rollback()
        return api_error_response("APIキーが無効です。", 401, exception_info=e, log_prefix="/api/recordings/upload")
    except openai.APIStatusError as e:
        db.session.rollback()
        return api_error_response(f"文字起こしサービスエラー (Status: {e.status_code})。", e.status_code or 502, exception_info=e, log_prefix="/api/recordings/upload")
    except RuntimeError as e:
        db.session.rollback()
        return api_error_response("文字起こしまたは保存処理中にランタイムエラーが発生しました。", 500, exception_info=e, log_prefix="/api/recordings/upload")
    except SQLAlchemyError as e:
        db.session.rollback() # ★ ロールバック
        return api_error_response("データベース処理中にエラーが発生しました。", 500, exception_info=e, log_prefix="/api/recordings/upload")
    except Exception as e:
        db.session.rollback() # ★ ロールバック
        return api_error_response("録音のアップロード処理中に予期せぬエラーが発生しました。", 500, exception_info=e, log_prefix="/api/recordings/upload")
    # finally:
        # process_and_transcribe_audio を使う場合、一時ファイルはその中で削除される
        # 直接 transcribe_audio を使う場合は、ここで一時ファイル filepath を削除する必要があるかもしれない
        # (ただし、DB保存成功時は filepath は AudioRecording.filename として残す必要がある)
        # エラー時のみ削除するロジックが必要。
        # pass




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



# app.py (修正後) /evaluate_read_aloud
# app.py (evaluate_read_aloud の修正案)

@app.route('/evaluate_read_aloud', methods=['POST'])
# @auth_required # 必要なら認証を追加
def evaluate_read_aloud():
    # --- 1. リクエストデータの検証 ---
    if 'audio' not in request.files:
        return api_error_response("録音された音声ファイルが提供されていません。", 400, log_prefix="/evaluate_read_aloud (Validation)")
    audio_file = request.files['audio']
    if not audio_file or not audio_file.filename:
        return api_error_response("無効な音声ファイルです。", 400, log_prefix="/evaluate_read_aloud (Validation)")

    reference_text = request.form.get('transcript') # 'transcript' キーで送られてくる想定
    if not reference_text:
        return api_error_response("比較対象のテキストが提供されていません。", 400, log_prefix="/evaluate_read_aloud (Validation)")

    log_context = "/evaluate_read_aloud" # ログ用コンテキスト

    try:
        # --- 2. 音声処理と文字起こし ---
        # 音読練習では通常、冒頭カットは不要
        current_app.logger.info(f"Processing recorded audio for read aloud...")
        user_transcribed = process_and_transcribe_audio(audio_file)
        current_app.logger.info("Recorded audio transcribed.")

        # --- 3. WER計算とDiff生成 ---
        current_app.logger.info("Calculating WER and Diff...")
        wer_score_val = calculate_wer(reference_text, user_transcribed)
        diff_result_html = diff_html(reference_text, user_transcribed)
        current_app.logger.info(f"WER calculated: {wer_score_val*100:.2f}%")

        # --- 4. (任意) データベースへのログ保存 ---
        # 必要であれば、PracticeLog などに保存するロジックを追加
        # user_id = request.headers.get('X-Replit-User-Id') # 認証する場合
        # try:
        #     log = PracticeLog(...)
        #     db.session.add(log)
        #     db.session.commit()
        # except SQLAlchemyError as e:
        #     db.session.rollback()
        #     current_app.logger.error(...)

        # --- 5. 成功レスポンス ---
        return api_success_response({
            "transcribed": user_transcribed,
            "wer": round(wer_score_val * 100, 2),
            "diff_html": diff_result_html
            # 必要に応じて "reference_text": reference_text も返す
        })

    # --- エラーハンドリング (evaluate_shadowing と同様) ---
    except FileNotFoundError as e:
        return api_error_response("処理に必要なファイルが見つかりません。", 404, exception_info=e, log_prefix=log_context)
    except ValueError as e:
        return api_error_response(f"入力値エラーまたはデータ処理エラー: {str(e)}", 400, exception_info=e, log_prefix=log_context)
    except AudioProcessingError as e:
        return api_error_response(f"録音音声ファイルの処理中にエラーが発生しました: {str(e)}", 500, exception_info=e, log_prefix=log_context)
    except TimeoutError as e:
        return api_error_response("文字起こし処理がタイムアウトしました。", 504, exception_info=e, log_prefix=log_context)
    except ConnectionError as e:
        return api_error_response("外部サービスへの接続に失敗しました。", 503, exception_info=e, log_prefix=log_context)
    except openai.RateLimitError as e:
        return api_error_response("APIのレート制限を超えました。", 429, exception_info=e, log_prefix=log_context)
    except openai.AuthenticationError as e:
        return api_error_response("APIキーが無効です。", 401, exception_info=e, log_prefix=log_context)
    except openai.APIStatusError as e:
        return api_error_response(f"文字起こしサービスエラー (Status: {e.status_code})。", e.status_code or 502, exception_info=e, log_prefix=log_context)
    except RuntimeError as e:
        return api_error_response("文字起こしまたは評価処理中にランタイムエラーが発生しました。", 500, exception_info=e, log_prefix=log_context)
    # except SQLAlchemyError as e: # DB保存を行う場合
    #     db.session.rollback()
    #     return api_error_response("データベース処理中にエラーが発生しました。", 500, exception_info=e, log_prefix=log_context)
    except Exception as e:
        # db.session.rollback() # DB保存を行う場合
        return api_error_response("音読評価処理中に予期せぬエラーが発生しました。", 500, exception_info=e, log_prefix=log_context)



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
# app.py

@app.route('/upload_custom_audio', methods=['POST'])
@auth_required
def upload_custom_audio():
    user_id = request.headers.get('X-Replit-User-Id')
    original_filepath = None # finally で使うため
    processed_chunk_paths = [] # finally で使うため

    if 'audio' not in request.files:
        return api_error_response("音声ファイルが選択されていません", 400, log_prefix="/upload_custom_audio")
    # ... (他の入力検証も同様に api_error_response を使用) ...
    audio_file = request.files['audio']
    if not audio_file or audio_file.filename == '':
        return api_error_response("無効なファイルです", 400, log_prefix="/upload_custom_audio")

    file_ext = os.path.splitext(audio_file.filename)[1].lower()
    # ... (拡張子チェック、api_error_response を使用) ...
    if file_ext not in ['.mp3', '.m4a', '.wav', '.mpga', '.mpeg', '.webm']: # app.configから読み込む方が良い
        return api_error_response(f"サポートされていないファイル形式です: {file_ext}", 400, log_prefix="/upload_custom_audio")

    filename_base = secure_filename(f"{user_id}_{uuid.uuid4().hex}")
    original_filename_for_save = f"{filename_base}_original{file_ext}" # DB保存・URL生成用
    original_filepath = os.path.join(app.config['UPLOAD_FOLDER'], original_filename_for_save)
    final_transcription = ""

    try:
        audio_file.save(original_filepath)
        current_app.logger.info(f"Custom audio saved to: {original_filepath}")
        file_size = os.path.getsize(original_filepath)

        MAX_WHISPER_SIZE = 25 * 1024 * 1024 # app.configから読み込む方が良い

        if file_size > MAX_WHISPER_SIZE:
            # チャンク処理 (既存ロジックをベースにエラーハンドリング強化)
            audio = AudioSegment.from_file(original_filepath)
            # ... (チャンク分割ロジック) ...
            transcribed_parts = []
            num_chunks = math.ceil(len(audio) / (app.config.get('TARGET_CHUNK_DURATION_MS', 10 * 60 * 1000) - app.config.get('CHUNK_OVERLAP_MS', 5000)))

            current_pos_ms = 0
            for chunk_index in range(num_chunks):
                # ... (チャンク作成) ...
                chunk = audio[start_ms:end_ms] # start_ms, end_ms の計算は既存ロジック

                with tempfile.NamedTemporaryFile(
                    prefix=f"{filename_base}_chunk_{chunk_index}_",
                    suffix=".mp3", # Whisperが扱いやすい形式
                    dir=app.config['UPLOAD_FOLDER'],
                    delete=False
                ) as tmp_chunk_file:
                    chunk_filepath_for_transcribe = tmp_chunk_file.name
                    processed_chunk_paths.append(chunk_filepath_for_transcribe)
                    chunk.export(chunk_filepath_for_transcribe, format="mp3")

                current_app.logger.info(f"Transcribing chunk {chunk_index + 1}/{num_chunks} for {original_filepath}")
                transcript_part = transcribe_audio(chunk_filepath_for_transcribe) # transcribe_utils がエラーをraise
                transcribed_parts.append(transcript_part)
            final_transcription = " ".join(transcribed_parts).strip()
        else:
            final_transcription = transcribe_audio(original_filepath)

        new_material = Material(
            user_id=user_id,
            material_name=audio_file.filename, # 元のファイル名
            storage_key=original_filename_for_save, # UPLOAD_FOLDERからの相対パス or 完全な識別子
            transcript=final_transcription,
            upload_timestamp=datetime.utcnow()
        )
        db.session.add(new_material)
        db.session.commit()
        current_app.logger.info(f"Material ID: {new_material.id} saved for user {user_id}")

        session['current_material_id'] = new_material.id
        session['custom_transcription'] = final_transcription

        return api_success_response({
            "audio_url": url_for('serve_upload', filename=original_filename_for_save),
            "transcription": final_transcription,
            "material_id": new_material.id
        })

    except FileNotFoundError as e:
        db.session.rollback()
        return api_error_response("処理に必要なファイルが見つかりません。", 404, exception_info=e, log_prefix="/upload_custom_audio")
    except ValueError as e:
        db.session.rollback()
        return api_error_response(f"入力値エラーまたはファイル形式エラー: {str(e)}", 400, exception_info=e, log_prefix="/upload_custom_audio")
    except pydub.exceptions.CouldntDecodeError as e: # pydubでのデコードエラー
        db.session.rollback()
        return api_error_response(f"音声ファイルのデコードに失敗しました。サポートされていない形式か、ファイルが破損している可能性があります。", 400, exception_info=e, log_prefix="/upload_custom_audio")
    except IOError as e:
        db.session.rollback()
        return api_error_response("ファイルの保存または読み込みに失敗しました。", 500, exception_info=e, log_prefix="/upload_custom_audio")
    except TimeoutError as e:
        db.session.rollback()
        return api_error_response("文字起こし処理がタイムアウトしました。", 504, exception_info=e, log_prefix="/upload_custom_audio")
    except ConnectionError as e:
        db.session.rollback()
        return api_error_response("外部サービスへの接続に失敗しました。", 503, exception_info=e, log_prefix="/upload_custom_audio")
    except openai.RateLimitError as e:
        db.session.rollback()
        return api_error_response("APIのレート制限を超えました。", 429, exception_info=e, log_prefix="/upload_custom_audio")
    except openai.AuthenticationError as e:
        db.session.rollback()
        return api_error_response("APIキーが無効です。", 401, exception_info=e, log_prefix="/upload_custom_audio")
    except openai.APIStatusError as e:
        db.session.rollback()
        return api_error_response(f"文字起こしサービスエラー (Status: {e.status_code})。", e.status_code or 502, exception_info=e, log_prefix="/upload_custom_audio")
    except RuntimeError as e: # transcribe_audio 内やチャンク処理の予期せぬエラー
        db.session.rollback()
        return api_error_response("文字起こし処理中にランタイムエラーが発生しました。", 500, exception_info=e, log_prefix="/upload_custom_audio")
    except SQLAlchemyError as e: # データベース関連のエラー
        db.session.rollback()
        return api_error_response("データベース処理中にエラーが発生しました。", 500, exception_info=e, log_prefix="/upload_custom_audio")
    except Exception as e:
        db.session.rollback()
        return api_error_response("カスタム音声のアップロード処理中に予期せぬエラーが発生しました。", 500, exception_info=e, log_prefix="/upload_custom_audio")
    finally:
        # 正常終了時は original_filepath は残すが、チャンクファイルは削除
        for path in processed_chunk_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    current_app.logger.info(f"Deleted temp chunk file: {path}")
                except OSError as e_os:
                    current_app.logger.error(f"Error deleting temp chunk file {path}", exc_info=e_os)
        # もし original_filepath もエラー時に削除したい場合は、成功フラグなどを使って制御する
        # 例:
        # success_flag = False
        # try:
        #    ...
        #    success_flag = True
        # finally:
        #    if not success_flag and original_filepath and os.path.exists(original_filepath):
        #        os.remove(original_filepath)


# app.py (evaluate_custom_shadowing の修正案)
@app.route('/evaluate_custom_shadowing', methods=['POST'])
@auth_required
def evaluate_custom_shadowing():
    user_id = request.headers.get('X-Replit-User-Id')
    original_transcription = None
    material_id = None # material_id を try ブロックの外で初期化

    # --- リクエストデータ検証 ---
    # material_id をリクエストから取得 (優先)
    material_id_from_request = request.form.get('material_id')
    if material_id_from_request:
        try:
            material_id = int(material_id_from_request)
        except ValueError:
            return api_error_response("無効な教材ID形式です。", 400, log_prefix="/evaluate_custom_shadowing (Validation)")
    else:
        # リクエストになければセッションから取得 (フォールバック)
        material_id_from_session = session.get('current_material_id')
        if not material_id_from_session:
             return api_error_response("教材情報が見つかりません。セッションが切れたか、教材が正しく選択されていません。", 400, log_prefix="/evaluate_custom_shadowing (Validation)")
        material_id = material_id_from_session # セッションのIDを使用

    if 'recorded_audio' not in request.files:
        return api_error_response("録音された音声ファイルが提供されていません", 400, log_prefix="/evaluate_custom_shadowing (Validation)")

    recorded_audio_file = request.files['recorded_audio']
    if not recorded_audio_file or not recorded_audio_file.filename:
        return api_error_response("無効な録音ファイルです。", 400, log_prefix="/evaluate_custom_shadowing (Validation)")

    # --- メイン処理ブロック ---
    try:
        # --- 1. 元の文字起こし取得 ---
        material = Material.query.get(material_id)
        if not material or material.user_id != user_id: # DB存在チェック & ユーザー所有チェック
            return api_error_response("指定された教材が見つからないか、アクセス権がありません。", 404, log_prefix=f"/evaluate_custom_shadowing (Material Fetch mid={material_id})")
        original_transcription = material.transcript
        if not original_transcription:
            # 文字起こしがない教材は評価できない
            return api_error_response("この教材には評価に必要な文字起こし情報がありません。", 400, log_prefix=f"/evaluate_custom_shadowing (Material Transcript mid={material_id})")

        # --- 2. 録音音声の処理と文字起こし ---
        current_app.logger.info(f"Processing recorded audio for custom shadowing (Material ID: {material_id})...")
        full_transcription = process_and_transcribe_audio(recorded_audio_file)
        current_app.logger.info("Recorded audio transcribed.")

        # --- 3. ウォームアップ除去 ---
        warmup_script = current_app.config.get('WARMUP_TRANSCRIPT', "10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0")
        user_transcription_for_eval = full_transcription # デフォルト
        if warmup_script:
            numbers = warmup_script.split(", ")
            possible_warmup_suffixes = [", ".join(numbers[i:]) for i in range(len(numbers))]
            possible_warmup_suffixes.sort(key=len, reverse=True)
            normalized_full_recorded = full_transcription.lower().strip()

            for suffix_candidate in possible_warmup_suffixes:
                normalized_suffix_candidate = suffix_candidate.lower()
                if normalized_full_recorded.startswith(normalized_suffix_candidate):
                     # 一致したサフィックスの元の文字列の長さで除去
                     # normalized_suffix_candidate の長さを使うのがより確実か
                     actual_removed_part_length = len(normalized_suffix_candidate)
                     user_transcription_for_eval = full_transcription[actual_removed_part_length:].lstrip(" ,")
                     current_app.logger.info(f"Warm-up part resembling '{suffix_candidate}' removed (length: {actual_removed_part_length}).")
                     break
            else: # for ループが break せずに終了した場合
                 current_app.logger.info("Warm-up part not identified in transcription.")
        else:
            current_app.logger.info("WARMUP_TRANSCRIPT not defined, skipping removal.")


        # --- 4. WER計算とDiff生成 ---
        current_app.logger.info("Calculating WER and Diff...")
        wer_score_val = calculate_wer(original_transcription, user_transcription_for_eval)
        diff_result_html = diff_html(original_transcription, user_transcription_for_eval)
        current_app.logger.info(f"WER calculated: {wer_score_val*100:.2f}%")

        # --- 5. データベースへのログ保存 ---
        current_app.logger.info("Saving practice log...")
        new_log = PracticeLog(
            user_id=user_id,
            practice_type='custom',
            material_id=material_id, # 取得したmaterial_idを使用
            recording_id=None, # カスタム練習では録音自体はDBに保存しない想定
            wer=round(wer_score_val * 100, 2),
            original_text=original_transcription,
            user_text=user_transcription_for_eval,
            practiced_at=datetime.utcnow()
        )
        db.session.add(new_log)
        db.session.commit() # ここでDBエラーが発生する可能性
        current_app.logger.info(f"Custom shadowing log saved (ID: {new_log.id}) for user {user_id}, material {material_id}")

        # --- 6. 成功レスポンス ---
        return api_success_response({
            "wer": round(wer_score_val * 100, 2),
            "diff_html": diff_result_html,
            "original_transcription": original_transcription,
            "user_transcription": user_transcription_for_eval # ウォームアップ除去後のテキスト
        })

    # --- エラーハンドリング ---
    except FileNotFoundError as e:
        db.session.rollback() # DB操作前でも念のため
        return api_error_response("処理に必要なファイルが見つかりません。", 404, exception_info=e, log_prefix=f"/evaluate_custom_shadowing (mid={material_id})")
    except ValueError as e:
        db.session.rollback()
        return api_error_response(f"入力値エラーまたはデータ処理エラー: {str(e)}", 400, exception_info=e, log_prefix=f"/evaluate_custom_shadowing (mid={material_id})")
    except AudioProcessingError as e: # pydubや音声ファイル処理中のエラー
        db.session.rollback()
        return api_error_response(f"録音音声ファイルの処理中にエラーが発生しました: {str(e)}", 500, exception_info=e, log_prefix=f"/evaluate_custom_shadowing (mid={material_id})")
    except TimeoutError as e:
        db.session.rollback()
        return api_error_response("文字起こし処理がタイムアウトしました。", 504, exception_info=e, log_prefix=f"/evaluate_custom_shadowing (mid={material_id})")
    except ConnectionError as e:
        db.session.rollback()
        return api_error_response("外部サービスへの接続に失敗しました。", 503, exception_info=e, log_prefix=f"/evaluate_custom_shadowing (mid={material_id})")
    except openai.RateLimitError as e:
        db.session.rollback()
        return api_error_response("APIのレート制限を超えました。", 429, exception_info=e, log_prefix=f"/evaluate_custom_shadowing (mid={material_id})")
    except openai.AuthenticationError as e:
        db.session.rollback()
        return api_error_response("APIキーが無効です。", 401, exception_info=e, log_prefix=f"/evaluate_custom_shadowing (mid={material_id})")
    except openai.APIStatusError as e:
        db.session.rollback()
        return api_error_response(f"文字起こしサービスエラー (Status: {e.status_code})。", e.status_code or 502, exception_info=e, log_prefix=f"/evaluate_custom_shadowing (mid={material_id})")
    except RuntimeError as e: # transcribe_audio やその他のランタイムエラー
        db.session.rollback()
        return api_error_response("文字起こしまたは評価処理中にランタイムエラーが発生しました。", 500, exception_info=e, log_prefix=f"/evaluate_custom_shadowing (mid={material_id})")
    except SQLAlchemyError as e: # DB関連エラー (commit時など)
        db.session.rollback() # ★ ロールバック
        return api_error_response("データベース処理中にエラーが発生しました。", 500, exception_info=e, log_prefix=f"/evaluate_custom_shadowing (mid={material_id})")
    except Exception as e: # その他の予期せぬエラー
        db.session.rollback() # ★ ロールバック
        return api_error_response("評価処理中に予期せぬエラーが発生しました。", 500, exception_info=e, log_prefix=f"/evaluate_custom_shadowing (mid={material_id})")



# app.py (/evaluate_shadowing の修正案)
@app.route('/evaluate_shadowing', methods=['POST'])
# @auth_required # 必要なら認証を追加
def evaluate_shadowing():
    original_transcribed = "" # tryブロック外で初期化

    # --- 1. リクエストデータの検証 ---
    if 'original_audio' not in request.files or 'recorded_audio' not in request.files:
        # 注意: original_audio は現在使用されていない可能性がありますが、リクエストに含まれている前提
        return api_error_response("教材音声または録音音声ファイルが不足しています。", 400, log_prefix="/evaluate_shadowing (Validation)")

    recorded_audio_file = request.files['recorded_audio']
    if not recorded_audio_file or not recorded_audio_file.filename:
        return api_error_response("無効な録音音声ファイルです。", 400, log_prefix="/evaluate_shadowing (Validation)")

    genre = request.form.get("genre")
    level = request.form.get("level")
    # username = request.form.get("username", "anonymous") # DB保存時に使用する場合

    if not genre or not level:
        return api_error_response("ジャンルまたはレベルが指定されていません。", 400, log_prefix="/evaluate_shadowing (Validation)")

    log_context = f"/evaluate_shadowing (Genre: {genre}, Level: {level})" # ログ用コンテキスト

    try:
        # --- 2. 正解テキストの取得 ---
        preset_base = current_app.config.get('PRESET_FOLDER', 'presets')
        script_path = os.path.join(preset_base, 'shadowing', genre, level, 'script.txt')

        if not os.path.exists(script_path):
            # ファイルが存在しない場合は 404 Not Found
            return api_error_response(f"指定された教材スクリプトが見つかりません: {script_path}", 404, log_prefix=log_context)

        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                original_transcribed = f.read().strip()
            if not original_transcribed:
                 current_app.logger.warning(f"スクリプトファイルが空です: {script_path}")
                 # 空のスクリプトでも処理は続行（WERは100%になるはず）
        except IOError as e:
            # ファイル読み込み中のI/Oエラー
            return api_error_response("正解スクリプトの読み込み中にエラーが発生しました。", 500, exception_info=e, log_prefix=log_context)

        # --- 3. 録音音声の処理と文字起こし ---
        current_app.logger.info(f"Processing recorded audio for preset shadowing {log_context}...")
        # プリセットシャドウイングでは冒頭カットが必要 (500ms)
        user_transcribed = process_and_transcribe_audio(recorded_audio_file, cut_head_ms=500)
        current_app.logger.info("Recorded audio transcribed.")


        # --- 4. WER計算とDiff生成 ---
        current_app.logger.info("Calculating WER and Diff...")
        wer_score_val = calculate_wer(original_transcribed, user_transcribed)
        diff_user = get_diff_html(original_transcribed, user_transcribed, mode='user')
        diff_original = get_diff_html(original_transcribed, user_transcribed, mode='original')
        current_app.logger.info(f"WER calculated: {wer_score_val*100:.2f}%")

        # --- 5. (任意) データベースへのログ保存 ---
        # shadowing-main.js が /api/practice/logs を別途呼ぶ想定であれば、
        # ここでのDB保存は不要かもしれません。もしここで保存するなら以下のようなコード。
        # user_id = request.headers.get('X-Replit-User-Id') or username # 認証を考慮
        # try:
        #     # PracticeLog モデルに genre, level カラムがないため、
        #     # recording_id を使うか、モデルを変更する必要がある。
        #     # ここでは recording_id は特定できないため、コメントアウト。
        #     # log = PracticeLog(...)
        #     # db.session.add(log)
        #     # db.session.commit()
        #     # current_app.logger.info(f"Preset shadowing log saved for user {user_id}, {log_context}")
        #     pass # DB保存しない場合
        # except SQLAlchemyError as e:
        #     db.session.rollback()
        #     current_app.logger.error(f"Database error saving preset shadowing log {log_context}", exc_info=e)
        #     # ログ保存失敗はユーザーに影響させないことが多い


        # --- 6. 成功レスポンス ---
        return api_success_response({
            "original_transcribed": original_transcribed,
            "user_transcribed": user_transcribed,
            "wer": round(wer_score_val * 100, 2),
            "diff_user": diff_user,
            "diff_original": diff_original
        })

    # --- エラーハンドリング ---
    except FileNotFoundError as e: # process_and_transcribe_audio 内
        return api_error_response("処理に必要なファイルが見つかりません。", 404, exception_info=e, log_prefix=log_context)
    except ValueError as e: # process_and_transcribe_audio や calculate_wer 内
        return api_error_response(f"入力値エラーまたはデータ処理エラー: {str(e)}", 400, exception_info=e, log_prefix=log_context)
    except AudioProcessingError as e: # pydub や音声ファイル処理中のエラー
        return api_error_response(f"録音音声ファイルの処理中にエラーが発生しました: {str(e)}", 500, exception_info=e, log_prefix=log_context)
    except TimeoutError as e: # transcribe_audio (OpenAI)
        return api_error_response("文字起こし処理がタイムアウトしました。", 504, exception_info=e, log_prefix=log_context)
    except ConnectionError as e: # transcribe_audio (OpenAI)
        return api_error_response("外部サービスへの接続に失敗しました。", 503, exception_info=e, log_prefix=log_context)
    except openai.RateLimitError as e:
        return api_error_response("APIのレート制限を超えました。", 429, exception_info=e, log_prefix=log_context)
    except openai.AuthenticationError as e:
        return api_error_response("APIキーが無効です。", 401, exception_info=e, log_prefix=log_context)
    except openai.APIStatusError as e:
        return api_error_response(f"文字起こしサービスエラー (Status: {e.status_code})。", e.status_code or 502, exception_info=e, log_prefix=log_context)
    except RuntimeError as e: # transcribe_audio やその他のランタイムエラー
        return api_error_response("文字起こしまたは評価処理中にランタイムエラーが発生しました。", 500, exception_info=e, log_prefix=log_context)
    # except SQLAlchemyError as e: # DB保存を行う場合のDBエラー
    #     db.session.rollback()
    #     return api_error_response("データベース処理中にエラーが発生しました。", 500, exception_info=e, log_prefix=log_context)
    except Exception as e: # その他の予期せぬエラー
        # db.session.rollback() # DB保存を行う場合はロールバック
        return api_error_response("シャドウイング評価処理中に予期せぬエラーが発生しました。", 500, exception_info=e, log_prefix=log_context)




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


# app.py (api/practice/logs の修正案)
# エンドポイント名は shadowing-main.js の呼び出しに合わせる
@app.route('/api/practice/logs', methods=['POST'])
@auth_required
def log_practice(): # 関数名もエンドポイントに合わせる
    user_id = request.headers.get('X-Replit-User-Id') # @auth_required で保証される
    log_context = "/api/log_attempt"

    # --- 1. リクエストデータ検証 ---
    data = request.json
    if not data:
        return api_error_response("リクエストボディが空か、JSON形式ではありません。", 400, log_prefix=f"{log_context} (Validation)")

    # 必須フィールドのチェック (モデルに合わせて調整)
    # 現在の PracticeLog モデルに合わせる: user_id, wer は必須。
    # practice_type, recording_id/material_id, original_text, user_text も欲しいところ。
    required_fields = ['wer'] # 最低限 'wer' が必要
    # practice_typeに応じて recording_id か material_id のどちらかが必要になるはず
    # 'original_text', 'user_text' もログとして有用

    if not all(field in data for field in required_fields):
        missing = [field for field in required_fields if field not in data]
        return api_error_response(f"必須フィールドが不足しています: {', '.join(missing)}", 400, log_prefix=f"{log_context} (Validation)")

    # practice_type に基づくIDのチェック
    practice_type = data.get('practice_type', 'preset') # デフォルトを preset とする例
    recording_id = data.get('recording_id')
    material_id = data.get('material_id')

    if practice_type == 'preset' and not recording_id:
         # preset練習なら、どの録音に対するログかを示す recording_id が欲しい
         # (ただし、現在の /evaluate_shadowing は recording_id を返していない)
         # return api_error_response("プリセット練習ログには recording_id が必要です。", 400, log_prefix=f"{log_context} (Validation)")
         pass # recording_id がなくても許容する場合
    elif practice_type == 'custom' and not material_id:
         return api_error_response("カスタム練習ログには material_id が必要です。", 400, log_prefix=f"{log_context} (Validation)")
    elif practice_type not in ['preset', 'custom', 'read_aloud']: # 想定されるタイプ
        return api_error_response(f"無効な練習タイプです: {practice_type}", 400, log_prefix=f"{log_context} (Validation)")

    try:
        # --- 2. データ変換とモデル作成 ---
        wer_value = float(data['wer']) # ValueError を捕捉

        log_entry = PracticeLog(
            user_id=user_id, # ヘッダーから取得した認証済みIDを使用
            practice_type=practice_type,
            recording_id=int(recording_id) if recording_id else None, # None または整数に変換
            material_id=int(material_id) if material_id else None, # None または整数に変換
            wer=wer_value,
            original_text=data.get('original_text'), # optional
            user_text=data.get('user_text'), # optional
            practiced_at=datetime.utcnow()
        )

        # --- 3. データベース保存 ---
        current_app.logger.info(f"Saving practice log for user {user_id}, type: {practice_type}...")
        db.session.add(log_entry)
        db.session.commit()
        current_app.logger.info(f"Practice log saved (ID: {log_entry.id})")

        # --- 4. 成功レスポンス ---
        return api_success_response({"message": "Logged successfully", "id": log_entry.id})

    # --- エラーハンドリング ---
    except (ValueError, TypeError) as e:
        db.session.rollback() # 念のため
        return api_error_response(f"データ形式エラー（WERやIDの数値変換など）: {str(e)}", 400, exception_info=e, log_prefix=f"{log_context}")
    except KeyError as e: # 必須でないフィールドを data[...] でアクセスした場合
        db.session.rollback() # 念のため
        return api_error_response(f"予期しないデータ構造です (KeyError: {str(e)})。", 400, exception_info=e, log_prefix=f"{log_context}")
    except SQLAlchemyError as e:
        db.session.rollback() # ★ ロールバック
        return api_error_response("データベース処理中にエラーが発生しました。", 500, exception_info=e, log_prefix=f"{log_context}")
    except Exception as e:
        db.session.rollback() # ★ ロールバック
        return api_error_response("ログの保存中に予期せぬエラーが発生しました。", 500, exception_info=e, log_prefix=f"{log_context}")



@app.route('/api/save_material', methods=['POST'])
@auth_required
def save_material():
    try:
        user_id = request.headers.get('X-Replit-User-Id')
        if not user_id:
            return api_error_response("User not authenticated", 401)

        if 'audio' not in request.files:
            return api_error_response("No audio file provided", 400)

        audio_file = request.files['audio']
        material_name = request.form.get('material_name', '').strip()

        if not material_name:
            return api_error_response("Material name is required", 400)

        if not audio_file.filename:
            return api_error_response("No audio file selected", 400)

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
        return api_error_response(str(e), 500)

@app.route('/api/my_materials', methods=['GET'])
@auth_required
def list_materials():
    try:
        user_id = request.headers.get('X-Replit-User-Id')
        if not user_id:
            return api_error_response("User not authenticated", 401)

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
        return api_error_response(str(e), 500)

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