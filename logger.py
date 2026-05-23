import os
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "log")
LOG_FILE = os.path.join(LOG_DIR, "attendance.log")

os.makedirs(LOG_DIR, exist_ok=True)

def log(message: str):
    now = datetime.now(ZoneInfo("Asia/Jakarta"))
    line = f"[{now:%Y-%m-%d %H:%M:%S}] {message}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    return line

