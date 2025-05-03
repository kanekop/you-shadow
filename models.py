# models.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class AudioRecording(db.Model):
    __tablename__ = 'audio_recordings'
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, nullable=False)
    filename      = db.Column(db.String, nullable=False)
    transcript    = db.Column(db.Text, nullable=False)
    file_hash     = db.Column(db.String, unique=True, nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

class PracticeLog(db.Model):
    __tablename__ = 'practice_logs'
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, nullable=False)
    recording_id   = db.Column(db.Integer, db.ForeignKey('audio_recordings.id'), nullable=False)
    wer            = db.Column(db.Float, nullable=False)
    practiced_at   = db.Column(db.DateTime, default=datetime.utcnow)
    recording      = db.relationship('AudioRecording', backref='practice_logs')

class Material(db.Model):
    __tablename__ = 'materials'
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.Integer, nullable=False)
    material_name    = db.Column(db.String, nullable=False)
    storage_key      = db.Column(db.String, nullable=False)
    transcript       = db.Column(db.Text, nullable=True)
    upload_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
