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
# routes/api_routes.py (修正後)
@api_bp.route('/recordings/upload', methods=['POST'])
@auth_required
def upload_recording():
    user_id = request.headers.get('X-Replit-User-Id')
    # filepath = None # finally がないので不要になる可能性

    # 1. リクエスト検証 (ここはルート内で行い、不備があれば ValueError を raise するか、直接 api_error_response を返す)
    if 'audio' not in request.files:
        # グローバルハンドラで処理させるなら:
        raise ValueError("音声ファイルが提供されていません。")
        # または直接返す:
        # return api_error_response("音声ファイルが提供されていません。", 400, log_prefix="/api/recordings/upload")
    audio_file = request.files['audio']
    if not audio_file or not audio_file.filename:
        raise ValueError("無効な音声ファイルです。") # グローバルハンドラへ

    # --- メイン処理ブロック ---
    # try-except は、グローバルハンドラで捕捉できない特有の事後処理 (ファイル削除など) が
    # 必要な場合や、エラーの種類によって処理を分岐したい場合に限定的に使用する。
    # ここでは、主要な例外はグローバルハンドラに任せる。

    original_filename_secure = secure_filename(audio_file.filename)
    _, file_ext = os.path.splitext(original_filename_secure)
    filename = f"{user_id}_{uuid.uuid4().hex}_{original_filename_secure}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

    try:
        audio_file.save(filepath) # IOErrorが発生する可能性
    except IOError as e:
        # IOErrorはグローバルハンドラでも捕捉できるが、ここでより詳細なログを残したり、
        # 特有の処理をするなら個別にキャッチする。
        # グローバルに任せるならこのtry-exceptは不要。
        current_app.logger.error(f"Failed to save audio file {filepath} in /api/recordings/upload", exc_info=True)
        raise # グローバルハンドラに再スロー

    current_app.logger.info(f"Audio file saved to: {filepath}")

    # transcribe_audio は FileNotFoundError, ValueError, openai系エラー, TimeoutError などをスローする可能性
    # これらはグローバルハンドラで捕捉される。
    transcript = transcribe_audio(filepath)
    if transcript is None: # transcribe_audio が None を返すことは基本的にないはずだが念のため
         raise ValueError("文字起こしに失敗しました(結果がNone)。")


    file_hash_val = str(uuid.uuid4()) # ハッシュは現状UUIDなので、特にエラーは起きない想定

    recording = AudioRecording(
        user_id=user_id,
        filename=filename,
        transcript=transcript,
        file_hash=file_hash_val
    )
    db.session.add(recording)
    db.session.commit() # SQLAlchemyError はグローバルハンドラで捕捉・ロールバックされる

    current_app.logger.info(f"AudioRecording saved (ID: {recording.id}) for user {user_id}")

    return api_success_response({
        "id": recording.id,
        "filename": recording.filename,
        "transcript": recording.transcript,
        "created_at": recording.created_at.isoformat()
    })
    # finallyブロックでのファイル削除は、エラー発生時にファイルが残ってしまう問題がある。
    # 成功時以外はファイルを残さない、または定期的なクリーンアップスクリプトで対応する方がシンプルかもしれない。
    # もし「エラーが起きたらアップロードされたファイルを必ず消す」という要件なら、
    # やはりルート側でtry-except-finallyが必要になる。
    # その場合、グローバルハンドラに処理が渡る前にfinallyを実行させる必要がある。

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


# evaluate_youtube (グローバルエラーハンドラ導入後)
@api_bp.route('/evaluate_youtube', methods=['POST'])
def evaluate_youtube():
    tmp_path = None

    # 1. リクエスト検証
    if 'audio' not in request.files:
        raise ValueError('音声ファイルが提供されていません。') # グローバルハンドラへ
    if 'transcript' not in request.form or not request.form['transcript']:
        raise ValueError('比較対象の文字起こしテキストが提供されていません。') # グローバルハンドラへ

    audio_file = request.files['audio']
    original_transcript_text = request.form['transcript']

    try:
        # 2. 一時ファイルに保存
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm', dir=current_app.config.get('UPLOAD_FOLDER')) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name
        current_app.logger.info(f"Temporary audio file for YouTube evaluation saved to: {tmp_path}")

        # 3. 文字起こし (ValueError, openai系エラー, TimeoutError などはグローバルハンドラへ)
        user_transcribed_text = transcribe_audio(tmp_path)
        if user_transcribed_text is None:
             raise ValueError("文字起こしに失敗しました(結果がNone)。")

        # 4. WER計算とDiff生成 (ValueError などはグローバルハンドラへ)
        wer_score_val = calculate_wer(original_transcript_text, user_transcribed_text)
        diff_result_html = diff_html(original_transcript_text, user_transcribed_text)

        # 5. 成功レスポンス
        return api_success_response({
            "transcribed": user_transcribed_text,
            "wer": round(wer_score_val * 100, 2),
            "diff_html": diff_result_html
        })

    # ルート固有の例外処理や、グローバルハンドラに渡したくない例外があればここでキャッチ。
    # 基本的にはグローバルハンドラに任せる。
    # except SpecificYouTubeEvaluationError as e:
    #     handle_specific_error()

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                current_app.logger.info(f"Deleted temporary file: {tmp_path}")
            except OSError as e_os:
                current_app.logger.error(f"Error deleting temp file {tmp_path}", exc_info=e_os)


# log_practice (グローバルエラーハンドラまだ導入してない 5月9日)
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


# 修正後 - /api/evaluate_custom_shadowing)
# このルートは、カスタムシャドウイングの評価を行うためのものです。
# 以下の処理を行います:
# 1. リクエストデータの検証
# 2. 正解テキストの取得 (セッションから)
# 3. 録音音声の処理と文字起こし
# 4. WER計算とDiff生成
# 5. データベースへのログ保存
# 6. 成功レスポンス
# グローバルエラーハンドラを活用して、エラー処理を簡潔にします。
# 具体的なエラーはグローバルハンドラで捕捉し、必要に応じて個別のエラーハンドラを追加します。
@api_bp.route('/evaluate_custom_shadowing', methods=['POST'])
@auth_required
def evaluate_custom_shadowing():
    user_id = request.headers.get('X-Replit-User-Id')

    # --- リクエストデータの検証 ---
    material_id = session.get('current_material_id')
    original_transcription = session.get('custom_transcription')

    # --- リクエスト/セッションデータの検証 ---
    if not material_id:



        # ここではセッション切れの可能性を示唆するエラーを返す
        return api_error_response("元の教材情報が見つかりません。セッションが切れたか、教材が正しく選択されていません。", 400, log_prefix="/evaluate_custom_shadowing")

    if not original_transcription:
        material = Material.query.get(material_id) # Materialはmodelsからimport
        if material and material.transcript:
            original_transcription = material.transcript
            session['custom_transcription'] = original_transcription
        else:
             return api_error_response("元の文字起こし情報が見つかりません (DB確認でも)。", 400, log_prefix="/evaluate_custom_shadowing")
    if 'recorded_audio' not in request.files:
        raise ValueError("録音された音声ファイルが提供されていません")

    recorded_audio_file = request.files['recorded_audio']
    if not recorded_audio_file or not recorded_audio_file.filename:
        raise ValueError("無効な録音ファイルです。")

    # --- メイン処理ブロック (try-except は減る) ---
    # FileNotFoundError, ValueError, TimeoutError, ConnectionError, PermissionError, RuntimeError,
    # AudioProcessingError, SQLAlchemyError はグローバルハンドラで処理される想定。

    # process_and_transcribe_audio は AudioProcessingError や transcribe_audio 内部の例外をスローする可能性
    full_transcription = process_and_transcribe_audio(recorded_audio_file)

    warmup_script = current_app.config.get('WARMUP_TRANSCRIPT', "10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0")
    user_transcription_for_eval = full_transcription # デフォルト
    # ... (ウォームアップ除去処理はそのまま) ...
    normalized_full_recorded = full_transcription.lower().strip()
    # (以下、変更前のコードからウォームアップ除去ロジックをペースト)
    numbers = warmup_script.split(", ")
    possible_warmup_suffixes = [", ".join(numbers[i:]) for i in range(len(numbers))]
    possible_warmup_suffixes.sort(key=len, reverse=True)
    for suffix_candidate in possible_warmup_suffixes:
        if normalized_full_recorded.startswith(suffix_candidate.lower()):
            actual_removed_part_length = len(suffix_candidate)
            user_transcription_for_eval = full_transcription[actual_removed_part_length:].lstrip(" ,")
            current_app.logger.info(f"Warm-up part '{suffix_candidate}' removed.")
            break
    else:
         current_app.logger.info("Warm-up part not identified in transcription.")

    # 4. WER計算とDiff生成
    wer_score_val = calculate_wer(original_transcription, user_transcription_for_eval)
    diff_result_html = diff_html(original_transcription, user_transcription_for_eval)

    new_log = PracticeLog( # PracticeLogはmodelsからimport
        user_id=user_id,
        practice_type='custom',
        material_id=material_id,
        recording_id=None, # カスタムなので recording_id は NULL
        wer=round(wer_score_val * 100, 2),
        original_text=original_transcription,
        user_text=user_transcription_for_eval,
        practiced_at=datetime.utcnow() # datetimeはimport
    )
    db.session.add(new_log)

    # 6. コミット (全ての処理が成功した場合)
    db.session.commit() # SQLAlchemyError はグローバルハンドラへ

    current_app.logger.info(f"Custom shadowing log saved (ID: {new_log.id}) for user {user_id}, material {material_id}")

    return api_success_response({
        "wer": round(wer_score_val * 100, 2),
        "diff_html": diff_result_html,
        "original_transcription": original_transcription,
        "user_transcription": user_transcription_for_eval
    })
    # process_and_transcribe_audio 内で一時ファイルは削除されるので、ここでの finally は不要


# evaluate_shadowing (グローバルエラーハンドラ導入後)
@api_bp.route('/evaluate_shadowing', methods=['POST'])
# @auth_required # 必要であれば認証デコレータを追加
def evaluate_shadowing():
    # 1. リクエストデータの検証 (ここはルート内で行うのが適切)
    #    検証NGの場合は、ValueError を raise するか、api_error_response を直接返す。
    #    ValueError を raise すれば、グローバルの ValueError ハンドラが対応する。
    if 'original_audio' not in request.files or 'recorded_audio' not in request.files:
        # グローバルハンドラで処理させる場合:
        raise ValueError("教材音声または録音音声ファイルが不足しています。")
        # 直接返す場合 (この方がメッセージを細かく制御できることもある):
        # return api_error_response("教材音声または録音音声ファイルが不足しています。", 400, log_prefix="/api/evaluate_shadowing")

    recorded_audio_file = request.files['recorded_audio']
    if not recorded_audio_file or not recorded_audio_file.filename:
        raise ValueError("無効な録音音声ファイルです。") # グローバルハンドラが処理

    genre = request.form.get("genre", "")
    level = request.form.get("level", "")
    if not genre or not level:
        raise ValueError("ジャンルまたはレベルが指定されていません。") # グローバルハンドラが処理

    # username = request.form.get("username", "anonymous") # 認証を使うなら不要になる想定

    # 2. 正解テキストの取得 (プリセット教材から)
    original_transcribed = ""
    preset_base = current_app.config.get('PRESET_FOLDER', 'presets')
    script_path = os.path.join(preset_base, 'shadowing', genre, level, 'script.txt')

    # [A] script_path の存在確認
    if not os.path.exists(script_path):
        # FileNotFoundError を raise すると、グローバルの FileNotFoundError ハンドラが対応
        raise FileNotFoundError(f"指定された教材のスクリプトファイルが見つかりません: {script_path}")

    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            original_transcribed = f.read().strip()
    except IOError as e: # ファイルI/O特有のエラーをここでログに記録したい場合
        current_app.logger.error(f"スクリプトファイル '{script_path}' の読み込みに失敗しました。", exc_info=True)
        raise # グローバルハンドラに処理を委譲


    if not original_transcribed:
         current_app.logger.warning(f"スクリプトファイルが空です: {script_path}")
         # 【仕様確認】空のスクリプトをエラーとすべきか？
         # もしエラーなら: raise ValueError(f"評価用のスクリプトが空です: {script_path}")

    # [E] は↑の FileNotFoundError でカバーされる。

    # 3. 録音音声の処理と文字起こし
    user_transcribed = process_and_transcribe_audio(recorded_audio_file, cut_head_ms=500)
    if user_transcribed is None: # process_and_transcribe_audio がNoneを返すことはない設計のはずだが念のため
        raise ValueError("文字起こし結果が取得できませんでした。")


    # 4. WER計算とDiff生成
    try:
        wer_score_val = calculate_wer(original_transcribed, user_transcribed)
        diff_user = get_diff_html(original_transcribed, user_transcribed, mode='user')
        diff_original = get_diff_html(original_transcribed, user_transcribed, mode='original')
    except Exception as e: # WER計算/Diff生成に特化したエラーをログに残したい場合
        current_app.logger.error(f"WER/Diff計算中に予期せぬエラーが発生しました (Genre: {genre}, Level: {level})", exc_info=True)
        # ここで汎用的なExceptionハンドラに任せても良いし、
        # 評価処理の失敗として500エラーを返すことを明示しても良い。
        # raise RuntimeError("評価結果の生成中に内部エラーが発生しました。") from e
        raise # グローバルハンドラに委譲


    # 5. (任意) データベースへのログ保存
    #    もしここでDB保存を行い、SQLAlchemyError が発生した場合は、
    #    グローバルの SQLAlchemyError ハンドラがロールバックとエラーレスポンス生成を行う。
    #    そのため、ここでの try-except は原則不要。

    # 6. 成功レスポンス
    return api_success_response({
        "original_transcribed": original_transcribed,
        "user_transcribed": user_transcribed,
        "wer": round(wer_score_val * 100, 2),
        "diff_user": diff_user,
        "diff_original": diff_original
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