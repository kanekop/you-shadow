let recorder;
let chunks = [];
let referenceText = "";

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("startBtn").addEventListener("click", startRecording);
  document.getElementById("stopBtn").addEventListener("click", stopRecording);
  document.getElementById("submitBtn").addEventListener("click", submitRecording);
  document.getElementById("loadTextBtn").addEventListener("click", loadText);
});

function loadText() {
  referenceText = document.getElementById("referenceInput").value.trim();
  if (!referenceText) {
    showMessage("正解テキストを入力してください。", "error");
    return;
  }
  document.getElementById("displayText").innerText = referenceText;
  document.getElementById("textLoaded").style.display = "block";
  showMessage("テキストを読み込みました", "success");
}

function showMessage(text, type) {
  const message = document.getElementById("message");
  message.textContent = text;
  message.className = type;
  setTimeout(() => message.textContent = "", 3000);
}

function isIOSChrome() {
  const userAgent = navigator.userAgent.toLowerCase();
  return /crios/.test(userAgent) || (/iphone|ipad/.test(userAgent) && /chrome/.test(userAgent));
}

function isIOSSafari() {
  const userAgent = navigator.userAgent.toLowerCase();
  return /iphone|ipad/.test(userAgent) && /safari/.test(userAgent) && !(/chrome/.test(userAgent));
}

function startRecording() {
  if (isIOSChrome()) {
    showMessage("iOS版Chromeでは録音機能が制限されています。Safariブラウザをご利用ください。", "error");
    return;
  }

  const constraints = { audio: true };

  navigator.mediaDevices.getUserMedia(constraints)
    .then(stream => {
      let options = {};
      const tryMimeTypes = ['audio/mp4', 'audio/aac', 'audio/webm;codecs=opus', 'audio/webm', ''];

      for (let mimeType of tryMimeTypes) {
        try {
          if (!mimeType || MediaRecorder.isTypeSupported(mimeType)) {
            options = mimeType ? { mimeType, audioBitsPerSecond: 128000 } : {};
            recorder = new MediaRecorder(stream, options);
            console.log('Using MIME type:', mimeType || 'browser default');
            break;
          }
        } catch (e) {
          console.warn('Failed to use MIME type:', mimeType, e);
        }
      }

      if (!recorder) recorder = new MediaRecorder(stream);

      chunks = [];
      recorder.ondataavailable = e => chunks.push(e.data);
      recorder.onstop = handleStop;
      recorder.start();

      document.getElementById("startBtn").disabled = true;
      document.getElementById("stopBtn").disabled = false;
      showMessage("録音中...", "success");
    })
    .catch(err => {
      showMessage("マイクへのアクセスに失敗しました。", "error");
      console.error(err);
    });
}

function stopRecording() {
  if (recorder && recorder.state === "recording") {
    recorder.stop();
    document.getElementById("startBtn").disabled = false;
    document.getElementById("stopBtn").disabled = true;
    document.getElementById("submitBtn").disabled = false;
    showMessage("録音を停止しました", "success");
  }
}

function handleStop() {
  if (chunks.length === 0) {
    showMessage("録音データが取得できませんでした。もう一度お試しください。", "error");
    return;
  }

  const recordedBlob = new Blob(chunks, { type: 'audio/webm' });
  const recordedAudio = document.getElementById("recordedAudio");
  recordedAudio.src = URL.createObjectURL(recordedBlob);
  recordedAudio.onerror = () => {
    showMessage("録音音声の再生に失敗しました。", "error");
    recordedAudio.src = '';
  };

  document.getElementById("submitBtn").disabled = false;
  document.recordedBlob = recordedBlob;
  showMessage("録音が完了しました", "success");
}

function submitRecording() {
  if (!referenceText || !document.recordedBlob) {
    showMessage("正解テキストと録音音声の両方が必要です。", "error");
    return;
  }

  const formData = new FormData();
  formData.append("audio", document.recordedBlob);
  formData.append("transcript", referenceText);

  document.getElementById("resultBox").innerHTML = '<div class="loading">評価中...</div>';

  fetch("/evaluate_read_aloud", {
    method: "POST",
    body: formData
  })
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        document.getElementById("resultBox").innerHTML = `<div class="error">❌ エラー: ${data.error}</div>`;
      } else {
        document.getElementById("resultBox").innerHTML = `
          <div class="result-box">
            <h3 class="success">✅ WER: ${data.wer}%</h3>
            <hr>
            <div class="diff-section">
              <h4>🔍 Diff:</h4>
              ${data.diff_html}
            </div>
            <hr>
            <div class="text-section">
              <h4>📜 Original Text:</h4>
              <div class="display-text">${referenceText}</div>
            </div>
            <hr>
            <div class="text-section">
              <h4>🗣️ Your Transcription:</h4>
              <div class="display-text">${data.transcribed}</div>
            </div>
          </div>
        `;
      }
    })
    .catch(err => {
      console.error("評価エラー:", err);
      document.getElementById("resultBox").innerHTML = '<div class="error">❌ 提出エラー</div>';
    });
}
