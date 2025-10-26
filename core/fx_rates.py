from __future__ import annotations

from datetime import datetime
from typing import Optional
import urllib.request
import json
import core.fx_cache as fx_cache


def get_or_fetch_rate(date_str: str | None) -> Optional[float]:
    """Return USD->TRY rate for date_str (YYYY-MM-DD) using DB-backed cache.

    Steps:
    - Normalize date_str (use today if None).
    - Try DB cache via db.get_cached_rate(date, 'USD', 'TRY').
    - If absent, fetch from frankfurter API and store via db.set_cached_rate.
    """
    if not date_str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
    # Try in-memory/file cache first (fast)
    try:
        cached = fx_cache.get(date_str, 'USD', 'TRY')
        if cached and float(cached) > 0:
            return float(cached)
    except Exception:
        cached = None
    # Try DB cache next for centralized/shared cache
    try:
        import db as db
        cached_db = db.get_cached_rate(date_str, 'USD', 'TRY')
        if cached_db and float(cached_db) > 0:
            # populate in-memory cache for faster subsequent lookups
            try:
                fx_cache.set_(date_str, 'USD', 'TRY', float(cached_db))
            except Exception:
                pass
            return float(cached_db)
    except Exception:
        cached_db = None

    # fetch from frankfurter
    url = f"https://api.frankfurter.app/{date_str}?from=USD&to=TRY"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TrackingApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rates = data.get("rates") or {}
            v = rates.get("TRY")
            if v:
                fv = float(v)
                # Persist into in-memory/file cache
                try:
                    fx_cache.set_(date_str, 'USD', 'TRY', fv)
                except Exception:
                    pass
                # Also persist into DB cache if available (backward compatible)
                try:
                    import db as db
                    db.set_cached_rate(date_str, 'USD', 'TRY', fv)
                except Exception:
                    pass
                return fv
    except Exception:
        return None
    return None
