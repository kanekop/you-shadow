import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# === Google Sheets の認証設定 ===
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# === スプレッドシートに接続 ===
spreadsheet_id = "1s_CYCvhZZiSLWftQt3A7Rvs7Ee2ibpmAsl2YI0cPewE"
sheet = client.open_by_key(spreadsheet_id).sheet1  # 1つ目のシートを使用

# === log.json の読み込み ===
with open("log.json", "r", encoding="utf-8") as f:
    logs = json.load(f)

# === シートの初期化（ヘッダー行を設定） ===
sheet.clear()
header = [
    "user_id", "date", "script", "transcript",
    "wer", "substitutions", "deletions", "insertions", "words", "note"
]
sheet.append_row(header)

# === データを1行ずつ追加 ===
for entry in logs:
    row = [
        entry.get("user_id", ""),
        entry.get("date", ""),
        entry.get("script", ""),
        entry.get("transcript", ""),
        entry.get("wer", ""),
        entry.get("substitutions", ""),
        entry.get("deletions", ""),
        entry.get("insertions", ""),
        entry.get("words", ""),
        entry.get("note", "")
    ]
    sheet.append_row(row)

print("✅ Google Sheets にログをアップロードしました！")
