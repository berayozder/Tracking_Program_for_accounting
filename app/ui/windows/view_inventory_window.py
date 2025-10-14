import tkinter as tk
from tkinter import ttk, messagebox
import db
from .theme import stripe_treeview, maximize_window, apply_theme, themed_button


def open_view_inventory_window(root):
    window = tk.Toplevel(root)
    window.title("📦 Inventory")
    window.geometry("700x400")
    try:
        window.minsize(620, 340)
    except Exception:
        pass
    # Apply theme for consistent styling
    try:
        apply_theme(window)
    except Exception:
        pass
    try:
        maximize_window(window)
    except Exception:
        pass

    rows = db.get_inventory()
    if not rows:
        messagebox.showinfo("No data", "No inventory found.")
        window.destroy()
        return

    # Search box
    search_frame = tk.Frame(window)
    tk.Label(search_frame, text='Search:').pack(side=tk.LEFT, padx=(8, 6))
    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side=tk.LEFT)
    search_frame.pack(fill='x', pady=6)

    cols = list(rows[0].keys())
    tree = ttk.Treeview(window, columns=cols, show='headings')
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=150, anchor=tk.CENTER)
    tree.pack(expand=True, fill='both')

    # Select All helper and key bindings
    def select_all(event=None):
        try:
            tree.selection_set(tree.get_children(''))
            return 'break'
        except Exception:
            return None
    try:
        tree.bind('<Control-a>', select_all)
        tree.bind('<Command-a>', select_all)  # macOS
    except Exception:
        pass

    # Column sorting helper
    sort_state = {}

    def _coerce_for_sort(col_name, value):
        v = '' if value is None else str(value)
        if col_name.lower().endswith('date') or col_name.lower() in ('date',):
            from datetime import datetime as _dt
            try:
                return _dt.strptime(v, '%Y-%m-%d')
            except Exception:
                pass
        try:
            return float(v)
        except Exception:
            return v.lower()

    def sort_by_column(col):
        reverse = sort_state.get(col, False)
        items = [(iid, tree.item(iid)['values']) for iid in tree.get_children('')]
        try:
            idx = cols.index(col)
        except ValueError:
            idx = 0
        items.sort(key=lambda t: _coerce_for_sort(col, t[1][idx] if idx < len(t[1]) else ''), reverse=reverse)
        for pos, (iid, _) in enumerate(items):
            tree.move(iid, '', pos)
        sort_state[col] = not reverse

    for c in cols:
        tree.heading(c, text=c, command=lambda cc=c: sort_by_column(cc))

    def row_matches(r, q):
        if not q:
            return True
        ql = q.lower()
        for c in cols:
            v = str(r.get(c, '')).lower()
            if ql in v:
                return True
        return False

    # Totals + Selected badge
    totals_row = ttk.Frame(window)
    totals_row.pack(fill='x', padx=8, pady=4)
    totals_var = tk.StringVar(value='')
    ttk.Label(totals_row, textvariable=totals_var, anchor='w').pack(side='left')
    selected_var = tk.StringVar(value='Selected: 0')
    ttk.Label(totals_row, textvariable=selected_var, anchor='e').pack(side='right')

    def populate():
        for r in tree.get_children():
            tree.delete(r)
        count = 0
        total_qty = 0.0
        for row in db.get_inventory():
            if row_matches(row, search_var.get().strip()):
                tree.insert('', tk.END, values=[row.get(c, '') for c in cols])
                count += 1
                try:
                    total_qty += float(row.get('quantity') or 0)
                except Exception:
                    pass
        totals_var.set(f"Rows: {count}    Total Qty: {total_qty:.2f}")
        try:
            stripe_treeview(tree)
        except Exception:
            pass
        try:
            selected_var.set('Selected: 0')
        except Exception:
            pass

    populate()

    def refresh():
        populate()

    def on_search_change(event=None):
        populate()

    search_entry.bind('<KeyRelease>', on_search_change)
    def _update_selected_badge(event=None):
        try:
            selected_var.set(f"Selected: {len(tree.selection())}")
        except Exception:
            pass
    tree.bind('<<TreeviewSelect>>', _update_selected_badge)
    # Toolbar with left/right grouping
    btns = ttk.Frame(window)
    primary_frame = ttk.Frame(btns)
    primary_frame.pack(side='left', fill='x', expand=True)
    secondary_frame = ttk.Frame(btns)
    secondary_frame.pack(side='right')

    themed_button(primary_frame, text='🔄 Refresh', variant='primary', command=refresh).pack(side=tk.LEFT, padx=(0, 8))
    themed_button(primary_frame, text='Select All', variant='primary', command=lambda: (select_all(), _update_selected_badge())).pack(side=tk.LEFT, padx=4)
    def deselect_all():
        try:
            tree.selection_remove(tree.get_children(''))
        except Exception:
            pass
    themed_button(primary_frame, text='Deselect All', variant='primary', command=lambda: (deselect_all(), _update_selected_badge())).pack(side=tk.LEFT, padx=4)
    btns.pack(fill='x', pady=8)
