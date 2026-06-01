"""Encrypt/decrypt short strings (API keys) for storage at rest.

Uses Fernet symmetric encryption keyed from SECRET_KEY.
"""
import base64
import hashlib
from cryptography.fernet import Fernet

from config import settings


def _fernet() -> Fernet:
    key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
