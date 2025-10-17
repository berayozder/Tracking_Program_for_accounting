"""connection.py - sqlite3 connection and initialization."""

from pathlib import Path
import sqlite3

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
    """Initialize DB schema if missing, return sqlite3.Connection."""
    ensure_data_dir()
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
    # Add columns to imports for import-level expenses and flag to include them
    try:
        cur.execute('PRAGMA table_info(imports)')
        imp_cols = [r['name'] for r in cur.fetchall()]
        if 'total_import_expenses' not in imp_cols:
            cur.execute('ALTER TABLE imports ADD COLUMN total_import_expenses REAL DEFAULT 0.0')
        if 'include_expenses' not in imp_cols:
            cur.execute('ALTER TABLE imports ADD COLUMN include_expenses INTEGER DEFAULT 0')
    except Exception:
        pass
    # import_lines: supports multiple category/subcategory lines per import/order
    cur.execute('''
    CREATE TABLE IF NOT EXISTS import_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        import_id INTEGER,
        category TEXT,
        subcategory TEXT,
        ordered_price REAL,
        quantity REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
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
        # Add soft-delete flag to imports if missing
        if 'deleted' not in cols:
            try:
                cur.execute("ALTER TABLE imports ADD COLUMN deleted INTEGER DEFAULT 0")
            except Exception:
                pass
        # If older DBs included an fx_to_try column on imports, preserve it into fx_to_base
        if 'fx_to_try' in cols and 'fx_to_base' not in cols:
            try:
                cur.execute('ALTER TABLE imports ADD COLUMN fx_to_base REAL')
                cur.execute('UPDATE imports SET fx_to_base = fx_to_try WHERE fx_to_try IS NOT NULL')
            except Exception:
                pass
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
        # Add soft-delete flag to expenses if missing
        if 'deleted' not in cols:
            try:
                cur.execute("ALTER TABLE expenses ADD COLUMN deleted INTEGER DEFAULT 0")
            except Exception:
                pass
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
    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_product_codes_cat_sub ON product_codes(category, subcategory)')
    # BATCH tracking tables
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
    unit_cost_base REAL,
        supplier TEXT,
        batch_notes TEXT,
        currency TEXT DEFAULT 'TRY',
    fx_to_base REAL DEFAULT 1.0,
        unit_cost_orig REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
    )
    ''')
    try:
        cur.execute('PRAGMA table_info(import_batches)')
        bcols = [row['name'] for row in cur.fetchall()]
        if 'currency' not in bcols:
            cur.execute("ALTER TABLE import_batches ADD COLUMN currency TEXT DEFAULT 'TRY'")
        if 'fx_to_base' not in bcols:
            cur.execute('ALTER TABLE import_batches ADD COLUMN fx_to_base REAL DEFAULT 1.0')
        if 'unit_cost_orig' not in bcols:
            cur.execute('ALTER TABLE import_batches ADD COLUMN unit_cost_orig REAL')
        if 'unit_cost_base' not in bcols:
            cur.execute('ALTER TABLE import_batches ADD COLUMN unit_cost_base REAL')
        # Add soft-delete flag to import_batches if missing
        if 'deleted' not in bcols:
            try:
                cur.execute('ALTER TABLE import_batches ADD COLUMN deleted INTEGER DEFAULT 0')
            except Exception:
                pass
        # Support linking batches to specific import_lines (multi-line orders)
        if 'import_line_id' not in bcols:
            try:
                cur.execute('ALTER TABLE import_batches ADD COLUMN import_line_id INTEGER')
            except Exception:
                pass
    except Exception:
        pass
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
    try:
        cur.execute('PRAGMA table_info(sale_batch_allocations)')
        sba_cols = [row['name'] for row in cur.fetchall()]
        if 'deleted' not in sba_cols:
            try:
                cur.execute("ALTER TABLE sale_batch_allocations ADD COLUMN deleted INTEGER DEFAULT 0")
            except Exception:
                pass
    except Exception:
        pass
    cur.execute('CREATE INDEX IF NOT EXISTS idx_import_batches_category ON import_batches(category, subcategory)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_import_batches_date ON import_batches(batch_date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sale_allocations_product ON sale_batch_allocations(product_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sale_allocations_batch ON sale_batch_allocations(batch_id)')
    # RETURNS table (currency-aware)
    cur.execute('''
    CREATE TABLE IF NOT EXISTS returns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        return_date TEXT,
        product_id TEXT,
        sale_date TEXT,
        category TEXT,
        subcategory TEXT,
        unit_price REAL,
        selling_price REAL,
        platform TEXT,
        refund_amount REAL,
        refund_currency TEXT,
        refund_amount_base REAL,
        restock INTEGER,
        reason TEXT,
        doc_paths TEXT,
        restock_processed INTEGER DEFAULT 0
    )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_returns_date ON returns(return_date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_returns_product ON returns(product_id)')
    try:
        cur.execute('PRAGMA table_info(returns)')
        rcols = [row['name'] for row in cur.fetchall()]
        if 'restock_processed' not in rcols:
            cur.execute("ALTER TABLE returns ADD COLUMN restock_processed INTEGER DEFAULT 0")
        # Add soft-delete flag to returns if missing
        if 'deleted' not in rcols:
            try:
                cur.execute("ALTER TABLE returns ADD COLUMN deleted INTEGER DEFAULT 0")
            except Exception:
                pass
    except Exception:
        pass
    # SALES table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        category TEXT,
        subcategory TEXT,
        quantity REAL,
        selling_price REAL,
        platform TEXT,
        product_id TEXT,
        customer_id TEXT,
        document_path TEXT,
        fx_to_base REAL,
        selling_price_base REAL,
        sale_currency TEXT,
        deleted INTEGER DEFAULT 0
    )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id)')
    # Triggers for product_codes integrity
    cur.execute('''
    CREATE TRIGGER IF NOT EXISTS trg_product_codes_bi
    BEFORE INSERT ON product_codes
    BEGIN
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.cat_code = NEW.cat_code AND p.category <> NEW.category
        ) THEN RAISE(ABORT, 'cat_code already used by different category') END;
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.category = NEW.category AND p.cat_code <> NEW.cat_code
        ) THEN RAISE(ABORT, 'category already mapped to different cat_code') END;
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.category = NEW.category AND p.sub_code = NEW.sub_code AND p.subcategory <> NEW.subcategory
        ) THEN RAISE(ABORT, 'sub_code already used by different subcategory in this category') END;
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
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.cat_code = NEW.cat_code AND p.category <> NEW.category
        ) THEN RAISE(ABORT, 'cat_code already used by different category') END;
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.category = NEW.category AND p.id <> NEW.id AND p.cat_code <> NEW.cat_code
        ) THEN RAISE(ABORT, 'category already mapped to different cat_code') END;
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.category = NEW.category AND p.id <> NEW.id AND p.sub_code = NEW.sub_code AND p.subcategory <> NEW.subcategory
        ) THEN RAISE(ABORT, 'sub_code already used by different subcategory in this category') END;
        SELECT CASE WHEN EXISTS(
            SELECT 1 FROM product_codes p
            WHERE p.category = NEW.category AND p.id <> NEW.id AND p.subcategory = NEW.subcategory AND p.sub_code <> NEW.sub_code
        ) THEN RAISE(ABORT, 'subcategory already mapped to different sub_code') END;
    END;
    ''')
    conn.commit()
    return conn

