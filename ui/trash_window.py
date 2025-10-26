import tkinter as tk
from tkinter import ttk, messagebox
import db as db


def _rows_for_table(table: str, extra_where: str = ''):
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        q = f"SELECT * FROM {table} WHERE (deleted IS NOT NULL AND deleted=1) OR (voided IS NOT NULL AND voided=1) {extra_where} ORDER BY id DESC LIMIT 500"
        cur.execute(q)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return []


def open_trash_window(root):
    win = tk.Toplevel(root)
    win.title('Trash / Archive')
    win.geometry('900x560')
    try:
        from .theme import apply_theme
        apply_theme(win)
    except Exception:
        pass

    nb = ttk.Notebook(win)
    nb.pack(fill='both', expand=True, padx=8, pady=8)

    tables = [
        ('Sales', 'sales'),
        ('Imports', 'imports'),
        ('Import Batches', 'import_batches'),
        ('Expenses', 'expenses'),
        ('Returns', 'returns'),
    ]

    tree_by_tab = {}

    for label, table in tables:
        frame = ttk.Frame(nb)
        nb.add(frame, text=label)
        cols = ('id', 'date', 'category', 'subcategory', 'info')
        tv = ttk.Treeview(frame, columns=cols, show='headings', selectmode='browse')
        for c in cols:
            tv.heading(c, text=c.title())
            tv.column(c, width=120 if c != 'info' else 380, anchor='w')
        tv.pack(fill='both', expand=True, side='left', padx=(0,6), pady=6)
        sb = ttk.Scrollbar(frame, orient='vertical', command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side='left', fill='y')
        tree_by_tab[table] = tv

        # bottom controls
        ctl_fr = ttk.Frame(frame)
        ctl_fr.pack(fill='x', side='bottom', padx=6, pady=6)
        def _refresh(t=table):
            tv.delete(*tv.get_children())
            rows = _rows_for_table(t)
            for r in rows:
                info = ''
                try:
                    info = r.get('platform') or r.get('supplier') or r.get('notes') or ''
                except Exception:
                    info = ''
                d = r.get('date') or r.get('return_date') or r.get('batch_date') or ''
                tv.insert('', 'end', values=(r.get('id'), d, r.get('category'), r.get('subcategory'), (info or '')[:200]))

        def _on_restore(t=table):
            sel = tv.selection()
            if not sel:
                messagebox.showinfo('Restore', 'Select a row to restore')
                return
            item = tv.item(sel[0])
            rid = item['values'][0]
            ok = messagebox.askyesno('Restore', f'Restore {t} id={rid}?')
            if not ok:
                return
            try:
                db.restore_entity(t, 'id', rid)
                messagebox.showinfo('Restore', 'Restored')
                _refresh(t)
            except Exception as e:
                messagebox.showerror('Restore error', str(e))

        def _on_purge(t=table):
            sel = tv.selection()
            if not sel:
                messagebox.showinfo('Purge', 'Select a row to permanently delete')
                return
            item = tv.item(sel[0])
            rid = item['values'][0]
            ok = messagebox.askyesno('Purge', f'Permanently delete {t} id={rid}? This cannot be undone.')
            if not ok:
                return
            try:
                # require admin
                try:
                    db.require_admin('purge', t, str(rid))
                except Exception:
                    # will raise if not admin
                    messagebox.showerror('Permission', 'Admin permission required to purge')
                    return
                conn = db.get_conn()
                cur = conn.cursor()
                cur.execute(f'DELETE FROM {t} WHERE id=?', (rid,))
                conn.commit()
                conn.close()
                try:
                    db.write_audit('purge', t, str(rid), 'purged via trash UI')
                except Exception:
                    pass
                messagebox.showinfo('Purge', 'Deleted')
                _refresh(t)
            except Exception as e:
                messagebox.showerror('Purge error', str(e))

        btn_fr = ttk.Frame(ctl_fr)
        btn_fr.pack(side='right')
        ttk.Button(btn_fr, text='Refresh', command=_refresh).pack(side='left', padx=6)
        ttk.Button(btn_fr, text='Restore', command=_on_restore).pack(side='left', padx=6)
        ttk.Button(btn_fr, text='Purge', command=_on_purge).pack(side='left', padx=6)

        # initial load
        _refresh()

    return win
