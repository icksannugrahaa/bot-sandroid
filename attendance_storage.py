# storage.py
import json
import os
import random
from datetime import datetime, timezone

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_DIR = os.path.join(_BASE_DIR, "tokens")
STATUS_DIR = os.path.join(_BASE_DIR, "status")

os.makedirs(TOKEN_DIR, exist_ok=True)
os.makedirs(STATUS_DIR, exist_ok=True)


def _token_path(alias: str) -> str:
    return os.path.join(TOKEN_DIR, f"{alias}.json")


def _status_path(alias: str) -> str:
    return os.path.join(STATUS_DIR, f"{alias}.json")


# ======================
# TOKEN
# ======================

def save_token(alias: str, data: dict):
    with open(_token_path(alias), "w") as f:
        json.dump(data, f, indent=2)


def load_token(alias: str):
    path = _token_path(alias)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def is_token_expired(token: dict) -> bool:
    expires_at = datetime.fromisoformat(token["expires_at"])
    return datetime.now(timezone.utc) >= expires_at


# ======================
# STATUS
# ======================

def _load_status(alias: str) -> dict:
    path = _status_path(alias)
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def _save_status(alias: str, data: dict):
    with open(_status_path(alias), "w") as f:
        json.dump(data, f, indent=2)


def is_already_checked_in(alias: str, date_key: str) -> bool:
    return _load_status(alias).get(date_key) == "IN"


def is_already_checked_out(alias: str, date_key: str) -> bool:
    return _load_status(alias).get(date_key) == "OUT"


def save_check_in(alias: str, date_key: str):
    data = _load_status(alias)
    data[date_key] = "IN"
    _save_status(alias, data)


def save_check_out(alias: str, date_key: str):
    data = _load_status(alias)
    data[date_key] = "OUT"
    _save_status(alias, data)

def get_or_create_time(alias: str, date_key: str, start, end):
    data = _load_status(alias)
    key = f"{date_key}:time:{start}-{end}"

    if key in data:
        return data[key]

    hour, minute = start
    end_hour, end_min = end

    base = hour * 60 + minute
    limit = end_hour * 60 + end_min
    picked = random.randint(base, limit)

    t = f"{picked//60:02d}:{picked%60:02d}:00"
    data[key] = t
    _save_status(alias, data)
    return t
