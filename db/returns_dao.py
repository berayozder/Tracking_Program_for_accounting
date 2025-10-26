# returns_dao.py
from typing import Any, Dict, Optional, List
from functools import wraps
from db.connection import get_conn
from db.settings import get_base_currency, get_default_sale_currency
from db.rates import convert_amount
import json


# ──────────────────────────────
# DB connection decorator
# ──────────────────────────────
def with_conn(func):
    """Automatically open, commit/rollback, and close DB connections."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        conn = get_conn()
        try:
            result = func(conn, *args, **kwargs)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return wrapper


# ──────────────────────────────
# Core DAO functions
# ──────────────────────────────

@with_conn
def list_returns(conn) -> List[Dict[str, Any]]:
    """Return all returns with refund amounts in base currency."""
    cur = conn.cursor()
    cur.execute('''
        SELECT id, return_date, product_id, sale_date, category, subcategory,
               unit_price, selling_price, platform, refund_amount, refund_currency,
               refund_amount_base, restock, reason, doc_paths, restock_processed
        FROM returns
        ORDER BY return_date DESC, id DESC
    ''')
    return [dict(row) for row in cur.fetchall()]


def _compute_refund_base(return_date: str, refund_amount: float, refund_currency: str) -> float:
    """Convert refund_amount into base currency."""
    base = get_base_currency()
    try:
        conv = convert_amount(return_date, float(refund_amount or 0.0), (refund_currency or base).upper(), base)
        return float(conv) if conv is not None else (float(refund_amount or 0.0) if (refund_currency or base).upper() == base else 0.0)
    except Exception:
        return float(refund_amount or 0.0) if (refund_currency or base).upper() == base else 0.0


@with_conn
def insert_return(conn, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Insert a return, compute refund_amount_base, optionally restock inventory."""
    # Normalize inputs
    rd = str(fields.get('return_date') or fields.get('ReturnDate') or '').strip()
    pid = str(fields.get('product_id') or fields.get('ProductID') or '').strip()
    sale_date = str(fields.get('sale_date') or fields.get('SaleDate') or '').strip()
    category = str(fields.get('category') or fields.get('Category') or '').strip()
    subcategory = str(fields.get('subcategory') or fields.get('Subcategory') or '').strip()
    platform = str(fields.get('platform') or fields.get('Platform') or '').strip()
    reason = fields.get('reason', fields.get('Reason', ''))

    unit_price = float(fields.get('unit_price', 0.0) or 0.0)
    selling_price = float(fields.get('selling_price', 0.0) or 0.0)
    refund_amount = float(fields.get('refund_amount', 0.0) or 0.0)
    refund_currency = str(fields.get('refund_currency', get_default_sale_currency()) or '').upper()

    restock = 1 if str(fields.get('restock', 0)).strip().lower() in ('1','true','yes') else 0

    doc_paths_val = fields.get('doc_paths', fields.get('ReturnDocPath', ''))
    if isinstance(doc_paths_val, list):
        doc_paths = json.dumps([str(x) for x in doc_paths_val if str(x).strip()], ensure_ascii=False)
    elif isinstance(doc_paths_val, str):
        dp = doc_paths_val.strip()
        try:
            json.loads(dp)
            doc_paths = dp
        except Exception:
            doc_paths = json.dumps([dp], ensure_ascii=False) if dp else ''
    else:
        doc_paths = ''

    refund_base = _compute_refund_base(rd, refund_amount, refund_currency)

    # Insert row
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO returns (
            return_date, product_id, sale_date, category, subcategory,
            unit_price, selling_price, platform, refund_amount,
            refund_currency, refund_amount_base, restock, reason, doc_paths
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (rd, pid, sale_date, category, subcategory, unit_price, selling_price, platform,
          refund_amount, refund_currency, refund_base, restock, reason, doc_paths))
    new_id = cur.lastrowid

    returned_batches = []
    if restock and pid:
        # optional: restock inventory logic (use same cursor for atomicity)
        try:
            remaining_to_return = 1.0
            cur.execute('SELECT batch_id, quantity_from_batch, unit_cost FROM sale_batch_allocations WHERE product_id = ? ORDER BY id DESC', (pid,))
            allocations = cur.fetchall()
            for alloc in allocations:
                if remaining_to_return <= 0:
                    break
                batch_id = alloc[0]
                original_allocation = float(alloc[1] or 0.0)
                unit_cost = float(alloc[2] or 0.0)
                if batch_id is None:
                    continue
                return_to_batch = min(remaining_to_return, original_allocation)
                cur.execute('UPDATE import_batches SET remaining_quantity = remaining_quantity + ? WHERE id = ?', (return_to_batch, batch_id))
                cur.execute('SELECT batch_date, supplier, category, subcategory FROM import_batches WHERE id = ?', (batch_id,))
                batch_info = cur.fetchone()
                returned_batches.append({
                    'batch_id': batch_id,
                    'batch_date': batch_info[0] if batch_info else 'Unknown',
                    'supplier': batch_info[1] if batch_info else 'Unknown',
                    'category': batch_info[2] if batch_info else '',
                    'subcategory': batch_info[3] if batch_info else '',
                    'returned_quantity': return_to_batch,
                    'unit_cost': unit_cost
                })
                remaining_to_return -= return_to_batch
            # mark restock processed
            if returned_batches:
                cur.execute('UPDATE returns SET restock_processed = 1 WHERE id = ?', (new_id,))
        except Exception:
            pass

    return {'id': new_id, 'restocked_batches': returned_batches}


@with_conn
def update_return(conn, ret_id: int, fields: Dict[str, Any]) -> bool:
    """Update a return and recompute refund_amount_base if needed."""
    cur = conn.cursor()
    cur.execute('SELECT * FROM returns WHERE id = ?', (ret_id,))
    curr = cur.fetchone()
    if not curr:
        return False

    rd = str(fields.get('return_date', curr['return_date']))
    ra = float(fields.get('refund_amount', curr['refund_amount']))
    rc = str(fields.get('refund_currency', curr['refund_currency'] or get_default_sale_currency())).upper()
    restock = 1 if str(fields.get('restock', curr['restock'])).strip().lower() in ('1','true','yes') else int(curr['restock'] or 0)
    reason = fields.get('reason', curr['reason'])
    doc_paths = fields.get('doc_paths', curr['doc_paths'])
    refund_base = _compute_refund_base(rd, ra, rc)

    cur.execute('''
        UPDATE returns
        SET return_date=?, refund_amount=?, refund_currency=?, refund_amount_base=?,
            restock=?, reason=?, doc_paths=?
        WHERE id=?
    ''', (rd, ra, rc, refund_base, restock, reason, doc_paths, ret_id))
    return True


@with_conn
def delete_return(conn, ret_id: int) -> bool:
    """Soft-delete a return."""
    cur = conn.cursor()
    cur.execute('UPDATE returns SET deleted = 1 WHERE id = ?', (ret_id,))
    return True


@with_conn
def undelete_return(conn, ret_id: int) -> bool:
    """Restore a soft-deleted return."""
    cur = conn.cursor()
    cur.execute('UPDATE returns SET deleted = 0 WHERE id = ?', (ret_id,))
    return True


@with_conn
def get_distinct_return_reasons(conn, limit: int = 200) -> List[str]:
    """Return distinct non-empty reasons from returns."""
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT TRIM(reason) AS r
        FROM returns
        WHERE reason IS NOT NULL AND TRIM(reason) <> ''
        ORDER BY r
        LIMIT ?
    """, (limit,))
    return [row[0] for row in cur.fetchall() if row and row[0]]
