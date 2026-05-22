from users import (
    list_users,
    add_user,
    get_user,
    set_automation,
    set_notes,
    set_location_pool,
    set_imei,
    load_users,
    set_checkin_timerange,
    set_checkout_timerange
)
from location import load_locations, save_location
import device_utils
from auth import AuthClient
from attendance import (
    check_in,
    check_out,
    get_history_for_user,
    generate_timesheet_excel
)

def deny(send_text_fn, chat_id):
    send_text_fn(chat_id, "❌ Akses ditolak")

def users_cmd(send_text_fn, chat_id):
    users = list_users()
    if not users:
        return send_text_fn(chat_id, "Belum ada user.")

    msg = "👥 *User Terdaftar:*\n"
    for alias, u in users.items():
        auto = "ON" if u.get("automation") else "OFF"
        notes = u.get("notes") or "-"
        pool = u.get("location_pool", "kanpus").upper()
        checkin_time = u.get("checkin_timerange") or "07:15-07:35"
        checkout_time = u.get("checkout_timerange") or "16:30-17:30"
        msg += (
            f"\n• `{alias}`\n"
            f"  username: `{u['username']}`\n"
            f"  location: `{pool}`\n"
            f"  check-in: `{checkin_time}`\n"
            f"  check-out: `{checkout_time}`\n"
            f"  auto: `{auto}`\n"
            f"  notes: {notes}\n"
        )

    send_text_fn(chat_id, msg)

def adduser_cmd(send_text_fn, chat_id, text):
    try:
        parts = text.split()
        if len(parts) == 5:
            _, alias, username, password, imei = parts
            add_user(alias, username, password, imei)
            send_text_fn(chat_id, f"✅ User {alias} ditambahkan!")
        else:
            raise ValueError()
    except ValueError:
        send_text_fn(chat_id, "Format:\n/adduser <alias> <user> <pass> <imei>")

def login_cmd(send_text_fn, chat_id, text):
    try:
        parts = text.split()
        alias = parts[1]
        user = get_user(alias)
        if not user:
            return send_text_fn(chat_id, "❌ User tidak ditemukan")

        AuthClient(
            alias=alias,
            username=user["username"],
            password=user["password"],
            imei=user["imei"]
        ).login_and_get_token()

        send_text_fn(chat_id, f"✅ Login berhasil `{alias}`")
    except Exception as e:
        send_text_fn(chat_id, f"❌ Login gagal: {e}")

def register_imei_cmd(send_text_fn, chat_id, text):
    try:
        parts = text.split()
        alias = parts[1]
        user = get_user(alias)
        if not user:
            return send_text_fn(chat_id, "❌ User tidak ditemukan")

        AuthClient(
            alias=alias,
            username=user["username"],
            password=user["password"],
            imei=user["imei"]
        ).register_imei()

        send_text_fn(chat_id, f"✅ IMEI Berhasil Didaftarkan untuk `{alias}`")
    except Exception as e:
        send_text_fn(chat_id, f"❌ Register IMEI gagal: {e}")

def gendeviceid_cmd(send_text_fn, chat_id, text):
    try:
        parts = text.split()
        new_imei = device_utils.generate_device_id()

        if len(parts) > 1:
            alias = parts[1]
            if set_imei(alias, new_imei):
                send_text_fn(chat_id, f"✅ Device ID (IMEI) baru untuk `{alias}` berhasil dibuat dan disimpan:\n`{new_imei}`\n\nSilahkan jalankan `/register_imei {alias}`.")
            else:
                send_text_fn(chat_id, "❌ User tidak ditemukan.")
        else:
            send_text_fn(chat_id, f"✅ Generated Device ID (Android):\n`{new_imei}`")
    except Exception as e:
        send_text_fn(chat_id, f"❌ Gagal generate device id: {e}")

def masuk_cmd(send_text_fn, chat_id, text):
    try:
        parts = text.split()
        alias = parts[1] if len(parts) > 1 else None
        msg = check_in(alias)
        send_text_fn(chat_id, msg)
    except Exception as e:
        send_text_fn(chat_id, f"❌ {e}")

def pulang_cmd(send_text_fn, chat_id, text):
    try:
        parts = text.split()
        alias = parts[1] if len(parts) > 1 else None
        msg = check_out(alias)
        send_text_fn(chat_id, msg)
    except Exception as e:
        send_text_fn(chat_id, f"❌ {e}")

def history_cmd(send_text_fn, chat_id, text):
    parts = text.split()
    mode = None
    alias = None

    if len(parts) == 2:
        if parts[1] in ("week", "month", "timesheet"):
            mode = parts[1]
        else:
            alias = parts[1]
    elif len(parts) >= 3:
        mode = parts[1]
        alias = parts[2]

    users = load_users()
    
    if mode == "timesheet":
        if not alias or alias not in users:
            return send_text_fn(chat_id, "❌ User tidak ditemukan atau format salah. /list_history timesheet <alias>")
        
        try:
            file_path = generate_timesheet_excel(alias)
            # send_document is needed in bot.py, here we'll just return the path for now or inform user
            # Since send_text doesn't support documents, we'll need to update bot.py to support send_file
            send_text_fn(chat_id, f"✅ Timesheet generated at: {file_path}")
        except Exception as e:
            send_text_fn(chat_id, f"❌ Gagal generate timesheet: {e}")
        return

    msg = ""
    if alias:
        msg = get_history_for_user(alias, mode)
    else:
        for a in users:
            msg += get_history_for_user(a, mode) + "\n"

    send_text_fn(chat_id, msg or "Tidak ada data")

def setnotes_cmd(send_text_fn, chat_id, text):
    try:
        _, alias, notes = text.split(maxsplit=2)
        if not set_notes(alias, notes):
            return send_text_fn(chat_id, "❌ User tidak ditemukan")
        send_text_fn(chat_id, f"📝 Notes `{alias}` diperbarui:\n{notes}")
    except ValueError:
        send_text_fn(chat_id, "Format:\n/set_notes <alias> <pesan>")

def clearnotes_cmd(send_text_fn, chat_id, text):
    try:
        _, alias = text.split()
        if not set_notes(alias, None):
            return send_text_fn(chat_id, "❌ User tidak ditemukan")
        send_text_fn(chat_id, f"🧹 Notes `{alias}` dihapus")
    except ValueError:
        send_text_fn(chat_id, "Format:\n/clear_notes <alias>")

def location_list_cmd(send_text_fn, chat_id):
    locations = load_locations()
    if not locations:
        return send_text_fn(chat_id, "Belum ada lokasi tersimpan.")
        
    sorted_keys = sorted(locations.keys())
    users = load_users()
    pool_counts = {k: 0 for k in sorted_keys}
    for u in users.values():
        pool = u.get("location_pool", "kanpus").lower()
        if pool in pool_counts:
            pool_counts[pool] += 1
    
    msg = "📍 *Daftar Lokasi*\n\n"
    for idx, key in enumerate(sorted_keys):
        lat, lng = locations[key]
        users_count = pool_counts[key]
        msg += f"*{idx + 1}. {key.upper()}*\n   • Lat/Lng: `{lat}, {lng}`\n   • Total User: `{users_count}` user\n\n"
        
    send_text_fn(chat_id, msg)

def setlocation_cmd(send_text_fn, chat_id, text):
    try:
        parts = text.split(maxsplit=2)
        alias = parts[1]
        pool = parts[2].lower()

        available_locations = load_locations()
        sorted_keys = sorted(available_locations.keys())

        if pool.isdigit():
            idx = int(pool) - 1
            if 0 <= idx < len(sorted_keys):
                pool = sorted_keys[idx]

        if pool not in available_locations:
            return send_text_fn(chat_id, "❌ Location pool tidak valid.")

        if not set_location_pool(alias, pool):
            return send_text_fn(chat_id, "❌ User tidak ditemukan")

        send_text_fn(chat_id, f"📍 Location pool `{alias}` diubah ke: *{pool.upper()}*")
    except Exception:
        send_text_fn(chat_id, "Format:\n/set_location <alias> <name_or_id>")

def addlocation_cmd(send_text_fn, chat_id, text):
    try:
        parts = text.split(maxsplit=2)
        loc_name = parts[1].lower()
        latlng_str = parts[2]
        
        latlng = latlng_str.replace(" ", "").split(",")
        if len(latlng) != 2:
            return send_text_fn(chat_id, "❌ Format latlng salah.")
            
        lat, lng = float(latlng[0]), float(latlng[1])
        save_location(loc_name, lat, lng)

        send_text_fn(chat_id, f"✅ Location `{loc_name}` berhasil ditambahkan.")
    except Exception:
        send_text_fn(chat_id, "Format:\n/add_location <location_name> <lat,lng>")

def set_checkin_timerange_cmd(send_text_fn, chat_id, text):
    try:
        parts = text.split()
        alias, start_time, end_time = parts[1], parts[2], parts[3]

        if not set_checkin_timerange(alias, start_time, end_time):
            return send_text_fn(chat_id, "❌ User tidak ditemukan")

        send_text_fn(chat_id, f"✅ Waktu check-in `{alias}` diatur ke: *{start_time} - {end_time}*")
    except Exception:
        send_text_fn(chat_id, "Format:\n/set_checkin_timerange <alias> HH:MM HH:MM")

def set_checkout_timerange_cmd(send_text_fn, chat_id, text):
    try:
        parts = text.split()
        alias, start_time, end_time = parts[1], parts[2], parts[3]

        if not set_checkout_timerange(alias, start_time, end_time):
            return send_text_fn(chat_id, "❌ User tidak ditemukan")

        send_text_fn(chat_id, f"✅ Waktu check-out `{alias}` diatur ke: *{start_time} - {end_time}*")
    except Exception:
        send_text_fn(chat_id, "Format:\n/set_checkout_timerange <alias> HH:MM HH:MM")

def auto_cmd(send_text_fn, chat_id, text):
    parts = text.split()
    if len(parts) != 3:
        return send_text_fn(chat_id, "Format:\n/set_auto on/off <alias>")

    _, mode, alias = parts
    enabled = mode.lower() == "on"

    if not set_automation(alias, enabled):
        return send_text_fn(chat_id, "❌ User tidak ditemukan")

    status = "AKTIF" if enabled else "NONAKTIF"
    send_text_fn(chat_id, f"⚙️ Automation `{alias}`: {status}")

