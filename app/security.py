import base64
import hashlib
import hmac
import secrets
import time

from app.config import settings

COOKIE_NAME = "pocketsmart_session"
SESSION_SECONDS = 60 * 60 * 24 * 7


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return base64.urlsafe_b64encode(salt + digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        raw = base64.urlsafe_b64decode(stored.encode())
        salt, expected = raw[:16], raw[16:]
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_session(user_id: int) -> str:
    payload = f"{user_id}:{int(time.time()) + SESSION_SECONDS}:{secrets.token_urlsafe(12)}"
    signature = hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    signed = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{encoded}.{signed}"


def session_user_id(token: str | None) -> int | None:
    if not token or "." not in token:
        return None
    try:
        payload_part, signature_part = token.split(".", 1)
        payload = base64.urlsafe_b64decode(payload_part + "=" * (-len(payload_part) % 4)).decode()
        signature = base64.urlsafe_b64decode(signature_part + "=" * (-len(signature_part) % 4))
        expected = hmac.new(settings.secret_key.encode(), payload.encode(), hashlib.sha256).digest()
        user_id, expires, _nonce = payload.split(":", 2)
        if not hmac.compare_digest(signature, expected) or int(expires) < int(time.time()):
            return None
        return int(user_id)
    except (ValueError, TypeError):
        return None
