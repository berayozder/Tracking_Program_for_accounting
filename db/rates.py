from .connection import get_conn
from .settings import get_base_currency
from typing import Optional

# ---------------- Currency conversion & FX cache ----------------
def _get_rate_generic(date_str: str, from_ccy: str, to_ccy: str) -> Optional[float]:
    from_ccy = (from_ccy or '').upper()
    to_ccy = (to_ccy or '').upper()
    if not from_ccy or not to_ccy:
        return None
    if from_ccy == to_ccy:
        return 1.0
    try:
        # Try local cache first
        cached = get_cached_rate(date_str, from_ccy, to_ccy)
        if cached and cached > 0:
            return cached
        # Use core.fx_rates for common USD/TRY path
        import core.fx_rates as fx_rates
        if from_ccy == 'USD' and to_ccy == 'TRY':
            r = fx_rates.get_or_fetch_rate(date_str)
            if r and r > 0:
                set_cached_rate(date_str, from_ccy, to_ccy, r)
            return r
        if from_ccy == 'TRY' and to_ccy == 'USD':
            r = fx_rates.get_or_fetch_rate(date_str)
            v = (1.0 / r) if r and r > 0 else None
            if v and v > 0:
                set_cached_rate(date_str, from_ccy, to_ccy, v)
            return v
        # Fallback: try frankfurter API
        from urllib import request
        path = f"/{date_str}?from={from_ccy}&to={to_ccy}" if date_str else f"/latest?from={from_ccy}&to={to_ccy}"
        for scheme in ("https", "http"):
            url = f"{scheme}://api.frankfurter.app{path}"
            try:
                req = request.Request(url, headers={'User-Agent': 'TrackingApp/1.0'})
                with request.urlopen(req, timeout=5.0) as resp:
                    import json as _json
                    j = _json.loads(resp.read().decode('utf-8'))
                    v = (j.get('rates') or {}).get(to_ccy)
                    if v is not None:
                        rate = float(v)
                        if rate and rate > 0:
                            set_cached_rate(date_str, from_ccy, to_ccy, rate)
                        return rate
            except Exception:
                continue
    except Exception:
        return None
    return None


def convert_amount(date_str: str, amount: float, from_ccy: str, to_ccy: str) -> Optional[float]:
    try:
        rate = _get_rate_generic(date_str, from_ccy, to_ccy)
        if rate is None or rate <= 0:
            return None
        return float(amount) * float(rate)
    except Exception:
        return None


def get_cached_rate(date_str: str, from_ccy: str, to_ccy: str) -> Optional[float]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT rate FROM fx_cache WHERE date=? AND from_ccy=? AND to_ccy=?', (date_str, from_ccy.upper(), to_ccy.upper()))
        row = cur.fetchone()
        conn.close()
        return float(row['rate']) if row and row['rate'] is not None else None
    except Exception:
        return None


def set_cached_rate(date_str: str, from_ccy: str, to_ccy: str, rate: float) -> None:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('INSERT OR REPLACE INTO fx_cache(date, from_ccy, to_ccy, rate) VALUES (?,?,?,?)',
                    (date_str, from_ccy.upper(), to_ccy.upper(), float(rate)))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_rate_to_base(date_str: str, from_ccy: str) -> Optional[float]:
    base = get_base_currency()
    return _get_rate_generic(date_str, (from_ccy or '').upper(), (base or '').upper())
