import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import csv
import db
from .theme import maximize_window, stripe_treeview, themed_button, make_treeview_sortable, export_treeview_csv


def open_audit_log_window(root):
    win = tk.Toplevel(root)
    win.title('Audit Log')
    win.geometry('980x560')
    try:
        win.minsize(880, 460)
    except Exception:
        pass
    try:
        maximize_window(win)
    except Exception:
        pass

    # Filters frame
    filt = ttk.LabelFrame(win, text='Filters', padding=8)
    filt.pack(fill='x', padx=8, pady=(8, 0))

    start_var = tk.StringVar()
    end_var = tk.StringVar()
    user_var = tk.StringVar()
    action_var = tk.StringVar()
    entity_var = tk.StringVar()
    q_var = tk.StringVar()

    # Load dropdown values
    users = [''] + (db.get_audit_distinct('user') or [])
    actions = [''] + (db.get_audit_distinct('action') or [])
    entities = [''] + (db.get_audit_distinct('entity') or [])

    row1 = ttk.Frame(filt)
    row1.pack(fill='x', pady=4)
    ttk.Label(row1, text='Start (YYYY-MM-DD)').pack(side='left')
    start_e = ttk.Entry(row1, textvariable=start_var, width=14)
    start_e.pack(side='left', padx=(6, 16))
    ttk.Label(row1, text='End').pack(side='left')
    end_e = ttk.Entry(row1, textvariable=end_var, width=14)
    end_e.pack(side='left', padx=(6, 16))
    ttk.Label(row1, text='User').pack(side='left')
    user_cb = ttk.Combobox(row1, values=users, textvariable=user_var, width=18)
    user_cb.pack(side='left', padx=(6, 16))
    ttk.Label(row1, text='Action').pack(side='left')
    action_cb = ttk.Combobox(row1, values=actions, textvariable=action_var, width=18)
    action_cb.pack(side='left', padx=(6, 16))
    ttk.Label(row1, text='Entity').pack(side='left')
    entity_cb = ttk.Combobox(row1, values=entities, textvariable=entity_var, width=18)
    entity_cb.pack(side='left', padx=(6, 16))

    row2 = ttk.Frame(filt)
    row2.pack(fill='x', pady=(0, 4))
    ttk.Label(row2, text='Text contains').pack(side='left')
    q_e = ttk.Entry(row2, textvariable=q_var, width=40)
    q_e.pack(side='left', padx=(6, 16))
    themed_button(row2, text='🔍 Search', variant='primary', command=lambda: populate()).pack(side='left', padx=4)
    themed_button(row2, text='Reset', variant='secondary', command=lambda: reset_filters()).pack(side='left', padx=4)
    themed_button(row2, text='Export CSV', variant='secondary', command=lambda: export_treeview_csv(win, tree, cols, 'Export Audit Log')).pack(side='right')

    # Table
    cols = ['id', 'ts', 'user', 'action', 'entity', 'ref_id', 'details']
    tree = ttk.Treeview(win, columns=cols, show='headings')
    for c in cols:
        tree.heading(c, text=c)
        width = 90 if c in ('id', 'user', 'action', 'entity') else 160
        if c == 'details':
            width = 320
        tree.column(c, width=width, anchor=tk.W if c in ('details', 'entity', 'action', 'user') else tk.CENTER)
    tree.pack(fill='both', expand=True, padx=8, pady=8)

    make_treeview_sortable(tree, cols)

    def populate():
        tree.delete(*tree.get_children())
        rows = db.get_audit_logs(
            start_date=(start_var.get().strip() or None),
            end_date=(end_var.get().strip() or None),
            user=(user_var.get().strip() or None),
            action=(action_var.get().strip() or None),
            entity=(entity_var.get().strip() or None),
            q=(q_var.get().strip() or None),
            limit=5000,
        )
        for r in rows:
            tree.insert('', tk.END, values=[r.get(c, '') for c in cols])
        try:
            stripe_treeview(tree)
        except Exception:
            pass

    def reset_filters():
        start_var.set('')
        end_var.set('')
        user_var.set('')
        action_var.set('')
        entity_var.set('')
        q_var.set('')
        populate()

    # export handled via export_treeview_csv utility

    def on_double_click(event):
        sel = tree.selection()
        if not sel:
            return
        vals = tree.item(sel[0])['values']
        detail = vals[cols.index('details')] if 'details' in cols else ''
        # Show details in a simple popup
        dlg = tk.Toplevel(win)
        dlg.title('Audit Details')
        dlg.geometry('640x420')
        txt = tk.Text(dlg, wrap='word')
        txt.pack(fill='both', expand=True)
        try:
            txt.insert('1.0', str(detail))
        except Exception:
            txt.insert('1.0', '')
        txt.config(state='disabled')
        themed_button(dlg, text='Close', variant='secondary', command=dlg.destroy).pack(pady=8)

    tree.bind('<Double-1>', on_double_click)

    populate()
