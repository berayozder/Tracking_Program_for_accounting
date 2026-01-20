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


def undelete_sales_by_indices(indices: list[int]) -> int:
    """
    Clear Deleted flag for rows specified by zero-based indices in the full sales list.
    
    Args:
        indices: List of 0-based indices from 'list_sales(include_deleted=True)'.
        
    Returns:
        Number of rows updated.
    """
    try:
        full = list_sales(include_deleted=True)
        ids = [
            row['id'] for i, row in enumerate(full)
            if 0 <= i < len(full) and 'id' in row and i in indices
        ]
        if not ids:
            return 0
        with get_cursor() as (conn, cur):
            q = f"UPDATE sales SET deleted=0 WHERE id IN ({','.join(['?']*len(ids))})"
            cur.execute(q, tuple(ids))
            return cur.rowcount or 0
    except Exception as e:
        logger.error(f"Error in undelete_sales_by_indices: {e}")
        return 0


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
