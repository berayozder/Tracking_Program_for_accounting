from datetime import datetime
from .connection import get_cursor
from contextlib import ExitStack

def get_inventory():
    with get_cursor() as (conn, cur):
        cur.execute('SELECT category, subcategory, quantity, last_updated FROM inventory ORDER BY category, subcategory')
        rows = [dict(r) for r in cur.fetchall()]
    return rows


def update_inventory(category, subcategory, quantity, cur=None):
    """
    Increment inventory for category/subcategory by quantity.
    If `cur` is provided, use it (allows transactional use), else open a new cursor.
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        q = float(quantity or 0)
    except Exception:
        q = 0.0

    if cur is not None:
        cursor = cur
        cursor.execute('SELECT id, quantity FROM inventory WHERE category=? AND subcategory=?',
                       (category or '', subcategory or ''))
        row = cursor.fetchone()
        if row:
            new_q = (row['quantity'] or 0) + q
            cursor.execute('UPDATE inventory SET quantity=?, last_updated=? WHERE id=?',
                           (new_q, now, row['id']))
        else:
            cursor.execute(
                'INSERT INTO inventory (category, subcategory, quantity, last_updated) VALUES (?,?,?,?)',
                (category or '', subcategory or '', q, now)
            )
    else:
        with get_cursor() as (conn, cursor):
            cursor.execute('SELECT id, quantity FROM inventory WHERE category=? AND subcategory=?',
                           (category or '', subcategory or ''))
            row = cursor.fetchone()
            if row:
                new_q = (row['quantity'] or 0) + q
                cursor.execute('UPDATE inventory SET quantity=?, last_updated=? WHERE id=?',
                               (new_q, now, row['id']))
            else:
                cursor.execute(
                    'INSERT INTO inventory (category, subcategory, quantity, last_updated) VALUES (?,?,?,?)',
                    (category or '', subcategory or '', q, now)
                )
            conn.commit()


def rebuild_inventory_from_imports(cur=None):
    """
    Rebuild the inventory table entirely from import totals.
    Can optionally accept a cursor to avoid creating a new connection.
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if cur:
        cursor = cur
        cursor.execute('DELETE FROM inventory')
        cursor.execute('''
            INSERT INTO inventory (category, subcategory, quantity, last_updated)
            SELECT category, subcategory, SUM(quantity), ?
            FROM imports
            GROUP BY category, subcategory
        ''', (now,))
    else:
        with get_cursor() as (conn, cursor):
            cursor.execute('DELETE FROM inventory')
            cursor.execute('''
                INSERT INTO inventory (category, subcategory, quantity, last_updated)
                SELECT category, subcategory, SUM(quantity), ?
                FROM imports
                GROUP BY category, subcategory
            ''', (now,))
            conn.commit()
        close_cursor = True

    try:
        cursor.execute('SELECT category, subcategory, SUM(quantity) as qty FROM active_imports GROUP BY category, subcategory')
    except Exception:
        cursor.execute('SELECT category, subcategory, SUM(quantity) as qty FROM imports GROUP BY category, subcategory')
    
    rows = cursor.fetchall()
    cursor.execute('DELETE FROM inventory')
    
    for r in rows:
        cursor.execute('INSERT INTO inventory (category, subcategory, quantity, last_updated) VALUES (?,?,?,?)',
                       (r['category'] or '', r['subcategory'] or '', r['qty'] or 0, now))

    if close_cursor:
        cursor.connection.commit()
        cursor.__exit__(None, None, None)
    else:
        cursor.connection.commit()
