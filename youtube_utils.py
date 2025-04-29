# youtube_utils.py

from flask import Blueprint, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
import re
from googleapiclient.discovery import build
import os
import os

API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    raise ValueError("YOUTUBE_API_KEY environment variable is not set")

def check_captions(video_id):
    youtube = build('youtube', 'v3', developerKey=API_KEY)

    try:
        response = youtube.captions().list(
            part='snippet',
            videoId=video_id
        ).execute()

        for caption in response.get("items", []):
            if caption["snippet"]["trackKind"] != "ASR":
                return True
        return False
    except Exception as e:
        print(f"Error: {e}")
        return None




youtube_bp = Blueprint('youtube', __name__)

@youtube_bp.route('/get_transcript', methods=['POST'])
def get_transcript():
    data = request.get_json()
    url = data.get('url', '')

    video_id_match = re.search(r"(?:v=|youtu.be/)([a-zA-Z0-9_-]{11})", url)
    if not video_id_match:
        print("Invalid URL:", url)  # ログ出力
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    video_id = video_id_match.group(1)
    print("Video ID extracted:", video_id)

    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = " ".join([line['text'] for line in transcript])
        return jsonify({'transcript': full_text})
    except Exception as e:
        print("Error while fetching transcript:", str(e))  # ログ出力追加
        return jsonify({'error': str(e)}), 500
