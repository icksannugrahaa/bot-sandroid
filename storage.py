"""
Encrypted SQLite storage for user credentials.
Passwords and TOTP secrets are encrypted at rest using Fernet (AES-128-CBC).
"""

import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Database path
# ──────────────────────────────────────────────────────────────
_DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_data.db")
DB_PATH = os.getenv("DB_PATH", _DEFAULT_DB_PATH)


def _ensure_encryption_key() -> str:
    """
    Ensure a valid ENCRYPTION_KEY exists.
    If missing or invalid, auto-generate one and append it to the .env file.
    """
    key = os.getenv("ENCRYPTION_KEY", "").strip()

    if key:
        # Validate the existing key
        try:
            Fernet(key.encode())
            return key
        except (ValueError, Exception):
            logger.warning("⚠️ ENCRYPTION_KEY in .env is invalid — generating a new one")

    # Generate a new key
    new_key = Fernet.generate_key().decode()
    logger.info("🔑 Generated new ENCRYPTION_KEY: %s", new_key)

    # Save it to .env file
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    with open(env_path, "a") as f:
        f.write(f"\nENCRYPTION_KEY={new_key}\n")
    logger.info("💾 ENCRYPTION_KEY saved to %s", env_path)

    # Also set it in the current process
    os.environ["ENCRYPTION_KEY"] = new_key
    return new_key


def _get_fernet() -> Fernet:
    """Get a Fernet instance using the master encryption key."""
    key = _ensure_encryption_key()
    return Fernet(key.encode())


def encrypt(plaintext: str) -> str:
    """Encrypt a string and return the token as a UTF-8 string."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """Decrypt a Fernet token back to the original string."""
    f = _get_fernet()
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("❌ Failed to decrypt data — ENCRYPTION_KEY may have changed")
        raise


# ──────────────────────────────────────────────────────────────
# Database initialization
# ──────────────────────────────────────────────────────────────
def init_db() -> None:
    """Create the users table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                phone_number    TEXT PRIMARY KEY,
                encrypted_pass  TEXT,
                encrypted_totp  TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_users (
                alias TEXT PRIMARY KEY,
                username TEXT,
                password TEXT,
                imei TEXT,
                active BOOLEAN,
                automation BOOLEAN,
                location_pool TEXT,
                checkin_timerange TEXT,
                checkout_timerange TEXT,
                notes TEXT,
                owner_chat_id TEXT
            )
        """)
        try:
            conn.execute("ALTER TABLE attendance_users ADD COLUMN owner_chat_id TEXT")
        except sqlite3.OperationalError:
            pass # column already exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_locations (
                name TEXT PRIMARY KEY,
                lat REAL,
                lng REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_tokens (
                alias TEXT PRIMARY KEY,
                data TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_status (
                alias TEXT PRIMARY KEY,
                data TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rbac_permissions (
                feature TEXT,
                role TEXT,
                is_active BOOLEAN,
                PRIMARY KEY (feature, role)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rbac_user_roles (
                chat_id TEXT PRIMARY KEY,
                role TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS global_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS muted_users (
                group_id TEXT,
                user_id TEXT,
                PRIMARY KEY (group_id, user_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_users (
                jid           TEXT PRIMARY KEY,
                lid           TEXT,
                phone         TEXT,
                pushname      TEXT,
                profile_pic   TEXT,
                registered_at TEXT NOT NULL
            )
        """)
        conn.commit()
        logger.info("📦 Database initialized at %s", DB_PATH)
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# CRUD operations
# ──────────────────────────────────────────────────────────────
def set_password(phone_number: str, password: str) -> None:
    """Encrypt and store (or update) the password for a phone number."""
    now = datetime.now(timezone.utc).isoformat()
    encrypted = encrypt(password)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO users (phone_number, encrypted_pass, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(phone_number)
            DO UPDATE SET encrypted_pass = ?, updated_at = ?
        """, (phone_number, encrypted, now, now, encrypted, now))
        conn.commit()
        logger.info("🔐 Password saved for %s", phone_number)
    finally:
        conn.close()


def set_totp_secret(phone_number: str, totp_secret: str) -> None:
    """Encrypt and store (or update) the TOTP secret for a phone number."""
    now = datetime.now(timezone.utc).isoformat()
    encrypted = encrypt(totp_secret)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO users (phone_number, encrypted_totp, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(phone_number)
            DO UPDATE SET encrypted_totp = ?, updated_at = ?
        """, (phone_number, encrypted, now, now, encrypted, now))
        conn.commit()
        logger.info("🔐 TOTP secret saved for %s", phone_number)
    finally:
        conn.close()


def get_credentials(phone_number: str) -> dict | None:
    """
    Retrieve and decrypt the credentials for a phone number.
    Returns {"password": str, "totp_secret": str} or None if not found.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT encrypted_pass, encrypted_totp FROM users WHERE phone_number = ?",
            (phone_number,)
        ).fetchone()

        if not row:
            return None

        result = {}
        result["password"] = decrypt(row[0]) if row[0] else None
        result["totp_secret"] = decrypt(row[1]) if row[1] else None
        return result
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# Attendance Storage (Users and Locations)
# ──────────────────────────────────────────────────────────────
def get_attendance_users() -> dict:
    """Return a dictionary of all attendance users."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM attendance_users").fetchall()
        users = {}
        for r in rows:
            users[r["alias"]] = {
                "username": r["username"],
                "password": r["password"],
                "imei": r["imei"],
                "active": bool(r["active"]),
                "automation": bool(r["automation"]),
                "location_pool": r["location_pool"],
                "checkin_timerange": r["checkin_timerange"],
                "checkout_timerange": r["checkout_timerange"],
                "notes": r["notes"],
                "owner_chat_id": r["owner_chat_id"] if "owner_chat_id" in r.keys() else None
            }
        return users
    finally:
        conn.close()


def get_attendance_user(alias: str) -> dict | None:
    """Return a specific attendance user."""
    return get_attendance_users().get(alias)


def upsert_attendance_user(alias: str, data: dict) -> None:
    """Insert or update an attendance user."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO attendance_users (
                alias, username, password, imei, active, automation, 
                location_pool, checkin_timerange, checkout_timerange, notes, owner_chat_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(alias) DO UPDATE SET
                username=excluded.username,
                password=excluded.password,
                imei=excluded.imei,
                active=excluded.active,
                automation=excluded.automation,
                location_pool=excluded.location_pool,
                checkin_timerange=excluded.checkin_timerange,
                checkout_timerange=excluded.checkout_timerange,
                notes=excluded.notes,
                owner_chat_id=excluded.owner_chat_id
        """, (
            alias,
            data.get("username"),
            data.get("password"),
            data.get("imei"),
            data.get("active", True),
            data.get("automation", False),
            data.get("location_pool", "kanpus"),
            data.get("checkin_timerange"),
            data.get("checkout_timerange"),
            data.get("notes"),
            data.get("owner_chat_id")
        ))
        conn.commit()
    finally:
        conn.close()


def get_attendance_locations() -> dict:
    """Return a dictionary of all locations {name: (lat, lng)}."""
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT name, lat, lng FROM attendance_locations").fetchall()
        locations = {}
        for r in rows:
            locations[r[0]] = (r[1], r[2])
        return locations
    finally:
        conn.close()


def upsert_attendance_location(name: str, lat: float, lng: float) -> None:
    """Insert or update a location."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO attendance_locations (name, lat, lng)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                lat=excluded.lat,
                lng=excluded.lng
        """, (name.lower(), lat, lng))
        conn.commit()
    finally:
        conn.close()


def get_attendance_token(alias: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT data FROM attendance_tokens WHERE alias = ?", (alias,)).fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return None
    finally:
        conn.close()

def save_attendance_token(alias: str, data: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO attendance_tokens (alias, data) VALUES (?, ?)
            ON CONFLICT(alias) DO UPDATE SET data=excluded.data
        """, (alias, json.dumps(data)))
        conn.commit()
    finally:
        conn.close()

def get_attendance_status(alias: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT data FROM attendance_status WHERE alias = ?", (alias,)).fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return {}
    finally:
        conn.close()

def save_attendance_status(alias: str, data: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO attendance_status (alias, data) VALUES (?, ?)
            ON CONFLICT(alias) DO UPDATE SET data=excluded.data
        """, (alias, json.dumps(data)))
        conn.commit()
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# RBAC Storage (Roles & Permissions)
# ──────────────────────────────────────────────────────────────

def get_all_rbac_permissions() -> list[dict]:
    """Returns a list of dicts: [{'feature': '...', 'role': '...', 'is_active': True}]"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT feature, role, is_active FROM rbac_permissions").fetchall()
        return [{"feature": r["feature"], "role": r["role"], "is_active": bool(r["is_active"])} for r in rows]
    finally:
        conn.close()

def set_rbac_permissions(permissions: list[dict]) -> None:
    """Clears existing permissions and sets the new ones."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM rbac_permissions")
        for p in permissions:
            conn.execute(
                "INSERT INTO rbac_permissions (feature, role, is_active) VALUES (?, ?, ?)",
                (p["feature"], p["role"], int(p["is_active"]))
            )
        conn.commit()
    finally:
        conn.close()

def get_rbac_user_roles() -> dict[str, str]:
    """Returns {chat_id: role}"""
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT chat_id, role FROM rbac_user_roles").fetchall()
        return {r[0]: r[1] for r in rows}
    finally:
        conn.close()

def get_user_role(chat_id: str) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT role FROM rbac_user_roles WHERE chat_id = ?", (chat_id,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()

def set_user_role(chat_id: str, role: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO rbac_user_roles (chat_id, role) VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET role=excluded.role
        """, (chat_id, role))
        conn.commit()
    finally:
        conn.close()

def delete_user_role(chat_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM rbac_user_roles WHERE chat_id = ?", (chat_id,))
        conn.commit()
    finally:
        conn.close()

# ──────────────────────────────────────────────────────────────
# Global Settings Storage
# ──────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = None) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT value FROM global_settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default
    except sqlite3.OperationalError:
        # Table might not exist yet if init_db() hasn't run
        return default
    finally:
        conn.close()

def set_setting(key: str, value: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            INSERT INTO global_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, value))
        conn.commit()
    finally:
        conn.close()

# ──────────────────────────────────────────────────────────────
# Muted Users Storage
# ──────────────────────────────────────────────────────────────

def get_muted_users(group_id: str) -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT user_id FROM muted_users WHERE group_id = ?", (group_id,)).fetchall()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

def is_muted(group_id: str, user_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT 1 FROM muted_users WHERE group_id = ? AND user_id = ?", (group_id, user_id)).fetchone()
        return bool(row)
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()

def mute_user(group_id: str, user_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("INSERT OR IGNORE INTO muted_users (group_id, user_id) VALUES (?, ?)", (group_id, user_id))
        conn.commit()
    finally:
        conn.close()

def unmute_user(group_id: str, user_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM muted_users WHERE group_id = ? AND user_id = ?", (group_id, user_id))
        conn.commit()
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# Bot User Registry
# ──────────────────────────────────────────────────────────────

def register_bot_user(
    jid: str,
    lid: str | None,
    phone: str | None,
    pushname: str | None,
    profile_pic: str | None,
) -> bool:
    """
    Register a new bot user.  Returns True if inserted (new user),
    False if the JID already existed (INSERT OR IGNORE → no update).
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO bot_users
                (jid, lid, phone, pushname, profile_pic, registered_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (jid, lid, phone, pushname, profile_pic, now)
        )
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def get_bot_user(jid: str) -> dict | None:
    """Return the bot_user row for the given JID, or None."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM bot_users WHERE jid = ?", (jid,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_bot_user_by_phone(phone: str) -> dict | None:
    """Return the bot_user row matching a raw phone number, or None."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM bot_users WHERE phone = ?", (phone,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_bot_users() -> list[dict]:
    """Return all registered bot users."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM bot_users ORDER BY registered_at").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
