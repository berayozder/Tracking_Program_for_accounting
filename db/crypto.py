

try:
    # Optional encryption helpers (now sibling package instead of relative)
    from core.crypto_utils import encrypt_str, decrypt_str  # type: ignore
    print("[DEBUG] Using encrypt_str from core.crypto_utils:", encrypt_str)
except Exception as e:  # pragma: no cover - fallback if module missing
    print(f"[DEBUG] Failed to import encrypt_str from core.crypto_utils: {e}")
    def encrypt_str(x):
        return x
    def decrypt_str(x):
        return x
print("[DEBUG] Final encrypt_str is:", encrypt_str)