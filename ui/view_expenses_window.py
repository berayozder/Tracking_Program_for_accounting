import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import db.db as db
from .theme import stripe_treeview, maximize_window, apply_theme
import os
import json
import sys
import subprocess


def open_view_expenses_window(root):
    window = tk.Toplevel(root)
    window.title('💳 View Expenses')
    window.geometry('1000x450')
    window.minsize(800, 350)
    
    # Apply theme
    try:
        apply_theme(window)
    except Exception:
        pass
    try:
        maximize_window(window)
    except Exception:
        pass

    rows = db.get_expenses()
    if not rows:
        messagebox.showinfo('No data', 'No expenses found.')
        window.destroy()
        return

    # Search box
    search_frame = tk.Frame(window)
    tk.Label(search_frame, text='Search:').pack(side=tk.LEFT, padx=(8, 6))
    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side=tk.LEFT)
    search_frame.pack(fill='x', pady=6)

    # Friendly, readable display order (hide internal fields like id/import_id)
    # We'll keep a separate map of Treeview item -> full record for edit/delete.
    display_cols = ['date', 'category', 'subcategory', 'amount', 'currency', 'notes', 'Document']
    col_headers = {
        'date': 'Date',
        'category': 'Category',
        'subcategory': 'Subcategory',
        'amount': 'Amount',
        'currency': 'Currency',
        'notes': 'Notes',
        'Document': 'Document',
    }
    cols = list(display_cols)
    tree = ttk.Treeview(window, columns=cols, show='headings')
    # Size columns sensibly
    col_widths = {
        'date': 110,
        'category': 160,
        'subcategory': 160,
        'amount': 100,
        'currency': 80,
        'notes': 240,
        'Document': 200,
    }
    for c in cols:
        tree.heading(c, text=col_headers.get(c, c))
        tree.column(c, width=col_widths.get(c, 120), anchor=tk.CENTER, stretch=True)
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
        ql = (q or '').lower()
        # Build a composite searchable string across key fields
        try:
            doc_list = parse_docs(r.get('document_path', ''))
            if len(doc_list) == 0:
                doc_disp = ''
            elif len(doc_list) == 1:
                doc_disp = doc_list[0]
            else:
                doc_disp = f"{len(doc_list)} docs"
        except Exception:
            doc_disp = ''
        parts = [
            str(r.get('id', '')),
            str(r.get('date', '')),
            str(r.get('category', '')),
            str(r.get('subcategory', '')),
            str(r.get('amount', '')),
            str(r.get('currency', '')),
            str(r.get('notes', '')),
            str(r.get('import_id', '')),
            doc_disp,
            str(r.get('document_path', '')),
        ]
        blob = ' | '.join([p for p in parts if p is not None]).lower()
        return ql in blob

    # Totals + Selected badge
    totals_row = ttk.Frame(window)
    totals_row.pack(fill='x', padx=8, pady=4)
    totals_var = tk.StringVar(value='')
    ttk.Label(totals_row, textvariable=totals_var, anchor='w').pack(side='left')
    selected_var = tk.StringVar(value='Selected: 0')
    ttk.Label(totals_row, textvariable=selected_var, anchor='e').pack(side='right')

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

    records_by_iid = {}

    def populate():
        for r in tree.get_children():
            tree.delete(r)
        records_by_iid.clear()
        count = 0
        total_amount = 0.0
        for row in db.get_expenses():
            if row_matches(row, search_var.get().strip()):
                # Build display values in the friendly order
                try:
                    doc_list = parse_docs(row.get('document_path', ''))
                    if len(doc_list) == 0:
                        doc_disp = ''
                    elif len(doc_list) == 1:
                        doc_disp = doc_list[0]
                    else:
                        doc_disp = f"{len(doc_list)} docs"
                except Exception:
                    doc_disp = ''
                row_vals = {
                    'date': row.get('date') or '',
                    'category': row.get('category') or '',
                    'subcategory': row.get('subcategory') or '',  # may be absent in schema; safe fallback
                    'amount': row.get('amount') if row.get('amount') is not None else '',
                    'currency': row.get('currency') or '',
                    'notes': row.get('notes') or '',
                    'Document': doc_disp,
                }
                vals = [row_vals.get(c, '') for c in cols]
                iid = tree.insert('', tk.END, values=vals)
                records_by_iid[iid] = row
                count += 1
                try:
                    total_amount += float(row.get('amount') or 0)
                except Exception:
                    pass
        totals_var.set(f"Rows: {count}    Total Amount: {total_amount:.2f}")
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

    def get_selected():
        s = tree.selection()
        if not s:
            return None
        iid = s[0]
        return records_by_iid.get(iid)

    def do_delete():
        rec = get_selected()
        if not rec:
            messagebox.showwarning('Select', 'Select a row first')
            return
        if messagebox.askyesno('Confirm', 'Delete selected expense?'):
            try:
                db.delete_expense(int(rec.get('id')))
                refresh()
            except Exception as e:
                messagebox.showerror('Error', f'Failed to delete: {e}')

    def do_edit():
        rec = get_selected()
        if not rec:
            messagebox.showwarning('Select', 'Select a row first')
            return
        f = tk.Toplevel(window)
        f.title('Edit Expense')
        f.geometry('480x540')

        ttk.Label(f, text='Date (YYYY-MM-DD):').pack(pady=4)
        date_e = ttk.Entry(f)
        date_e.insert(0, rec.get('date', ''))
        date_e.pack(pady=4)

        amt_row = ttk.Frame(f)
        amt_row.pack(pady=4)
        ttk.Label(amt_row, text='Amount:').pack(side=tk.LEFT)
        amount_e = ttk.Entry(amt_row, width=14)
        amount_e.insert(0, rec.get('amount', ''))
        amount_e.pack(side=tk.LEFT, padx=(6, 8))
        ttk.Label(amt_row, text='Currency:').pack(side=tk.LEFT)
        exp_ccy_var = tk.StringVar(value=(rec.get('currency') or db.get_default_expense_currency() or db.get_base_currency()))
        exp_ccy = ttk.Combobox(amt_row, textvariable=exp_ccy_var, state='readonly', width=8, values=['USD','TRY','EUR','GBP'])
        exp_ccy.pack(side=tk.LEFT)

        # Documents manager inline
        ttk.Label(f, text='Documents:').pack(pady=4)
        doc_list = parse_docs(rec.get('document_path',''))
        lf = ttk.Frame(f)
        lf.pack(fill='both', expand=False)
        lb = tk.Listbox(lf, height=5, selectmode=tk.EXTENDED, exportselection=False)
        sb = ttk.Scrollbar(lf, orient='vertical', command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side=tk.LEFT, fill='both', expand=True)
        sb.pack(side=tk.LEFT, fill='y')

        def refresh_lb():
            lb.delete(0, tk.END)
            for p in doc_list:
                lb.insert(tk.END, p)
        refresh_lb()

        btns = ttk.Frame(f)
        btns.pack(fill='x', pady=4)
        def add_docs():
            paths = filedialog.askopenfilenames(parent=f, title='Select document(s)')
            if not paths:
                return
            from pathlib import Path as _P
            for p in paths:
                try:
                    rp = str(_P(p).resolve())
                except Exception:
                    rp = str(p)
                if rp and rp not in doc_list:
                    doc_list.append(rp)
            refresh_lb()
        def remove_selected():
            sel = list(lb.curselection())
            for i in reversed(sel):
                try:
                    del doc_list[i]
                except Exception:
                    pass
            refresh_lb()
        def open_selected():
            sel = lb.curselection()
            if not sel:
                return
            for i in sel:
                _open_default(doc_list[i])
        ttk.Button(btns, text='➕ Add…', command=add_docs).pack(side=tk.LEFT)
        ttk.Button(btns, text='🗑️ Remove', command=remove_selected).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text='📄 Open', command=open_selected).pack(side=tk.LEFT, padx=6)

        is_imp_var = tk.IntVar(value=int(rec.get('is_import_related') or 0))
        is_imp_cb = ttk.Checkbutton(f, text='Import-related', variable=is_imp_var)
        is_imp_cb.pack(pady=4)

        # Link to Import(s): Section (hidden unless Import-related)
        import_section = ttk.LabelFrame(f, text='Link to Import(s) (optional):', padding=8, style='TLabelframe')
        import_section.pack(fill='both', expand=False, padx=2, pady=(4,0))
        imports_frame = ttk.Frame(import_section)
        imports_frame.pack(fill='both', expand=False)
        # Filter row for imports
        imp_filter_row = ttk.Frame(import_section)
        imp_filter_row.pack(fill='x')
        ttk.Label(imp_filter_row, text='Filter imports:').pack(side=tk.LEFT, padx=(0,6))
        imp_filter_var = tk.StringVar()
        imp_filter_entry = ttk.Entry(imp_filter_row, textvariable=imp_filter_var, width=28)
        imp_filter_entry.pack(side=tk.LEFT, fill='x', expand=True)
        imp_canvas = tk.Canvas(imports_frame, height=140, highlightthickness=0)
        imp_sb = ttk.Scrollbar(imports_frame, orient='vertical', command=imp_canvas.yview)
        imp_inner = ttk.Frame(imp_canvas)
        imp_inner.bind("<Configure>", lambda e: imp_canvas.configure(scrollregion=imp_canvas.bbox("all")))
        imp_canvas.create_window((0,0), window=imp_inner, anchor='nw')
        imp_canvas.configure(yscrollcommand=imp_sb.set)
        imp_canvas.pack(side=tk.LEFT, fill='both', expand=True)
        imp_sb.pack(side=tk.LEFT, fill='y')
        imp_vars = []  # list of dicts: {'id': id, 'var': IntVar, 'cb': widget}
        selected_imp_ids = set()
        ctrl_row = ttk.Frame(import_section)
        ctrl_row.pack(fill='x', pady=(4,0))

        # Category and Notes
        ttk.Label(f, text='Category (optional):').pack(pady=4)
        cat_e = ttk.Entry(f)
        cat_e.insert(0, rec.get('category', ''))
        cat_e.pack(pady=4)

        ttk.Label(f, text='Notes (optional):').pack(pady=4)
        notes_e = ttk.Entry(f)
        notes_e.insert(0, rec.get('notes', ''))
        notes_e.pack(pady=4)

        # Category suggestions
        cat_dropdown = {"win": None}
        def load_cat_suggestions():
            cats = set()
            try:
                for r in db.get_expenses(limit=1000):
                    c = (r.get('category') or '').strip()
                    if c:
                        cats.add(c)
            except Exception:
                pass
            return sorted(cats)

        def show_cat_suggestions(event=None):
            q = cat_e.get().strip().lower()
            cats = load_cat_suggestions()
            matches = [c for c in cats if q in c.lower()]
            if matches:
                if not (cat_dropdown["win"] and tk.Toplevel.winfo_exists(cat_dropdown["win"])):
                    win = tk.Toplevel(f)
                    win.wm_overrideredirect(True)
                    win.attributes("-topmost", True)
                    lb2 = tk.Listbox(win, height=min(8, len(matches)), exportselection=False)
                    lb2.pack()
                    lb2.bind("<<ListboxSelect>>", pick_cat)
                    win.listbox = lb2
                    cat_dropdown["win"] = win
                else:
                    win = cat_dropdown["win"]
                    lb2 = win.listbox
                lb2.delete(0, tk.END)
                for m in matches[:8]:
                    lb2.insert(tk.END, m)
                x = f.winfo_rootx() + cat_e.winfo_x()
                y = f.winfo_rooty() + cat_e.winfo_y() + cat_e.winfo_height()
                win.geometry(f"+{x}+{y}")
                win.deiconify()
            else:
                if cat_dropdown["win"]:
                    try:
                        cat_dropdown["win"].destroy()
                    except Exception:
                        pass
                    cat_dropdown["win"] = None

        def pick_cat(evt):
            lbw = evt.widget
            sel = lbw.curselection()
            if sel:
                cat_e.delete(0, tk.END)
                cat_e.insert(0, lbw.get(sel[0]))
            if cat_dropdown["win"]:
                try:
                    cat_dropdown["win"].destroy()
                except Exception:
                    pass
                cat_dropdown["win"] = None
            try:
                notes_e.focus_set()
            except Exception:
                pass

        cat_e.bind('<KeyRelease>', show_cat_suggestions)

        # Populate and pre-select import links
        def refresh_import_checks():
            nonlocal imp_vars, selected_imp_ids
            for child in imp_inner.winfo_children():
                child.destroy()
            # capture current selections
            if imp_vars:
                try:
                    selected_imp_ids = {int(item['id']) for item in imp_vars if int(item['var'].get()) == 1}
                except Exception:
                    selected_imp_ids = selected_imp_ids
            imp_vars = []
            rows_imp = db.get_imports(limit=500)
            q = (imp_filter_var.get() or '').strip().lower()
            pre_ids = []
            try:
                pre_ids = db.get_expense_import_links(int(rec.get('id')))
            except Exception:
                pre_ids = []
            if not pre_ids:
                try:
                    if rec.get('import_id'):
                        pre_ids = [int(rec.get('import_id'))]
                except Exception:
                    pre_ids = []
            for r in rows_imp:
                iid = r.get('id')
                label = f"{iid} - {r.get('date')} {r.get('category')}/{r.get('subcategory')} qty:{r.get('quantity')}"
                if q and q not in label.lower():
                    continue
                var = tk.IntVar(value=1 if iid in pre_ids else 0)
                cb = ttk.Checkbutton(imp_inner, text=label, variable=var)
                cb.pack(anchor='w', fill='x')
                imp_vars.append({'id': iid, 'var': var, 'cb': cb})
            if pre_ids:
                is_imp_var.set(1)
            # re-apply selections from filtering state
            for item in imp_vars:
                try:
                    if int(item['id']) in selected_imp_ids:
                        item['var'].set(1)
                except Exception:
                    pass
            # re-apply enabled/disabled state
            _set_imp_checks(bool(is_imp_var.get()))

        refresh_import_checks()

        # Live filter binding for imports
        def _on_imp_filter_change(event=None):
            refresh_import_checks()
        imp_filter_entry.bind('<KeyRelease>', _on_imp_filter_change)

        # Toggle and selection helpers
        def _set_imp_checks(enabled: bool):
            state = 'normal' if enabled else 'disabled'
            for item in imp_vars:
                try:
                    item['cb'].state([state]) if hasattr(item['cb'], 'state') else item['cb'].configure(state=state)
                except Exception:
                    try:
                        item['cb'].configure(state=state)
                    except Exception:
                        pass
            imp_canvas.configure(state=state)
            imp_sb.configure(state=state)

        def _set_import_section_visible(visible: bool):
            try:
                if visible:
                    import_section.pack(fill='both', expand=False, padx=2, pady=(4,0))
                else:
                    import_section.pack_forget()
            except Exception:
                pass

        def _clear_imp_checks():
            for item in imp_vars:
                try:
                    item['var'].set(0)
                except Exception:
                    pass

        def on_imp_toggle(*a):
            if is_imp_var.get():
                _set_imp_checks(True)
                _set_import_section_visible(True)
            else:
                _clear_imp_checks()
                _set_imp_checks(False)
                _set_import_section_visible(False)

        def _select_all_imp():
            for item in imp_vars:
                try:
                    item['var'].set(1)
                except Exception:
                    pass

        def _clear_all_imp():
            _clear_imp_checks()

        ttk.Button(ctrl_row, text='Select All', command=_select_all_imp).pack(side=tk.LEFT, padx=(0,6))
        ttk.Button(ctrl_row, text='Clear', command=_clear_all_imp).pack(side=tk.LEFT)

        is_imp_var.trace_add('write', on_imp_toggle)
        on_imp_toggle()

        def _get_selected_import_ids():
            ids = []
            for item in imp_vars:
                try:
                    if int(item['var'].get()) == 1:
                        ids.append(int(item['id']))
                except Exception:
                    pass
            uniq = []
            for x in ids:
                if x not in uniq:
                    uniq.append(x)
            return uniq

        def save_edit():
            d = date_e.get().strip()
            try:
                datetime.strptime(d, '%Y-%m-%d')
            except Exception:
                messagebox.showerror('Invalid date', 'Use YYYY-MM-DD')
                return
            try:
                a = float(amount_e.get().strip())
            except Exception:
                messagebox.showerror('Invalid amount', 'Amount must be a number')
                return
            selected_import_ids = _get_selected_import_ids() if is_imp_var.get() else []
            try:
                db.edit_expense(int(rec.get('id')),
                                d, a, bool(is_imp_var.get()), None, cat_e.get().strip(), notes_e.get().strip(), document_path=format_docs(doc_list), import_ids=selected_import_ids, currency=exp_ccy_var.get())
                f.destroy()
                refresh()
            except Exception as e:
                messagebox.showerror('Error', f'Failed to save: {e}')

        ttk.Button(f, text='Save', command=save_edit).pack(pady=8)

    def _open_default(path):
        p = (path or '').strip()
        if not p:
            messagebox.showwarning('No document', 'No document path set for this row.', parent=window)
            return
        from pathlib import Path as _P
        pp = _P(p).expanduser()
        if not pp.exists():
            messagebox.showerror('Not found', f'File not found:\n{pp}', parent=window)
            return
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(['open', str(pp)])
            elif sys.platform.startswith('win'):
                os.startfile(str(pp))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(['xdg-open', str(pp)])
        except Exception as e:
            messagebox.showerror('Error', f'Failed to open document: {e}', parent=window)

    def do_manage_docs():
        rec = get_selected()
        if not rec:
            messagebox.showwarning('Select', 'Select a row first')
            return
        docs = parse_docs(rec.get('document_path',''))
        dlg = tk.Toplevel(window)
        dlg.title('Documents (Expense)')
        dlg.geometry('560x360')
        dlg.transient(window)
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
            for i in reversed(sel):
                try:
                    del docs[i]
                except Exception:
                    pass
            refresh_lb()
        def open_selected():
            sel = lb.curselection()
            if not sel:
                return
            for i in sel:
                _open_default(docs[i])
        def open_all():
            for p in docs:
                _open_default(p)
        def save_and_close():
            # write back using db.edit_expense
            try:
                # re-fetch to avoid stale data
                rows = db.get_expenses()
                # map by id
                exp_id = int(rec.get('id'))
                # update record
                # we need other fields to persist
                d = rec.get('date', '')
                a = float(rec.get('amount') or 0)
                is_imp = bool(int(rec.get('is_import_related') or 0))
                # Preserve multi-import links
                try:
                    link_ids = db.get_expense_import_links(exp_id)
                except Exception:
                    link_ids = []
                cat = rec.get('category', '')
                notes = rec.get('notes', '')
                # Preserve currency from existing record during docs-only save
                curr = rec.get('currency')
                db.edit_expense(exp_id, d, a, is_imp, None, cat, notes, document_path=format_docs(docs), import_ids=link_ids, currency=curr)
                dlg.destroy()
                refresh()
            except Exception as e:
                messagebox.showerror('Error', f'Failed to save: {e}', parent=dlg)
        ttk.Button(btns, text='➕ Add…', command=add_docs).pack(side=tk.LEFT)
        ttk.Button(btns, text='🗑️ Remove', command=remove_selected).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text='📄 Open', command=open_selected).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text='📂 Open All', command=open_all).pack(side=tk.LEFT, padx=6)
        ttk.Button(container, text='Save & Close', command=save_and_close).pack(pady=(8,0))

    def do_open_doc():
        rec = get_selected()
        if not rec:
            messagebox.showwarning('Select', 'Select a row first')
            return
        _open_default(rec.get('document_path', ''))

    btn_frame = ttk.Frame(window)
    search_entry.bind('<KeyRelease>', on_search_change)
    def _update_selected_badge(event=None):
        try:
            selected_var.set(f"Selected: {len(tree.selection())}")
        except Exception:
            pass
    tree.bind('<<TreeviewSelect>>', _update_selected_badge)
    
    # Primary actions (left)
    primary_frame = ttk.Frame(btn_frame)
    primary_frame.pack(side='left', fill='x', expand=True)
    ttk.Button(primary_frame, text='🔄 Refresh', style='Primary.TButton', command=refresh).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(primary_frame, text='Select All', style='Primary.TButton', command=lambda: (select_all(), _update_selected_badge())).pack(side=tk.LEFT, padx=4)
    def deselect_all():
        try:
            tree.selection_remove(tree.get_children(''))
        except Exception:
            pass
    ttk.Button(primary_frame, text='Deselect All', style='Primary.TButton', command=lambda: (deselect_all(), _update_selected_badge())).pack(side=tk.LEFT, padx=4)
    ttk.Button(primary_frame, text='✏️ Edit', style='Success.TButton', command=do_edit).pack(side=tk.LEFT, padx=4)
    
    # Secondary actions (right)
    secondary_frame = ttk.Frame(btn_frame)
    secondary_frame.pack(side='right')
    ttk.Button(secondary_frame, text='📂 Documents', style='Secondary.TButton', command=do_manage_docs).pack(side=tk.LEFT, padx=4)
    ttk.Button(secondary_frame, text='🗑️ Delete', style='Danger.TButton', command=do_delete).pack(side=tk.LEFT, padx=(8, 0))
    
    btn_frame.pack(fill='x', pady=8)
