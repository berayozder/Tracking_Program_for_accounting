import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
from pathlib import Path
import os
import json
import sys
import subprocess
from .theme import stripe_treeview, maximize_window, themed_button
import core.fx_rates as fx_rates

SALES_CSV = Path(__file__).resolve().parents[1] / 'data' / 'sales.csv'
RETURNS_CSV = Path(__file__).resolve().parents[1] / 'data' / 'returns.csv'


def read_sales(include_deleted: bool = False):
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
        # Normalize FX and currency columns: support legacy SaleFXToTRY and new FXToBase
        if rows and 'FXToBase' not in reader.fieldnames:
            for r in rows:
                # Prefer FXToBase, fallback to SaleFXToTRY if present
                if 'FXToBase' not in r or not r.get('FXToBase'):
                    if 'SaleFXToTRY' in r and r.get('SaleFXToTRY'):
                        r['FXToBase'] = r.get('SaleFXToTRY')
                    else:
                        r['FXToBase'] = ''

        # Inject SaleCurrency if missing
        if rows and 'SaleCurrency' not in reader.fieldnames:
            try:
                from db.db import get_default_sale_currency as _get_def_sale_ccy
                _def_ccy = _get_def_sale_ccy()
            except Exception:
                _def_ccy = ''
            for r in rows:
                if 'SaleCurrency' not in r or not r.get('SaleCurrency'):
                    r['SaleCurrency'] = _def_ccy
        # Filter out soft-deleted rows if the CSV contains a Deleted column
        filtered = []
        for r in rows:
            try:
                if not include_deleted and str(r.get('Deleted', '')).strip() in ('1', 'true', 'True'):
                    continue
            except Exception:
                pass
            filtered.append(r)
        return filtered


# Include SaleCurrency to capture the currency in which the sale occurred.
DESIRED_COLS = ['Date', 'Category', 'Subcategory', 'Quantity', 'UnitPrice', 'SellingPrice', 'Platform', 'ProductID', 'CustomerID', 'DocumentPath', 'FXToBase', 'SellingPriceBase', 'SaleCurrency', 'Deleted']


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
            # Ensure SaleCurrency present
            if 'SaleCurrency' not in r or not r.get('SaleCurrency'):
                try:
                    from db.db import get_default_sale_currency as _get_def_sale_ccy
                    r['SaleCurrency'] = _get_def_sale_ccy()
                except Exception:
                    r['SaleCurrency'] = ''
            out = {c: r.get(c, '') for c in DESIRED_COLS}
            if 'Deleted' not in out:
                out['Deleted'] = r.get('Deleted', '')
            w.writerow(out)


def ensure_returns_csv():
    RETURNS_CSV.parent.mkdir(parents=True, exist_ok=True)
    # Include RefundCurrency to support FX-aware refunds
    desired = ['ReturnDate', 'ProductID', 'SaleDate', 'Category', 'Subcategory', 'UnitPrice', 'SellingPrice', 'Platform', 'RefundAmount', 'RefundCurrency', 'Restock', 'Reason', 'ReturnDocPath']
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
                'RefundCurrency': rowd.get('RefundCurrency', ''),
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
    # Prefer DB for returns to reflect real-time state; fallback to CSV only if needed
    try:
        import db.db as db
        rows = db.list_returns()
        # Map to a CSV-like dict for compatibility where used
        out = []
        for r in rows:
            try:
                # sqlite3.Row doesn't implement .get, so convert to dict safely
                if hasattr(r, 'keys'):
                    rr = {k: r[k] for k in r.keys()}
                else:
                    rr = dict(r)
            except Exception:
                rr = {}
            out.append({
                'ReturnDate': rr.get('return_date',''),
                'ProductID': rr.get('product_id',''),
                'SaleDate': rr.get('sale_date',''),
                'Category': rr.get('category',''),
                'Subcategory': rr.get('subcategory',''),
                'UnitPrice': rr.get('unit_price',''),
                'SellingPrice': rr.get('selling_price',''),
                'Platform': rr.get('platform',''),
                'RefundAmount': rr.get('refund_amount',''),
                'RefundCurrency': rr.get('refund_currency',''),
                'Restock': rr.get('restock',''),
                'Reason': rr.get('reason',''),
                'ReturnDocPath': rr.get('doc_paths',''),
            })
        return out
    except Exception:
        # Legacy fallback
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
    'SaleCurrency': {'width': 80, 'anchor': 'center'},
    'FXToBase': {'width': 120, 'anchor': 'e'},
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

    # Show deleted toggle
    show_deleted_var = tk.BooleanVar(value=False)
    try:
        cb = ttk.Checkbutton(totals_frame, text='Show deleted', variable=show_deleted_var, command=lambda: refresh())
        cb.pack(side='right', padx=(8, 0))
    except Exception:
        pass

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
            import db.db as db
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
        returned_ids = set()
        try:
            for rr in read_returns():
                pid = (rr.get('ProductID') or '').strip()
                if pid:
                    returned_ids.add(pid)
        except Exception:
            returned_ids = set()
        for idx, r in enumerate(all_rows):
            is_returned = (r.get('ProductID') or '').strip() in returned_ids
            if row_matches_year(r, yy) and row_matches_search(r, q) and row_matches_returned(r, return_var.get(), returned_ids):
                vals = [r.get(c, '') for c in cols]
                # Mark returned items visually
                try:
                    pid_idx = cols.index('ProductID')
                    pidv = str(vals[pid_idx])
                    if pidv in returned_ids:
                        vals[pid_idx] = pidv + ' (Returned)'
                except Exception:
                    pass
                try:
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
                # Insert row and apply tag for returned
                tag = 'returned' if is_returned else ''
                tree.insert('', tk.END, iid=str(idx), values=vals, tags=(tag,))
                shown += 1
                # Only count non-returned sales in totals
                if not is_returned:
                    try:
                        total_sell += float(r.get('SellingPrice') or 0)
                    except Exception:
                        pass
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
        # Highlight returned rows — make them more visually noticeable
        try:
            # Apply striping first, then override returned tag so it stands out
            stripe_treeview(tree)
            # Stronger background and amber text, bold font for emphasis (distinct from error red)
            tree.tag_configure('returned', background='#fff9e6', foreground='#8a6d00', font=('', 9, 'bold'))
            # Also configure a visible border-like highlight when possible
            # (Some themes may ignore font or foreground on Treeview tags; this still helps on most platforms)
        except Exception:
            try:
                tree.tag_configure('returned', background='#fff4cc')
            except Exception:
                pass

    # Initial options and population
    year_combo['values'] = compute_year_options(rows)
    year_combo.set('All')
    populate_tree(rows, 'All', '')

    def refresh():
        new_rows = read_sales(include_deleted=show_deleted_var.get())
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
        sel = tree.selection()
        if not sel:
            messagebox.showwarning('Select', 'Select at least one row first')
            return
        count = len(sel)
        if count == 1:
            prompt = 'Delete the selected sale?'
        else:
            prompt = f'Delete {count} selected sales?'
        if not messagebox.askyesno('Confirm', prompt):
            return

        # Read current rows and mark selected ones as Deleted (soft-delete)
        rows = read_sales()
        # iids were set to original list index when populating; convert to ints where possible
        idxs = []
        for iid in sel:
            try:
                idxs.append(int(iid))
            except Exception:
                # If iid isn't an int, try to locate by matching ProductID in values
                try:
                    vals = tree.item(iid).get('values', ())
                    pid_idx = cols.index('ProductID') if 'ProductID' in cols else 0
                    pidv = vals[pid_idx] if pid_idx < len(vals) else None
                    found = next((i for i, r in enumerate(rows) if str(r.get('ProductID','')) == str(pidv)), None)
                    if found is not None:
                        idxs.append(found)
                except Exception:
                    pass

        changed = False
        for i in set(idxs):
            if 0 <= i < len(rows):
                try:
                    rows[i]['Deleted'] = '1'
                    changed = True
                except Exception:
                    pass
        if changed:
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
        dlg.geometry('460x340')

        from datetime import datetime as _dt
        ttk.Label(dlg, text='Return Date (YYYY-MM-DD):').pack(pady=4)
        date_e = ttk.Entry(dlg, width=32)
        date_e.insert(0, _dt.now().strftime('%Y-%m-%d'))
        date_e.pack(pady=2)

        # No manual refund entry; refund will equal SellingPrice in SaleCurrency

        restock_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dlg, text='Restock inventory', variable=restock_var).pack(pady=6)

        ttk.Label(dlg, text='Reason (recommended):').pack(pady=4)
        reason_frame = ttk.Frame(dlg)
        reason_frame.pack(pady=2)
        # Load suggestions: distinct reasons from DB plus common defaults
        try:
            import db.db as db
            db_reasons = db.get_distinct_return_reasons() or []
        except Exception:
            db_reasons = []
        common_defaults = [
            'Defective', 'Damaged in shipping', 'Not as described', 'Changed mind',
            'Wrong item sent', 'Missing parts', 'Warranty return', 'Customer complaint'
        ]
        # Merge unique values keeping DB reasons first
        seen = set()
        suggestions = []
        for s in db_reasons + common_defaults:
            v = str(s).strip()
            if v and v not in seen:
                seen.add(v)
                suggestions.append(v)
        reason_var = tk.StringVar(value='')

        # Type-ahead filtering: update Combobox values as user types
        def filter_suggestions(event=None):
            typed = reason_var.get().strip().lower()
            filtered = [s for s in suggestions if typed in s.lower()] if typed else suggestions
            reason_combo['values'] = filtered

        reason_combo = ttk.Combobox(reason_frame, textvariable=reason_var, values=suggestions, width=38)
        reason_combo.pack(side=tk.LEFT)
        reason_combo.configure(state='normal')
        reason_combo.bind('<KeyRelease>', filter_suggestions)

        # '+ Add to defaults' button
        def add_reason_to_defaults():
            val = reason_var.get().strip()
            if val and val not in suggestions:
                try:
                    import db.db as db
                    db.add_return_reason(val)
                    suggestions.append(val)
                    reason_combo['values'] = suggestions
                    tk.messagebox.showinfo('Added', f'"{val}" added to Reason presets.')
                except Exception:
                    tk.messagebox.showerror('Error', 'Could not add reason to presets.')

        add_btn = ttk.Button(reason_frame, text='+ Add to defaults', command=add_reason_to_defaults)
        add_btn.pack(side=tk.LEFT, padx=6)

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

        themed_button(doc_frame, text='Browse…', variant='secondary', command=browse_doc).pack(side=tk.LEFT)
        doc_frame.pack(pady=2)

        def save_return():
            d = date_e.get().strip()
            try:
                _dt.strptime(d, '%Y-%m-%d')
            except Exception:
                messagebox.showerror('Invalid date', 'Use YYYY-MM-DD', parent=dlg)
                return
            # Refund amount equals sale price automatically
            try:
                refund = float(rec.get('SellingPrice') or 0.0)
            except Exception:
                refund = 0.0
            try:
                # Determine restock final decision with confirmation if requested
                restock_final = 0
                if restock_var.get():
                    if messagebox.askyesno('Confirm Restock', 'Return item to original batch inventory? The product may be broken. Proceed?', parent=dlg):
                        restock_final = 1
                    else:
                        restock_final = 0

                # Write return directly into DB
                import db.db as db
                # Use SaleCurrency for refund currency; fallback to default if missing
                refund_ccy = (rec.get('SaleCurrency') or '').strip().upper()
                if not refund_ccy:
                    try:
                        refund_ccy = db.get_default_sale_currency()
                    except Exception:
                        refund_ccy = ''
                # Build fields and insert
                res = db.insert_return({
                    'return_date': d,
                    'product_id': pid,
                    'sale_date': rec.get('Date',''),
                    'category': rec.get('Category',''),
                    'subcategory': rec.get('Subcategory',''),
                    'unit_price': rec.get('UnitPrice',''),
                    'selling_price': rec.get('SellingPrice',''),
                    'platform': rec.get('Platform',''),
                    'refund_amount': refund,
                    'refund_currency': refund_ccy,
                    'restock': restock_final,
                    'reason': reason_var.get().strip(),
                    'doc_paths': doc_entry.get().strip(),
                })
                # Show batch restock confirmation if insert_return returned restocked details
                try:
                    if res and isinstance(res, dict) and res.get('restocked_batches'):
                        batch_info = []
                        for batch in res.get('restocked_batches'):
                            info = f"Batch {batch['batch_id']} ({batch['batch_date']}, {batch['supplier']}): +{batch['returned_quantity']}"
                            batch_info.append(info)
                        if batch_info:
                            msg = f"✅ Return processed with batch tracking:\n\n"
                            msg += f"🔄 Restocked to batches:\n" + "\n".join(batch_info)
                            messagebox.showinfo('Return Completed with Batch Tracking', msg, parent=dlg)
                except Exception:
                    pass
                
                dlg.destroy()
                # Refresh the sales view immediately
                refresh()
                # Emit a virtual event so other windows can refresh (e.g., batch analytics)
                try:
                    win.event_generate('<<ReturnRecorded>>')
                except Exception:
                    pass
            except Exception as e:
                messagebox.showerror('Error', f'Failed to record return: {e}', parent=dlg)

        themed_button(dlg, text='Save Return', variant='primary', command=save_return).pack(pady=10)

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

        themed_button(doc_frame, text='Browse…', variant='secondary', command=browse_doc).pack(side=tk.LEFT)
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

        themed_button(dlg, text='Save', variant='primary', command=save_edit).pack(pady=10)

    # Action buttons with improved hierarchy
    btn_frame = ttk.Frame(main_container)
    year_combo.bind('<<ComboboxSelected>>', on_year_change)
    search_entry.bind('<KeyRelease>', on_search_change)
    
    # Primary actions (left side)
    primary_frame = ttk.Frame(btn_frame)
    primary_frame.pack(side='left', fill='x', expand=True)
    
    themed_button(primary_frame, text='✏️ Edit', variant='success', 
              command=do_edit).pack(side=tk.LEFT, padx=(0, 8))
    themed_button(primary_frame, text='🔄 Refresh', variant='primary',
              command=refresh).pack(side=tk.LEFT, padx=4)
    themed_button(primary_frame, text='Select All', variant='primary', command=lambda: (select_all(), selected_var.set(f"Selected: {len(tree.selection())}"))).pack(side=tk.LEFT, padx=4)
    def deselect_all():
        try:
            tree.selection_remove(tree.get_children(''))
        except Exception:
            pass
    themed_button(primary_frame, text='Deselect All', variant='primary', command=lambda: (deselect_all(), selected_var.set('Selected: 0'))).pack(side=tk.LEFT, padx=4)
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

        themed_button(btns, text='➕ Add…', variant='secondary', command=add_docs).pack(side=tk.LEFT)
        themed_button(btns, text='🗑️ Remove', variant='secondary', command=remove_selected).pack(side=tk.LEFT, padx=6)
        themed_button(btns, text='📄 Open', variant='secondary', command=open_selected).pack(side=tk.LEFT, padx=6)
        themed_button(btns, text='📂 Open All', variant='secondary', command=open_all).pack(side=tk.LEFT, padx=6)
        themed_button(container, text='Save & Close', variant='primary', command=save_and_close).pack(pady=(8,0))

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
                import db.db as db
                allocations = db.get_sale_batch_info(product_id)
                show_batch_info_dialog(product_id, allocations)
            except Exception as e:
                messagebox.showerror('Error', f'Failed to get batch info: {e}')
    
    def show_batch_info_dialog(product_id, allocations):
        """Show detailed batch allocation information for a sale."""
        dlg = tk.Toplevel(win)
        dlg.title(f'🔍 Batch Info: {product_id}')
        # Slightly larger default size for comfortable viewing
        dlg.geometry('920x520')
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
            total_cost = sum(float(a.get('quantity_from_batch') or 0) * float(a.get('unit_cost') or 0) for a in allocations)
            total_revenue = sum(float(a.get('quantity_from_batch') or 0) * float(a.get('unit_sale_price') or 0) for a in allocations)
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
                total_item_profit = float(alloc.get('quantity_from_batch') or 0) * float(alloc.get('profit_per_unit') or 0)
                values = [
                    str(alloc['batch_id']) if alloc['batch_id'] else 'SHORTAGE',
                    alloc.get('batch_date', 'N/A'),
                    alloc.get('supplier', 'N/A'),
                    f"{float(alloc.get('quantity_from_batch') or 0):.1f}",
                    f"${float(alloc.get('unit_cost') or 0):.2f}",
                    f"${float(alloc.get('unit_sale_price') or 0):.2f}",
                    f"${float(alloc.get('profit_per_unit') or 0):.2f}",
                    f"${float(total_item_profit or 0):.2f}"
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
            # Ensure the tree gets focus so the Close button isn't highlighted on open
            try:
                tree.focus_set()
            except Exception:
                pass
        
        # Close button
        themed_button(container, text='Close', variant='secondary', command=dlg.destroy).pack(pady=(12, 0))

    themed_button(secondary_frame, text='📊 Batch Info', variant='secondary',
              command=do_view_batch_info).pack(side=tk.LEFT, padx=4)
    themed_button(secondary_frame, text='📄 Documents', variant='secondary',
              command=do_manage_docs).pack(side=tk.LEFT, padx=4)
    themed_button(secondary_frame, text='↩️ Mark Returned', variant='secondary',
              command=do_mark_returned).pack(side=tk.LEFT, padx=(8, 4))
    themed_button(secondary_frame, text='🗑️ Delete', variant='danger',
              command=do_delete).pack(side=tk.LEFT, padx=4)
    def do_undelete():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning('Select', 'Select at least one row first')
            return
        # iids correspond to CSV row indices where possible
        idxs = []
        for iid in sel:
            try:
                idxs.append(int(iid))
            except Exception:
                # try to map via ProductID fallback
                try:
                    vals = tree.item(iid).get('values', ())
                    pid_idx = cols.index('ProductID') if 'ProductID' in cols else 0
                    pidv = vals[pid_idx] if pid_idx < len(vals) else None
                    # find matching row index in full file
                    all_rows = read_sales(include_deleted=True)
                    found = next((i for i, r in enumerate(all_rows) if str(r.get('ProductID','')) == str(pidv)), None)
                    if found is not None:
                        idxs.append(found)
                except Exception:
                    pass
        if not idxs:
            messagebox.showinfo('Nothing', 'No matching rows to undelete')
            return
        try:
            import db.db as db
            # db.undelete_sales_by_indices expects a list of indices
            db.undelete_sales_by_indices(idxs)
            refresh()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to undelete: {e}')

    themed_button(secondary_frame, text='♻️ Undelete', variant='primary',
              command=do_undelete).pack(side=tk.LEFT, padx=4)
    
    btn_frame.pack(fill='x', pady=8)

    # Bind filters after buttons defined
    return_combo.bind('<<ComboboxSelected>>', on_return_change)
