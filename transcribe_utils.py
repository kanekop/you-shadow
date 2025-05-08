import openai
import os

# --- OpenAI Client の取得方法 ---
# app.py から client をインポートする想定。
# もし transcribe_utils が app より先にロードされる可能性がある場合は、
# Flask の application context を使うか、別の方法で client を渡す必要がある。
# ここでは app.py からインポートする前提とする。
try:
    # app.py 内で openai_client = openai.OpenAI(...) のように初期化されている想定
    from app import openai_client as client
except ImportError:
    # app.py 以外から直接使う場合やテストのためのフォールバック
    # 環境変数から直接キーを取得して初期化するなど、状況に応じて調整
    print("WARN: Could not import openai_client from app. Falling back.")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ImportError("OpenAI API key not found and could not import client from app.")
    client = openai.OpenAI(api_key=api_key)
# --- ここまで Client 取得 ---


def transcribe_audio(filepath):
    """指定された音声ファイルをOpenAI Whisperで文字起こしする"""
    try:
        # client = openai.OpenAI() # ここで毎回初期化しない

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"音声ファイルが見つかりません: {filepath}")

        file_size = os.path.getsize(filepath)
        if file_size == 0:
            raise ValueError("音声ファイルが空です")

        # Whisper APIがサポートする最大ファイルサイズチェック (例: 25MB)
        MAX_WHISPER_SIZE = 25 * 1024 * 1024
        if file_size > MAX_WHISPER_SIZE:
            # ここではエラーにする。大きなファイルの扱いは呼び出し元 (例: /upload_custom_audio) で行う想定
             raise ValueError(f"ファイルサイズが大きすぎます ({file_size / (1024*1024):.1f}MB)。最大{MAX_WHISPER_SIZE / (1024*1024)}MBまでです。")


        with open(filepath, "rb") as audio_file:
            # Whisper API呼び出し
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        # 文字起こし結果のテキストを返す
        return transcript.text

    except FileNotFoundError as e:
         # ファイルが見つからないエラーはそのままraise
        raise e
    except ValueError as e:
        # ファイルサイズなどの事前チェックエラーはそのままraise
        raise e
    except openai.APIConnectionError as e:
        raise ConnectionError(f"OpenAI APIへの接続に失敗しました: {e}")
    except openai.RateLimitError as e:
         raise Exception(f"OpenAI APIのレート制限を超えました: {e}")
    except openai.AuthenticationError as e:
        raise PermissionError(f"OpenAI APIキーが無効または設定されていません: {e}")
    except openai.APIStatusError as e:
        raise Exception(f"OpenAI APIエラー (ステータス: {e.status_code}): {e.response}")
    except Exception as e:
        # その他の予期せぬエラー
        error_type = type(e).__name__
        raise Exception(f"文字起こし中に予期せぬエラーが発生しました ({error_type}): {str(e)}")