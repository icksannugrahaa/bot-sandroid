import requests
from datetime import datetime, timedelta, timezone

from attendance_storage import save_token
from logger import log
from config import URL_VALIDASI_LOGIN, URL_TOKEN, URL_REGISTER_IMEI


class AuthClient:
    def __init__(self, alias: str, username: str, password: str, imei: str):
        self.alias = alias
        self.username = username.strip()
        self.password = password
        self.imei = imei.strip()

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "okhttp/3.14.9",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/x-www-form-urlencoded"
        })

    def login_and_get_token(self):
        # ===============================
        # 1️⃣ VALIDASI LOGIN
        # ===============================
        login_url = URL_VALIDASI_LOGIN

        log(
            f"[{self.alias}] LOGIN REQUEST -> "
            f"username={self.username}, "
            f"imei={self.imei}"
        )

        try:
            r = self.session.post(
                login_url,
                data={
                    "username": self.username,
                    "password": self.password,
                    "IMEI": self.imei
                },
                timeout=15
            )
            r.raise_for_status()
        except Exception as e:
            raise Exception(f"Login request failed: {e}")

        try:
            login_data = r.json()
        except Exception:
            raise Exception(f"Login response bukan JSON: {r.text}")

        if not login_data.get("isSucceed"):
            # pesan backend lebih informatif
            message = login_data.get("message", "Login validation failed")
            raise Exception(message)

        # ===============================
        # 2️⃣ REQUEST TOKEN
        # ===============================
        token_url = URL_TOKEN

        try:
            r = self.session.post(
                token_url,
                data={
                    "grant_type": "password",
                    "username": self.username,
                    "password": self.password,
                    "client_id": "ngAuthApp",
                    "IMEI": self.imei
                },
                headers={
                    "User-Agent": "okhttp/3.14.9",
                    "Accept-Encoding": "gzip",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=15
            )
            r.raise_for_status()
        except Exception as e:
            raise Exception(f"Token request failed: {e}")

        try:
            token = r.json()
        except Exception:
            raise Exception(f"Token response bukan JSON: {r.text}")

        if "access_token" not in token:
            raise Exception(f"Token tidak valid: {token}")

        # ===============================
        # 3️⃣ HITUNG EXPIRED TIME
        # ===============================
        expires_in = token.get("expires_in")
        if not isinstance(expires_in, int):
            raise Exception(f"expires_in tidak valid: {token}")

        token["expires_at"] = (
            datetime.now(timezone.utc) +
            timedelta(seconds=expires_in)
        ).isoformat()

        # ===============================
        # 4️⃣ TAMBAHKAN DATA YANG DIPERLUKAN ATTENDANCE
        # ===============================
        # Pastikan key ini ada, karena dipakai di attendance.py
        token["loginName"] = token.get("loginName") or self.username
        token["LocationID"] = token.get("LocationID")
        token["Location"] = token.get("Location")


        if not token["LocationID"] or not token["Location"]:
            log(f"[{self.alias}] WARNING: Location data tidak lengkap")

        # ===============================
        # 5️⃣ SIMPAN TOKEN (MULTI-USER)
        # ===============================
        save_token(self.alias, token)

        log(f"[{self.alias}] Login & token berhasil disimpan")
        return True

    def register_imei(self):
        # ===============================
        # REGISTER IMEI
        # ===============================
        register_url = URL_REGISTER_IMEI

        log(
            f"[{self.alias}] REGISTER IMEI REQUEST -> "
            f"username={self.username}, "
            f"imei={self.imei}"
        )

        try:
            r = self.session.post(
                register_url,
                data={
                    "username": self.username,
                    "password": self.password,
                    "IMEI": self.imei
                },
                timeout=15
            )
            r.raise_for_status()
        except Exception as e:
            raise Exception(f"Register IMEI request failed: {e}")

        try:
            register_data = r.json()
        except Exception:
            raise Exception(f"Register IMEI response bukan JSON: {r.text}")

        if not register_data.get("isSucceed"):
            message = register_data.get("message", "Register IMEI failed")
            raise Exception(message)

        log(f"[{self.alias}] Register IMEI berhasil")
        return True
