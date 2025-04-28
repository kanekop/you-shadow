
# Language Learning Assistant

A Flask-based web application that helps users practice language learning through various exercises including shadowing, reading aloud, and sentence practice.

## Core Features

1. **Shadowing Practice**
   - Practice speaking along with audio recordings
   - Real-time WER (Word Error Rate) calculation
   - Level-based progression system
   - Multiple genres support

2. **Read Aloud Practice**
   - Text-to-speech comparison
   - Accuracy scoring
   - Detailed feedback on pronunciation

3. **Sentence Practice**
   - Structured learning with preset sentences
   - Progressive difficulty levels
   - Audio playback support

4. **YouTube Integration**
   - Practice with YouTube video transcripts
   - Subtitle availability checking
   - Video-based shadowing practice

5. **Performance Tracking**
   - User progress tracking
   - Achievement system
   - Performance analytics
   - Ranking system

## Project Structure

```
├── app.py                    # Main Flask application
├── config.py                 # Configuration settings
├── error_handler.py          # Error handling module
├── logger.py                 # Logging utilities
├── audio_utils.py           # Audio processing utilities
├── transcribe_utils.py      # Audio transcription module
├── youtube_utils.py         # YouTube integration
├── wer_utils.py            # Word Error Rate calculation
├── diff_viewer.py          # Text difference visualization
│
├── static/                  # Static assets
│   ├── js/                 # JavaScript modules
│   │   ├── audio-recorder.js    # Audio recording functionality
│   │   ├── preset-manager.js    # Practice preset management
│   │   ├── shadowing-main.js    # Shadowing practice logic
│   │   └── ...
│   ├── audio/              # Audio assets
│   └── style.css          # Global styles
│
├── templates/              # HTML templates
│   ├── index.html         # Main page
│   ├── shadowing.html     # Shadowing practice interface
│   ├── read_aloud.html    # Reading practice interface
│   └── ...
│
├── presets/               # Practice materials
│   ├── sentences/         # Sentence practice content
│   │   └── genre1/       # Organized by genre and level
│   └── shadowing/        # Shadowing practice content
│       ├── genre1/
│       ├── genre2/
│       └── genre3/
│
└── uploads/              # User uploaded files

```

## Technical Features

- **Authentication**: Replit authentication integration
- **API Integration**: OpenAI Whisper for speech recognition
- **Data Storage**: JSON-based logging system
- **Performance Metrics**: WER calculation and diff viewing
- **Audio Processing**: Real-time audio recording and processing
- **Cross-browser Support**: Modern web standards compliance

## Dependencies

- Flask
- OpenAI API
- YouTube API
- Audio processing libraries
- Speech recognition utilities

Each module is designed to be modular and maintainable, with clear separation of concerns between different functionalities.
