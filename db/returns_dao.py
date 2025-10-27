def process_restock_change(ret_id: int, restock: int) -> bool:
    """Update inventory and restock_processed for a return, without changing deleted flag."""
    try:
        with get_cursor() as (conn, cur):
            cur.execute('SELECT * FROM returns WHERE id = ?', (ret_id,))
            ret = cur.fetchone()
            if not ret:
                return False
            prev_restock = int(ret['restock'] or 0)
            restock_processed = int(ret['restock_processed'] or 0)
            product_id = ret['product_id']
            category = ret['category']
            subcategory = ret['subcategory']
            # Only process if restock value is changing
            if restock != prev_restock:
                if restock == 1:
                    # Apply restock logic (like undelete)
                    cur.execute('SELECT batch_id, quantity_from_batch FROM sale_batch_allocations WHERE product_id = ?', (product_id,))
                    allocations = cur.fetchall()
                    for alloc in allocations:
                        batch_id = alloc['batch_id']
                        qty = float(alloc['quantity_from_batch'] or 0.0)
                        if batch_id:
                            cur.execute('UPDATE import_batches SET remaining_quantity = remaining_quantity + ? WHERE id = ?', (qty, batch_id))
                    update_inventory(category, subcategory, 1, cur=cur)
                    cur.execute('UPDATE returns SET restock_processed = 1, restock = 1 WHERE id = ?', (ret_id,))
                else:
                    # Reverse restock logic (like delete)
                    cur.execute('SELECT batch_id, quantity_from_batch FROM sale_batch_allocations WHERE product_id = ?', (product_id,))
                    allocations = cur.fetchall()
                    for alloc in allocations:
                        batch_id = alloc['batch_id']
                        qty = float(alloc['quantity_from_batch'] or 0.0)
                        if batch_id:
                            cur.execute('UPDATE import_batches SET remaining_quantity = remaining_quantity - ? WHERE id = ?', (qty, batch_id))
                    update_inventory(category, subcategory, -1, cur=cur)
                    cur.execute('UPDATE returns SET restock_processed = 0, restock = 0 WHERE id = ?', (ret_id,))
                return True
            return False
    except Exception as e:
        logger.exception(f"Error processing restock change: {e}")
        return False
# returns_dao.py

__all__ = [
    "list_returns",
    "insert_return",
    "update_return",
    "delete_return",
    "undelete_return",
    "get_distinct_return_reasons",
]

import logging

from typing import Any, Dict, Optional, List
from db.connection import get_cursor
from db.settings import get_base_currency, get_default_sale_currency
from db.rates import convert_amount
from db.inventory_dao import update_inventory
import json



logger = logging.getLogger("returns_dao")

def normalize_doc_paths(val):
    """Normalize doc_paths to a JSON string."""
    if val is None:
        return ''
    if isinstance(val, list):
        return json.dumps([str(x).strip() for x in val if str(x).strip()], ensure_ascii=False)
    if isinstance(val, str):
        v = val.strip()
        if not v:
            return ''
        try:
            arr = json.loads(v)
            if isinstance(arr, list):
                return json.dumps([str(x).strip() for x in arr if str(x).strip()], ensure_ascii=False)
        except Exception:
            pass
        return v
    return ''

# ──────────────────────────────
# DB connection decorator
# ──────────────────────────────

# ──────────────────────────────
# Core DAO functions
# ──────────────────────────────

def list_returns() -> List[Dict[str, Any]]:
    """Return all non-deleted returns with refund amounts in base currency."""
    with get_cursor() as (conn, cur):
        cur.execute('''
            SELECT id, return_date, product_id, sale_date, category, subcategory,
                   unit_price, selling_price, platform, refund_amount, refund_currency,
                   refund_amount_base, restock, reason, doc_paths, restock_processed, deleted
            FROM returns
            WHERE COALESCE(deleted, 0) = 0
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


def insert_return(fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Insert a return, compute refund_amount_base, optionally restock inventory."""
    # Normalize inputs
    rd = str(fields.get('return_date') or fields.get('ReturnDate') or '').strip()
    pid = str(fields.get('product_id') or fields.get('ProductID') or '').strip()
    sale_date = str(fields.get('sale_date') or fields.get('SaleDate') or '').strip()
    category = str(fields.get('category') or fields.get('Category') or '').strip()
    subcategory = str(fields.get('subcategory') or fields.get('Subcategory') or '').strip()
    platform = str(fields.get('platform') or fields.get('Platform') or '').strip()
    unit_price = float(fields.get('unit_price', 0.0) or 0.0)
    selling_price = float(fields.get('selling_price', 0.0) or 0.0)
    refund_amount = float(fields.get('refund_amount', 0.0) or 0.0)
    refund_currency = str(fields.get('refund_currency', get_default_sale_currency()) or '').upper()
    restock = 1 if str(fields.get('restock', 0)).strip().lower() in ('1','true','yes') else 0
    reason = fields.get('reason', fields.get('Reason', ''))
    doc_paths = normalize_doc_paths(fields.get('doc_paths', fields.get('ReturnDocPath', '')))
    refund_base = _compute_refund_base(rd, refund_amount, refund_currency)

    with get_cursor() as (conn, cur):
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
            try:
                remaining_to_return = 1.0
                cur.execute('SELECT batch_id, quantity_from_batch, unit_cost FROM sale_batch_allocations WHERE product_id = ? ORDER BY id DESC', (pid,))
                allocations = cur.fetchall()
                for alloc in allocations:
                    if remaining_to_return <= 0:
                        break
                    batch_id = alloc['batch_id']
                    original_allocation = float(alloc['quantity_from_batch'] or 0.0)
                    unit_cost = float(alloc['unit_cost'] or 0.0)
                    if batch_id is None:
                        continue
                    return_to_batch = min(remaining_to_return, original_allocation)
                    cur.execute('UPDATE import_batches SET remaining_quantity = remaining_quantity + ? WHERE id = ?', (return_to_batch, batch_id))
                    cur.execute('SELECT batch_date, supplier, category, subcategory FROM import_batches WHERE id = ?', (batch_id,))
                    batch_info = cur.fetchone()
                    returned_batches.append({
                        'batch_id': batch_id,
                        'batch_date': batch_info['batch_date'] if batch_info else 'Unknown',
                        'supplier': batch_info['supplier'] if batch_info else 'Unknown',
                        'category': batch_info['category'] if batch_info else '',
                        'subcategory': batch_info['subcategory'] if batch_info else '',
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


def update_return(ret_id: int, fields: Dict[str, Any]) -> bool:
    """Update a return and recompute refund_amount_base if needed."""
    with get_cursor() as (conn, cur):
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


def delete_return(ret_id: int) -> bool:
    """Soft-delete a return and reverse inventory restock if needed."""
    logger.info(f"Deleted return id={ret_id} (soft-delete)")
    with get_cursor() as (conn, cur):
        cur.execute('SELECT * FROM returns WHERE id = ?', (ret_id,))
        ret = cur.fetchone()
        if not ret:
            return False
        # Row access safety
        restock = ret['restock']
        restock_processed = ret['restock_processed']
        product_id = ret['product_id']
        category = ret['category']
        subcategory = ret['subcategory']
        if int(restock or 0) == 1 and int(restock_processed or 0) == 1 and product_id:
            try:
                cur.execute('SELECT batch_id, quantity_from_batch FROM sale_batch_allocations WHERE product_id = ?', (product_id,))
                allocations = cur.fetchall()
                for alloc in allocations:
                    batch_id = alloc['batch_id']
                    qty = float(alloc['quantity_from_batch'] or 0.0)
                    if batch_id:
                        cur.execute('UPDATE import_batches SET remaining_quantity = remaining_quantity - ? WHERE id = ?', (qty, batch_id))
                update_inventory(category, subcategory, -1, cur=cur)
            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating inventory or batches during delete_return: {e}")
                return False
        cur.execute('UPDATE returns SET deleted = 1 WHERE id = ?', (ret_id,))
        return True


def undelete_return(ret_id: int) -> bool:
    """Restore a soft-deleted return and re-apply inventory restock if needed."""
    logger.info(f"Undeleted return id={ret_id}")
    with get_cursor() as (conn, cur):
        cur.execute('SELECT * FROM returns WHERE id = ?', (ret_id,))
        ret = cur.fetchone()
        if not ret:
            return False
        restock = ret['restock']
        restock_processed = ret['restock_processed']
        product_id = ret['product_id']
        category = ret['category']
        subcategory = ret['subcategory']
        if int(restock or 0) == 1 and int(restock_processed or 0) == 1 and product_id:
            try:
                cur.execute('SELECT batch_id, quantity_from_batch FROM sale_batch_allocations WHERE product_id = ?', (product_id,))
                allocations = cur.fetchall()
                for alloc in allocations:
                    batch_id = alloc['batch_id']
                    qty = float(alloc['quantity_from_batch'] or 0.0)
                    if batch_id:
                        cur.execute('UPDATE import_batches SET remaining_quantity = remaining_quantity + ? WHERE id = ?', (qty, batch_id))
                update_inventory(category, subcategory, 1, cur=cur)
            except Exception as e:
                conn.rollback()
                logger.error(f"Error updating inventory or batches during undelete_return: {e}")
                return False
        cur.execute('UPDATE returns SET deleted = 0 WHERE id = ?', (ret_id,))
        return True


def get_distinct_return_reasons(limit: int = 200) -> List[str]:
    """Return distinct non-empty reasons from returns."""
    with get_cursor() as (conn, cur):
        cur.execute("""
            SELECT DISTINCT TRIM(reason) AS r
            FROM returns
            WHERE reason IS NOT NULL AND TRIM(reason) <> ''
            ORDER BY r
            LIMIT ?
        """, (limit,))
        return [row[0] for row in cur.fetchall() if row and row[0]]
