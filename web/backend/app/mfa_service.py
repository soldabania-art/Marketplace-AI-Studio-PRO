import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings


def generate_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def encrypt_secret(secret: str) -> str:
    return Fernet(get_settings().mfa_encryption_key.encode()).encrypt(secret.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return Fernet(get_settings().mfa_encryption_key.encode()).decrypt(ciphertext.encode()).decode()
    except (InvalidToken, ValueError) as exc:
        raise ValueError("MFA secret cannot be decrypted") from exc


def _base32_decode(secret: str) -> bytes:
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(padded, casefold=True)


def totp_code(secret: str, at_time: int | None = None) -> str:
    counter = int(time.time() if at_time is None else at_time) // 30
    digest = hmac.new(_base32_decode(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{value:06d}"


def verify_totp(secret: str, code: str, at_time: int | None = None) -> bool:
    return matched_totp_step(secret, code, at_time) is not None


def matched_totp_step(secret: str, code: str, at_time: int | None = None) -> int | None:
    normalized = code.replace(" ", "").strip()
    if len(normalized) != 6 or not normalized.isdigit():
        return None
    now = int(time.time() if at_time is None else at_time)
    for offset in (-1, 0, 1):
        candidate_time = now + offset * 30
        if hmac.compare_digest(totp_code(secret, candidate_time), normalized):
            return candidate_time // 30
    return None


def _recovery_hash(code: str) -> str:
    normalized = code.replace("-", "").replace(" ", "").upper()
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, normalized.encode(), hashlib.sha256).hexdigest()


def generate_recovery_codes(count: int = 10) -> tuple[list[str], list[str]]:
    raw = [f"{secrets.token_hex(4)[:4]}-{secrets.token_hex(4)[:4]}".upper() for _ in range(count)]
    return raw, [_recovery_hash(code) for code in raw]


def consume_recovery_code(hashes: list[str], code: str) -> list[str] | None:
    candidate = _recovery_hash(code)
    for index, stored in enumerate(hashes or []):
        if hmac.compare_digest(stored, candidate):
            return [value for position, value in enumerate(hashes) if position != index]
    return None


def provisioning_uri(secret: str, email: str) -> str:
    issuer = "TROVENDI"
    label = quote(f"{issuer}:{email}", safe="")
    return f"otpauth://totp/{label}?secret={quote(secret)}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
