# Language Learning Assistant 🌍

A sophisticated Flask-based web application designed to help users improve their language pronunciation and speaking skills through interactive exercises, real-time feedback, and progress tracking.

## 🗄️ Database Architecture

### Database Schema and Features

#### 1. AudioRecording
Stores user-recorded audio files and their transcripts.
```sql
CREATE TABLE audio_recordings (
    id INTEGER PRIMARY KEY,
    user_id VARCHAR NOT NULL,           -- User identifier
    filename VARCHAR NOT NULL,          -- Stored audio file name
    transcript TEXT NOT NULL,           -- Speech-to-text transcript
    file_hash VARCHAR UNIQUE NOT NULL,  -- Unique hash for deduplication
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
- Features:
  - Unique file hashing to prevent duplicates
  - Automatic timestamp tracking
  - Direct mapping to filesystem storage
  - Association with user sessions

#### 2. Material
Manages custom practice materials uploaded by users.
```sql
CREATE TABLE materials (
    id INTEGER PRIMARY KEY,
    user_id VARCHAR NOT NULL,           -- User identifier
    material_name VARCHAR NOT NULL,     -- Display name
    storage_key VARCHAR NOT NULL,       -- Storage location key
    transcript TEXT,                    -- Optional transcript
    upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```
- Features:
  - Flexible storage key system
  - Optional transcript support
  - Timestamp-based organization
  - User-specific content management

#### 3. PracticeLog
Tracks user practice sessions and performance metrics.
```sql
CREATE TABLE practice_logs (
    id INTEGER PRIMARY KEY,
    user_id VARCHAR NOT NULL,           -- User identifier
    practice_type VARCHAR NOT NULL,     -- 'preset' or 'custom'
    recording_id INTEGER,               -- FK to audio_recordings
    material_id INTEGER,                -- FK to materials
    wer FLOAT NOT NULL,                -- Word Error Rate score
    practiced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    original_text TEXT,                 -- Reference text
    user_text TEXT,                    -- User's spoken text
    FOREIGN KEY (recording_id) REFERENCES audio_recordings(id),
    FOREIGN KEY (material_id) REFERENCES materials(id),
    CHECK ((recording_id IS NOT NULL AND material_id IS NULL) OR 
           (recording_id IS NULL AND material_id IS NOT NULL))
);
```
- Features:
  - Dual practice type support
  - Performance metrics storage
  - Text comparison capability
  - Referential integrity enforcement
  - Constraint ensuring valid practice source

### Database Implementation

#### Project Structure
```
project/
├── migrations/                     # Database migration files
│   ├── versions/                  # Version-controlled schema changes
│   │   └── [migration files].py
│   └── env.py                     # Migration environment config
├── models.py                      # SQLAlchemy model definitions
├── config.py                      # Database configuration
└── app.py                         # Main application with routes
```

#### Key Database Operations

1. Recording Management
```python
# Save new recording
recording = AudioRecording(
    user_id=user_id,
    filename=filename,
    transcript=transcript,
    file_hash=unique_hash
)
db.session.add(recording)
db.session.commit()
```

2. Practice Logging
```python
# Log practice session
log = PracticeLog(
    user_id=user_id,
    practice_type='preset',
    recording_id=recording_id,
    wer=wer_score,
    original_text=reference_text,
    user_text=spoken_text
)
db.session.add(log)
db.session.commit()
```

3. Custom Material Management
```python
# Save custom material
material = Material(
    user_id=user_id,
    material_name=name,
    storage_key=storage_path,
    transcript=transcript
)
db.session.add(material)
db.session.commit()
```

### Database Usage in Application

1. Shadow Practice Feature
- Records user attempts in AudioRecording
- Logs performance in PracticeLog
- Associates with preset or custom materials

2. Custom Practice Materials
- Stores user uploads in Material table
- Links practice sessions to materials
- Maintains user-specific content

3. Progress Tracking
- Queries PracticeLog for performance history
- Calculates improvement metrics
- Generates user statistics

4. Content Management
- Manages both preset and custom content
- Handles file storage references
- Maintains practice history

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

## 📦 Project Structure
```
project/
├── app.py                    # Main application entry point
├── models.py                # Database models
├── config.py               # Configuration settings
├── wer_utils.py           # Word Error Rate calculation utilities
├── diff_viewer.py        # Diff generation utilities
├── transcribe_utils.py  # Audio transcription utilities
├── youtube_utils.py    # YouTube integration utilities
├── utils.py           # General utilities
├── core/             # Core functionality
│   ├── audio_utils.py    # Audio processing utilities
│   └── responses.py      # API response handlers
├── migrations/          # Database migrations
│   ├── versions/       # Migration versions
│   └── env.py         # Migration environment
├── presets/           # Practice materials
│   ├── sentences/    # Sentence practice content
│   └── shadowing/   # Shadowing practice content
├── static/          # Static assets
│   ├── audio/      # Audio files
│   ├── js/        # JavaScript modules
│   │   ├── audio-recorder.js
│   │   ├── compare.js
│   │   ├── custom-shadowing.js
│   │   ├── index.js
│   │   ├── preset-manager.js
│   │   ├── ranking.js
│   │   ├── read_aloud.js
│   │   ├── recordings.js
│   │   ├── sentence-practice.js
│   │   └── shadowing-main.js
│   └── style.css
├── templates/     # HTML templates
│   ├── compare.html
│   ├── custom_shadowing.html
│   ├── dashboard.html
│   ├── detail.html
│   ├── index.html
│   ├── my-recordings.html
│   ├── ranking.html
│   ├── read_aloud.html
│   ├── sentence_practice.html
│   ├── shadowing.html
│   └── youtube.html
└── uploads/     # User uploaded files
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