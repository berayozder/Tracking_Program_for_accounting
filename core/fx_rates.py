from __future__ import annotations

from datetime import datetime
from typing import Optional
import urllib.request
import json


def get_or_fetch_rate(date_str: str | None) -> Optional[float]:
    """Return USD->TRY rate for date_str (YYYY-MM-DD) using DB-backed cache.

    Steps:
    - Normalize date_str (use today if None).
    - Try DB cache via db.get_cached_rate(date, 'USD', 'TRY').
    - If absent, fetch from frankfurter API and store via db.set_cached_rate.
    """
    if not date_str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
    # Try DB cache first to avoid filesystem and allow centralized cache
    try:
        import db as db
        cached = db.get_cached_rate(date_str, 'USD', 'TRY')
        if cached and float(cached) > 0:
            return float(cached)
    except Exception:
        # If DB is not available, proceed to fetch but don't fail loudly
        cached = None

    # fetch from frankfurter
    url = f"https://api.frankfurter.app/{date_str}?from=USD&to=TRY"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TrackingApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rates = data.get("rates") or {}
            v = rates.get("TRY")
            if v:
                try:
                    # Persist into DB cache if available
                    import db as db
                    db.set_cached_rate(date_str, 'USD', 'TRY', float(v))
                except Exception:
                    pass
                return float(v)
    except Exception:
        return None
    return None
