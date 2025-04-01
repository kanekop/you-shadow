let recorder;
let chunks = [];
let originalAudioBlob = null;
let currentScript = "";
let presetData = {}; // ← グローバル変数として定義
let unlockedLevels = {};  // ← 解放レベルを保持
let highestLevels = {}; // 👈 新しい最高レベル状態

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
  await fetchHighestLevels(username);

  genreSelect.addEventListener("change", updateLevelSelect);

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


/**
 * ユーザーのマイクから音声を録音し、録音の開始が確認された時点で
 * 同時に元音声（originalAudio）の再生を開始する。
 * 録音と再生のズレを防ぐため、MediaRecorder の onstart イベント内で再生を開始する設計。
 * 録音データは chunks 配列に蓄積され、停止時に blob 化される。
 */
/**
 * Starts recording the user's microphone input and plays the original audio
 * only after the recording has fully started. This ensures proper sync
 * between playback and recording by triggering playback inside the
 * MediaRecorder's `onstart` event. Audio chunks are stored for later use.
 */
function startRecording() {
  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      recorder = new MediaRecorder(stream);
      chunks = [];

      recorder.ondataavailable = e => chunks.push(e.data);
      recorder.onstop = handleStop;

      // ✅ 録音が完全に開始されたタイミングで再生する
      recorder.onstart = () => {
        console.log("🎙️ 録音開始を確認 → 再生スタート");
        document.getElementById("originalAudio").currentTime = 0;
        document.getElementById("originalAudio").play();
      };

      recorder.start(); // 🎙️ 録音スタート

      // UI 更新は録音開始と同時に行ってOK
      document.getElementById("startBtn").disabled = true;
      document.getElementById("stopBtn").disabled = false;
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

async function submitRecording() {
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

  try {
    const res = await fetch("/evaluate_shadowing", {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    const resultDiv = document.getElementById("resultBox");

    if (data.error) {
      resultDiv.innerText = "❌ エラー: " + data.error;
      return;
    }
    
    // ✅ 結果を表示（WERとスクリプト両方）
    resultDiv.innerHTML = `
      ✅ WER: ${data.wer}%<br>
      <hr>
      🔍 Diff:<br>${data.diff_html}<br>
      <hr>
      📜 Original Transcript:<br>${data.original_transcribed}<br>
      <hr>
      🗣️ Your Transcription:<br>${data.user_transcribed}
    `;

    // ✅ ログを保存（本練習）
    await logAttempt(username, genre, level, data.wer, data.original_transcribed, data.user_transcribed);

    // ✅ WERが30%未満なら次レベルを自動解放
    if (data.wer < 30) {
      resultDiv.innerHTML += "<br>🎉 あなたのWERが30%未満です！次のレベルに進めます！";

      const match = level.match(/^level(\d+)$/i);
      if (match) {
        const nextLevel = `level${parseInt(match[1]) + 1}`;
        await logAttempt(username, genre, nextLevel, 0.0, "(auto-unlocked)", "(auto-unlocked)");
        console.log(`🔓 次のレベル ${nextLevel} を自動解放しました`);
      }
    }

    // ✅ 最新の最高到達レベルを取得してUI更新
    await fetchHighestLevels(username);
    updateLevelSelect();

    
  } catch (err) {
    console.error("提出時エラー:", err);
    document.getElementById("resultBox").innerText = "❌ 提出中にエラーが発生しました。";
  }
}


function getUnlockedLevels() {
  const key = "unlockedLevels_" + (localStorage.getItem("username") || "guest");
  const data = localStorage.getItem(key);
  return data ? JSON.parse(data) : {};
}

/**
 * レベルセレクトボックスを現在の解放状況に応じて更新する
 */
async function updateLevelSelect() {
  const genre = document.getElementById("genreSelect").value.trim().toLowerCase();
  const levelSelect = document.getElementById("levelSelect");
  levelSelect.innerHTML = '<option value="">-- レベル選択 --</option>';

  if (!genre || !presetData[genre]) return;

  // 🎯 このジャンルでの最大解放レベル（数値）を取得
  let maxUnlocked = 1;
  const match = (highestLevels[genre] || "").match(/^level(\d+)$/);
  if (match) {
    maxUnlocked = parseInt(match[1]);
  }

  // 🎯 セレクトボックスにレベルを設定
  // 🔽 レベル番号順にソートしてからセレクトに追加
  presetData[genre]
    .slice()
    .sort((a, b) => {
      const aNum = parseInt(a.replace("level", ""));
      const bNum = parseInt(b.replace("level", ""));
      return aNum - bNum;
    })
    .forEach(level => {
      const opt = document.createElement("option");
      opt.value = level;

      const match = level.match(/^level(\d+)$/);
      const levelNum = match ? parseInt(match[1]) : 0;

      if (levelNum <= maxUnlocked || levelNum === 1) {
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

/**
 * サーバーに提出結果（練習ログ）を送信する
 */
/**
 * サーバーに提出結果（練習ログ）を送信する
 */
async function logAttempt(username, genre, level, wer, original, user) {
  const res = await fetch("/api/log_attempt", {
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

  const result = await res.json();
  console.log("📝 Logged:", result);
}

/**
 * サーバーからユーザーの最高到達レベル一覧を取得する
 */
async function fetchHighestLevels(username) {
  const res = await fetch(`/api/highest_levels/${username}`);
  highestLevels = await res.json();
  console.log("⭐ Highest levels fetched:", highestLevels);
}

function displayResults(data) {
  document.getElementById('werScore').innerText = `WER: ${data.wer.toFixed(1)}%`;

  const diffUser = data.diff_user;
  const diffOriginal = data.diff_original;

  const diffContainer = document.getElementById('diffResult');
  const radios = document.getElementsByName('diffMode');

  function updateDiffView() {
    const selected = [...radios].find(r => r.checked).value;
    diffContainer.innerHTML = selected === 'original' ? diffOriginal : diffUser;
  }

  radios.forEach(radio => {
    radio.addEventListener('change', updateDiffView);
  });

  updateDiffView();
}
