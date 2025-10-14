"""Lightweight encryption helpers for optional at-rest protection.

If the 'cryptography' package is available, we use Fernet for authenticated
encryption and store the key at data/secret.key. If not available, we fall
back to passthrough (no encryption). Callers should treat encryption as best
effort unless the environment guarantees the dependency is installed.

Public API:
  - encrypt_str(plaintext: str) -> str
  - decrypt_str(token: str) -> str

We prefix encrypted payloads with 'enc::' so readers can detect and decrypt.
If the prefix is missing, the value is returned as-is for backward compat.
"""
from pathlib import Path
from typing import Optional

FERNET_AVAILABLE = False
try:
    from cryptography.fernet import Fernet  # type: ignore
    FERNET_AVAILABLE = True
except Exception:
    FERNET_AVAILABLE = False


KEY_PATH = Path(__file__).resolve().parents[1] / 'data' / 'secret.key'


def _load_or_create_key() -> Optional[bytes]:
    if not FERNET_AVAILABLE:
        return None
    try:
        KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if KEY_PATH.exists():
            return KEY_PATH.read_bytes()
        key = Fernet.generate_key()
        KEY_PATH.write_bytes(key)
        return key
    except Exception:
        return None


def _get_fernet() -> Optional["Fernet"]:
    if not FERNET_AVAILABLE:
        return None
    key = _load_or_create_key()
    if not key:
        return None
    try:
        return Fernet(key)
    except Exception:
        return None


def encrypt_str(plaintext: Optional[str]) -> Optional[str]:
    if plaintext is None:
        return None
    s = str(plaintext)
    if not s:
        return s
    f = _get_fernet()
    if not f:
        # No encryption available; return plaintext for compatibility
        return s
    try:
        token = f.encrypt(s.encode('utf-8'))
        return 'enc::' + token.decode('utf-8')
    except Exception:
        return s


def decrypt_str(token: Optional[str]) -> Optional[str]:
    if token is None:
        return None
    s = str(token)
    if not s:
        return s
    if not s.startswith('enc::'):
        return s
    f = _get_fernet()
    if not f:
        # Can't decrypt without cryptography; return raw token
        return s
    try:
        payload = s[len('enc::'):].encode('utf-8')
        pt = f.decrypt(payload)
        return pt.decode('utf-8')
    except Exception:
        # On failure, return the raw string so UI at least shows something
        return s
