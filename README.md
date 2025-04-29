
# Language Learning Assistant 🌍

A sophisticated Flask-based web application designed to help users improve their language pronunciation and speaking skills through interactive exercises, real-time feedback, and progress tracking.

## 🌟 Key Features

### 1. Shadowing Practice System
- **Preset Content Library**
  - Multiple genres and progressive difficulty levels
  - High-quality audio samples with professional recordings
  - Customizable practice sessions
  - Real-time performance feedback

- **Advanced Recording System**  
  - Synchronized audio playback and recording
  - Automatic speech recognition
  - Word Error Rate (WER) calculation
  - Visual feedback with color-coded differences

- **Progress Tracking**
  - Level-based advancement system
  - Performance metrics tracking
  - Achievement unlocking
  - Detailed practice history

### 2. Custom Shadowing
- **File Support**
  - Multiple audio formats (MP3, M4A, WAV)
  - Automatic transcription
  - Custom practice material creation
  
- **Practice Features**
  - Warm-up countdown system
  - Audio playback controls
  - Performance analysis
  - WER calculation

### 3. Sentence Practice
- **Structured Learning**
  - Progressive difficulty levels
  - Genre-based content organization
  - Professional audio recordings
  - Text visibility toggles

- **Practice Modes**
  - Playback only mode
  - Shadowing practice mode
  - Customizable WER targets
  - Instant feedback system

### 4. Read Aloud Practice
- **Input Options**
  - Direct text input
  - Text file upload
  - Custom practice material
  
- **Evaluation System**
  - Speech recognition
  - Accuracy scoring
  - Word-level difference highlighting
  - Performance metrics

### 5. Analytics Dashboard
- **User Progress**
  - Practice streak tracking
  - Performance visualization
  - Level completion status
  - Detailed practice logs

## 🛠️ Technical Architecture

### Backend (Python/Flask)
- **Core Components**
  - Flask web framework
  - OpenAI Whisper for speech recognition
  - Custom WER calculation implementation
  - JSON-based logging system

### Frontend
- **Technologies**
  - HTML5/CSS3
  - Vanilla JavaScript
  - Web Audio API
  - Dynamic UI updates

### Authentication
- **Replit Auth Integration**
  - Secure user authentication
  - Session management
  - User progress tracking

## 📦 Project Structure
```
project/
├── app.py                  # Main application entry point
├── static/                # Static assets
│   ├── js/               # JavaScript modules
│   ├── audio/            # Audio resources
│   └── style.css         # Global styles
├── templates/            # HTML templates
├── presets/              # Practice materials
│   ├── sentences/        # Sentence practice content
│   └── shadowing/        # Shadowing practice content
└── utils/               # Utility modules
    ├── audio_utils.py    # Audio processing
    ├── wer_utils.py      # WER calculation
    └── diff_viewer.py    # Difference visualization
```

## 🚀 Getting Started

1. **Setup**
   - Clone the repository
   - Install dependencies from `requirements.txt`
   - Configure environment variables

2. **Running the Application**
   - Execute `python app.py`
   - Access the application at `http://0.0.0.0:5000`

## 🎯 Usage Guide

### Shadowing Practice
1. Select genre and difficulty level
2. Listen to the original audio
3. Practice shadowing with recording
4. Review performance feedback
5. Track progress through levels

### Custom Shadowing
1. Upload audio file
2. Wait for transcription
3. Use warm-up countdown
4. Record shadowing attempt
5. Review performance metrics

### Sentence Practice
1. Choose genre and level
2. Select practice mode
3. Set WER target
4. Practice with audio
5. Review feedback

## 📊 Performance Metrics

- **Word Error Rate (WER)**
  - Measures pronunciation accuracy
  - Tracks improvement over time
  - Unlocks new levels

- **Practice Statistics**
  - Session frequency
  - Completion rates
  - Level progression
  - Genre diversity

## 🔒 Security Features

- **Replit Authentication**
  - Secure user sessions
  - Progress persistence
  - User-specific content

## 🌱 Future Enhancements

- Enhanced analytics dashboard
- Additional practice modes
- More content genres
- Performance optimization
- Mobile responsiveness improvements

## 📝 Contributing

We welcome contributions! Please feel free to submit pull requests or open issues for improvements.

## 📄 License

This project is proprietary and confidential. All rights reserved.
