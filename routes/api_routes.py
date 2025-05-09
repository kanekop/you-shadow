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
    jsonify, send_from_directory, session, current_app, Blueprint
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
from core.auth import auth_required



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


@api_bp.route('/evaluate_custom_shadowing', methods=['POST'])
@auth_required
def evaluate_custom_shadowing():
    user_id = request.headers.get('X-Replit-User-Id')

    # 1. リクエストデータの検証 (セッション、ファイル)
    material_id = session.get('current_material_id')
    original_transcription = session.get('custom_transcription')

    if not material_id:
        # セッション情報がない場合、DBから取得を試みる (前回の提案)
        # Material.query.get(...) など
        # それでも見つからなければエラー
        return api_error_response("元の教材情報が見つかりません。セッションが切れた可能性があります。", 400)

    if not original_transcription:
        material = Material.query.get(material_id)
        if material and material.transcript:
            original_transcription = material.transcript
            session['custom_transcription'] = original_transcription # セッションにも再設定
        else:
             return api_error_response("元の文字起こし情報が見つかりません。", 400)

    if 'recorded_audio' not in request.files:
        return api_error_response("録音された音声ファイルが提供されていません", 400)

    recorded_audio_file = request.files['recorded_audio']
    if not recorded_audio_file or not recorded_audio_file.filename:
        return api_error_response("無効な録音ファイルです。", 400)

    # --- メイン処理ブロック ---
    try:
        # 2. 録音音声の処理と文字起こし
        #    (内部で transcribe_audio が呼ばれ、具体的なエラーが発生する可能性)
        full_transcription = process_and_transcribe_audio(recorded_audio_file)

        # 3. ウォームアップ除去処理 (変更なし)
        warmup_script = current_app.config.get('WARMUP_TRANSCRIPT', "10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0")
        user_transcription_for_eval = full_transcription # デフォルト
        numbers = warmup_script.split(", ")
        possible_warmup_suffixes = [", ".join(numbers[i:]) for i in range(len(numbers))]
        possible_warmup_suffixes.sort(key=len, reverse=True)
        normalized_full_recorded = full_transcription.lower().strip()
        for suffix_candidate in possible_warmup_suffixes:
            if normalized_full_recorded.startswith(suffix_candidate.lower()):
                actual_removed_part_length = len(suffix_candidate)
                user_transcription_for_eval = full_transcription[actual_removed_part_length:].lstrip(" ,")
                current_app.logger.info(f"Warm-up part '{suffix_candidate}' removed.")
                break
        else: # for ループが break せずに終了した場合
             current_app.logger.info("Warm-up part not identified in transcription.")


        # 4. WER計算とDiff生成
        wer_score_val = calculate_wer(original_transcription, user_transcription_for_eval)
        diff_result_html = diff_html(original_transcription, user_transcription_for_eval)

        # 5. データベースへのログ保存準備
        new_log = PracticeLog(
            user_id=user_id,
            practice_type='custom',
            material_id=material_id,
            recording_id=None,
            wer=round(wer_score_val * 100, 2),
            original_text=original_transcription,
            user_text=user_transcription_for_eval,
            practiced_at=datetime.utcnow()
        )
        db.session.add(new_log)

        # 6. コミット (全ての処理が成功した場合)
        db.session.commit()
        current_app.logger.info(f"Custom shadowing log saved (ID: {new_log.id}) for user {user_id}, material {material_id}")

        # 7. 成功レスポンス
        return api_success_response({
            "wer": round(wer_score_val * 100, 2),
            "diff_html": diff_result_html,
            "original_transcription": original_transcription,
            "user_transcription": user_transcription_for_eval
        })

    # --- ★ここから個別エラー捕捉 ---
    except FileNotFoundError as e: # process_and_transcribe_audio 内で発生
        db.session.rollback() # 念のため
        log_prefix = "FileNotFound in /evaluate_custom_shadowing"
        return api_error_response(f"処理に必要なファイルが見つかりません。", 404, exception_info=e, log_prefix=log_prefix)
    except ValueError as e: # process_and_transcribe_audio 内 or calculate_wer などで発生
        db.session.rollback() # 念のため
        log_prefix = "ValueError in /evaluate_custom_shadowing"
        return api_error_response(f"入力値またはファイル形式に問題があります: {str(e)}", 400, exception_info=e, log_prefix=log_prefix)
    except TimeoutError as e: # process_and_transcribe_audio -> transcribe_audio から発生
        db.session.rollback() # 念のため
        log_prefix = "TimeoutError in /evaluate_custom_shadowing"
        return api_error_response(f"文字起こし処理がタイムアウトしました。", 504, exception_info=e, log_prefix=log_prefix)
    except ConnectionError as e: # process_and_transcribe_audio -> transcribe_audio から発生
        db.session.rollback() # 念のため
        log_prefix = "ConnectionError in /evaluate_custom_shadowing"
        return api_error_response(f"外部サービスへの接続に失敗しました。", 503, exception_info=e, log_prefix=log_prefix)
    except PermissionError as e: # process_and_transcribe_audio -> transcribe_audio から発生
        db.session.rollback() # 念のため
        log_prefix = "PermissionError in /evaluate_custom_shadowing"
        return api_error_response(f"処理に必要な権限がありません。", 401, exception_info=e, log_prefix=log_prefix)
    except RuntimeError as e: # process_and_transcribe_audio -> transcribe_audio から発生
        db.session.rollback() # 念のため
        log_prefix = "RuntimeError in /evaluate_custom_shadowing"
        return api_error_response(f"文字起こし処理中にエラーが発生しました。", 500, exception_info=e, log_prefix=log_prefix)
    except AudioProcessingError as ape: # process_and_transcribe_audio 内で発生
        db.session.rollback() # 念のため
        log_prefix = "AudioProcessingError in /evaluate_custom_shadowing"
        return api_error_response(f"音声ファイルの処理中にエラーが発生しました: {str(ape)}", 500, exception_info=ape, log_prefix=log_prefix)
    # except SQLAlchemyError as db_err: # DB関連エラーを具体的に捕捉する場合 (import必要)
    #     db.session.rollback() # ★重要
    #     log_prefix = "Database Error in /evaluate_custom_shadowing"
    #     return api_error_response("データベース処理中にエラーが発生しました。", 500, exception_info=db_err, log_prefix=log_prefix)
    except Exception as e: # 上記以外の予期せぬエラー全般 (DBエラーも含む)
        db.session.rollback() # ★重要
        log_prefix = "Unexpected Error in /evaluate_custom_shadowing"
        return api_error_response(f"評価処理中に予期せぬエラーが発生しました。", 500, exception_info=e, log_prefix=log_prefix)
    # finally ブロックは process_and_transcribe_audio 内で一時ファイルが削除されるなら不要




@api_bp.route('/evaluate_shadowing', methods=['POST'])
# @auth_required # 必要に応じて認証デコレータを追加
def evaluate_shadowing():
    # 1. リクエストデータの検証
    if 'original_audio' not in request.files or 'recorded_audio' not in request.files:
        return api_error_response("教材音声または録音音声ファイルが不足しています。", 400) # 共通関数使用済み

    recorded_audio_file = request.files['recorded_audio']
    if not recorded_audio_file or not recorded_audio_file.filename:
        return api_error_response("無効な録音音声ファイルです。", 400) # 共通関数使用済み

    genre = request.form.get("genre", "")
    level = request.form.get("level", "")
    username = request.form.get("username", "anonymous")

    # 2. 正解テキストの取得 (プリセット教材から)
    original_transcribed = ""
    preset_base = current_app.config.get('PRESET_FOLDER', 'presets')
    script_path = os.path.join(preset_base, 'shadowing', genre, level, 'script.txt')

    if not genre or not level:
        return api_error_response("ジャンルまたはレベルが指定されていません。", 400) # 共通関数使用済み

    if os.path.exists(script_path):
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                original_transcribed = f.read().strip()
            if not original_transcribed:
                 current_app.logger.warning(f"スクリプトファイルが空です: {script_path}")
                 # 空のスクリプトはエラーにしない
        except Exception as e:
            current_app.logger.error(f"スクリプトファイルの読み込みエラー ({script_path}): {e}")
            # ★ api_error_response を使用するように変更が必要
            return api_error_response("正解スクリプトの読み込み中にエラーが発生しました。", 500)
    else:
        current_app.logger.error(f"スクリプトファイルが見つかりません: {script_path}")
        # ★ api_error_response を使用するように変更が必要
        return api_error_response(f"指定された教材が見つかりません: {genre}/{level}", 404)

    # 3. 録音音声の処理と文字起こし
    try:
        # ★ 冒頭カットを指定
        user_transcribed = process_and_transcribe_audio(recorded_audio_file, cut_head_ms=500)

    except ValueError as ve: # ファイル形式エラーなど
        # ★ handle_transcription_error ではなく api_error_response を使う
        return api_error_response(f"入力エラー: {ve}", 400)
    except AudioProcessingError as ape: # 音声処理中のエラー
        # ★ handle_transcription_error ではなく api_error_response を使う
        return handle_transcription_error(ape, f"/api/evaluate_shadowing での音声処理エラー ({genre}/{level})")
    except Exception as e: # 文字起こしAPIエラーなど
        # ★ handle_transcription_error ではなく api_error_response を使う
        return handle_transcription_error(e, f"/api/evaluate_shadowing での文字起こしエラー ({genre}/{level})")

    # 4. WER計算とDiff生成
    try:
        wer_score_val = calculate_wer(original_transcribed, user_transcribed)
        diff_user = get_diff_html(original_transcribed, user_transcribed, mode='user')
        diff_original = get_diff_html(original_transcribed, user_transcribed, mode='original')
    except Exception as eval_err:
        current_app.logger.error(f"WER/Diff計算エラー ({genre}/{level}): {eval_err}")
        # ★ api_error_response を使う
        return api_error_response("評価結果の計算中にエラーが発生しました。", 500)

    # 5. (任意) データベースへのログ保存
    #    - shadowing-main.js は /api/practice/logs を呼び出す logAttempt 関数を持っている。
    #    - バックエンドで直接ログを保存するか、フロントエンドに任せるか方針を決める。
    #    - ここで直接保存する場合の例：
    # try:
    #     user_id_from_header = request.headers.get('X-Replit-User-Id') # 認証利用時
    #     log = PracticeLog(
    #         user_id=user_id_from_header or username, # 認証があればヘッダー優先
    #         practice_type='preset', # プリセットシャドウイング
    #         # recording_id や material_id は、この時点で特定できる情報に基づいて設定
    #         # recording_id を保存するには、録音ファイルを永続化し、AudioRecordingに登録する必要がある
    #         # もし genre/level で管理するなら、PracticeLogモデルにカラム追加が必要
    #         wer=round(wer_score_val * 100, 2),
    #         original_text=original_transcribed,
    #         user_text=user_transcribed,
    #         practiced_at=datetime.utcnow()
    #     )
    #     db.session.add(log)
    #     db.session.commit()
    #     current_app.logger.info(f"Preset shadowing log saved for user {log.user_id}, {genre}/{level}")
    # except Exception as db_err:
    #     db.session.rollback()
    #     current_app.logger.error(f"Shadowing ログ保存エラー ({genre}/{level}): {db_err}")
    #     # ログ保存エラーはレスポンスに影響させない場合もある

    # 6. 成功レスポンス (共通関数を使用)
    return api_success_response({
        "original_transcribed": original_transcribed,
        "user_transcribed": user_transcribed,
        "wer": round(wer_score_val * 100, 2),
        "diff_user": diff_user, # shadowing.html が期待するキー名に合わせる
        "diff_original": diff_original # shadowing.html が期待するキー名に合わせる
    })


@api_bp.route('/evaluate_read_aloud', methods=['POST'])
def evaluate_read_aloud():
    # 1. リクエストデータの検証 (変更なし)
    # ... (audio_file, reference_text の取得と検証) ...
    if 'audio' not in request.files:
        return api_error_response("録音された音声ファイルが提供されていません。", 400)
    audio_file = request.files['audio']
    if not audio_file or not audio_file.filename:
        return api_error_response("無効な音声ファイルです。", 400)
    reference_text = request.form.get('transcript')
    if not reference_text:
        return api_error_response("比較対象のテキストが提供されていません。", 400)

    # 2. 音声処理と文字起こし
    try:
        user_transcribed = process_and_transcribe_audio(audio_file)

    # --- ★ここから個別エラー捕捉を追加 ---
    except FileNotFoundError as e: # transcribe_audio内 or process_and_transcribe_audio内
        log_prefix = "FileNotFound in /api/evaluate_read_aloud"
        return api_error_response(f"処理に必要なファイルが見つかりません。", 404, exception_info=e, log_prefix=log_prefix)
    except ValueError as e: # transcribe_audio内 or process_and_transcribe_audio内
        log_prefix = "ValueError in /api/evaluate_read_aloud"
        return api_error_response(f"入力値またはファイル形式に問題があります: {str(e)}", 400, exception_info=e, log_prefix=log_prefix)
    except TimeoutError as e: # transcribe_audioから発生
        log_prefix = "TimeoutError in /api/evaluate_read_aloud"
        return api_error_response(f"文字起こし処理がタイムアウトしました。時間をおいて再試行してください。", 504, exception_info=e, log_prefix=log_prefix)
    except ConnectionError as e: # transcribe_audioから発生
        log_prefix = "ConnectionError in /api/evaluate_read_aloud"
        return api_error_response(f"外部サービスへの接続に失敗しました。しばらくしてから再試行してください。", 503, exception_info=e, log_prefix=log_prefix)
    except PermissionError as e: # transcribe_audioから発生 (APIキー関連)
        log_prefix = "PermissionError in /api/evaluate_read_aloud"
        return api_error_response(f"処理に必要な権限がありません。設定を確認してください。", 401, exception_info=e, log_prefix=log_prefix)
    except RuntimeError as e: # transcribe_audioから発生 (レート制限、その他内部エラー)
         # RateLimitError由来かチェックすることも可能 (e.args[0] の内容を見るなど)
         # if "レート制限" in str(e): status_code = 429
         # else: status_code = 500
        status_code = 500 # ここでは汎用的に500
        log_prefix = "RuntimeError in /api/evaluate_read_aloud"
        return api_error_response(f"文字起こし処理中にエラーが発生しました。", status_code, exception_info=e, log_prefix=log_prefix)
    except AudioProcessingError as ape: # core.audio_utils 固有のエラー
        log_prefix = "AudioProcessingError in /api/evaluate_read_aloud"
        return api_error_response(f"音声ファイルの処理中にエラーが発生しました: {str(ape)}", 500, exception_info=ape, log_prefix=log_prefix)
    # --- ★個別エラー捕捉ここまで ---
    except Exception as e: # その他の予期せぬエラー全般
        log_prefix = "Unexpected Error in /api/evaluate_read_aloud (Transcription Phase)"
        return api_error_response(f"文字起こし中に予期せぬエラーが発生しました。", 500, exception_info=e, log_prefix=log_prefix)

    # 3. WER計算とDiff生成
    try:
        wer_score_val = calculate_wer(reference_text, user_transcribed)
        diff_result_html = diff_html(reference_text, user_transcribed)
    except Exception as eval_err:
        log_prefix = "Unexpected Error in /api/evaluate_read_aloud (Evaluation Phase)"
        # 評価計算でのエラーはサーバー内部の問題
        return api_error_response("評価結果の計算中にエラーが発生しました。", 500, exception_info=eval_err, log_prefix=log_prefix)


    # 4. (任意) データベースへのログ保存
    # 必要であれば、ここで PracticeLog に結果を保存するロジックを追加
    # 例:
    # try:
    #     user_id = request.headers.get('X-Replit-User-Id') # 認証が必要な場合
    #     if user_id:
    #         log = PracticeLog(
    #             user_id=user_id,
    #             practice_type='read_aloud', # 練習タイプを区別
    #             material_id=None, # Read Aloud は特定の教材IDがない場合
    #             recording_id=None, # 保存した録音IDがない場合
    #             wer=round(wer_score_val * 100, 2),
    #             original_text=reference_text,
    #             user_text=user_transcribed,
    #             practiced_at=datetime.utcnow()
    #         )
    #         db.session.add(log)
    #         db.session.commit()
    # except Exception as db_err:
    #     db.session.rollback()
    #     current_app.logger.error(f"Read Aloud ログ保存エラー: {db_err}")
    #     # ログ保存エラーは致命的ではない場合、ここではエラーレスポンスを返さない選択肢もある

    # 5. 成功レスポンス
    return api_success_response({
        "transcribed": user_transcribed,
        "wer": round(wer_score_val * 100, 2),
        "diff_html": diff_result_html
        # 必要であれば reference_text もレスポンスに含める
        # "reference_text": reference_text
    })