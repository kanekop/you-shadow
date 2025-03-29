from wer_utils import wer
from diff_viewer import color_diff
import json
from datetime import datetime
import os

# --- 入力：ユーザーIDとメモ（note）を受け取る ---
user_id = input("User IDを入力してください（例: kaneko）：")

# 正解スクリプト（教材）
correct_script = "This is the test recording."

# Whisperの出力（ここは実際のTranscriptに書き換えてください）
user_transcript = "this is the testing recording"

# WER計算
wer_score, S, D, I, N = wer(correct_script, user_transcript)

# 評価結果の表示
print("=== WER Evaluation Result ===")
print(f"Correct Script     : {correct_script}")
print(f"Your Transcript    : {user_transcript}")
print(f"WER Score          : {round(wer_score, 2)}%")
print(f"Substitutions (S)  : {S}")
print(f"Deletions (D)      : {D}")
print(f"Insertions (I)     : {I}")
print(f"Total Words (N)    : {N}")

# --- コメント欄の入力（自由記述） ---
note = input("コメントがあれば入力してください（空欄でもOK）：")

# ログの保存準備
log_data = {
    "user_id": user_id,
    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "script": correct_script,
    "transcript": user_transcript,
    "wer": round(wer_score, 2),
    "substitutions": S,
    "deletions": D,
    "insertions": I,
    "words": N,
    "note": note
}

# log.json に追記（なければ新規作成）
log_file = "log.json"

# 既存ログ読み込み（なければ空リスト）
if os.path.exists(log_file):
    with open(log_file, "r", encoding="utf-8") as f:
        logs = json.load(f)
else:
    logs = []

# 新しいログを追加
logs.append(log_data)

# 保存
with open(log_file, "w", encoding="utf-8") as f:
    json.dump(logs, f, ensure_ascii=False, indent=2)

print("✅ ログが log.json に保存されました。")
color_diff(correct_script, user_transcript)
