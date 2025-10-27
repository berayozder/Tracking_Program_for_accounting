import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import os
import json
import sys
import subprocess
from .theme import stripe_treeview, maximize_window, apply_theme, themed_button

import db as db
from db.returns_dao import list_returns as db_list_returns, update_return as db_update_return, delete_return as db_delete_return, undelete_return as db_undelete_return
from db.returns_dao import process_restock_change as db_process_restock_change

# Columns from DB (read-only ones are disabled in edit).
DB_COLS = ['id', 'return_date', 'product_id', 'sale_date', 'category', 'subcategory', 'unit_price', 'selling_price', 'platform', 'refund_amount', 'refund_currency', 'refund_amount_base', 'restock', 'reason', 'doc_paths']


def open_view_returns_window(root):
    import csv
    def do_export_csv():
        file_path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
            title='Export Returns to CSV'
        )
        if not file_path:
            return
        columns = [tree.heading(col)['text'] for col in tree['columns']]
        data = []
        for iid in tree.get_children():
            values = tree.item(iid)['values']
            data.append(values)
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(data)
            messagebox.showinfo('Exported', f'Returns exported to {file_path}')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to export CSV: {e}')
    rows = db_list_returns()
    if not rows:
        messagebox.showinfo('No data', 'No returns found.')
        return

    win = tk.Toplevel(root)
    win.title('↩️ View Returns')
    win.geometry('980x460')
    try:
        win.minsize(860, 380)
    except Exception:
        pass
    try:
        apply_theme(win)
    except Exception:
        pass
    try:
        maximize_window(win)
    except Exception:
        pass

    # Search box
    filter_frame = ttk.Frame(win)
    ttk.Label(filter_frame, text='Search:').pack(side=tk.LEFT, padx=(8, 6))
    search_var = tk.StringVar()
    search_entry = ttk.Entry(filter_frame, textvariable=search_var, width=30)
    search_entry.pack(side=tk.LEFT)
    filter_frame.pack(fill='x', pady=6)

    cols = ['id', 'return_date', 'product_id', 'sale_date', 'category', 'subcategory', 'unit_price', 'selling_price', 'platform', 'refund_amount', 'refund_currency', 'refund_amount_base', 'restock', 'reason', 'doc_paths']
    tree = ttk.Treeview(win, columns=cols, show='headings')
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=140, anchor=tk.CENTER)
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

    totals_var = tk.StringVar(value='')
    show_deleted_var = tk.BooleanVar(value=False)
    ttk.Label(win, textvariable=totals_var, anchor='w').pack(fill='x', padx=8, pady=4)

    def _fetch_returns(include_deleted=False):
        if include_deleted:
            try:
                conn = db.get_conn()
                cur = conn.cursor()
                cur.execute('SELECT id, return_date, product_id, sale_date, category, subcategory, unit_price, selling_price, platform, refund_amount, refund_currency, refund_amount_base, restock, reason, doc_paths, restock_processed, deleted FROM returns ORDER BY id DESC')
                rows = [dict(r) for r in cur.fetchall()]
                conn.close()
                return rows
            except Exception:
                return []
        return db_list_returns()

    def row_matches(r, q):
        if not q:
            return True
        ql = q.lower()
        for c in cols:
            v = str(r.get(c, '') if isinstance(r, dict) else r.get(c, '')).lower()
            if ql in v:
                return True
        return False

    def parse_docs(val):
        if val is None:
            return []
        v = str(val).strip()
        if not v:
            return []
        try:
            arr = json.loads(v)
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
        return [v]

    def format_docs(paths):
        cleaned = []
        seen = set()
        for p in paths or []:
            s = str(p).strip()
            if s and s not in seen:
                seen.add(s)
                cleaned.append(s)
        return json.dumps(cleaned, ensure_ascii=False)

    # cache of latest rows to support edit/delete
    last_rows = []

    def populate():
        for r in tree.get_children():
            tree.delete(r)
        count = 0
        total_refund = 0.0
        last_rows.clear()
        show_deleted = show_deleted_var.get()
        for row in _fetch_returns(show_deleted):
            # Convert sqlite Row to dict if needed
            rowd = dict(row) if not isinstance(row, dict) else row
            # Hide deleted returns unless show_deleted is True
            if not show_deleted and int(rowd.get('deleted', 0)) == 1:
                continue
            if row_matches(rowd, search_var.get().strip()):
                vals = [rowd.get(c, '') for c in cols]
                try:
                    di = cols.index('doc_paths')
                    doc_list = parse_docs(rowd.get('doc_paths', ''))
                    if len(doc_list) == 0:
                        vals[di] = ''
                    elif len(doc_list) == 1:
                        vals[di] = doc_list[0]
                    else:
                        vals[di] = f"{len(doc_list)} docs"
                except Exception:
                    pass
                iid = str(rowd.get('id'))
                # Determine tag: if restock_processed is set (1) -> restocked, else if restock requested but not processed -> nonrestocked
                tag = None
                try:
                    rp = int(rowd.get('restock_processed') or 0)
                except Exception:
                    rp = 0
                try:
                    rflag = int(rowd.get('restock') or 0)
                except Exception:
                    rflag = 0
                if rp == 1:
                    tag = 'returned_restocked'
                elif rflag == 1:
                    tag = 'returned_nonrestocked'
                # Insert with tag if determined
                if tag:
                    tree.insert('', 0, iid=iid, values=vals, tags=(tag,))
                else:
                    tree.insert('', 0, iid=iid, values=vals)
                last_rows.append(rowd)
                count += 1
                try:
                    total_refund += float(rowd.get('refund_amount_base') or 0)
                except Exception:
                    pass
        totals_var.set(f"Rows: {count}    Total Refund (base): {total_refund:.2f}")
        try:
            stripe_treeview(tree)
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
        if not messagebox.askyesno('Confirm', f'Undelete {count} selected returns?'):
            return
        any_done = False
        for iid in sel:
            try:
                rid = int(iid)
            except Exception:
                continue
            try:
                if db_undelete_return(rid):
                    any_done = True
            except Exception:
                continue
        if any_done:
            refresh()

    def do_undo_return():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning('Select', 'Select at least one row first')
            return
        count = len(sel)
        if not messagebox.askyesno('Confirm', f'Undo {count} selected returns?'):
            return
        any_done = False
        from db.imports_dao import undo_return_batch_allocation
        for iid in sel:
            try:
                rid = int(iid)
            except Exception:
                continue
            try:
                # Undo batch allocation
                if undo_return_batch_allocation(rid):
                    # Mark the return row as deleted
                    try:
                        db_delete_return(rid)
                    except Exception:
                        pass
                    any_done = True
            except Exception:
                continue
        if any_done:
            refresh()
            # Emit a virtual event so other windows (e.g., sales) can refresh
            try:
                win.event_generate('<<ReturnUndone>>')
            except Exception:
                pass

    def get_selected_index():
        sel = tree.selection()
        if not sel:
            return None
        try:
            return sel[0]
        except Exception:
            return None

    def do_delete():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning('Select', 'Select at least one row first')
            return
        count = len(sel)
        if count == 1:
            prompt = 'Delete the selected return?'
        else:
            prompt = f'Delete {count} selected returns?'
        if not messagebox.askyesno('Confirm', prompt):
            return

        any_deleted = False
        for iid in sel:
            try:
                rid = int(iid)
            except Exception:
                continue
            try:
                if db_delete_return(rid):
                    any_deleted = True
            except Exception:
                # continue deleting others even if one fails
                continue
        if any_deleted:
            refresh()

    def do_edit():
        iid = get_selected_index()
        if iid is None:
            messagebox.showwarning('Select', 'Select a row first')
            return
        try:
            rid = int(iid)
        except Exception:
            messagebox.showerror('Error', 'Invalid selection', parent=win)
            return
        # locate record in last_rows
        rec = None
        for r in last_rows:
            if int(r.get('id')) == rid:
                rec = r
                break
        if rec is None:
            messagebox.showerror('Error', 'Selected row not found', parent=win)
            return

        dlg = tk.Toplevel(win)
        dlg.title('Edit Return')
        dlg.geometry('480x520')

        # --- Scrollable Frame Setup ---
        canvas = tk.Canvas(dlg, borderwidth=0, background="#f8f8f8", height=480)
        vscroll = ttk.Scrollbar(dlg, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        scroll_frame.bind("<Configure>", _on_frame_configure)
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        entries = {}

        def add_field(label, key, disabled=False):
            ttk.Label(scroll_frame, text=label).pack(pady=4)
            e = ttk.Entry(scroll_frame, width=40)
            e.insert(0, str(rec.get(key, '')))
            if disabled:
                e.configure(state='disabled')
            e.pack(pady=2)
            entries[key] = e

        add_field('Return Date (YYYY-MM-DD):', 'return_date')
        add_field('Product ID:', 'product_id', disabled=True)
        add_field('Sale Date:', 'sale_date', disabled=True)
        add_field('Category:', 'category', disabled=True)
        add_field('Subcategory:', 'subcategory', disabled=True)
        add_field('Unit Price:', 'unit_price', disabled=True)
        add_field('Selling Price:', 'selling_price', disabled=True)
        add_field('Platform:', 'platform', disabled=True)
        add_field('Refund Amount:', 'refund_amount')
        add_field('Refund Currency (e.g., TRY, USD):', 'refund_currency')
        add_field('Restock (1/0):', 'restock')
        # Reason with suggestions
        ttk.Label(scroll_frame, text='Reason:').pack(pady=4)
        # Suggestions from DB plus defaults
        try:
            import db as db
            reasons = db.get_distinct_return_reasons() or []
        except Exception:
            reasons = []
        defaults = ['Defective', 'Damaged in shipping', 'Not as described', 'Changed mind',
                    'Wrong item sent', 'Missing parts', 'Warranty return', 'Customer complaint']
        seen = set()
        suggestions = []
        for s in reasons + defaults:
            v = str(s).strip()
            if v and v not in seen:
                seen.add(v)
                suggestions.append(v)
        reason_var = tk.StringVar(value=str(rec.get('reason','') or ''))

        # Type-ahead filtering: update Combobox values as user types
        def filter_suggestions(event=None):
            typed = reason_var.get().strip().lower()
            filtered = [s for s in suggestions if typed in s.lower()] if typed else suggestions
            reason_combo['values'] = filtered

        reason_combo = ttk.Combobox(scroll_frame, textvariable=reason_var, values=suggestions, width=38)
        reason_combo.pack(pady=2, fill='x')
        reason_combo.configure(state='normal')
        reason_combo.bind('<KeyRelease>', filter_suggestions)

        # '+ Add to defaults' button
        def add_reason_to_defaults():
            val = reason_var.get().strip()
            if val and val not in suggestions:
                try:
                    import db as db
                    db.add_return_reason(val)
                    suggestions.append(val)
                    reason_combo['values'] = suggestions
                    tk.messagebox.showinfo('Added', f'"{val}" added to Reason presets.')
                except Exception:
                    tk.messagebox.showerror('Error', 'Could not add reason to presets.')

        add_btn = ttk.Button(scroll_frame, text='+ Add to defaults', command=add_reason_to_defaults)
        add_btn.pack(pady=2)

        # DocumentPath with Browse button
        ttk.Label(scroll_frame, text='Return Document (path):').pack(pady=4)
        doc_frame = ttk.Frame(scroll_frame)
        doc_entry = ttk.Entry(doc_frame, width=32)
        doc_entry.insert(0, str(rec.get('doc_paths', '')))
        doc_entry.pack(side=tk.LEFT, padx=(0, 6))

        def browse_doc():
            path = filedialog.askopenfilename(parent=dlg, title='Select document')
            if path:
                try:
                    from pathlib import Path as _P
                    doc_entry.delete(0, tk.END)
                    doc_entry.insert(0, str(_P(path).resolve()))
                except Exception:
                    doc_entry.delete(0, tk.END)
                    doc_entry.insert(0, path)

        from .theme import themed_button
        themed_button(doc_frame, text='Browse…', variant='secondary', command=browse_doc).pack(side=tk.LEFT)
        doc_frame.pack(pady=2)

        def save_edit():
            from datetime import datetime as _dt
            d = entries['return_date'].get().strip()
            try:
                _dt.strptime(d, '%Y-%m-%d')
            except Exception:
                messagebox.showerror('Invalid date', 'Use YYYY-MM-DD', parent=dlg)
                return
            # refund amount and restock
            try:
                refund = float(entries['refund_amount'].get().strip() or 0)
            except Exception:
                messagebox.showerror('Invalid', 'RefundAmount must be a number', parent=dlg)
                return
            restock_val = entries['restock'].get().strip()
            restock = 1 if restock_val in ('1', 'true', 'True', 'YES', 'yes') else 0
            prev_restock = int(rec.get('restock', 0))
            update_data = dict(rec)
            update_data.update({
                'return_date': d,
                'refund_amount': refund,
                'refund_currency': entries['refund_currency'].get().strip().upper() or '',
                'restock': restock,
                'reason': reason_var.get().strip(),
                'doc_paths': doc_entry.get().strip(),
            })
            update_ok = True
            if restock != prev_restock:
                update_ok = db_process_restock_change(rid, restock)
            else:
                update_ok = db_update_return(rid, update_data)
            if not update_ok:
                messagebox.showerror('Error', 'Failed to update return', parent=dlg)
                return
            dlg.destroy()
            refresh()

        themed_button(scroll_frame, text='Save', variant='primary', command=save_edit).pack(pady=10)

    def on_search_change(event=None):
        populate()

    search_entry.bind('<KeyRelease>', on_search_change)

    def _open_default(path):
        p = Path(path).expanduser()
        if not str(p):
            messagebox.showwarning('No document', 'No document path set for this row.', parent=win)
            return
        if not p.exists():
            messagebox.showerror('Not found', f'File not found:\n{p}', parent=win)
            return
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(['open', str(p)])
            elif sys.platform.startswith('win'):
                os.startfile(str(p))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(['xdg-open', str(p)])
        except Exception as e:
            messagebox.showerror('Error', f'Failed to open document: {e}', parent=win)

    def get_selected_index():
        sel = tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def do_manage_docs():
        idx = get_selected_index()
        if idx is None:
            messagebox.showwarning('Select', 'Select a row first')
            return
        iid = get_selected_index()
        if iid is None:
            messagebox.showwarning('Select', 'Select a row first')
            return
        try:
            rid = int(iid)
        except Exception:
            messagebox.showerror('Error', 'Invalid selection', parent=win)
            return
        rec = None
        for r in last_rows:
            if int(r.get('id')) == rid:
                rec = r
                break
        if rec is None:
            messagebox.showerror('Error', 'Selected row not found', parent=win)
            return
        pid = rec.get('ProductID','')
        pid = rec.get('product_id','')
        docs = parse_docs(rec.get('doc_paths',''))

        dlg = tk.Toplevel(win)
        dlg.title(f'Documents (Return): {pid}')
        dlg.geometry('560x360')
        dlg.transient(win)
        dlg.grab_set()

        container = ttk.Frame(dlg, padding=12)
        container.pack(fill='both', expand=True)

        list_frame = ttk.Frame(container)
        list_frame.pack(fill='both', expand=True)
        lb = tk.Listbox(list_frame, selectmode=tk.EXTENDED, height=10, exportselection=False)
        sb = ttk.Scrollbar(list_frame, orient='vertical', command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side=tk.LEFT, fill='both', expand=True)
        sb.pack(side=tk.LEFT, fill='y')

        def refresh_lb():
            lb.delete(0, tk.END)
            for p in docs:
                lb.insert(tk.END, p)
        refresh_lb()

        btns = ttk.Frame(container)
        btns.pack(fill='x', pady=8)

        def add_docs():
            paths = filedialog.askopenfilenames(parent=dlg, title='Select document(s)')
            if not paths:
                return
            from pathlib import Path as _P
            for p in paths:
                try:
                    rp = str(_P(p).resolve())
                except Exception:
                    rp = str(p)
                if rp and rp not in docs:
                    docs.append(rp)
            refresh_lb()

        def remove_selected():
            sel = list(lb.curselection())
            if not sel:
                return
            for i in reversed(sel):
                try:
                    del docs[i]
                except Exception:
                    pass
            refresh_lb()

        def open_selected():
            sel = lb.curselection()
            if not sel:
                messagebox.showinfo('Select', 'Select a document to open', parent=dlg)
                return
            for i in sel:
                try:
                    _open_default(docs[i])
                except Exception as e:
                    messagebox.showerror('Error', f'Failed to open: {e}', parent=dlg)

        def open_all():
            for p in docs:
                try:
                    _open_default(p)
                except Exception:
                    pass

        def save_and_close():
            if not db_update_return(rid, {'doc_paths': format_docs(docs)}):
                messagebox.showerror('Error', 'Failed to update documents', parent=dlg)
                return
            dlg.destroy()
            refresh()

        themed_button(btns, text='➕ Add…', variant='secondary', command=add_docs).pack(side=tk.LEFT)
        themed_button(btns, text='🗑️ Remove', variant='secondary', command=remove_selected).pack(side=tk.LEFT, padx=6)
        themed_button(btns, text='📄 Open', variant='secondary', command=open_selected).pack(side=tk.LEFT, padx=6)
        themed_button(btns, text='📂 Open All', variant='secondary', command=open_all).pack(side=tk.LEFT, padx=6)
        themed_button(container, text='Save & Close', variant='primary', command=save_and_close).pack(pady=(8,0))

    btn_frame = ttk.Frame(win)
    btn_frame.pack(fill='x', pady=8)
    themed_button(btn_frame, text='Export CSV', command=do_export_csv).pack(side=tk.LEFT, padx=4)
    themed_button(btn_frame, text='Edit', command=do_edit).pack(side=tk.LEFT, padx=4)
    themed_button(btn_frame, text='Delete', command=do_delete).pack(side=tk.LEFT, padx=4)
    themed_button(btn_frame, text='Undelete', command=do_undelete).pack(side=tk.LEFT, padx=4)
    themed_button(btn_frame, text='Undo Return', command=do_undo_return, variant='danger').pack(side=tk.LEFT, padx=4)
    themed_button(btn_frame, text='Manage Docs', command=do_manage_docs).pack(side=tk.LEFT, padx=4)
