
class SentencePractice {
  constructor() {
    this.currentMode = 'playback';
    this.recorder = new AudioRecorder();
    this.sentences = [];
    this.currentSentence = null;
    this.setupEventListeners();
  }

  async setupEventListeners() {
    document.getElementById('practiceMode').addEventListener('change', (e) => {
      this.currentMode = e.target.value;
      document.getElementById('recordingControls').style.display = 
        this.currentMode === 'shadowing' ? 'block' : 'none';
    });
  }

  async loadSentences() {
    const response = await fetch('/api/sentences');
    this.sentences = await response.json();
    this.displaySentences();
  }

  displaySentences() {
    const container = document.getElementById('sentenceList');
    container.innerHTML = this.sentences.map((sentence, index) => `
      <div class="sentence-item" data-index="${index}">
        <div class="sentence-text">${sentence.text}</div>
        <div class="sentence-controls">
          <button class="play-btn">再生</button>
          ${this.currentMode === 'shadowing' ? '<button class="record-btn">録音</button>' : ''}
        </div>
        <audio class="sentence-audio" src="/audio/${sentence.audio_file}"></audio>
      </div>
    `).join('');

    container.addEventListener('click', async (e) => {
      if (e.target.classList.contains('play-btn')) {
        const item = e.target.closest('.sentence-item');
        const audio = item.querySelector('.sentence-audio');
        audio.play();
      } else if (e.target.classList.contains('record-btn')) {
        const item = e.target.closest('.sentence-item');
        this.currentSentence = item;
        await this.startRecording(item);
      }
    });
  }

  async startRecording(sentenceItem) {
    const audio = sentenceItem.querySelector('.sentence-audio');
    try {
      await this.recorder.startRecording();
      audio.currentTime = 0;
      audio.play();
    } catch (err) {
      alert('マイクの使用が許可されていません。');
      console.error(err);
    }
  }

  async stopRecording() {
    this.recorder.stop();
    document.getElementById('submitBtn').disabled = false;
    
    const audioURL = URL.createObjectURL(this.recorder.getBlob());
    document.getElementById('recordedAudio').src = audioURL;
  }

  async submitRecording() {
    const formData = new FormData();
    formData.append('recorded_audio', this.recorder.getBlob());
    formData.append('sentence_id', this.currentSentence.dataset.index);

    try {
      const response = await fetch('/evaluate_sentence', {
        method: 'POST',
        body: formData
      });

      const result = await response.json();
      this.displayResult(result);
    } catch (err) {
      console.error('Error submitting recording:', err);
    }
  }

  displayResult(result) {
    const resultBox = document.getElementById('resultBox');
    resultBox.innerHTML = `
      <h3>評価結果</h3>
      <p>精度: ${result.wer}%</p>
      <div class="diff-result">${result.diff_html}</div>
    `;
  }
}

const practice = new SentencePractice();
practice.loadSentences();
