"""Tiny in-memory FX cache with optional JSON persistence.

Used for UI suggestions (Hybrid approach). Does not replace per-transaction
storage of the applied rate (fx_to_base) which remains authoritative.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

try:
    from db.connection import DATA_DIR
except Exception:
    DATA_DIR = Path('.') / 'data'

_CACHE: dict[str, tuple[float, float]] = {}  # key -> (rate, ts)
_CACHE_FILE = DATA_DIR / 'fx_cache.json'
# Default TTL: 7 days
_TTL = 7 * 24 * 60 * 60


def _key(date_str: str, from_ccy: str, to_ccy: str) -> str:
    return f"{(date_str or '').strip()}|{(from_ccy or '').upper()}|{(to_ccy or '').upper()}"


def get(date_str: str, from_ccy: str, to_ccy: str) -> Optional[float]:
    k = _key(date_str, from_ccy, to_ccy)
    v = _CACHE.get(k)
    if not v:
        return None
    rate, ts = v
    if _TTL and (time.time() - ts) > _TTL:
        try:
            del _CACHE[k]
        except Exception:
            pass
        return None
    return float(rate)


def set_(date_str: str, from_ccy: str, to_ccy: str, rate: float) -> None:
    try:
        k = _key(date_str, from_ccy, to_ccy)
        _CACHE[k] = (float(rate), time.time())
    except Exception:
        pass


def load_from_disk() -> None:
    try:
        if not _CACHE_FILE.exists():
            return
        txt = _CACHE_FILE.read_text(encoding='utf-8')
        data = json.loads(txt)
        now = time.time()
        for k, v in (data or {}).items():
            try:
                rate = float(v.get('rate'))
                ts = float(v.get('ts', now))
                _CACHE[k] = (rate, ts)
            except Exception:
                continue
    except Exception:
        pass


def save_to_disk() -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        out = {}
        for k, (rate, ts) in _CACHE.items():
            out[k] = {'rate': rate, 'ts': ts}
        _CACHE_FILE.write_text(json.dumps(out, indent=2), encoding='utf-8')
    except Exception:
        pass


# Load on import if possible
try:
    load_from_disk()
except Exception:
    pass


# Register atexit save so cached suggestions persist across restarts
try:
    import atexit

    atexit.register(save_to_disk)
except Exception:
    pass
