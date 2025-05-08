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
           │   ├─ audio_utils.py      ──► FFmpeg / pydub
           │   ├─ transcribe_utils.py ──► OpenAI Whisper
           │   ├─ wer_utils.py        ──► WER calculation
           │   └─ diff_viewer.py      ──► HTML diff
           ├─ Models (SQLAlchemy)
           └─ PostgreSQL / SQLite
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
├── app.py                    # Main application file (Flask routes, initialization)
├── config.py               # Configuration classes (Dev, Prod, etc.)
├── models.py                # SQLAlchemy database models (AudioRecording, Material, PracticeLog)
├── requirements.txt         # Python dependencies
├── transcribe_utils.py    # Handles OpenAI Whisper API calls and related logic
├── wer_utils.py             # Calculates Word Error Rate (WER)
├── diff_viewer.py          # Generates HTML diffs between texts
├── youtube_utils.py      # Handles YouTube API interactions (transcript fetching)
├── utils.py                 # General utility functions (e.g., remove_fillers)
├── core/                    # Core application modules
│   ├── audio_utils.py       # Audio processing helpers (e.g., process_and_transcribe_audio)
│   └── responses.py         # Standardized API response functions (success/error)
├── instance/                # Instance folder (e.g., for SQLite DB in dev)
│   └── dev.db               # Example development database location
├── migrations/              # Flask-Migrate database migration scripts
│   ├── versions/
│   └── ...
├── presets/                 # Default practice materials
│   ├── sentences/
│   └── shadowing/
├── static/                  # Frontend assets (CSS, JS, Audio)
│   ├── audio/               # Static audio files (e.g., warm-up)
│   ├── js/                  # JavaScript files for different pages/features
│   └── style.css            # Main CSS stylesheet
├── templates/               # Jinja2 HTML templates for web pages
├── uploads/                 # Directory for user-uploaded audio files
└── README.md                # This file
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
| **POST** `/evaluate_read_aloud` | Evaluate read‑aloud attempt |
| **POST** `/evaluate_custom_shadowing` | Evaluate custom material attempt |
| **POST** `/evaluate_shadowing` | Evaluate preset shadowing |
| **POST** `/evaluate_youtube` | Evaluate YouTube shadowing |

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
