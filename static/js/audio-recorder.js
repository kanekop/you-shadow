export class AudioRecorder {
  constructor() {
    this.mediaRecorder = null;
    this.audioChunks = [];
  }

  async startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.mediaRecorder = new MediaRecorder(stream);
    this.audioChunks = [];

    this.mediaRecorder.ondataavailable = (event) => {
      this.audioChunks.push(event.data);
    };

    this.mediaRecorder.start();
  }

  stop() {
    if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
      this.mediaRecorder.stop();
    }
  }

  getBlob() {
    return new Blob(this.audioChunks, { type: 'audio/webm' });
  }
}