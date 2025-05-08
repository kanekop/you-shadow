# routes/api_routes.py

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
from core.services.transcribe_utils import transcribe_audio
from core.wer_utils import wer, calculate_wer
from core.diff_viewer import diff_html, get_diff_html
from core.services.youtube_utils import youtube_bp, check_captions
from config import config_by_name # config.pyから設定辞書をインポート
from core.responses import api_error_response, api_success_response
from core.audio_utils import process_and_transcribe_audio, AudioProcessingError # インポート
#from core.evaluation_utils import generate_evaluation_metrics # 次の提案で使用


# 必要に応じて他のモジュールもインポートしてください
# 例: from models import db, YourApiModel

# 'api' という名前で Blueprint を作成します。
# 第2引数の __name__ は Blueprint の名前空間を指定します。
# url_prefix を指定すると、この Blueprint に属するルート全てのURLの先頭に
# 例えば '/api' のようなプレフィックスが付きます。
api_bp = Blueprint('api', __name__, url_prefix='/api')

# ここに app.py から移動してくるAPI関連のルートを定義していきます。
# 例:
# @api_bp.route('/example_endpoint', methods=['GET'])
# def example_endpoint():
#     return jsonify({"message": "This is an example API endpoint."})

# 他のAPIエンドポイントも同様に定義します。

@api_bp.route("/unlocked_levels/<username>")
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


#POST /api/recordings/upload	Upload & transcribe new recording
@api_bp.route('/recordings/upload', methods=['POST'])
@auth_required
def upload_recording():
    user_id = request.headers.get('X-Replit-User-Id') # 認証済みなので取得できるはず
    filepath = None # finally で削除するために定義

    # 1. リクエスト検証
    if 'audio' not in request.files:
        return api_error_response("音声ファイルが提供されていません。", 400, log_prefix="/api/recordings/upload")
    audio_file = request.files['audio']
    if not audio_file or not audio_file.filename:
        return api_error_response("無効な音声ファイルです。", 400, log_prefix="/api/recordings/upload")

    # --- メイン処理ブロック ---
    try:
        # 2. ファイル保存 (一意なファイル名生成)
        #    ファイル名をユーザーIDとUUIDで一意にする
        original_filename_secure = secure_filename(audio_file.filename)
        _, file_ext = os.path.splitext(original_filename_secure)
        # filename = f"{user_id}_{uuid.uuid4().hex}{file_ext}" # UUIDベース
        # または、ファイルハッシュベース (重複排除したい場合)
        # temp_path_for_hash = ... (一時保存してハッシュ計算)
        # file_hash_val = calculate_file_hash(temp_path_for_hash)
        # filename = f"{user_id}_{file_hash_val}{file_ext}"
        # ここではUUIDベースの例
        filename = f"{user_id}_{uuid.uuid4().hex}_{original_filename_secure}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        audio_file.save(filepath)
        current_app.logger.info(f"Audio file saved to: {filepath}")

        # 3. 文字起こし (例外はここでキャッチ)
        transcript = transcribe_audio(filepath)
        if transcript is None: # transcribe_audio が None を返すケースに対応 (もしあれば)
             raise ValueError("文字起こしに失敗しました(結果がNone)。")

        # 4. (オプション) ファイルハッシュ計算 (重複排除が必要な場合)
        # file_hash_val = calculate_file_hash(filepath)
        # 既存チェック: existing = AudioRecording.query.filter_by(file_hash=file_hash_val, user_id=user_id).first()
        # if existing:
        #     # 既存のレコードを返すか、エラーとするかは仕様次第
        #     os.remove(filepath) # 不要なファイルを削除
        #     return api_success_response({ "id": existing.id, ... , "message": "既存の録音を使用"})
        # 今回はUUIDをハッシュ代わりに使う (重複チェックはしない)
        file_hash_val = str(uuid.uuid4())


        # 5. データベース保存準備
        recording = AudioRecording(
            user_id=user_id,
            filename=filename, # 一意なファイル名
            transcript=transcript,
            file_hash=file_hash_val # UUIDまたは計算したハッシュ
        )
        db.session.add(recording)

        # 6. コミット
        db.session.commit()
        current_app.logger.info(f"AudioRecording saved (ID: {recording.id}) for user {user_id}")

        # 7. 成功レスポンス
        return api_success_response({
            "id": recording.id,
            "filename": recording.filename,
            "transcript": recording.transcript,
            "created_at": recording.created_at.isoformat() # 作成日時も返すと便利かも
        })

    # --- ★ここから個別エラー捕捉 ---
    except FileNotFoundError as e: # transcribe_audio 内で発生
        # db.session.rollback() # commit前なので不要
        log_prefix = "FileNotFound in /api/recordings/upload"
        return api_error_response(f"処理に必要なファイルが見つかりません。", 404, exception_info=e, log_prefix=log_prefix)
    except ValueError as e: # transcribe_audio 内 or ファイル名関連などで発生
        # db.session.rollback() # commit前なので不要
        log_prefix = "ValueError in /api/recordings/upload"
        return api_error_response(f"入力値またはファイル形式に問題があります: {str(e)}", 400, exception_info=e, log_prefix=log_prefix)
    except IOError as e: # audio_file.save で発生
        # db.session.rollback() # commit前なので不要
        log_prefix = "IOError in /api/recordings/upload"
        return api_error_response(f"ファイルの保存に失敗しました。", 500, exception_info=e, log_prefix=log_prefix)
    except TimeoutError as e: # transcribe_audio から発生
        # db.session.rollback() # commit前なので不要
        log_prefix = "TimeoutError in /api/recordings/upload"
        return api_error_response(f"文字起こし処理がタイムアウトしました。", 504, exception_info=e, log_prefix=log_prefix)
    except ConnectionError as e: # transcribe_audio から発生
        # db.session.rollback() # commit前なので不要
        log_prefix = "ConnectionError in /api/recordings/upload"
        return api_error_response(f"外部サービスへの接続に失敗しました。", 503, exception_info=e, log_prefix=log_prefix)
    except PermissionError as e: # transcribe_audio から発生
        # db.session.rollback() # commit前なので不要
        log_prefix = "PermissionError in /api/recordings/upload"
        return api_error_response(f"処理に必要な権限がありません。", 401, exception_info=e, log_prefix=log_prefix)
    except RuntimeError as e: # transcribe_audio から発生
        # db.session.rollback() # commit前なので不要
        log_prefix = "RuntimeError in /api/recordings/upload"
        return api_error_response(f"文字起こし処理中にエラーが発生しました。", 500, exception_info=e, log_prefix=log_prefix)
    # except SQLAlchemyError as db_err: # DB関連エラー (commit時)
    #     db.session.rollback() # ★重要
    #     log_prefix = "Database Error in /api/recordings/upload"
    #     return api_error_response("データベース処理中にエラーが発生しました。", 500, exception_info=db_err, log_prefix=log_prefix)
    except Exception as e: # 上記以外の予期せぬエラー全般 (DBエラーも含む)
        db.session.rollback() # ★重要
        log_prefix = "Unexpected Error in /api/recordings/upload"
        return api_error_response(f"記録のアップロード中に予期せぬエラーが発生しました。", 500, exception_info=e, log_prefix=log_prefix)
    finally:
        # ★ エラー発生時に保存されたファイルを削除する処理を追加 (オプション)
        #    ただし、成功時はファイルを残す必要がある
        #    この例では、成功時以外（つまりexceptブロックに入った場合）に
        #    ファイルが作成されていれば削除する、という実装は少し複雑になる。
        #    よりシンプルなのは、エラーに関わらずファイルを残し、
        #    定期的なクリーンアップスクリプトでDBに紐づかないファイルを消す方法。
        #    ここでは finally は空にしておく。
        pass



@api_bp.route("/presets")
def api_presets():
    structure = get_presets_structure()
    return jsonify(structure)

@api_bp.route("/highest_levels/<username>")
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

@api_bp.route('/my_materials', methods=['GET'])
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


@api_bp.route('/evaluate_youtube', methods=['POST'])
# @auth_required # YouTube評価は認証が必要か？ 必要なら追加
def evaluate_youtube():
    tmp_path = None # finally で使うために try の外で初期化

    # 1. リクエスト検証
    if 'audio' not in request.files:
        return api_error_response('音声ファイルが提供されていません。', 400, log_prefix="/api/evaluate_youtube")
    if 'transcript' not in request.form or not request.form['transcript']:
        return api_error_response('比較対象の文字起こしテキストが提供されていません。', 400, log_prefix="/api/evaluate_youtube")

    audio_file = request.files['audio']
    original_transcript_text = request.form['transcript']
    # audio_file オブジェクト自体の検証 (例: filename) も必要なら追加

    # --- メイン処理ブロック ---
    try:
        # 2. 一時ファイルに保存
        #    suffix はクライアントから送られてくる形式に合わせるのがベターだが、
        #    transcribe_audio が様々な形式を扱えるなら .webm でも良い場合が多い
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm', dir=current_app.config.get('UPLOAD_FOLDER')) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name
            current_app.logger.info(f"Temporary audio file for YouTube evaluation saved to: {tmp_path}")

        # 3. 文字起こし (例外はここでキャッチ)
        user_transcribed_text = transcribe_audio(tmp_path)
        if user_transcribed_text is None: # transcribe_audio が None を返すケースに対応
             raise ValueError("文字起こしに失敗しました(結果がNone)。")

        # 4. WER計算とDiff生成 (例外はここでキャッチ)
        wer_score_val = calculate_wer(original_transcript_text, user_transcribed_text)
        diff_result_html = diff_html(original_transcript_text, user_transcribed_text)

        # 5. 成功レスポンス
        return api_success_response({
            "transcribed": user_transcribed_text,
            "wer": round(wer_score_val * 100, 2),
            "diff_html": diff_result_html
        })

    # --- ★ここから個別エラー捕捉 ---
    except FileNotFoundError as e: # transcribe_audio 内で発生
        log_prefix = "FileNotFound in /api/evaluate_youtube"
        return api_error_response(f"処理に必要な一時ファイルが見つかりません。", 404, exception_info=e, log_prefix=log_prefix)
    except ValueError as e: # transcribe_audio 内 or calculate_wer などで発生
        log_prefix = "ValueError in /api/evaluate_youtube"
        return api_error_response(f"入力値エラーまたは評価計算エラー: {str(e)}", 400, exception_info=e, log_prefix=log_prefix)
    except IOError as e: # audio_file.save で発生
        log_prefix = "IOError in /api/evaluate_youtube"
        return api_error_response(f"一時ファイルの保存に失敗しました。", 500, exception_info=e, log_prefix=log_prefix)
    except TimeoutError as e: # transcribe_audio から発生
        log_prefix = "TimeoutError in /api/evaluate_youtube"
        return api_error_response(f"文字起こし処理がタイムアウトしました。", 504, exception_info=e, log_prefix=log_prefix)
    except ConnectionError as e: # transcribe_audio から発生
        log_prefix = "ConnectionError in /api/evaluate_youtube"
        return api_error_response(f"外部サービスへの接続に失敗しました。", 503, exception_info=e, log_prefix=log_prefix)
    except PermissionError as e: # transcribe_audio から発生
        log_prefix = "PermissionError in /api/evaluate_youtube"
        return api_error_response(f"処理に必要な権限がありません。", 401, exception_info=e, log_prefix=log_prefix)
    except RuntimeError as e: # transcribe_audio から発生
        log_prefix = "RuntimeError in /api/evaluate_youtube"
        return api_error_response(f"文字起こし処理中にエラーが発生しました。", 500, exception_info=e, log_prefix=log_prefix)
    # except openai.APIError as oai_err: # 必要なら openai.APIError を個別に捕捉
    #    log_prefix = "OpenAI Error in /api/evaluate_youtube"
    #    status_code = getattr(oai_err, 'status_code', 502)
    #    return api_error_response(f"文字起こしサービスでエラーが発生しました。", status_code, exception_info=oai_err, log_prefix=log_prefix)
    except Exception as e: # 上記以外の予期せぬエラー全般
        log_prefix = "Unexpected Error in /api/evaluate_youtube"
        return api_error_response(f"YouTube音声評価中に予期せぬエラーが発生しました。", 500, exception_info=e, log_prefix=log_prefix)
    finally:
        # 一時ファイルの削除 (変更なし、ただしログ出力を logger に統一)
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                current_app.logger.info(f"Deleted temporary file: {tmp_path}")
            except OSError as e_os:
                # ファイル削除エラーはログに残すだけで、ユーザーには影響させない
                current_app.logger.error(f"Error deleting temp file {tmp_path}", exc_info=e_os)


@api_bp.route('/practice/logs', methods=['POST'])
@auth_required
def log_practice():
        data = request.json
        user_id = data.get("user") # 'user' が存在しない場合の考慮が必要

        # ★ 認証: @auth_required を使うか、ここで user_id をヘッダーから取得/検証する
        # if not user_id:
        #    user_id = request.headers.get('X-Replit-User-Id')
        # if not user_id:
        #     return api_error_response("User not authenticated", 401)

        # ★ データ検証: data が None や dict でない場合の考慮
        if not data:
            return api_error_response("Invalid request data", 400)

        # ★ キー存在と型チェック: data['key'] は KeyError のリスク、float(data['wer']) は ValueError/TypeError のリスク
        required_fields = ["user", "genre", "level", "wer", "original_transcribed", "user_transcribed"]
        if not all(field in data for field in required_fields):
            return api_error_response("Missing required fields", 400)

        try:
            # ★ データ変換時のエラー考慮
            wer_value = float(data["wer"])

            # genre, level は PracticeLog モデルに存在しない？
            # もし保存したい場合はモデルにカラム追加が必要。
            # 現在の PracticeLog モデルには genre, level はないためコメントアウト
            log_entry = PracticeLog(
                user_id=data["user"],
                # practice_type='preset', # preset固定か？データから取るべきか？
                # recording_id=None, # presetの場合、対応するAudioRecording IDは？
                # material_id=None,  # presetなので material_id は使わない想定
                # genre=data["genre"], # モデルにカラム追加が必要
                # level=data["level"], # モデルにカラム追加が必要
                wer=wer_value,
                original_text=data["original_transcribed"],
                user_text=data["user_transcribed"],
                practiced_at=datetime.utcnow()
            )

            db.session.add(log_entry)
            db.session.commit() # ★ DBエラーはここで発生

            return api_success_response({"message": "Logged successfully", "id": log_entry.id}) # ★ api_success_response を使用

        except (ValueError, TypeError) as e:
            # float(data["wer"]) などでの型変換エラー
            db.session.rollback() # 念のためロールバック
            log_prefix="ValueError/TypeError in /api/log_attempt"
            return api_error_response(f"データ形式エラー: {str(e)}", 400, exception_info=e, log_prefix=log_prefix)
        except KeyError as e:
            # data['key'] で存在しないキーにアクセスした場合
            db.session.rollback() # 念のためロールバック
            log_prefix="KeyError in /api/log_attempt"
            return api_error_response(f"必須フィールドが不足しています: {str(e)}", 400, exception_info=e, log_prefix=log_prefix)
        except Exception as e: # DBエラー (commit時など) やその他の予期せぬエラー
            db.session.rollback() # ★ ロールバック (重要！)
            log_prefix = "Unexpected Error in /api/log_attempt"
            # ログには詳細を記録し、ユーザーには汎用メッセージ
            return api_error_response(f"ログの保存中にエラーが発生しました。", 500, exception_info=e, log_prefix=log_prefix)


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


@api_bp.route('/save_material', methods=['POST'])
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



