import json
import csv
import os

# ファイル名
json_file = "log.json"
csv_file = "log.csv"

# JSONファイルの読み込み
if not os.path.exists(json_file):
    print("⚠️ log.json が見つかりません。先にログを作成してください。")
    exit()

with open(json_file, "r", encoding="utf-8") as f:
    data = json.load(f)

# 空のときの処理
if not data:
    print("⚠️ log.json にデータがありません。")
    exit()

# CSVに書き出すフィールド（列の順番）
fields = [
    "user_id",
    "date",
    "script",
    "transcript",
    "wer",
    "substitutions",
    "deletions",
    "insertions",
    "words",
    "note"
]

# 書き込み
with open(csv_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(data)

print(f"✅ log.json の内容を {csv_file} に書き出しました。")
