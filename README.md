
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
├── app.py                     # Main application entry point
├── static/                    # Static assets
│   ├── js/                   # JavaScript modules
│   │   ├── components/       # Reusable components
│   │   │   ├── audio-recorder.js
│   │   │   └── preset-manager.js
│   │   ├── features/        # Feature-specific logic
│   │   │   ├── compare.js
│   │   │   ├── custom-shadowing.js
│   │   │   ├── ranking.js
│   │   │   ├── sentence-practice.js
│   │   │   └── shadowing-main.js
│   │   └── utils/          # Shared utilities
│   │       └── common.js
│   ├── css/                # Styles
│   │   ├── components/     # Component styles
│   │   ├── features/       # Feature styles
│   │   └── main.css       # Global styles
│   └── assets/            # Media and other assets
│       ├── audio/         # Audio resources
│       └── images/        # Image resources
├── templates/               # HTML templates
│   ├── compare.html        # Text comparison page
│   ├── custom_shadowing.html
│   ├── dashboard.html      # User progress dashboard
│   ├── ranking.html        # User rankings
│   ├── sentence_practice.html
│   ├── shadowing.html
│   └── other templates
├── presets/                 # Practice materials
│   ├── sentences/          # Sentence practice content
│   │   └── genre1/        # Organized by genre and level
│   └── shadowing/         # Shadowing practice content
│       ├── genre1/
│       ├── genre2/
│       ├── genre3/
│       └── genre4/        # Includes special content like riddles
├── utils/                  # Core utilities
│   ├── audio/            # Audio-related utilities
│   │   ├── __init__.py
│   │   ├── processor.py  # Audio processing
│   │   └── transcribe.py # Transcription handling
│   ├── metrics/          # Evaluation metrics
│   │   ├── __init__.py
│   │   ├── wer.py       # WER calculation
│   │   └── diff.py      # Difference visualization
│   ├── integrations/     # External services
│   │   ├── __init__.py
│   │   └── youtube.py   # YouTube integration
│   └── core/            # Core functionality
│       ├── __init__.py
│       └── logger.py    # Logging functionality
├── uploads/               # User uploaded files
└── .replit               # Replit configuration
```

## 🔑 Key Features (Updated)

### 1. Core Learning Features
- **Shadowing Practice** - Practice with preset audio content, organized by genre and level
- **Custom Shadowing** - Upload and practice with your own audio, with warm-up countdown
- **Sentence Practice** - Progressive difficulty level practice with professional audio
- **Text Comparison** - Compare and analyze text differences with WER calculation
- **Read Aloud Practice** - Practice with custom text input and instant feedback
- **YouTube Integration** - Practice with YouTube video transcripts

### 2. Progress Tracking
- **User Dashboard** - Track your learning progress
- **Performance Analytics** - WER scores and improvements
- **Rankings** - Compare performance with other users
- **Achievement System** - Level-based progression

### 3. Technical Features
- **Secure Authentication** - Replit Auth integration
- **Audio Processing** - Support for MP3, M4A, WAV, and WEBM formats
- **YouTube Integration** - Practice with YouTube video transcripts and captions
- **Object Storage** - Secure file management with Replit Storage
- **Real-time Feedback** - WER calculation and color-coded difference highlighting
- **Logging System** - Comprehensive activity and performance tracking

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

## 💪 Performance Optimization

- **Audio Processing**
  - Lazy loading of audio resources
  - Automatic audio format conversion
  - Progressive audio loading
  - Audio caching strategy

- **Application Performance**
  - Static asset optimization
  - Response compression
  - Database query optimization
  - Browser caching implementation

## 🌱 Future Enhancements

- Enhanced analytics dashboard
- Additional practice modes
- More content genres
- Advanced performance metrics
- Mobile responsiveness improvements
- Offline mode support

## 📝 Contributing

We welcome contributions! Please feel free to submit pull requests or open issues for improvements.

## 📄 License

This project is proprietary and confidential. All rights reserved.
