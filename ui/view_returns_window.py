import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
from pathlib import Path
import os
import json
import sys
import subprocess
from .theme import stripe_treeview, maximize_window, apply_theme

RETURNS_CSV = Path(__file__).resolve().parents[2] / 'data' / 'returns.csv'

DESIRED = ['ReturnDate', 'ProductID', 'SaleDate', 'Category', 'Subcategory', 'UnitPrice', 'SellingPrice', 'Platform', 'RefundAmount', 'Restock', 'Reason', 'ReturnDocPath']


def ensure_returns_csv():
    RETURNS_CSV.parent.mkdir(parents=True, exist_ok=True)
    if not RETURNS_CSV.exists():
        with RETURNS_CSV.open('w', newline='') as f:
            csv.writer(f).writerow(DESIRED)


def read_returns():
    ensure_returns_csv()
    with RETURNS_CSV.open('r', newline='') as f:
        return list(csv.DictReader(f))


def write_returns(rows):
    ensure_returns_csv()
    with RETURNS_CSV.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=DESIRED)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in DESIRED})


def open_view_returns_window(root):
    rows = read_returns()
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

    cols = DESIRED
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
    ttk.Label(win, textvariable=totals_var, anchor='w').pack(fill='x', padx=8, pady=4)

    def row_matches(r, q):
        if not q:
            return True
        ql = q.lower()
        for c in cols:
            v = str(r.get(c, '')).lower()
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

    def populate():
        for r in tree.get_children():
            tree.delete(r)
        count = 0
        total_refund = 0.0
        for i, row in enumerate(read_returns()):
            if row_matches(row, search_var.get().strip()):
                vals = [row.get(c, '') for c in cols]
                try:
                    idx = cols.index('ReturnDocPath')
                    doc_list = parse_docs(row.get('ReturnDocPath', ''))
                    if len(doc_list) == 0:
                        vals[idx] = ''
                    elif len(doc_list) == 1:
                        vals[idx] = doc_list[0]
                    else:
                        vals[idx] = f"{len(doc_list)} docs"
                except Exception:
                    pass
                tree.insert('', tk.END, iid=str(i), values=vals)
                count += 1
                try:
                    total_refund += float(row.get('RefundAmount') or 0)
                except Exception:
                    pass
        totals_var.set(f"Rows: {count}    Total Refund: {total_refund:.2f}")
        try:
            stripe_treeview(tree)
        except Exception:
            pass

    populate()

    def refresh():
        populate()

    def get_selected_index():
        sel = tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def do_delete():
        idx = get_selected_index()
        if idx is None:
            messagebox.showwarning('Select', 'Select a row first')
            return
        if not messagebox.askyesno('Confirm', 'Delete selected return?'):
            return
        rows = read_returns()
        if 0 <= idx < len(rows):
            del rows[idx]
            write_returns(rows)
            refresh()

    def do_edit():
        idx = get_selected_index()
        if idx is None:
            messagebox.showwarning('Select', 'Select a row first')
            return
        rows = read_returns()
        if not (0 <= idx < len(rows)):
            messagebox.showerror('Error', 'Invalid selection index')
            return
        rec = rows[idx]

        dlg = tk.Toplevel(win)
        dlg.title('Edit Return')
        dlg.geometry('480x520')

        entries = {}

        def add_field(label, key, disabled=False):
            ttk.Label(dlg, text=label).pack(pady=4)
            e = ttk.Entry(dlg, width=40)
            e.insert(0, str(rec.get(key, '')))
            if disabled:
                e.configure(state='disabled')
            e.pack(pady=2)
            entries[key] = e

        add_field('Return Date (YYYY-MM-DD):', 'ReturnDate')
        add_field('Product ID:', 'ProductID', disabled=True)
        add_field('Sale Date:', 'SaleDate', disabled=True)
        add_field('Category:', 'Category', disabled=True)
        add_field('Subcategory:', 'Subcategory', disabled=True)
        add_field('Unit Price:', 'UnitPrice', disabled=True)
        add_field('Selling Price:', 'SellingPrice', disabled=True)
        add_field('Platform:', 'Platform', disabled=True)
        add_field('Refund Amount:', 'RefundAmount')
        add_field('Restock (1/0):', 'Restock')
        add_field('Reason:', 'Reason')

        # DocumentPath with Browse button
        ttk.Label(dlg, text='Return Document (path):').pack(pady=4)
        doc_frame = ttk.Frame(dlg)
        doc_entry = ttk.Entry(doc_frame, width=32)
        doc_entry.insert(0, str(rec.get('ReturnDocPath', '')))
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

        ttk.Button(doc_frame, text='Browse...', command=browse_doc).pack(side=tk.LEFT)
        doc_frame.pack(pady=2)

        def save_edit():
            from datetime import datetime as _dt
            d = entries['ReturnDate'].get().strip()
            try:
                _dt.strptime(d, '%Y-%m-%d')
            except Exception:
                messagebox.showerror('Invalid date', 'Use YYYY-MM-DD', parent=dlg)
                return
            # refund amount and restock
            try:
                refund = float(entries['RefundAmount'].get().strip() or 0)
            except Exception:
                messagebox.showerror('Invalid', 'RefundAmount must be a number', parent=dlg)
                return
            restock_val = entries['Restock'].get().strip()
            restock = 1 if restock_val in ('1', 'true', 'True', 'YES', 'yes') else 0

            rows[idx] = {
                'ReturnDate': d,
                'ProductID': rec.get('ProductID',''),
                'SaleDate': rec.get('SaleDate',''),
                'Category': rec.get('Category',''),
                'Subcategory': rec.get('Subcategory',''),
                'UnitPrice': rec.get('UnitPrice',''),
                'SellingPrice': rec.get('SellingPrice',''),
                'Platform': rec.get('Platform',''),
                'RefundAmount': refund,
                'Restock': restock,
                'Reason': entries['Reason'].get().strip(),
                'ReturnDocPath': doc_entry.get().strip(),
            }
            write_returns(rows)
            dlg.destroy()
            refresh()

        ttk.Button(dlg, text='Save', command=save_edit).pack(pady=10)

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
        rows = read_returns()
        if not (0 <= idx < len(rows)):
            messagebox.showerror('Error', 'Invalid selection index', parent=win)
            return
        rec = rows[idx]
        pid = rec.get('ProductID','')
        docs = parse_docs(rec.get('ReturnDocPath',''))

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
            rows2 = read_returns()
            if 0 <= idx < len(rows2):
                rows2[idx]['ReturnDocPath'] = format_docs(docs)
                write_returns(rows2)
            dlg.destroy()
            refresh()

        ttk.Button(btns, text='➕ Add…', command=add_docs).pack(side=tk.LEFT)
        ttk.Button(btns, text='🗑️ Remove', command=remove_selected).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text='📄 Open', command=open_selected).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text='📂 Open All', command=open_all).pack(side=tk.LEFT, padx=6)
        ttk.Button(container, text='Save & Close', command=save_and_close).pack(pady=(8,0))

    btn_frame = ttk.Frame(win)
    ttk.Button(btn_frame, text='Refresh', style='Primary.TButton', command=refresh).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text='Select All', style='Primary.TButton', command=select_all).pack(side=tk.LEFT, padx=6)
    def deselect_all():
        try:
            tree.selection_remove(tree.get_children(''))
        except Exception:
            pass
    ttk.Button(btn_frame, text='Deselect All', style='Primary.TButton', command=deselect_all).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text='Edit', style='Success.TButton', command=do_edit).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text='Delete', style='Danger.TButton', command=do_delete).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_frame, text='📂 Documents', style='Secondary.TButton', command=do_manage_docs).pack(side=tk.LEFT, padx=6)
    btn_frame.pack(fill='x', pady=8)
