from .connection import get_conn
from .utils import float_or_none


def list_sales(include_deleted: bool = False):
    """Return sales rows as list of dicts ordered by date ascending (oldest first).
    include_deleted toggles inclusion of soft-deleted rows.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        if include_deleted:
            cur.execute('SELECT * FROM sales ORDER BY datetime(date) ASC, id ASC')
        else:
            cur.execute('SELECT * FROM sales WHERE deleted IS NULL OR deleted=0 ORDER BY datetime(date) ASC, id ASC')
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    finally:
        conn.close()


def add_sale(row: dict) -> int:
    """Insert a sale into the sales table. Returns the new row id.

    Expected keys (case-insensitive): Date, Category, Subcategory, Quantity, SellingPrice, Platform, ProductID,
    CustomerID, DocumentPath, FXToBase, SellingPriceBase, SaleCurrency
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        # Normalize keys
        r = {k.lower(): v for k, v in (row or {}).items()}
        deleted_flag = r.get('deleted')
        try:
            deleted_val = 1 if str(deleted_flag) in ('1', 'True', 'true') else 0
        except Exception:
            deleted_val = 0
        cur.execute('''INSERT INTO sales (date, category, subcategory, quantity, selling_price, platform, product_id, customer_id, document_path, fx_to_base, selling_price_base, sale_currency, deleted)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            r.get('date', ''),
            r.get('category', ''),
            r.get('subcategory', ''),
            float_or_none(r.get('quantity')) or 0,
            float_or_none(r.get('sellingprice') or r.get('selling_price') or r.get('unit_price')) or 0,
            r.get('platform', ''),
            r.get('productid') or r.get('product_id') or '',
            r.get('customerid') or r.get('customer_id') or '',
            r.get('documentpath') or r.get('document_path') or r.get('doc_paths') or '',
            float_or_none(r.get('fxtobase') or r.get('fx_to_base')) or None,
            float_or_none(r.get('sellingpricebase') or r.get('selling_price_base') or r.get('sellingpriceusd')) or None,
            (r.get('salecurrency') or r.get('sale_currency') or '').upper(),
            deleted_val
        ))
        conn.commit()
        nid = cur.lastrowid
        conn.close()
        return nid
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return 0


def overwrite_sales(rows: list) -> int:
    """Replace all sales rows with provided rows. Returns number of rows written."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM sales')
        count = 0
        for r in rows or []:
            add_sale(r)
            count += 1
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        return 0
    finally:
        conn.close()


def get_distinct_sale_platforms():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT platform FROM sales WHERE platform IS NOT NULL AND platform <> '' ORDER BY platform COLLATE NOCASE")
        vals = [r[0] for r in cur.fetchall() if r[0] is not None]
        conn.close()
        return vals
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return []


def undelete_sales_by_indices(indices: list[int]) -> int:
    """Clear Deleted flag for rows specified by zero-based indices in the current sales ordering.
    Returns number of rows updated."""
    try:
        full = list_sales(include_deleted=True)
        ids = []
        for idx in indices:
            if 0 <= idx < len(full):
                row = full[idx]
                if 'id' in row:
                    ids.append(row['id'])
        if not ids:
            return 0
        conn = get_conn()
        cur = conn.cursor()
        q = f"UPDATE sales SET deleted=0 WHERE id IN ({','.join(['?']*len(ids))})"
        cur.execute(q, tuple(ids))
        conn.commit()
        changed = cur.rowcount if cur.rowcount is not None else 0
        conn.close()
        return changed
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return 0


def undelete_sales_by_ids(ids: list[int]) -> int:
    """Clear Deleted flag for sales specified by their DB ids."""
    if not ids:
        return 0
    try:
        conn = get_conn()
        cur = conn.cursor()
        q = f"UPDATE sales SET deleted=0 WHERE id IN ({','.join(['?']*len(ids))})"
        cur.execute(q, tuple(ids))
        conn.commit()
        changed = cur.rowcount if cur.rowcount is not None else 0
        conn.close()
        return changed
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return 0


def mark_sale_deleted(ids: list[int]) -> int:
    """Mark given sale ids as deleted (soft-delete). Returns number of rows updated."""
    if not ids:
        return 0
    try:
        conn = get_conn()
        cur = conn.cursor()
        q = f"UPDATE sales SET deleted=1 WHERE id IN ({','.join(['?']*len(ids))})"
        cur.execute(q, tuple(ids))
        conn.commit()
        changed = cur.rowcount if cur.rowcount is not None else 0
        conn.close()
        return changed
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return 0


def update_sale(sale_id: int, changes: dict) -> bool:
    """Update fields on a sale row. `changes` keys should be DB column names (snake_case).
    Returns True on success.
    """
    if not sale_id or not changes:
        return False
    allowed = {'date','category','subcategory','quantity','selling_price','platform','product_id','customer_id','document_path','fx_to_base','selling_price_base','sale_currency','deleted'}
    sets = []
    params = []
    for k, v in changes.items():
        if k in allowed:
            sets.append(f"{k}=?")
            params.append(v)
    if not sets:
        return False
    params.append(sale_id)
    try:
        conn = get_conn()
        cur = conn.cursor()
        sql = f"UPDATE sales SET {', '.join(sets)} WHERE id=?"
        cur.execute(sql, tuple(params))
        conn.commit()
        conn.close()
        return True
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False
