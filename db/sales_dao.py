"""Sales data access and management."""
from __future__ import annotations

import logging
from typing import Optional, Any, Union

from .connection import get_cursor
from .utils import float_or_none

logger = logging.getLogger(__name__)


def list_sales(include_deleted: bool = False) -> list[dict[str, Any]]:
    """
    Return sales rows as list of dicts ordered by date ascending (oldest first).
    
    Args:
        include_deleted: If True, includes soft-deleted rows.
        
    Returns:
        List of sale dictionaries.
    """
    try:
        with get_cursor() as (conn, cur):
            if include_deleted:
                cur.execute('SELECT * FROM sales ORDER BY datetime(date) ASC, id ASC')
            else:
                try:
                    cur.execute('SELECT * FROM active_sales ORDER BY datetime(date) ASC, id ASC')
                except Exception:
                    # Fallback if view doesn't exist
                    cur.execute(
                        'SELECT * FROM sales WHERE deleted IS NULL OR deleted=0 ORDER BY datetime(date) ASC, id ASC'
                    )
            rows = [dict(r) for r in cur.fetchall()]
            return rows
    except Exception as e:
        logger.error(f"Error in list_sales: {e}")
        return []


def add_sale(row: dict[str, Any]) -> int:
    """
    Insert a sale into the sales table.
    
    Args:
        row: Dictionary containing sale details. Keys are case-insensitive.
        
    Returns:
        The new row id, or 0 on failure.
    """
    try:
        with get_cursor() as (conn, cur):
            r = {k.lower(): v for k, v in (row or {}).items()}
            
            deleted_flag = str(r.get('deleted')).lower()
            deleted_val = 1 if deleted_flag in ('1', 'true', 'yes', 'y') else 0
            
            vat_rate = float_or_none(r.get('vat_rate'))
            vat_amount = float_or_none(r.get('vat_amount'))
            
            is_vat_inclusive = r.get('is_vat_inclusive')
            if is_vat_inclusive is None:
                is_vat_inclusive = 1
            else:
                is_vat_inclusive = 1 if str(is_vat_inclusive).lower() in ('1','true','yes','y') else 0

            cur.execute(
                '''INSERT INTO sales (
                    date, category, subcategory, quantity, selling_price, platform, product_id,
                    customer_id, document_path, fx_to_base, selling_price_base, sale_currency,
                    vat_rate, vat_amount, is_vat_inclusive, deleted
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    r.get('date', ''),
                    r.get('category', ''),
                    r.get('subcategory', ''),
                    float_or_none(r.get('quantity')) or 0,
                    float_or_none(r.get('sellingprice') or r.get('selling_price') or r.get('unit_price')) or 0,
                    r.get('platform', ''),
                    r.get('productid') or r.get('product_id') or '',
                    r.get('customerid') or r.get('customer_id'),
                    r.get('documentpath') or r.get('document_path') or r.get('doc_paths') or '',
                    float_or_none(r.get('fxtobase') or r.get('fx_to_base')),
                    float_or_none(r.get('sellingpricebase') or r.get('selling_price_base') or r.get('sellingpriceusd')),
                    (r.get('salecurrency') or r.get('sale_currency') or '').upper(),
                    vat_rate,
                    vat_amount,
                    is_vat_inclusive,
                    deleted_val
                )
            )
            return cur.lastrowid or 0
    except Exception as e:
        logger.error(f"Error in add_sale: {e}")
        return 0


def overwrite_sales(rows: list[dict[str, Any]]) -> int:
    """
    Replace all sales rows with provided rows.
    
    Args:
        rows: List of sales to insert after clearing existing sales.
        
    Returns:
        Number of rows successfully inserted.
    """
    try:
        with get_cursor() as (conn, cur):
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
                        rr.get('customerid') or rr.get('customer_id'),
                        rr.get('documentpath') or rr.get('document_path') or rr.get('doc_paths') or '',
                        float_or_none(rr.get('fxtobase') or rr.get('fx_to_base')),
                        float_or_none(rr.get('sellingpricebase') or rr.get('selling_price_base') or rr.get('sellingpriceusd')),
                        (rr.get('salecurrency') or rr.get('sale_currency') or '').upper(),
                        deleted_val
                    )
                )
                count += 1
            return count
    except Exception as e:
        logger.error(f"Error in overwrite_sales: {e}")
        return 0


def get_distinct_sale_platforms() -> list[str]:
    """Return list of distinct, non-empty platform names from sales."""
    try:
        with get_cursor() as (conn, cur):
            cur.execute(
                "SELECT DISTINCT platform FROM sales WHERE platform IS NOT NULL AND platform <> '' "
                "ORDER BY platform COLLATE NOCASE"
            )
            vals = [r[0] for r in cur.fetchall() if r[0] is not None]
            return vals
    except Exception as e:
        logger.error(f"Error in get_distinct_sale_platforms: {e}")
        return []





def undelete_sales_by_ids(ids: list[int]) -> int:
    """
    Clear Deleted flag for sales specified by their DB ids.
    
    Args:
        ids: List of database IDs to undelete.
        
    Returns:
        Number of rows updated.
    """
    if not ids:
        return 0
    try:
        with get_cursor() as (conn, cur):
            q = f"UPDATE sales SET deleted=0 WHERE id IN ({','.join(['?']*len(ids))})"
            cur.execute(q, tuple(ids))
            return cur.rowcount or 0
    except Exception as e:
        logger.error(f"Error in undelete_sales_by_ids: {e}")
        return 0


def mark_sale_deleted(ids: list[int]) -> int:
    """
    Mark given sale ids as deleted (soft-delete).
    
    Args:
        ids: List of database IDs to mark as deleted.
        
    Returns:
        Number of rows updated.
    """
    if not ids:
        return 0
    try:
        with get_cursor() as (conn, cur):
            q = f"UPDATE sales SET deleted=1 WHERE id IN ({','.join(['?']*len(ids))})"
            cur.execute(q, tuple(ids))
            return cur.rowcount or 0
    except Exception as e:
        logger.error(f"Error in mark_sale_deleted: {e}")
        return 0


def update_sale(sale_id: int, changes: dict[str, Any]) -> bool:
    """
    Update fields on a sale row.
    
    Args:
        sale_id: ID of the sale to update.
        changes: Dictionary of column_name: new_value.
        
    Returns:
        True if successful, False otherwise.
    """
    if not sale_id or not changes:
        return False

    allowed = {
        'date', 'category', 'subcategory', 'quantity', 'selling_price', 'platform',
        'product_id', 'customer_id', 'document_path', 'fx_to_base', 'selling_price_base',
        'sale_currency', 'vat_rate', 'vat_amount', 'is_vat_inclusive', 'deleted'
    }

    sets, params = [], []
    for k, v in changes.items():
        if k in allowed:
            sets.append(f"{k}=?")
            params.append(v)
    if not sets:
        return False
    params.append(sale_id)

    try:
        with get_cursor() as (conn, cur):
            sql = f"UPDATE sales SET {', '.join(sets)} WHERE id=?"
            cur.execute(sql, tuple(params))
            return True
    except Exception as e:
        logger.error(f"Error in update_sale: {e}")
        return False





def get_allocations_for_sales(sale_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """
    Fetch batch allocations for multiple sale_ids in one query.
    Returns a dict mapping sale_id -> list of allocations.
    """
    if not sale_ids:
        return {}
    try:
        with get_cursor() as (conn, cur):
            placeholders = ','.join(['?'] * len(sale_ids))
            query = f'''
                SELECT sba.*, ib.supplier, ib.batch_date
                FROM sale_batch_allocations sba
                LEFT JOIN import_batches ib ON sba.batch_id = ib.id
                WHERE sba.sale_id IN ({placeholders}) AND (sba.deleted IS NULL OR sba.deleted = 0)
                ORDER BY sba.sale_id, sba.id
            '''
            cur.execute(query, list(sale_ids))
            rows = [dict(r) for r in cur.fetchall()]
            
            result = {}
            for r in rows:
                sid = r['sale_id']
                if sid not in result:
                    result[sid] = []
                result[sid].append(r)
            return result
    except Exception as e:
        logger.error(f"Error in get_allocations_for_sales: {e}")
        return {}


def delete_sale_allocation(allocation_id: int) -> bool:
    """
    Soft-delete a single allocation, restore inventory, and update parent sale totals.
    """
    from core.vat_utils import compute_vat
    try:
        with get_cursor() as (conn, cur):
            # 1. Fetch allocation details
            cur.execute('SELECT * FROM sale_batch_allocations WHERE id=?', (allocation_id,))
            alloc = cur.fetchone()
            if not alloc:
                return False
            alloc = dict(alloc)
            
            qty = alloc.get('quantity') or 0
            if qty <= 0:
                return False # Should not happen, but safety check

            sale_id = alloc.get('sale_id')
            batch_id = alloc.get('batch_id')
            
            sale_price_total = (alloc.get('unit_sale_price') or 0) * qty # Total revenue from this chunk
            # Note: Dictionary might store per-unit profit/cost, need to be careful.
            # unit_sale_price in alloc is unit price. 
            # In parent sale, 'selling_price' is total.
            
            # 2. Mark allocation deleted
            cur.execute('UPDATE sale_batch_allocations SET deleted=1 WHERE id=?', (allocation_id,))
            
            # 3. Restore inventory if batch exists
            if batch_id:
                cur.execute('UPDATE import_batches SET remaining_quantity = remaining_quantity + ? WHERE id=?', (qty, batch_id))
            
            # 4. Update Parent Sale
            if sale_id:
                cur.execute('SELECT * FROM sales WHERE id=?', (sale_id,))
                sale = cur.fetchone()
                if sale:
                    sale = dict(sale)
                    new_qty = (sale.get('quantity') or 0) - qty
                    current_total_price = sale.get('selling_price') or 0
                    current_total_base = sale.get('selling_price_base') or 0
                    
                    # Proportional deduction? Or generic unit price?
                    # The allocation has specific unit_sale_price, so we subtract that * qty.
                    
                    new_selling_price = current_total_price - sale_price_total
                    
                    # Update Base price too
                    # Allocation doesn't implicitly store total base revenue, but unit_sale_price is usually base?
                    # Let's check `allocate_sale_to_batches`: `unit_sale_price` passed is `unit_sale_price_base`.
                    # So `alloc['unit_sale_price']` IS base price.
                    # Wait, `sales` table `selling_price` is Transaction Currency (TRY usually), `selling_price_base` is USD.
                    # In `allocate_sale_to_batches`, we insert `unit_sale_price` which is derived from `unit_sale_price_base`.
                    # Actually `allocate_sale_to_batches` doc says `unit_sale_price_base` is passed.
                    # And inserted into `unit_sale_price` column of allocation. So allocation stores BASE price?
                    # Let's verify `sales_window.py`... 
                    # `db.allocate_sale_to_batches(..., unit_in_base, ...)`
                    # Yes, allocation tracks Base/USD profit.
                    
                    # So we subtract from `selling_price_base`.
                    deduct_base = (alloc.get('unit_sale_price') or 0) * qty
                    new_price_base = current_total_base - deduct_base
                    
                    # How much to deduct from `selling_price` (TRY/Transaction currency)?
                    # We need the FX rate or original ratio.
                    # `sale['fx_to_base']` might help or ratio.
                    # If total_base was X and total_try was Y.
                    # If we deduct dX from base, we should deduct dY from TRY.
                    # dY = dX / fx_to_base (if fx = base/try? No, fx is usually Try->Base or Base->Try?)
                    # Let's look at `add_sale`: unit_in_base calculated via convert_amount.
                    # `selling_price` is passed explicitly.
                    # We can estimate deduction for `selling_price` based on average unit price of the sale.
                    # Average Unit Price (TRY) = current_total_price / old_qty
                    deduct_try = (current_total_price / (sale.get('quantity') or 1)) * qty
                    new_price_try = current_total_price - deduct_try
                    
                    # Recalculate VAT
                    vat_rate = sale.get('vat_rate')
                    is_inc = sale.get('is_vat_inclusive')
                    if vat_rate is not None:
                        net, vat_amt = compute_vat(new_price_try, vat_rate, is_inc)
                    else:
                        vat_amt = 0
                    
                    # If new quantity is 0, we might want to soft-delete the sale entirely or keep it as 0?
                    # Usually if 0 items, delete the sale.
                    if new_qty <= 0:
                        cur.execute('UPDATE sales SET deleted=1, quantity=0, selling_price=0, selling_price_base=0, vat_amount=0 WHERE id=?', (sale_id,))
                    else:
                        cur.execute('''
                            UPDATE sales 
                            SET quantity=?, selling_price=?, selling_price_base=?, vat_amount=? 
                            WHERE id=?
                        ''', (new_qty, new_price_try, new_price_base, vat_amt, sale_id))
                        
            return True
            
    except Exception as e:
        logger.error(f"Error delete_sale_allocation: {e}")
        return False
