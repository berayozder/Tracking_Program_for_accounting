"""connection.py - sqlite3 connection and initialization."""

from pathlib import Path
import sqlite3
from .schema import init_db_schema
from contextlib import contextmanager

# Root-level data directory (db/ is one level below project root)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_DIR / "app.db"


def ensure_data_dir() -> None:
    """Create data dir if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    """Return a sqlite3.Connection with row_factory sqlite3.Row."""
    ensure_data_dir()
    conn = sqlite3.connect(str(DB_PATH), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn

def init_db() -> sqlite3.Connection:
    """Initialize DB schema if missing and return sqlite3.Connection."""
    conn = get_conn()
    init_db_schema(conn)
    return conn

@contextmanager
def get_cursor():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
