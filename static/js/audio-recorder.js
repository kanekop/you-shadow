
class AudioRecorder {
  constructor() {
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.stream = null;
  }

  async startRecording() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          sampleRate: 44100,
          channelCount: 1,
          autoGainControl: false,
          noiseSuppression: false
        }
      });

      const options = {
        mimeType: 'audio/webm',
        audioBitsPerSecond: 128000
      };

      this.mediaRecorder = new MediaRecorder(this.stream, options);
      this.audioChunks = [];

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.start(1000);
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

  getBlob() {
    return new Blob(this.audioChunks, { type: 'audio/webm' });
  }
}

window.AudioRecorder = AudioRecorder;
