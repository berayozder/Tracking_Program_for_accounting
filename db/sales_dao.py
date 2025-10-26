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
            try:
                cur.execute('SELECT * FROM active_sales ORDER BY datetime(date) ASC, id ASC')
            except Exception:
                cur.execute(
                    'SELECT * FROM sales WHERE deleted IS NULL OR deleted=0 ORDER BY datetime(date) ASC, id ASC'
                )
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    except Exception as e:
        print("Error in list_sales:", e)
        return []
    finally:
        conn.close()


def add_sale(row: dict) -> int:
    """Insert a sale into the sales table. Returns the new row id."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        r = {k.lower(): v for k, v in (row or {}).items()}

        deleted_flag = str(r.get('deleted')).lower()
        deleted_val = 1 if deleted_flag in ('1', 'true', 'yes', 'y') else 0

        cur.execute(
            '''INSERT INTO sales (
                date, category, subcategory, quantity, selling_price, platform, product_id,
                customer_id, document_path, fx_to_base, selling_price_base, sale_currency, deleted
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (
                r.get('date', ''),
                r.get('category', ''),
                r.get('subcategory', ''),
                float_or_none(r.get('quantity')) or 0,
                float_or_none(r.get('sellingprice') or r.get('selling_price') or r.get('unit_price')) or 0,
                r.get('platform', ''),
                r.get('productid') or r.get('product_id') or '',
                r.get('customerid') or r.get('customer_id') or '',
                r.get('documentpath') or r.get('document_path') or r.get('doc_paths') or '',
                float_or_none(r.get('fxtobase') or r.get('fx_to_base')),
                float_or_none(r.get('sellingpricebase') or r.get('selling_price_base') or r.get('sellingpriceusd')),
                (r.get('salecurrency') or r.get('sale_currency') or '').upper(),
                deleted_val
            )
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        print("Error in add_sale:", e)
        conn.rollback()
        return 0
    finally:
        conn.close()


def overwrite_sales(rows: list) -> int:
    """Replace all sales rows with provided rows. Returns number of rows written."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM sales')
        count = 0
        for r in rows or []:
            # inline insert instead of calling add_sale (to reuse connection)
            rr = {k.lower(): v for k, v in (r or {}).items()}
            deleted_flag = str(rr.get('deleted')).lower()
            deleted_val = 1 if deleted_flag in ('1', 'true', 'yes', 'y') else 0
            cur.execute(
                '''INSERT INTO sales (
                    date, category, subcategory, quantity, selling_price, platform, product_id,
                    customer_id, document_path, fx_to_base, selling_price_base, sale_currency, deleted
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    rr.get('date', ''),
                    rr.get('category', ''),
                    rr.get('subcategory', ''),
                    float_or_none(rr.get('quantity')) or 0,
                    float_or_none(rr.get('sellingprice') or rr.get('selling_price') or rr.get('unit_price')) or 0,
                    rr.get('platform', ''),
                    rr.get('productid') or rr.get('product_id') or '',
                    rr.get('customerid') or rr.get('customer_id') or '',
                    rr.get('documentpath') or rr.get('document_path') or rr.get('doc_paths') or '',
                    float_or_none(rr.get('fxtobase') or rr.get('fx_to_base')),
                    float_or_none(rr.get('sellingpricebase') or rr.get('selling_price_base') or rr.get('sellingpriceusd')),
                    (rr.get('salecurrency') or rr.get('sale_currency') or '').upper(),
                    deleted_val
                )
            )
            count += 1
        conn.commit()
        return count
    except Exception as e:
        print("Error in overwrite_sales:", e)
        conn.rollback()
        return 0
    finally:
        conn.close()


def get_distinct_sale_platforms():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT DISTINCT platform FROM sales WHERE platform IS NOT NULL AND platform <> '' ORDER BY platform COLLATE NOCASE"
        )
        vals = [r[0] for r in cur.fetchall() if r[0] is not None]
        return vals
    except Exception as e:
        print("Error in get_distinct_sale_platforms:", e)
        return []
    finally:
        conn.close()


def undelete_sales_by_indices(indices: list[int]) -> int:
    """Clear Deleted flag for rows specified by zero-based indices."""
    try:
        full = list_sales(include_deleted=True)
        ids = [
            row['id'] for i, row in enumerate(full)
            if 0 <= i < len(full) and 'id' in row and i in indices
        ]
        if not ids:
            return 0

        conn = get_conn()
        cur = conn.cursor()
        q = f"UPDATE sales SET deleted=0 WHERE id IN ({','.join(['?']*len(ids))})"
        cur.execute(q, tuple(ids))
        conn.commit()
        return cur.rowcount or 0
    except Exception as e:
        print("Error in undelete_sales_by_indices:", e)
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


def undelete_sales_by_ids(ids: list[int]) -> int:
    """Clear Deleted flag for sales specified by their DB ids."""
    if not ids:
        return 0
    conn = get_conn()
    cur = conn.cursor()
    try:
        q = f"UPDATE sales SET deleted=0 WHERE id IN ({','.join(['?']*len(ids))})"
        cur.execute(q, tuple(ids))
        conn.commit()
        return cur.rowcount or 0
    except Exception as e:
        print("Error in undelete_sales_by_ids:", e)
        conn.rollback()
        return 0
    finally:
        conn.close()


def mark_sale_deleted(ids: list[int]) -> int:
    """Mark given sale ids as deleted (soft-delete)."""
    if not ids:
        return 0
    conn = get_conn()
    cur = conn.cursor()
    try:
        q = f"UPDATE sales SET deleted=1 WHERE id IN ({','.join(['?']*len(ids))})"
        cur.execute(q, tuple(ids))
        conn.commit()
        return cur.rowcount or 0
    except Exception as e:
        print("Error in mark_sale_deleted:", e)
        conn.rollback()
        return 0
    finally:
        conn.close()


def update_sale(sale_id: int, changes: dict) -> bool:
    """Update fields on a sale row. `changes` keys should be DB column names (snake_case)."""
    if not sale_id or not changes:
        return False

    allowed = {
        'date', 'category', 'subcategory', 'quantity', 'selling_price', 'platform',
        'product_id', 'customer_id', 'document_path', 'fx_to_base', 'selling_price_base',
        'sale_currency', 'deleted'
    }

    sets, params = [], []
    for k, v in changes.items():
        if k in allowed:
            sets.append(f"{k}=?")
            params.append(v)
    if not sets:
        return False
    params.append(sale_id)

    conn = get_conn()
    cur = conn.cursor()
    try:
        sql = f"UPDATE sales SET {', '.join(sets)} WHERE id=?"
        cur.execute(sql, tuple(params))
        conn.commit()
        return True
    except Exception as e:
        print("Error in update_sale:", e)
        conn.rollback()
        return False
    finally:
        conn.close()
