import tkinter as tk
from tkinter import ttk, messagebox
import db.db as db
from .theme import stripe_treeview, maximize_window, themed_button, make_treeview_sortable, export_treeview_csv, apply_theme


def open_view_imports_window(root):
    window = tk.Toplevel(root)
    window.title("📦 View Imports")
    window.geometry("900x400")
    try:
        window.minsize(800, 360)
    except Exception:
        pass
    # Apply theme for consistent look
    try:
        apply_theme(window)
    except Exception:
        pass
    try:
        maximize_window(window)
    except Exception:
        pass

    rows = db.get_imports()
    if not rows:
        messagebox.showinfo("No data", "No imports found.")
        window.destroy()
        return

    # Search box
    search_frame = ttk.Frame(window)
    ttk.Label(search_frame, text='Search:').pack(side=tk.LEFT, padx=(8, 6))
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side=tk.LEFT)
    search_frame.pack(fill='x', pady=6)

    # Determine columns but hide FX and currency (imports are USD-only now)
    all_cols = list(rows[0].keys())
    cols = [c for c in all_cols if c not in ('fx_to_base', 'currency')]
    tree = ttk.Treeview(window, columns=cols, show='headings')
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=120, anchor=tk.CENTER)
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
        tree.heading(c, text=c)
    make_treeview_sortable(tree, cols)

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
        total_qty = 0.0
        total_cost_usd = 0.0
        for row in db.get_imports():
            if row_matches(row, search_var.get().strip()):
                tree.insert('', tk.END, values=[row.get(c, '') for c in cols])
                try:
                    q = float(row.get('quantity') or 0)
                    p = float(row.get('ordered_price') or 0)
                    total_qty += q
                    total_cost_usd += q * p
                except Exception:
                    pass
        totals_var.set(f"Rows: {len(tree.get_children())}    Total Qty: {total_qty:.2f}    Total Cost (USD): {total_cost_usd:.2f}")
        try:
            stripe_treeview(tree)
        except Exception:
            pass
        # reset selected badge
        try:
            selected_var.set('Selected: 0')
        except Exception:
            pass

    populate()

    def refresh():
        populate()

    def on_search_change(event=None):
        populate()

    # Update selected badge on selection changes
    def _update_selected_badge(event=None):
        try:
            selected_var.set(f"Selected: {len(tree.selection())}")
        except Exception:
            pass
    tree.bind('<<TreeviewSelect>>', _update_selected_badge)

    # Edit / Delete selected
    def get_selected_import():
        sel = tree.selection()
        if not sel:
            return None
        vals = tree.item(sel[0])['values']
        # map back to dict by cols
        return {c: vals[i] for i, c in enumerate(cols)}

    def do_delete():
        rec = get_selected_import()
        if not rec:
            messagebox.showwarning('Select', 'Select a row first')
            return
        if messagebox.askyesno('Confirm', 'Delete selected import?'):
            try:
                db.delete_import(int(rec.get('id')))
                refresh()
            except Exception as e:
                messagebox.showerror('Error', f'Failed to delete: {e}')

    def do_edit():
        rec = get_selected_import()
        if not rec:
            messagebox.showwarning('Select', 'Select a row first')
            return
        # open a simple modal to edit fields
        f = tk.Toplevel(window)
        f.title('Edit Import')
        f.geometry('400x400')
        entries = {}
        for i, c in enumerate(cols):
            ttk.Label(f, text=c).pack()
            e = ttk.Entry(f, width=40)
            # Prefill
            e.insert(0, rec.get(c, ''))
            e.pack()
            # Prevent editing currency; enforced via Record Import UI
            if c.lower() == 'currency':
                try:
                    e.config(state='disabled')
                except Exception:
                    pass
            entries[c] = e

        def save_edit():
            try:
                # Validate numeric fields
                new_price = float(entries.get('ordered_price').get().strip() or 0)
                new_qty = float(entries.get('quantity').get().strip() or 0)
                fx_val = None
                if 'fx_to_base' in entries:
                    txt = entries.get('fx_to_base').get().strip()
                    if txt:
                        v = float(txt)
                        if v <= 0:
                            messagebox.showerror('Invalid FX', 'FX rate must be greater than 0.')
                            return
                        fx_val = v
                db.edit_import(
                    int(rec.get('id')),
                    entries.get('date').get().strip(),
                    new_price,
                    new_qty,
                    entries.get('supplier').get().strip(),
                    entries.get('notes').get().strip(),
                    entries.get('category').get().strip(),
                    entries.get('subcategory').get().strip(),
                    fx_override=fx_val
                )
                f.destroy()
                refresh()
            except ValueError:
                messagebox.showerror('Invalid input', 'Price, Quantity and FX must be numbers.')
            except Exception as e:
                messagebox.showerror('Error', f'Failed to save: {e}')
        themed_button(f, text='Save', variant='primary', command=save_edit).pack(pady=8)

    # Toolbar with left/right grouping
    btn_frame = ttk.Frame(window)
    search_entry.bind('<KeyRelease>', on_search_change)
    primary_frame = ttk.Frame(btn_frame)
    primary_frame.pack(side='left', fill='x', expand=True)
    secondary_frame = ttk.Frame(btn_frame)
    secondary_frame.pack(side='right')

    themed_button(primary_frame, text='🔄 Refresh', variant='primary', command=refresh).pack(side=tk.LEFT, padx=(0, 8))
    themed_button(primary_frame, text='Select All', variant='primary', command=lambda: (select_all(), _update_selected_badge())).pack(side=tk.LEFT, padx=4)
    def deselect_all():
        try:
            tree.selection_remove(tree.get_children(''))
        except Exception:
            pass
    themed_button(primary_frame, text='Deselect All', variant='primary', command=lambda: (deselect_all(), _update_selected_badge())).pack(side=tk.LEFT, padx=4)

    themed_button(secondary_frame, text='✏️ Edit', variant='success', command=do_edit).pack(side=tk.LEFT, padx=4)
    themed_button(secondary_frame, text='🗑️ Delete', variant='danger', command=do_delete).pack(side=tk.LEFT, padx=4)
    themed_button(secondary_frame, text='📄 Export CSV', variant='secondary', command=lambda: export_treeview_csv(window, tree, cols, 'Export Imports')).pack(side=tk.LEFT, padx=(8, 0))

    btn_frame.pack(fill='x', pady=8)
