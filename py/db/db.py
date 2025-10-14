import sqlite3
from pathlib import Path
import csv
from datetime import datetime
import os
import hashlib
import hmac
from typing import Optional, Dict, Any

try:
    # Optional encryption helpers
    from ..core.crypto_utils import encrypt_str, decrypt_str  # type: ignore
except Exception:  # pragma: no cover - fallback if module missing
    def encrypt_str(x):
        return x
    def decrypt_str(x):
        return x

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "app.db"
IMPORTS_CSV = DATA_DIR / "imports.csv"
INVENTORY_CSV = DATA_DIR / "inventory.csv"
SUPPLIERS_CSV = DATA_DIR / "suppliers.csv"
RETURNS_CSV = DATA_DIR / "returns.csv"


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- Settings helpers ----------------
def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT value FROM settings WHERE key=?', (key,))
        row = cur.fetchone()
        return row['value'] if row else default
    except Exception:
        return default


def set_setting(key: str, value: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, value))
    conn.commit()


def get_base_currency() -> str:
    return (get_setting('base_currency', 'USD') or 'USD').upper()


def get_default_import_currency() -> str:
    return (get_setting('default_import_currency', 'USD') or 'USD').upper()


def get_default_sale_currency() -> str:
    return (get_setting('default_sale_currency', 'TRY') or 'TRY').upper()


def get_default_expense_currency() -> str:
    return (get_setting('default_expense_currency', get_base_currency()) or get_base_currency()).upper()


# ---------------- Currency conversion ----------------
def _get_rate_generic(date_str: str, from_ccy: str, to_ccy: str) -> Optional[float]:
    """Return rate (to_ccy per 1 from_ccy) using frankfurter when possible.
    Currently optimized for USD<->TRY flows. If same currency, return 1.0.
    """
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
        # Import placed rates assume USD base previously; reuse fx_rates for USD->TRY
        import py.core.fx_rates as fx_rates  # local import to avoid circular at module load
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
        # Fallback via frankfurter direct call for other pairs
        # Minimal inline fetch to avoid adding new dependencies
        from urllib import request
        base = from_ccy
        to = to_ccy
        path = f"/{date_str}?from={base}&to={to}" if date_str else f"/latest?from={base}&to={to}"
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
    except Exception:
        pass


def get_rate_to_base(date_str: str, from_ccy: str) -> Optional[float]:
    base = get_base_currency()
    return _get_rate_generic(date_str, (from_ccy or '').upper(), (base or '').upper())


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # imports table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS imports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        ordered_price REAL,
        quantity REAL,
        supplier TEXT,
        supplier_id TEXT,
        notes TEXT,
        category TEXT,
        subcategory TEXT,
        currency TEXT DEFAULT 'TRY'
    )
    ''')
    # app settings (key/value)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')
    # fx cache for arbitrary pairs
    cur.execute('''
    CREATE TABLE IF NOT EXISTS fx_cache (
        date TEXT,
        from_ccy TEXT,
        to_ccy TEXT,
        rate REAL,
        PRIMARY KEY (date, from_ccy, to_ccy)
    )
    ''')
    # Migration: add supplier_id if missing in existing DBs
    try:
        cur.execute('PRAGMA table_info(imports)')
        cols = [row['name'] for row in cur.fetchall()]
        if 'supplier_id' not in cols:
            cur.execute('ALTER TABLE imports ADD COLUMN supplier_id TEXT')
        if 'currency' not in cols:
            cur.execute("ALTER TABLE imports ADD COLUMN currency TEXT DEFAULT 'TRY'")
        # Drop fx_to_try column if present by table-rebuild (SQLite safe migration)
        if 'fx_to_try' in cols:
            # Build new table without fx_to_try and copy data
            cur.execute('''CREATE TABLE IF NOT EXISTS imports_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                ordered_price REAL,
                quantity REAL,
                supplier TEXT,
                supplier_id TEXT,
                notes TEXT,
                category TEXT,
                subcategory TEXT,
                currency TEXT DEFAULT 'TRY'
            )''')
            # Copy data from old to new (exclude fx_to_try)
            cur.execute('''INSERT INTO imports_new (id, date, ordered_price, quantity, supplier, supplier_id, notes, category, subcategory, currency)
                           SELECT id, date, ordered_price, quantity, supplier, supplier_id, notes, category, subcategory, currency FROM imports''')
            cur.execute('DROP TABLE imports')
            cur.execute('ALTER TABLE imports_new RENAME TO imports')
    except Exception:
        pass
    # USERS (for login/roles)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password_hash BLOB,
        salt BLOB,
        role TEXT DEFAULT 'user',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    # AUDIT LOG
    cur.execute('''
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT DEFAULT CURRENT_TIMESTAMP,
        user TEXT,
        action TEXT,
        entity TEXT,
        ref_id TEXT,
        details TEXT
    )
    ''')
    # inventory table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        subcategory TEXT,
        quantity REAL,
        last_updated TEXT
    )
    ''')
    # expenses table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        amount REAL,
        is_import_related INTEGER,
        import_id INTEGER,
        category TEXT,
        notes TEXT,
        document_path TEXT,
        currency TEXT
    )
    ''')
    # Add document_path column if upgrading from older schema
    # expense_import_links: many-to-many links between expenses and imports
    cur.execute('''
    CREATE TABLE IF NOT EXISTS expense_import_links (
        expense_id INTEGER,
        import_id INTEGER,
        PRIMARY KEY (expense_id, import_id),
        FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE,
        FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
    )
    ''')
    try:
        cur.execute('PRAGMA table_info(expenses)')
        cols = [row['name'] for row in cur.fetchall()]
        if 'document_path' not in cols:
            cur.execute('ALTER TABLE expenses ADD COLUMN document_path TEXT')
        if 'currency' not in cols:
            cur.execute('ALTER TABLE expenses ADD COLUMN currency TEXT')
    except Exception:
        pass
    # product codes table (for generating product IDs)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS product_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        subcategory TEXT,
        cat_code TEXT,
        sub_code TEXT,
        next_serial INTEGER
    )
    ''')
    # Ensure one row per (category, subcategory)
    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_product_codes_cat_sub ON product_codes(category, subcategory)')

    # BATCH TRACKING SYSTEM
    # import_batches: Each import creates a batch with remaining quantity for FIFO allocation
    cur.execute('''
    CREATE TABLE IF NOT EXISTS import_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        import_id INTEGER,
        batch_date TEXT,
        category TEXT,
        subcategory TEXT,
        original_quantity REAL,
        remaining_quantity REAL,
        unit_cost REAL,
        supplier TEXT,
        batch_notes TEXT,
        currency TEXT DEFAULT 'TRY',
        fx_to_try REAL DEFAULT 1.0,
        unit_cost_orig REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
    )
    ''')
    # Migration for import_batches extra columns
    try:
        cur.execute('PRAGMA table_info(import_batches)')
        bcols = [row['name'] for row in cur.fetchall()]
        if 'currency' not in bcols:
            cur.execute("ALTER TABLE import_batches ADD COLUMN currency TEXT DEFAULT 'TRY'")
        if 'fx_to_try' not in bcols:
            cur.execute('ALTER TABLE import_batches ADD COLUMN fx_to_try REAL DEFAULT 1.0')
        if 'unit_cost_orig' not in bcols:
            cur.execute('ALTER TABLE import_batches ADD COLUMN unit_cost_orig REAL')
    except Exception:
        pass
    
    # sale_batch_allocations: Links each sale item to specific batch(es) for cost tracking
    cur.execute('''
    CREATE TABLE IF NOT EXISTS sale_batch_allocations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT,
        sale_date TEXT,
        category TEXT,
        subcategory TEXT,
        batch_id INTEGER,
        quantity_from_batch REAL,
        unit_cost REAL,
        unit_sale_price REAL,
        profit_per_unit REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (batch_id) REFERENCES import_batches(id) ON DELETE CASCADE
    )
    ''')
    
    # Indexes for efficient batch queries
    cur.execute('CREATE INDEX IF NOT EXISTS idx_import_batches_category ON import_batches(category, subcategory)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_import_batches_date ON import_batches(batch_date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sale_allocations_product ON sale_batch_allocations(product_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sale_allocations_batch ON sale_batch_allocations(batch_id)')

    # Triggers to enforce code uniqueness and consistency
    # 1) A cat_code belongs to a single category (no reuse across different categories)
    # 2) A category is consistently mapped to a single cat_code
    # 3) Within a category, sub_code is unique across subcategories
    # 4) A (category, subcategory) is consistently mapped to a single sub_code
    cur.execute('''
    CREATE TRIGGER IF NOT EXISTS trg_product_codes_bi
    BEFORE INSERT ON product_codes
    BEGIN
        -- cat_code not used by other categories
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.cat_code = NEW.cat_code AND p.category <> NEW.category
        ) THEN RAISE(ABORT, 'cat_code already used by different category') END;

        -- category must keep same cat_code
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.category = NEW.category AND p.cat_code <> NEW.cat_code
        ) THEN RAISE(ABORT, 'category already mapped to different cat_code') END;

        -- sub_code unique within the category across different subcategories
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.category = NEW.category AND p.sub_code = NEW.sub_code AND p.subcategory <> NEW.subcategory
        ) THEN RAISE(ABORT, 'sub_code already used by different subcategory in this category') END;

        -- subcategory must keep same sub_code
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.category = NEW.category AND p.subcategory = NEW.subcategory AND p.sub_code <> NEW.sub_code
        ) THEN RAISE(ABORT, 'subcategory already mapped to different sub_code') END;
    END;
    ''')

    cur.execute('''
    CREATE TRIGGER IF NOT EXISTS trg_product_codes_bu
    BEFORE UPDATE ON product_codes
    BEGIN
        -- cat_code not used by other categories
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.cat_code = NEW.cat_code AND p.category <> NEW.category
        ) THEN RAISE(ABORT, 'cat_code already used by different category') END;

        -- category must keep same cat_code (exclude self)
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.category = NEW.category AND p.id <> NEW.id AND p.cat_code <> NEW.cat_code
        ) THEN RAISE(ABORT, 'category already mapped to different cat_code') END;

        -- sub_code unique within the category across different subcategories (exclude self)
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.category = NEW.category AND p.id <> NEW.id AND p.sub_code = NEW.sub_code AND p.subcategory <> NEW.subcategory
        ) THEN RAISE(ABORT, 'sub_code already used by different subcategory in this category') END;

        -- subcategory must keep same sub_code (exclude self)
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.category = NEW.category AND p.id <> NEW.id AND p.subcategory = NEW.subcategory AND p.sub_code <> NEW.sub_code
        ) THEN RAISE(ABORT, 'subcategory already mapped to different sub_code') END;
    END;
    ''')
    conn.commit()

    return conn


# ------------------------ SECURITY: USERS & AUTH ------------------------
_CURRENT_USER: Dict[str, Any] = {"username": None, "role": None}


def _pbkdf2_hash(password: str, salt: bytes, iterations: int = 120_000) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)


def create_user(username: str, password: str, role: str = 'user') -> bool:
    if not username or not password:
        return False
    conn = get_conn()
    cur = conn.cursor()
    salt = os.urandom(16)
    pwd_hash = _pbkdf2_hash(password, salt)
    try:
        cur.execute('INSERT INTO users (username, password_hash, salt, role) VALUES (?,?,?,?)',
                    (username.strip(), pwd_hash, salt, role.strip() or 'user'))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def users_exist() -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) as c FROM users')
    row = cur.fetchone()
    conn.close()
    return bool(row and (row['c'] or 0) > 0)


def verify_user(username: str, password: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT username, password_hash, salt, role FROM users WHERE username=?', (username.strip(),))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    salt = row['salt']
    expected = row['password_hash']
    test = _pbkdf2_hash(password, salt)
    if not hmac.compare_digest(expected, test):
        return False
    # set current user
    _CURRENT_USER['username'] = row['username']
    _CURRENT_USER['role'] = row['role'] or 'user'
    return True


def set_current_user(username: Optional[str], role: Optional[str]):
    _CURRENT_USER['username'] = username
    _CURRENT_USER['role'] = role


def get_current_user() -> Dict[str, Optional[str]]:
    return {"username": _CURRENT_USER.get('username'), "role": _CURRENT_USER.get('role')}


def require_admin(action: str, entity: str, ref_id: str = ''):
    role = (_CURRENT_USER.get('role') or 'user').lower()
    if role != 'admin':
        raise PermissionError('Admin privileges required')


def write_audit(action: str, entity: str, ref_id: str = '', details: str = ''):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('INSERT INTO audit_log (user, action, entity, ref_id, details) VALUES (?,?,?,?,?)',
                    (_CURRENT_USER.get('username'), action, entity, str(ref_id or ''), details))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_audit_logs(start_date: str = None, end_date: str = None, user: str = None,
                   action: str = None, entity: str = None, q: str = None, limit: int = 1000):
    """Return filtered audit log rows as list of dicts. Dates in YYYY-MM-DD (inclusive)."""
    conn = get_conn()
    cur = conn.cursor()
    where = []
    params = []
    if start_date:
        where.append("date(ts) >= date(?)")
        params.append(start_date)
    if end_date:
        where.append("date(ts) <= date(?)")
        params.append(end_date)
    if user:
        where.append("user = ?")
        params.append(user)
    if action:
        where.append("action = ?")
        params.append(action)
    if entity:
        where.append("entity = ?")
        params.append(entity)
    if q:
        where.append("(details LIKE ? OR ref_id LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])
    sql = "SELECT id, ts, user, action, entity, ref_id, details FROM audit_log"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY datetime(ts) DESC LIMIT ?"
    params.append(limit)
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_audit_distinct(field: str):
    if field not in ("user", "action", "entity"):
        return []
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT DISTINCT {field} FROM audit_log WHERE {field} IS NOT NULL AND {field} <> '' ORDER BY {field}")
    vals = [r[0] for r in cur.fetchall()]
    conn.close()
    return vals


##


def float_or_none(v):
    try:
        return float(v)
    except Exception:
        return None


def add_import(date, ordered_price, quantity, supplier, notes, category, subcategory, currency: str = 'TRY'):
    conn = get_conn()
    cur = conn.cursor()
    # Optional supplier linkage via suppliers.csv
    supplier_name = (supplier or '').strip()
    supplier_id = None
    if supplier_name:
        try:
            supplier_id = find_or_create_supplier(supplier_name)
        except Exception:
            supplier_id = None

    enc_notes = encrypt_str(notes)
    # Determine currency with default from settings if not specified
    cur_ccy = (currency or get_default_import_currency() or 'USD').upper()
    cur.execute('''INSERT INTO imports (date, ordered_price, quantity, supplier, supplier_id, notes, category, subcategory, currency)
                VALUES (?,?,?,?,?,?,?,?,?)''', (date, ordered_price, quantity, supplier_name, supplier_id, enc_notes, category, subcategory, cur_ccy))
    
    import_id = cur.lastrowid
    conn.commit()
    
    # Create batch for this import for FIFO tracking (unit_cost stored in TRY)
    # Default TRY cost to equal USD price (rate=1.0); USD analysis uses unit_cost_orig
    # Compute unit costs: store unit_cost in original ccy (for historical), and unit_cost_orig in base currency
    unit_cost_in_import_ccy = float(ordered_price or 0.0)
    base_ccy = get_base_currency()
    unit_cost_in_base = unit_cost_in_import_ccy
    if (cur_ccy or '').upper() != (base_ccy or '').upper():
        converted = convert_amount(date, unit_cost_in_import_ccy, cur_ccy, base_ccy)
        unit_cost_in_base = converted if converted is not None else unit_cost_in_base
    create_import_batch(import_id, date, category, subcategory, quantity, unit_cost_in_import_ccy, supplier, notes, cur_ccy, 1.0, unit_cost_in_base)
    
    # update inventory
    update_inventory(category, subcategory, quantity, conn)
    conn.close()
    write_audit('add', 'import', str(import_id), f"qty={quantity}; price={ordered_price}")

    # CSV append removed (exports handled by explicit backfill script)


def get_imports(limit=500):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, date, ordered_price, quantity, supplier, notes, category, subcategory, currency FROM imports ORDER BY id DESC LIMIT ?', (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    # Decrypt notes if encrypted
    for r in rows:
        r['notes'] = decrypt_str(r.get('notes'))
    return rows


def edit_import(import_id, date, ordered_price, quantity, supplier, notes, category, subcategory, currency: str = None):
    conn = get_conn()
    cur = conn.cursor()
    # Resolve optional supplier link
    supplier_name = (supplier or '').strip()
    supplier_id = None
    if supplier_name:
        try:
            supplier_id = find_or_create_supplier(supplier_name)
        except Exception:
            supplier_id = None

    # Fetch existing for defaults
    cur.execute('SELECT currency FROM imports WHERE id=?', (import_id,))
    row = cur.fetchone()
    cur_currency = (row['currency'] if row else 'TRY')
    new_currency = currency or cur_currency or 'TRY'

    # Update import record
    enc_notes = encrypt_str(notes)
    cur.execute('''UPDATE imports SET date=?, ordered_price=?, quantity=?, supplier=?, supplier_id=?, notes=?, category=?, subcategory=?, currency=? WHERE id=?''',
                (date, ordered_price, quantity, supplier_name, supplier_id, enc_notes, category, subcategory, new_currency, import_id))
    
    # Update corresponding batch record
    unit_cost_in_import_ccy = float(ordered_price or 0.0)
    base_ccy = get_base_currency()
    new_currency_u = (new_currency or '').upper()
    unit_cost_in_base = unit_cost_in_import_ccy
    if (new_currency_u or '') != (base_ccy or '').upper():
        converted = convert_amount(date, unit_cost_in_import_ccy, new_currency_u, base_ccy)
        unit_cost_in_base = converted if converted is not None else unit_cost_in_base
    cur.execute('''UPDATE import_batches 
                   SET batch_date=?, category=?, subcategory=?, unit_cost=?, supplier=?, batch_notes=?, 
                       original_quantity=?, remaining_quantity=remaining_quantity+(?)-(original_quantity),
                       currency=?, unit_cost_orig=?
                   WHERE import_id=?''',
                (date, category, subcategory, unit_cost_in_import_ccy, supplier, notes, quantity, quantity, new_currency, unit_cost_in_base, import_id))
    
    conn.commit()
    # rebuild inventory to remain consistent
    rebuild_inventory_from_imports(conn)
    conn.close()
    write_audit('edit', 'import', str(import_id), f"qty={quantity}; price={ordered_price}")


def delete_import(import_id):
    require_admin('delete', 'import', str(import_id))
    conn = get_conn()
    cur = conn.cursor()
    
    # Delete associated batch (CASCADE will handle sale allocations)
    cur.execute('DELETE FROM import_batches WHERE import_id=?', (import_id,))
    
    # Delete import record
    cur.execute('DELETE FROM imports WHERE id=?', (import_id,))
    conn.commit()
    rebuild_inventory_from_imports(conn)
    conn.close()
    write_audit('delete', 'import', str(import_id))


def get_inventory():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT category, subcategory, quantity, last_updated FROM inventory ORDER BY category, subcategory')
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def update_inventory(category, subcategory, quantity, conn=None):
    close_conn = False
    if conn is None:
        conn = get_conn()
        close_conn = True
    cur = conn.cursor()
    # find existing
    cur.execute('SELECT id, quantity FROM inventory WHERE category=? AND subcategory=?', (category or '', subcategory or ''))
    row = cur.fetchone()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        q = float(quantity or 0)
    except Exception:
        q = 0.0

    if row:
        new_q = (row['quantity'] or 0) + q
        cur.execute('UPDATE inventory SET quantity=?, last_updated=? WHERE id=?', (new_q, now, row['id']))
    else:
        cur.execute('INSERT INTO inventory (category, subcategory, quantity, last_updated) VALUES (?,?,?,?)', (category or '', subcategory or '', q, now))
    conn.commit()
    if close_conn:
        conn.close()


def rebuild_inventory_from_imports(conn=None):
    close_conn = False
    if conn is None:
        conn = get_conn()
        close_conn = True
    cur = conn.cursor()
    cur.execute('SELECT category, subcategory, SUM(quantity) as qty FROM imports GROUP BY category, subcategory')
    rows = cur.fetchall()
    # overwrite inventory table
    cur.execute('DELETE FROM inventory')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for r in rows:
        cur.execute('INSERT INTO inventory (category, subcategory, quantity, last_updated) VALUES (?,?,?,?)', (r['category'] or '', r['subcategory'] or '', r['qty'] or 0, now))
    conn.commit()
    if close_conn:
        conn.close()


def add_expense(date, amount, is_import_related=False, import_id=None, category=None, notes=None, document_path=None, import_ids=None, currency: Optional[str] = None):
    """Add an expense, optionally linking to multiple imports via expense_import_links.
    - import_ids: list of import IDs (int or str) to link. If provided, the first will be stored in expenses.import_id for compatibility.
    - import_id: single link; used if import_ids not provided.
    """
    conn = get_conn()
    cur = conn.cursor()
    # Normalize import_ids
    ids = []
    if import_ids:
        for v in import_ids:
            try:
                ids.append(int(v))
            except Exception:
                pass
        ids = list(dict.fromkeys(ids))  # unique preserve order
    first_id = None
    if ids:
        first_id = ids[0]
    elif import_id:
        try:
            first_id = int(import_id)
            ids = [first_id]
        except Exception:
            first_id = None

    enc_notes = encrypt_str(notes)
    exp_ccy = (currency or get_default_expense_currency() or get_base_currency()).upper()
    cur.execute('''INSERT INTO expenses (date, amount, is_import_related, import_id, category, notes, document_path, currency)
                VALUES (?,?,?,?,?,?,?,?)''', (date, amount, 1 if is_import_related else 0, first_id, category, enc_notes, document_path, exp_ccy))
    expense_id = cur.lastrowid
    # Create links
    try:
        for iid in ids:
            cur.execute('INSERT OR IGNORE INTO expense_import_links (expense_id, import_id) VALUES (?,?)', (expense_id, iid))
    except Exception:
        pass
    conn.commit()
    conn.close()
    write_audit('add', 'expense', str(expense_id), f"amount={amount}")


def get_expenses(limit=500):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, date, amount, is_import_related, import_id, category, notes, document_path, currency FROM expenses ORDER BY id DESC LIMIT ?', (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    for r in rows:
        r['notes'] = decrypt_str(r.get('notes'))
    return rows


def edit_expense(expense_id, date, amount, is_import_related=False, import_id=None, category=None, notes=None, document_path=None, import_ids=None, currency: Optional[str] = None):
    conn = get_conn()
    cur = conn.cursor()
    # Determine primary import_id
    ids = []
    if import_ids:
        for v in import_ids:
            try:
                ids.append(int(v))
            except Exception:
                pass
        ids = list(dict.fromkeys(ids))
    first_id = None
    if ids:
        first_id = ids[0]
    elif import_id:
        try:
            first_id = int(import_id)
            ids = [first_id]
        except Exception:
            first_id = None
    enc_notes = encrypt_str(notes)
    exp_ccy = (currency or get_default_expense_currency() or get_base_currency()).upper()
    cur.execute('''UPDATE expenses SET date=?, amount=?, is_import_related=?, import_id=?, category=?, notes=?, document_path=?, currency=? WHERE id=?''',
                (date, amount, 1 if is_import_related else 0, first_id, category, enc_notes, document_path, exp_ccy, expense_id))
    # Update links
    try:
        cur.execute('DELETE FROM expense_import_links WHERE expense_id=?', (expense_id,))
        for iid in ids:
            cur.execute('INSERT OR IGNORE INTO expense_import_links (expense_id, import_id) VALUES (?,?)', (expense_id, iid))
    except Exception:
        pass
    conn.commit()
    conn.close()
    write_audit('edit', 'expense', str(expense_id), f"amount={amount}")

def get_expense_import_links(expense_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT import_id FROM expense_import_links WHERE expense_id=? ORDER BY import_id', (expense_id,))
    rows = [r['import_id'] for r in cur.fetchall()]
    conn.close()
    return rows


def delete_expense(expense_id):
    require_admin('delete', 'expense', str(expense_id))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM expenses WHERE id=?', (expense_id,))
    conn.commit()
    conn.close()
    write_audit('delete', 'expense', str(expense_id))


# --- Product code mapping helpers ---
def get_product_code(category, subcategory):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT category, subcategory, cat_code, sub_code, next_serial FROM product_codes WHERE category=? AND subcategory=?', (category or '', subcategory or ''))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def set_product_code(category, subcategory, cat_code, sub_code, next_serial=1):
    # Normalize codes to 3-digit zero-padded strings
    cat_code = str(cat_code).strip().zfill(3)
    sub_code = str(sub_code).strip().zfill(3)
    try:
        ns = int(next_serial)
        if ns < 1:
            ns = 1
    except Exception:
        ns = 1
    conn = get_conn()
    cur = conn.cursor()
    # Python-side validations for clearer error messages (mirrors DB triggers)
    # 1) cat_code can only belong to one category
    cur.execute('SELECT DISTINCT category FROM product_codes WHERE cat_code=?', (cat_code,))
    rows = [r['category'] for r in cur.fetchall()]
    if rows and any((c or '') != (category or '') for c in rows):
        conn.close()
        raise ValueError(f"cat_code {cat_code} already used by a different category")

    # 2) category must keep same cat_code if already present
    cur.execute('SELECT DISTINCT cat_code FROM product_codes WHERE category=?', (category or '',))
    codes = [r['cat_code'] for r in cur.fetchall()]
    codes = [c for c in codes if c]
    if codes and any(c != cat_code for c in codes):
        conn.close()
        raise ValueError(f"Category '{category}' is already mapped to a different cat_code ({codes[0]})")

    # 3) sub_code unique within category across different subcategories
    cur.execute('SELECT subcategory FROM product_codes WHERE category=? AND sub_code=?', (category or '', sub_code))
    owner_subs = [r['subcategory'] for r in cur.fetchall()]
    if owner_subs and any((s or '') != (subcategory or '') for s in owner_subs):
        conn.close()
        raise ValueError(f"sub_code {sub_code} already used by a different subcategory in '{category}'")

    # 4) subcategory must keep same sub_code
    cur.execute('SELECT sub_code FROM product_codes WHERE category=? AND subcategory=?', (category or '', subcategory or ''))
    subs_codes = [r['sub_code'] for r in cur.fetchall()]
    subs_codes = [c for c in subs_codes if c]
    if subs_codes and any(c != sub_code for c in subs_codes):
        conn.close()
        raise ValueError(f"Subcategory '{subcategory}' is already mapped to a different sub_code ({subs_codes[0]})")
    cur.execute('SELECT id FROM product_codes WHERE category=? AND subcategory=?', (category or '', subcategory or ''))
    row = cur.fetchone()
    if row:
        cur.execute('UPDATE product_codes SET cat_code=?, sub_code=?, next_serial=? WHERE id=?', (cat_code, sub_code, ns, row['id']))
    else:
        cur.execute('INSERT INTO product_codes (category, subcategory, cat_code, sub_code, next_serial) VALUES (?,?,?,?,?)', (category or '', subcategory or '', cat_code, sub_code, ns))
    conn.commit()
    conn.close()


def get_cat_code_for_category(category: str) -> Optional[str]:
    """Return the cat_code for a given category if it exists, else None.
    By design (enforced by triggers), a category maps to a single cat_code.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('SELECT DISTINCT cat_code FROM product_codes WHERE category=? AND cat_code IS NOT NULL AND cat_code <> ""', (category or '',))
        row = cur.fetchone()
        return (row['cat_code'] if row and row['cat_code'] else None)
    except Exception:
        return None
    finally:
        conn.close()

def generate_product_ids(category, subcategory, count, year_prefix=None):
    """Generate a list of product IDs for the given count and advance the serial.
    Format: <yy:2><cat_code:3><sub_code:3><serial:4>
    Returns list of strings; returns empty list if mapping doesn't exist.
    """
    try:
        c = int(count)
    except Exception:
        c = 0
    if c <= 0:
        return []

    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, cat_code, sub_code, next_serial FROM product_codes WHERE category=? AND subcategory=?', (category or '', subcategory or ''))
    row = cur.fetchone()
    if not row:
        conn.close()
        return []
    cat_code = (row['cat_code'] or '').zfill(3)
    sub_code = (row['sub_code'] or '').zfill(3)
    try:
        start = int(row['next_serial'] or 1)
    except Exception:
        start = 1
    ids = []
    # Determine 2-digit year prefix
    if year_prefix:
        yy = str(year_prefix)[-2:]
    else:
        yy = datetime.now().strftime('%y')
    for i in range(start, start + c):
        ids.append(f"{yy}{cat_code}{sub_code}{str(i).zfill(4)}")
    # advance serial
    cur.execute('UPDATE product_codes SET next_serial=? WHERE id=?', (start + c, row['id']))
    conn.commit()
    conn.close()
    return ids


def get_all_product_codes():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT category, subcategory, cat_code, sub_code, next_serial FROM product_codes ORDER BY category, subcategory')
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
    return {'total_sales': 0, 'total_revenue': 0.0, 'sales_count': 0, 'recent_sales': []}


# =====================================================================================
# SUPPLIER MANAGEMENT (CSV-backed, optional)
# =====================================================================================

def ensure_suppliers_csv():
    """Ensure suppliers.csv exists with proper headers."""
    from pathlib import Path
    SUPPLIERS_CSV.parent.mkdir(parents=True, exist_ok=True)
    desired_headers = ['supplier_id', 'name', 'email', 'phone', 'address', 'payment_terms', 'notes', 'created_date']

    if not SUPPLIERS_CSV.exists():
        with SUPPLIERS_CSV.open('w', newline='') as f:
            import csv
            csv.writer(f).writerow(desired_headers)
        return

    # Non-destructive header migration
    try:
        with SUPPLIERS_CSV.open('r', newline='') as f:
            import csv
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            with SUPPLIERS_CSV.open('w', newline='') as f:
                csv.writer(f).writerow(desired_headers)
            return

        header = rows[0]
        if header == desired_headers:
            return

        # Map existing rows to new header
        data = rows[1:]
        mapped = []
        for r in data:
            rowd = {header[i]: r[i] if i < len(r) else '' for i in range(len(header))}
            mapped.append({
                'supplier_id': rowd.get('supplier_id', ''),
                'name': rowd.get('name', ''),
                'email': rowd.get('email', ''),
                'phone': rowd.get('phone', ''),
                'address': rowd.get('address', ''),
                'payment_terms': rowd.get('payment_terms', ''),
                'notes': rowd.get('notes', ''),
                'created_date': rowd.get('created_date', ''),
            })

        with SUPPLIERS_CSV.open('w', newline='') as f:
            import csv
            w = csv.DictWriter(f, fieldnames=desired_headers)
            w.writeheader()
            w.writerows(mapped)
    except Exception:
        pass


def read_suppliers():
    ensure_suppliers_csv()
    if not SUPPLIERS_CSV.exists():
        return []
    with SUPPLIERS_CSV.open('r', newline='') as f:
        import csv
        return list(csv.DictReader(f))


def write_suppliers(suppliers):
    ensure_suppliers_csv()
    with SUPPLIERS_CSV.open('w', newline='') as f:
        import csv
        fieldnames = ['supplier_id', 'name', 'email', 'phone', 'address', 'payment_terms', 'notes', 'created_date']
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(suppliers)


def get_next_supplier_id():
    try:
        suppliers = read_suppliers()
        max_num = 0
        for s in suppliers:
            sid = (s.get('supplier_id', '') or '').strip()
            if sid.startswith('SUP'):
                try:
                    num = int(sid[3:])
                    if num > max_num:
                        max_num = num
                except Exception:
                    continue
        return f"SUP{max_num + 1:03d}"
    except Exception:
        return "SUP001"


def add_supplier(name, email='', phone='', address='', payment_terms='', notes=''):
    ensure_suppliers_csv()
    supplier_id = get_next_supplier_id()
    created_date = datetime.now().strftime('%Y-%m-%d')
    with SUPPLIERS_CSV.open('a', newline='') as f:
        import csv
        w = csv.DictWriter(f, fieldnames=['supplier_id', 'name', 'email', 'phone', 'address', 'payment_terms', 'notes', 'created_date'])
        w.writerow({
            'supplier_id': supplier_id,
            'name': (name or '').strip(),
            'email': (email or '').strip(),
            'phone': (phone or '').strip(),
            'address': (address or '').strip(),
            'payment_terms': (payment_terms or '').strip(),
            'notes': (notes or '').strip(),
            'created_date': created_date,
        })
    return supplier_id


def find_supplier_by_name(name):
    if not name:
        return None
    suppliers = read_suppliers()
    n = name.strip().lower()
    for s in suppliers:
        if (s.get('name', '') or '').strip().lower() == n:
            return s
    return None


def find_or_create_supplier(name):
    if not name or not name.strip():
        return None
    s = find_supplier_by_name(name)
    if s:
        return s.get('supplier_id')
    return add_supplier(name=name)


def edit_supplier(supplier_id, name=None, email=None, phone=None, address=None, payment_terms=None, notes=None):
    updated = False
    suppliers = read_suppliers()
    for i, s in enumerate(suppliers):
        if (s.get('supplier_id', '') or '').strip() == (supplier_id or '').strip():
            s.update({
                'name': (name if name is not None else s.get('name', '')),
                'email': (email if email is not None else s.get('email', '')),
                'phone': (phone if phone is not None else s.get('phone', '')),
                'address': (address if address is not None else s.get('address', '')),
                'payment_terms': (payment_terms if payment_terms is not None else s.get('payment_terms', '')),
                'notes': (notes if notes is not None else s.get('notes', '')),
            })
            suppliers[i] = s
            updated = True
            break
    if updated:
        write_suppliers(suppliers)
    return updated


def delete_supplier(supplier_id):
    suppliers = read_suppliers()
    new_list = [s for s in suppliers if (s.get('supplier_id', '') or '').strip() != (supplier_id or '').strip()]
    if len(new_list) != len(suppliers):
        write_suppliers(new_list)
        return True
    return False


def get_supplier_purchases_summary(supplier_id):
    """Aggregate imports for a supplier: total purchases (ordered_price*quantity), import count, last purchase date."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('''SELECT COUNT(*) as cnt, COALESCE(SUM(ordered_price * quantity), 0) as total, MAX(date) as last_date
                       FROM imports WHERE supplier_id = ?''', (supplier_id,))
        row = cur.fetchone()
        conn.close()
        return {
            'import_count': int(row['cnt'] or 0) if row else 0,
            'total_purchases': float(row['total'] or 0.0) if row else 0.0,
            'last_purchase': row['last_date'] if row else None
        }
    except Exception:
        return {'import_count': 0, 'total_purchases': 0.0, 'last_purchase': None}


def get_supplier_name_suggestions():
    try:
        names = [(s.get('name', '') or '').strip() for s in read_suppliers()]
        return sorted({n for n in names if n})
    except Exception:
        return []

# =====================================================================================
# MONTHLY / YEARLY ANALYTICS HELPERS
# =====================================================================================

def get_monthly_sales_profit(year: int):
    """Return dict keyed by YYYY-MM with revenue, cogs, gross_profit, items_sold.
    Refunds are subtracted from revenue and items; if Restock=1, we also reverse COGS for 1 unit per return.
    All amounts are assumed already in base currency when recorded (unit_sale_price/unit_cost in base).
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT strftime('%Y-%m', sale_date) as ym,
               SUM(COALESCE(unit_sale_price,0) * COALESCE(quantity_from_batch,0)) as revenue,
               SUM(COALESCE(unit_cost,0) * COALESCE(quantity_from_batch,0)) as cogs,
               SUM((COALESCE(unit_sale_price,0) - COALESCE(unit_cost,0)) * COALESCE(quantity_from_batch,0)) as gross_profit,
               SUM(COALESCE(quantity_from_batch,0)) as items_sold
        FROM sale_batch_allocations
        WHERE strftime('%Y', sale_date) = ?
        GROUP BY ym
        ORDER BY ym
    ''', (str(year),))
    rows = cur.fetchall()
    conn.close()
    result = {}
    for r in rows:
        k = r['ym']
        result[k] = {
            'revenue': float(r['revenue'] or 0.0),
            'cogs': float(r['cogs'] or 0.0),
            'gross_profit': float(r['gross_profit'] or 0.0),
            'items_sold': float(r['items_sold'] or 0.0),
        }
    # Integrate refunds (CSV-based)
    try:
        # Returns CSV header: ReturnDate, ProductID, SaleDate, Category, Subcategory, UnitPrice, SellingPrice, Platform, RefundAmount, Restock, Reason, ReturnDocPath
        if RETURNS_CSV.exists():
            import csv as _csv
            with RETURNS_CSV.open('r', newline='') as _f:
                rdr = _csv.DictReader(_f)
                for rr in rdr:
                    try:
                        rd = (rr.get('ReturnDate') or '').strip()
                        ym = rd[:7] if rd else None
                        if not ym or not (str(year) == ym[:4]):
                            continue
                        refund_amt = float(rr.get('RefundAmount') or 0)
                        restock = str(rr.get('Restock') or '0').strip()
                        restock_flag = 1 if restock in ('1','true','True','YES','yes') else 0
                        pid = rr.get('ProductID')
                        # Subtract refund from revenue and 1 from items
                        bucket = result.setdefault(ym, {'revenue': 0.0, 'cogs': 0.0, 'gross_profit': 0.0, 'items_sold': 0.0})
                        bucket['revenue'] -= refund_amt
                        bucket['items_sold'] -= 1.0
                        # If restocked, reverse COGS using exact allocations for this product
                        if restock_flag and pid:
                            try:
                                # Compute exact total cogs and total qty to get per-unit average for this product
                                conn2 = get_conn()
                                cur2 = conn2.cursor()
                                cur2.execute('''
                                    SELECT 
                                        SUM(COALESCE(sba.quantity_from_batch,0)) AS tq,
                                        SUM(COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_orig, ib.unit_cost, 0) * COALESCE(sba.quantity_from_batch,0)) AS tc
                                    FROM sale_batch_allocations sba
                                    LEFT JOIN import_batches ib ON sba.batch_id = ib.id
                                    WHERE sba.product_id = ?
                                ''', (pid,))
                                rowc = cur2.fetchone()
                                conn2.close()
                                tq = float(rowc['tq'] or 0.0) if rowc else 0.0
                                tc = float(rowc['tc'] or 0.0) if rowc else 0.0
                                per_unit = (tc / tq) if tq > 0 else 0.0
                                bucket['cogs'] -= per_unit
                            except Exception:
                                pass
                    except Exception:
                        pass
    except Exception:
        pass
    # Recompute gross_profit after adjustments
    for k, v in result.items():
        v['gross_profit'] = float(v.get('revenue', 0.0)) - float(v.get('cogs', 0.0))
    return result


def get_monthly_imports_value(year: int):
    """Return dict keyed by YYYY-MM with imports_value in base currency."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT date, strftime('%Y-%m', date) as ym, ordered_price, quantity, COALESCE(currency,'') as currency
        FROM imports
        WHERE strftime('%Y', date) = ?
        ORDER BY date
    ''', (str(year),))
    rows = cur.fetchall()
    conn.close()
    totals = {}
    base = get_base_currency()
    for r in rows:
        ym = r['ym']
        amt = float(r['ordered_price'] or 0.0) * float(r['quantity'] or 0.0)
        from_ccy = (r['currency'] or get_default_import_currency() or base).upper()
        date_str = r['date']
        try:
            conv = convert_amount(date_str, amt, from_ccy, base)
            val = conv if conv is not None else amt if from_ccy == base else 0.0
        except Exception:
            val = amt if from_ccy == base else 0.0
        totals[ym] = totals.get(ym, 0.0) + float(val or 0.0)
    return totals


def get_monthly_expenses(year: int):
    """Return dict keyed by YYYY-MM with expenses_total in base currency."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT date, strftime('%Y-%m', date) as ym, COALESCE(amount,0) as amount, COALESCE(currency,'') as currency
        FROM expenses
        WHERE strftime('%Y', date) = ?
        ORDER BY date
    ''', (str(year),))
    rows = cur.fetchall()
    conn.close()
    totals = {}
    base = get_base_currency()
    for r in rows:
        ym = r['ym']
        amt = float(r['amount'] or 0.0)
        from_ccy = (r['currency'] or base).upper()
        date_str = r['date']
        try:
            conv = convert_amount(date_str, amt, from_ccy, base)
            val = conv if conv is not None else amt if from_ccy == base else 0.0
        except Exception:
            val = amt if from_ccy == base else 0.0
        totals[ym] = totals.get(ym, 0.0) + float(val or 0.0)
    return totals


def get_yearly_sales_profit():
    """Return dict keyed by YYYY with revenue, cogs, gross_profit, items_sold.
    Refunds are subtracted from revenue and items; if Restock=1, we also reverse COGS using last known allocation unit_cost for the product.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT strftime('%Y', sale_date) as y,
               SUM(COALESCE(unit_sale_price,0) * COALESCE(quantity_from_batch,0)) as revenue,
               SUM(COALESCE(unit_cost,0) * COALESCE(quantity_from_batch,0)) as cogs,
               SUM((COALESCE(unit_sale_price,0) - COALESCE(unit_cost,0)) * COALESCE(quantity_from_batch,0)) as gross_profit,
               SUM(COALESCE(quantity_from_batch,0)) as items_sold
        FROM sale_batch_allocations
        GROUP BY y
        ORDER BY y
    ''')
    rows = cur.fetchall()
    conn.close()
    base_res = {r['y']: {
        'revenue': float(r['revenue'] or 0.0),
        'cogs': float(r['cogs'] or 0.0),
        'gross_profit': float(r['gross_profit'] or 0.0),
        'items_sold': float(r['items_sold'] or 0.0),
    } for r in rows}
    # Integrate refunds
    try:
        if RETURNS_CSV.exists():
            import csv as _csv
            with RETURNS_CSV.open('r', newline='') as _f:
                rdr = _csv.DictReader(_f)
                for rr in rdr:
                    try:
                        rd = (rr.get('ReturnDate') or '').strip()
                        y = rd[:4] if rd else None
                        if not y:
                            continue
                        refund_amt = float(rr.get('RefundAmount') or 0)
                        restock = str(rr.get('Restock') or '0').strip()
                        restock_flag = 1 if restock in ('1','true','True','YES','yes') else 0
                        pid = rr.get('ProductID')
                        bucket = base_res.setdefault(y, {'revenue': 0.0, 'cogs': 0.0, 'gross_profit': 0.0, 'items_sold': 0.0})
                        bucket['revenue'] -= refund_amt
                        bucket['items_sold'] -= 1.0
                        if restock_flag and pid:
                            try:
                                conn2 = get_conn()
                                cur2 = conn2.cursor()
                                cur2.execute('''
                                    SELECT 
                                        SUM(COALESCE(sba.quantity_from_batch,0)) AS tq,
                                        SUM(COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_orig, ib.unit_cost, 0) * COALESCE(sba.quantity_from_batch,0)) AS tc
                                    FROM sale_batch_allocations sba
                                    LEFT JOIN import_batches ib ON sba.batch_id = ib.id
                                    WHERE sba.product_id = ?
                                ''', (pid,))
                                rowc = cur2.fetchone()
                                conn2.close()
                                tq = float(rowc['tq'] or 0.0) if rowc else 0.0
                                tc = float(rowc['tc'] or 0.0) if rowc else 0.0
                                per_unit = (tc / tq) if tq > 0 else 0.0
                                bucket['cogs'] -= per_unit
                            except Exception:
                                pass
                    except Exception:
                        pass
    except Exception:
        pass
    for y, v in base_res.items():
        v['gross_profit'] = float(v.get('revenue', 0.0)) - float(v.get('cogs', 0.0))
    return base_res


def get_yearly_expenses():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT date, strftime('%Y', date) as y, COALESCE(amount,0) as amount, COALESCE(currency,'') as currency
        FROM expenses
        ORDER BY date
    ''')
    rows = cur.fetchall()
    conn.close()
    totals = {}
    base = get_base_currency()
    for r in rows:
        y = r['y']
        amt = float(r['amount'] or 0.0)
        from_ccy = (r['currency'] or base).upper()
        date_str = r['date']
        try:
            conv = convert_amount(date_str, amt, from_ccy, base)
            val = conv if conv is not None else amt if from_ccy == base else 0.0
        except Exception:
            val = amt if from_ccy == base else 0.0
        totals[y] = totals.get(y, 0.0) + float(val or 0.0)
    return totals


def get_monthly_return_impact(year: int):
    """Return dict keyed by YYYY-MM with returns_refunds, returns_cogs_reversed, items_returned.
    Refunds are taken from returns.csv; COGS reversed computed as one per-unit average cost for returned ProductID when Restock=1.
    """
    out = {}
    try:
        if not RETURNS_CSV.exists():
            return out
        import csv as _csv
        with RETURNS_CSV.open('r', newline='') as _f:
            rdr = _csv.DictReader(_f)
            for rr in rdr:
                rd = (rr.get('ReturnDate') or '').strip()
                if not rd or rd[:4] != str(year):
                    continue
                ym = rd[:7]
                bucket = out.setdefault(ym, {'returns_refunds': 0.0, 'returns_cogs_reversed': 0.0, 'items_returned': 0.0})
                try:
                    refund_amt = float(rr.get('RefundAmount') or 0)
                except Exception:
                    refund_amt = 0.0
                bucket['returns_refunds'] += refund_amt
                bucket['items_returned'] += 1.0
                restock = str(rr.get('Restock') or '0').strip()
                if restock in ('1','true','True','YES','yes'):
                    pid = rr.get('ProductID')
                    if pid:
                        # compute per-unit average allocation cost for this product
                        try:
                            conn2 = get_conn()
                            cur2 = conn2.cursor()
                            cur2.execute('''
                                SELECT 
                                    SUM(COALESCE(sba.quantity_from_batch,0)) AS tq,
                                    SUM(COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_orig, ib.unit_cost, 0) * COALESCE(sba.quantity_from_batch,0)) AS tc
                                FROM sale_batch_allocations sba
                                LEFT JOIN import_batches ib ON sba.batch_id = ib.id
                                WHERE sba.product_id = ?
                            ''', (pid,))
                            rowc = cur2.fetchone()
                            conn2.close()
                            tq = float(rowc['tq'] or 0.0) if rowc else 0.0
                            tc = float(rowc['tc'] or 0.0) if rowc else 0.0
                            per_unit = (tc / tq) if tq > 0 else 0.0
                            bucket['returns_cogs_reversed'] += per_unit
                        except Exception:
                            pass
    except Exception:
        return out
    return out


def get_yearly_return_impact():
    """Return dict keyed by YYYY with returns_refunds, returns_cogs_reversed, items_returned."""
    out = {}
    try:
        if not RETURNS_CSV.exists():
            return out
        import csv as _csv
        with RETURNS_CSV.open('r', newline='') as _f:
            rdr = _csv.DictReader(_f)
            for rr in rdr:
                rd = (rr.get('ReturnDate') or '').strip()
                if not rd:
                    continue
                y = rd[:4]
                bucket = out.setdefault(y, {'returns_refunds': 0.0, 'returns_cogs_reversed': 0.0, 'items_returned': 0.0})
                try:
                    refund_amt = float(rr.get('RefundAmount') or 0)
                except Exception:
                    refund_amt = 0.0
                bucket['returns_refunds'] += refund_amt
                bucket['items_returned'] += 1.0
                restock = str(rr.get('Restock') or '0').strip()
                if restock in ('1','true','True','YES','yes'):
                    pid = rr.get('ProductID')
                    if pid:
                        try:
                            conn2 = get_conn()
                            cur2 = conn2.cursor()
                            cur2.execute('''
                                SELECT 
                                    SUM(COALESCE(sba.quantity_from_batch,0)) AS tq,
                                    SUM(COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_orig, ib.unit_cost, 0) * COALESCE(sba.quantity_from_batch,0)) AS tc
                                FROM sale_batch_allocations sba
                                LEFT JOIN import_batches ib ON sba.batch_id = ib.id
                                WHERE sba.product_id = ?
                            ''', (pid,))
                            rowc = cur2.fetchone()
                            conn2.close()
                            tq = float(rowc['tq'] or 0.0) if rowc else 0.0
                            tc = float(rowc['tc'] or 0.0) if rowc else 0.0
                            per_unit = (tc / tq) if tq > 0 else 0.0
                            bucket['returns_cogs_reversed'] += per_unit
                        except Exception:
                            pass
    except Exception:
        return out
    return out


def get_yearly_imports_value():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT date, strftime('%Y', date) as y, ordered_price, quantity, COALESCE(currency,'') as currency
        FROM imports
        ORDER BY date
    ''')
    rows = cur.fetchall()
    conn.close()
    totals = {}
    base = get_base_currency()
    for r in rows:
        y = r['y']
        amt = float(r['ordered_price'] or 0.0) * float(r['quantity'] or 0.0)
        from_ccy = (r['currency'] or get_default_import_currency() or base).upper()
        date_str = r['date']
        try:
            conv = convert_amount(date_str, amt, from_ccy, base)
            val = conv if conv is not None else amt if from_ccy == base else 0.0
        except Exception:
            val = amt if from_ccy == base else 0.0
        totals[y] = totals.get(y, 0.0) + float(val or 0.0)
    return totals


def build_monthly_overview(year: int):
    """Combine monthly sales/profit, expenses into a list for UI (one row per month)."""
    sales = get_monthly_sales_profit(year)
    expenses = get_monthly_expenses(year)
    returns_impact = get_monthly_return_impact(year)
    # imports can be shown separately; not included in net profit calculation directly
    months = [f"{year}-{m:02d}" for m in range(1, 13)]
    rows = []
    for ym in months:
        s = sales.get(ym, {})
        revenue = float(s.get('revenue', 0.0))
        cogs = float(s.get('cogs', 0.0))
        gp = float(s.get('gross_profit', 0.0))
        items = float(s.get('items_sold', 0.0))
        exp = float(expenses.get(ym, 0.0))
        net = gp - exp
        ri = returns_impact.get(ym, {'returns_refunds': 0.0, 'returns_cogs_reversed': 0.0, 'items_returned': 0.0})
        rows.append({
            'ym': ym,
            'revenue': revenue,
            'cogs': cogs,
            'gross_profit': gp,
            'expenses': exp,
            'net_profit': net,
            'items_sold': items,
            'returns_refunds': float(ri['returns_refunds']),
            'returns_cogs_reversed': float(ri['returns_cogs_reversed']),
            'returns_net_impact': float(ri['returns_cogs_reversed']) - float(ri['returns_refunds']),
            'items_returned': float(ri['items_returned']),
        })
    return rows


def build_yearly_summary():
    sales = get_yearly_sales_profit()
    expenses = get_yearly_expenses()
    imports = get_yearly_imports_value()
    returns_impact = get_yearly_return_impact()
    years = sorted(set(list(sales.keys()) + list(expenses.keys()) + list(imports.keys())))
    rows = []
    for y in years:
        s = sales.get(y, {})
        revenue = float(s.get('revenue', 0.0))
        cogs = float(s.get('cogs', 0.0))
        gp = float(s.get('gross_profit', 0.0))
        items = float(s.get('items_sold', 0.0))
        exp = float(expenses.get(y, 0.0))
        net = gp - exp
        ri = returns_impact.get(y, {'returns_refunds': 0.0, 'returns_cogs_reversed': 0.0, 'items_returned': 0.0})
        rows.append({
            'year': y,
            'revenue': revenue,
            'cogs': cogs,
            'gross_profit': gp,
            'expenses': exp,
            'net_profit': net,
            'imports_value': float(imports.get(y, 0.0)),
            'items_sold': items,
            'returns_refunds': float(ri['returns_refunds']),
            'returns_cogs_reversed': float(ri['returns_cogs_reversed']),
            'returns_net_impact': float(ri['returns_cogs_reversed']) - float(ri['returns_refunds']),
            'items_returned': float(ri['items_returned']),
        })
    return rows



def update_next_serial(category, subcategory, next_serial):
    try:
        ns = int(next_serial)
        if ns < 1:
            ns = 1
    except Exception:
        ns = 1
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE product_codes SET next_serial=? WHERE category=? AND subcategory=?', (ns, category or '', subcategory or ''))
    if cur.rowcount == 0:
        # if not exists, create with default codes 000
        cur.execute('INSERT INTO product_codes (category, subcategory, cat_code, sub_code, next_serial) VALUES (?,?,?,?,?)', (category or '', subcategory or '', '000', '000', ns))
    conn.commit()
    conn.close()


def delete_product_code(category, subcategory):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM product_codes WHERE category=? AND subcategory=?', (category or '', subcategory or ''))
    conn.commit()
    conn.close()


# --- Maintenance / Reset helpers ---
def reset_all_tables(clear_product_codes=True):
    """Delete all rows from core tables. Useful for clearing cached suggestions.
    If clear_product_codes is False, keeps product_codes table as-is.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM imports')
    cur.execute('DELETE FROM inventory')
    cur.execute('DELETE FROM expenses')
    if clear_product_codes:
        cur.execute('DELETE FROM product_codes')
    conn.commit()
    conn.close()


def delete_database_file():
    """Remove the SQLite database file. Next app start will recreate schema."""
    try:
        if DB_PATH.exists():
            DB_PATH.unlink()
            return True
    except Exception:
        return False
    return False


# =====================================================================================
# BATCH TRACKING SYSTEM - FIFO Cost Allocation for Accurate Profit Analysis
# =====================================================================================

def create_import_batch(import_id, date, category, subcategory, quantity, unit_cost, supplier, notes="", currency: str = 'TRY', fx_to_try: float = 1.0, unit_cost_orig: float = None):
    """Create a new batch from an import with full quantity available for allocation."""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
        INSERT INTO import_batches (import_id, batch_date, category, subcategory, 
                                   original_quantity, remaining_quantity, unit_cost, supplier, batch_notes, currency, fx_to_try, unit_cost_orig)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (import_id, date, category or '', subcategory or '', quantity, quantity, unit_cost, supplier or '', notes or '', currency or 'TRY', float(fx_to_try or 1.0), unit_cost_orig))
    
    batch_id = cur.lastrowid
    conn.commit()
    conn.close()
    return batch_id


def get_available_batches(category, subcategory=None, order_by_date=True):
    """Get available batches (remaining_quantity > 0) for FIFO allocation."""
    conn = get_conn()
    cur = conn.cursor()
    
    if subcategory:
        query = '''
            SELECT id, batch_date, category, subcategory, original_quantity, remaining_quantity, 
                   unit_cost, unit_cost_orig, currency, fx_to_try, supplier, batch_notes, import_id
            FROM import_batches 
            WHERE category = ? AND subcategory = ? AND remaining_quantity > 0
        '''
        params = (category, subcategory)
    else:
        query = '''
            SELECT id, batch_date, category, subcategory, original_quantity, remaining_quantity, 
                   unit_cost, unit_cost_orig, currency, fx_to_try, supplier, batch_notes, import_id
            FROM import_batches 
            WHERE category = ? AND remaining_quantity > 0
        '''
        params = (category,)
    
    if order_by_date:
        query += ' ORDER BY batch_date ASC, id ASC'  # FIFO: oldest first
    
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def allocate_sale_to_batches(product_id, sale_date, category, subcategory, quantity, unit_sale_price_base):
    """
    Allocate a sale to available batches using FIFO (First In, First Out).
    All amounts are expected to be in the app's base currency.
    Returns list of allocations with cost basis and profit calculations.
    """
    if quantity <= 0:
        return []
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get available batches in FIFO order (oldest first)
    batches = get_available_batches(category, subcategory)
    
    allocations = []
    remaining_to_allocate = quantity
    
    for batch in batches:
        if remaining_to_allocate <= 0:
            break
            
        batch_id = batch['id']
        batch_available = batch['remaining_quantity']
        # Use base currency cost as baseline; prefer unit_cost_orig (stored in base currency)
        unit_cost_base = 0.0
        try:
            # Prefer explicit original unit cost in base currency; fallback to batch.unit_cost if missing
            unit_cost_base = float((batch.get('unit_cost_orig') if isinstance(batch, dict) else None) or 0.0)
            if unit_cost_base == 0.0:
                unit_cost_base = float(batch.get('unit_cost') or 0.0)
        except Exception:
            unit_cost_base = float(batch.get('unit_cost') or 0.0)
        # Sale unit price is already provided in base currency
        unit_sale_price_base = float(unit_sale_price_base or 0.0)
        
        # Allocate as much as possible from this batch
        allocated_from_batch = min(remaining_to_allocate, batch_available)
        
        # Calculate profit
        profit_per_unit = unit_sale_price_base - unit_cost_base
        
        # Record allocation
        cur.execute('''
            INSERT INTO sale_batch_allocations 
            (product_id, sale_date, category, subcategory, batch_id, quantity_from_batch, 
             unit_cost, unit_sale_price, profit_per_unit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (product_id, sale_date, category or '', subcategory or '', batch_id, 
              allocated_from_batch, unit_cost_base, unit_sale_price_base, profit_per_unit))
        
        # Update batch remaining quantity
        new_remaining = batch_available - allocated_from_batch
        cur.execute('UPDATE import_batches SET remaining_quantity = ? WHERE id = ?', 
                   (new_remaining, batch_id))
        
        allocations.append({
            'batch_id': batch_id,
            'batch_date': batch['batch_date'],
            'supplier': batch['supplier'],
            'quantity_allocated': allocated_from_batch,
            'unit_cost': unit_cost_base,
            'unit_sale_price': unit_sale_price_base,
            'profit_per_unit': profit_per_unit,
            'total_cost': allocated_from_batch * unit_cost_base,
            'total_revenue': allocated_from_batch * unit_sale_price_base,
            'total_profit': allocated_from_batch * profit_per_unit
        })
        
        remaining_to_allocate -= allocated_from_batch
    
    conn.commit()
    conn.close()
    
    # Check if we couldn't allocate everything (negative inventory scenario)
    if remaining_to_allocate > 0:
        # Create a warning allocation with zero cost (inventory shortage)
        allocations.append({
            'batch_id': None,
            'batch_date': 'NO_INVENTORY',
            'supplier': 'SHORTAGE',
            'quantity_allocated': remaining_to_allocate,
            'unit_cost': 0.0,
            'unit_sale_price': unit_sale_price_base,
            'profit_per_unit': unit_sale_price_base,
            'total_cost': 0.0,
            'total_revenue': remaining_to_allocate * unit_sale_price_base,
            'total_profit': remaining_to_allocate * unit_sale_price_base
        })
    
    return allocations


def backfill_allocation_unit_costs():
    """
    For historical allocations where unit_cost was stored as 0, backfill from related batch.
    Recompute profit_per_unit accordingly. Leaves shortage rows (batch_id is NULL) untouched.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Update unit_cost from import_batches.unit_cost_orig (fallback to unit_cost)
        cur.execute('''
            UPDATE sale_batch_allocations
            SET unit_cost = (
                SELECT COALESCE(ib.unit_cost_orig, ib.unit_cost, 0)
                FROM import_batches ib
                WHERE ib.id = sale_batch_allocations.batch_id
            )
            WHERE (unit_cost IS NULL OR unit_cost = 0) AND batch_id IS NOT NULL
        ''')
        # Recompute profit_per_unit where it doesn't match unit_sale_price - unit_cost
        cur.execute('''
            UPDATE sale_batch_allocations
            SET profit_per_unit = unit_sale_price - unit_cost
            WHERE batch_id IS NOT NULL
        ''')
        conn.commit()
    finally:
        conn.close()


def get_sale_batch_info(product_id):
    """Get detailed batch allocation information for a specific sale."""
    conn = get_conn()
    cur = conn.cursor()
    
    # Use batch cost when allocation unit_cost is missing/zero and recompute profit_per_unit on the fly
    cur.execute('''
        SELECT 
            sba.product_id,
            sba.sale_date,
            sba.category,
            sba.subcategory,
            sba.batch_id,
            sba.quantity_from_batch,
            COALESCE(NULLIF(sba.unit_cost, 0), ib.unit_cost_orig, ib.unit_cost, 0) AS unit_cost,
            sba.unit_sale_price,
            (COALESCE(sba.unit_sale_price,0) - COALESCE(NULLIF(sba.unit_cost, 0), ib.unit_cost_orig, ib.unit_cost, 0)) AS profit_per_unit,
            ib.batch_date,
            ib.supplier,
            ib.batch_notes
        FROM sale_batch_allocations sba
        LEFT JOIN import_batches ib ON sba.batch_id = ib.id
        WHERE sba.product_id = ?
        ORDER BY sba.id
    ''', (product_id,))
    
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_batch_utilization_report():
    """Generate comprehensive batch utilization and profit report.
    Note: see get_batch_utilization_report_inclusive for version including import-related expenses.
    """
    conn = get_conn()
    cur = conn.cursor()
    
    # Get all batches with utilization stats
    cur.execute('''
        SELECT 
            ib.id,
            ib.batch_date,
            ib.category,
            ib.subcategory,
            ib.supplier,
            ib.original_quantity,
            ib.remaining_quantity,
            ib.unit_cost,
            ib.original_quantity - ib.remaining_quantity as allocated_quantity,
            ROUND((ib.original_quantity - ib.remaining_quantity) * ib.unit_cost, 2) as total_cost_allocated,
            COALESCE(SUM(sba.quantity_from_batch * sba.unit_sale_price), 0) as total_revenue,
            COALESCE(SUM(sba.quantity_from_batch * sba.profit_per_unit), 0) as total_profit
        FROM import_batches ib
        LEFT JOIN sale_batch_allocations sba ON ib.id = sba.batch_id
        GROUP BY ib.id
        ORDER BY ib.batch_date DESC
    ''')
    
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _build_import_expense_per_unit_map() -> Dict[int, float]:
    """Compute per-import extra expense per unit in base currency using expense_import_links.
    Sum expenses linked to an import (converted to base on expense date), divide by that import's batch original_quantity.
    Returns {import_id: expense_per_unit_base}.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        # Get all imports with their original quantities (from batches)
        cur.execute('SELECT import_id, SUM(original_quantity) as oq FROM import_batches GROUP BY import_id')
        imp_qty = {int(r['import_id']): float(r['oq'] or 0.0) for r in cur.fetchall() if r['import_id'] is not None}
        # Get expense links
        cur.execute('''
            SELECT eil.import_id AS import_id, e.date as date, e.amount as amount, COALESCE(e.currency,'') as currency
            FROM expense_import_links eil
            JOIN expenses e ON e.id = eil.expense_id
        ''')
        rows = cur.fetchall()
        conn.close()
        base = get_base_currency()
        totals: Dict[int, float] = {}
        for r in rows:
            iid = int(r['import_id']) if r['import_id'] is not None else None
            if not iid:
                continue
            amt = float(r['amount'] or 0.0)
            ccy = (r['currency'] or base).upper()
            dt = r['date']
            try:
                conv = convert_amount(dt, amt, ccy, base)
                val = conv if conv is not None else (amt if ccy == base else 0.0)
            except Exception:
                val = amt if ccy == base else 0.0
            totals[iid] = totals.get(iid, 0.0) + float(val or 0.0)
        per_unit: Dict[int, float] = {}
        for iid, total in totals.items():
            oq = float(imp_qty.get(iid, 0.0))
            per_unit[iid] = (total / oq) if oq > 0 else 0.0
        return per_unit
    except Exception:
        return {}


def get_batch_utilization_report_inclusive(include_expenses: bool = False):
    """Batch utilization with optional inclusion of import-related expenses as per-unit extra cost.
    When include_expenses is True, unit cost and totals are adjusted by expense_per_unit(import_id).
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT 
            ib.id,
            ib.import_id,
            ib.batch_date,
            ib.category,
            ib.subcategory,
            ib.supplier,
            ib.original_quantity,
            ib.remaining_quantity,
            ib.unit_cost,
            (ib.original_quantity - ib.remaining_quantity) as allocated_quantity,
            COALESCE(SUM(sba.quantity_from_batch * sba.unit_sale_price), 0) as total_revenue,
            COALESCE(SUM(sba.quantity_from_batch * sba.profit_per_unit), 0) as total_profit_unadj
        FROM import_batches ib
        LEFT JOIN sale_batch_allocations sba ON ib.id = sba.batch_id
        GROUP BY ib.id
        ORDER BY ib.batch_date DESC
    ''')
    rows_raw = [dict(r) for r in cur.fetchall()]
    conn.close()
    if not include_expenses:
        # compute derived totals as original function did
        out = []
        for r in rows_raw:
            total_cost_allocated = float(r['allocated_quantity']) * float(r['unit_cost'])
            out.append({
                'id': r['id'],
                'batch_date': r['batch_date'],
                'category': r['category'],
                'subcategory': r['subcategory'],
                'supplier': r['supplier'],
                'original_quantity': float(r['original_quantity']),
                'remaining_quantity': float(r['remaining_quantity']),
                'unit_cost': float(r['unit_cost']),
                'allocated_quantity': float(r['allocated_quantity']),
                'total_cost_allocated': round(total_cost_allocated, 2),
                'total_revenue': float(r['total_revenue'] or 0.0),
                'total_profit': float(r['total_profit_unadj'] or 0.0),
            })
        return out
    # include expenses
    per_imp = _build_import_expense_per_unit_map()
    out = []
    for r in rows_raw:
        imp_id = r.get('import_id')
        extra = float(per_imp.get(imp_id, 0.0))
        unit_cost_eff = float(r['unit_cost']) + extra
        allocated_qty = float(r['allocated_quantity'] or 0.0)
        total_cost_allocated = allocated_qty * unit_cost_eff
        # Adjust profit by subtracting extra expense on allocated qty
        profit_unadj = float(r['total_profit_unadj'] or 0.0)
        profit_adj = profit_unadj - (allocated_qty * extra)
        out.append({
            'id': r['id'],
            'batch_date': r['batch_date'],
            'category': r['category'],
            'subcategory': r['subcategory'],
            'supplier': r['supplier'],
            'original_quantity': float(r['original_quantity']),
            'remaining_quantity': float(r['remaining_quantity']),
            'unit_cost': unit_cost_eff,
            'allocated_quantity': allocated_qty,
            'total_cost_allocated': round(total_cost_allocated, 2),
            'total_revenue': float(r['total_revenue'] or 0.0),
            'total_profit': round(profit_adj, 2),
        })
    return out



def get_profit_analysis_by_sale(include_expenses: bool = False):
    """Get detailed profit analysis for each sale with batch breakdown.
    Uses batch cost when allocation cost is missing to ensure correct totals.
    """
    conn = get_conn()
    cur = conn.cursor()
    
    if not include_expenses:
        cur.execute('''
            SELECT 
                sba.product_id,
                sba.sale_date,
                sba.category,
                sba.subcategory,
                SUM(sba.quantity_from_batch) as total_quantity,
                ROUND(SUM(sba.quantity_from_batch * COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_orig, ib.unit_cost, 0)), 2) as total_cost,
                ROUND(SUM(sba.quantity_from_batch * sba.unit_sale_price), 2) as total_revenue,
                ROUND(SUM(sba.quantity_from_batch * (sba.unit_sale_price - COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_orig, ib.unit_cost, 0))), 2) as total_profit,
                ROUND(
                    SUM(sba.quantity_from_batch * (sba.unit_sale_price - COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_orig, ib.unit_cost, 0))) 
                    / NULLIF(SUM(sba.quantity_from_batch * COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_orig, ib.unit_cost, 0)), 0) * 100
                , 2) as profit_margin_percent,
                COUNT(DISTINCT sba.batch_id) as batches_used
            FROM sale_batch_allocations sba
            LEFT JOIN import_batches ib ON sba.batch_id = ib.id
            GROUP BY sba.product_id
            ORDER BY sba.sale_date DESC
        ''')
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    # Include expenses: compute extra per product by summing qty * expense_per_unit(import_id)
    cur.execute('''
        SELECT 
            sba.product_id,
            sba.sale_date,
            sba.category,
            sba.subcategory,
            sba.quantity_from_batch,
            sba.unit_sale_price,
            COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_orig, ib.unit_cost, 0) AS unit_cost,
            ib.import_id
        FROM sale_batch_allocations sba
        LEFT JOIN import_batches ib ON sba.batch_id = ib.id
        ORDER BY sba.sale_date DESC
    ''')
    allocs = [dict(r) for r in cur.fetchall()]
    conn.close()
    per_imp = _build_import_expense_per_unit_map()
    # Aggregate per product
    agg: Dict[str, Dict[str, float]] = {}
    sale_date: Dict[str, str] = {}
    category: Dict[str, str] = {}
    subcategory: Dict[str, str] = {}
    batches_used: Dict[str, set] = {}
    for a in allocs:
        pid = a['product_id']
        if not pid:
            continue
        q = float(a['quantity_from_batch'] or 0.0)
        unit_sale = float(a['unit_sale_price'] or 0.0)
        unit_cost = float(a['unit_cost'] or 0.0)
        imp_id = a.get('import_id')
        extra = float(per_imp.get(imp_id, 0.0)) if imp_id is not None else 0.0
        eff_cost = unit_cost + extra
        d = agg.setdefault(pid, {'qty': 0.0, 'cost': 0.0, 'rev': 0.0})
        d['qty'] += q
        d['cost'] += q * eff_cost
        d['rev'] += q * unit_sale
        sale_date[pid] = sale_date.get(pid) or a.get('sale_date')
        category[pid] = category.get(pid) or a.get('category')
        subcategory[pid] = subcategory.get(pid) or a.get('subcategory')
    rows = []
    for pid, d in agg.items():
        cost = float(d['cost'])
        rev = float(d['rev'])
        profit = rev - cost
        margin = (profit / cost * 100.0) if cost > 0 else 0.0
        rows.append({
            'product_id': pid,
            'sale_date': sale_date.get(pid),
            'category': category.get(pid),
            'subcategory': subcategory.get(pid),
            'total_quantity': float(d['qty']),
            'total_cost': round(cost, 2),
            'total_revenue': round(rev, 2),
            'total_profit': round(profit, 2),
            'profit_margin_percent': round(margin, 2),
            'batches_used': None,
        })
    # Optionally compute batches_used count per product for parity
    # We can derive from allocations
    bu: Dict[str, set] = {}
    for a in allocs:
        pid = a['product_id']
        if not pid:
            continue
        # cannot get batch_id as not selected; recompute quickly
    # Re-fetch minimal for batch ids
    try:
        conn2 = get_conn()
        cur2 = conn2.cursor()
        cur2.execute('SELECT product_id, COUNT(DISTINCT batch_id) as bc FROM sale_batch_allocations GROUP BY product_id')
        for r in cur2.fetchall():
            for row in rows:
                if row['product_id'] == r['product_id']:
                    row['batches_used'] = r['bc']
        conn2.close()
    except Exception:
        pass
    return rows


def _get_exact_cogs_for_product(product_id: str) -> float:
    """Return the total cost basis in base currency for a sold product based on its recorded allocations.
    Uses sba.unit_cost when present, otherwise falls back to import batch's unit_cost_orig or unit_cost.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('''
            SELECT 
                SUM(COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_orig, ib.unit_cost, 0) * COALESCE(sba.quantity_from_batch,0)) AS total_cost
            FROM sale_batch_allocations sba
            LEFT JOIN import_batches ib ON sba.batch_id = ib.id
            WHERE sba.product_id = ?
        ''', (product_id,))
        row = cur.fetchone()
        conn.close()
        return float(row['total_cost'] or 0.0) if row else 0.0
    except Exception:
        return 0.0


def handle_return_batch_allocation(product_id, restock_quantity=1.0):
    """
    Handle return by adding quantity back to the original batch(es) that were used.
    Returns the batch(es) that inventory was returned to.
    """
    if restock_quantity <= 0:
        return []
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Get original allocations for this sale (LIFO order for returns)
    cur.execute('''
        SELECT batch_id, quantity_from_batch, unit_cost
        FROM sale_batch_allocations 
        WHERE product_id = ?
        ORDER BY id DESC
    ''', (product_id,))
    
    allocations = cur.fetchall()
    returned_to_batches = []
    remaining_to_return = restock_quantity
    
    for alloc in allocations:
        if remaining_to_return <= 0:
            break
            
        batch_id = alloc[0]
        original_allocation = alloc[1]
        unit_cost = alloc[2]
        
        if batch_id is None:  # Skip shortage allocations
            continue
        
        # Return as much as possible to this batch (up to original allocation amount)
        return_to_batch = min(remaining_to_return, original_allocation)
        
        # Add back to batch remaining quantity
        cur.execute('UPDATE import_batches SET remaining_quantity = remaining_quantity + ? WHERE id = ?',
                   (return_to_batch, batch_id))
        
        # Get batch info for reporting
        cur.execute('SELECT batch_date, supplier, category, subcategory FROM import_batches WHERE id = ?', (batch_id,))
        batch_info = cur.fetchone()
        
        returned_to_batches.append({
            'batch_id': batch_id,
            'batch_date': batch_info[0] if batch_info else 'Unknown',
            'supplier': batch_info[1] if batch_info else 'Unknown',
            'category': batch_info[2] if batch_info else '',
            'subcategory': batch_info[3] if batch_info else '',
            'returned_quantity': return_to_batch,
            'unit_cost': unit_cost
        })
        
        remaining_to_return -= return_to_batch
    
    conn.commit()
    conn.close()
    return returned_to_batches


def migrate_existing_imports_to_batches():
    """One-time migration to convert existing imports to batch system."""
    conn = get_conn()
    cur = conn.cursor()
    
    # Check if we have any imports that aren't in batches yet
    cur.execute('''
        SELECT i.id, i.date, i.category, i.subcategory, i.quantity, i.ordered_price, i.supplier, i.notes
        FROM imports i
        LEFT JOIN import_batches ib ON i.id = ib.import_id
        WHERE ib.import_id IS NULL
    ''')
    
    unmigrated_imports = cur.fetchall()
    
    for imp in unmigrated_imports:
        import_id, date, category, subcategory, quantity, unit_cost, supplier, notes = imp
        create_import_batch(import_id, date, category, subcategory, quantity, unit_cost, supplier, notes)
    
    conn.close()
    return len(unmigrated_imports)


# =====================================================================================
# CUSTOMER MANAGEMENT SYSTEM
# =====================================================================================

CUSTOMERS_CSV = Path(__file__).resolve().parents[1] / "data" / "customers.csv"

def ensure_customers_csv():
    """Ensure customers.csv exists with proper headers."""
    CUSTOMERS_CSV.parent.mkdir(parents=True, exist_ok=True)
    desired_headers = ['customer_id', 'name', 'email', 'phone', 'address', 'notes', 'created_date']
    
    if not CUSTOMERS_CSV.exists():
        with CUSTOMERS_CSV.open('w', newline='') as f:
            import csv
            csv.writer(f).writerow(desired_headers)
        return
    
    # Migrate header if needed (non-destructive)
    try:
        with CUSTOMERS_CSV.open('r', newline='') as f:
            import csv
            reader = csv.reader(f)
            rows = list(reader)
        
        if not rows:
            with CUSTOMERS_CSV.open('w', newline='') as f:
                csv.writer(f).writerow(desired_headers)
            return
            
        header = rows[0]
        if header == desired_headers:
            return
            
        # Migrate to desired header structure
        data = rows[1:]
        mapped = []
        for r in data:
            rowd = {header[i]: r[i] if i < len(r) else '' for i in range(len(header))}
            mapped.append({
                'customer_id': rowd.get('customer_id', ''),
                'name': rowd.get('name', ''),
                'email': rowd.get('email', ''),
                'phone': rowd.get('phone', ''),
                'address': rowd.get('address', ''),
                'notes': rowd.get('notes', ''),
                'created_date': rowd.get('created_date', ''),
            })
        
        with CUSTOMERS_CSV.open('w', newline='') as f:
            import csv
            w = csv.DictWriter(f, fieldnames=desired_headers)
            w.writeheader()
            w.writerows(mapped)
            
    except Exception:
        pass  # Keep existing file if migration fails


def get_next_customer_id():
    """Generate next customer ID in format CUST001, CUST002, etc."""
    try:
        customers = read_customers()
        if not customers:
            return "CUST001"
        
        # Find highest existing ID
        max_num = 0
        for customer in customers:
            cid = customer.get('customer_id', '').strip()
            if cid.startswith('CUST') and len(cid) >= 7:
                try:
                    num = int(cid[4:])
                    max_num = max(max_num, num)
                except ValueError:
                    continue
        
        return f"CUST{max_num + 1:03d}"
    except Exception:
        return "CUST001"


def add_customer(name, email='', phone='', address='', notes=''):
    """Add a new customer and return the generated customer ID."""
    ensure_customers_csv()
    
    customer_id = get_next_customer_id()
    created_date = datetime.now().strftime('%Y-%m-%d')
    
    with CUSTOMERS_CSV.open('a', newline='') as f:
        import csv
        writer = csv.DictWriter(f, fieldnames=['customer_id', 'name', 'email', 'phone', 'address', 'notes', 'created_date'])
        writer.writerow({
            'customer_id': customer_id,
            'name': name.strip(),
            'email': email.strip(),
            'phone': phone.strip(),
            'address': address.strip(),
            'notes': notes.strip(),
            'created_date': created_date
        })
    
    return customer_id


def read_customers():
    """Read all customers from CSV."""
    ensure_customers_csv()
    if not CUSTOMERS_CSV.exists():
        return []
    
    with CUSTOMERS_CSV.open('r', newline='') as f:
        import csv
        reader = csv.DictReader(f)
        return list(reader)


def write_customers(customers):
    """Write customers list back to CSV."""
    ensure_customers_csv()
    with CUSTOMERS_CSV.open('w', newline='') as f:
        import csv
        fieldnames = ['customer_id', 'name', 'email', 'phone', 'address', 'notes', 'created_date']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(customers)


def find_customer_by_name(name):
    """Find customer by name (case-insensitive). Returns customer record or None."""
    customers = read_customers()
    name_lower = name.lower().strip()
    for customer in customers:
        if customer.get('name', '').lower().strip() == name_lower:
            return customer
    return None


def find_or_create_customer(name):
    """Find existing customer by name or create new one. Returns customer_id."""
    if not name or not name.strip():
        return None
    
    existing = find_customer_by_name(name.strip())
    if existing:
        return existing['customer_id']
    
    # Create new customer with just the name
    return add_customer(name.strip())


def get_customer_name_suggestions():
    """Get list of existing customer names for auto-suggestions."""
    customers = read_customers()
    names = []
    for customer in customers:
        name = customer.get('name', '').strip()
        if name:
            names.append(name)
    return sorted(set(names))  # Remove duplicates and sort


def edit_customer(customer_id, name='', email='', phone='', address='', notes=''):
    """Edit existing customer details."""
    customers = read_customers()
    for i, customer in enumerate(customers):
        if customer.get('customer_id', '').strip() == customer_id.strip():
            customers[i].update({
                'name': name.strip() if name else customer.get('name', ''),
                'email': email.strip() if email else customer.get('email', ''),
                'phone': phone.strip() if phone else customer.get('phone', ''),
                'address': address.strip() if address else customer.get('address', ''),
                'notes': notes.strip() if notes else customer.get('notes', ''),
            })
            write_customers(customers)
            return True
    return False


def delete_customer(customer_id):
    """Delete customer by ID."""
    customers = read_customers()
    original_count = len(customers)
    customers = [c for c in customers if c.get('customer_id', '').strip() != customer_id.strip()]
    
    if len(customers) < original_count:
        write_customers(customers)
        return True
    return False


def get_customer_sales_summary(customer_id):
    """Get sales summary for a specific customer (requires reading sales.csv)."""
    try:
        from pathlib import Path
        import csv
        
        SALES_CSV = Path(__file__).resolve().parents[1] / 'data' / 'sales.csv'
        if not SALES_CSV.exists():
            return {'total_sales': 0, 'total_revenue': 0.0, 'sales_count': 0, 'recent_sales': []}
        
        with SALES_CSV.open('r', newline='') as f:
            reader = csv.DictReader(f)
            customer_sales = []
            total_revenue = 0.0
            
            for row in reader:
                if row.get('CustomerID', '').strip() == customer_id.strip():
                    customer_sales.append(row)
                    try:
                        selling_price = float(row.get('SellingPrice', 0))
                        total_revenue += selling_price
                    except (ValueError, TypeError):
                        pass
        
        # Sort by date descending for recent sales
        customer_sales.sort(key=lambda x: x.get('Date', ''), reverse=True)
        
        return {
            'total_sales': len(customer_sales),
            'total_revenue': total_revenue,
            'sales_count': len(customer_sales),
            'recent_sales': customer_sales[:10]  # Last 10 sales
        }
        
    except Exception:
        return {'total_sales': 0, 'total_revenue': 0.0, 'sales_count': 0, 'recent_sales': []}
