
import openai
import os

def transcribe_audio(filepath):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not found. Please make sure OPENAI_API_KEY is set in Secrets.")
    
    if not api_key.startswith("sk-"):
        raise ValueError("Invalid OpenAI API key format. The key should start with 'sk-'")

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
            raise ValueError("Authentication failed. Please check if your OpenAI API key is valid.")
        elif "request failed" in error_msg.lower():
            raise ValueError("Network error. Please check your internet connection.")
        raise ValueError(f"Transcription failed: {error_msg}")
