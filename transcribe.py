import openai

# --- あなたのAPIキーをここに貼り付け（後で環境変数化も可） ---
openai.api_key = "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"

# --- アップロードした音声ファイルのパス ---
audio_file_path = "thisistheah.mp3"  # Replitにアップロードしたファイル名に合わせて変更

# --- Whisper APIを使って文字起こし ---
with open(audio_file_path, "rb") as audio_file:
    transcript = openai.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="text"
    )

# --- 結果を出力 ---
print("=== Transcription Result ===\n")
print(transcript)
