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

    show_deleted_var = tk.BooleanVar(value=False)

    def _fetch_imports(include_deleted: bool = False):
        if include_deleted:
            try:
                conn = db.get_conn()
                cur = conn.cursor()
                cur.execute('SELECT id, date, ordered_price, quantity, supplier, notes, category, subcategory, currency, deleted FROM imports ORDER BY id DESC')
                rows = [dict(r) for r in cur.fetchall()]
                conn.close()
                return rows
            except Exception:
                return []
        return db.get_imports()

    def populate():
        for r in tree.get_children():
            tree.delete(r)
        total_qty = 0.0
        total_cost_usd = 0.0
        # Collect rows that match search, then sort newest->oldest for display
        fetched = list(_fetch_imports(show_deleted_var.get()))
        shown_rows = []
        for row in fetched:
            if row_matches(row, search_var.get().strip()):
                shown_rows.append(row)
        # Sort by numeric id if available, otherwise by date string (YYYY-MM-DD) — newest first
        def _sort_key(r):
            try:
                return int(r.get('id'))
            except Exception:
                try:
                    return r.get('date') or ''
                except Exception:
                    return ''
        shown_rows.sort(key=_sort_key, reverse=True)

        for row in shown_rows:
            tree.insert('', 'end', values=[row.get(c, '') for c in cols])
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

    def do_undelete():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning('Select', 'Select at least one row first')
            return
        count = len(sel)
        if not messagebox.askyesno('Confirm', f'Undelete {count} selected imports?'):
            return
        any_done = False
        for iid in sel:
            try:
                vals = tree.item(iid).get('values', ())
                rec = {c: vals[i] for i, c in enumerate(cols) if i < len(vals)}
                iid_val = rec.get('id') or (vals[0] if vals else None)
                if iid_val is None:
                    continue
                db.undelete_import(int(iid_val))
                any_done = True
            except Exception:
                continue
        if any_done:
            refresh()

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
        sel = tree.selection()
        if not sel:
            messagebox.showwarning('Select', 'Select at least one row first')
            return
        count = len(sel)
        if count == 1:
            prompt = 'Soft-delete the selected import? This will hide it from views but keep a record.'
        else:
            prompt = f'Soft-delete {count} selected imports? This will hide them from views but keep records.'
        if not messagebox.askyesno('Confirm', prompt):
            return

        any_deleted = False
        for iid in sel:
            try:
                vals = tree.item(iid).get('values', ())
                # map back to dict by cols
                rec = {c: vals[i] for i, c in enumerate(cols) if i < len(vals)}
                iid_val = rec.get('id') or (vals[0] if vals else None)
                if iid_val is None:
                    continue
                db.delete_import(int(iid_val))
                any_deleted = True
            except Exception:
                continue
        if any_deleted:
            refresh()

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

    # Secondary actions: edit, delete, undelete, export
    themed_button(secondary_frame, text='✏️ Edit', variant='success', command=do_edit).pack(side=tk.LEFT, padx=4)
    themed_button(secondary_frame, text='🗑️ Delete', variant='danger', command=do_delete).pack(side=tk.LEFT, padx=4)
    themed_button(secondary_frame, text='📋 Show Lines', variant='secondary', command=lambda: show_lines_for_selected()).pack(side=tk.LEFT, padx=4)
    ttk.Checkbutton(secondary_frame, text='Show deleted', variable=show_deleted_var, command=refresh).pack(side=tk.LEFT, padx=(6, 4))
    themed_button(secondary_frame, text='♻️ Undelete', variant='primary', command=do_undelete).pack(side=tk.LEFT, padx=4)
    themed_button(secondary_frame, text='📄 Export CSV', variant='secondary', command=lambda: export_treeview_csv(window, tree, cols, 'Export Imports')).pack(side=tk.LEFT, padx=(8, 0))

    btn_frame.pack(fill='x', pady=8)

    def show_lines_for_selected():
        rec = get_selected_import()
        if not rec:
            messagebox.showwarning('Select', 'Select a row first')
            return
        try:
            imp_id = int(rec.get('id') or rec.get('ID') or rec.get('Id') or 0)
        except Exception:
            messagebox.showerror('Error', 'Could not determine import id for selected row')
            return
        # Fetch imports with lines and find matching id
        try:
            imports = db.get_imports_with_lines(limit=1000)
            target = None
            for imp in imports:
                if int(imp.get('id')) == imp_id:
                    target = imp
                    break
            if not target:
                messagebox.showinfo('No lines', 'No detailed lines found for the selected import')
                return
            # Show modal dialog with lines
            d = tk.Toplevel(window)
            d.title(f'Import {imp_id} — Lines')
            d.geometry('600x300')
            try:
                apply_theme(d)
            except Exception:
                pass
            tree_l = ttk.Treeview(d, columns=('id','category','subcategory','quantity','ordered_price'), show='headings')
            for c in ('id','category','subcategory','quantity','ordered_price'):
                tree_l.heading(c, text=c.title())
                tree_l.column(c, width=120, anchor=tk.CENTER)
            tree_l.pack(expand=True, fill='both', padx=8, pady=8)
            for ln in target.get('lines', []):
                tree_l.insert('', 0, values=(ln.get('id'), ln.get('category'), ln.get('subcategory'), ln.get('quantity'), ln.get('ordered_price')))
            themed_button(d, text='Close', variant='secondary', command=d.destroy).pack(pady=6)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load lines: {e}')

    # Double-click on a row to show lines as well
    def on_row_double_click(event=None):
        show_lines_for_selected()
    tree.bind('<Double-1>', on_row_double_click)
