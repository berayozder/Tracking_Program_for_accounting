"""Database utility functions."""
from __future__ import annotations

from .connection import DB_PATH, get_cursor


def float_or_none(v) -> float | None:
    """Convert value to float or return None if conversion fails."""
    try:
        return float(v)
    except Exception:
        return None


def delete_database_file() -> bool:
    """Delete the database file if it exists. Returns True if deleted, False otherwise."""
    try:
        if DB_PATH.exists():
            DB_PATH.unlink()
            return True
        return False
    except Exception:
        return False


def reset_all_tables(clear_product_codes: bool = True) -> None:
    """
    Delete all records from core tables.
    
    Args:
        clear_product_codes: If True, also clear product_codes table.
    """
    with get_cursor() as (conn, cur):
        cur.execute('DELETE FROM imports')
        cur.execute('DELETE FROM inventory')
        cur.execute('DELETE FROM expenses')
        if clear_product_codes:
            cur.execute('DELETE FROM product_codes')
        conn.commit()
