# Language Learning Assistant 🌍

A **Flask–based web application** that helps users improve pronunciation and speaking skills through interactive shadowing, read‑aloud practice, and real‑time feedback powered by OpenAI Whisper.

---

## 📖 Table of Contents
1. [Features](#features)
2. [Tech Stack](#tech-stack)
3. [Architecture Overview](#architecture-overview)
4. [Getting Started](#getting-started)
   1. [Prerequisites](#prerequisites)
   2. [Installation](#installation)
   3. [Environment Variables](#environment-variables)
   4. [Database Migration](#database-migration)
   5. [Run](#run)
5. [Directory Structure](#directory-structure)
6. [Database Schema](#database-schema)
7. [API Reference](#api-reference)
8. [Security](#security)
9. [License](#license)

---

## Features

| Category | Highlights |
| -------- | ---------- |
| **Shadowing Practice** | • Preset audio/text library<br>• Custom audio uploads<br>• YouTube transcript shadowing |
| **Real‑time Feedback** | • Word Error Rate (WER)<br>• Side‑by‑side diff view |
| **Progress Tracking** | • PostgreSQL / SQLite backend<br>• User practice logs & statistics |
| **Content Management** | • Upload & store custom materials<br>• Genre / level system for presets |
| **Auth & Hosting** | • Replit user authentication<br>• Secrets management & persistent storage |

---

## Tech Stack

- **Backend :** Flask 2 · SQLAlchemy · Flask‑Migrate  
- **Frontend :** HTML · Jinja2 · Vanilla JS (+ fetch API)  
- **AI Services :** OpenAI Whisper (STT)  
- **Database :** PostgreSQL (Prod) / SQLite (Dev)  
- **Tools :** FFmpeg · pydub · Replit deployment

---

## Architecture Overview

```
Browser → Flask (app.py)
           ├─ Core modules
           │   ├─ audio_utils.py      ──► FFmpeg / pydub (Audio processing)
           │   └─ responses.py        ──► API Response handling
           ├─ Utils
           │   ├─ transcribe_utils.py ──► OpenAI Whisper (Speech-to-Text)
           │   ├─ wer_utils.py        ──► WER calculation
           │   ├─ diff_viewer.py      ──► HTML diff generation
           │   ├─ youtube_utils.py    ──► YouTube API integration
           │   └─ utils.py            ──► Common utilities
           ├─ Static assets
           │   ├─ JS modules          ──► Frontend functionality
           │   └─ Audio files         ──► System audio (warm-up, etc.)
           ├─ Templates               ──► Jinja2 HTML views
           ├─ Models (SQLAlchemy)     ──► Database schema
           └─ PostgreSQL / SQLite     ──► Data persistence
```

---

## Getting Started

### Prerequisites

- Python ≥ 3.10  
- pip  
- PostgreSQL instance **or** SQLite (for local dev)  
- OpenAI API key  
- *(Optional)* YouTube Data API key

### Installation

```bash
# 1 Clone & enter repository
$ git clone <your‑repo>
$ cd <repo>

# 2 Install dependencies
$ pip install -r requirements.txt
```

### Environment Variables

| Name | Purpose | Example |
| ---- | ------- | ------- |
| `FLASK_CONFIG` | Environment (`dev`, `prod`) | dev |
| `SECRET_KEY` | Session security | super‑secret‑string |
| `DATABASE_URL` | DB connection URI | postgresql://user:pwd@host/db |
| `OPENAI_API_KEY` | Whisper transcription | sk‑… |
| `YOUTUBE_API_KEY` | (Optional) YouTube features | AIza… |

> **Tip :** On Replit use *Secrets* to store these safely.

### Database Migration

```bash
# Initialise (only once)
$ flask db upgrade
```

### Run

```bash
$ python app.py  # http://localhost:5000
```

---

## Directory Structure

```
project/
├── app.py                # Main Flask application & routes
├── config.py             # Environment configurations
├── models.py             # SQLAlchemy database models
├── utils.py             # Common utility functions
├── core/                # Core application modules
│   ├── audio_utils.py   # Audio processing & FFmpeg operations
│   └── responses.py     # API response standardization
├── static/              # Frontend assets
│   ├── audio/          # System audio files (warm-up.mp3, etc.)
│   ├── js/             # Frontend JavaScript modules
│   │   ├── audio-recorder.js    # Audio recording functionality
│   │   ├── preset-manager.js    # Practice material management
│   │   ├── shadowing-main.js    # Main shadowing feature
│   │   └── [feature].js         # Feature-specific modules
│   └── style.css        # Global stylesheet
├── templates/           # Jinja2 HTML templates
│   ├── shadowing.html   # Shadowing practice view
│   ├── custom_shadowing.html    # Custom practice view
│   └── [feature].html   # Feature-specific views
├── presets/             # Practice materials
│   ├── sentences/       # Read-aloud materials
│   └── shadowing/       # Shadowing materials by genre/level
├── migrations/          # Database migration scripts
├── instance/           # Instance-specific files (SQLite, etc.)
├── uploads/            # User-uploaded audio files
└── requirements.txt    # Python dependencies
```

---

## Database Schema

> Full DDL lives in **`migrations/versions/`**. Below is a high‑level view.

| Table | Purpose | Key Columns |
| ----- | ------- | ---------- |
| `audio_recordings` | Stores user recordings & transcripts | `id`, `user_id`, `file_hash`, `transcript` |
| `materials` | Custom practice materials | `id`, `user_id`, `storage_key` |
| `practice_logs` | Performance history | `id`, `user_id`, `wer`, `recording_id ↔ audio_recordings` |

All timestamps default to `CURRENT_TIMESTAMP`; referential integrity enforced via FKs.

---

## API Reference

| Method & Path | Description |
| ------------- | ----------- |
| **GET** `/api/recordings` | List authenticated user recordings |
| **GET** `/api/recordings/last` | Latest practice log summary |
| **POST** `/api/recordings/upload` | Upload & transcribe new recording |
| **POST** `/api/practice/logs` | Store practice result (WER, diff) |
| **GET** `/api/presets` | Fetch preset library structure |
| **POST** `/api/evaluate_read_aloud` | Evaluate read‑aloud attempt |
| **POST** `/api/evaluate_custom_shadowing` | Evaluate custom material attempt |
| **POST** `/api/evaluate_shadowing` | Evaluate preset shadowing |
| **POST** `/api/evaluate_youtube` | Evaluate YouTube shadowing |

All endpoints return standardized JSON via `core/responses.py`.<br>Authentication uses Replit headers `X‑Replit‑User‑Id` / `X‑Replit‑User‑Name`.

---

## Security

- Replit OAuth headers secure user identity.  
- `SECRET_KEY` protects session cookies.  
- Always run behind **HTTPS** in production.  
- Rotate API keys regularly.

---

## License

© 2025 Your Name. All rights reserved. Commercial use requires explicit permission.