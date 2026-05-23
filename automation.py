import sys
import os
import random
import json
import time as time_mod
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import holidays

# Add root directory to python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import ADMIN_CHAT_IDS
from whatsapp import send_text
from logger import log as bot_log
from auth import AuthClient
from attendance import check_in, check_out
from storage import (
    get_attendance_users,
    get_attendance_status,
    save_attendance_status
)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_DIR = os.path.join(_BASE_DIR, "status")
os.makedirs(STATUS_DIR, exist_ok=True)
LOCK_FILE = os.path.join(STATUS_DIR, "attendance_runner.lock")
NIGHTLY_LOCK_FILE = os.path.join(STATUS_DIR, "nightly_runner.lock")

def acquire_lock(lock_path: str = None):
    path = lock_path or LOCK_FILE
    if os.name == 'nt':
        import msvcrt
        lock_fd = open(path, "w")
        try:
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
            return lock_fd
        except OSError:
            print(f"Runner masih berjalan ({path}), skip.")
            sys.exit(0)
    else:
        import fcntl
        lock_fd = open(path, "w")
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_fd
        except BlockingIOError:
            print(f"Runner masih berjalan ({path}), skip.")
            sys.exit(0)

def notify_admin(msg: str):
    if not ADMIN_CHAT_IDS:
        bot_log("⚠️ Tidak ada ADMIN_CHAT_IDS untuk notifikasi automation.")
        return
    admin_id = ADMIN_CHAT_IDS[0]
    send_text(admin_id, msg)

def notify_error(msg: str, alias: str = None):
    notify_admin(f"🚨 *Automation Error*\n{msg}")


# ======================
# CONFIG
# ======================

TZ = ZoneInfo("Asia/Jakarta")

CHECK_IN_START  = time(7, 15)
CHECK_IN_END    = time(7, 35)

CHECK_OUT_START = time(16, 30)
CHECK_OUT_END   = time(17, 30)


# ======================
# HELPER
# ======================

def now():
    return datetime.now(TZ)


ID_HOLIDAYS = holidays.ID()

def is_weekend_or_holiday(dt: datetime) -> tuple[bool, str]:
    if dt.weekday() >= 5: # 5=Sat, 6=Sun
        return True, "Akhir pekan (Weekend)"
    
    date_obj = dt.date()
    if date_obj in ID_HOLIDAYS:
        return True, f"Libur Nasional: {ID_HOLIDAYS.get(date_obj)}"
        
    return False, ""


def _update_notif_state(filepath: str, key: str, value: str) -> bool:
    """Helper for reading, updating, and writing json notification state. Returns True if updated."""
    data = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
        except:
            pass

    if data.get(key) != value:
        data[key] = value
        try:
            with open(filepath, "w") as f:
                json.dump(data, f)
        except:
            pass
        return True
    return False


def check_tomorrow_holiday(dt: datetime):
    tomorrow = dt.date() + timedelta(days=1)
    if tomorrow in ID_HOLIDAYS:
        notif_path = os.path.join(STATUS_DIR, "holiday_notif.json")
        today_str = dt.strftime("%Y-%m-%d")
        if _update_notif_state(notif_path, "last_notified", today_str):
            holiday_name = ID_HOLIDAYS.get(tomorrow)
            notify_admin(f"ℹ️ *Info Libur*\nBesok adalah hari libur: *{holiday_name}*.\nBot tidak akan absen otomatis besok.")


def notify_today_holiday(dt: datetime, reason: str, window: str):
    notif_path = os.path.join(STATUS_DIR, "today_holiday_notif.json")
    today_str = dt.strftime("%Y-%m-%d")
    
    if _update_notif_state(notif_path, window, today_str):
        notify_admin(f"ℹ️ *Info Libur / Akhir Pekan*\nHari ini adalah *{reason}*.\nBot tidak melakukan absen *{window}* otomatis hari ini.")


def notify_tomorrow_status(alias: str, dt_now: datetime, context: str):
    tomorrow = dt_now.date() + timedelta(days=1)
    
    is_weekend = tomorrow.weekday() >= 5
    holiday_name = ID_HOLIDAYS.get(tomorrow)
    
    if is_weekend or holiday_name:
        reason = holiday_name if holiday_name else "Akhir Pekan"
        if context == 'checkout':
            msg = f"🎉 *Selamat Beristirahat, {alias}!*\nKamu sudah berhasil check-out.\n\nBesok adalah *{reason}*, jadi bot absen otomatis akan dimatikan besok. Sampai jumpa di hari kerja berikutnya!"
        else: # nightly
            msg = f"🌙 *Nightly Update ({alias})*\nBesok adalah *{reason}*.\nBot absen otomatis *TIDAK* akan berjalan besok."
    else:
        if context == 'nightly':
            msg = f"🌙 *Nightly Update ({alias})*\nBesok adalah hari kerja biasa.\nBot absen otomatis *AKAN* berjalan sesuai jadwal besok pagi."
        else:
            return
            
    notify_admin(msg)



def in_range(now_t: time, start: time, end: time) -> bool:
    return start <= now_t <= end


def random_time_between(start: time, end: time) -> str:
    start_sec = start.hour * 3600 + start.minute * 60
    end_sec   = end.hour * 3600 + end.minute * 60
    sec = random.randint(start_sec, end_sec)
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h:02d}:{m:02d}"

def _get_user_time_bounds(timerange_str: str | None, default_start: time, default_end: time) -> tuple:
    if not timerange_str:
        return default_start, default_end
    try:
        start_str, end_str = timerange_str.split('-')
        start_h, start_m = map(int, start_str.split(':'))
        end_h, end_m = map(int, end_str.split(':'))
        return time(start_h, start_m), time(end_h, end_m)
    except Exception:
        return default_start, default_end


def _sched_key(date_key: str) -> str:
    """Key terpisah agar tidak konflik dengan status lain."""
    return f"schedule_{date_key}"


def load_daily_schedule(alias: str, date_key: str) -> dict:
    data = get_attendance_status(alias)
    value = data.get(_sched_key(date_key), {})
    return value if isinstance(value, dict) else {}


def save_daily_schedule(alias: str, date_key: str, payload: dict):
    data = get_attendance_status(alias)
    data[_sched_key(date_key)] = payload
    save_attendance_status(alias, data)


def is_already_checked_in(alias: str, date_key: str) -> bool:
    data = get_attendance_status(alias)
    return data.get(f"IN_{date_key}") == True

def is_already_checked_out(alias: str, date_key: str) -> bool:
    data = get_attendance_status(alias)
    return data.get(f"OUT_{date_key}") == True


def ensure_schedule(alias: str, date_key: str, user: dict) -> dict:
    sched = load_daily_schedule(alias, date_key)
    if sched:
        return sched

    in_start, in_end = _get_user_time_bounds(user.get("checkin_timerange"), CHECK_IN_START, CHECK_IN_END)
    out_start, out_end = _get_user_time_bounds(user.get("checkout_timerange"), CHECK_OUT_START, CHECK_OUT_END)

    sched = {
        "in": random_time_between(in_start, in_end),
        "out": random_time_between(out_start, out_end)
    }

    save_daily_schedule(alias, date_key, sched)
    bot_log(f"[AUTO] [{alias}] Jadwal hari ini IN={sched['in']} OUT={sched['out']}")
    notify_admin(f"[AUTO] [{alias}] Jadwal hari ini IN={sched['in']} OUT={sched['out']} ON {user.get('location_pool')}")
    return sched


def force_login(alias: str, user: dict, max_retries: int = 3):
    for attempt in range(1, max_retries + 1):
        try:
            bot_log(f"[AUTO] [{alias}] Memaksa login sebelum absen (Attempt {attempt}/{max_retries})")
            AuthClient(
                alias=alias,
                username=user["username"],
                password=user["password"],
                imei=user["imei"]
            ).login_and_get_token()
            return  # Login berhasil, keluar dari loop
        except Exception as e:
            if attempt < max_retries:
                bot_log(f"[AUTO] [{alias}] Login gagal: {e}. Retrying in 5 seconds...")
                time_mod.sleep(5)
            else:
                bot_log(f"[AUTO] [{alias}] Login gagal setelah {max_retries} percobaan: {e}")
                raise e # Lempar error agar attendance tidak dieksekusi


# ======================
# MAIN RUNNER
# ======================

def run():
    now_dt = now()
    now_t = now_dt.time()
    date_key = now_dt.strftime("%Y-%m-%d")

    check_tomorrow_holiday(now_dt)

    is_day_off, reason = is_weekend_or_holiday(now_dt)
    if is_day_off:
        bot_log(f"[AUTO] Skip automation hari ini: {reason}")
        if in_range(now_t, CHECK_IN_START, CHECK_IN_END):
            notify_today_holiday(now_dt, reason, "Masuk")
        elif in_range(now_t, CHECK_OUT_START, CHECK_OUT_END):
            notify_today_holiday(now_dt, reason, "Pulang")
        return

    users = get_attendance_users()
    if not users:
        return

    for alias, user in users.items():
        if not user.get("automation"):
            continue

        try:
            sched = ensure_schedule(alias, date_key, user)

            # ===== CHECK IN =====
            if not is_already_checked_in(alias, date_key):
                sched_in = time.fromisoformat(sched["in"])
                in_start, in_end = _get_user_time_bounds(user.get("checkin_timerange"), CHECK_IN_START, CHECK_IN_END)
                if now_t >= sched_in and in_range(now_t, in_start, in_end):
                    force_login(alias, user)
                    bot_log(f"[AUTO] [{alias}] Eksekusi absen masuk @ {sched['in']}")
                    msg = check_in(alias)
                    notify_admin(msg)

            # ===== CHECK OUT =====
            elif not is_already_checked_out(alias, date_key):
                sched_out = time.fromisoformat(sched["out"])
                out_start, out_end = _get_user_time_bounds(user.get("checkout_timerange"), CHECK_OUT_START, CHECK_OUT_END)
                if now_t >= sched_out and in_range(now_t, out_start, out_end):
                    force_login(alias, user)
                    bot_log(f"[AUTO] [{alias}] Eksekusi absen pulang @ {sched['out']}")
                    msg = check_out(alias)
                    notify_admin(msg)
                    notify_tomorrow_status(alias, now_dt, context='checkout')

        except Exception as e:
            bot_log(f"[AUTO] [{alias}] ERROR: {e}")
            notify_error(f"{alias}\n{e}", alias)

    bot_log("[AUTO] Runner tick selesai")


def run_nightly_check():
    now_dt = now()
    bot_log("[NIGHTLY] Menjalankan pengecekan Nightly Update")
    
    users = get_attendance_users()
    if not users:
        bot_log("[NIGHTLY] Tidak ada user terdaftar, skip.")
        return

    # Kumpulkan unique owner_chat_id
    owners = set()
    for alias, user in users.items():
        owner = user.get("owner_chat_id")
        if owner:
            owners.add(owner)
            
    # Buat pesan umum untuk besok
    tomorrow = now_dt.date() + timedelta(days=1)
    is_weekend = tomorrow.weekday() >= 5
    holiday_name = ID_HOLIDAYS.get(tomorrow)
    
    if is_weekend or holiday_name:
        reason = holiday_name if holiday_name else "Akhir Pekan"
        msg = f"🌙 *Nightly Update*\nBesok adalah *{reason}*.\nBot absen otomatis *TIDAK* akan berjalan besok."
    else:
        msg = f"🌙 *Nightly Update*\nBesok adalah hari kerja biasa.\nBot absen otomatis *AKAN* berjalan sesuai jadwal besok pagi."

    notified_count = 0
    for chat_id in owners:
        try:
            send_text(chat_id, msg)
            notified_count += 1
        except Exception as e:
            bot_log(f"[NIGHTLY] Error notifikasi chat_id {chat_id}: {e}")
            notify_error(f"Nightly notif gagal untuk {chat_id}\n{e}")

    if notified_count == 0:
        bot_log("[NIGHTLY] Tidak ada notifikasi yang dikirim.")
    else:
        bot_log(f"[NIGHTLY] Selesai, {notified_count} notifikasi terkirim.")


# ======================
# ENTRY
# ======================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--nightly":
        lock = acquire_lock(NIGHTLY_LOCK_FILE)
        try:
            run_nightly_check()
        except Exception as e:
            bot_log(f"[NIGHTLY] FATAL ERROR: {e}")
            notify_error(f"Nightly check gagal total\n{e}")
    else:
        lock = acquire_lock(LOCK_FILE)
        run()
