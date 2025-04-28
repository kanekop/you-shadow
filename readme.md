├── app.py                 # Main Flask application
├── templates/            # HTML templates
│   ├── index.html        # Main page
│   ├── shadowing.html    # Shadowing practice page
│   ├── read_aloud.html   # Reading practice page
│   └── ...              # Other HTML templates
├── static/              # Static assets
│   ├── js/             # JavaScript files
│   ├── audio/          # Audio files
│   └── style.css       # Main stylesheet
├── presets/            # Practice materials
│   ├── sentences/      # Sentence practice content
│   └── shadowing/      # Shadowing practice content
├── uploads/            # User uploaded files
├── wer/               # Word Error Rate calculation
├── diff_viewer.py     # Diff viewing utility
├── transcribe_utils.py # Transcription utilities
├── wer_utils.py       # WER calculation utilities
├── youtube_utils.py   # YouTube integration
├── requirements.txt   # Python dependencies
└── .replit           # Replit configuration
The application follows a typical Flask structure with:

Frontend: Templates (HTML), static files (JS, CSS, audio)
Backend: Python utilities for audio processing, transcription, and scoring
Content: Preset materials for practice organized by genre and level
Configuration: Replit-specific settings and dependencies
This structure supports the main features:

Shadowing practice
Reading practice
Sentence practice
YouTube integration
WER (Word Error Rate) calculation
Audio recording and processing