# models.py
# models.py の修正案
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class AudioRecording(db.Model):
    # ... (既存の AudioRecording モデル) ...
    __tablename__ = 'audio_recordings'
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, nullable=False) # user_id は String の方が Replit User ID と整合性が取れるかもしれません
    filename      = db.Column(db.String, nullable=False)
    transcript    = db.Column(db.Text, nullable=False)
    file_hash     = db.Column(db.String, unique=True, nullable=False) # Object Storage を使う場合、これは storage_key になる可能性があります
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Material(db.Model):
    # ... (既存の Material モデル) ...
    __tablename__ = 'materials'
    id               = db.Column(db.Integer, primary_key=True)
    user_id          = db.Column(db.String, nullable=False) # user_id は String の方が Replit User ID と整合性が取れるかもしれません
    material_name    = db.Column(db.String, nullable=False)
    storage_key      = db.Column(db.String, nullable=False) # 例: 'uploads/filename.mp3' や Object Storage のキー
    transcript       = db.Column(db.Text, nullable=True)
    upload_timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # 必要であれば、ファイルタイプや長さなどのメタデータを追加

class PracticeLog(db.Model):
    __tablename__ = 'practice_logs'
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.String, nullable=False) # user_id は String の方が Replit User ID と整合性が取れるかもしれません

    # --- 修正箇所 ---
    practice_type  = db.Column(db.String, nullable=False, default='preset') # 'preset' or 'custom'
    recording_id   = db.Column(db.Integer, db.ForeignKey('audio_recordings.id'), nullable=True) # NULL許容に
    material_id    = db.Column(db.Integer, db.ForeignKey('materials.id'), nullable=True) # MaterialへのFKを追加、NULL許容に
    # --------------

    wer            = db.Column(db.Float, nullable=False)
    practiced_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    original_text  = db.Column(db.Text, nullable=True) # 元のテキストも保存
    user_text      = db.Column(db.Text, nullable=True) # ユーザーの発話テキストも保存

    # --- リレーションシップの調整 ---
    # backref は一意である必要があるので、必要に応じて調整
    recording      = db.relationship('AudioRecording', backref=db.backref('preset_practice_logs', lazy=True))
    material       = db.relationship('Material', backref=db.backref('custom_practice_logs', lazy=True))
    # --------------------------

    # 制約: recording_id か material_id のどちらか一方は必須
    __table_args__ = (
        db.CheckConstraint('(recording_id IS NOT NULL AND material_id IS NULL) OR (recording_id IS NULL AND material_id IS NOT NULL)', name='chk_practice_source'),
    )