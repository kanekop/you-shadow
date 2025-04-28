
from pydub import AudioSegment
import tempfile
from openai import OpenAI
import os

def trim_audio(audio_file, trim_ms=500):
    """Trim silence from beginning of audio file"""
    audio = AudioSegment.from_file(audio_file)
    return audio[trim_ms:]

def transcribe_with_whisper(audio_file):
    """Transcribe audio using OpenAI Whisper"""
    client = OpenAI()
    with open(audio_file, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f
        )
    return response.text

def process_audio_file(input_file, trim_ms=500):
    """Process audio file - trim and transcribe"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        # Trim audio
        trimmed = trim_audio(input_file, trim_ms)
        trimmed.export(tmp.name, format="wav")
        
        # Transcribe
        transcript = transcribe_with_whisper(tmp.name)
        
        # Cleanup
        os.unlink(tmp.name)
        
        return transcript
