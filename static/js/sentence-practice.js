
class SentencePractice {
  constructor() {
    this.sentences = [];
    this.currentSentenceIndex = 0;
    this.structure = null;
    this.isLoading = false;
    this.recorder = null;
    this.chunks = [];
    this.loadGenres();
    this.setupEventListeners();
  }

  setupEventListeners() {
    const genreSelect = document.getElementById('genreSelect');
    const levelSelect = document.getElementById('levelSelect');
    const modeSelect = document.getElementById('practiceMode');

    if (!genreSelect || !levelSelect || !modeSelect) {
      console.error('Required elements not found');
      return;
    }

    levelSelect.disabled = true;
    modeSelect.disabled = true;

    genreSelect.addEventListener('change', () => this.updateLevelSelect());
    levelSelect.addEventListener('change', (e) => {
      if (e.target.value) {
        modeSelect.disabled = false;
        this.loadSentences();
      }
    });
  }

  async loadGenres() {
    this.isLoading = true;
    try {
      const response = await fetch('/api/sentence_structure');
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      this.structure = await response.json();
      this.displayGenreSelect();
    } catch (error) {
      console.error('Error loading genres:', error);
    } finally {
      this.isLoading = false;
    }
  }

  displayGenreSelect() {
    const select = document.getElementById('genreSelect');
    if (!select) return;
    
    select.innerHTML = '<option value="">-- ジャンル選択 --</option>';
    
    for (const genre in this.structure) {
      const option = document.createElement('option');
      option.value = genre;
      option.textContent = genre;
      select.appendChild(option);
    }
  }

  updateLevelSelect() {
    const genre = document.getElementById('genreSelect').value;
    const select = document.getElementById('levelSelect');
    select.innerHTML = '<option value="">-- レベル選択 --</option>';

    if (!genre || !this.structure[genre]) return;

    select.disabled = false;
    
    this.structure[genre].forEach(level => {
      const option = document.createElement('option');
      option.value = level;
      option.textContent = level;
      select.appendChild(option);
    });
  }

  async loadSentences() {
    const genre = document.getElementById('genreSelect').value;
    const level = document.getElementById('levelSelect').value;

    if (!genre || !level) return;

    try {
      const response = await fetch(`/api/sentences/${genre}/${level}`);
      this.sentences = await response.json();
      this.displaySentences();
    } catch (error) {
      console.error('Error loading sentences:', error);
    }
  }

  async startRecording(sentenceDiv) {
    try {
      const constraints = {
        audio: {
          sampleRate: 44100,
          channelCount: 1,
          autoGainControl: false,
          noiseSuppression: false
        }
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      let options = {};
      const mimeTypes = ['audio/aac', 'audio/mp4', 'audio/webm', ''];

      for (let type of mimeTypes) {
        try {
          if (!type || MediaRecorder.isTypeSupported(type)) {
            options = type ? {
              mimeType: type,
              audioBitsPerSecond: 96000,
              bitsPerSecond: 96000
            } : {};
            console.log('Using audio format:', type || 'default');
            break;
          }
        } catch (e) {
          console.warn('Mime type not supported:', type);
        }
      }

      this.recorder = new MediaRecorder(stream, options);
      this.chunks = [];

      this.recorder.ondataavailable = e => this.chunks.push(e.data);
      this.recorder.onstop = () => this.handleRecordingStop(sentenceDiv);
      this.recorder.onerror = (e) => {
        console.error("❌ MediaRecorder error:", e);
        alert("Recording error: " + e.name);
      };

      this.recorder.start(1000); // Use smaller chunks

      // Update UI
      const recordBtn = sentenceDiv.querySelector('.record-btn');
      recordBtn.textContent = '⏹ Stop';
      recordBtn.onclick = () => this.stopRecording();

      // Play original audio after recording starts
      this.recorder.onstart = () => {
        console.log("🎙️ Recording started → playing audio");
        const audio = sentenceDiv.querySelector('audio');
        audio.currentTime = 0;
        audio.play();
      };
    } catch (err) {
      console.error('Recording error:', err);
      alert('マイクの使用が許可されていません。');
    }
  }

  stopRecording() {
    if (this.recorder && this.recorder.state === "recording") {
      this.recorder.stop();
    }
  }

  async handleRecordingStop(sentenceDiv) {
    const blob = new Blob(this.chunks, { type: 'audio/webm' });
    const recordedAudio = sentenceDiv.querySelector('.recorded-audio');
    recordedAudio.src = URL.createObjectURL(blob);
    recordedAudio.style.display = 'block';

    // Reset record button
    const recordBtn = sentenceDiv.querySelector('.record-btn');
    recordBtn.textContent = '🎤 Record';
    recordBtn.onclick = () => this.startRecording(sentenceDiv);

    // Evaluate recording
    const formData = new FormData();
    formData.append('audio', blob);
    formData.append('transcript', sentenceDiv.querySelector('.sentence-text').textContent);

    try {
      const response = await fetch('/evaluate_read_aloud', {
        method: 'POST',
        body: formData
      });
      const data = await response.json();
      
      const resultDiv = sentenceDiv.querySelector('.eval-result');
      if (!resultDiv) {
        const newResultDiv = document.createElement('div');
        newResultDiv.className = 'eval-result';
        sentenceDiv.appendChild(newResultDiv);
      }
      
      const evalResult = sentenceDiv.querySelector('.eval-result');
      evalResult.innerHTML = `
        <div class="wer-score">WER: ${data.wer}%</div>
        <div class="eval-content">
          <div class="text-label">Original text:</div>
          <div class="diff-result">${data.diff_html}</div>
          <div class="text-label">Your recording:</div>
          <div class="transcribed-text">${data.transcribed}</div>
        </div>
      `;
      evalResult.style.display = 'block';
    } catch (error) {
      console.error('Evaluation error:', error);
    }
  }

  displaySentences() {
    const container = document.getElementById('sentenceList');
    container.innerHTML = '';

    this.sentences.forEach((sentence, index) => {
      const sentenceDiv = document.createElement('div');
      sentenceDiv.className = 'sentence-item';
      
      const textSpan = document.createElement('span');
      textSpan.className = 'sentence-text';
      textSpan.textContent = sentence.text;
      
      const audio = document.createElement('audio');
      audio.src = sentence.audio_file;
      audio.controls = true;
      
      const recordedAudio = document.createElement('audio');
      recordedAudio.className = 'recorded-audio';
      recordedAudio.controls = true;
      recordedAudio.style.display = 'none';
      
      const recordBtn = document.createElement('button');
      recordBtn.className = 'record-btn';
      recordBtn.textContent = '🎤 Record';
      recordBtn.onclick = () => this.startRecording(sentenceDiv);
      
      sentenceDiv.appendChild(textSpan);
      sentenceDiv.appendChild(document.createElement('br'));
      sentenceDiv.appendChild(audio);
      sentenceDiv.appendChild(recordedAudio);
      sentenceDiv.appendChild(recordBtn);
      
      container.appendChild(sentenceDiv);
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  new SentencePractice();
});
