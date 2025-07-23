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
      copyTranscriptBtn: document.getElementById('copyTranscriptBtn'),
      startBtn: document.getElementById('startBtn'),
      stopBtn: document.getElementById('stopBtn'),
      submitBtn: document.getElementById('submitBtn'),
      recordedAudio: document.getElementById('recordedAudio'),
      resultBox: document.getElementById('resultBox'),
      progressSpinner: document.getElementById('progressSpinner'),
      spinnerText: document.querySelector('#progressSpinner .spinner-text'),
      userMessageArea: document.getElementById('userMessageArea'),
      prevMaterialIdInput: document.getElementById('prevMaterialId'),
      prevMaterialAudioUrlInput: document.getElementById('prevMaterialAudioUrl'),
      prevMaterialScriptFullTextarea: document.getElementById('prevMaterialScriptFull')
    };
    this.setupEventListeners();
    this.initializePage();
  }

  initializePage() {
    // body タグから Replit ユーザーIDを取得してヘッダーにセット
    const replitUserId = document.body.dataset.replitUserId;
    if (replitUserId) {
        this.requestHeaders.set('X-Replit-User-Id', replitUserId);
        console.log("User ID set for API requests:", replitUserId);
    } else {
        console.warn("Replit User ID not found in body data attribute.");
    }

    // ★ 隠しフィールドから前回の教材情報があるか確認し、ボタンを有効化
    if (this.dom.prevMaterialIdInput && this.dom.prevMaterialIdInput.value) {
      this.dom.usePreviousMaterialBtn.disabled = false;
      console.log("Previous material info found.");
    } else {
      this.dom.usePreviousMaterialBtn.disabled = true;
      this.dom.previousMaterialInfo.style.display = 'none'; // 情報がなければ表示エリアも隠す
      console.log("No previous material info found.");
    }
  }

  setupEventListeners() {
    this.dom.usePreviousMaterialBtn.addEventListener('click', () => this.handleUsePreviousMaterial());
    this.dom.uploadNewMaterialBtn.addEventListener('click', () => this.handleUploadNewMaterialChoice());
    this.dom.uploadBtn.addEventListener('click', () => this.handleUpload());
    this.dom.startBtn.addEventListener('click', () => this.startRecording());
    this.dom.stopBtn.addEventListener('click', () => this.stopRecording());
    this.dom.submitBtn.addEventListener('click', () => this.submitRecording());
    this.dom.toggleTranscriptBtn.addEventListener('click', () => this.toggleTranscript());
    this.dom.copyTranscriptBtn.addEventListener('click', () => this.copyTranscript());
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
    if (!this.dom.prevMaterialIdInput || !this.dom.prevMaterialIdInput.value) {
        this.showUserAlert('前回の教材データが見つかりません。', 'error');
        return;
    }

    this.showUserAlert('前回の教材を読み込んでいます...', 'info');

    // ★ 隠しフィールドから実際のデータを取得
    const materialId = this.dom.prevMaterialIdInput.value;
    const audioUrl = this.dom.prevMaterialAudioUrlInput.value;
    const script = this.dom.prevMaterialScriptFullTextarea.value;
    const filename = this.dom.prevMaterialFilename.textContent; // 表示されているファイル名

    // currentMaterial に取得した情報をセット
    this.currentMaterial = {
      id: materialId,
      audio_url: audioUrl,
      transcription: script,
      name: filename // ファイル名も保持
    };

    // UIを更新
    this.dom.practiceMaterialTitle.textContent = `練習中: ${this.currentMaterial.name}`;
    this.dom.originalAudio.src = this.currentMaterial.audio_url;
    this.dom.originalAudio.load(); // ★ 音声ファイルをロード
    this.dom.transcriptionText.textContent = this.currentMaterial.transcription;
    this.dom.transcriptionText.style.display = 'none';
    this.dom.toggleTranscriptBtn.textContent = 'スクリプト表示';
    // practiceSection の dataset に materialId をセット (評価時に使う場合)
    this.dom.practiceSection.dataset.materialId = this.currentMaterial.id;

    this.showSection(this.dom.practiceSection);
    this.resetPracticeUI();
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
    const MAX_UPLOAD_SIZE_MB = 100;
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
            if (xhr.response && typeof xhr.response === 'object' && xhr.response.error) {
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
    this.dom.copyTranscriptBtn.style.display = isHidden ? 'inline-block' : 'none';
  }

  copyTranscript() {
    if (!this.dom.transcriptionText.textContent) {
      this.showUserAlert('コピーするスクリプトがありません。', 'error');
      return;
    }

    navigator.clipboard.writeText(this.dom.transcriptionText.textContent)
      .then(() => {
        this.showUserAlert('スクリプトをクリップボードにコピーしました！', 'success');
      })
      .catch(err => {
        console.error('Copy failed:', err);
        // フォールバック: テキストエリアを作成してコピー
        const textArea = document.createElement('textarea');
        textArea.value = this.dom.transcriptionText.textContent;
        document.body.appendChild(textArea);
        textArea.select();
        try {
          document.execCommand('copy');
          this.showUserAlert('スクリプトをクリップボードにコピーしました！', 'success');
        } catch (fallbackErr) {
          this.showUserAlert('コピーに失敗しました。手動でコピーしてください。', 'error');
        }
        document.body.removeChild(textArea);
      });
  }



  // ★ submitRecording メソッドは前回のエラーハンドリング改善版を使用 (モック解除済み) ...
  //    ただし、material_id をどう渡すか確認が必要。
  //    現状の /api/evaluate_custom_shadowing はセッションから取得しているので、
  //    フロントから送る必要はないかもしれない。
  //    もし送る場合は formData に append する。
  async submitRecording() {
    const recordedBlob = this.recorder.getBlob();
    if (!recordedBlob || recordedBlob.size === 0) {
      this.showUserAlert('評価する録音データがありません。', 'error');
      return;
    }

    // セッションを使うので material_id は送らない想定
    // const materialId = this.dom.practiceSection.dataset.materialId;
    // if (!materialId) {
    //     this.showUserAlert('現在の教材情報が見つかりません。', 'error');
    //     return;
    // }

    const formData = new FormData();
    formData.append('recorded_audio', recordedBlob, `custom_recording_${Date.now()}.webm`);
    // formData.append('material_id', materialId); // 送る場合は追加

    this.showSpinner('評価中...');

    try {
      const response = await fetch('/api/evaluate_custom_shadowing', {
        method: 'POST',
        headers: this.requestHeaders, // 認証ヘッダー
        body: formData
      });
      // ... (以降のレスポンス処理は変更なし) ...
      const data = await response.json();
      this.hideSpinner();
      // ... (エラーチェック、結果表示) ...
      if (!response.ok) {
          throw new Error(data.error || `評価サーバーエラー (HTTP ${response.status})`);
      }
      if (data.error) {
          throw new Error(data.error);
      }
      this.displayEvaluationResult(data);
      this.showUserAlert('評価が完了しました。', 'success');

    } catch (error) {
      // ... (エラー処理は変更なし) ...
      console.error('Evaluation error:', error);
      this.hideSpinner();
      this.showUserAlert(error.message || '評価処理中に不明なエラーが発生しました。', 'error');
      this.dom.resultBox.innerHTML = `<p class="error-message">評価エラー: ${error.message || '不明なエラー'}</p>`;
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

  validateFileSize(file) {
    const maxSize = 100 * 1024 * 1024; // 100MB
    if (file.size > maxSize) {
      this.showUserAlert('ファイルサイズが大きすぎます。100MB以下のファイルを選択してください。', 'error');
      return false;
    }
    return true;
  }
} // クラス定義の終わり

document.addEventListener('DOMContentLoaded', () => {
  // ★ bodyタグの data-* 属性からユーザーIDを取得
  //    このコードは CustomShadowing クラスの外、またはインスタンス化の直前が良い
  // new CustomShadowing(); // ★ initializePage 内でID取得するように変更済み
  new CustomShadowing();
});