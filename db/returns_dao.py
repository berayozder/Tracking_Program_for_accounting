from .connection import get_conn
from typing import Any, Dict, Optional
from .settings import get_base_currency,get_default_sale_currency
from .rates import convert_amount


def list_returns():
    """Return all returns with refund amounts in base currency."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('''
            SELECT id, return_date, product_id, sale_date, category, subcategory,
                   unit_price, selling_price, platform, refund_amount, refund_currency,
                   refund_amount_base, restock, reason, doc_paths, restock_processed
            FROM returns
            ORDER BY return_date DESC, id DESC
        ''')
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def insert_return(fields: Dict[str, Any]) -> Optional[dict]:
    """Insert a new return row and compute refund_amount_base.
    Expects keys: return_date, product_id, sale_date, category, subcategory,
    unit_price, selling_price, platform, refund_amount, refund_currency,
    restock, reason, doc_paths (string JSON or list/single path).
    Returns a dict {'id': new_id, 'restocked_batches': [...]} on success, or None on failure.
    """
    try:
        # Normalize inputs
        rd = str(fields.get('return_date') or fields.get('ReturnDate') or '').strip()
        pid = str(fields.get('product_id') or fields.get('ProductID') or '').strip()
        sale_date = str(fields.get('sale_date') or fields.get('SaleDate') or '').strip()
        category = str(fields.get('category') or fields.get('Category') or '').strip()
        subcategory = str(fields.get('subcategory') or fields.get('Subcategory') or '').strip()
        platform = str(fields.get('platform') or fields.get('Platform') or '').strip()
        reason = fields.get('reason', fields.get('Reason', ''))
        try:
            unit_price = float(fields.get('unit_price', fields.get('UnitPrice', 0.0)) or 0.0)
        except Exception:
            unit_price = 0.0
        try:
            selling_price = float(fields.get('selling_price', fields.get('SellingPrice', 0.0)) or 0.0)
        except Exception:
            selling_price = 0.0
        try:
            refund_amount = float(fields.get('refund_amount', fields.get('RefundAmount', 0.0)) or 0.0)
        except Exception:
            refund_amount = 0.0
        refund_currency = str(fields.get('refund_currency', fields.get('RefundCurrency', '')).upper() or get_default_sale_currency())
        # restock may be bool/int/str
        restock = fields.get('restock', fields.get('Restock', 0))
        try:
            restock = 1 if str(restock).strip() in ('1','true','True','YES','yes') else 0
        except Exception:
            restock = 0
        # doc paths: accept JSON string, list, or single string
        doc_paths_val = fields.get('doc_paths', fields.get('ReturnDocPath', ''))
        import json as _json
        doc_paths: str
        if isinstance(doc_paths_val, list):
            doc_paths = _json.dumps([str(x) for x in doc_paths_val if str(x).strip()], ensure_ascii=False)
        elif isinstance(doc_paths_val, str):
            dp = doc_paths_val.strip()
            if not dp:
                doc_paths = ''
            else:
                # if it's already JSON, keep; else wrap single path
                try:
                    _ = _json.loads(dp)
                    doc_paths = dp
                except Exception:
                    doc_paths = _json.dumps([dp], ensure_ascii=False)
        else:
            doc_paths = ''

        refund_base = _compute_refund_base(rd, refund_amount, refund_currency)

        # Use a single DB connection/transaction so insert + optional restock is atomic
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO returns (
                    return_date, product_id, sale_date, category, subcategory,
                    unit_price, selling_price, platform, refund_amount,
                    refund_currency, refund_amount_base, restock, reason, doc_paths
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (rd, pid, sale_date, category, subcategory, float(unit_price or 0.0), float(selling_price or 0.0),
                  platform, float(refund_amount or 0.0), refund_currency or None, float(refund_base or 0.0), int(restock or 0), reason, doc_paths))
            new_id = cur.lastrowid

            # If restock requested, try to return units to the original batches and update inventory
            returned = []
            if int(restock or 0) == 1 and pid:
                try:
                    # Use the same connection to update import_batches so it's in same transaction
                    # We'll mimic handle_return_batch_allocation logic here but using this cursor
                    remaining_to_return = 1.0
                    cur.execute('''
                        SELECT batch_id, quantity_from_batch, unit_cost
                        FROM sale_batch_allocations
                        WHERE product_id = ?
                        ORDER BY id DESC
                    ''', (pid,))
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
                        cur.execute('UPDATE import_batches SET remaining_quantity = remaining_quantity + ? WHERE id = ?',
                                   (return_to_batch, batch_id))
                        cur.execute('SELECT batch_date, supplier, category, subcategory FROM import_batches WHERE id = ?', (batch_id,))
                        batch_info = cur.fetchone()
                        returned.append({
                            'batch_id': batch_id,
                            'batch_date': batch_info[0] if batch_info else 'Unknown',
                            'supplier': batch_info[1] if batch_info else 'Unknown',
                            'category': batch_info[2] if batch_info else '',
                            'subcategory': batch_info[3] if batch_info else '',
                            'returned_quantity': return_to_batch,
                            'unit_cost': unit_cost
                        })
                        remaining_to_return -= return_to_batch
                except Exception:
                    # Any exception here should rollback the whole transaction below
                    raise
                try:
                    # Update the inventory summary using same connection
                    cur.execute('SELECT id, quantity FROM inventory WHERE category = ? AND subcategory = ? LIMIT 1', (category or '', subcategory or ''))
                    inv = cur.fetchone()
                    if inv:
                        cur.execute('UPDATE inventory SET quantity = quantity + ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?', (1.0, inv[0]))
                    else:
                        cur.execute('INSERT INTO inventory(category, subcategory, quantity, last_updated) VALUES(?,?,?,CURRENT_TIMESTAMP)', (category or '', subcategory or '', 1.0))
                except Exception:
                    raise

            # If we returned units successfully, mark restock_processed on the inserted return
            try:
                if returned and int(restock or 0) == 1:
                    cur.execute('UPDATE returns SET restock_processed = 1 WHERE id = ?', (new_id,))
            except Exception:
                # Non-fatal; but if this fails we'll still commit the other changes
                pass

            # Commit transaction
            # If we returned units successfully, mark restock_processed on the inserted return
            try:
                if returned and int(restock or 0) == 1:
                    cur.execute('UPDATE returns SET restock_processed = 1 WHERE id = ?', (new_id,))
            except Exception:
                # Non-fatal; but if this fails we'll still commit the other changes
                pass

            # Commit transaction
            conn.commit()
            conn.close()
            return {'id': int(new_id), 'restocked_batches': returned}
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
            return None
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return None


def _compute_refund_base(return_date: str, refund_amount: float, refund_currency: str) -> float:
    base = get_base_currency()
    try:
        conv = convert_amount(return_date, float(refund_amount or 0.0), (refund_currency or base).upper(), base)
        return float(conv) if conv is not None else (float(refund_amount or 0.0) if (refund_currency or base).upper() == base else 0.0)
    except Exception:
        return float(refund_amount or 0.0) if (refund_currency or base).upper() == base else 0.0


def update_return(ret_id: int, fields: Dict[str, Any]) -> bool:
    """Update a return row; if ReturnDate/RefundAmount/RefundCurrency change, recompute refund_amount_base."""
    try:
        conn = get_conn()
        cur = conn.cursor()
        # Fetch current row
        cur.execute('SELECT * FROM returns WHERE id = ?', (ret_id,))
        curr = cur.fetchone()
        if not curr:
            conn.close()
            return False
        # Merge
        rd = str(fields.get('return_date', fields.get('ReturnDate', curr['return_date']) or curr['return_date']))
        ra = fields.get('refund_amount', fields.get('RefundAmount', curr['refund_amount']))
        try:
            ra = float(ra)
        except Exception:
            ra = float(curr['refund_amount'] or 0.0)
        rc = str(fields.get('refund_currency', fields.get('RefundCurrency', curr['refund_currency']) or '')).upper()
        restock = fields.get('restock', fields.get('Restock', curr['restock']))
        try:
            restock = 1 if str(restock).strip() in ('1','true','True','YES','yes') else 0
        except Exception:
            restock = int(curr['restock'] or 0)
        reason = fields.get('reason', fields.get('Reason', curr['reason']))
        doc_paths = fields.get('doc_paths', fields.get('ReturnDocPath', curr['doc_paths']))
        refund_base = _compute_refund_base(rd, ra, rc or get_default_sale_currency())
        # Build update
        cur.execute('''
            UPDATE returns
            SET return_date=?, refund_amount=?, refund_currency=?, refund_amount_base=?,
                restock=?, reason=?, doc_paths=?
            WHERE id=?
        ''', (rd, float(ra or 0.0), rc or None, float(refund_base or 0.0), int(restock or 0), reason, doc_paths, ret_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def delete_return(ret_id: int) -> bool:
    try:
        conn = get_conn()
        cur = conn.cursor()
        # Soft-delete: mark as deleted and preserve for audit/restore
        cur.execute('UPDATE returns SET deleted = 1 WHERE id = ?', (ret_id,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def undelete_return(ret_id: int) -> bool:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('UPDATE returns SET deleted = 0 WHERE id = ?', (ret_id,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def get_distinct_return_reasons(limit: int = 200) -> list:
    """Return a list of distinct non-empty reasons from returns, ordered alphabetically.
    Limited to a reasonable number to keep UI snappy.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT TRIM(reason) AS r
            FROM returns
            WHERE reason IS NOT NULL AND TRIM(reason) <> ''
            ORDER BY r
            LIMIT ?
        """, (int(limit or 200),))
        out = [row[0] for row in cur.fetchall() if row and row[0]]
        conn.close()
        return out
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return []

