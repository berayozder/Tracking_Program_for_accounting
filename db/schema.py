"""schema.py

This module defines all tables, indexes, triggers, and views for the accounting
tracking application. Tables are created in dependency order with proper foreign
key constraints, CHECK constraints, and indexes for performance.

"""
from __future__ import annotations


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def add_column_if_missing(cur, table: str, column_def: str) -> None:
    """Add a column if it does not exist in the table.
    
    Args:
        cur: Database cursor
        table: Table name
        column_def: Column definition (e.g., 'amount REAL DEFAULT 0.0')
    """
    col_name = column_def.split()[0]
    cur.execute(f'PRAGMA table_info({table})')
    existing_cols = [r['name'] for r in cur.fetchall()]
    if col_name not in existing_cols:
        cur.execute(f'ALTER TABLE {table} ADD COLUMN {column_def}')


def create_audit_columns() -> str:
    """Return SQL fragment for standard audit columns."""
    return """
        deleted INTEGER DEFAULT 0 CHECK(deleted IN (0, 1)),
        deleted_at TEXT,
        deleted_by TEXT,
        delete_reason TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT
    """


def create_currency_columns(default_currency: str = 'TRY') -> str:
    """Return SQL fragment for currency-related columns.
    
    Args:
        default_currency: Default 3-letter currency code
    """
    return f"""
        currency TEXT DEFAULT '{default_currency}' CHECK(LENGTH(currency) = 3),
        fx_to_base REAL DEFAULT 1.0 CHECK(fx_to_base > 0)
    """


def create_vat_columns(default_rate: float = 18.0) -> str:
    """Return SQL fragment for VAT-related columns.
    
    Args:
        default_rate: Default VAT rate percentage
    """
    return f"""
        vat_rate REAL DEFAULT {default_rate} CHECK(vat_rate >= 0 AND vat_rate <= 100),
        vat_amount REAL DEFAULT 0.0 CHECK(vat_amount >= 0),
        is_vat_inclusive INTEGER DEFAULT 1 CHECK(is_vat_inclusive IN (0, 1))
    """


# ============================================================================
# CORE ENTITY TABLES (No Dependencies)
# ============================================================================

def create_users_table(cur) -> None:
    """Create users table for authentication."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            salt BLOB NOT NULL,
            role TEXT DEFAULT 'user' CHECK(role IN ('user', 'admin')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        )
    ''')


def create_settings_table(cur) -> None:
    """Create settings table for application configuration."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def create_audit_log_table(cur) -> None:
    """Create audit_log table for tracking user actions."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT CURRENT_TIMESTAMP,
            user TEXT,
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            ref_id TEXT,
            details TEXT
        )
    ''')


def create_fx_cache_table(cur) -> None:
    """Create fx_cache table for caching exchange rates."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS fx_cache (
            date TEXT NOT NULL,
            from_ccy TEXT NOT NULL CHECK(LENGTH(from_ccy) = 3),
            to_ccy TEXT NOT NULL CHECK(LENGTH(to_ccy) = 3),
            rate REAL NOT NULL CHECK(rate > 0),
            cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, from_ccy, to_ccy)
        )
    ''')


def create_suppliers_table(cur) -> None:
    """Create suppliers table with proper constraints."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            payment_terms TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        )
    ''')


def create_customers_table(cur) -> None:
    """Create customers table with proper constraints."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        )
    ''')


# ============================================================================
# CATEGORY/PRODUCT HIERARCHY (Normalized Structure)
# ============================================================================

def create_categories_table(cur) -> None:
    """Create categories table (top level of product hierarchy)."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            cat_code TEXT UNIQUE NOT NULL CHECK(LENGTH(cat_code) = 3),
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def create_subcategories_table(cur) -> None:
    """Create subcategories table (belongs to category)."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS subcategories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            sub_code TEXT NOT NULL CHECK(LENGTH(sub_code) = 3),
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
            UNIQUE(category_id, name),
            UNIQUE(category_id, sub_code)
        )
    ''')


def create_products_table(cur) -> None:
    """Create products table (individual product instances)."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT UNIQUE NOT NULL,
            subcategory_id INTEGER NOT NULL,
            serial_number INTEGER NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subcategory_id) REFERENCES subcategories(id) ON DELETE RESTRICT,
            UNIQUE(subcategory_id, serial_number)
        )
    ''')


def create_product_codes_table(cur) -> None:
    """Create product_codes table (legacy compatibility - to be deprecated).
    
    This table maintains backwards compatibility during migration.
    New code should use categories/subcategories/products tables.
    """
    cur.execute('''
        CREATE TABLE IF NOT EXISTS product_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            subcategory TEXT,
            cat_code TEXT CHECK(LENGTH(cat_code) = 3),
            sub_code TEXT CHECK(LENGTH(sub_code) = 3),
            next_serial INTEGER DEFAULT 1 CHECK(next_serial > 0),
            UNIQUE(category, subcategory)
        )
    ''')


# ============================================================================
# TRANSACTION TABLES (With Dependencies)
# ============================================================================

def create_imports_table(cur) -> None:
    """Create imports table for tracking purchases from suppliers."""
    cur.execute(f'''
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            supplier_id INTEGER,
            supplier TEXT,
            ordered_price REAL NOT NULL CHECK(ordered_price >= 0),
            quantity REAL NOT NULL CHECK(quantity > 0),
            category TEXT NOT NULL,
            subcategory TEXT,
            notes TEXT,
            document_path TEXT,
            total_import_expenses REAL DEFAULT 0.0 CHECK(total_import_expenses >= 0),
            include_expenses INTEGER DEFAULT 0 CHECK(include_expenses IN (0, 1)),
            {create_currency_columns()},
            {create_vat_columns()},
            {create_audit_columns()},
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
        )
    ''')


def create_import_lines_table(cur) -> None:
    """Create import_lines table for multi-line imports."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS import_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            ordered_price REAL NOT NULL CHECK(ordered_price >= 0),
            quantity REAL NOT NULL CHECK(quantity > 0),
            FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
        )
    ''')


def create_import_batches_table(cur) -> None:
    """Create import_batches table for FIFO inventory tracking."""
    cur.execute(f'''
        CREATE TABLE IF NOT EXISTS import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_id INTEGER NOT NULL,
            import_line_id INTEGER,
            batch_date TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            supplier TEXT,
            original_quantity REAL NOT NULL CHECK(original_quantity > 0),
            remaining_quantity REAL NOT NULL CHECK(remaining_quantity >= 0),
            unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
            unit_cost_base REAL CHECK(unit_cost_base >= 0),
            unit_cost_orig REAL CHECK(unit_cost_orig >= 0),
            batch_notes TEXT,
            {create_currency_columns()},
            {create_audit_columns()},
            FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE,
            FOREIGN KEY (import_line_id) REFERENCES import_lines(id) ON DELETE SET NULL,
            CHECK(remaining_quantity <= original_quantity)
        )
    ''')


def create_expenses_table(cur) -> None:
    """Create expenses table for tracking business expenses."""
    cur.execute(f'''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            is_import_related INTEGER DEFAULT 0 CHECK(is_import_related IN (0, 1)),
            import_id INTEGER,
            category TEXT,
            notes TEXT,
            document_path TEXT,
            net_amount REAL CHECK(net_amount >= 0),
            gross_amount REAL CHECK(gross_amount >= 0),
            {create_currency_columns()},
            {create_vat_columns()},
            {create_audit_columns()},
            FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE SET NULL
        )
    ''')


def create_expense_import_links_table(cur) -> None:
    """Create junction table for many-to-many expense-import relationship."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS expense_import_links (
            expense_id INTEGER NOT NULL,
            import_id INTEGER NOT NULL,
            PRIMARY KEY (expense_id, import_id),
            FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE,
            FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
        )
    ''')


def create_sales_table(cur) -> None:
    """Create sales table for tracking product sales."""
    cur.execute(f'''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            category TEXT,
            subcategory TEXT,
            customer_id INTEGER,
            quantity REAL NOT NULL CHECK(quantity > 0),
            selling_price REAL NOT NULL CHECK(selling_price >= 0),
            selling_price_base REAL CHECK(selling_price_base >= 0),
            platform TEXT,
            document_path TEXT,
            sale_currency TEXT CHECK(LENGTH(sale_currency) = 3),
            fx_to_base REAL CHECK(fx_to_base > 0),
            {create_vat_columns()},
            voided INTEGER DEFAULT 0 CHECK(voided IN (0, 1)),
            voided_at TEXT,
            voided_by TEXT,
            void_reason TEXT,
            reversal_id INTEGER,
            {create_audit_columns()},
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL,
            FOREIGN KEY (reversal_id) REFERENCES sales(id) ON DELETE SET NULL
        )
    ''')


def create_sale_batch_allocations_table(cur) -> None:
    """Create sale_batch_allocations table for FIFO cost tracking."""
    cur.execute(f'''
        CREATE TABLE IF NOT EXISTS sale_batch_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            sale_id INTEGER,
            sale_date TEXT NOT NULL,
            category TEXT,
            subcategory TEXT,
            batch_id INTEGER NOT NULL,
            quantity REAL,
            quantity_from_batch REAL NOT NULL CHECK(quantity_from_batch > 0),
            unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
            unit_sale_price REAL NOT NULL CHECK(unit_sale_price >= 0),
            profit_per_unit REAL,
            {create_audit_columns()},
            FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE SET NULL,
            FOREIGN KEY (batch_id) REFERENCES import_batches(id) ON DELETE CASCADE
        )
    ''')


def create_returns_table(cur) -> None:
    """Create returns table for tracking product returns."""
    cur.execute(f'''
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            return_date TEXT NOT NULL,
            product_id INTEGER,
            sale_id INTEGER,
            category TEXT,
            subcategory TEXT,
            sale_date TEXT,
            unit_price REAL CHECK(unit_price >= 0),
            selling_price REAL CHECK(selling_price >= 0),
            platform TEXT,
            refund_amount REAL CHECK(refund_amount >= 0),
            refund_currency TEXT CHECK(LENGTH(refund_currency) = 3),
            refund_amount_base REAL CHECK(refund_amount_base >= 0),
            restock INTEGER DEFAULT 0 CHECK(restock IN (0, 1)),
            restock_processed INTEGER DEFAULT 0 CHECK(restock_processed IN (0, 1)),
            reason TEXT,
            doc_paths TEXT,
            {create_audit_columns()},

            FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE SET NULL
        )
    ''')


def create_inventory_table(cur) -> None:
    """Create inventory table for caching current stock levels."""
    cur.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            subcategory TEXT,
            quantity REAL NOT NULL DEFAULT 0 CHECK(quantity >= 0),
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category, subcategory)
        )
    ''')


# ============================================================================
# INDEXES FOR PERFORMANCE
# ============================================================================

def create_indexes(cur) -> None:
    """Create all performance indexes."""
    
    # Supplier indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name)')
    
    # Customer indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name)')
    
    # Category/Product indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_subcategories_category ON subcategories(category_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_products_subcategory ON products(subcategory_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_products_product_id ON products(product_id)')
    
    # Product codes (legacy)
    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_product_codes_cat_sub ON product_codes(category, subcategory)')
    
    # Import indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_imports_supplier ON imports(supplier_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_imports_date ON imports(date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_imports_category ON imports(category, subcategory)')
    
    # Import batch indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_import_batches_import ON import_batches(import_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_import_batches_category ON import_batches(category, subcategory)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_import_batches_date ON import_batches(batch_date)')
    
    # Expense indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_expenses_import ON expenses(import_id)')
    
    # Sales indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id)')
    
    # Sale allocation indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sale_allocations_product ON sale_batch_allocations(product_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sale_allocations_sale ON sale_batch_allocations(sale_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sale_allocations_batch ON sale_batch_allocations(batch_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_sale_allocations_date ON sale_batch_allocations(sale_date)')
    
    # Returns indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_returns_date ON returns(return_date)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_returns_product ON returns(product_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_returns_sale ON returns(sale_id)')
    
    # Audit log indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log(ts)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity, ref_id)')


# ============================================================================
# VIEWS FOR CONVENIENCE
# ============================================================================

def create_views(cur) -> None:
    """Create convenience views for filtering active records."""
    
    cur.execute('''
        CREATE VIEW IF NOT EXISTS active_imports AS
        SELECT * FROM imports WHERE COALESCE(deleted, 0) = 0
    ''')
    
    cur.execute('''
        CREATE VIEW IF NOT EXISTS active_import_batches AS
        SELECT * FROM import_batches WHERE COALESCE(deleted, 0) = 0
    ''')
    
    cur.execute('''
        CREATE VIEW IF NOT EXISTS active_expenses AS
        SELECT * FROM expenses WHERE COALESCE(deleted, 0) = 0
    ''')
    
    cur.execute('''
        CREATE VIEW IF NOT EXISTS active_sales AS
        SELECT * FROM sales 
        WHERE COALESCE(deleted, 0) = 0 AND COALESCE(voided, 0) = 0
    ''')
    
    cur.execute('''
        CREATE VIEW IF NOT EXISTS active_sale_batch_allocations AS
        SELECT * FROM sale_batch_allocations WHERE COALESCE(deleted, 0) = 0
    ''')
    
    cur.execute('''
        CREATE VIEW IF NOT EXISTS active_returns AS
        SELECT * FROM returns WHERE COALESCE(deleted, 0) = 0
    ''')


# ============================================================================
# TRIGGERS FOR DATA INTEGRITY
# ============================================================================

def create_triggers(cur) -> None:
    """Create triggers for enforcing business rules."""
    
    # Trigger: Prevent duplicate cat_code across categories
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
    
    # Trigger: Same checks on update
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


# ============================================================================
# MAIN INITIALIZATION FUNCTION
# ============================================================================

def init_db_schema(conn) -> None:
    """Initialize the complete database schema.
   
    Creates all tables, indexes, triggers, and views in the correct dependency order.
    This function is idempotent - it can be called multiple times safely.
    
    Args:
        conn: SQLite database connection
    """
    cur = conn.cursor()
    
    # Phase 1: Core entity tables (no dependencies)
    create_users_table(cur)
    create_settings_table(cur)
    create_audit_log_table(cur)
    create_fx_cache_table(cur)
    create_suppliers_table(cur)
    create_customers_table(cur)
    
    # Phase 2: Category/Product hierarchy
    create_categories_table(cur)
    create_subcategories_table(cur)
    create_products_table(cur)
    create_product_codes_table(cur)  # Legacy compatibility
    
    # Phase 3: Transaction tables
    create_imports_table(cur)
    create_import_lines_table(cur)
    create_import_batches_table(cur)
    create_expenses_table(cur)
    create_expense_import_links_table(cur)
    create_sales_table(cur)
    create_sale_batch_allocations_table(cur)
    create_returns_table(cur)
    create_inventory_table(cur)
    
    # Phase 4: Indexes, triggers, and views
    create_indexes(cur)
    create_triggers(cur)
    create_views(cur)
    
    # Commit all changes
    conn.commit()
