from __future__ import annotations

import base64
import os
try:
    from cryptography.fernet import Fernet  # type: ignore
except ImportError:
    Fernet = None

_KEY_ENV = "TRACKING_APP_SECRET_KEY"


def _get_key() -> bytes:
    k = os.environ.get(_KEY_ENV)
    if k:
        try:
            return k.encode("utf-8")
        except Exception:
            pass
    # fallback deterministic key (NOT for production secrets)
    return base64.urlsafe_b64encode(b"tracking-app-demo-key-32bytes!!")


def _cipher() -> Fernet:
    if Fernet is None:
        raise ImportError(
            "cryptography library is required for encryption. "
            "Install it with: pip install cryptography"
        )
    return Fernet(_get_key())


def encrypt_str(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _cipher().encrypt(value.encode("utf-8")).decode("utf-8")
    except Exception:
        return value


def decrypt_str(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _cipher().decrypt(value.encode("utf-8")).decode("utf-8")
    except Exception:
        return value
