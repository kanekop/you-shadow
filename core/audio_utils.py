import os
import tempfile
import uuid # ファイル名の一意性確保のために使用する場合
from flask import current_app # app.config や app.logger を使うため
from pydub import AudioSegment, exceptions as pydub_exceptions # pydub の例外もインポート
from core.services.transcribe_utils import transcribe_audio # transcribe_utils.py の場所に合わせてインポート

# エラーの種類を明確にするためのカスタム例外 (任意)
class AudioProcessingError(Exception):
    pass

def process_and_transcribe_audio(
    audio_file_storage, # Flask の request.files から取得した FileStorage オブジェクト
    cut_head_ms=0,
    target_format="wav" # Whisper が最も安定して処理できる形式の一つ
):
    """
    アップロードされた音声ファイルを一時保存し、前処理（任意）を行い、文字起こしを実行します。

    Args:
        audio_file_storage: Flask の FileStorage オブジェクト。
        cut_head_ms (int): 音声の先頭からカットするミリ秒数。デフォルトは0。
        target_format (str): 文字起こし前に変換する音声フォーマット。デフォルトは "wav"。

    Returns:
        str: 文字起こしされたテキスト。

    Raises:
        ValueError: ファイルが無効な場合、またはサポートされていない形式の場合。
        AudioProcessingError: 音声ファイルの読み込みや変換中にエラーが発生した場合。
        Exception: 文字起こしAPI呼び出し中やその他の予期せぬエラーが発生した場合 (transcribe_audioからスローされる)。
    """
    if not audio_file_storage or not audio_file_storage.filename:
        raise ValueError("音声ファイルが無効です。")

    # Content-Type で簡単な形式チェック (より厳密にするなら python-magic など)
    # allowed_mime_types = ['audio/mpeg', 'audio/wav', 'audio/webm', 'audio/mp4', 'audio/x-m4a'] # 例
    # if audio_file_storage.mimetype not in allowed_mime_types:
    #     raise ValueError(f"サポートされていないファイル形式です: {audio_file_storage.mimetype}")

    upload_folder = current_app.config.get('UPLOAD_FOLDER', '/tmp') # UPLOAD_FOLDER設定を参照、なければ /tmp

    # --- 一時ファイルの管理 ---
    temp_input_path = None
    temp_processed_path = None

    try:
        # 1. 入力ファイルを一時保存
        #    - suffix で元の拡張子を保持しつつ、安全なファイル名を確保
        #    - delete=False で作成し、finally で確実に削除
        suffix = os.path.splitext(audio_file_storage.filename)[1]
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
            dir=upload_folder,
            prefix="input_"
        ) as tmp_in:
            audio_file_storage.save(tmp_in.name)
            temp_input_path = tmp_in.name
            current_app.logger.info(f"一時入力ファイル保存: {temp_input_path}")

        # 2. 音声ファイルの前処理 (pydub)
        try:
            audio = AudioSegment.from_file(temp_input_path)
        except pydub_exceptions.CouldntDecodeError as decode_error:
            raise AudioProcessingError(f"音声ファイルのデコードに失敗しました: {decode_error}")

        if cut_head_ms > 0:
            audio = audio[cut_head_ms:]
            current_app.logger.info(f"音声の先頭 {cut_head_ms}ms をカットしました。")

        # 3. 処理済み音声を一時ファイルとしてエクスポート (文字起こしAPI用)
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=f".{target_format}",
            dir=upload_folder,
            prefix="processed_"
        ) as tmp_proc:
            temp_processed_path = tmp_proc.name
            try:
                audio.export(temp_processed_path, format=target_format)
                current_app.logger.info(f"処理済み一時ファイル保存 ({target_format}形式): {temp_processed_path}")
            except Exception as export_error: # pydub の export でエラーが起きる可能性
                raise AudioProcessingError(f"音声のエクスポートに失敗しました ({target_format}形式): {export_error}")

        # 4. 文字起こし実行 (transcribe_utils を利用)
        #    - transcribe_audio 内で OpenAI API のエラーは処理される想定
        #    - FileNotFoundError なども transcribe_audio が処理
        transcription_text = transcribe_audio(temp_processed_path)
        current_app.logger.info(f"文字起こし成功 (先頭50文字): {transcription_text[:50]}...")

        return transcription_text

    # except (ValueError, AudioProcessingError) as pae:
        # これらのエラーは予期された処理エラーなので、そのまま上位にraise
        # current_app.logger.warning(f"音声処理または検証エラー: {pae}")
        # raise pae
    # except Exception as e:
        # transcribe_audio から来る可能性のあるエラーや、その他の予期せぬエラー
        # current_app.logger.error(f"process_and_transcribe_audio で予期せぬエラー: {e}")
        # raise # 上位の handle_transcription_error でキャッチさせる

    finally:
        # --- 一時ファイルのクリーンアップ ---
        for path in [temp_input_path, temp_processed_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    current_app.logger.info(f"一時ファイル削除: {path}")
                except OSError as e_os:
                    current_app.logger.error(f"一時ファイル削除エラー ({path}): {e_os}")