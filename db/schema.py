"""schema.py - all table creation, migrations, triggers, indexes, and views."""

def add_column_if_missing(cur, table: str, column_def: str):
    """Add a column if it does not exist in the table."""
    col_name = column_def.split()[0]
    cur.execute(f'PRAGMA table_info({table})')
    existing_cols = [r['name'] for r in cur.fetchall()]
    if col_name not in existing_cols:
        cur.execute(f'ALTER TABLE {table} ADD COLUMN {column_def}')


def init_db_schema(conn):
    """Create tables, migrations, triggers, indexes, and views."""
    cur = conn.cursor()


    # --- CORE TABLES ---
    
    # 1. Imports
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
        currency TEXT DEFAULT 'TRY',
        total_import_expenses REAL DEFAULT 0.0,
        include_expenses INTEGER DEFAULT 0,
        deleted INTEGER DEFAULT 0,
        deleted_at TEXT,
        deleted_by TEXT,
        delete_reason TEXT,
        fx_to_base REAL,
        vat_rate REAL DEFAULT 18.0,
        vat_amount REAL DEFAULT 0.0,
        is_vat_inclusive INTEGER DEFAULT 1,
        document_path TEXT
    )
    ''')
    # Migrations for existing DBs
    add_column_if_missing(cur, 'imports', 'total_import_expenses REAL DEFAULT 0.0')
    add_column_if_missing(cur, 'imports', 'include_expenses INTEGER DEFAULT 0')
    add_column_if_missing(cur, 'imports', 'deleted INTEGER DEFAULT 0')
    add_column_if_missing(cur, 'imports', 'deleted_at TEXT')
    add_column_if_missing(cur, 'imports', 'deleted_by TEXT')
    add_column_if_missing(cur, 'imports', 'delete_reason TEXT')
    add_column_if_missing(cur, 'imports', 'fx_to_base REAL')
    add_column_if_missing(cur, 'imports', 'vat_rate REAL DEFAULT 18.0')
    add_column_if_missing(cur, 'imports', 'vat_amount REAL DEFAULT 0.0')
    add_column_if_missing(cur, 'imports', 'is_vat_inclusive INTEGER DEFAULT 1')
    add_column_if_missing(cur, 'imports', 'document_path TEXT')

    # 2. Customers
    cur.execute('''
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        address TEXT,
        notes TEXT,
        created_date TEXT
    )
    ''')
    
    # 3. Product Codes
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

    # 4. Sales
    cur.execute('''
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        subcategory TEXT,
        quantity REAL NOT NULL,
        selling_price REAL NOT NULL,
        platform TEXT,
        product_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        document_path TEXT,
        fx_to_base REAL,
        selling_price_base REAL,
        sale_currency TEXT,
        vat_rate REAL NOT NULL DEFAULT 18.0,
        vat_amount REAL NOT NULL DEFAULT 0.0,
        is_vat_inclusive INTEGER NOT NULL DEFAULT 1,
        deleted INTEGER DEFAULT 0,
        deleted_at TEXT,
        deleted_by TEXT,
        delete_reason TEXT,
        voided INTEGER DEFAULT 0,
        voided_at TEXT,
        voided_by TEXT,
        void_reason TEXT,
        reversal_id INTEGER,
        FOREIGN KEY (product_id) REFERENCES product_codes(cat_code) ON DELETE SET NULL,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE SET NULL
    )
    ''')

    # 5. Expenses
    cur.execute('''
     CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        amount REAL,
        is_import_related INTEGER DEFAULT 0,
        import_id INTEGER,
        category TEXT,
        notes TEXT,
        document_path TEXT,
        currency TEXT,
        vat_rate REAL DEFAULT 18.0,
        vat_amount REAL DEFAULT 0.0,
        is_vat_inclusive INTEGER DEFAULT 1,
        net_amount REAL,
        gross_amount REAL,
        deleted INTEGER DEFAULT 0,
        deleted_at TEXT,
        deleted_by TEXT,
        delete_reason TEXT
    )
    ''')

    # Migrations for existing DBs
    add_column_if_missing(cur, 'expenses', 'amount REAL')
    add_column_if_missing(cur, 'expenses', 'is_import_related INTEGER DEFAULT 0')
    add_column_if_missing(cur, 'expenses', 'import_id INTEGER')
    add_column_if_missing(cur, 'expenses', 'category TEXT')
    add_column_if_missing(cur, 'expenses', 'notes TEXT')
    add_column_if_missing(cur, 'expenses', 'document_path TEXT')
    add_column_if_missing(cur, 'expenses', 'currency TEXT')
    add_column_if_missing(cur, 'expenses', 'vat_rate REAL DEFAULT 18.0')
    add_column_if_missing(cur, 'expenses', 'vat_amount REAL DEFAULT 0.0')
    add_column_if_missing(cur, 'expenses', 'is_vat_inclusive INTEGER DEFAULT 1')
    add_column_if_missing(cur, 'expenses', 'net_amount REAL')
    add_column_if_missing(cur, 'expenses', 'gross_amount REAL')
    add_column_if_missing(cur, 'expenses', 'deleted INTEGER DEFAULT 0')
    add_column_if_missing(cur, 'expenses', 'deleted_at TEXT')
    add_column_if_missing(cur, 'expenses', 'deleted_by TEXT')
    add_column_if_missing(cur, 'expenses', 'delete_reason TEXT')

    # 6. Links and Helpers
    cur.execute('''
    CREATE TABLE IF NOT EXISTS expense_import_links (
        expense_id INTEGER,
        import_id INTEGER,
        PRIMARY KEY (expense_id, import_id),
        FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE,
        FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
    )
    ''')
    
    cur.execute('''
    CREATE TABLE IF NOT EXISTS import_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        import_id INTEGER,
        category TEXT,
        subcategory TEXT,
        ordered_price REAL,
        quantity REAL,
        FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
    )
    ''')

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
        import_line_id INTEGER,
        deleted INTEGER DEFAULT 0,
        deleted_at TEXT,
        deleted_by TEXT,
        delete_reason TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
    )
    ''')

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
        deleted INTEGER DEFAULT 0,
        deleted_at TEXT,
        deleted_by TEXT,
        delete_reason TEXT,
        FOREIGN KEY (batch_id) REFERENCES import_batches(id) ON DELETE CASCADE
    )
    ''')
    add_column_if_missing(cur, 'sale_batch_allocations', 'product_id TEXT')
    add_column_if_missing(cur, 'sale_batch_allocations', 'sale_date TEXT')
    add_column_if_missing(cur, 'sale_batch_allocations', 'category TEXT')
    add_column_if_missing(cur, 'sale_batch_allocations', 'subcategory TEXT')
    add_column_if_missing(cur, 'sale_batch_allocations', 'quantity_from_batch REAL')
    add_column_if_missing(cur, 'sale_batch_allocations', 'unit_cost REAL')
    add_column_if_missing(cur, 'sale_batch_allocations', 'unit_sale_price REAL')
    add_column_if_missing(cur, 'sale_batch_allocations', 'profit_per_unit REAL')
    add_column_if_missing(cur, 'sale_batch_allocations', 'deleted INTEGER DEFAULT 0')
    add_column_if_missing(cur, 'sale_batch_allocations', 'deleted_at TEXT')
    add_column_if_missing(cur, 'sale_batch_allocations', 'deleted_by TEXT')
    add_column_if_missing(cur, 'sale_batch_allocations', 'delete_reason TEXT')

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
        restock_processed INTEGER DEFAULT 0,
        deleted INTEGER DEFAULT 0,
        deleted_at TEXT,
        deleted_by TEXT,
        delete_reason TEXT
    )
    ''')
    add_column_if_missing(cur, 'returns', 'product_id TEXT')
    add_column_if_missing(cur, 'returns', 'sale_date TEXT')
    add_column_if_missing(cur, 'returns', 'category TEXT')
    add_column_if_missing(cur, 'returns', 'subcategory TEXT')
    add_column_if_missing(cur, 'returns', 'unit_price REAL')
    add_column_if_missing(cur, 'returns', 'selling_price REAL')
    add_column_if_missing(cur, 'returns', 'platform TEXT')
    add_column_if_missing(cur, 'returns', 'refund_amount REAL')
    add_column_if_missing(cur, 'returns', 'refund_currency TEXT')
    add_column_if_missing(cur, 'returns', 'refund_amount_base REAL')
    add_column_if_missing(cur, 'returns', 'restock INTEGER')
    add_column_if_missing(cur, 'returns', 'reason TEXT')
    add_column_if_missing(cur, 'returns', 'doc_paths TEXT')
    add_column_if_missing(cur, 'returns', 'restock_processed INTEGER DEFAULT 0')
    add_column_if_missing(cur, 'returns', 'deleted INTEGER DEFAULT 0')

    # 7. Users and Logs
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

    # 8. Inventory Cache
    cur.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        subcategory TEXT,
        quantity REAL,
        last_updated TEXT
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS fx_cache (
        date TEXT,
        from_ccy TEXT,
        to_ccy TEXT,
        rate REAL,
        PRIMARY KEY (date, from_ccy, to_ccy)
    )
    ''')

    # --- INDEXES ---
    cur.execute('CREATE INDEX IF NOT EXISTS idx_import_batches_category ON import_batches(category, subcategory)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_import_batches_date ON import_batches(batch_date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sale_allocations_product ON sale_batch_allocations(product_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sale_allocations_batch ON sale_batch_allocations(batch_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_returns_date ON returns(return_date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_returns_product ON returns(product_id)')

    # --- VIEWS ---
    cur.execute("CREATE VIEW IF NOT EXISTS active_sales AS SELECT * FROM sales WHERE (deleted IS NULL OR deleted=0) AND (voided IS NULL OR voided=0)")
    cur.execute("CREATE VIEW IF NOT EXISTS active_imports AS SELECT * FROM imports WHERE (deleted IS NULL OR deleted=0)")
    cur.execute("CREATE VIEW IF NOT EXISTS active_expenses AS SELECT * FROM expenses WHERE (deleted IS NULL OR deleted=0)")
    cur.execute("CREATE VIEW IF NOT EXISTS active_import_batches AS SELECT * FROM import_batches WHERE (deleted IS NULL OR deleted=0)")
    cur.execute("CREATE VIEW IF NOT EXISTS active_sale_batch_allocations AS SELECT * FROM sale_batch_allocations WHERE (deleted IS NULL OR deleted=0)")
    cur.execute("CREATE VIEW IF NOT EXISTS active_returns AS SELECT * FROM returns WHERE (deleted IS NULL OR deleted=0)")

    # --- TRIGGERS ---
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
