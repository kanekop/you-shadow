// Main shadowing functionality
const recorder = new AudioRecorder();
const presetManager = new PresetManager();
let originalAudioBlob = null;
let currentScript = "";
let highestLevels = {};

async function loadLastPractice() {
  try {
    const response = await fetch('/api/recordings/last');
    if (response.status === 204) {
      return; // No last practice
    }

    if (response.ok) {
      const data = await response.json();
      const audioElement = document.getElementById('shadowing-audio');
      const transcriptElement = document.getElementById('transcript-text');
      const sectionElement = document.getElementById('last-practice-section');

      audioElement.src = `/storage/${data.filename}`;
      transcriptElement.textContent = data.transcript;
      sectionElement.classList.remove('hidden');
    }
  } catch (error) {
    console.error('Error loading last practice:', error);
  }
}

async function setupPresets() {
  const presets = await presetManager.fetchPresets();
  const username = localStorage.getItem("username") || "guest";
  highestLevels = await presetManager.fetchHighestLevels(username);
  setupGenreSelect(presets);
}

function setupGenreSelect(presets) {
  const genreSelect = document.getElementById("genreSelect");
  genreSelect.innerHTML = '<option value="">-- ジャンル選択 --</option>';

  Object.keys(presets).forEach(genre => {
    const opt = document.createElement("option");
    opt.value = genre;
    opt.textContent = genre;
    genreSelect.appendChild(opt);
  });

  genreSelect.addEventListener("change", () => updateLevelSelect());
}

function setupUI() {
  const username = localStorage.getItem("username") || "anonymous";
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

  try {
    const result = await presetManager.loadPreset(genre, level);
    if (!result) return;

    originalAudioBlob = result.audioBlob;
    currentScript = result.script;

    document.getElementById("originalAudio").src = URL.createObjectURL(originalAudioBlob);
    document.getElementById("displayScript").textContent = currentScript;
    document.getElementById("presetLoaded").style.display = "block";
  } catch (error) {
    console.error("Error loading preset:", error);
    alert("プリセットの読み込みに失敗しました");
  }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', async function() {
  await loadLastPractice();
  await setupPresets();
  setupUI();
  setupEventListeners();
});

//500ms待つ処理を外した。ah.mp3追加
async function startRecording() {
  try {
    const originalAudio = document.getElementById("originalAudio");

    // 教材再生をリセットしておく
    originalAudio.pause();
    originalAudio.currentTime = 0;

    // 🎙️ 録音スタート
    await recorder.startRecording();

    const USE_WAIT_BEFORE_REPLAY = true;
    if (USE_WAIT_BEFORE_REPLAY) {
      // 保険として、録音直後に500ms待ってから ah.mp3 を再生
      await new Promise(resolve => setTimeout(resolve, 500));
    }


    // 🎧 ah.mp3 再生
    const ahAudio = new Audio("/static/audio/ah.mp3");
    ahAudio.play();

    // ah.mp3 再生後に教材再生
    ahAudio.onended = () => {
      console.log("✅ ah.mp3 finished. Starting main audio...");
      originalAudio.play();
    };

    // UI制御
    document.getElementById("startBtn").disabled = true;
    document.getElementById("stopBtn").disabled = false;

  } catch (err) {
    // 録音やストリーム停止処理（元のコードを維持）
    if (recorder) {
      try {
        recorder.stop();
        if (recorder.stream) {
          recorder.stream.getTracks().forEach(track => track.stop());
        }
      } catch (cleanupErr) {
        console.error("Cleanup error:", cleanupErr);
      }
    }

    alert("マイクの使用が許可されていません。");
    console.error("Recording error:", err);

    // UIを元に戻す
    document.getElementById("startBtn").disabled = false;
    document.getElementById("stopBtn").disabled = true;
  }
}

function stopRecording() {
  recorder.stop();
  document.getElementById("startBtn").disabled = false;
  document.getElementById("stopBtn").disabled = true;
  document.getElementById("submitBtn").disabled = false;

  const recordedBlob = recorder.getBlob();
  if (recordedBlob && recordedBlob.size > 0) {
    const audioURL = URL.createObjectURL(recordedBlob);
    const recordedAudio = document.getElementById("recordedAudio");
    recordedAudio.src = audioURL;
    recordedAudio.controls = true;
  } else {
    console.error("No recording data available");
  }
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
    const res = await fetch("/api/evaluate_shadowing", {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    displayResults(data);

    // 🔒 提出ボタンを無効化
    document.getElementById("submitBtn").disabled = true;

    // ✅ ログを保存（通常の練習）
    await logPractice(username, genre, level, data.wer, data.original_transcribed, data.user_transcribed);

    // ✅ WERが30%未満なら次のレベルを自動開放（shadowing.jsと同じロジック）
    if (data.wer < 30) {
      const resultDiv = document.getElementById("resultBox");
      resultDiv.innerHTML += "<br>🎉 あなたのWERが30%未満です！次のレベルに進めます！";

      const match = level.match(/^level(\d+)$/i);
      if (match) {
        const nextLevel = `level${parseInt(match[1]) + 1}`;
        await logPractice(username, genre, nextLevel, 0.0, "(auto-unlocked)", "(auto-unlocked)");
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
    await logPractice(username, genre, nextLevel, 0.0, "(auto-unlocked)", "(auto-unlocked)");
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

async function logPractice(username, genre, level, wer, original_transcribed, user_transcribed) {
  const response = await fetch("/api/practice/logs", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      username: username,
      genre: genre,
      level: level,
      wer: wer,
      original_transcribed: original_transcribed,
      user_transcribed: user_transcribed
    })
  });

  if (!response.ok) {
    throw new Error('Failed to log practice attempt');
  }

  return await response.json();
}