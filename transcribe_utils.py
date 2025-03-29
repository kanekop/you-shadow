import openai
import os

def transcribe_audio(filepath):
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    with open(filepath, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcript.text
