class CustomShadowing {
  constructor() {
    this.recorder = new AudioRecorder();
    this.currentMaterial = null; // 現在練習中の教材情報 (音声URL、スクリプト、IDなど)
    this.requestHeaders = new Headers(); // Replit ユーザーID用

    this.dom = { // 主要なDOM要素をまとめて管理
      initialChoiceSection: document.getElementById('initialChoiceSection'),
      usePreviousMaterialBtn: document.getElementById('usePreviousMaterialBtn'),
      uploadNewMaterialBtn: document.getElementById('uploadNewMaterialBtn'),
      previousMaterialInfo: document.getElementById('previousMaterialInfo'),
      prevMaterialFilename: document.getElementById('prevMaterialFilename'),
      prevMaterialScriptPreview: document.getElementById('prevMaterialScriptPreview'),
      uploadSection: document.getElementById('uploadSection'),
      practiceSection: document.getElementById('practiceSection'),
      practiceMaterialTitle: document.getElementById('practiceMaterialTitle'),
      audioFileInput: document.getElementById('audioFileInput'),
      uploadBtn: document.getElementById('uploadBtn'),
      originalAudio: document.getElementById('originalAudio'),
      transcriptionText: document.getElementById('transcriptionText'),
      toggleTranscriptBtn: document.getElementById('toggleTranscript'),
      startBtn: document.getElementById('startBtn'),
      stopBtn: document.getElementById('stopBtn'),
      submitBtn: document.getElementById('submitBtn'),
      recordedAudio: document.getElementById('recordedAudio'),
      resultBox: document.getElementById('resultBox'),
      progressSpinner: document.getElementById('progressSpinner'),
      spinnerText: document.querySelector('#progressSpinner .spinner-text'),
      userMessageArea: document.getElementById('userMessageArea'),
    };
    this.setupEventListeners();
    this.initializePage();
  }

  initializePage() {
    // ReplitユーザーIDをヘッダーにセット
    const replitUserId = document.body.dataset.replitUserId; // HTML側でセットされている前提
    if (replitUserId) {
        this.requestHeaders.set('X-Replit-User-Id', replitUserId);
    }

    // ★ダミーの前回教材情報を表示（実際のロード処理は後で）
    this.loadPreviousMaterialInfo(); // この関数内でダミー情報を表示するようにする
  }

  setupEventListeners() {
    this.dom.usePreviousMaterialBtn.addEventListener('click', () => this.handleUsePreviousMaterial());
    this.dom.uploadNewMaterialBtn.addEventListener('click', () => this.handleUploadNewMaterialChoice());
    this.dom.uploadBtn.addEventListener('click', () => this.handleUpload());
    this.dom.startBtn.addEventListener('click', () => this.startRecording());
    this.dom.stopBtn.addEventListener('click', () => this.stopRecording());
    this.dom.submitBtn.addEventListener('click', () => this.submitRecording());
    this.dom.toggleTranscriptBtn.addEventListener('click', () => this.toggleTranscript());
    this.dom.audioFileInput.addEventListener('change', () => { // ファイル選択時に即アップロードボタンを有効化する例
        if (this.dom.audioFileInput.files.length > 0) {
            this.dom.uploadBtn.disabled = false;
        } else {
            this.dom.uploadBtn.disabled = true;
        }
    });
  }

  // --- UI制御ロジック ---
  showSection(sectionElement) {
    this.dom.initialChoiceSection.style.display = 'none';
    this.dom.uploadSection.style.display = 'none';
    this.dom.practiceSection.style.display = 'none';
    if (sectionElement) {
      sectionElement.style.display = 'block';
    }
  }

  loadPreviousMaterialInfo() {
    // TODO: 実際のバックエンドAPIを呼び出して前回の教材情報を取得する
    // 以下はダミー表示のロジック
    const dummyPreviousMaterial = {
      // id: "dummy_material_123", // 将来的に使うかも
      filename: "my_last_practice_audio.mp3",
      script: "This is a dummy script from your previous practice session. Hello world, this is a test...",
      audio_url: "/static/audio/warm-up.mp3" // ダミーの音声URL
    };

    if (dummyPreviousMaterial && dummyPreviousMaterial.filename) { // ダミーでも情報があるか
      this.dom.prevMaterialFilename.textContent = dummyPreviousMaterial.filename;
      this.dom.prevMaterialScriptPreview.textContent = dummyPreviousMaterial.script.substring(0, 100); // 冒頭100文字
      this.dom.previousMaterialInfo.style.display = 'block';
      this.dom.usePreviousMaterialBtn.disabled = false;
    } else {
      this.dom.previousMaterialInfo.style.display = 'none';
      this.dom.usePreviousMaterialBtn.disabled = true; // 前回の教材がなければ無効化
      this.showUserAlert('前回の練習データが見つかりませんでした。新しい教材をアップロードしてください。', 'info');
    }
  }

  handleUsePreviousMaterial() {
    this.showUserAlert('前回の教材を読み込みます... (現在はダミー表示)', 'info');
    // TODO: 実際のバックエンドから前回の教材データを取得し、this.currentMaterial にセットする
    // ダミーデータをセット
    this.currentMaterial = {
      id: "prev_dummy_id_123", // バックエンドから取得する教材ID
      audio_url: this.dom.originalAudio.src || "/static/audio/warm-up.mp3", // ダミーのURLか、infoから取得したURL
      transcription: this.dom.prevMaterialScriptPreview.textContent + " (これはダミーの全文です)",
      name: this.dom.prevMaterialFilename.textContent || "前回の教材"
    };

    this.dom.practiceMaterialTitle.textContent = `練習中: ${this.currentMaterial.name}`;
    this.dom.originalAudio.src = this.currentMaterial.audio_url;
    this.dom.originalAudio.load();
    this.dom.transcriptionText.textContent = this.currentMaterial.transcription;
    this.dom.transcriptionText.style.display = 'none'; // 初期は非表示
    this.dom.toggleTranscriptBtn.textContent = 'スクリプト表示';


    this.showSection(this.dom.practiceSection);
    this.resetPracticeUI(); // 録音ボタンなどを初期状態に
  }

  handleUploadNewMaterialChoice() {
    this.showSection(this.dom.uploadSection);
    this.dom.audioFileInput.value = ''; // ファイル選択をリセット
    this.dom.uploadBtn.disabled = true; // アップロードボタンを初期は無効に
    this.currentMaterial = null; // 新規アップロードなので現在の教材情報をクリア
  }

  resetPracticeUI() {
    this.dom.startBtn.disabled = false;
    this.dom.stopBtn.disabled = true;
    this.dom.submitBtn.disabled = true;
    this.dom.recordedAudio.src = '';
    this.dom.resultBox.innerHTML = '';
  }

  // --- スピナーとメッセージ表示 ---
  showSpinner(message = '処理中...', showProgressText = false) {
    this.dom.spinnerText.textContent = message;
    const progressSpanClass = 'progress-percentage';
    let progressSpan = this.dom.spinnerText.querySelector(`.${progressSpanClass}`);

    if (showProgressText) {
      if (!progressSpan) {
        progressSpan = document.createElement('span');
        progressSpan.className = progressSpanClass;
        this.dom.spinnerText.appendChild(document.createElement('br'));
        this.dom.spinnerText.appendChild(progressSpan);
      }
      progressSpan.textContent = '0%';
    } else {
      if (progressSpan) {
        if (progressSpan.previousSibling && progressSpan.previousSibling.nodeName === 'BR') {
            this.dom.spinnerText.removeChild(progressSpan.previousSibling);
        }
        this.dom.spinnerText.removeChild(progressSpan);
      }
    }
    this.dom.progressSpinner.style.display = 'flex';
  }

  updateSpinnerMessage(newMessage) {
    if (this.dom.progressSpinner.style.display === 'none') return;
    const progressSpan = this.dom.spinnerText.querySelector('.progress-percentage');
    if (progressSpan) {
        this.dom.spinnerText.firstChild.textContent = newMessage;
    } else {
        this.dom.spinnerText.textContent = newMessage;
    }
  }

  updateSpinnerProgress(percent) {
    if (this.dom.progressSpinner.style.display === 'none') return;
    const progressSpan = this.dom.spinnerText.querySelector('.progress-percentage');
    if (progressSpan) {
      progressSpan.textContent = `${Math.round(percent)}%`;
    }
  }

  hideSpinner() {
    this.dom.progressSpinner.style.display = 'none';
  }

  showUserAlert(message, type = 'info') {
    this.dom.userMessageArea.textContent = message;
    this.dom.userMessageArea.style.display = 'block';
    this.dom.userMessageArea.className = `alert alert-${type}`; // style.cssで定義するクラス

    // typeに応じて背景色などを変更
    switch(type) {
        case 'success':
            this.dom.userMessageArea.style.backgroundColor = 'var(--primary, #4CAF50)';
            break;
        case 'error':
            this.dom.userMessageArea.style.backgroundColor = '#d32f2f';
            break;
        case 'info':
        default:
            this.dom.userMessageArea.style.backgroundColor = '#2196F3';
            break;
    }

    // 数秒後に自動で消す場合
    setTimeout(() => {
      this.dom.userMessageArea.style.display = 'none';
    }, 5000); // 5秒後に非表示
  }


  // --- アップロード、録音、評価処理 (バックエンド連携部分はコメントアウトまたはダミー) ---
  async handleUpload() {
    const file = this.dom.audioFileInput.files[0];
    if (!file) {
      this.showUserAlert('ファイルを選択してください。', 'error');
      return;
    }
    // ファイル形式・サイズチェック (前回同様)
    const allowedTypes = ['audio/mpeg', 'audio/mp3', 'audio/mp4', 'audio/wav', 'audio/x-m4a', 'audio/webm', 'audio/mpga', 'audio/mpeg']; // 許可するMIMEタイプを増やす
    if (!allowedTypes.includes(file.type)) {
        this.showUserAlert(`サポートされていないファイル形式です: ${file.type}。MP3, M4A, WAV, WebM等でお願いします。`, 'error');
        return;
    }
    const MAX_UPLOAD_SIZE_MB = 25;
    if (file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024) {
        this.showUserAlert(`ファイルサイズが大きすぎます。${MAX_UPLOAD_SIZE_MB}MB以下のファイルを選択してください。`, 'error');
        return;
    }

    const formData = new FormData();
    formData.append('audio', file);

    this.showSpinner('アップロード中... ', true);

    // XHRオブジェクトの作成 (進捗表示のため)
    const xhr = new XMLHttpRequest();
    xhr.responseType = 'json'; // サーバーからの応答は JSON 形式

    // アップロード進捗
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percentComplete = (event.loaded / event.total) * 100;
        this.updateSpinnerProgress(percentComplete);
        if (percentComplete >= 100) {
            this.updateSpinnerMessage('サーバーで文字起こし中...');
            // 進捗表示が不要ならテキストからパーセンテージ部分を消す (前回同様)
            const spinnerTextElement = this.dom.spinnerText; // this.domから取得
            const progressSpan = spinnerTextElement.querySelector('.progress-percentage');
            if (progressSpan) {
                if (progressSpan.previousSibling && progressSpan.previousSibling.nodeName === 'BR') {
                    spinnerTextElement.removeChild(progressSpan.previousSibling);
                }
                spinnerTextElement.removeChild(progressSpan);
            }
        }
      }
    };

    try {
      // Promiseでラップして非同期処理を待つ
      const data = await new Promise((resolve, reject) => {
        xhr.open('POST', '/upload_custom_audio', true);
        // 認証ヘッダー (this.requestHeaders は initializePage でセットされている想定)
        if (this.requestHeaders.has('X-Replit-User-Id')) {
            xhr.setRequestHeader('X-Replit-User-Id', this.requestHeaders.get('X-Replit-User-Id'));
        }

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(xhr.response);
          } else {
            let errorMsg = `アップロードまたは処理に失敗しました (HTTP ${xhr.status})。`;
            if (xhr.response && xhr.response.error) {
              errorMsg = xhr.response.error;
            } else if (xhr.statusText) {
              errorMsg += ` ${xhr.statusText}`;
            }
            reject(new Error(errorMsg));
          }
        };
        xhr.onerror = () => {
          reject(new Error('ネットワークエラーが発生しました。接続を確認してください。'));
        };
        xhr.send(formData);
      });

      this.hideSpinner();

      if (data.error) { // サーバーがエラーを返した場合のハンドリング
        throw new Error(data.error);
      }

      this.currentMaterial = data; // サーバーからのレスポンスを保存

      this.dom.practiceMaterialTitle.textContent = `練習中: ${file.name}`; // ファイル名を表示
      this.dom.originalAudio.src = this.currentMaterial.audio_url;
      this.dom.originalAudio.load();
      this.dom.transcriptionText.textContent = this.currentMaterial.transcription; // ★実際の文字起こし結果を表示
      this.dom.transcriptionText.style.display = 'none';
      this.dom.toggleTranscriptBtn.textContent = 'スクリプト表示';
      // this.dom.practiceSection.dataset.materialId = this.currentMaterial.material_id; // datasetは文字列なので注意

      this.showSection(this.dom.practiceSection);
      this.resetPracticeUI();
      this.showUserAlert('アップロードと文字起こしが完了しました！練習を開始できます。', 'success');

    } catch (error) {
      console.error('Upload error:', error);
      this.hideSpinner();
      this.showUserAlert(error.message || 'アップロード処理中に不明なエラーが発生しました。', 'error');
      // エラー発生時は練習セクションに進まないように、必要ならここで return
    }
  }

  
  async startRecording() {
    if (!this.currentMaterial || !this.dom.originalAudio.src || this.dom.originalAudio.src === window.location.href) { // srcが空か、ベースURLのままの場合
        this.showUserAlert('練習用の音声が読み込まれていません。教材を選択またはアップロードしてください。', 'error');
        return;
    }
    try {
      this.showUserAlert('録音準備中...', 'info');
      await this.recorder.startRecording(); // AudioRecorderのstartRecordingを呼び出す
      this.showUserAlert('録音開始！', 'success');

      // ウォームアップ音声を再生 (warm-up.mp3 が static/audio にある前提)
      const warmupAudio = new Audio('/static/audio/warm-up.mp3'); // warm-up.mp3 のパス
      warmupAudio.play();

      warmupAudio.onended = () => {
        this.dom.originalAudio.currentTime = 0;
        this.dom.originalAudio.play();
      };

      this.dom.startBtn.disabled = true;
      this.dom.stopBtn.disabled = false;
      this.dom.submitBtn.disabled = true;
    } catch (err) {
      console.error('Recording error:', err);
      this.showUserAlert('録音の開始に失敗しました。マイクの接続とアクセス許可を確認してください。', 'error');
      this.dom.startBtn.disabled = false; // 開始ボタンを再度有効化
    }
  }

  stopRecording() {
    if (this.recorder) { // recorder が初期化されているか確認
        this.recorder.stop();
    }
    if (this.dom.originalAudio) { // originalAudio が存在するか確認
        this.dom.originalAudio.pause();
    }

    this.dom.startBtn.disabled = false;
    this.dom.stopBtn.disabled = true;
    this.dom.submitBtn.disabled = false; // 停止したら提出可能に

    const recordedBlob = this.recorder.getBlob();
    if (recordedBlob && recordedBlob.size > 0) {
      this.dom.recordedAudio.src = URL.createObjectURL(recordedBlob);
    } else {
      this.showUserAlert('録音データが空のようです。もう一度お試しください。', 'warning');
      this.dom.submitBtn.disabled = true; // データがない場合は提出不可
    }
  }

  toggleTranscript() {
    const isHidden = this.dom.transcriptionText.style.display === 'none';
    this.dom.transcriptionText.style.display = isHidden ? 'block' : 'none';
    this.dom.toggleTranscriptBtn.textContent = isHidden ? 'スクリプト非表示' : 'スクリプト表示';
  }


  async submitRecording() {
    const recordedBlob = this.recorder.getBlob();
    if (!recordedBlob || recordedBlob.size === 0) {
      this.showUserAlert('評価する録音データがありません。', 'error');
      return;
    }
    // currentMaterial が設定されているか、または material_id が取得できるかを確認
    // (前回 material_id をセッションから取得する実装だったので、そちらに合わせるか、
    //  currentMaterial.id を使うなら、handleUpload や handleUsePreviousMaterial で
    //  currentMaterial.id が正しくセットされるようにする)
    // ここでは、前回の方針（セッションからmaterial_idを取得）に沿った形でコメントを残しつつ、
    // currentMaterial.id があればそれを使う形も想定できるようにしておきます。

    // const materialId = this.dom.practiceSection.dataset.materialId; // もしdatasetに保存していれば
    // if (!materialId && (!this.currentMaterial || !this.currentMaterial.id)) {
    //   this.showUserAlert('現在の教材情報が見つかりません。教材の選択からやり直してください。', 'error');
    //   return;
    // }

    const formData = new FormData();
    formData.append('recorded_audio', recordedBlob, `custom_recording_${Date.now()}.webm`);
    // formData.append('material_id', materialId || this.currentMaterial.id); // material_idを送信する場合

    this.showSpinner('評価中...');

    try {
      const response = await fetch('/evaluate_custom_shadowing', {
        method: 'POST',
        headers: this.requestHeaders, // 認証ヘッダー (X-Replit-User-Idなど)
        body: formData
      });

      const data = await response.json();
      this.hideSpinner();

      if (!response.ok) { // HTTPステータスが2xxでない場合
        throw new Error(data.error || `評価サーバーエラー (HTTP ${response.status})`);
      }
      // data.error があっても response.ok な場合もあるので、data.errorもチェック
      if (data.error) {
          throw new Error(data.error);
      }

      this.displayEvaluationResult(data); // 結果表示関数を呼び出す
      this.showUserAlert('評価が完了しました。', 'success');

    } catch (error) {
      console.error('Evaluation error:', error);
      this.hideSpinner();
      this.showUserAlert(error.message || '評価処理中に不明なエラーが発生しました。', 'error');
      this.dom.resultBox.innerHTML = `<p class="error-message">評価エラー: ${error.message || '不明なエラー'}</p>`; // エラーメッセージ用のクラスを付与
    }
  }
  
  
  displayEvaluationResult(data) {
      this.dom.resultBox.innerHTML = `
        <h3>✅ WER: ${data.wer}%</h3>
        <hr>
        <div class="diff-section">
          <h4>🔍 Diff (お手本 vs あなたの発話):</h4>
          <div class="diff-result">${data.diff_html}</div>
        </div>
        <hr>
        <div class="text-section">
            <h4>📜 お手本の文字起こし:</h4>
            <div class="display-text" style="white-space: pre-wrap; max-height: 150px; overflow-y: auto;">${data.original_transcription}</div>
        </div>
        <hr>
        <div class="text-section">
            <h4>🗣️ あなたの文字起こし (ウォームアップ除去後):</h4>
            <div class="display-text" style="white-space: pre-wrap; max-height: 150px; overflow-y: auto;">${data.user_transcription}</div>
        </div>
      `;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // HTMLのbodyタグにReplitのユーザーIDをdata属性として埋め込むことを想定
  // Flaskテンプレート側: <body data-replit-user-id="{{ user_id }}">
  // JavaScript側でそれを読み取る
  const bodyData = document.body.dataset;
  if (bodyData.replitUserId) {
    // CustomShadowingクラスのインスタンス作成時に渡すか、
    // クラス内でグローバルな window オブジェクト経由でアクセスするなどの方法がある
  }
  new CustomShadowing();
});