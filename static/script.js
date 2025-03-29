let mediaRecorder;
let audioChunks = [];
let ytPlayer;

function startRecording() {
  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.start();

      document.getElementById("startBoth").disabled = true;
      document.getElementById("stopBtn").disabled = false;

      audioChunks = [];
      mediaRecorder.addEventListener("dataavailable", event => {
        audioChunks.push(event.data);
      });

      mediaRecorder.addEventListener("stop", () => {
        handleRecordingStop(audioChunks);
      });

      // ✅ YouTubeプレイヤーが使える場合はそちらを再生、そうでなければ音声教材を再生
      if (ytPlayer && typeof ytPlayer.playVideo === "function") {
        ytPlayer.seekTo(0);
        ytPlayer.playVideo();
      } else {
        const audio = document.getElementById("audioPlayer");
        audio.currentTime = 0;
        audio.play()
          .catch(error => {
            alert("音声の再生に失敗しました。");
            console.error("Audio play failed:", error);
          });
      }

    })
    .catch(error => {
      alert("マイクへのアクセスが許可されていません。");
      console.error("Mic error:", error);
    });
}



function handleRecordingStop(chunks) {
  const audioBlob = new Blob(chunks, { type: "audio/webm" });
  const file = new File([audioBlob], "recorded.webm", {
    type: "audio/webm"
  });
  const container = new DataTransfer();
  container.items.add(file);
  document.getElementById("audioBlobInput").files = container.files;

  // 🎧 自分の録音を再生できるようにする
  const recordedAudio = document.getElementById("recordedAudio");
  recordedAudio.src = URL.createObjectURL(audioBlob);
  recordedAudio.load();

  document.getElementById("startBoth").disabled = false;
  document.getElementById("stopBtn").disabled = true;
}


// 🔴 ボタンイベントを追加（この部分がなければ index.html 側ではなくJS内で処理）
document.getElementById("startBoth").addEventListener("click", startRecording);
document.getElementById("stopBtn").addEventListener("click", () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
});

async function fetchTranscriptFromURL() {
  const url = document.getElementById('youtube-url').value;

  const response = await fetch('/get_transcript', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ url: url })
  });

  const data = await response.json();
  if (data.transcript) {
    document.getElementById('script').value = data.transcript;
  } else {
    alert('字幕の取得に失敗しました: ' + (data.error || 'Unknown error'));
  }
}

function setYouTubeVideo() {
  const url = document.getElementById('youtube-url').value;
  const match = url.match(/(?:v=|youtu.be\/)([a-zA-Z0-9_-]{11})/);
  if (!match) {
    alert("YouTube URLが無効です");
    return;
  }
  const videoId = match[1];

  // すでにある iframe を削除（ある場合）
  const container = document.getElementById('youtube-container');
  container.innerHTML = '<div id="youtube-player"></div>'; // プレースホルダを再設定

  // YouTubeプレイヤーを初期化（ここで ytPlayer を作る）
  ytPlayer = new YT.Player('youtube-player', {
    height: '315',
    width: '560',
    videoId: videoId,
    playerVars: {
      'autoplay': 0,
      'controls': 1,
      'rel': 0,
      'modestbranding': 1
    },
    events: {
      'onReady': function (event) {
        console.log("✅ プレイヤー準備完了（setYouTubeVideoから）");
      }
    }
  });
}


function onYouTubeIframeAPIReady() {
  ytPlayer = new YT.Player('youtube-player');
}

window.onYouTubeIframeAPIReady = function () {
  console.log("✅ YouTubeプレイヤーAPIの初期化完了");
  ytPlayer = new YT.Player('youtube-player');
};


function testYouTubePlay() {
  if (ytPlayer && typeof ytPlayer.playVideo === "function") {
    ytPlayer.seekTo(0); // 0秒から再生
    ytPlayer.playVideo();
    console.log("✅ YouTube 再生コマンドを実行しました");
  } else {
    console.error("❌ ytPlayer が未初期化です");
    alert("YouTube プレイヤーがまだ準備できていません");
  }
}
