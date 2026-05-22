import hashlib
import time
import random
import uuid

def generate_device_id(package_id: str = "id.co.indocyber.android.starbridges") -> str:
    """
    Generate an Android-based device ID (16 hex characters) using the specified package ID.
    This creates a deterministic-looking but unique 16-character hex string similar to Settings.Secure.ANDROID_ID
    which can be used as an IMEI/Device ID for app backends.
    """
    random_component = str(random.random()) + str(time.time())
    raw_string = f"{package_id}-{random_component}"
    
    # Android IDs are typically 16 hex characters.
    # We use md5 hash of our pseudo-random string and take the first 16 characters.
    return hashlib.md5(raw_string.encode()).hexdigest()[:16]
