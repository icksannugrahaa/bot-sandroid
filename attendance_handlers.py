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
    set_checkout_timerange,
    get_authorized_alias,
    is_admin
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
    users = list_users(chat_id)
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
        content = text[9:].strip() # len("add user ")
        parts = content.split()
        if len(parts) == 4:
            alias, username, password, imei = parts
            add_user(alias, username, password, imei, chat_id)
            send_text_fn(chat_id, f"✅ User {alias} ditambahkan!")
        else:
            raise ValueError()
    except ValueError:
        send_text_fn(chat_id, "Format:\nadd user <alias> <user> <pass> <imei>")

def login_cmd(send_text_fn, chat_id, text):
    try:
        alias_arg = text[6:].strip() or None
        alias = get_authorized_alias(chat_id, alias_arg)
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
        alias_arg = text[14:].strip() or None
        alias = get_authorized_alias(chat_id, alias_arg)
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
            alias = get_authorized_alias(chat_id, parts[1])
            if set_imei(alias, new_imei):
                send_text_fn(chat_id, f"✅ Device ID (IMEI) baru untuk `{alias}` berhasil dibuat dan disimpan:\n`{new_imei}`\n\nSilahkan jalankan `register imei {alias}`.")
            else:
                send_text_fn(chat_id, "❌ User tidak ditemukan.")
        else:
            send_text_fn(chat_id, f"✅ Generated Device ID (Android):\n`{new_imei}`")
    except Exception as e:
        send_text_fn(chat_id, f"❌ Gagal generate device id: {e}")

def masuk_cmd(send_text_fn, chat_id, text):
    try:
        parts = text.split()
        alias_arg = parts[1] if len(parts) > 1 else None
        alias = get_authorized_alias(chat_id, alias_arg)
        msg = check_in(alias)
        send_text_fn(chat_id, msg)
    except Exception as e:
        send_text_fn(chat_id, f"❌ {e}")

def pulang_cmd(send_text_fn, chat_id, text):
    try:
        parts = text.split()
        alias_arg = parts[1] if len(parts) > 1 else None
        alias = get_authorized_alias(chat_id, alias_arg)
        msg = check_out(alias)
        send_text_fn(chat_id, msg)
    except Exception as e:
        send_text_fn(chat_id, f"❌ {e}")

def history_cmd(send_text_fn, chat_id, text):
    try:
        content = text[13:].strip() # len("list history ")
        parts = content.split()
        mode = None
        alias_arg = None

        if len(parts) == 1:
            if parts[0] in ("week", "month", "timesheet"):
                mode = parts[0]
            else:
                alias_arg = parts[0]
        elif len(parts) >= 2:
            mode = parts[1] if parts[1] in ("week", "month", "timesheet") else parts[0]
            alias_arg = parts[0] if parts[1] in ("week", "month", "timesheet") else parts[1]

        users = list_users(chat_id)
        
        if mode == "timesheet":
            alias = get_authorized_alias(chat_id, alias_arg)
            file_path = generate_timesheet_excel(alias)
            send_text_fn(chat_id, f"✅ Timesheet generated at: {file_path}")
            return

        msg = ""
        if alias_arg:
            alias = get_authorized_alias(chat_id, alias_arg)
            msg = get_history_for_user(alias, mode)
        else:
            if not users:
                return send_text_fn(chat_id, "Tidak ada data (Belum ada alias yang didaftarkan).")
            for a in users:
                msg += get_history_for_user(a, mode) + "\n"

        send_text_fn(chat_id, msg or "Tidak ada data")
    except Exception as e:
        send_text_fn(chat_id, f"❌ Gagal mengambil history: {e}")

def setnotes_cmd(send_text_fn, chat_id, text):
    try:
        content = text[10:].strip() # len("set notes ")
        alias_arg, notes = content.split(maxsplit=1)
        alias = get_authorized_alias(chat_id, alias_arg)
        
        if not set_notes(alias, notes):
            return send_text_fn(chat_id, "❌ User tidak ditemukan")
        send_text_fn(chat_id, f"📝 Notes `{alias}` diperbarui:\n{notes}")
    except ValueError:
        send_text_fn(chat_id, "Format:\nset notes <alias> <pesan>")
    except Exception as e:
        send_text_fn(chat_id, f"❌ {e}")

def clearnotes_cmd(send_text_fn, chat_id, text):
    try:
        alias_arg = text[12:].strip() or None
        alias = get_authorized_alias(chat_id, alias_arg)
        
        if not set_notes(alias, None):
            return send_text_fn(chat_id, "❌ User tidak ditemukan")
        send_text_fn(chat_id, f"🧹 Notes `{alias}` dihapus")
    except Exception as e:
        send_text_fn(chat_id, f"❌ {e}")

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
        gmaps_link = f"https://www.google.com/maps?q={lat},{lng}"
        msg += f"*{idx + 1}. {key.upper()}*\n   • 🗺️ {gmaps_link}\n   • Total User: `{users_count}` user\n\n"
        
    send_text_fn(chat_id, msg)

def setlocation_cmd(send_text_fn, chat_id, text):
    try:
        content = text[13:].strip() # len("set location ")
        parts = content.split(maxsplit=1)
        if len(parts) == 1:
            alias = get_authorized_alias(chat_id, None)
            pool = parts[0].lower()
        elif len(parts) == 2:
            alias = get_authorized_alias(chat_id, parts[0])
            pool = parts[1].lower()
        else:
            raise ValueError()

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
    except Exception as e:
        send_text_fn(chat_id, f"❌ {e}")

def addlocation_cmd(send_text_fn, chat_id, text):
    if not is_admin(chat_id):
        return deny(send_text_fn, chat_id)
        
    try:
        content = text[13:].strip() # len("add location ")
        
        if "," not in content:
            raise ValueError()
            
        comma_idx = content.rfind(",")
        space_idx = content.rfind(" ", 0, comma_idx)
        
        if space_idx == -1:
            raise ValueError()
            
        loc_name = content[:space_idx].strip().lower()
        lat_str = content[space_idx:comma_idx].strip()
        lng_str = content[comma_idx+1:].strip()
        
        lat = float(lat_str)
        lng = float(lng_str)
        save_location(loc_name, lat, lng)

        send_text_fn(chat_id, f"✅ Location `{loc_name}` berhasil ditambahkan.")
    except Exception:
        send_text_fn(chat_id, "Format:\nadd location <location_name> <lat,lng>")

def set_checkin_timerange_cmd(send_text_fn, chat_id, text):
    try:
        content = text[22:].strip() # len("set checkin timerange ")
        parts = content.split()
        if len(parts) == 2:
            alias = get_authorized_alias(chat_id, None)
            start_time, end_time = parts[0], parts[1]
        elif len(parts) == 3:
            alias = get_authorized_alias(chat_id, parts[0])
            start_time, end_time = parts[1], parts[2]
        else:
            raise ValueError("Format salah")

        if not set_checkin_timerange(alias, start_time, end_time):
            return send_text_fn(chat_id, "❌ User tidak ditemukan")

        send_text_fn(chat_id, f"✅ Waktu check-in `{alias}` diatur ke: *{start_time} - {end_time}*")
    except Exception as e:
        send_text_fn(chat_id, f"❌ {e}")

def set_checkout_timerange_cmd(send_text_fn, chat_id, text):
    try:
        content = text[23:].strip() # len("set checkout timerange ")
        parts = content.split()
        if len(parts) == 2:
            alias = get_authorized_alias(chat_id, None)
            start_time, end_time = parts[0], parts[1]
        elif len(parts) == 3:
            alias = get_authorized_alias(chat_id, parts[0])
            start_time, end_time = parts[1], parts[2]
        else:
            raise ValueError("Format salah")

        if not set_checkout_timerange(alias, start_time, end_time):
            return send_text_fn(chat_id, "❌ User tidak ditemukan")

        send_text_fn(chat_id, f"✅ Waktu check-out `{alias}` diatur ke: *{start_time} - {end_time}*")
    except Exception as e:
        send_text_fn(chat_id, f"❌ {e}")

def auto_cmd(send_text_fn, chat_id, text):
    try:
        content = text[9:].strip() # len("set auto ")
        parts = content.split()
        if len(parts) == 1:
            mode = parts[0]
            alias = get_authorized_alias(chat_id, None)
        elif len(parts) == 2:
            mode = parts[0]
            alias = get_authorized_alias(chat_id, parts[1])
        else:
            return send_text_fn(chat_id, "Format:\nset auto on/off <alias>")

        enabled = mode.lower() == "on"

        if not set_automation(alias, enabled):
            return send_text_fn(chat_id, "❌ User tidak ditemukan")

        status = "AKTIF" if enabled else "NONAKTIF"
        send_text_fn(chat_id, f"⚙️ Automation `{alias}`: {status}")
    except Exception as e:
        send_text_fn(chat_id, f"❌ {e}")
