from .connection import get_conn
from datetime import datetime
from typing import Optional

def get_product_code(category, subcategory):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT category, subcategory, cat_code, sub_code, next_serial FROM product_codes WHERE category=? AND subcategory=?', (category or '', subcategory or ''))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def set_product_code(category, subcategory, cat_code, sub_code, next_serial=1):
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
    cur.execute('SELECT DISTINCT category FROM product_codes WHERE cat_code=?', (cat_code,))
    rows = [r['category'] for r in cur.fetchall()]
    if rows and any((c or '') != (category or '') for c in rows):
        conn.close()
        raise ValueError(f"cat_code {cat_code} already used by a different category")
    cur.execute('SELECT DISTINCT cat_code FROM product_codes WHERE category=?', (category or '',))
    codes = [r['cat_code'] for r in cur.fetchall()]
    codes = [c for c in codes if c]
    if codes and any(c != cat_code for c in codes):
        conn.close()
        raise ValueError(f"Category '{category}' is already mapped to a different cat_code ({codes[0]})")
    cur.execute('SELECT subcategory FROM product_codes WHERE category=? AND sub_code=?', (category or '', sub_code))
    owner_subs = [r['subcategory'] for r in cur.fetchall()]
    if owner_subs and any((s or '') != (subcategory or '') for s in owner_subs):
        conn.close()
        raise ValueError(f"sub_code {sub_code} already used by a different subcategory in '{category}'")
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
    if year_prefix:
        yy = str(year_prefix)[-2:]
    else:
        yy = datetime.now().strftime('%y')
    for i in range(start, start + c):
        ids.append(f"{yy}{cat_code}{sub_code}{str(i).zfill(4)}")
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
        cur.execute('INSERT INTO product_codes (category, subcategory, cat_code, sub_code, next_serial) VALUES (?,?,?,?,?)', (category or '', subcategory or '', '000', '000', ns))
    conn.commit()
    conn.close()


def delete_product_code(category, subcategory):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM product_codes WHERE category=? AND subcategory=?', (category or '', subcategory or ''))
    conn.commit()
    conn.close()