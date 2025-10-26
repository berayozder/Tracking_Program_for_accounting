from datetime import datetime
from typing import Optional
from .connection import get_cursor
from .audit import write_audit
import traceback


def _now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def soft_delete_entity(table: str, id_col: str, id_value, by: Optional[str] = None, reason: Optional[str] = None) -> bool:
    """Mark a row as deleted and record metadata. Returns True on success."""
    try:
        with get_cursor() as (conn, cur):
            q = f"UPDATE {table} SET deleted=1, deleted_at=?, deleted_by=?, delete_reason=? WHERE {id_col}=?"
            cur.execute(q, (_now_str(), by or '', reason or '', id_value))
            try:
                write_audit('soft_delete', table, str(id_value), f"by={by}; reason={reason}",cur=cur)
            except Exception:
                pass
        return True
    except Exception:
        traceback.print_exc()
        return False


def restore_entity(table: str, id_col: str, id_value) -> bool:
    """Restore a previously soft-deleted row (clear deleted flags and metadata)."""
    try:
        with get_cursor() as (conn, cur):
            q = f"UPDATE {table} SET deleted=0, deleted_at=NULL, deleted_by=NULL, delete_reason=NULL WHERE {id_col}=?"
            cur.execute(q, (id_value,))
            try:
                write_audit('restore', table, str(id_value), '',cur=cur)
            except Exception:
                pass
        return True
    except Exception:
        return False


def void_transaction(table: str, id_col: str, id_value, by: Optional[str] = None, reason: Optional[str] = None) -> bool:
    """Mark a financial transaction as voided. Does not create reversal rows.

    For immutable accounting records you should prefer creating a reversing transaction
    and mark the original as voided; use `void_sale` convenience helper for sales.
    """
    try:
        with get_cursor() as (conn, cur):
            q = f"UPDATE {table} SET voided=1, voided_at=?, voided_by=?, void_reason=? WHERE {id_col}=?"
            cur.execute(q, (_now_str(), by or '', reason or '', id_value))
            try:
                write_audit('void', table, str(id_value), f"by={by}; reason={reason}",cur=cur)
            except Exception:
                pass
        return True
    except Exception:
        return False


def void_sale(sale_id: int, by: Optional[str] = None, reason: Optional[str] = None, create_reversal: bool = False) -> bool:
    """Void a sale. Optionally create a reversing sale row that negates quantity/revenue.

    If create_reversal is True, a new sale row is inserted with negated quantity
    and selling_price_base so ledger sums remain balanced; the original sale's
    `reversal_id` will point to the new row.
    """
    try:
        with get_cursor() as (conn, cur):
            cur.execute('SELECT * FROM sales WHERE id=?', (sale_id,))
            row = cur.fetchone()
            if not row:
                return False

            # mark original as voided
            now = _now_str()
            try:
                cur.execute('UPDATE sales SET voided=1, voided_at=?, voided_by=?, void_reason=? WHERE id=?', (now, by or '', reason or '', sale_id))
            except Exception:
                pass

            reversal_id = None
            if create_reversal:
                # Build reversal row: negate quantity and selling_price_base (if present)
                qty = float(row['quantity'] or 0)
                new_qty = -qty
                # safe access helper for sqlite3.Row
                def _r(k):
                    try:
                        return row[k] if k in row.keys() else None
                    except Exception:
                        return None

                unit_price = _r('selling_price')
                sp_base = _r('selling_price_base')
                new_sp_base = -(float(sp_base) if sp_base is not None else 0.0)

                insert_sql = ('''INSERT INTO sales (date, category, subcategory, quantity, selling_price, platform, product_id, customer_id, document_path, fx_to_base, selling_price_base, sale_currency, deleted)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''')
                insert_params = (
                    now,
                    _r('category'),
                    _r('subcategory'),
                    new_qty,
                    unit_price,
                    _r('platform'),
                    _r('product_id'),
                    _r('customer_id'),
                    _r('document_path'),
                    _r('fx_to_base'),
                    new_sp_base,
                    _r('sale_currency'),
                    0,
                )
                cur.execute(insert_sql, insert_params)
                reversal_id = cur.lastrowid
                try:
                    cur.execute('UPDATE sales SET reversal_id=? WHERE id=?', (reversal_id, sale_id))
                except Exception:
                    pass

            try:
                write_audit('void_sale', 'sales', str(sale_id), f'by={by}; reason={reason}; reversal_id={reversal_id}',cur=cur)
            except Exception:
                pass
        return True
    except Exception:
        return False
