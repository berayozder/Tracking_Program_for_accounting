"""Returns management and inventory restocking."""
from __future__ import annotations

import logging
import json
import traceback
from typing import Any, Optional

from db.connection import get_cursor
from db.settings import get_base_currency, get_default_sale_currency
from db.rates import convert_amount
from db.inventory_dao import update_inventory

__all__ = [
    "list_returns",
    "insert_return",
    "update_return",
    "delete_return",
    "undelete_return",
    "get_distinct_return_reasons",
    "add_return_reason",
    "process_restock_change"
]

logger = logging.getLogger("returns_dao")

# ──────────────────────────────
# Helpers
# ──────────────────────────────

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

def _compute_refund_base(return_date: str, refund_amount: float, refund_currency: str) -> float:
    """Convert refund_amount into base currency."""
    base = get_base_currency()
    try:
        conv = convert_amount(return_date, float(refund_amount or 0.0), (refund_currency or base).upper(), base)
        return float(conv) if conv is not None else (float(refund_amount or 0.0) if (refund_currency or base).upper() == base else 0.0)
    except Exception:
        return float(refund_amount or 0.0) if (refund_currency or base).upper() == base else 0.0

def _apply_restock_logic(cur, product_id: str, category: str, subcategory: str, direction: int) -> list[dict]:
    """
    Apply restock (+1) or unstock (-1) logic to batches and global inventory.
    Returns list of affected batches.
    """
    affected_batches = []
    try:
        cur.execute('SELECT batch_id, quantity_from_batch, unit_cost FROM sale_batch_allocations WHERE product_id = ? ORDER BY id DESC', (product_id,))
        allocations = cur.fetchall()
        
        remaining_change = 1.0 # We assume 1 unit per return typically, matching logic "remaining_to_return -= return_to_batch"
        
        for alloc in allocations:
            if remaining_change <= 0:
                break
            
            batch_id = alloc['batch_id']
            qty = float(alloc['quantity_from_batch'] or 0.0)
            unit_cost = float(alloc['unit_cost'] or 0.0)
            
            if not batch_id:
                continue
                
            # For restock (direction=1), we add back up to 'qty'.
            # For unstock (direction=-1), we remove up to 'qty'.
            # Logic simplifies to: modify batch remaining_quantity by (direction * qty)
            # BUT wait, the original logic had `min(remaining_to_return, original_allocation)`.
            # If we just use full allocation qty, it's safer?
            # Returns logic in insert_return used: `min(remaining_to_return, original_allocation)`.
            # Since `remaining_to_return` starts at 1.0, and `original_allocation` is usually 1.0 (for single unit), it works out.
            
            amount_to_process = min(remaining_change, qty)
            
            if direction > 0:
                cur.execute('UPDATE import_batches SET remaining_quantity = remaining_quantity + ? WHERE id = ?', (amount_to_process, batch_id))
            else:
                cur.execute('UPDATE import_batches SET remaining_quantity = remaining_quantity - ? WHERE id = ?', (amount_to_process, batch_id))
            
            # Fetch batch info for reporting
            cur.execute('SELECT batch_date, supplier, category, subcategory FROM import_batches WHERE id = ?', (batch_id,))
            batch_info = cur.fetchone()
            
            affected_batches.append({
                'batch_id': batch_id,
                'batch_date': batch_info['batch_date'] if batch_info else 'Unknown',
                'supplier': batch_info['supplier'] if batch_info else 'Unknown',
                'category': batch_info['category'] if batch_info else '',
                'subcategory': batch_info['subcategory'] if batch_info else '',
                'returned_quantity': amount_to_process,
                'unit_cost': unit_cost
            })
            
            remaining_change -= amount_to_process
            
        # Update global inventory
        # If direction=1 (Restock), Add 1. If -1, Remove 1.
        # We use strict 1.0 here as existing logic did.
        update_inventory(category, subcategory, float(direction), cur=cur)
            
    except Exception as e:
        logger.error(f"Error in _apply_restock_logic: {e}")
        traceback.print_exc()
        raise e
        
    return affected_batches

# ──────────────────────────────
# DAO Functions
# ──────────────────────────────

def process_restock_change(ret_id: int, restock: int, conn=None, cur=None) -> bool:
    """Update inventory and restock_processed for a return, without changing deleted flag."""
    try:
        if cur:
            return _process_restock_change_internal(cur, ret_id, restock)
        with get_cursor() as (conn, cur):
            return _process_restock_change_internal(cur, ret_id, restock)
    except Exception as e:
        logger.exception(f"Error processing restock change: {e}")
        return False

def _process_restock_change_internal(cur, ret_id, restock):
    cur.execute('SELECT * FROM returns WHERE id = ?', (ret_id,))
    ret = cur.fetchone()
    if not ret:
        return False
        
    prev_restock = int(ret['restock'] or 0)
    product_id = ret['product_id']
    category = ret['category']
    subcategory = ret['subcategory']
    
    if restock != prev_restock:
        if restock == 1:
            _apply_restock_logic(cur, product_id, category, subcategory, 1)
            cur.execute('UPDATE returns SET restock_processed = 1, restock = 1 WHERE id = ?', (ret_id,))
        else:
            _apply_restock_logic(cur, product_id, category, subcategory, -1)
            cur.execute('UPDATE returns SET restock_processed = 0, restock = 0 WHERE id = ?', (ret_id,))
        return True
    return False

def list_returns() -> list[dict[str, Any]]:
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

def insert_return(fields: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Insert a return, compute refund_amount_base, optionally restock inventory."""
    rd = str(fields.get('return_date') or fields.get('ReturnDate') or '').strip()
    pid = fields.get('product_id') or fields.get('ProductID') or ''
    if pid is None: pid = ''
    # pid can be int or str. If it's pure int, leave as int. If str, strip.
    if isinstance(pid, str): pid = pid.strip()
    
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
    sale_id = fields.get('sale_id')
    refund_base = _compute_refund_base(rd, refund_amount, refund_currency)

    with get_cursor() as (conn, cur):
        cur.execute('''
            INSERT INTO returns (
                return_date, product_id, sale_date, category, subcategory,
                unit_price, selling_price, platform, refund_amount,
                refund_currency, refund_amount_base, restock, reason, doc_paths, sale_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (rd, pid, sale_date, category, subcategory, unit_price, selling_price, platform,
              refund_amount, refund_currency, refund_base, restock, reason, doc_paths, sale_id))
        new_id = cur.lastrowid

        returned_batches = []
        if restock and pid:
            try:
                returned_batches = _apply_restock_logic(cur, pid, category, subcategory, 1)
                if returned_batches:
                    cur.execute('UPDATE returns SET restock_processed = 1 WHERE id = ?', (new_id,))
            except Exception as e:
                logger.error(f"Error in insert_return restock: {e}")

        return {'id': new_id, 'restocked_batches': returned_batches}

def update_return(ret_id: int, fields: dict[str, Any]) -> bool:
    """Update a return and recompute refund_amount_base if needed."""
    with get_cursor() as (conn, cur):
        cur.execute('SELECT * FROM returns WHERE id = ?', (ret_id,))
        curr = cur.fetchone()
        if not curr:
            return False

        rd = str(fields.get('return_date', curr['return_date']))
        ra = float(fields.get('refund_amount', curr['refund_amount']))
        rc = str(fields.get('refund_currency', curr['refund_currency'] or get_default_sale_currency())).upper()
        
        # Proper argument parsing
        if 'restock' in fields:
             val = str(fields['restock'])
             restock = 1 if val.strip().lower() in ('1', 'true', 'yes') else 0
        else:
             restock = int(curr['restock'] or 0)

        reason = fields.get('reason', curr['reason'])
        doc_paths = fields.get('doc_paths', curr['doc_paths'])
        refund_base = _compute_refund_base(rd, ra, rc)

        # Trigger logic if restock status changed
        process_restock_change(ret_id, restock, cur=cur)

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
            
        restock = int(ret['restock'] or 0)
        restock_processed = int(ret['restock_processed'] or 0)
        
        if restock == 1 and restock_processed == 1 and ret['product_id']:
            try:
                _apply_restock_logic(cur, ret['product_id'], ret['category'], ret['subcategory'], -1)
            except Exception as e:
                conn.rollback()
                logger.error(f"Error reversing restock in delete_return: {e}")
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
            
        restock = int(ret['restock'] or 0)
        restock_processed = int(ret['restock_processed'] or 0)
        
        if restock == 1 and restock_processed == 1 and ret['product_id']:
            try:
                _apply_restock_logic(cur, ret['product_id'], ret['category'], ret['subcategory'], 1)
            except Exception as e:
                conn.rollback()
                logger.error(f"Error reapplying restock in undelete_return: {e}")
                return False
                
        cur.execute('UPDATE returns SET deleted = 0 WHERE id = ?', (ret_id,))
        return True

def get_distinct_return_reasons(limit: int = 200) -> list[str]:
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

def add_return_reason(reason: str) -> None:
    """
    Placeholder for adding a return reason to defaults.
    Since reasons are distinct values from the `returns` table, 
    this currently does not persist anything until used in a return.
    """
    pass
