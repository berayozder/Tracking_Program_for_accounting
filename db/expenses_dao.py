from .imports_dao import recompute_import_batches
from .connection import get_cursor
from .audit import write_audit
from .settings import get_default_expense_currency, get_base_currency
from .crypto import encrypt_str, decrypt_str
from .auth import require_admin
from .imports_dao import recompute_import_batches



from typing import Optional
from core.vat_utils import compute_vat


def add_expense(date, amount, is_import_related=False, import_id=None, category=None, notes=None, document_path=None, import_ids=None, currency: Optional[str] = None, conn=None, cur=None):
    ids = []
    if import_ids:
        for v in import_ids:
            try:
                ids.append(int(v))
            except Exception:
                pass
        ids = list(dict.fromkeys(ids))
    first_id = None
    if ids:
        first_id = ids[0]
    elif import_id:
        try:
            first_id = int(import_id)
            ids = [first_id]
        except Exception:
            first_id = None

    enc_notes = encrypt_str(notes or '')
    exp_ccy = ((currency or get_default_expense_currency() or get_base_currency() or '')).upper()
    # VAT logic
    vat_rate = 18.0
    is_vat_inclusive = True
    if isinstance(notes, dict):
        vat_rate = float(notes.get('vat_rate', 18.0))
        is_vat_inclusive = bool(notes.get('is_vat_inclusive', True))
    net, vat = compute_vat(amount, vat_rate, is_vat_inclusive)
    if conn is not None and cur is not None:
        _conn, _cur = conn, cur
    else:
        from .connection import get_cursor
        with get_cursor() as (_conn, _cur):
            return add_expense(date, amount, is_import_related, import_id, category, notes, document_path, import_ids, currency, conn=_conn, cur=_cur)
    try:
        _cur.execute('''INSERT INTO expenses (date, amount, is_import_related, import_id, category, notes, document_path, currency, vat_rate, vat_amount, is_vat_inclusive)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (date, amount, 1 if is_import_related else 0, first_id, category, enc_notes, document_path, exp_ccy, vat_rate, vat, 1 if is_vat_inclusive else 0))
        expense_id = _cur.lastrowid
        try:
            for iid in ids:
                _cur.execute('INSERT OR IGNORE INTO expense_import_links (expense_id, import_id) VALUES (?,?)', (expense_id, iid))
        except Exception:
            pass
        try:
            write_audit('add', 'expense', str(expense_id), f"amount={amount}", cur=_cur)
            print(f"[DEBUG] Wrote audit log for expense id: {expense_id}")
        except Exception as e:
            print(f"[DEBUG] Failed to write audit log: {e}")
    except Exception as e:
        print(f"[DEBUG] Exception during DB insert: {e}")

    # Trigger recompute for each linked import so batch costs reflect this expense
    try:
        if ids:
            for iid in ids:
                try:
                    recompute_import_batches(int(iid))
                    print(f"[DEBUG] Recomputed import batch for import_id: {iid}")
                except Exception as e:
                    print(f"[DEBUG] Failed to recompute import batch for {iid}: {e}")
    except Exception as e:
        print(f"[DEBUG] Exception during recompute_import_batches: {e}")




def get_expenses(limit=500):
    with get_cursor() as (conn, cur):
        try:
            cur.execute('SELECT id, date, amount, is_import_related, import_id, category, notes, document_path, currency, vat_rate, vat_amount, is_vat_inclusive FROM active_expenses ORDER BY id DESC LIMIT ?', (limit,))
        except Exception:
            cur.execute('SELECT id, date, amount, is_import_related, import_id, category, notes, document_path, currency, vat_rate, vat_amount, is_vat_inclusive FROM expenses ORDER BY id DESC LIMIT ?', (limit,))
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        r['notes'] = decrypt_str(r.get('notes'))
        # Calculate net and gross
        is_incl = r.get('is_vat_inclusive', 1)
        amt = r.get('amount', 0) or 0
        vat = r.get('vat_amount', 0) or 0
        r['net_amount'] = amt - vat if is_incl else amt
        r['gross_amount'] = amt if is_incl else amt + vat
    return rows


def edit_expense(expense_id, date, amount, is_import_related=False, import_id=None, category=None, notes=None, document_path=None, import_ids=None, currency: Optional[str] = None):

    # --- ids logic ---
    ids = []
    if import_ids:
        for v in import_ids:
            try:
                ids.append(int(v))
            except Exception:
                pass
        ids = list(dict.fromkeys(ids))
    first_id = None
    if ids:
        first_id = ids[0]
    elif import_id:
        try:
            first_id = int(import_id)
            ids = [first_id]
        except Exception:
            first_id = None

    enc_notes = encrypt_str(notes or '')
    exp_ccy = ((currency or get_default_expense_currency() or get_base_currency() or '')).upper()
    # VAT logic
    vat_rate = 18.0
    is_vat_inclusive = True
    if isinstance(notes, dict):
        vat_rate = float(notes.get('vat_rate', 18.0))
        is_vat_inclusive = bool(notes.get('is_vat_inclusive', True))
    net, vat = compute_vat(amount, vat_rate, is_vat_inclusive)
    with get_cursor() as (conn, cur):
        cur.execute('''UPDATE expenses SET date=?, amount=?, is_import_related=?, import_id=?, category=?, notes=?, document_path=?, currency=?, vat_rate=?, vat_amount=?, is_vat_inclusive=? WHERE id=?''',
                    (date, amount, 1 if is_import_related else 0, first_id, category, enc_notes, document_path, exp_ccy, vat_rate, vat, 1 if is_vat_inclusive else 0, expense_id))
        try:
            cur.execute('DELETE FROM expense_import_links WHERE expense_id=?', (expense_id,))
            for iid in ids:
                cur.execute('INSERT OR IGNORE INTO expense_import_links (expense_id, import_id) VALUES (?,?)', (expense_id, iid))
        except Exception:
            pass
        write_audit('edit', 'expense', str(expense_id), f"amount={amount}", cur=cur)

    # Trigger recompute for each linked import so batch costs reflect this expense
    try:
        if ids:
            for iid in ids:
                try:
                    recompute_import_batches(int(iid))
                except Exception:
                    pass
    except Exception:
        pass




def get_expense_import_links(expense_id):
    with get_cursor() as (conn, cur):
        cur.execute('SELECT import_id FROM expense_import_links WHERE expense_id=? ORDER BY import_id', (expense_id,))
        rows = [r['import_id'] if hasattr(r, 'keys') else r[0] for r in cur.fetchall()]
    return rows


def delete_expense(expense_id):
    try:
        linked = get_expense_import_links(expense_id)
        if linked:
            for iid in linked:
                try:
                    recompute_import_batches(int(iid))
                except Exception:
                    pass
    except Exception:
        pass
    require_admin('delete', 'expense', str(expense_id))
    with get_cursor() as (conn, cur):
        cur.execute('UPDATE expenses SET deleted = 1 WHERE id=?', (expense_id,))
        write_audit('delete', 'expense', str(expense_id), cur=cur)




def undelete_expense(expense_id):
    try:
        linked = get_expense_import_links(expense_id)
        if linked:
            for iid in linked:
                try:
                    recompute_import_batches(int(iid))
                except Exception:
                    pass
    except Exception:
        pass
    try:
        with get_cursor() as (conn, cur):
            cur.execute('UPDATE expenses SET deleted = 0 WHERE id = ?', (expense_id,))
    except Exception:
        return False


    return True
