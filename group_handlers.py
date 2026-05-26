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
    target = resolve_lid_to_cus(clean_number(parts[2]))
    res = whatsapp.add_group_admin(chat_id, [target])
    if res.get("success"): send_text(chat_id, f"✅ Berhasil mengangkat {target.replace('@c.us','').replace('@lid','')} menjadi admin.")
    else: send_text(chat_id, f"❌ Gagal: {res.get('error')}")

def admin_remove_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    if len(parts) < 3: return send_text(chat_id, "⚠️ Usage: *admin remove <nomor>*")
    target = resolve_lid_to_cus(clean_number(parts[2]))
    res = whatsapp.remove_group_admin(chat_id, [target])
    if res.get("success"): send_text(chat_id, f"✅ Berhasil menurunkan {target.replace('@c.us','').replace('@lid','')} dari admin.")
    else: send_text(chat_id, f"❌ Gagal: {res.get('error')}")

def user_add_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    if len(parts) < 3: return send_text(chat_id, "⚠️ Usage: *user add <nomor>*")
    target = resolve_lid_to_cus(clean_number(parts[2]))
    res = whatsapp.add_group_participant(chat_id, [target])
    if res.get("success"): send_text(chat_id, f"✅ Berhasil menambahkan {target.replace('@c.us','').replace('@lid','')} ke grup.")
    else: send_text(chat_id, f"❌ Gagal: {res.get('error')}")

def user_kick_cmd(send_text, chat_id, raw_body, data):
    if not data.get("isGroup"): return send_text(chat_id, "⚠️ Hanya di dalam grup.")
    parts = raw_body.split()
    if len(parts) < 3: return send_text(chat_id, "⚠️ Usage: *user kick <nomor>*")
    target = resolve_lid_to_cus(clean_number(parts[2]))
    res = whatsapp.remove_group_participant(chat_id, [target])
    if res.get("success"): send_text(chat_id, f"✅ Berhasil mengeluarkan {target.replace('@c.us','').replace('@lid','')} dari grup.")
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
    send_text(chat_id, f"✅ ID info untuk @{raw_number} sudah dikirim ke super admin via PM.")
