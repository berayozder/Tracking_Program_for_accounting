from .connection import get_conn, get_cursor
from datetime import datetime


# ---------------- SUPPLIER MANAGEMENT (DB-backed) ----------------

def _ensure_suppliers_table():
    try:
        with get_cursor() as (conn, cur):
            cur.execute('''
                CREATE TABLE IF NOT EXISTS suppliers (
                    supplier_id TEXT PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    phone TEXT,
                    address TEXT,
                    payment_terms TEXT,
                    notes TEXT,
                    created_date TEXT
                )
            ''')
            conn.commit()
    except Exception:
        pass


def read_suppliers() -> list:
    """Return list of suppliers as dicts from the DB.

    Maintains the same dict shape used by the UI code.
    """
    try:
        _ensure_suppliers_table()
        with get_cursor() as (conn, cur):
            cur.execute('SELECT supplier_id, name, email, phone, address, payment_terms, notes, created_date FROM suppliers ORDER BY name')
            rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({
                'supplier_id': r['supplier_id'],
                'name': r['name'],
                'email': r['email'],
                'phone': r['phone'],
                'address': r['address'],
                'payment_terms': r['payment_terms'],
                'notes': r['notes'],
                'created_date': r['created_date'],
            })
        return out
    except Exception:
        return []


def write_suppliers(suppliers: list) -> None:
    """Overwrite suppliers in the DB using an upsert behavior.

    The input is expected as a list of dicts with supplier fields.
    """
    try:
        _ensure_suppliers_table()
        with get_cursor() as (conn, cur):
            for s in suppliers:
                sid = (s.get('supplier_id') or '').strip()
                if not sid:
                    continue
                cur.execute('''
                    INSERT INTO suppliers(supplier_id, name, email, phone, address, payment_terms, notes, created_date)
                    VALUES (?,?,?,?,?,?,?,?)
                    ON CONFLICT(supplier_id) DO UPDATE SET
                        name=excluded.name,
                        email=excluded.email,
                        phone=excluded.phone,
                        address=excluded.address,
                        payment_terms=excluded.payment_terms,
                        notes=excluded.notes,
                        created_date=excluded.created_date
                ''', (
                    sid,
                    s.get('name',''),
                    s.get('email',''),
                    s.get('phone',''),
                    s.get('address',''),
                    s.get('payment_terms',''),
                    s.get('notes',''),
                    s.get('created_date',''),
                ))
            conn.commit()
    except Exception:
        pass


def get_next_supplier_id():
    try:
        _ensure_suppliers_table()
        with get_cursor() as (conn, cur):
            cur.execute("SELECT supplier_id FROM suppliers WHERE supplier_id LIKE 'SUP%'")
            rows = cur.fetchall()
        max_num = 0
        for r in rows:
            sid = (r['supplier_id'] or '').strip()
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
    try:
        _ensure_suppliers_table()
        supplier_id = get_next_supplier_id()
        created_date = datetime.now().strftime('%Y-%m-%d')
        with get_cursor() as (conn, cur):
            cur.execute('''
                INSERT INTO suppliers(supplier_id, name, email, phone, address, payment_terms, notes, created_date)
                VALUES (?,?,?,?,?,?,?,?)
            ''', (
                supplier_id,
                (name or '').strip(),
                (email or '').strip(),
                (phone or '').strip(),
                (address or '').strip(),
                (payment_terms or '').strip(),
                (notes or '').strip(),
                created_date,
            ))
            conn.commit()
        return supplier_id
    except Exception:
        return None


def find_supplier_by_name(name):
    if not name:
        return None
    try:
        _ensure_suppliers_table()
        with get_cursor() as (conn, cur):
            cur.execute('SELECT supplier_id, name, email, phone, address, payment_terms, notes, created_date FROM suppliers WHERE LOWER(TRIM(name)) = ? LIMIT 1', (name.strip().lower(),))
            row = cur.fetchone()
        if not row:
            return None
        return {
            'supplier_id': row['supplier_id'],
            'name': row['name'],
            'email': row['email'],
            'phone': row['phone'],
            'address': row['address'],
            'payment_terms': row['payment_terms'],
            'notes': row['notes'],
            'created_date': row['created_date'],
        }
    except Exception:
        return None


def find_or_create_supplier(name):
    if not name or not name.strip():
        return None
    s = find_supplier_by_name(name)
    if s:
        return s.get('supplier_id')
    return add_supplier(name=name)


def edit_supplier(supplier_id, name=None, email=None, phone=None, address=None, payment_terms=None, notes=None):
    try:
        _ensure_suppliers_table()
        # Build update parts
        fields = {}
        if name is not None:
            fields['name'] = name
        if email is not None:
            fields['email'] = email
        if phone is not None:
            fields['phone'] = phone
        if address is not None:
            fields['address'] = address
        if payment_terms is not None:
            fields['payment_terms'] = payment_terms
        if notes is not None:
            fields['notes'] = notes
        if not fields:
            return False
        set_clause = ', '.join([f"{k} = ?" for k in fields.keys()])
        params = list(fields.values()) + [supplier_id]
        with get_cursor() as (conn, cur):
            cur.execute(f'UPDATE suppliers SET {set_clause} WHERE supplier_id = ?', params)
            conn.commit()
            updated = cur.rowcount > 0
        return bool(updated)
    except Exception:
        return False


def delete_supplier(supplier_id):
    try:
        _ensure_suppliers_table()
        with get_cursor() as (conn, cur):
            cur.execute('DELETE FROM suppliers WHERE supplier_id = ?', (supplier_id,))
            conn.commit()
            deleted = cur.rowcount > 0
        return bool(deleted)
    except Exception:
        return False


def get_supplier_purchases_summary(supplier_id):
    try:
        with get_cursor() as (conn, cur):
            cur.execute('''SELECT COUNT(*) as cnt, COALESCE(SUM(ordered_price * quantity), 0) as total, MAX(date) as last_date
                           FROM imports WHERE supplier_id = ?''', (supplier_id,))
            row = cur.fetchone()
        return {
            'import_count': int(row['cnt'] or 0) if row else 0,
            'total_purchases': float(row['total'] or 0.0) if row else 0.0,
            'last_purchase': row['last_date'] if row else None
        }
    except Exception:
        return {'import_count': 0, 'total_purchases': 0.0, 'last_purchase': None}


def get_supplier_name_suggestions():
    try:
        _ensure_suppliers_table()
        with get_cursor() as (conn, cur):
            cur.execute('SELECT DISTINCT name FROM suppliers')
            rows = cur.fetchall()
        names = [ (r[0] or '').strip() for r in rows if r and r[0] ]
        return sorted({n for n in names if n})
    except Exception:
        return []