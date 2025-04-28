
import json
from datetime import datetime
from config import LOG_FILE

def save_log_entry(data):
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logs = []
    
    data["timestamp"] = datetime.utcnow().isoformat()
    logs.append(data)
    
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

def get_user_logs(username):
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
        return [log for log in logs if log.get("user", "").lower() == username.lower()]
    except (FileNotFoundError, json.JSONDecodeError):
        return []
