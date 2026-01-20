"""Database cryptography wrapper.

Provides encrypt_str and decrypt_str functions with graceful fallback
if core.crypto_utils is unavailable.
"""

try:
    from core.crypto_utils import encrypt_str, decrypt_str  # type: ignore
except Exception:  # pragma: no cover - fallback if module missing
    def encrypt_str(x):
        return x
    
    def decrypt_str(x):
        return x