"""
Encryption helpers for storing user-supplied AI provider API keys at rest.

Keys are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) using a server-side
secret (AI_KEY_ENCRYPTION_KEY) that is never sent to the frontend, never logged,
and never returned by any API response. Only ciphertext and a masked preview
(last 4 characters) are persisted in the database.
"""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _get_fernet() -> Fernet:
    key = getattr(settings, 'AI_KEY_ENCRYPTION_KEY', None)
    if not key:
        raise ImproperlyConfigured(
            "AI_KEY_ENCRYPTION_KEY is not configured. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\" "
            "and set it as an environment variable."
        )
    return Fernet(key.encode('utf-8') if isinstance(key, str) else key)


def encrypt_api_key(raw_key: str) -> bytes:
    """Encrypt a plaintext API key for storage. Callers must never log `raw_key`."""
    return _get_fernet().encrypt(raw_key.strip().encode('utf-8'))


def decrypt_api_key(encrypted_key: bytes) -> str:
    """Decrypt a stored API key. Raises ValueError if the ciphertext is invalid."""
    try:
        return _get_fernet().decrypt(bytes(encrypted_key)).decode('utf-8')
    except InvalidToken as exc:
        raise ValueError("Stored API key could not be decrypted") from exc
