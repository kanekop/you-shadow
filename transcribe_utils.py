
import openai
import os

def transcribe_audio(filepath):
    try:
        from app import openai_client as client
    except Exception as e:
        print(f"OpenAI client initialization error: {str(e)}")
        raise ValueError(f"Failed to initialize OpenAI client: {str(e)}")

    try:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Audio file not found at path: {filepath}")

        file_size = os.path.getsize(filepath)
        if file_size == 0:
            raise ValueError("Audio file is empty")

        with open(filepath, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        return transcript.text
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        detailed_msg = f"Error Type: {error_type}\nError Details: {error_msg}"
        
        # API Key related errors
        if "api_key" in error_msg.lower():
            raise ValueError(f"Authentication Error:\n{detailed_msg}\nPlease check if your OpenAI API key is valid.")
        
        # Network related errors
        elif "request failed" in error_msg.lower() or "connection" in error_msg.lower():
            raise ValueError(f"Network Error:\n{detailed_msg}\nPlease check your internet connection.")
        
        # File related errors
        elif "file" in error_msg.lower():
            raise ValueError(f"File Processing Error:\n{detailed_msg}\nPlease check if the audio file is valid and not corrupted.")
        
        # OpenAI service errors
        elif "openai" in error_msg.lower():
            raise ValueError(f"OpenAI Service Error:\n{detailed_msg}\nThis might be a temporary issue with the OpenAI service.")
        
        # Unknown errors
        raise ValueError(f"Transcription Failed:\n{detailed_msg}\nEnvironment: {'REPLIT_DEPLOYMENT' in os.environ}")
