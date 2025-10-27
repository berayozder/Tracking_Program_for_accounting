from typing import Optional
from .connection import get_conn, get_cursor

# ---------------- Settings helpers ----------------
def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        with get_cursor() as (conn, cur):
            cur.execute('SELECT value FROM settings WHERE key=?', (key,))
            row = cur.fetchone()
        return row['value'] if row else default
    except Exception:
        return default


def set_setting(key: str, value: Optional[str]) -> None:
    """Persist a simple key/value app setting into the settings table.

    Uses INSERT OR REPLACE so callers can set or update values safely.
    """
    try:
        with get_cursor() as (conn, cur):
            cur.execute('INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)', (key, None if value is None else str(value)))
            conn.commit()
    except Exception:
        # Silent failure is acceptable for non-critical settings
        pass


def get_base_currency() -> str:
    return (get_setting('base_currency', 'USD') or 'USD').upper()


def get_default_import_currency() -> str:
    return (get_setting('default_import_currency', 'USD') or 'USD').upper()


def get_default_sale_currency() -> str:
    return (get_setting('default_sale_currency', 'TRY') or 'TRY').upper()


def get_default_expense_currency() -> str:
    return (get_setting('default_expense_currency', get_base_currency()) or get_base_currency()).upper()

