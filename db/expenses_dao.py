from .imports_dao import recompute_import_batches
from .connection import get_cursor
from .audit import write_audit
from .settings import get_default_expense_currency, get_base_currency
from .crypto import encrypt_str, decrypt_str
from .auth import require_admin
from .imports_dao import recompute_import_batches


from typing import Optional


def add_expense(date, amount, is_import_related=False, import_id=None, category=None, notes=None, document_path=None, import_ids=None, currency: Optional[str] = None):

    print(f"[DEBUG] add_expense called with: date={date}, amount={amount}, is_import_related={is_import_related}, import_id={import_id}, category={category}, notes={notes}, document_path={document_path}, import_ids={import_ids}, currency={currency}")
    ids = []
    if import_ids:
        for v in import_ids:
            try:
                ids.append(int(v))
            except Exception as e:
                print(f"[DEBUG] Failed to convert import_id '{v}' to int: {e}")
        ids = list(dict.fromkeys(ids))
    print(f"[DEBUG] ids after processing import_ids: {ids}")
    first_id = None
    if ids:
        first_id = ids[0]
    elif import_id:
        try:
            first_id = int(import_id)
            ids = [first_id]
        except Exception as e:
            print(f"[DEBUG] Failed to convert import_id '{import_id}' to int: {e}")
            first_id = None

    print(f"[DEBUG] first_id: {first_id}")
    enc_notes = encrypt_str(notes or '')
    print(f"[DEBUG] enc_notes: {enc_notes}")
    exp_ccy = ((currency or get_default_expense_currency() or get_base_currency() or '')).upper()
    print(f"[DEBUG] exp_ccy: {exp_ccy}")
    try:
        with get_cursor() as (conn, cur):
            print(f"[DEBUG] Got DB cursor: conn={conn}, cur={cur}")
            cur.execute('''INSERT INTO expenses (date, amount, is_import_related, import_id, category, notes, document_path, currency)
                        VALUES (?,?,?,?,?,?,?,?)''', (date, amount, 1 if is_import_related else 0, first_id, category, enc_notes, document_path, exp_ccy))
            expense_id = cur.lastrowid
            print(f"[DEBUG] Inserted expense with id: {expense_id}")
            try:
                for iid in ids:
                    cur.execute('INSERT OR IGNORE INTO expense_import_links (expense_id, import_id) VALUES (?,?)', (expense_id, iid))
                    print(f"[DEBUG] Linked expense {expense_id} to import {iid}")
            except Exception as e:
                print(f"[DEBUG] Failed to link expense to import: {e}")
            try:
                write_audit('add', 'expense', str(expense_id), f"amount={amount}", cur=cur)
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
            cur.execute('SELECT id, date, amount, is_import_related, import_id, category, notes, document_path, currency FROM active_expenses ORDER BY id DESC LIMIT ?', (limit,))
        except Exception:
            cur.execute('SELECT id, date, amount, is_import_related, import_id, category, notes, document_path, currency FROM expenses ORDER BY id DESC LIMIT ?', (limit,))
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        r['notes'] = decrypt_str(r.get('notes'))
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
    with get_cursor() as (conn, cur):
        cur.execute('''UPDATE expenses SET date=?, amount=?, is_import_related=?, import_id=?, category=?, notes=?, document_path=?, currency=? WHERE id=?''',
                    (date, amount, 1 if is_import_related else 0, first_id, category, enc_notes, document_path, exp_ccy, expense_id))
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
