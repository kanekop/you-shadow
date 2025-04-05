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

  const audioUrl = `/presets/shadowing/${genre}/${level}/audio.mp3`;
  const scriptUrl = `/presets/shadowing/${genre}/${level}/script.txt`;

  try {
    console.log('Attempting to load audio and script from:', audioUrl, scriptUrl);
    const [audioResponse, scriptResponse] = await Promise.all([
      fetch(audioUrl),
      fetch(scriptUrl)
    ]);

    console.log('Audio fetch response:', audioResponse.status, audioResponse.statusText);
    console.log('Script fetch response:', scriptResponse.status, scriptResponse.statusText);

    if (!audioResponse.ok || !scriptResponse.ok) {
      throw new Error(`Failed to fetch resources: Audio ${audioResponse.status}, Script ${scriptResponse.status}`);
    }

    const audioBlob = await audioResponse.blob();
    const scriptText = await scriptResponse.text();


    originalAudioBlob = audioBlob;
    currentScript = scriptText;

    console.log('Audio and script loaded successfully.');

    document.getElementById("originalAudio").src = URL.createObjectURL(originalAudioBlob);
    document.getElementById("displayScript").textContent = currentScript;
    document.getElementById("presetLoaded").style.display = "block";
  } catch (error) {
    console.error("Error loading preset:", error);
    alert("プリセットの読み込みに失敗しました。");
  }
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

    // 🔒 提出ボタンを無効化
    document.getElementById("submitBtn").disabled = true;

    // ✅ ログを保存（通常の練習）
    await logAttempt(username, genre, level, data.wer, data.original_transcribed, data.user_transcribed);

    // ✅ WERが30%未満なら次のレベルを自動開放（shadowing.jsと同じロジック）
    if (data.wer < 30) {
      const resultDiv = document.getElementById("resultBox");
      resultDiv.innerHTML += "<br>🎉 あなたのWERが30%未満です！次のレベルに進めます！";

      const match = level.match(/^level(\d+)$/i);
      if (match) {
        const nextLevel = `level${parseInt(match[1]) + 1}`;
        await logAttempt(username, genre, nextLevel, 0.0, "(auto-unlocked)", "(auto-unlocked)");
        console.log(`🔓 次のレベル ${nextLevel} を自動解放しました`);
      }
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
  const levelSelect = document.getElementById("levelSelect");
  const currentLevel = levelSelect.value; // Store current selection

  highestLevels = await presetManager.fetchHighestLevels(username);
  await updateLevelSelect();

  // Restore previous selection if it exists
  if (currentLevel) {
    levelSelect.value = currentLevel;
  }
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