import sqlite3
from pathlib import Path
import csv
from datetime import datetime

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "app.db"
IMPORTS_CSV = Path(__file__).resolve().parents[1] / "data" / "imports.csv"
INVENTORY_CSV = Path(__file__).resolve().parents[1] / "data" / "inventory.csv"
SUPPLIERS_CSV = Path(__file__).resolve().parents[1] / "data" / "suppliers.csv"


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(migrate_csv=True):
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
        subcategory TEXT
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
        document_path TEXT
    )
    ''')
    # Add document_path column if upgrading from older schema
    try:
        cur.execute('PRAGMA table_info(expenses)')
        cols = [row['name'] for row in cur.fetchall()]
        if 'document_path' not in cols:
            cur.execute('ALTER TABLE expenses ADD COLUMN document_path TEXT')
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
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (import_id) REFERENCES imports(id) ON DELETE CASCADE
    )
    ''')
    
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

    if migrate_csv:
        migrate_csv_to_db(conn)

    return conn


def migrate_csv_to_db(conn=None):
    close_conn = False
    if conn is None:
        conn = get_conn()
        close_conn = True

    cur = conn.cursor()
    # import CSVs if present and not already in DB
    if IMPORTS_CSV.exists():
        with IMPORTS_CSV.open(newline='') as f:
            reader = csv.DictReader(f)
            for r in reader:
                # check if similar row exists (by date, category, subcategory, quantity)
                cur.execute('''SELECT id FROM imports WHERE date=? AND category=? AND subcategory=? AND quantity=? LIMIT 1''',
                            (r.get('Date'), r.get('Category'), r.get('Subcategory'), r.get('Quantity')))
                if cur.fetchone():
                    continue
                # Optional link supplier_id using suppliers.csv (create if missing)
                supplier_name = (r.get('Supplier') or '').strip()
                supplier_id = None
                if supplier_name:
                    try:
                        supplier_id = find_or_create_supplier(supplier_name)
                    except Exception:
                        supplier_id = None
                cur.execute('''INSERT INTO imports (date, ordered_price, quantity, supplier, supplier_id, notes, category, subcategory)
                            VALUES (?,?,?,?,?,?,?,?)''', (
                    r.get('Date'), float_or_none(r.get('OrderedPrice')), float_or_none(r.get('Quantity')), supplier_name, supplier_id, r.get('Notes'), r.get('Category'), r.get('Subcategory')
                ))
    conn.commit()

    # rebuild inventory from imports
    rebuild_inventory_from_imports(conn)

    # migrate expenses.csv if present
    if IMPORTS_CSV.parent.joinpath('expenses.csv').exists():
        EXP_CSV = IMPORTS_CSV.parent.joinpath('expenses.csv')
        with EXP_CSV.open(newline='') as f:
            reader = csv.DictReader(f)
            for r in reader:
                # check if similar exists
                cur.execute('''SELECT id FROM expenses WHERE date=? AND amount=? AND description=? LIMIT 1''',
                            (r.get('Date'), float_or_none(r.get('Amount')), r.get('Description')))
                if cur.fetchone():
                    continue
                is_imp = 1 if (r.get('IsImportRelated') or '').strip().lower() in ('1', 'true', 'yes') else 0
                imp_id = r.get('ImportID') or None
                cur.execute('''INSERT INTO expenses (date, amount, description, is_import_related, import_id, category, notes)
                            VALUES (?,?,?,?,?,?,?)''', (
                    r.get('Date'), float_or_none(r.get('Amount')), r.get('Description'), is_imp, imp_id, r.get('Category'), r.get('Notes')
                ))
        conn.commit()

    if close_conn:
        conn.close()


def float_or_none(v):
    try:
        return float(v)
    except Exception:
        return None


def add_import(date, ordered_price, quantity, supplier, notes, category, subcategory):
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

    cur.execute('''INSERT INTO imports (date, ordered_price, quantity, supplier, supplier_id, notes, category, subcategory)
                VALUES (?,?,?,?,?,?,?,?)''', (date, ordered_price, quantity, supplier_name, supplier_id, notes, category, subcategory))
    
    import_id = cur.lastrowid
    conn.commit()
    
    # Create batch for this import for FIFO tracking
    create_import_batch(import_id, date, category, subcategory, quantity, ordered_price, supplier, notes)
    
    # update inventory
    update_inventory(category, subcategory, quantity, conn)
    conn.close()


def get_imports(limit=500):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, date, ordered_price, quantity, supplier, notes, category, subcategory FROM imports ORDER BY id DESC LIMIT ?', (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def edit_import(import_id, date, ordered_price, quantity, supplier, notes, category, subcategory):
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

    # Update import record
    cur.execute('''UPDATE imports SET date=?, ordered_price=?, quantity=?, supplier=?, supplier_id=?, notes=?, category=?, subcategory=? WHERE id=?''',
                (date, ordered_price, quantity, supplier_name, supplier_id, notes, category, subcategory, import_id))
    
    # Update corresponding batch record
    cur.execute('''UPDATE import_batches 
                   SET batch_date=?, category=?, subcategory=?, unit_cost=?, supplier=?, batch_notes=?, 
                       original_quantity=?, remaining_quantity=remaining_quantity+(?)-(original_quantity)
                   WHERE import_id=?''',
                (date, category, subcategory, ordered_price, supplier, notes, quantity, quantity, import_id))
    
    conn.commit()
    # rebuild inventory to remain consistent
    rebuild_inventory_from_imports(conn)
    conn.close()


def delete_import(import_id):
    conn = get_conn()
    cur = conn.cursor()
    
    # Delete associated batch (CASCADE will handle sale allocations)
    cur.execute('DELETE FROM import_batches WHERE import_id=?', (import_id,))
    
    # Delete import record
    cur.execute('DELETE FROM imports WHERE id=?', (import_id,))
    conn.commit()
    rebuild_inventory_from_imports(conn)
    conn.close()


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


def add_expense(date, amount, is_import_related=False, import_id=None, category=None, notes=None, document_path=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''INSERT INTO expenses (date, amount, is_import_related, import_id, category, notes, document_path)
                VALUES (?,?,?,?,?,?,?)''', (date, amount, 1 if is_import_related else 0, import_id, category, notes, document_path))
    conn.commit()
    conn.close()


def get_expenses(limit=500):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, date, amount, is_import_related, import_id, category, notes, document_path FROM expenses ORDER BY id DESC LIMIT ?', (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def edit_expense(expense_id, date, amount, is_import_related=False, import_id=None, category=None, notes=None, document_path=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''UPDATE expenses SET date=?, amount=?, is_import_related=?, import_id=?, category=?, notes=?, document_path=? WHERE id=?''',
                (date, amount, 1 if is_import_related else 0, import_id, category, notes, document_path, expense_id))
    conn.commit()
    conn.close()


def delete_expense(expense_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM expenses WHERE id=?', (expense_id,))
    conn.commit()
    conn.close()


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

def create_import_batch(import_id, date, category, subcategory, quantity, unit_cost, supplier, notes=""):
    """Create a new batch from an import with full quantity available for allocation."""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
        INSERT INTO import_batches (import_id, batch_date, category, subcategory, 
                                   original_quantity, remaining_quantity, unit_cost, supplier, batch_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (import_id, date, category or '', subcategory or '', quantity, quantity, unit_cost, supplier or '', notes or ''))
    
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
                   unit_cost, supplier, batch_notes, import_id
            FROM import_batches 
            WHERE category = ? AND subcategory = ? AND remaining_quantity > 0
        '''
        params = (category, subcategory)
    else:
        query = '''
            SELECT id, batch_date, category, subcategory, original_quantity, remaining_quantity, 
                   unit_cost, supplier, batch_notes, import_id
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


def allocate_sale_to_batches(product_id, sale_date, category, subcategory, quantity, unit_sale_price):
    """
    Allocate a sale to available batches using FIFO (First In, First Out).
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
        unit_cost = batch['unit_cost']
        
        # Allocate as much as possible from this batch
        allocated_from_batch = min(remaining_to_allocate, batch_available)
        
        # Calculate profit
        profit_per_unit = unit_sale_price - unit_cost
        
        # Record allocation
        cur.execute('''
            INSERT INTO sale_batch_allocations 
            (product_id, sale_date, category, subcategory, batch_id, quantity_from_batch, 
             unit_cost, unit_sale_price, profit_per_unit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (product_id, sale_date, category or '', subcategory or '', batch_id, 
              allocated_from_batch, unit_cost, unit_sale_price, profit_per_unit))
        
        # Update batch remaining quantity
        new_remaining = batch_available - allocated_from_batch
        cur.execute('UPDATE import_batches SET remaining_quantity = ? WHERE id = ?', 
                   (new_remaining, batch_id))
        
        allocations.append({
            'batch_id': batch_id,
            'batch_date': batch['batch_date'],
            'supplier': batch['supplier'],
            'quantity_allocated': allocated_from_batch,
            'unit_cost': unit_cost,
            'unit_sale_price': unit_sale_price,
            'profit_per_unit': profit_per_unit,
            'total_cost': allocated_from_batch * unit_cost,
            'total_revenue': allocated_from_batch * unit_sale_price,
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
            'unit_sale_price': unit_sale_price,
            'profit_per_unit': unit_sale_price,
            'total_cost': 0.0,
            'total_revenue': remaining_to_allocate * unit_sale_price,
            'total_profit': remaining_to_allocate * unit_sale_price
        })
    
    return allocations


def get_sale_batch_info(product_id):
    """Get detailed batch allocation information for a specific sale."""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT sba.*, ib.batch_date, ib.supplier, ib.batch_notes
        FROM sale_batch_allocations sba
        LEFT JOIN import_batches ib ON sba.batch_id = ib.id
        WHERE sba.product_id = ?
        ORDER BY sba.id
    ''', (product_id,))
    
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_batch_utilization_report():
    """Generate comprehensive batch utilization and profit report."""
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


def get_profit_analysis_by_sale():
    """Get detailed profit analysis for each sale with batch breakdown."""
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT 
            sba.product_id,
            sba.sale_date,
            sba.category,
            sba.subcategory,
            SUM(sba.quantity_from_batch) as total_quantity,
            ROUND(SUM(sba.quantity_from_batch * sba.unit_cost), 2) as total_cost,
            ROUND(SUM(sba.quantity_from_batch * sba.unit_sale_price), 2) as total_revenue,
            ROUND(SUM(sba.quantity_from_batch * sba.profit_per_unit), 2) as total_profit,
            ROUND(SUM(sba.quantity_from_batch * sba.profit_per_unit) / 
                  NULLIF(SUM(sba.quantity_from_batch * sba.unit_cost), 0) * 100, 2) as profit_margin_percent,
            COUNT(DISTINCT sba.batch_id) as batches_used
        FROM sale_batch_allocations sba
        GROUP BY sba.product_id
        ORDER BY sba.sale_date DESC
    ''')
    
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


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
