import re
import whatsapp
import storage
import logging
from users import is_admin

logger = logging.getLogger(__name__)

def clean_number(num_str: str) -> str:
    # If the user provides a full ID with @ (like @lid or @c.us), preserve the domain
    if "@" in num_str:
        num_part, domain_part = num_str.split("@", 1)
        cleaned_num = re.sub(r'\D', '', num_part)
        if not cleaned_num: return ""
        if cleaned_num.startswith("08"):
            cleaned_num = "628" + cleaned_num[2:]
        return f"{cleaned_num}@{domain_part}"
    
    # Otherwise, assume it's a regular phone number and append @c.us
    cleaned = re.sub(r'\D', '', num_str)
    if not cleaned: return ""
    if cleaned.startswith("08"):
        cleaned = "628" + cleaned[2:]
    return f"{cleaned}@c.us"

def group_create_cmd(send_text, chat_id, raw_body):
    parts = raw_body.split()
    if len(parts) < 3:
        return send_text(chat_id, "⚠️ Usage: *group create <name> [nomor1,nomor2]*")
    
    name_parts = []
    participants = []
    
    for p in parts[2:]:
        # Strip brackets just in case user typed literal documentation brackets
        clean_p = p.strip("[]")
        
        # If it looks like a number or has commas
        if clean_p.replace(",","").isdigit() or clean_p.startswith("@"):
            nums = clean_p.split(",")
            for n in nums:
                cn = clean_number(n)
                if cn: participants.append(cn)
        else:
            name_parts.append(p)
            
    name = " ".join(name_parts)
    if not name:
        return send_text(chat_id, "⚠️ Nama grup tidak boleh kosong.")
        
    if not participants:
        return send_text(chat_id, "⚠️ Gagal membuat grup: Anda harus memasukkan minimal 1 nomor peserta.\nFormat: *group create <nama> <nomor_peserta>*")
        
    send_text(chat_id, f"⏳ Sedang membuat grup '{name}' dengan {len(participants)} peserta...")
    res = whatsapp.create_group(name, participants)
    if res.get("success"):
        send_text(chat_id, f"✅ Grup berhasil dibuat!")
    else:
        send_text(chat_id, f"❌ Gagal membuat grup: {res.get('error')}")

def group_update_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"):
        return send_text(chat_id, "⚠️ Perintah ini hanya bisa digunakan di dalam grup.")
        
    # group update <name> | <desc>
    content = raw_body[len("group update "):].strip()
    
    media = data.get("media")
    if media and "data" in media and "mimetype" in media:
        send_text(chat_id, "⏳ Sedang mengupdate foto grup...")
        res_pic = whatsapp.update_group_picture(chat_id, media["data"], media["mimetype"])
        if not res_pic.get("success"):
            send_text(chat_id, f"❌ Gagal mengupdate foto grup: {res_pic.get('error')}\n_(Mungkin API ini belum didukung oleh OpenWA)_")
        else:
            send_text(chat_id, "✅ Foto grup berhasil diupdate.")
            
    if not content and not media:
        return send_text(chat_id, "⚠️ Usage: *group update <nama baru> | <deskripsi baru>* (atau lampirkan gambar untuk ganti profil)")
        
    if content:
        name = None
        desc = None
        if "|" in content:
            name, desc = [x.strip() for x in content.split("|", 1)]
        else:
            name = content
            
        send_text(chat_id, "⏳ Sedang mengupdate info grup...")
        res = whatsapp.update_group(chat_id, name, desc)
        if res.get("success"):
            send_text(chat_id, "✅ Info grup berhasil diupdate.")
        else:
            send_text(chat_id, f"❌ Gagal update grup: {res.get('error')}")

def group_users_cmd(send_text, chat_id, data):
    if not data.get("isGroup"):
        return send_text(chat_id, "⚠️ Perintah ini hanya bisa digunakan di dalam grup.")
        
    res = whatsapp.get_group_info(chat_id)
    if not res.get("success"):
        return send_text(chat_id, f"❌ Gagal mendapatkan info grup: {res.get('error')}")
        
    group_data = res.get("data", {})
    participants = group_data.get("participants", [])
    msg = f"👥 *Daftar Member ({len(participants)})*\n"
    for p in participants:
        pid = p.get("id", "").replace("@c.us", "")
        role = "Admin" if p.get("isAdmin") else "Member"
        msg += f"• {pid} ({role})\n"
        
    send_text(chat_id, msg)

def group_leave_cmd(send_text, chat_id, data):
    if not data.get("isGroup"):
        return send_text(chat_id, "⚠️ Perintah ini hanya bisa digunakan di dalam grup.")
    
    send_text(chat_id, "👋 Selamat tinggal! Bot akan keluar dari grup.")
    whatsapp.leave_group(chat_id)

def admin_add_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    if len(parts) < 3: return send_text(chat_id, "⚠️ Usage: *admin add <nomor>*")
    target = clean_number(parts[2])
    res = whatsapp.add_group_admin(chat_id, [target])
    if res.get("success"): send_text(chat_id, f"✅ Berhasil mengangkat {target.replace('@c.us','')} menjadi admin.")
    else: send_text(chat_id, f"❌ Gagal: {res.get('error')}")

def admin_remove_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    if len(parts) < 3: return send_text(chat_id, "⚠️ Usage: *admin remove <nomor>*")
    target = clean_number(parts[2])
    res = whatsapp.remove_group_admin(chat_id, [target])
    if res.get("success"): send_text(chat_id, f"✅ Berhasil menurunkan {target.replace('@c.us','')} dari admin.")
    else: send_text(chat_id, f"❌ Gagal: {res.get('error')}")

def user_add_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    if len(parts) < 3: return send_text(chat_id, "⚠️ Usage: *user add <nomor>*")
    target = clean_number(parts[2])
    res = whatsapp.add_group_participant(chat_id, [target])
    if res.get("success"): send_text(chat_id, f"✅ Berhasil menambahkan {target.replace('@c.us','')} ke grup.")
    else: send_text(chat_id, f"❌ Gagal: {res.get('error')}")

def user_kick_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    if len(parts) < 3: return send_text(chat_id, "⚠️ Usage: *user kick <nomor>*")
    target = clean_number(parts[2])
    res = whatsapp.remove_group_participant(chat_id, [target])
    if res.get("success"): send_text(chat_id, f"✅ Berhasil mengeluarkan {target.replace('@c.us','')} dari grup.")
    else: send_text(chat_id, f"❌ Gagal: {res.get('error')}")

def user_mute_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    if len(parts) < 3: return send_text(chat_id, "⚠️ Usage: *user mute <nomor>*")
    target = clean_number(parts[2])
    storage.mute_user(chat_id, target)
    send_text(chat_id, f"🔇 Berhasil membisukan {target.replace('@c.us','')}. Pesan mereka akan dihapus otomatis (pastikan bot adalah admin).")

def user_unmute_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    if len(parts) < 3: return send_text(chat_id, "⚠️ Usage: *user unmute <nomor>*")
    target = clean_number(parts[2])
    storage.unmute_user(chat_id, target)
    send_text(chat_id, f"🔊 {target.replace('@c.us','')} telah di-unmute.")
