import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import db
from .theme import stripe_treeview
import os
import sys
import subprocess


def open_view_expenses_window(root):
    window = tk.Toplevel(root)
    window.title('💳 View Expenses')
    window.geometry('1000x450')
    window.minsize(800, 350)
    
    # Apply theme
    from .theme import apply_theme
    apply_theme(window)

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

    cols = list(rows[0].keys())
    tree = ttk.Treeview(window, columns=cols, show='headings')
    for c in cols:
        tree.heading(c, text=c)
        tree.column(c, width=120, anchor=tk.CENTER)
    tree.pack(expand=True, fill='both')

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

    # Totals label
    totals_var = tk.StringVar(value='')
    totals_lbl = ttk.Label(window, textvariable=totals_var, anchor='w')
    totals_lbl.pack(fill='x', padx=8, pady=4)

    def populate():
        for r in tree.get_children():
            tree.delete(r)
        count = 0
        total_amount = 0.0
        for row in db.get_expenses():
            if row_matches(row, search_var.get().strip()):
                tree.insert('', tk.END, values=[row.get(c, '') for c in cols])
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

    populate()

    def refresh():
        populate()

    def on_search_change(event=None):
        populate()

    def get_selected():
        s = tree.selection()
        if not s:
            return None
        vals = tree.item(s[0])['values']
        return {c: vals[i] for i, c in enumerate(cols)}

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
        f.geometry('420x420')

        ttk.Label(f, text='Date (YYYY-MM-DD):').pack(pady=4)
        date_e = ttk.Entry(f)
        date_e.insert(0, rec.get('date', ''))
        date_e.pack(pady=4)

        ttk.Label(f, text='Amount:').pack(pady=4)
        amount_e = ttk.Entry(f)
        amount_e.insert(0, rec.get('amount', ''))
        amount_e.pack(pady=4)

        # Document path with Browse
        ttk.Label(f, text='Document (optional):').pack(pady=4)
        doc_frame = ttk.Frame(f)
        doc_e = ttk.Entry(doc_frame, width=34)
        doc_e.insert(0, rec.get('document_path', ''))
        doc_e.pack(side=tk.LEFT, padx=(0, 6))
        def browse_doc():
            path = filedialog.askopenfilename(parent=f, title='Select document')
            if path:
                try:
                    from pathlib import Path as _P
                    doc_e.delete(0, tk.END)
                    doc_e.insert(0, str(_P(path).resolve()))
                except Exception:
                    doc_e.delete(0, tk.END)
                    doc_e.insert(0, path)
        ttk.Button(doc_frame, text='Browse...', command=browse_doc).pack(side=tk.LEFT)
        doc_frame.pack(pady=2)

        is_imp_var = tk.IntVar(value=int(rec.get('is_import_related') or 0))
        is_imp_cb = ttk.Checkbutton(f, text='Import-related', variable=is_imp_var)
        is_imp_cb.pack(pady=4)

        ttk.Label(f, text='Link to Import (optional):').pack(pady=4)
        import_combo = ttk.Combobox(f, values=[], state='disabled')
        import_combo.pack(pady=4)

        ttk.Label(f, text='Category (optional):').pack(pady=4)
        cat_e = ttk.Entry(f)
        cat_e.insert(0, rec.get('category', ''))
        cat_e.pack(pady=4)

        # suggestion dropdown for category (gather from imports and past expenses)
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
                    lb = tk.Listbox(win, height=min(8, len(matches)), exportselection=False)
                    lb.pack()
                    lb.bind("<<ListboxSelect>>", pick_cat)
                    win.listbox = lb
                    cat_dropdown["win"] = win
                else:
                    win = cat_dropdown["win"]
                    lb = win.listbox
                lb.delete(0, tk.END)
                for m in matches[:8]:
                    lb.insert(tk.END, m)
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
            lb = evt.widget
            sel = lb.curselection()
            if sel:
                cat_e.delete(0, tk.END)
                cat_e.insert(0, lb.get(sel[0]))
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

        ttk.Label(f, text='Notes (optional):').pack(pady=4)
        notes_e = ttk.Entry(f)
        notes_e.insert(0, rec.get('notes', ''))
        notes_e.pack(pady=4)

        # populate imports
        rows_imp = db.get_imports(limit=500)
        choices = [f"{r.get('id')} - {r.get('date')} {r.get('category')}/{r.get('subcategory')} qty:{r.get('quantity')}" for r in rows_imp]
        import_combo['values'] = choices
        if rec.get('import_id'):
            # try to select matching
            match = [c for c in choices if c.startswith(str(rec.get('import_id')) + ' -')]
            if match:
                import_combo.set(match[0])
                import_combo.config(state='readonly')
                is_imp_var.set(1)

        def on_imp_toggle(*a):
            if is_imp_var.get():
                import_combo.config(state='readonly')
            else:
                import_combo.set('')
                import_combo.config(state='disabled')

        is_imp_var.trace_add('write', on_imp_toggle)

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
            imp_sel = import_combo.get().strip()
            imp_id = None
            if imp_sel:
                try:
                    imp_id = int(imp_sel.split(' - ', 1)[0])
                except Exception:
                    imp_id = None
            try:
                db.edit_expense(int(rec.get('id')),
                                d, a, bool(is_imp_var.get()), imp_id, cat_e.get().strip(), notes_e.get().strip(), document_path=doc_e.get().strip())
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

    def do_attach():
        rec = get_selected()
        if not rec:
            messagebox.showwarning('Select', 'Select a row first')
            return
        path = filedialog.askopenfilename(parent=window, title='Attach document')
        if not path:
            return
        from pathlib import Path as _P
        try:
            attach = str(_P(path).resolve())
        except Exception:
            attach = path
        try:
            # Keep other fields the same
            d = rec.get('date', '')
            a = float(rec.get('amount') or 0)
            is_imp = bool(int(rec.get('is_import_related') or 0))
            imp_id = rec.get('import_id')
            if imp_id in ("", None):
                imp_id = None
            else:
                try:
                    imp_id = int(imp_id)
                except Exception:
                    imp_id = None
            cat = rec.get('category', '')
            notes = rec.get('notes', '')
            db.edit_expense(int(rec.get('id')), d, a, is_imp, imp_id, cat, notes, document_path=attach)
            refresh()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to attach: {e}', parent=window)

    def do_open_doc():
        rec = get_selected()
        if not rec:
            messagebox.showwarning('Select', 'Select a row first')
            return
        _open_default(rec.get('document_path', ''))

    btn_frame = ttk.Frame(window)
    search_entry.bind('<KeyRelease>', on_search_change)
    
    # Primary actions (left)
    primary_frame = ttk.Frame(btn_frame)
    primary_frame.pack(side='left', fill='x', expand=True)
    ttk.Button(primary_frame, text='🔄 Refresh', command=refresh).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(primary_frame, text='✏️ Edit', style='Success.TButton', command=do_edit).pack(side=tk.LEFT, padx=4)
    
    # Secondary actions (right)
    secondary_frame = ttk.Frame(btn_frame)
    secondary_frame.pack(side='right')
    ttk.Button(secondary_frame, text='📎 Attach Document', command=do_attach).pack(side=tk.LEFT, padx=4)
    ttk.Button(secondary_frame, text='📄 Open Document', command=do_open_doc).pack(side=tk.LEFT, padx=4)
    ttk.Button(secondary_frame, text='🗑️ Delete', style='Danger.TButton', command=do_delete).pack(side=tk.LEFT, padx=(8, 0))
    
    btn_frame.pack(fill='x', pady=8)
