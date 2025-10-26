from .connection import get_conn
from datetime import datetime

# ---------------- CUSTOMER MANAGEMENT ----------------

def _row_to_dict(row, cols):
    """Convert a DB row (sqlite3.Row or tuple) to dict given column names."""
    if row is None:
        return None
    if hasattr(row, "keys"):
        # sqlite3.Row or mapping-like
        return {k: row[k] for k in row.keys()}
    # tuple/list -> map by provided cols
    return {cols[i]: row[i] for i in range(min(len(cols), len(row)))}


def get_next_customer_id():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT customer_id FROM customers ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        # normalize result retrieval
        if not row:
            return "CUST001"
        # row may be tuple or sqlite3.Row; prefer first column value
        last = row[0] if isinstance(row, (list, tuple)) or (hasattr(row, "__getitem__") and not hasattr(row, "keys")) else (row['customer_id'] if hasattr(row, 'keys') and 'customer_id' in row.keys() else None)
        if not last or not isinstance(last, str) or not last.startswith('CUST'):
            return "CUST001"
        try:
            num = int(last[4:])
            return f"CUST{num + 1:03d}"
        except Exception:
            return "CUST001"
    except Exception:
        return "CUST001"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def add_customer(name, email='', phone='', address='', notes=''):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cid = get_next_customer_id()
        created_date = datetime.now().strftime('%Y-%m-%d')
        cur.execute('''
            INSERT INTO customers(customer_id, name, email, phone, address, notes, created_date)
            VALUES (?,?,?,?,?,?,?)
        ''', (cid, name.strip(), email.strip(), phone.strip(), address.strip(), notes.strip(), created_date))
        conn.commit()
        return cid
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def read_customers():
    cols = ['customer_id', 'name', 'email', 'phone', 'address', 'notes', 'created_date']
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT customer_id, name, email, phone, address, notes, created_date FROM customers ORDER BY id DESC')
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(_row_to_dict(r, cols))
        return out
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def write_customers(customers):
    try:
        conn = get_conn()
        cur = conn.cursor()
        # Replace all customers with provided list
        cur.execute('DELETE FROM customers')
        for c in (customers or []):
            cur.execute('''
                INSERT INTO customers(customer_id, name, email, phone, address, notes, created_date)
                VALUES (?,?,?,?,?,?,?)
            ''', (
                c.get('customer_id'), c.get('name'), c.get('email'),
                c.get('phone'), c.get('address'), c.get('notes'), c.get('created_date')
            ))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def find_customer_by_name(name):
    name_lower = (name or '').lower().strip()
    if not name_lower:
        return []
    cols = ['customer_id', 'name', 'email', 'phone', 'address', 'notes', 'created_date']
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT customer_id, name, email, phone, address, notes, created_date FROM customers WHERE LOWER(name) LIKE ? LIMIT 50', (f'%{name_lower}%',))
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(_row_to_dict(r, cols))
        return out
    except Exception:
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


def find_or_create_customer(name):
    if not name or not name.strip():
        return None
    search_name = name.strip()
    existing = find_customer_by_name(search_name)
    if existing:
        # return the first matching customer's customer_id
        first = existing[0]
        if isinstance(first, dict):
            return first.get('customer_id')
    return add_customer(search_name)


def get_customer_name_suggestions():
    customers = read_customers()
    names = []
    for customer in customers:
        if not customer:
            continue
        name = customer.get('name', '').strip()
        if name:
            names.append(name)
    return sorted(set(names))


def edit_customer(customer_id, name='', email='', phone='', address='', notes=''):
    customers = read_customers()
    target_id = (customer_id or '').strip()
    if not target_id:
        return False
    for i, customer in enumerate(customers):
        if (customer.get('customer_id') or '').strip() == target_id:
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
    customers = read_customers()
    target_id = (customer_id or '').strip()
    if not target_id:
        return False
    original_count = len(customers)
    customers = [c for c in customers if (c.get('customer_id') or '').strip() != target_id]
    if len(customers) < original_count:
        write_customers(customers)
        return True
    return False


def get_customer_sales_summary(customer_id):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM sales WHERE customer_id=? AND (deleted IS NULL OR deleted=0) ORDER BY datetime(date) DESC', (customer_id.strip(),))
        rows = cur.fetchall()
        sales_rows = [dict(r) if hasattr(r, 'keys') else dict(r) for r in rows]
        total_revenue = 0.0
        for row in sales_rows:
            try:
                total_revenue += float(row.get('selling_price') or row.get('SellingPrice') or 0)
            except Exception:
                pass
        return {
            'total_sales': len(sales_rows),
            'total_revenue': total_revenue,
            'sales_count': len(sales_rows),
            'recent_sales': sales_rows[:10]
        }
    except Exception:
        return {'total_sales': 0, 'total_revenue': 0.0, 'sales_count': 0, 'recent_sales': []}
    finally:
        try:
            conn.close()
        except Exception:
            pass
