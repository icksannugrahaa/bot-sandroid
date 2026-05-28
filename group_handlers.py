import re
import whatsapp
import storage
import logging
from users import is_admin
from config import ADMIN_CHAT_IDS

logger = logging.getLogger(__name__)

def clean_number(num_str: str) -> str:
    # Remove leading @ if the user used a plain text mention like @1234
    if num_str.startswith("@"):
        num_str = num_str[1:]
        
    # If the user provides a full ID with @ (like @lid or @c.us), preserve the domain
    if "@" in num_str:
        num_part, domain_part = num_str.split("@", 1)
        cleaned_num = re.sub(r'\D', '', num_part)
        if not cleaned_num: return ""
        if cleaned_num.startswith("08"):
            cleaned_num = "628" + cleaned_num[2:]
        return f"{cleaned_num}@{domain_part}"
    
    # Otherwise, assume it's a regular phone number
    cleaned = re.sub(r'\D', '', num_str)
    if not cleaned: return ""
    if cleaned.startswith("08"):
        cleaned = "628" + cleaned[2:]
        
    # Linked Device IDs (LIDs) are usually 15 digits long
    if len(cleaned) >= 15:
        return f"{cleaned}@lid"
    return f"{cleaned}@c.us"

def resolve_lid_to_cus(target: str) -> str:
    if target.endswith("@lid"):
        contact_res = whatsapp.get_contact_info(target)
        logger.info("resolve_lid_to_cus contact_res: %s", contact_res)
        if contact_res.get("success"):
            contact_data = contact_res.get("data", {})
            real_id = contact_data.get("id")
            if real_id and real_id.endswith("@c.us"):
                logger.info("Resolved %s to %s", target, real_id)
                return real_id
    return target

def group_create_cmd(send_text, chat_id, raw_body):
    parts = raw_body.split()
    if len(parts) < 3:
        return send_text(chat_id, "⚠️ Usage: *group create <nama> <nomor_peserta> [nomor_admin] [admin_only]*")
    
    # Defaults
    admin_only = False
    admins = []
    participants = []
    name_parts = []
    
    # Parse from the end to the beginning
    args = parts[2:]
    
    if args and args[-1].lower() == "admin_only":
        admin_only = True
        args.pop()
        
    # We expect up to 2 numeric groups at the end: [participants] [admins]
    numeric_args = []
    while args:
        clean_p = args[-1].strip("[]")
        # Check if it looks like a JID or a list of phone numbers
        if clean_p.replace(",", "").isdigit() or clean_p.startswith("@"):
            numeric_args.insert(0, args.pop())
        else:
            break
            
    name_parts = args
    
    # If 2 numeric arguments, first is participants, second is admins
    if len(numeric_args) >= 2:
        parts_str = numeric_args[0].split(",")
        admins_str = numeric_args[1].split(",")
        participants = [clean_number(n) for n in parts_str if clean_number(n)]
        admins = [clean_number(n) for n in admins_str if clean_number(n)]
    elif len(numeric_args) == 1:
        parts_str = numeric_args[0].split(",")
        participants = [clean_number(n) for n in parts_str if clean_number(n)]
        
    name = " ".join(name_parts)
    if not name:
        return send_text(chat_id, "⚠️ Nama grup tidak boleh kosong.")
        
    if not participants:
        return send_text(chat_id, "⚠️ Gagal membuat grup: Anda harus memasukkan minimal 1 nomor peserta.\nFormat: *group create <nama> <nomor_peserta> [nomor_admin] [admin_only]*")
        
    send_text(chat_id, f"⏳ Sedang membuat grup '{name}' dengan {len(participants)} peserta...")
    res = whatsapp.create_group(name, participants)
    
    # OpenWA returns raw group info on success, so we check if 'id' or 'gid' is in the result.
    if res.get("success") or ("id" in res) or ("gid" in res):
        group_id = res.get("id") or res.get("gid")
        reply = f"✅ Grup berhasil dibuat!"
        
        if group_id and admins:
            import time
            time.sleep(2)
            admin_res = whatsapp.add_group_admin(group_id, admins)
            if admin_res.get("success"):
                reply += f"\n✅ Berhasil mengangkat {len(admins)} admin."
            else:
                reply += f"\n❌ Gagal mengangkat admin: {admin_res.get('error')}"
                
        if group_id:
            import time
            time.sleep(2)
            setting_res = whatsapp.set_group_messages_setting(group_id, admin_only)
            if setting_res.get("success"):
                status_str = "Hanya Admin" if admin_only else "Semua Peserta"
                reply += f"\n✅ Setting chat grup diubah ke: {status_str}."
            else:
                reply += "\n\n⚠️ *Catatan:* API untuk mengatur izin chat ('admin_only') belum tersedia di server OpenWA Anda. Pesan error: " + str(setting_res.get('error'))
                
        send_text(chat_id, reply)
    else:
        send_text(chat_id, f"❌ Gagal membuat grup: {res.get('error', res)}")

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

def get_target_jid(parts, data):
    mentioned_jids = data.get("mentionedJidList") or data.get("mentionedJids") or []
    if mentioned_jids:
        return mentioned_jids[0]
    if len(parts) >= 3:
        return clean_number(parts[2])
    return None

def admin_add_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    target = get_target_jid(parts, data)
    if not target: return send_text(chat_id, "⚠️ Usage: *admin add <nomor>*")
    res = whatsapp.add_group_admin(chat_id, [target])
    if res.get("success"): send_text(chat_id, f"✅ Berhasil mengangkat {target.replace('@c.us','').replace('@lid','')} menjadi admin.")
    else: send_text(chat_id, f"❌ Gagal: {res.get('error')}")

def admin_remove_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    target = get_target_jid(parts, data)
    if not target: return send_text(chat_id, "⚠️ Usage: *admin remove <nomor>*")
    
    import rbac
    if rbac.is_protected(target):
        return send_text(chat_id, "🛡️ Tidak dapat melakukan aksi ini pada Super Admin atau Bot.")
        
    res = whatsapp.remove_group_admin(chat_id, [target])
    if res.get("success"): send_text(chat_id, f"✅ Berhasil menurunkan {target.replace('@c.us','').replace('@lid','')} dari admin.")
    else: send_text(chat_id, f"❌ Gagal: {res.get('error')}")

def user_add_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    target = get_target_jid(parts, data)
    if not target: return send_text(chat_id, "⚠️ Usage: *user add <nomor>*")
    res = whatsapp.add_group_participant(chat_id, [target])
    if res.get("success"): send_text(chat_id, f"✅ Berhasil menambahkan {target.replace('@c.us','').replace('@lid','')} ke grup.")
    else: send_text(chat_id, f"❌ Gagal: {res.get('error')}")

def user_kick_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    target = get_target_jid(parts, data)
    if not target: return send_text(chat_id, "⚠️ Usage: *user kick <nomor>*")
    
    import rbac
    if rbac.is_protected(target):
        return send_text(chat_id, "🛡️ Tidak dapat mengeluarkan Super Admin atau Bot.")
        
    res = whatsapp.remove_group_participant(chat_id, [target])
    if res.get("success"): send_text(chat_id, f"✅ Berhasil mengeluarkan {target.replace('@c.us','').replace('@lid','')} dari grup.")
    else: send_text(chat_id, f"❌ Gagal: {res.get('error')}")

def user_mute_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    target = get_target_jid(parts, data)
    if not target: return send_text(chat_id, "⚠️ Usage: *user mute <nomor>*")
    
    import rbac
    if rbac.is_protected(target):
        return send_text(chat_id, "🛡️ Tidak dapat membisukan Super Admin atau Bot.")
        
    storage.mute_user(chat_id, target)
    send_text(chat_id, f"🔇 Berhasil membisukan {target.replace('@c.us','').replace('@lid','')}. Pesan mereka akan dihapus otomatis (pastikan bot adalah admin).")

def user_unmute_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    target = get_target_jid(parts, data)
    if not target: return send_text(chat_id, "⚠️ Usage: *user unmute <nomor>*")
    storage.unmute_user(chat_id, target)
    send_text(chat_id, f"🔊 {target.replace('@c.us','').replace('@lid','')} telah di-unmute.")

def check_id_cmd(send_text, chat_id, data, bot_lid: str = "", bot_phone: str = ""):
    """
    Handle: check id @user

    Reads the first @mentioned user (that isn't the bot itself) from
    mentionedJidList, resolves their LID/phone JID, then sends the
    result privately to every Super Admin in ADMIN_CHAT_IDS.
    The group only sees a brief acknowledgement.
    """
    if not data.get("isGroup"):
        return send_text(chat_id, "⚠️ Perintah ini hanya bisa digunakan di dalam grup.")

    mentioned_jids = (
        data.get("mentionedJidList")
        or data.get("mentionedJids")
        or []
    )

    # Build bot JIDs to exclude from the mention list
    bot_jids = set()
    if bot_phone:
        bot_jids.add(f"{bot_phone}@c.us")
    if bot_lid:
        bot_jids.add(f"{bot_lid}@lid")
        bot_jids.add(bot_lid)          # bare LID without domain

    # Pick the first mentioned JID that isn't the bot
    target_jid = None
    for jid in mentioned_jids:
        # Also check the body for @<lid> style raw mentions
        if jid not in bot_jids and jid.split("@")[0] not in bot_jids:
            target_jid = jid
            break

    # Fallback: try to extract an @<number> mention from the raw body
    if not target_jid:
        raw_body = (data.get("body") or "").strip()
        # Find all @-mentions in body
        mentions_in_body = re.findall(r"@(\d+)", raw_body)
        for m in mentions_in_body:
            candidate = f"{m}@lid" if len(m) >= 15 else f"{m}@c.us"
            if m not in bot_jids and candidate not in bot_jids:
                target_jid = candidate
                break

    if not target_jid:
        return send_text(chat_id, "⚠️ Tidak ada user yang di-mention. Gunakan: *check id @user*")

    # Try to resolve the LID to a real @c.us number
    resolved_jid = resolve_lid_to_cus(target_jid)

    # Determine display number
    raw_number = target_jid.split("@")[0]
    resolved_number = resolved_jid.split("@")[0]

    # Compose the private report
    lines = ["🔍 *Check ID Result* (dari grup)"]
    lines.append(f"📌 Grup: `{chat_id}`")
    lines.append(f"\n👤 *User yang di-check:*")
    lines.append(f"• JID mentionedJidList : `{target_jid}`")
    if resolved_jid != target_jid:
        lines.append(f"• JID resolved (@c.us) : `{resolved_jid}`")
        lines.append(f"• Nomor HP             : `{resolved_number}`")
    else:
        lines.append(f"• Nomor / LID          : `{raw_number}`")
    report = "\n".join(lines)

    # Send report privately to each super admin
    if not ADMIN_CHAT_IDS:
        logger.warning("check_id_cmd: ADMIN_CHAT_IDS is empty, nowhere to send the report.")
        return send_text(chat_id, "⚠️ Tidak ada super admin yang dikonfigurasi (ADMIN_CHAT_IDS kosong).")

    for admin_id in ADMIN_CHAT_IDS:
        send_text(admin_id, report)
        logger.info("check_id_cmd: sent ID report for %s to admin %s", target_jid, admin_id)

    # Brief public ack — no sensitive data in group
    send_text(chat_id, f"✅ ID sudah dikirim ke super admin via PM.")
