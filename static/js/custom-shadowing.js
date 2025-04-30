class CustomShadowing {
  constructor() {
    this.recorder = new AudioRecorder();
    this.setupEventListeners();
  }

  setupEventListeners() {
    document.getElementById('uploadBtn').addEventListener('click', () => this.handleUpload());
    document.getElementById('startBtn').addEventListener('click', () => this.startRecording());
    document.getElementById('stopBtn').addEventListener('click', () => this.stopRecording());
    document.getElementById('submitBtn').addEventListener('click', () => this.submitRecording());
    document.getElementById('toggleTranscript').addEventListener('click', () => this.toggleTranscript());
  }

  showSpinner(message = '') {
    const spinner = document.getElementById('progressSpinner');
    const spinnerText = spinner.querySelector('.spinner-text');
    spinnerText.textContent = message;
    spinner.style.display = 'flex';
  }

  updateProgress(percent) {
    const spinnerText = document.querySelector('.spinner-text');
    spinnerText.textContent = `${Math.round(percent)}%`;
  }

  hideSpinner() {
    document.getElementById('progressSpinner').style.display = 'none';
  }

  async handleUpload() {
    const fileInput = document.getElementById('audioFileInput');
    const file = fileInput.files[0];
    if (!file) {
      alert('ファイルを選択してください');
      return;
    }

    const formData = new FormData();
    formData.append('audio', file);

    try {
      this.showSpinner('0%');

      const xhr = new XMLHttpRequest();
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const percent = (e.loaded / e.total) * 100;
          this.updateProgress(percent);
        }
      };

      const response = await new Promise((resolve, reject) => {
        xhr.onload = () => {
          if (xhr.status === 500) {
            reject(new Error('Server error occurred during transcription. Please try again.'));
            return;
          }
          resolve(xhr.response);
        };
        xhr.onerror = () => reject(new Error('Network error occurred'));
        xhr.responseType = 'json';
        xhr.open('POST', '/upload_custom_audio');
        xhr.send(formData);
      }).catch(error => {
        throw new Error(`Upload failed: ${error.message}`);
      });

      if (response.error) {
        throw new Error(response.error);
      }

      // Show practice section and setup audio
      document.getElementById('practiceSection').style.display = 'block';
      const audio = document.getElementById('originalAudio');
      audio.src = response.audio_url;
      audio.load();
      document.getElementById('transcriptionText').textContent = response.transcription;

    } catch (error) {
      console.error('Upload error:', error);
      alert(`Upload error: ${error.message}`);
    } finally {
      this.hideSpinner();
    }
  }

  async startRecording() {
    try {
      const originalAudio = document.getElementById('originalAudio');
      const warmupAudio = new Audio('/static/audio/warm-up.mp3');

      await this.recorder.startRecording();

      warmupAudio.play();

      warmupAudio.onended = () => {
        originalAudio.currentTime = 0;
        originalAudio.play();
      };

      document.getElementById('startBtn').disabled = true;
      document.getElementById('stopBtn').disabled = false;
    } catch (err) {
      console.error('Recording error:', err);
      alert('録音開始時にエラーが発生しました');
    }
  }

  stopRecording() {
    this.recorder.stop();
    document.getElementById('originalAudio').pause();
    document.getElementById('startBtn').disabled = false;
    document.getElementById('stopBtn').disabled = true;
    document.getElementById('submitBtn').disabled = false;

    const recordedBlob = this.recorder.getBlob();
    if (recordedBlob) {
      document.getElementById('recordedAudio').src = URL.createObjectURL(recordedBlob);
    }
  }

  toggleTranscript() {
    const transcriptText = document.getElementById('transcriptionText');
    const toggleBtn = document.getElementById('toggleTranscript');
    if (transcriptText.style.display === 'none') {
      transcriptText.style.display = 'block';
      toggleBtn.textContent = '非表示';
    } else {
      transcriptText.style.display = 'none';
      toggleBtn.textContent = '表示';
    }
  }

  async submitRecording() {
    const recordedBlob = this.recorder.getBlob();
    if (!recordedBlob) {
      alert('録音データがありません');
      return;
    }

    const formData = new FormData();
    formData.append('recorded_audio', recordedBlob);

    try {
      this.showSpinner('Evaluating...');

      const response = await fetch('/evaluate_custom_shadowing', {
        method: 'POST',
        body: formData
      });
      const data = await response.json();

      document.getElementById('resultBox').innerHTML = `
        <h3>✅ WER: ${data.wer}%</h3>
        <hr>
        <div class="diff-section">
          <h4>🔍 Diff:</h4>
          ${data.diff_html}
        </div>
      `;
    } catch (error) {
      console.error('Evaluation error:', error);
      alert('評価中にエラーが発生しました');
    } finally {
      this.hideSpinner();
    }
  }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
  new CustomShadowing();
});