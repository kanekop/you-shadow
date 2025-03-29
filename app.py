from flask import Flask, render_template, request, redirect, url_for, jsonify
from transcribe_utils import transcribe_audio
import os
from werkzeug.utils import secure_filename
from wer_utils import wer
from diff_viewer import diff_html
import json
from datetime import datetime
import shutil  # ファイルコピー用のモジュールを追加
from youtube_utils import get_transcript
from youtube_utils import youtube_bp
from diff_viewer import diff_html

# === Flask設定 ===
app = Flask(__name__)
app.register_blueprint(youtube_bp)
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# === ルート画面 ===
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shorts')
def shorts_ui():
    return render_template('shorts.html')

@app.route('/youtube')
def youtube_ui():
    return render_template('youtube.html')
    
@app.route('/evaluate_youtube', methods=['POST'])
def evaluate_youtube():
    from openai import OpenAI
    import tempfile
    from wer_utils import calculate_wer

    audio_file = request.files['audio']
    transcript_text = request.form['transcript']

    # Whisper 1.0 形式のクライアントを使う
    client = OpenAI()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        audio_file.save(tmp.name)
        with open(tmp.name, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        transcribed = response.text

    wer = calculate_wer(transcript_text, transcribed)

    diff_result = diff_html(transcript_text, transcribed)

    return jsonify({
        "transcribed": transcribed,
        "wer": round(wer * 100, 2),
        "diff_html": diff_result
    })



# === 音声ファイルと入力の受信 ===
@app.route('/submit', methods=['POST'])
def submit():
    user_id = request.form['user_id']
    script = request.form['script']
    file = request.files['audio']

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # 🔄 static にコピー（上書き）
    static_path = os.path.join("static", "recorded.webm")
    shutil.copy(filepath, static_path)  # ← 変更ポイント！
    
    # 🔍 Whisperで文字起こし
    transcript = transcribe_audio(filepath)

    # 📊 WER計算
    wer_score, subs, dels, ins, word_count = wer(script, transcript)

    # HTML差分を生成
    diff_result = diff_html(script, transcript)

    # 📁 ログ情報
    log_entry = {
        "user_id": user_id,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "script": script,
        "transcript": transcript,
        "wer": round(wer_score, 1),
        "substitutions": subs,
        "deletions": dels,
        "insertions": ins,
        "words": word_count,
        "note": ""
    }

    log_path = "log.json"
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
    else:
        logs = []

    logs.append(log_entry)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

    
    # 結果を表示
    # 結果ページに必要な情報を渡す
    return render_template(
        "result.html",
        user_id=user_id,
        filename=filename,
        script=script,
        transcript=transcript,
        wer_score=wer_score,
        subs=subs,
        dels=dels,
        ins=ins,
        word_count=word_count,
        diff_result=diff_result
    )
    


# === アプリ実行（Replitでは不要、ローカル用） ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Heroku用ポート
    app.run(host="0.0.0.0", port=port, debug=True)