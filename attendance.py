# attendance.py
import requests
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from attendance_storage import (
    load_token,
    is_already_checked_in,
    is_already_checked_out,
    save_check_in,
    save_check_out,
    get_or_create_time,
    is_token_expired
)
from sprint import get_current_sprint
from logger import log
from config import URL_ABSENCE, URL_HISTORY, TEST_MODE
from users import load_users
from location import get_random_location

# ======================
# CONFIG
# ======================

DEFAULT_USERNAME = "icksan.nugraha"

# ======================
# HELPER
# ======================

def random_time(start_h, start_m, end_h, end_m) -> str:
    base = datetime(2000, 1, 1, start_h, start_m)
    end = datetime(2000, 1, 1, end_h, end_m)
    seconds = int((end - base).total_seconds())
    return datetime.fromtimestamp(
        base.timestamp() + random.randint(0, seconds)
    ).strftime("%H:%M:%S")


def _headers(token: dict) -> dict:
    return {
        "Authorization": f"Bearer {token['access_token']}",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "okhttp/3.14.9",
    }


def _resolve_alias(alias: str | None) -> str:
    """
    Jika alias None → pakai default user
    """
    if alias:
        return alias

    users = load_users()
    for a, u in users.items():
        if u.get("username") == DEFAULT_USERNAME:
            return a

    raise Exception("Default user tidak ditemukan")


def _get_user(alias: str) -> dict:
    users = load_users()
    if alias not in users:
        raise Exception(f"User '{alias}' tidak ditemukan")
    return users[alias]


def _now_jakarta():
    return datetime.now(ZoneInfo("Asia/Jakarta"))


def _submit_attendance(
    alias: str, 
    token: dict, 
    user: dict, 
    date_key: str, 
    time_range: tuple, 
    log_type: str, 
    notes: str, 
    is_test: bool
) -> str:
    """Helper private khusus submit payload absen (In / Out)."""
    now = _now_jakarta()
    
    # 1. Tentukan pool location dari preferensi user
    pool_type = user.get("location_pool", "kanpus")
    
    # 2. Ambil random location baru
    location = get_random_location(pool_type)
    
    log_time = get_or_create_time(
        alias,
        date_key,
        time_range[0],
        time_range[1]
    )

    payload = {
        "UserName": token["loginName"],
        "LogDate": now.strftime("%m/%d/%Y"),
        "LogTime": log_time,
        "LocationID": token.get("LocationID"),
        "LocationName": token.get("Location"),
        "LocationAddress": "Gedung BRI Tower II, Jakarta",
        "Longitude": location["lng"],
        "Latitude": location["lat"],
        "LogType": log_type,
        "GMT": "7",
    }
    
    if log_type == "Start Day":
        payload["Event"] = ""
        payload["Notes"] = notes

    action_name = "masuk" if log_type == "Start Day" else "pulang"

    # ===== TEST MODE =====
    if is_test:
        msg_suffix = f" | {notes}" if log_type == "Start Day" else ""
        msg = log(f"[TEST] [{alias}] Simulasi absen {action_name}{msg_suffix}")
        return msg

    # ===== REAL MODE =====
    r = requests.post(
        URL_ABSENCE,
        data=payload,
        headers=_headers(token),
        timeout=15
    )
    r.raise_for_status()

    resp = r.json()
    if resp.get("isSucceed"):
        msg_suffix = f" | {notes}" if log_type == "Start Day" else ""
        msg = log(f"[{alias}] Absen {action_name} berhasil{msg_suffix}")
        return msg

    raise Exception(f"[{alias}] Absen {action_name} gagal: {resp}")


def _parse_id_date(raw_date: str) -> str:
    """Mengubah format tanggal api ke format Indonesia (DD Bulan YYYY)"""
    id_months = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    try:
        if "T" in raw_date:
            dt_obj = datetime.strptime(raw_date.split("T")[0], "%Y-%m-%d")
        else:
            dt_obj = datetime.strptime(raw_date.split(" ")[0], "%m/%d/%Y")
        return f"{dt_obj.day} {id_months[dt_obj.month]} {dt_obj.year}"
    except (ValueError, TypeError):
        return raw_date or "-"


def _parse_time_range(timerange_str: str | None, default_range: tuple) -> tuple:
    """Parses 'HH:MM-HH:MM' into ((H, M), (H, M))"""
    if not timerange_str:
        return default_range
    try:
        start_str, end_str = timerange_str.split('-')
        start_h, start_m = start_str.split(':')
        end_h, end_m = end_str.split(':')
        return ((int(start_h), int(start_m)), (int(end_h), int(end_m)))
    except Exception:
        return default_range


# ======================
# CHECK IN
# ======================

def check_in(alias: str | None = None) -> str:
    alias = _resolve_alias(alias)
    user = _get_user(alias)

    token = load_token(alias)
    if not token or is_token_expired(token):
        raise Exception(f"[{alias}] Token tidak ada / expired")

    now = _now_jakarta()
    date_key = now.strftime("%Y-%m-%d")

    if is_already_checked_in(alias, date_key):
        return f"[{alias}] Sudah absen masuk hari ini"

    sprint = get_current_sprint(now.date())
    notes = user.get("notes") or f"Working sprint {sprint}"
    
    # Save test mode status internally to save_check_in inside wrapper
    if TEST_MODE:
        save_check_in(alias, date_key)
    else:
        # Optimistic block inside _submit_attendance will test isSucceed
        pass
        
    try:
        time_range = _parse_time_range(user.get("checkin_timerange"), ((7, 15), (7, 35)))
        res = _submit_attendance(
            alias=alias,
            token=token,
            user=user,
            date_key=date_key,
            time_range=time_range,
            log_type="Start Day",
            notes=notes,
            is_test=TEST_MODE
        )
        if not TEST_MODE:
            save_check_in(alias, date_key)
        return res
    except Exception as e:
        raise e


# ======================
# CHECK OUT
# ======================

def check_out(alias: str | None = None) -> str:
    alias = _resolve_alias(alias)

    token = load_token(alias)
    if not token or is_token_expired(token):
        raise Exception(f"[{alias}] Token tidak ada / expired")

    now = _now_jakarta()
    date_key = now.strftime("%Y-%m-%d")

    if is_already_checked_out(alias, date_key):
        return f"[{alias}] Sudah absen pulang hari ini"

    if TEST_MODE:
        save_check_out(alias, date_key)
        
    # Perlu load user untuk menarik properti location_pool
    user = _get_user(alias)
        
    try:
        time_range = _parse_time_range(user.get("checkout_timerange"), ((16, 30), (17, 30)))
        res = _submit_attendance(
            alias=alias,
            token=token,
            user=user,
            date_key=date_key,
            time_range=time_range,
            log_type="End Day",
            notes="",
            is_test=TEST_MODE
        )
        if not TEST_MODE:
            save_check_out(alias, date_key)
        return res
    except Exception as e:
        raise e


# ======================
# HISTORY
# ======================

def get_attendance_history(alias: str, date_from: str, date_to: str) -> list:
    token = load_token(alias)
    if not token or is_token_expired(token):
        raise Exception(f"[{alias}] Token tidak ada / expired")

    payload = {
        "DateFrom": date_from,
        "DateTo": date_to
    }

    r = requests.post(
        URL_HISTORY,
        data=payload,
        headers=_headers(token),
        timeout=15
    )
    r.raise_for_status()

    result = r.json()
    if result.get("isSucceed"):
        return result.get("ReturnValue", [])

    raise Exception(f"[{alias}] Gagal mengambil history: {result}")


def get_history_for_user(alias: str, mode: str | None = None) -> str:
    from datetime import timedelta

    now = _now_jakarta()

    if mode == "week":
        start = (now - timedelta(days=6)).strftime("%m/%d/%Y")
    elif mode == "month":
        start = (now - timedelta(days=30)).strftime("%m/%d/%Y")
    else:
        start = now.strftime("%m/%d/%Y")

    end = now.strftime("%m/%d/%Y")

    records = get_attendance_history(alias, start, end)

    msg = f"\n👤 *{alias}*\n"
    if not records:
        return msg + "Belum ada data\n"

    for r in records:
        raw_date = r.get("LogDate", "")
        date_str = _parse_id_date(raw_date)

        time = r.get("DisplayTime", "-")
        typ = r.get("LogType", "-")
        note = r.get("Notes", "-")
        lat = r.get("Latitude")
        lng = r.get("Longitude")

        map_url = (
            f"https://maps.google.com/?q={lat},{lng}"
            if lat and lng else ""
        )

        msg += f"• {date_str} - {time} - {typ} - {note} - {lat} - {lng} - {map_url}\n"

    return msg


def generate_timesheet_excel(alias: str) -> str:
    """
    Generate an Excel timesheet for the specified user and return the true file path.
    Requires openpyxl.
    """
    from datetime import timedelta
    import os

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
    except ImportError:
        raise Exception("openpyxl library is required for this feature")

    now = _now_jakarta()
    # default fetch 1 month history
    start = (now - timedelta(days=30)).strftime("%m/%d/%Y")
    end = now.strftime("%m/%d/%Y")

    records = get_attendance_history(alias, start, end)

    # Group records by Date
    grouped_data = {}
    
    for r in records:
        raw_date = r.get("LogDate", "")
        date_str = _parse_id_date(raw_date)

        if date_str not in grouped_data:
            grouped_data[date_str] = {
                "check_in": "-",
                "check_out": "-",
                "work_place": "-"
            }

        typ = r.get("LogType", "")
        time = r.get("DisplayTime", "")
        loc_name = r.get("LocationName") or r.get("LocationAddress") or "Gedung BRI Tower II, Jakarta"
        
        if typ == "Start Day":
            if grouped_data[date_str]["check_in"] == "-":
                grouped_data[date_str]["check_in"] = time
                grouped_data[date_str]["work_place"] = loc_name
        elif typ == "End Day":
            grouped_data[date_str]["check_out"] = time
            if grouped_data[date_str]["work_place"] == "-":
                 grouped_data[date_str]["work_place"] = loc_name

    # Create Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = f"Timesheet {alias}"

    # Headers
    headers = ["date", "check in", "check out", "work place"]
    ws.append(headers)
    
    header_font = Font(bold=True)
    alignment = Alignment(horizontal="center")

    for col in range(1, 5):
        cell = ws.cell(row=1, column=col)
        cell.font = header_font
        cell.alignment = alignment

    # Write Data Rows
    # get_attendance_history often returns descending. To sort it, we could try parsing "date_str" back if needed.
    # But usually it's fine as returned.
    
    for date_str, data in grouped_data.items():
        ws.append([
            date_str, 
            data["check_in"], 
            data["check_out"], 
            data["work_place"]
        ])

    # Adjust Column Widths mildly
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 15
    ws.column_dimensions["C"].width = 15
    ws.column_dimensions["D"].width = 30

    import tempfile
    file_path = os.path.join(tempfile.gettempdir(), f"{alias}_timesheet.xlsx")
    wb.save(file_path)

    return file_path
