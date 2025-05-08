from flask import Blueprint, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
import re
from googleapiclient.discovery import build
import os