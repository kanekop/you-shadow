let recorder;
let chunks = [];
let originalAudioBlob = null;
let currentScript = "";
let presetData = {}; // ← グローバル変数として定義
let unlockedLevels = {};  // ← 解放レベルを保持

document.addEventListener("DOMContentLoaded", () => {
  fetchPresets();

  document.getElementById("startBtn").addEventListener("click", startRecording);
  document.getElementById("stopBtn").addEventListener("click", stopRecording);
  document.getElementById("submitBtn").addEventListener("click", submitRecording);
});

async function fetchPresets() {
  const res = await fetch("/api/presets");
  presetData = await res.json();

  const genreSelect = document.getElementById("genreSelect");
  genreSelect.innerHTML = '<option value="">-- ジャンル選択 --</option>';
  for (const genre in presetData) {
    const opt = document.createElement("option");
    opt.value = genre;
    opt.textContent = genre;
    genreSelect.appendChild(opt);
  }

  const username = localStorage.getItem("username") || "guest";
  await fetchUnlockedLevels(username);

  genreSelect.addEventListener("change", () => {
    updateLevelSelect();
  });

  document.getElementById("levelSelect").addEventListener("change", loadPreset);
}

async function loadPreset() {
  const genre = document.getElementById("genreSelect").value.trim().toLowerCase();
  const level = document.getElementById("levelSelect").value.trim().toLowerCase();

  if (!genre || !level) return;

  const audioUrl = `/presets/${genre}/${level}/audio.mp3`;
  const scriptUrl = `/presets/${genre}/${level}/script.txt`;

  document.getElementById("originalAudio").src = audioUrl;
  originalAudioBlob = await fetch(audioUrl).then(res => res.blob());

  currentScript = await fetch(scriptUrl).then(res => res.text());
  document.getElementById("displayScript").textContent = currentScript;

  document.getElementById("presetLoaded").style.display = "block";
}

function startRecording() {
  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      recorder = new MediaRecorder(stream);
      chunks = [];
      recorder.ondataavailable = e => chunks.push(e.data);
      recorder.onstop = handleStop;
      recorder.start();

      document.getElementById("startBtn").disabled = true;
      document.getElementById("stopBtn").disabled = false;
      document.getElementById("originalAudio").currentTime = 0;
      document.getElementById("originalAudio").play();
    })
    .catch(err => {
      alert("マイクの使用が許可されていません。");
      console.error(err);
    });
}

function stopRecording() {
  if (recorder && recorder.state === "recording") {
    recorder.stop();
    document.getElementById("startBtn").disabled = false;
    document.getElementById("stopBtn").disabled = true;
    document.getElementById("submitBtn").disabled = false;
  }
}

function handleStop() {
  const recordedBlob = new Blob(chunks, { type: 'audio/webm' });
  document.getElementById("recordedAudio").src = URL.createObjectURL(recordedBlob);
  document.recordedBlob = recordedBlob;
}

function submitRecording() {
  if (!originalAudioBlob || !document.recordedBlob || !currentScript) {
    alert("プリセットと録音が揃っていません。");
    return;
  }

  const formData = new FormData();
  formData.append("original_audio", originalAudioBlob);
  formData.append("recorded_audio", document.recordedBlob);

  const username = localStorage.getItem("username") || "anonymous";
  const genre = document.getElementById("genreSelect").value.trim().toLowerCase();
  const level = document.getElementById("levelSelect").value.trim().toLowerCase();

  formData.append("username", username);
  formData.append("genre", genre);
  formData.append("level", level);

  fetch("/evaluate_shadowing", {
    method: "POST",
    body: formData
  })
  .then(res => res.json())
  .then(data => {
    if (data.error) {
      document.getElementById("resultBox").innerText = "❌ エラー: " + data.error;
    } else {
      document.getElementById("resultBox").innerHTML = `
        ✅ WER: ${data.wer}%<br>
        <hr>
        🔍 Diff:<br>${data.diff_html}<br>
        <hr>
        📜 Original Transcript:<br>${data.original_transcribed}<br>
        <hr>
        🗣️ Your Transcription:<br>${data.user_transcribed}
      `;
    }
    if (data.wer < 30) {
      updateLevelSelect();
    }
  })
  .catch(err => {
    console.error("提出時エラー:", err);
    document.getElementById("resultBox").innerText = "❌ 提出失敗";
  });
}

function getUnlockedLevels() {
  const key = "unlockedLevels_" + (localStorage.getItem("username") || "guest");
  const data = localStorage.getItem(key);
  return data ? JSON.parse(data) : {};
}

function updateLevelSelect() {
  const genre = document.getElementById("genreSelect").value.trim().toLowerCase();
  const levelSelect = document.getElementById("levelSelect");
  levelSelect.innerHTML = '<option value="">-- レベル選択 --</option>';

  const levels = presetData[genre] || [];
  const unlocked = unlockedLevels[genre] || [];

  levels.forEach(level => {
    const opt = document.createElement("option");
    opt.value = level;

    const isFirstLevel = level.toLowerCase() === "level1";
    const isUnlocked = unlocked.includes(level.toLowerCase());

    if (isFirstLevel || isUnlocked) {
      opt.textContent = level;
    } else {
      opt.textContent = `🔒 ${level}`;
      opt.disabled = true;
    }

    levelSelect.appendChild(opt);
  });
}

async function fetchUnlockedLevels(username) {
  const res = await fetch(`/api/unlocked_levels/${username}`);
  unlockedLevels = await res.json();
  console.log("✅ Unlocked levels fetched:", unlockedLevels);
}