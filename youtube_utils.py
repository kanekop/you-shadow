# youtube_utils.py

from flask import Blueprint, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
import re

youtube_bp = Blueprint('youtube', __name__)

@youtube_bp.route('/get_transcript', methods=['POST'])
def get_transcript():
    data = request.get_json()
    url = data.get('url', '')

    # YouTube動画IDを抽出
    video_id_match = re.search(r"(?:v=|youtu.be/)([a-zA-Z0-9_-]{11})", url)
    if not video_id_match:
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    video_id = video_id_match.group(1)

    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = " ".join([line['text'] for line in transcript])
        return jsonify({'transcript': full_text})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
