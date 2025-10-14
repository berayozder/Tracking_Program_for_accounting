from pathlib import Path
import csv
import json
from urllib import request
from typing import Optional
import os

# FX rates store: one row per date when a sale occurs
# Columns: Date, FXToTRY  (FXToTRY = TRY per 1 USD)

FX_CSV = Path(__file__).resolve().parents[1] / 'data' / 'fx_rates.csv'
FX_DEBUG = os.environ.get('FX_RATES_DEBUG', '0') in ('1', 'true', 'True', 'YES', 'yes')


def ensure_fx_csv():
    FX_CSV.parent.mkdir(parents=True, exist_ok=True)
    if not FX_CSV.exists():
        with FX_CSV.open('w', newline='') as f:
            csv.writer(f).writerow(['Date', 'FXToTRY'])


def read_fx_rows():
    ensure_fx_csv()
    with FX_CSV.open('r', newline='') as f:
        reader = csv.DictReader(f)
        return list(reader)


def read_fx_map():
    """Return mapping date->float(rate). Invalid or missing rates are skipped."""
    rows = read_fx_rows()
    out = {}
    for r in rows:
        d = (r.get('Date') or '').strip()
        v = (r.get('FXToTRY') or '').strip()
        if not d:
            continue
        try:
            out[d] = float(v)
        except Exception:
            # skip invalid number
            pass
    return out


def get_rate_for_date(date_str):
    """Get rate for a specific date (YYYY-MM-DD). Returns float or None if not found."""
    m = read_fx_map()
    return m.get(date_str)


def upsert_rate(date_str, rate):
    """Add a new row if date not present. Do not modify existing dates."""
    ensure_fx_csv()
    try:
        rate = float(rate)
    except Exception:
        raise ValueError('rate must be a number')
    with FX_CSV.open('r', newline='') as f:
        reader = csv.DictReader(f)
        existing = [r for r in reader]
        seen_dates = { (r.get('Date') or '').strip() for r in existing }
    if date_str in seen_dates:
        return False
    with FX_CSV.open('a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['Date', 'FXToTRY'])
        if FX_CSV.stat().st_size == 0:
            w.writeheader()
        w.writerow({'Date': date_str, 'FXToTRY': rate})
    return True


def set_rate(date_str: str, rate: float) -> bool:
    """Insert or replace the rate for a specific date.
    Returns True if file updated successfully.
    """
    ensure_fx_csv()
    try:
        rate = float(rate)
    except Exception:
        raise ValueError('rate must be a number')
    # Load all rows
    rows = []
    try:
        with FX_CSV.open('r', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception:
        rows = []
    seen = False
    new_rows = []
    for r in rows:
        d = (r.get('Date') or '').strip()
        if d == date_str:
            new_rows.append({'Date': date_str, 'FXToTRY': rate})
            seen = True
        else:
            new_rows.append({'Date': d, 'FXToTRY': (r.get('FXToTRY') or '').strip()})
    if not seen:
        new_rows.append({'Date': date_str, 'FXToTRY': rate})
    # Write back
    with FX_CSV.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['Date', 'FXToTRY'])
        w.writeheader()
        w.writerows(new_rows)
    return True


# ---------------- Live FX Fetching ----------------
def _http_get_json(url: str, timeout: float = 5.0):
    try:
        req = request.Request(url, headers={'User-Agent': 'TrackingApp/1.0'})
        with request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            j = json.loads(data.decode('utf-8'))
            # Debug print removed (use FX_DEBUG and logging if reinstated)
            return j
    except Exception as e:
        # Suppressed debug print for errors; return None silently
        return None


def fetch_live_rate(date_str: Optional[str] = None) -> Optional[float]:
    """Fetch USD->TRY (TRY per 1 USD) from frankfurter.app only.
    - If date_str (YYYY-MM-DD) provided, query historical for that date.
    - Otherwise, return latest rate.
    Tries HTTPS first, then HTTP as a fallback. Returns None on failure.
    """
    base = "USD"
    to = "TRY"
    paths = []
    if date_str and isinstance(date_str, str) and len(date_str) == 10:
        # historical for specific date
        paths = [f"/{date_str}?from={base}&to={to}"]
    else:
        # latest
        paths = [f"/latest?from={base}&to={to}"]

    for scheme in ("https", "http"):
        for p in paths:
            url = f"{scheme}://api.frankfurter.app{p}"
            j = _http_get_json(url)
            try:
                if j and isinstance(j, dict) and 'rates' in j:
                    v = (j.get('rates') or {}).get('TRY')
                    if v is not None:
                        return float(v)
            except Exception:
                pass
    return None


def get_or_fetch_rate(date_str: str) -> Optional[float]:
    """Prefer cached rate; if missing, fetch live and cache it."""
    r = get_rate_for_date(date_str)
    if r is not None:
        return r
    live = fetch_live_rate(date_str)
    if live is not None:
        try:
            upsert_rate(date_str, live)
        except Exception:
            pass
        return live
    return None
