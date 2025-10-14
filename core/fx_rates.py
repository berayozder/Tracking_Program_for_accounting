from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional
import csv
import urllib.request
import json

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_CSV = DATA_DIR / "fx_rates.csv"


def _load_cache() -> dict[tuple[str, str], float]:
    cache: dict[tuple[str, str], float] = {}
    if CACHE_CSV.exists():
        try:
            with CACHE_CSV.open() as f:
                r = csv.reader(f)
                next(r, None)
                for row in r:
                    if len(row) >= 3:
                        cache[(row[0], row[1])] = float(row[2])
        except Exception:
            pass
    return cache


def _save_cache(cache: dict[tuple[str, str], float]):
    try:
        with CACHE_CSV.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "pair", "rate"])
            for (d, pair), rate in sorted(cache.items()):
                w.writerow([d, pair, rate])
    except Exception:
        pass


def get_or_fetch_rate(date_str: str | None) -> Optional[float]:
    if not date_str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
    pair = "USDTRY"
    cache = _load_cache()
    key = (date_str, pair)
    if key in cache:
        return cache[key]
    # fetch from frankfurter
    url = f"https://api.frankfurter.app/{date_str}?from=USD&to=TRY"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TrackingApp/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            rates = data.get("rates") or {}
            v = rates.get("TRY")
            if v:
                cache[key] = float(v)
                _save_cache(cache)
                return float(v)
    except Exception:
        return None
    return None
