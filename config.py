
import os

# API Keys
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Flask App Settings
UPLOAD_FOLDER = 'uploads'
SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev_key_only')
MAX_CONTENT_LENGTH = 250 * 1024 * 1024  # Max 25MB upload

# Database
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///data.db')
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'  # 開発用

SQLALCHEMY_TRACK_MODIFICATIONS = False

# File Paths
UPLOAD_FOLDER = 'uploads'
PRESET_FOLDER = 'presets'
LOG_FILE = 'preset_log.json'

# Audio Processing
FILLER_WORDS = {
    "uh", "um", "you know", "like", "i mean", "you see", 
    "well", "so", "basically", "actually", "literally",
    "kind of", "sort of", "you know what i mean"
}

# WER Calculation
NUMBER_MAP = {
    'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
    'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
}
