

try:
    # Optional encryption helpers (now sibling package instead of relative)
    from core.crypto_utils import encrypt_str, decrypt_str  # type: ignore
except Exception:  # pragma: no cover - fallback if module missing
    def encrypt_str(x):
        return x
    def decrypt_str(x):
        return x