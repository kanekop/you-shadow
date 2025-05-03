# Language Learning Assistant 🌍

A sophisticated Flask-based web application designed to help users improve their language pronunciation and speaking skills through interactive exercises, real-time feedback, and progress tracking.

## 🌟 Key Features

### 1. Database Integration
- **SQLite Database**
  - User practice logs
  - Audio recordings storage
  - Custom practice materials
  - Progression tracking
  - Relationship management between recordings and practices

### 2. Shadowing Practice System
- **Preset Content Library**
  - Multiple genres and progressive difficulty levels
  - High-quality audio samples with professional recordings
  - Customizable practice sessions
  - Real-time performance feedback
  - Last practice retrieval

### 3. Custom Shadowing
- **File Support**
  - Multiple audio formats (MP3, M4A, WAV)
  - Automatic transcription
  - Custom practice material creation
  - Database storage of materials

### 4. Progress Tracking
- **Database-Driven Analytics**
  - Practice history
  - Performance metrics
  - WER scores
  - Custom material usage

## 🗄️ Database Schema

### AudioRecording
```sql
CREATE TABLE audio_recordings (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    filename VARCHAR NOT NULL,
    transcript TEXT NOT NULL,
    file_hash VARCHAR UNIQUE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### PracticeLog
```sql
CREATE TABLE practice_logs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    recording_id INTEGER NOT NULL,
    wer FLOAT NOT NULL,
    practiced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recording_id) REFERENCES audio_recordings(id)
);
```

### Material
```sql
CREATE TABLE materials (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    material_name VARCHAR NOT NULL,
    storage_key VARCHAR NOT NULL,
    transcript TEXT,
    upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 📦 Project Structure
```
project/
├── app.py                 # Main application entry point
├── models.py             # Database models
├── config.py            # Configuration settings
├── migrations/         # Database migrations
├── static/            # Static assets
│   ├── js/           # JavaScript modules
│   │   ├── audio-recorder.js
│   │   ├── compare.js
│   │   ├── custom-shadowing.js
│   │   ├── preset-manager.js
│   │   ├── ranking.js
│   │   ├── recordings.js
│   │   └── shadowing-main.js
│   └── style.css
├── templates/        # HTML templates
│   ├── compare.html
│   ├── custom_shadowing.html
│   ├── dashboard.html
│   ├── my-recordings.html
│   └── other templates
├── utils/           # Core utilities
│   ├── audio_utils.py
│   ├── transcribe_utils.py
│   ├── wer_utils.py
│   └── diff_viewer.py
└── uploads/        # User uploaded files
```

## 🔑 API Endpoints

### Recordings
- `GET /api/recordings` - List user's recordings
- `GET /api/recordings/last` - Get user's most recent practice
- `POST /api/recordings/upload` - Upload new recording

### Practice
- `POST /api/practice/logs` - Log a practice session
- `GET /api/presets` - Get available practice presets

### Materials
- `POST /api/save_material` - Save custom practice material
- `GET /api/my_materials` - List user's custom materials

## 🚀 Getting Started

1. **Setup Database**
   ```bash
   flask db upgrade
   ```

2. **Run Application**
   ```bash
   python app.py
   ```

## 📊 Database Operations

### Recording Management
```python
# Save new recording
recording = AudioRecording(
    user_id=user_id,
    filename=filename,
    transcript=transcript,
    file_hash=str(uuid.uuid4())
)
db.session.add(recording)
db.session.commit()

# Get user's recordings
recordings = AudioRecording.query.filter_by(user_id=user_id).all()
```

### Practice Logging
```python
# Log practice
log = PracticeLog(
    user_id=user_id,
    recording_id=recording_id,
    wer=wer_score
)
db.session.add(log)
db.session.commit()
```

## 🔒 Security Features

- **Replit Authentication**
  - Secure user sessions
  - Progress persistence
  - User-specific content

## 📄 License

This project is proprietary and confidential. All rights reserved.