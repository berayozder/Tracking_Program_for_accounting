from datetime import datetime
from .connection import get_conn

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
    cur.execute('DELETE FROM inventory')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for r in rows:
        cur.execute('INSERT INTO inventory (category, subcategory, quantity, last_updated) VALUES (?,?,?,?)', (r['category'] or '', r['subcategory'] or '', r['qty'] or 0, now))
    conn.commit()
    if close_conn:
        conn.close()