class AudioRecorder {
  constructor() {
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.stream = null;
    this.startTime = null;//追加
  }

  async startRecording() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          sampleRate: 44100,
          channelCount: 1,
          autoGainControl: true,
          noiseSuppression: true,
          echoCancellation: true,
        }
      });

      const options = {
        mimeType: 'audio/webm',
        audioBitsPerSecond: 128000
      };

      this.mediaRecorder = new MediaRecorder(this.stream, options);
      this.audioChunks = [];

      this.mediaRecorder.onstart = () => {
        console.log("✅ MediaRecorder has started.");
      };

      this.mediaRecorder.onstop = () => {
        console.log("🛑 MediaRecorder has stopped.");
      };

      this.mediaRecorder.ondataavailable = (event) => {
        console.log("📦 ondataavailable fired:", event.data?.size);
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      
      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.start(100);
      this.startTime = Date.now(); // ⬅️ スタート時間を記録
      console.log('Recording started');
    } catch (err) {
      console.error('Failed to start recording:', err);
      throw err;
    }
  }

  stop() {
    if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
      this.mediaRecorder.stop();
      this.stream.getTracks().forEach(track => track.stop());
      console.log('Recording stopped');
    }
  }

  getBlob(cutHeadMs = 500) {
    const fullBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
  
    if (cutHeadMs === 0) {
      return fullBlob;
    }
  
    // 💡 カット処理は後段で行うため、ここではそのまま返す
    return fullBlob;
  }
}

window.AudioRecorder = AudioRecorder;