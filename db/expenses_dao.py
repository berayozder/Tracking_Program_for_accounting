"""Expense tracking and management."""
from __future__ import annotations

import logging
from typing import Optional, Any, Union

from .connection import get_cursor
from .audit import write_audit
from .settings import get_default_expense_currency, get_base_currency
from .crypto import encrypt_str, decrypt_str
from .auth import require_admin
from .imports_dao import recompute_import_batches
from core.vat_utils import compute_vat

logger = logging.getLogger(__name__)


def _parse_import_ids(import_ids: Optional[list[Any]], single_import_id: Optional[Any]) -> tuple[list[int], Optional[int]]:
    """Helper to parse and deduplicate import IDs."""
    ids: list[int] = []
    if import_ids:
        for v in import_ids:
            try:
                ids.append(int(v))
            except Exception:
                pass
        ids = list(dict.fromkeys(ids))  # deduplicate preserving order

    first_id = None
    if ids:
        first_id = ids[0]
    elif single_import_id:
        try:
            first_id = int(single_import_id)
            ids = [first_id]
        except Exception:
            first_id = None
            
    return ids, first_id


def add_expense(
    date: str,
    amount: float,
    is_import_related: bool = False,
    import_id: Optional[Any] = None,
    category: Optional[str] = None,
    notes: Optional[str] = None,
    document_path: Optional[str] = None,
    import_ids: Optional[list[Any]] = None,
    currency: Optional[str] = None,
    vat_rate: float = 20.0,
    vat_inclusive: bool = True,
    conn=None,
    cur=None
) -> Optional[int]:
    """
    Add a new expense record.
    
    Args:
        date: Date string (YYYY-MM-DD).
        amount: Expense amount.
        is_import_related: Whether related to an import.
        import_id: Single import ID (legacy/primary).
        category: Expense category.
        notes: Description/notes.
        document_path: Path to related document.
        import_ids: List of related import IDs.
        currency: Currency code.
        vat_rate: VAT rate percentage.
        vat_inclusive: Whether amount includes VAT.
        conn: Optional existing DB connection.
        cur: Optional existing DB cursor.
        
    Returns:
        The new expense ID or None on failure.
    """
    ids, first_id = _parse_import_ids(import_ids, import_id)

    enc_notes = encrypt_str(notes or '')
    exp_ccy = ((currency or get_default_expense_currency() or get_base_currency() or '')).upper()
    
    net, vat = compute_vat(amount, vat_rate, vat_inclusive)
    
    net_amount = net
    gross_amount = amount if vat_inclusive else (amount + vat)

    if conn is not None and cur is not None:
        _cur = cur
    else:
        # If no cursor provided, create a context manager (but we need to return from it)
        # Recursive call is safest simple refactor if not rewriting context handling fully
        from .connection import get_cursor
        with get_cursor() as (_conn_ctx, _cur_ctx):
            return add_expense(
                date, amount, is_import_related, import_id, category, notes, 
                document_path, import_ids, currency, vat_rate, vat_inclusive, 
                conn=_conn_ctx, cur=_cur_ctx
            )

    try:
        _cur.execute('''
            INSERT INTO expenses (
                date, amount, is_import_related, import_id, category, notes, 
                document_path, currency, vat_rate, vat_amount, is_vat_inclusive, 
                net_amount, gross_amount
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            date, amount, 1 if is_import_related else 0, first_id, category, 
            enc_notes, document_path, exp_ccy, vat_rate, vat, 
            1 if vat_inclusive else 0, net_amount, gross_amount
        ))
        expense_id = _cur.lastrowid
        
        try:
            for iid in ids:
                _cur.execute(
                    'INSERT OR IGNORE INTO expense_import_links (expense_id, import_id) VALUES (?,?)', 
                    (expense_id, iid)
                )
        except Exception:
            pass
            
        try:
            write_audit('add', 'expense', str(expense_id), f"amount={amount}", cur=_cur)
            logger.debug(f"Wrote audit log for expense id: {expense_id}")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
            
    except Exception as e:
        logger.error(f"Exception during DB insert: {e}")
        return None

    # Trigger recompute
    try:
        if ids:
            for iid in ids:
                try:
                    recompute_import_batches(int(iid), conn=conn, cur=_cur)
                    logger.debug(f"Recomputed import batch for import_id: {iid}")
                except Exception as e:
                    logger.warning(f"Failed to recompute import batch for {iid}: {e}")
    except Exception as e:
        logger.error(f"Exception during recompute_import_batches: {e}")
    
    return expense_id


def get_expenses(limit: int = 500, offset: int = 0) -> list[dict[str, Any]]:
    """
    Fetch duplicate-free list of expenses with pagination.
    
    Args:
        limit: Max rows to return.
        offset: Offset for pagination.
        
    Returns:
        List of expense dictionaries.
    """
    with get_cursor() as (conn, cur):
        try:
            cur.execute(
                'SELECT id, date, amount, is_import_related, import_id, category, notes, '
                'document_path, currency, vat_rate, vat_amount, is_vat_inclusive '
                'FROM active_expenses ORDER BY id DESC LIMIT ? OFFSET ?', 
                (limit, offset)
            )
        except Exception:
            # Fallback if view doesn't exist
            cur.execute(
                'SELECT id, date, amount, is_import_related, import_id, category, notes, '
                'document_path, currency, vat_rate, vat_amount, is_vat_inclusive '
                'FROM expenses ORDER BY id DESC LIMIT ? OFFSET ?', 
                (limit, offset)
            )
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        r['notes'] = decrypt_str(r.get('notes'))
        # Calculate derived net/gross for display
        is_incl = r.get('is_vat_inclusive', 1)
        amt = r.get('amount', 0) or 0
        vat = r.get('vat_amount', 0) or 0
        r['net_amount'] = amt - vat if is_incl else amt
        r['gross_amount'] = amt if is_incl else amt + vat
        
    return rows


def edit_expense(
    expense_id: int,
    date: str,
    amount: float,
    is_import_related: bool = False,
    import_id: Optional[Any] = None,
    category: Optional[str] = None,
    notes: Optional[str] = None,
    document_path: Optional[str] = None,
    import_ids: Optional[list[Any]] = None,
    currency: Optional[str] = None,
    vat_rate: float = 20.0,
    vat_inclusive: bool = True
) -> None:
    """
    Update an existing expense record.
    """
    ids, first_id = _parse_import_ids(import_ids, import_id)

    enc_notes = encrypt_str(notes or '')
    exp_ccy = ((currency or get_default_expense_currency() or get_base_currency() or '')).upper()
    
    net, vat = compute_vat(amount, vat_rate, vat_inclusive)
    
    net_amount = net
    gross_amount = amount if vat_inclusive else (amount + vat)
    
    with get_cursor() as (conn, cur):
        cur.execute('''
            UPDATE expenses 
            SET date=?, amount=?, is_import_related=?, import_id=?, category=?, notes=?, 
                document_path=?, currency=?, vat_rate=?, vat_amount=?, is_vat_inclusive=?, 
                net_amount=?, gross_amount=? 
            WHERE id=?
        ''', (
            date, amount, 1 if is_import_related else 0, first_id, category, 
            enc_notes, document_path, exp_ccy, vat_rate, vat, 
            1 if vat_inclusive else 0, net_amount, gross_amount, expense_id
        ))
        
        try:
            cur.execute('DELETE FROM expense_import_links WHERE expense_id=?', (expense_id,))
            for iid in ids:
                cur.execute(
                    'INSERT OR IGNORE INTO expense_import_links (expense_id, import_id) VALUES (?,?)', 
                    (expense_id, iid)
                )
        except Exception:
            pass
            
        write_audit('edit', 'expense', str(expense_id), f"amount={amount}", cur=cur)

        # Trigger recompute
        try:
            if ids:
                for iid in ids:
                    try:
                        recompute_import_batches(int(iid), conn=conn, cur=cur)
                    except Exception:
                        pass
        except Exception:
            pass


def get_expense_import_links(expense_id: int) -> list[int]:
    """Get list of import IDs linked to an expense."""
    with get_cursor() as (conn, cur):
        cur.execute(
            'SELECT import_id FROM expense_import_links WHERE expense_id=? ORDER BY import_id', 
            (expense_id,)
        )
        rows = [r['import_id'] if hasattr(r, 'keys') else r[0] for r in cur.fetchall()]
    return rows


def delete_expense(expense_id: int) -> None:
    """Soft delete an expense."""
    require_admin('delete', 'expense', str(expense_id))
    
    with get_cursor() as (conn, cur):
        cur.execute('UPDATE expenses SET deleted = 1 WHERE id=?', (expense_id,))
        write_audit('delete', 'expense', str(expense_id), cur=cur)

        # Recompute after delete
        try:
            linked = get_expense_import_links(expense_id)
            if linked:
                for iid in linked:
                    try:
                        recompute_import_batches(int(iid), conn=conn, cur=cur)
                    except Exception:
                        pass
        except Exception:
            pass


def undelete_expense(expense_id: int) -> bool:
    """Restore a soft-deleted expense."""
    try:
        linked = get_expense_import_links(expense_id)
    except Exception:
        pass
        
    try:
        with get_cursor() as (conn, cur):
            cur.execute('UPDATE expenses SET deleted = 0 WHERE id = ?', (expense_id,))
            
            # Recompute after undelete
            try:
                if linked:
                    for iid in linked:
                        try:
                            recompute_import_batches(int(iid), conn=conn, cur=cur)
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        return False

    return True
