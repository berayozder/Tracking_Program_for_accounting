from .connection import get_conn
from datetime import datetime

# ---------------- CUSTOMER MANAGEMENT ----------------
def get_next_customer_id():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT customer_id FROM customers ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if not row:
            return "CUST001"
        last = row[0] if isinstance(row, (list, tuple)) else row['customer_id'] if hasattr(row, 'keys') else str(row)
        if not last or not last.startswith('CUST'):
            return "CUST001"
        try:
            num = int(last[4:])
            return f"CUST{num + 1:03d}"
        except Exception:
            return "CUST001"
    except Exception:
        return "CUST001"


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
        conn.close()
        return cid
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return None


def read_customers():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT customer_id, name, email, phone, address, notes, created_date FROM customers ORDER BY id DESC')
        rows = cur.fetchall()
        conn.close()
        out = []
        for r in rows:
            if hasattr(r, 'keys'):
                out.append({k: r[k] for k in r.keys()})
            else:
                out.append(dict(r))
        return out
    except Exception:
        return []


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
                c.get('customer_id'), c.get('name'), c.get('email'), c.get('phone'), c.get('address'), c.get('notes'), c.get('created_date')
            ))
        conn.commit()
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def find_customer_by_name(name):
    name_lower = (name or '').lower().strip()
    if not name_lower:
        return []
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT customer_id, name, email, phone, address, notes, created_date FROM customers WHERE LOWER(name) LIKE ? LIMIT 50', (f'%{name_lower}%',))
        rows = cur.fetchall()
        conn.close()
        out = []
        for r in rows:
            if hasattr(r, 'keys'):
                out.append({k: r[k] for k in r.keys()})
            else:
                out.append(dict(r))
        return out
    except Exception:
        return []
        if customer.get('name', '').lower().strip() == name_lower:
            return customer
    return None


def find_or_create_customer(name):
    if not name or not name.strip():
        return None
    existing = find_customer_by_name(name.strip())
    if existing:
        return existing['customer_id']
    return add_customer(name.strip())


def get_customer_name_suggestions():
    customers = read_customers()
    names = []
    for customer in customers:
        name = customer.get('name', '').strip()
        if name:
            names.append(name)
    return sorted(set(names))


def edit_customer(customer_id, name='', email='', phone='', address='', notes=''):
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
    customers = read_customers()
    original_count = len(customers)
    customers = [c for c in customers if c.get('customer_id', '').strip() != customer_id.strip()]
    if len(customers) < original_count:
        write_customers(customers)
        return True
    return False


def get_customer_sales_summary(customer_id):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('SELECT * FROM sales WHERE customer_id=? AND (deleted IS NULL OR deleted=0) ORDER BY datetime(date) DESC', (customer_id.strip(),))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        total_revenue = 0.0
        for row in rows:
            try:
                total_revenue += float(row.get('selling_price') or row.get('SellingPrice') or 0)
            except Exception:
                pass
        return {
            'total_sales': len(rows),
            'total_revenue': total_revenue,
            'sales_count': len(rows),
            'recent_sales': rows[:10]
        }
    except Exception:
        return {'total_sales': 0, 'total_revenue': 0.0, 'sales_count': 0, 'recent_sales': []}
