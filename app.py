from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
from flask_cors import CORS
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
from youtube_utils import check_captions
from diff_viewer import diff_html
from dotenv import load_dotenv

load_dotenv()  # .env ファイルの読み込み

api_key = os.environ.get("YOUTUBE_API_KEY")
print(f"APIキー：{api_key}")  # 動作確認用（あとで削除してOK）



# === Flask設定 ===
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.register_blueprint(youtube_bp)
CORS(app) # Enable CORS
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# === ルート画面 ===
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shorts')
def shorts_ui():
    return render_template('shorts.html')

from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
# ...他のimport省略

@app.route("/read-aloud", methods=["GET", "POST"])
def read_aloud():
    if request.method == "GET":
        return render_template("read_aloud.html")

    # === 正解テキストの取得 ===
    reference_text = request.form.get("reference_text", "").strip()
    reference_file = request.files.get("reference_file")
    if reference_file and reference_file.filename.endswith(".txt"):
        reference_text = reference_file.read().decode("utf-8").strip()

    # === 音声ファイルの取得 ===
    audio_file = request.files["audio_file"]
    audio_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(audio_file.filename))
    audio_file.save(audio_path)

    # === 音声の文字起こし ===
    recognized_text = transcribe_audio(audio_path)

    # === 精度チェック（WER & 差分） ===
    wer_score = wer(reference_text, recognized_text)
    diff_result = diff_html(reference_text, recognized_text)

    # === 結果ページに渡す ===
    return render_template("result.html",
                           ref_text=reference_text,
                           hyp_text=recognized_text,
                           wer_score=wer_score,
                           diff_result=diff_result)


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



@app.route("/check_subtitles", methods=["GET"])
def check_subtitles():
    video_id = request.args.get("video_id")
    if not video_id:
        return jsonify({"error": "Missing video_id"}), 400

    result = check_captions(video_id)
    if result is None:
        return jsonify({"error": "Failed to check captions"}), 500

    return jsonify({
        "video_id": video_id,
        "has_subtitles": result
    })

@app.route('/evaluate_read_aloud', methods=['POST'])
def evaluate_read_aloud():
    from openai import OpenAI
    import tempfile
    from wer_utils import calculate_wer

    audio_file = request.files['audio']
    transcript_text = request.form['transcript']

    client = OpenAI()

    # 一時ファイルに保存
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        audio_file.save(tmp.name)
        with open(tmp.name, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        transcribed = response.text

    # WER計算
    wer_score = calculate_wer(transcript_text, transcribed)

    # 差分をHTMLで生成
    diff_result = diff_html(transcript_text, transcribed)

    return jsonify({
        "transcribed": transcribed,
        "wer": round(wer_score * 100, 2),
        "diff_html": diff_result
    })

@app.route('/shadowing')
def shadowing_ui():
    return render_template('shadowing.html')


@app.route('/evaluate_shadowing', methods=['POST'])
def evaluate_shadowing():
    from openai import OpenAI
    import tempfile
    from wer_utils import calculate_wer

    original_audio = request.files['original_audio']
    recorded_audio = request.files['recorded_audio']

    client = OpenAI()

    # === 元音声の文字起こし ===
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_original:
        original_audio.save(tmp_original.name)
        with open(tmp_original.name, "rb") as f:
            original_result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        original_transcribed = original_result.text

    # === ユーザー音声の文字起こし ===
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_user:
        recorded_audio.save(tmp_user.name)
        with open(tmp_user.name, "rb") as f:
            user_result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        user_transcribed = user_result.text

    # === 精度評価
    wer_score = calculate_wer(original_transcribed, user_transcribed)
    diff_result = diff_html(original_transcribed, user_transcribed)

    return jsonify({
        "original_transcribed": original_transcribed,
        "user_transcribed": user_transcribed,
        "wer": round(wer_score * 100, 2),
        "diff_html": diff_result
    })




# === アプリ実行（Replitでは不要、ローカル用） ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 443))  # Heroku用ポート, changed to 443 for HTTPS
    app.run(host="0.0.0.0", port=port, debug=True)