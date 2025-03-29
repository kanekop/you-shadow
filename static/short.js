let ytShortPlayer;
let shortRecorder;
let shortChunks = [];

function fetchTranscriptAndEmbedShort() {
  const url = document.getElementById('youtube-url').value;
  const match = url.match(/(?:shorts\/|v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
  if (!match) {
    alert("無効なYouTube ShortsのURLです。");
    return;
  }
  const videoId = match[1];

  // 字幕取得
  fetch('/get_transcript', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: url })
  })
    .then(res => res.json())
    .then(data => {
      if (data.transcript) {
        document.getElementById('script').value = data.transcript;
      } else {
        alert("字幕が取得できませんでした。");
      }
    });

  // プレイヤー再初期化
  const container = document.getElementById('youtube-container');
  container.innerHTML = '<div id="youtube-player"></div>';

  ytShortPlayer = new YT.Player('youtube-player', {
    height: '360',
    width: '202', // ショート動画風に縦長
    videoId: videoId,
    playerVars: {
      autoplay: 0,
      controls: 1,
      rel: 0,
      modestbranding: 1
    },
    events: {
      onReady: () => console.log("✅ Shortsプレイヤー準備OK")
    }
  });
}

window.onYouTubeIframeAPIReady = function () {
  console.log("✅ YouTube IFrame API ロード済");
};

// 再生 & 録音開始
function startShortRecording() {
  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      shortRecorder = new MediaRecorder(stream);
      shortRecorder.start();
      shortChunks = [];

      document.getElementById('startShort').disabled = true;
      document.getElementById('stopShort').disabled = false;

      shortRecorder.ondataavailable = e => shortChunks.push(e.data);
      shortRecorder.onstop = () => handleShortStop();

      if (ytShortPlayer && ytShortPlayer.playVideo) {
        ytShortPlayer.seekTo(0);
        ytShortPlayer.playVideo();
      }
    })
    .catch(err => {
      alert("マイクへのアクセスができませんでした");
      console.error(err);
    });
}

function handleShortStop() {
  const audioBlob = new Blob(shortChunks, { type: 'audio/webm' });
  document.getElementById('recordedAudio').src = URL.createObjectURL(audioBlob);
  document.getElementById('audioBlobInput').files = new DataTransfer().files;

  document.getElementById('startShort').disabled = false;
  document.getElementById('stopShort').disabled = true;
}

document.getElementById('startShort').addEventListener('click', startShortRecording);
document.getElementById('stopShort').addEventListener('click', () => {
  if (shortRecorder && shortRecorder.state === 'recording') {
    shortRecorder.stop();
  }
});
