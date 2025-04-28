
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
      const response = await fetch('/upload_custom_audio', {
        method: 'POST',
        body: formData
      });
      const data = await response.json();

      if (data.error) {
        alert('エラー: ' + data.error);
        return;
      }

      // Show practice section and setup audio
      document.getElementById('practiceSection').style.display = 'block';
      const audio = document.getElementById('originalAudio');
      audio.src = data.audio_url;
      audio.load(); // Force reload of audio element
      document.getElementById('transcriptionText').textContent = data.transcription;

    } catch (error) {
      console.error('Upload error:', error);
      alert('アップロード中にエラーが発生しました');
    }
  }

  async startRecording() {
    try {
      const originalAudio = document.getElementById('originalAudio');
      originalAudio.currentTime = 0;
      
      await this.recorder.startRecording();
      originalAudio.play();

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
    }
  }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
  new CustomShadowing();
});
