let ytPlayer;
let recorder;
let chunks = [];
let lastTranscript = "";

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById('startBtn').addEventListener('click', startRecording);
  document.getElementById('stopBtn').addEventListener('click', () => {
    if (recorder && recorder.state === 'recording') {
      recorder.stop();
    }
  });

  document.getElementById('submitBtn').addEventListener('click', () => {
    if (!document.recordedBlob || !lastTranscript) {
      alert("録音か字幕が不足しています。");
      return;
    }

    const formData = new FormData();
    formData.append('audio', document.recordedBlob);
    formData.append('transcript', lastTranscript);

    fetch('/api/evaluate_youtube', {
      method: 'POST',
      body: formData
    })
      .then(res => res.json())
      .then(data => {
        if (data.error) {
          document.getElementById('resultBox').innerText = "❌ エラー: " + data.error;
        } else {
          document.getElementById('resultBox').innerHTML = `
            ✅ WER: ${data.wer}%<br>
            <hr>
            🔍 Diff:<br>${data.diff_html}<br>
            <hr>
            📜 Original Transcript:<br>${lastTranscript}<br>
            <hr>
            🗣️ Your Transcription:<br>${data.transcribed}
          `;
        }
      })
      .catch(err => {
        console.error("評価エラー:", err);
        document.getElementById('resultBox').innerText = "❌ 提出エラー";
      });
  });
});

function embedYouTubeAndStart() {
  const url = document.getElementById('youtube-url').value;
  const match = url.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
  if (!match) {
    alert("無効なYouTube URLです。");
    return;
  }
  const videoId = match[1];

  // 字幕を取得して保存（画面には出さない）
  fetch('/get_transcript', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: url })
  })
    .then(res => res.json())
    .then(data => {
      if (data.transcript) {
        lastTranscript = data.transcript;
        console.log("📜 字幕:", data.transcript);
      } else {
        alert("字幕が取得できませんでした。");
      }
    });

  // YouTube プレイヤー初期化
  const container = document.getElementById('youtube-container');
  container.innerHTML = '<div id="youtube-player"></div>';

  ytPlayer = new YT.Player('youtube-player', {
    height: '360',
    width: '560',
    videoId: videoId,
    playerVars: {
      autoplay: 0,
      controls: 1,
      rel: 0,
      modestbranding: 1
    },
    events: {
      onReady: () => console.log("✅ YouTubeプレイヤー準備完了")
    }
  });
}

window.onYouTubeIframeAPIReady = function () {
  console.log("✅ YouTube IFrame API ロード済");
};

function startRecording() {
  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      recorder = new MediaRecorder(stream);
      chunks = [];

      recorder.ondataavailable = e => chunks.push(e.data);
      recorder.onstop = () => handleStop();

      recorder.start();

      document.getElementById('startBtn').disabled = true;
      document.getElementById('stopBtn').disabled = false;

      if (ytPlayer && ytPlayer.playVideo) {
        ytPlayer.seekTo(0);
        ytPlayer.playVideo();
      }
    })
    .catch(err => {
      alert("マイクへのアクセスができませんでした。");
      console.error(err);
    });
}

function handleStop() {
  const audioBlob = new Blob(chunks, { type: 'audio/webm' });
  document.getElementById('recordedAudio').src = URL.createObjectURL(audioBlob);
  document.getElementById('startBtn').disabled = false;
  document.getElementById('stopBtn').disabled = true;
  document.getElementById('submitBtn').disabled = false;

  // 評価用に保持しておく
  document.recordedBlob = audioBlob;
}
