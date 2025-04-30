import openai
import os

def transcribe_audio(filepath):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not found in environment variables")

    client = openai.OpenAI(api_key=api_key)

    try:
        with open(filepath, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return transcript.text
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower():
            raise ValueError("Invalid OpenAI API key")
        raise ValueError(f"Transcription failed: {error_msg}")
