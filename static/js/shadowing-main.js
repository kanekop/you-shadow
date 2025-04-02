
// Main shadowing functionality
const recorder = new AudioRecorder();
const presetManager = new PresetManager();

document.addEventListener("DOMContentLoaded", async () => {
  const presets = await presetManager.fetchPresets();
  setupUI();
  setupEventListeners();
});

function setupUI() {
  const username = localStorage.getItem("username") || "（未設定）";
  document.getElementById("userDisplay").textContent = `🧑‍💻 現在のユーザー：${username}`;
}

function setupEventListeners() {
  document.getElementById("startBtn").addEventListener("click", startRecording);
  document.getElementById("stopBtn").addEventListener("click", stopRecording);
  document.getElementById("submitBtn").addEventListener("click", submitRecording);
}

// ... Rest of the shadowing functionality ...
