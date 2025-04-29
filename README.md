
# Language Learning Assistant

A comprehensive Flask-based web application designed to help users improve their language skills through various interactive exercises and real-time feedback mechanisms.

## 🌟 Core Features

### 1. Shadowing Practice
- **Preset Content**: Multiple genres and difficulty levels
- **Audio Playback**: High-quality audio samples
- **Real-time Recording**: Practice speaking alongside audio
- **Accuracy Analysis**: WER (Word Error Rate) calculation
- **Visual Feedback**: Color-coded diff view of transcriptions
- **Progress Tracking**: Level-based advancement system

### 2. Custom Shadowing
- **Audio Upload**: Support for MP3, M4A, WAV formats
- **Warm-up Feature**: Countdown sequence for preparation
- **Transcription**: Automatic speech-to-text conversion
- **Performance Analysis**: WER calculation and visual diff

### 3. Read Aloud Practice
- **Text Input**: Support for custom text or file upload
- **Speech Recognition**: High-accuracy transcription
- **Performance Metrics**: Detailed accuracy scoring
- **Visual Feedback**: Word-level difference highlighting

### 4. Sentence Practice
- **Structured Learning**: Progressive difficulty levels
- **Genre-based Content**: Various topics and styles
- **Audio Integration**: Professional recordings
- **Performance Tracking**: Progress monitoring

### 5. YouTube Integration
- **Video Selection**: Practice with YouTube content
- **Caption Verification**: Automatic subtitle checking
- **Transcription**: Speech-to-text for practice sessions

### 6. Analytics & Tracking
- **User Dashboard**: Performance overview
- **Progress Metrics**: WER tracking over time
- **Achievement System**: Level unlocking
- **Ranking System**: Compare with other users

## 🛠 Technical Architecture

### Backend (Python/Flask)
- **Audio Processing**: pydub for audio manipulation
- **Speech Recognition**: OpenAI Whisper API integration
- **WER Calculation**: Custom implementation
- **API Integration**: YouTube API, OpenAI API
- **Session Management**: Flask sessions
- **File Handling**: Secure file operations

### Frontend
- **Audio Recording**: Web Audio API
- **Playback Control**: Custom audio player
- **Real-time Updates**: AJAX/Fetch API
- **Visual Feedback**: Dynamic UI updates
- **Responsive Design**: Mobile-friendly interface

### Data Management
- **User Progress**: JSON-based logging
- **File Storage**: Organized preset structure
- **Performance Data**: WER metrics tracking
- **Authentication**: Replit authentication integration

## 📁 Project Structure
```
project/
├── app.py                 # Main application entry point
├── static/               # Static assets
│   ├── js/              # JavaScript modules
│   ├── audio/           # Audio assets
│   └── style.css        # Global styles
├── templates/           # HTML templates
├── presets/             # Practice materials
│   ├── sentences/       # Sentence practice content
│   └── shadowing/       # Shadowing practice content
└── utils/               # Utility modules
    ├── audio_utils.py   # Audio processing
    ├── wer_utils.py     # WER calculation
    └── youtube_utils.py # YouTube integration
```

## 🚀 Features in Detail

### Shadowing Practice Workflow
1. User selects genre and level
2. Original audio plays
3. User records shadowing attempt
4. System processes recording
5. WER calculation and feedback display

### Custom Shadowing Process
1. User uploads audio file
2. Automatic transcription
3. Warm-up countdown
4. Recording session
5. Performance analysis

### Read Aloud Evaluation
1. Text input/upload
2. User recording
3. Speech-to-text conversion
4. Accuracy calculation
5. Visual feedback generation

## 🔧 Technical Requirements
- Python 3.8+
- Flask
- OpenAI API access
- YouTube API credentials
- Modern web browser with audio support

## 🎯 Learning Path
1. Start with sentence practice
2. Progress to read aloud exercises
3. Begin shadowing with lower levels
4. Advance through difficulty levels
5. Practice with custom content

## 📈 Performance Metrics
- Word Error Rate (WER)
- Completion rates
- Level progression
- Practice consistency
- Genre diversity

The application emphasizes user progress and provides immediate feedback for continuous improvement in language learning.
