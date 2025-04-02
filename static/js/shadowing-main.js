
// Main shadowing functionality
const recorder = new AudioRecorder();
const presetManager = new PresetManager();
let originalAudioBlob = null;
let currentScript = "";
let highestLevels = {};

document.addEventListener("DOMContentLoaded", async () => {
  await setupPresets();
  setupUI();
  setupEventListeners();
});

async function setupPresets() {
  const presets = await presetManager.fetchPresets();
  const username = localStorage.getItem("username") || "guest";
  highestLevels = await presetManager.fetchHighestLevels(username);
  
  setupGenreSelect(presets);
}

function setupGenreSelect(presets) {
  const genreSelect = document.getElementById("genreSelect");
  genreSelect.innerHTML = '<option value="">-- ジャンル選択 --</option>';
  
  for (const genre in presets) {
    const opt = document.createElement("option");
    opt.value = genre;
    opt.textContent = genre;
    genreSelect.appendChild(opt);
  }
  
  genreSelect.addEventListener("change", updateLevelSelect);
}

function setupUI() {
  const username = localStorage.getItem("username") || "（未設定）";
  document.getElementById("userDisplay").textContent = `🧑‍💻 現在のユーザー：${username}`;
}

function setupEventListeners() {
  document.getElementById("startBtn").addEventListener("click", startRecording);
  document.getElementById("stopBtn").addEventListener("click", stopRecording);
  document.getElementById("submitBtn").addEventListener("click", submitRecording);
  document.getElementById("levelSelect").addEventListener("change", loadPreset);
}

async function updateLevelSelect() {
  const genre = document.getElementById("genreSelect").value;
  const levelSelect = document.getElementById("levelSelect");
  levelSelect.innerHTML = '<option value="">-- レベル選択 --</option>';

  if (!genre) return;

  const presets = await presetManager.fetchPresets();
  let maxUnlocked = 1;
  const match = (highestLevels[genre] || "").match(/^level(\d+)$/);
  if (match) {
    maxUnlocked = parseInt(match[1]);
  }

  presets[genre]
    .sort((a, b) => {
      const aNum = parseInt(a.replace("level", ""));
      const bNum = parseInt(b.replace("level", ""));
      return aNum - bNum;
    })
    .forEach(level => {
      const opt = document.createElement("option");
      opt.value = level;
      
      const levelNum = parseInt(level.replace("level", ""));
      if (levelNum <= maxUnlocked || levelNum === 1) {
        opt.textContent = level;
      } else {
        opt.textContent = `🔒 ${level}`;
        opt.disabled = true;
      }
      
      levelSelect.appendChild(opt);
    });
}

async function loadPreset() {
  const genre = document.getElementById("genreSelect").value;
  const level = document.getElementById("levelSelect").value;

  if (!genre || !level) return;

  const preset = await presetManager.loadPreset(genre, level);
  if (!preset) return;

  originalAudioBlob = preset.audioBlob;
  currentScript = preset.script;

  document.getElementById("originalAudio").src = URL.createObjectURL(originalAudioBlob);
  document.getElementById("displayScript").textContent = currentScript;
  document.getElementById("presetLoaded").style.display = "block";
}

async function startRecording() {
  try {
    document.getElementById("originalAudio").currentTime = 0;
    await recorder.startRecording();
    document.getElementById("originalAudio").play();
    
    document.getElementById("startBtn").disabled = true;
    document.getElementById("stopBtn").disabled = false;
  } catch (err) {
    alert("マイクの使用が許可されていません。");
    console.error(err);
  }
}

function stopRecording() {
  recorder.stop();
  document.getElementById("startBtn").disabled = false;
  document.getElementById("stopBtn").disabled = true;
  document.getElementById("submitBtn").disabled = false;
  
  const audioURL = URL.createObjectURL(recorder.getBlob());
  document.getElementById("recordedAudio").src = audioURL;
}

async function submitRecording() {
  if (!originalAudioBlob || !recorder.getBlob() || !currentScript) {
    alert("プリセットと録音が揃っていません。");
    return;
  }

  const formData = new FormData();
  formData.append("original_audio", originalAudioBlob);
  formData.append("recorded_audio", recorder.getBlob());
  
  const username = localStorage.getItem("username") || "anonymous";
  const genre = document.getElementById("genreSelect").value;
  const level = document.getElementById("levelSelect").value;

  formData.append("username", username);
  formData.append("genre", genre);
  formData.append("level", level);

  try {
    const res = await fetch("/evaluate_shadowing", {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    displayResults(data);
    
    if (data.wer < 30) {
      await handleLevelUnlock(username, genre, level);
    }
    
    await updateHighestLevels();
  } catch (err) {
    console.error("提出時エラー:", err);
    document.getElementById("resultBox").innerText = "❌ 提出中にエラーが発生しました。";
  }
}

function displayResults(data) {
  const resultDiv = document.getElementById("resultBox");
  
  if (data.error) {
    resultDiv.innerText = "❌ エラー: " + data.error;
    return;
  }

  resultDiv.innerHTML = `
    ✅ WER: ${data.wer}%<br>
    <hr>
    🔍 Diff:
    <div>
      <label><input type="radio" name="diffMode" value="user" checked> ユーザーベース</label>
      <label><input type="radio" name="diffMode" value="original"> 教材ベース</label>
    </div>
    <div id="diffResult">${data.diff_user}</div>
    <hr>
    📜 Original Transcript:<br>${data.original_transcribed}<br>
    <hr>
    🗣️ Your Transcription:<br>${data.user_transcribed}
  `;

  const radios = document.getElementsByName("diffMode");
  radios.forEach(radio => {
    radio.addEventListener("change", () => {
      const selected = [...radios].find(r => r.checked).value;
      document.getElementById("diffResult").innerHTML =
        selected === "original" ? data.diff_original : data.diff_user;
    });
  });
}

async function handleLevelUnlock(username, genre, level) {
  const match = level.match(/^level(\d+)$/i);
  if (match) {
    const nextLevel = `level${parseInt(match[1]) + 1}`;
    await logAttempt(username, genre, nextLevel, 0.0, "(auto-unlocked)", "(auto-unlocked)");
    console.log(`🔓 次のレベル ${nextLevel} を自動解放しました`);
  }
}

async function updateHighestLevels() {
  const username = localStorage.getItem("username") || "guest";
  highestLevels = await presetManager.fetchHighestLevels(username);
  updateLevelSelect();
}

async function logAttempt(username, genre, level, wer, original, user) {
  await fetch("/api/log_attempt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user: username,
      genre: genre,
      level: level,
      wer: wer,
      original_transcribed: original,
      user_transcribed: user
    })
  });
}
