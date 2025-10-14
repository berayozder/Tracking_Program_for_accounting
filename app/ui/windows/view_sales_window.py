import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
from pathlib import Path
import os
import json
import sys
import subprocess
from .theme import stripe_treeview, maximize_window
import fx_rates

SALES_CSV = Path(__file__).resolve().parents[2] / 'data' / 'sales.csv'
RETURNS_CSV = Path(__file__).resolve().parents[2] / 'data' / 'returns.csv'


def read_sales():
    if not SALES_CSV.exists():
        return []
    with SALES_CSV.open('r', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        # Backward compatibility: map SellingPriceUSD to SellingPriceBase if present
        if rows and 'SellingPriceBase' not in reader.fieldnames and 'SellingPriceUSD' in reader.fieldnames:
            for r in rows:
                if 'SellingPriceBase' not in r or not r.get('SellingPriceBase'):
                    r['SellingPriceBase'] = r.get('SellingPriceUSD', '')
        return rows


DESIRED_COLS = ['Date', 'Category', 'Subcategory', 'Quantity', 'UnitPrice', 'SellingPrice', 'Platform', 'ProductID', 'CustomerID', 'DocumentPath', 'SaleFXToTRY', 'SellingPriceBase']


def write_sales(rows):
    # Write rows with canonical columns, filling missing keys with ''
    SALES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SALES_CSV.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=DESIRED_COLS)
        w.writeheader()
        for r in rows:
            # Map legacy key if needed
            if 'SellingPriceBase' not in r and 'SellingPriceUSD' in r:
                r['SellingPriceBase'] = r.get('SellingPriceUSD', '')
            w.writerow({c: r.get(c, '') for c in DESIRED_COLS})


def ensure_returns_csv():
    RETURNS_CSV.parent.mkdir(parents=True, exist_ok=True)
    desired = ['ReturnDate', 'ProductID', 'SaleDate', 'Category', 'Subcategory', 'UnitPrice', 'SellingPrice', 'Platform', 'RefundAmount', 'Restock', 'Reason', 'ReturnDocPath']
    if not RETURNS_CSV.exists():
        with RETURNS_CSV.open('w', newline='') as f:
            csv.writer(f).writerow(desired)
        return
    # Try to migrate header if missing cols (non-destructive)
    try:
        with RETURNS_CSV.open('r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            with RETURNS_CSV.open('w', newline='') as f:
                csv.writer(f).writerow(desired)
            return
        header = rows[0]
        if header == desired:
            return
        # map rows into desired
        data = rows[1:]
        mapped = []
        for r in data:
            rowd = {header[i]: r[i] if i < len(r) else '' for i in range(len(header))}
            mapped.append({
                'ReturnDate': rowd.get('ReturnDate', ''),
                'ProductID': rowd.get('ProductID', ''),
                'SaleDate': rowd.get('SaleDate', ''),
                'Category': rowd.get('Category', ''),
                'Subcategory': rowd.get('Subcategory', ''),
                'UnitPrice': rowd.get('UnitPrice', ''),
                'SellingPrice': rowd.get('SellingPrice', ''),
                'Platform': rowd.get('Platform', ''),
                'RefundAmount': rowd.get('RefundAmount', ''),
                'Restock': rowd.get('Restock', ''),
                'Reason': rowd.get('Reason', ''),
                'ReturnDocPath': rowd.get('ReturnDocPath', ''),
            })
        with RETURNS_CSV.open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=desired)
            w.writeheader()
            w.writerows(mapped)
    except Exception:
        pass


def read_returns():
    ensure_returns_csv()
    with RETURNS_CSV.open('r', newline='') as f:
        reader = csv.DictReader(f)
        return list(reader)


def open_view_sales_window(root):
    rows = read_sales()
    if not rows:
        messagebox.showinfo('No data', 'No sales found.')
        return

    win = tk.Toplevel(root)
    win.title('💰 View Sales')
    win.geometry('1020x500')
    win.minsize(900, 400)
    try:
        maximize_window(win)
    except Exception:
        pass

    # Main container with padding
    main_container = ttk.Frame(win, padding=12)
    main_container.pack(fill='both', expand=True)

    # Filter section with improved layout
    filter_section = ttk.LabelFrame(main_container, text="🔍 Filters", padding=12, style='TLabelframe')
    filter_section.pack(fill='x', pady=(0, 12))
    
    filter_row1 = ttk.Frame(filter_section)
    filter_row1.pack(fill='x', pady=(0, 8))
    
    ttk.Label(filter_row1, text='Warranty (YY):', font=('', 9)).pack(side=tk.LEFT, padx=(0, 6))
    year_var = tk.StringVar(value='All')
    year_combo = ttk.Combobox(filter_row1, textvariable=year_var, state='readonly', width=12)
    year_combo.pack(side=tk.LEFT, padx=(0, 16))
    
    ttk.Label(filter_row1, text='Status:', font=('', 9)).pack(side=tk.LEFT, padx=(0, 6))
    return_var = tk.StringVar(value='All')
    return_combo = ttk.Combobox(filter_row1, textvariable=return_var, state='readonly', width=14)
    return_combo['values'] = ['All', 'Not Returned', 'Returned']
    return_combo.set('All')
    return_combo.pack(side=tk.LEFT, padx=(0, 16))
    
    ttk.Label(filter_row1, text='Search:', font=('', 9)).pack(side=tk.LEFT, padx=(0, 6))
    search_var = tk.StringVar()
    search_entry = ttk.Entry(filter_row1, textvariable=search_var, width=25, font=('', 9))
    search_entry.pack(side=tk.LEFT)

    ensure_returns_csv()
    cols = DESIRED_COLS
    
    # Table container
    table_frame = ttk.Frame(main_container)
    table_frame.pack(fill='both', expand=True, pady=(0, 12))
    
    tree = ttk.Treeview(table_frame, columns=cols, show='headings', style='Treeview')
    
    # Improved column configuration with better widths and alignment
    col_config = {
        'Date': {'width': 90, 'anchor': 'center'},
        'Category': {'width': 120, 'anchor': 'w'},
        'Subcategory': {'width': 120, 'anchor': 'w'},
        'Quantity': {'width': 70, 'anchor': 'center'},
        'UnitPrice': {'width': 80, 'anchor': 'e'},
        'SellingPrice': {'width': 90, 'anchor': 'e'},
    'SaleFXToTRY': {'width': 120, 'anchor': 'e'},
    'SellingPriceBase': {'width': 140, 'anchor': 'e'},
        'Platform': {'width': 100, 'anchor': 'w'},
        'ProductID': {'width': 120, 'anchor': 'center'},
        'CustomerID': {'width': 100, 'anchor': 'center'},
        'DocumentPath': {'width': 100, 'anchor': 'w'}
    }
    
    for c in cols:
        config = col_config.get(c, {'width': 100, 'anchor': 'center'})
        tree.heading(c, text=c)
        tree.column(c, width=config['width'], anchor=config['anchor'])
    
    # Add scrollbars
    v_scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
    h_scrollbar = ttk.Scrollbar(table_frame, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    
    tree.pack(side='left', fill='both', expand=True)
    v_scrollbar.pack(side='right', fill='y')
    h_scrollbar.pack(side='bottom', fill='x')

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
        # Try date
        if col_name.lower().endswith('date') or col_name.lower() in ('date',):
            from datetime import datetime as _dt
            try:
                return _dt.strptime(v, '%Y-%m-%d')
            except Exception:
                pass
        # Try numeric
        try:
            return float(v)
        except Exception:
            return v.lower()

    def sort_by_column(col):
        # Toggle reverse for this column
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

    # Attach sort commands on headers
    for c in cols:
        tree.heading(c, text=c, command=lambda cc=c: sort_by_column(cc))

    # Totals section with Selected badge
    totals_frame = ttk.Frame(main_container)
    totals_frame.pack(fill='x', pady=(0, 12))
    
    totals_var = tk.StringVar(value='')
    ttk.Label(totals_frame, text='📊', font=('', 12)).pack(side='left', padx=(0, 6))
    totals_lbl = ttk.Label(totals_frame, textvariable=totals_var, font=('', 9, 'bold'), 
                          foreground='#2c3e50')
    totals_lbl.pack(side='left')
    selected_var = tk.StringVar(value='Selected: 0')
    ttk.Label(totals_frame, textvariable=selected_var).pack(side='right')

    # Helper to extract 2-digit year prefixes present in data
    def compute_year_options(all_rows):
        years = set()
        for r in all_rows:
            pid = (r.get('ProductID') or '').strip()
            if not pid:
                continue
            # Backcompat: may contain comma-separated IDs
            parts = [p.strip() for p in pid.split(',') if p.strip()]
            for p in parts:
                if len(p) >= 2 and p[:2].isdigit():
                    years.add(p[:2])
        return ['All'] + sorted(years)

    def row_matches_year(r, yy):
        if yy == 'All':
            return True
        pid = (r.get('ProductID') or '').strip()
        if not pid:
            return False
        parts = [p.strip() for p in pid.split(',') if p.strip()]
        for p in parts:
            if len(p) >= 2 and p[:2] == yy:
                return True
        return False

    def row_matches_search(r, q):
        if not q:
            return True
        ql = q.lower()
        # Search in common fields
        fields = ['Date', 'Category', 'Subcategory', 'Platform', 'ProductID', 'UnitPrice', 'SellingPrice']
        for f in fields:
            v = str(r.get(f, '')).lower()
            if ql in v:
                return True
        return False

    def row_matches_returned(r, status, returned_ids):
        if status == 'All':
            return True
        pid = (r.get('ProductID') or '').strip()
        if status == 'Returned':
            return pid in returned_ids
        if status == 'Not Returned':
            return pid not in returned_ids
        return True

    # Load customer name mapping for display
    def get_customer_name_mapping():
        """Create mapping from customer ID to customer name."""
        try:
            import db
            customers = db.read_customers()
            return {c.get('customer_id', ''): c.get('name', '') for c in customers}
        except Exception:
            return {}
    
    customer_names = get_customer_name_mapping()

    def parse_docs(val):
        """Parse DocumentPath value into a list of paths (supports JSON array or single string)."""
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
        """Serialize list of paths to JSON string with unique non-empty entries."""
        cleaned = []
        seen = set()
        for p in paths or []:
            s = str(p).strip()
            if s and s not in seen:
                seen.add(s)
                cleaned.append(s)
        return json.dumps(cleaned, ensure_ascii=False)

    def populate_tree(all_rows, yy, q=''):
        for r in tree.get_children():
            tree.delete(r)
        # Insert rows using original indices as iids so edits/deletes map correctly
        shown = 0
        total_sell = 0.0
        total_sell_usd = 0.0
        computed_usd_count = 0
        # Build set of returned ProductIDs
        returned_ids = set()
        try:
            for rr in read_returns():
                pid = (rr.get('ProductID') or '').strip()
                if pid:
                    returned_ids.add(pid)
        except Exception:
            returned_ids = set()
        for idx, r in enumerate(all_rows):
            if row_matches_year(r, yy) and row_matches_search(r, q) and row_matches_returned(r, return_var.get(), returned_ids):
                vals = [r.get(c, '') for c in cols]
                
                # Enhance display values
                try:
                    # Mark returned items
                    pid_idx = cols.index('ProductID')
                    pidv = str(vals[pid_idx])
                    if pidv in returned_ids:
                        vals[pid_idx] = pidv + ' (Returned)'
                except Exception:
                    pass
                
                try:
                    # Show customer name instead of ID
                    customer_idx = cols.index('CustomerID')
                    customer_id = str(vals[customer_idx])
                    if customer_id and customer_id in customer_names:
                        vals[customer_idx] = f"{customer_names[customer_id]}"
                    elif customer_id and customer_id.strip():
                        vals[customer_idx] = f"{customer_id} (Unknown)"
                    else:
                        vals[customer_idx] = ""
                except Exception:
                    pass
                
                # Display-friendly DocumentPath: show count if multiple
                try:
                    doc_idx = cols.index('DocumentPath')
                    doc_raw = r.get('DocumentPath', '')
                    doc_list = parse_docs(doc_raw)
                    if len(doc_list) == 0:
                        vals[doc_idx] = ''
                    elif len(doc_list) == 1:
                        vals[doc_idx] = doc_list[0]
                    else:
                        vals[doc_idx] = f"{len(doc_list)} docs"
                except Exception:
                    pass

                tree.insert('', tk.END, iid=str(idx), values=vals)
                shown += 1
                try:
                    total_sell += float(r.get('SellingPrice') or 0)
                except Exception:
                    pass
                # Prefer stored USD; if missing, compute using fx_rates for row date
                usd_val = None
                try:
                    usd_val = float(r.get('SellingPriceUSD')) if r.get('SellingPriceUSD') not in (None, '') else None
                except Exception:
                    usd_val = None
                if usd_val is None:
                    try:
                        rate = fx_rates.get_rate_for_date(str(r.get('Date') or '').strip())
                        if rate and rate > 0:
                            usd_val = float(r.get('SellingPrice') or 0) / float(rate)
                            computed_usd_count += 1
                    except Exception:
                        usd_val = None
                if usd_val is not None:
                    try:
                        total_sell_usd += float(usd_val)
                    except Exception:
                        pass
        suffix = f" (computed {computed_usd_count} from rates)" if computed_usd_count else ""
        totals_var.set(f"Items: {shown}    Total Selling (TRY): {total_sell:.2f}    Total Selling (USD): {total_sell_usd:.2f}{suffix}")
        try:
            stripe_treeview(tree)
        except Exception:
            pass

    # Initial options and population
    year_combo['values'] = compute_year_options(rows)
    year_combo.set('All')
    populate_tree(rows, 'All', '')

    def refresh():
        new_rows = read_sales()
        # Refresh year options (in case new prefixes were added)
        vals = compute_year_options(new_rows)
        year_combo['values'] = vals
        if year_var.get() not in vals:
            year_combo.set('All')
        populate_tree(new_rows, year_var.get(), search_var.get().strip())
        try:
            selected_var.set('Selected: 0')
        except Exception:
            pass

    def on_year_change(event=None):
        # Re-populate using current file content and selected filter
        refresh()

    def on_search_change(event=None):
        refresh()
    def on_return_change(event=None):
        refresh()

    def get_selected_index():
        sel = tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def _update_selected_badge(event=None):
        try:
            selected_var.set(f"Selected: {len(tree.selection())}")
        except Exception:
            pass
    tree.bind('<<TreeviewSelect>>', _update_selected_badge)

    def do_delete():
        idx = get_selected_index()
        if idx is None:
            messagebox.showwarning('Select', 'Select a row first')
            return
        if not messagebox.askyesno('Confirm', 'Delete selected sale?'):
            return
        rows = read_sales()
        if 0 <= idx < len(rows):
            del rows[idx]
            write_sales(rows)
            refresh()

    def do_mark_returned():
        idx = get_selected_index()
        if idx is None:
            messagebox.showwarning('Select', 'Select a row first')
            return
        rows = read_sales()
        if not (0 <= idx < len(rows)):
            messagebox.showerror('Error', 'Invalid selection index')
            return
        rec = rows[idx]
        # Prevent duplicate returns for same product id
        existing = { (r.get('ProductID') or '').strip() for r in read_returns() }
        pid = (rec.get('ProductID') or '').strip()
        if pid in existing:
            if not messagebox.askyesno('Already returned', 'This Product ID already has a return recorded. Record another return anyway?'):
                return

        # Dialog to collect return info
        dlg = tk.Toplevel(win)
        dlg.title('Mark as Returned')
        dlg.geometry('460x380')

        from datetime import datetime as _dt
        ttk.Label(dlg, text='Return Date (YYYY-MM-DD):').pack(pady=4)
        date_e = ttk.Entry(dlg, width=32)
        date_e.insert(0, _dt.now().strftime('%Y-%m-%d'))
        date_e.pack(pady=2)

        ttk.Label(dlg, text='Refund Amount (optional):').pack(pady=4)
        refund_e = ttk.Entry(dlg, width=20)
        refund_e.insert(0, '')
        refund_e.pack(pady=2)

        restock_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dlg, text='Restock inventory', variable=restock_var).pack(pady=6)

        ttk.Label(dlg, text='Reason (optional):').pack(pady=4)
        reason_e = ttk.Entry(dlg, width=40)
        reason_e.pack(pady=2)

        ttk.Label(dlg, text='Attach Document (optional):').pack(pady=4)
        doc_frame = ttk.Frame(dlg)
        doc_entry = ttk.Entry(doc_frame, width=32)
        doc_entry.pack(side=tk.LEFT, padx=(0,6))
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

        def save_return():
            d = date_e.get().strip()
            try:
                _dt.strptime(d, '%Y-%m-%d')
            except Exception:
                messagebox.showerror('Invalid date', 'Use YYYY-MM-DD', parent=dlg)
                return
            refund = None
            ra = refund_e.get().strip()
            if ra:
                try:
                    refund = float(ra)
                except Exception:
                    messagebox.showerror('Invalid amount', 'Refund must be a number', parent=dlg)
                    return
            try:
                # Determine restock final decision with confirmation if requested
                restock_final = 0
                restocked_batches = []
                if restock_var.get():
                    if messagebox.askyesno('Confirm Restock', 'Return item to original batch inventory? The product may be broken. Proceed?', parent=dlg):
                        restock_final = 1
                        try:
                            import db
                            # Use batch-aware return handling
                            restocked_batches = db.handle_return_batch_allocation(pid, 1.0)
                            # Also update the general inventory
                            db.update_inventory(rec.get('Category',''), rec.get('Subcategory',''), 1)
                        except Exception as e:
                            messagebox.showwarning('Batch Restock Warning', 
                                f'General inventory updated, but batch restock failed: {e}', parent=dlg)
                    else:
                        restock_final = 0

                ensure_returns_csv()
                with RETURNS_CSV.open('a', newline='') as f:
                    w = csv.DictWriter(f, fieldnames=['ReturnDate', 'ProductID', 'SaleDate', 'Category', 'Subcategory', 'UnitPrice', 'SellingPrice', 'Platform', 'RefundAmount', 'Restock', 'Reason', 'ReturnDocPath'])
                    w.writerow({
                        'ReturnDate': d,
                        'ProductID': pid,
                        'SaleDate': rec.get('Date',''),
                        'Category': rec.get('Category',''),
                        'Subcategory': rec.get('Subcategory',''),
                        'UnitPrice': rec.get('UnitPrice',''),
                        'SellingPrice': rec.get('SellingPrice',''),
                        'Platform': rec.get('Platform',''),
                        'RefundAmount': refund if refund is not None else '',
                        'Restock': restock_final,
                        'Reason': reason_e.get().strip(),
                        'ReturnDocPath': doc_entry.get().strip(),
                    })
                
                # Show batch restock confirmation
                if restock_final and restocked_batches:
                    batch_info = []
                    for batch in restocked_batches:
                        info = f"Batch {batch['batch_id']} ({batch['batch_date']}, {batch['supplier']}): +{batch['returned_quantity']}"
                        batch_info.append(info)
                    
                    if batch_info:
                        msg = f"✅ Return processed with batch tracking:\n\n"
                        msg += f"🔄 Restocked to batches:\n" + "\n".join(batch_info)
                        messagebox.showinfo('Return Completed with Batch Tracking', msg, parent=dlg)
                
                dlg.destroy()
                refresh()
            except Exception as e:
                messagebox.showerror('Error', f'Failed to record return: {e}', parent=dlg)

        ttk.Button(dlg, text='Save Return', command=save_return).pack(pady=10)

    def do_edit():
        idx = get_selected_index()
        if idx is None:
            messagebox.showwarning('Select', 'Select a row first')
            return
        rows = read_sales()
        if not (0 <= idx < len(rows)):
            messagebox.showerror('Error', 'Invalid selection index')
            return
        rec = rows[idx]
        # Prevent editing core sale if returned
        try:
            returned = { (r.get('ProductID') or '').strip() for r in read_returns() }
        except Exception:
            returned = set()
        pid = (rec.get('ProductID') or '').strip()
        if pid in returned:
            messagebox.showinfo('Not allowed', 'This sale has a recorded return and cannot be edited. You can delete the return first if needed.')
            return

        dlg = tk.Toplevel(win)
        dlg.title('Edit Sale')
        dlg.geometry('460x600')

        entries = {}

        def add_field(label, key, disabled=False):
            ttk.Label(dlg, text=label).pack(pady=4)
            e = ttk.Entry(dlg, width=40)
            e.insert(0, str(rec.get(key, '')))
            if disabled:
                e.configure(state='disabled')
            e.pack(pady=2)
            entries[key] = e

        add_field('Date (YYYY-MM-DD):', 'Date')
        add_field('Category:', 'Category')
        add_field('Subcategory (optional):', 'Subcategory')
        add_field('Quantity:', 'Quantity')
        add_field('Unit Price:', 'UnitPrice')
        # Show SellingPrice but keep disabled; it will be recomputed on save
        add_field('Selling Price (auto):', 'SellingPrice', disabled=True)
        add_field('Platform:', 'Platform')
        add_field('Product ID:', 'ProductID')
        add_field('Customer ID:', 'CustomerID')
        # DocumentPath with Browse button
        ttk.Label(dlg, text='Related Document (path):').pack(pady=4)
        doc_frame = ttk.Frame(dlg)
        doc_entry = ttk.Entry(doc_frame, width=32)
        doc_entry.insert(0, str(rec.get('DocumentPath', '')))
        doc_entry.pack(side=tk.LEFT, padx=(0, 6))

        def browse_doc():
            path = filedialog.askopenfilename(parent=dlg, title='Select document')
            if path:
                try:
                    doc_entry.delete(0, tk.END)
                    from pathlib import Path as _P
                    doc_entry.insert(0, str(_P(path).resolve()))
                except Exception:
                    doc_entry.delete(0, tk.END)
                    doc_entry.insert(0, path)

        ttk.Button(doc_frame, text='Browse...', command=browse_doc).pack(side=tk.LEFT)
        doc_frame.pack(pady=2)
        entries['DocumentPath'] = doc_entry

        def save_edit():
            from datetime import datetime as _dt
            d = entries['Date'].get().strip()
            try:
                _dt.strptime(d, '%Y-%m-%d')
            except Exception:
                messagebox.showerror('Invalid date', 'Use YYYY-MM-DD')
                return
            cat = entries['Category'].get().strip()
            if not cat:
                messagebox.showwarning('Missing', 'Category is required')
                return
            sub = entries['Subcategory'].get().strip()
            try:
                qty = float(entries['Quantity'].get().strip())
            except Exception:
                messagebox.showerror('Invalid quantity', 'Quantity must be a number')
                return
            try:
                unit = float(entries['UnitPrice'].get().strip())
            except Exception:
                messagebox.showerror('Invalid unit price', 'Unit price must be a number')
                return
            price = qty * unit
            platform = entries['Platform'].get().strip()
            pid = entries['ProductID'].get().strip()
            customer_id = entries['CustomerID'].get().strip()
            docp = entries['DocumentPath'].get().strip()

            # update row and write
            rows[idx] = {
                'Date': d,
                'Category': cat,
                'Subcategory': sub,
                'Quantity': qty,
                'UnitPrice': unit,
                'SellingPrice': price,
                'Platform': platform,
                'ProductID': pid,
                'CustomerID': customer_id,
                'DocumentPath': docp,
            }
            write_sales(rows)
            dlg.destroy()
            refresh()

        ttk.Button(dlg, text='Save', command=save_edit).pack(pady=10)

    # Action buttons with improved hierarchy
    btn_frame = ttk.Frame(main_container)
    year_combo.bind('<<ComboboxSelected>>', on_year_change)
    search_entry.bind('<KeyRelease>', on_search_change)
    
    # Primary actions (left side)
    primary_frame = ttk.Frame(btn_frame)
    primary_frame.pack(side='left', fill='x', expand=True)
    
    ttk.Button(primary_frame, text='✏️ Edit', style='Success.TButton', 
              command=do_edit).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(primary_frame, text='🔄 Refresh', style='Primary.TButton',
              command=refresh).pack(side=tk.LEFT, padx=4)
    ttk.Button(primary_frame, text='Select All', style='Primary.TButton', command=lambda: (select_all(), selected_var.set(f"Selected: {len(tree.selection())}"))).pack(side=tk.LEFT, padx=4)
    def deselect_all():
        try:
            tree.selection_remove(tree.get_children(''))
        except Exception:
            pass
    ttk.Button(primary_frame, text='Deselect All', style='Primary.TButton', command=lambda: (deselect_all(), selected_var.set('Selected: 0'))).pack(side=tk.LEFT, padx=4)
    def do_manage_docs():
        idx = get_selected_index()
        if idx is None:
            messagebox.showwarning('Select', 'Select a row first')
            return
        rows = read_sales()
        if not (0 <= idx < len(rows)):
            messagebox.showerror('Error', 'Invalid selection index', parent=win)
            return
        rec = rows[idx]
        product_id = (rec.get('ProductID') or '').strip()
        docs = parse_docs(rec.get('DocumentPath', ''))

        dlg = tk.Toplevel(win)
        dlg.title(f'Documents: {product_id or "(no ProductID)"}')
        dlg.geometry('560x380')
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
            if not docs:
                return
            for p in docs:
                try:
                    _open_default(p)
                except Exception:
                    pass

        def save_and_close():
            rows2 = read_sales()
            if 0 <= idx < len(rows2):
                rows2[idx]['DocumentPath'] = format_docs(docs)
                write_sales(rows2)
            dlg.destroy()
            refresh()

        ttk.Button(btns, text='➕ Add…', command=add_docs).pack(side=tk.LEFT)
        ttk.Button(btns, text='🗑️ Remove', command=remove_selected).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text='📄 Open', command=open_selected).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text='📂 Open All', command=open_all).pack(side=tk.LEFT, padx=6)
        ttk.Button(container, text='Save & Close', command=save_and_close).pack(pady=(8,0))

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

    # removed single open/attach; managed via do_manage_docs

    # Secondary actions (right side)
    secondary_frame = ttk.Frame(btn_frame)
    secondary_frame.pack(side='right')
    
    def do_view_batch_info():
        idx = get_selected_index()
        if idx is None:
            messagebox.showwarning('Select', 'Select a row first')
            return
        
        rows = read_sales()
        if 0 <= idx < len(rows):
            product_id = rows[idx].get('ProductID', '').strip()
            if not product_id:
                messagebox.showwarning('No Product ID', 'This sale has no Product ID')
                return
            
            try:
                import db
                allocations = db.get_sale_batch_info(product_id)
                show_batch_info_dialog(product_id, allocations)
            except Exception as e:
                messagebox.showerror('Error', f'Failed to get batch info: {e}')
    
    def show_batch_info_dialog(product_id, allocations):
        """Show detailed batch allocation information for a sale."""
        dlg = tk.Toplevel(win)
        dlg.title(f'🔍 Batch Info: {product_id}')
        dlg.geometry('800x400')
        dlg.resizable(True, True)
        dlg.transient(win)
        dlg.grab_set()
        
        # Apply theme
        from .theme import apply_theme
        apply_theme(dlg)
        
        container = ttk.Frame(dlg, padding=16)
        container.pack(fill='both', expand=True)
        
        # Header
        ttk.Label(container, text=f'🔍 Batch Allocation Details for {product_id}', 
                 font=('', 12, 'bold')).pack(anchor='w', pady=(0, 12))
        
        if not allocations:
            ttk.Label(container, text='❌ No batch allocation found for this Product ID\n\nThis may be a sale from before batch tracking was implemented.',
                     font=('', 10)).pack(anchor='w')
        else:
            # Summary
            total_cost = sum(a['quantity_from_batch'] * a['unit_cost'] for a in allocations)
            total_revenue = sum(a['quantity_from_batch'] * a['unit_sale_price'] for a in allocations)
            total_profit = total_revenue - total_cost
            margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
            
            summary = ttk.LabelFrame(container, text='💰 Profit Summary', padding=8)
            summary.pack(fill='x', pady=(0, 12))
            
            ttk.Label(summary, text=f'💸 Total Cost Basis: ${total_cost:.2f}', font=('', 9)).pack(anchor='w')
            ttk.Label(summary, text=f'💰 Total Revenue: ${total_revenue:.2f}', font=('', 9)).pack(anchor='w')
            ttk.Label(summary, text=f'📈 Total Profit: ${total_profit:.2f}', font=('', 9)).pack(anchor='w')
            ttk.Label(summary, text=f'📊 Profit Margin: {margin:.1f}%', font=('', 9)).pack(anchor='w')
            
            # Allocation details table
            table_frame = ttk.LabelFrame(container, text='📦 Batch Allocation Details', padding=8)
            table_frame.pack(fill='both', expand=True)
            
            cols = ['Batch ID', 'Batch Date', 'Supplier', 'Quantity', 'Unit Cost', 'Sale Price', 'Profit/Unit', 'Total Profit']
            tree = ttk.Treeview(table_frame, columns=cols, show='headings', height=8)
            
            for col in cols:
                tree.heading(col, text=col, anchor='w')
                tree.column(col, width=100, minwidth=60)
            
            for alloc in allocations:
                total_item_profit = alloc['quantity_from_batch'] * alloc['profit_per_unit']
                values = [
                    str(alloc['batch_id']) if alloc['batch_id'] else 'SHORTAGE',
                    alloc.get('batch_date', 'N/A'),
                    alloc.get('supplier', 'N/A'),
                    f"{alloc['quantity_from_batch']:.1f}",
                    f"${alloc['unit_cost']:.2f}",
                    f"${alloc['unit_sale_price']:.2f}",
                    f"${alloc['profit_per_unit']:.2f}",
                    f"${total_item_profit:.2f}"
                ]
                
                item_id = tree.insert('', 'end', values=values)
                
                # Highlight shortages
                if alloc['batch_id'] is None:
                    from .theme import stripe_treeview
                    stripe_treeview(tree, item_id, 'danger')
            
            scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
        
        # Close button
        ttk.Button(container, text='Close', command=dlg.destroy).pack(pady=(12, 0))

    ttk.Button(secondary_frame, text='📊 Batch Info', 
              command=do_view_batch_info).pack(side=tk.LEFT, padx=4)
    ttk.Button(secondary_frame, text='� Documents', 
              command=do_manage_docs).pack(side=tk.LEFT, padx=4)
    ttk.Button(secondary_frame, text='↩️ Mark Returned', style='Secondary.TButton',
              command=do_mark_returned).pack(side=tk.LEFT, padx=(8, 4))
    ttk.Button(secondary_frame, text='🗑️ Delete', style='Danger.TButton',
              command=do_delete).pack(side=tk.LEFT, padx=4)
    
    btn_frame.pack(fill='x', pady=8)

    # Bind filters after buttons defined
    return_combo.bind('<<ComboboxSelected>>', on_return_change)
