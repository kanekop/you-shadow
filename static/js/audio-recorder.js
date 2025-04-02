
// Audio recording functionality
export class AudioRecorder {
  constructor() {
    this.recorder = null;
    this.chunks = [];
  }

  async startRecording() {
    console.log("🎤 Requesting microphone access...");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 44100,
          channelCount: 1,
          autoGainControl: false,
          noiseSuppression: false
        }
      });
      
      console.log("✅ Microphone access granted");
      const options = this.getSupportedMimeType();
      this.recorder = new MediaRecorder(stream, options);
      this.chunks = [];
      
      this.recorder.ondataavailable = e => this.chunks.push(e.data);
      this.setupRecorderEvents();
      
      this.recorder.start(1000);
    } catch (err) {
      console.error("❌ Recording error:", err);
      throw err;
    }
  }

  getSupportedMimeType() {
    const mimeTypes = ['audio/aac', 'audio/mp4', 'audio/webm', ''];
    for (let type of mimeTypes) {
      try {
        if (!type || MediaRecorder.isTypeSupported(type)) {
          return type ? {
            mimeType: type,
            audioBitsPerSecond: 96000,
            bitsPerSecond: 96000
          } : {};
        }
      } catch (e) {
        console.warn('Mime type not supported:', type);
      }
    }
    return {};
  }

  setupRecorderEvents() {
    this.recorder.onstart = () => console.log("🎙️ Recording started");
    this.recorder.onpause = () => console.log("⏸️ Recording paused");
    this.recorder.onresume = () => console.log("▶️ Recording resumed");
    this.recorder.onstop = () => console.log("⏹️ Recording stopped");
    this.recorder.onerror = (e) => console.error("❌ MediaRecorder error:", e);
  }

  stop() {
    if (this.recorder?.state === "recording") {
      this.recorder.stop();
    }
  }

  getBlob() {
    return new Blob(this.chunks, { type: 'audio/webm' });
  }
}
