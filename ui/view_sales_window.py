import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from pathlib import Path
import os
import json
import sys
import subprocess
from .theme import stripe_treeview, maximize_window, themed_button
import core.fx_rates as fx_rates

# DAO imports
from db.sales_dao import list_sales, overwrite_sales, mark_sale_deleted, update_sale
from db.returns_dao import list_returns, insert_return
from db.imports_dao import get_sale_batch_info

# Column headers for Treeview / CSV
DESIRED_COLS = [
    'Date', 'Category', 'Subcategory', 'Quantity', 'SellingPrice',
    'VAT Rate', 'VAT Amount', 'Net', 'Gross',
    'Platform', 'ProductID', 'CustomerID', 'DocumentPath',
    'FXToBase', 'SellingPriceBase', 'SaleCurrency', 'Deleted'
]

# ────────────────────────────────
# Data access wrappers
# ────────────────────────────────

def read_sales(include_deleted: bool = False):
    return [_normalize_row_for_ui(r) for r in list_sales(include_deleted=include_deleted)]

def write_sales(rows):
    return overwrite_sales(rows)

def read_returns():
    """Fetch returns using DAO."""
    try:
        return [ _normalize_row_for_ui(r) for r in list_returns() ]
    except Exception:
        try:
            return list_returns()
        except Exception:
            return []


def _normalize_row_for_ui(row):
    # Add VAT analytics fields for display
    try:
        vat_rate = float(r.get('vat_rate', 18.0) or 18.0)
        is_incl = int(r.get('is_vat_inclusive', 1) or 1)
        amt = float(r.get('selling_price', 0) or 0)
        if is_incl:
            net = amt / (1 + vat_rate/100)
            vat_amt = amt - net
            gross = amt
        else:
            net = amt
            vat_amt = amt * vat_rate/100
            gross = amt + vat_amt
        r['VAT Rate'] = f"{vat_rate:.2f}"
        r['VAT Amount'] = f"{vat_amt:.2f}"
        r['Net'] = f"{net:.2f}"
        r['Gross'] = f"{gross:.2f}"
    except Exception:
        r['VAT Rate'] = ''
        r['VAT Amount'] = ''
        r['Net'] = ''
        r['Gross'] = ''
    """Return a copy of the DB row that contains both snake_case and TitleCase keys
    so the legacy UI can read either shape."""
    try:
        r = dict(row)
    except Exception:
        # If it's already a dict-like
        r = {} if row is None else dict(row)
    # Mapping from UI TitleCase -> DB snake_case
    mapping = {
        'Date': 'date',
        'Category': 'category',
        'Subcategory': 'subcategory',
        'Quantity': 'quantity',
        'SellingPrice': 'selling_price',
        'Platform': 'platform',
        'ProductID': 'product_id',
        'CustomerID': 'customer_id',
        'DocumentPath': 'document_path',
        'FXToBase': 'fx_to_base',
        'SellingPriceBase': 'selling_price_base',
        'SaleCurrency': 'sale_currency',
        'Deleted': 'deleted',
    }
    for ui_k, db_k in mapping.items():
        # Ensure both forms exist on the dict so existing UI code can access either
        if ui_k not in r and db_k in r:
            try:
                r[ui_k] = r.get(db_k)
            except Exception:
                r[ui_k] = r.get(db_k)
        if db_k not in r and ui_k in r:
            try:
                r[db_k] = r.get(ui_k)
            except Exception:
                r[db_k] = r.get(ui_k)
    return r


def open_view_sales_window(root):
    # Helper: Select all rows in the treeview
    def select_all():
        try:
            tree.selection_set(tree.get_children())
        except Exception:
            pass

    # Helper: Export current table to CSV
    def do_export_csv():
        import csv
        from tkinter import filedialog
        file_path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
            title='Export Sales to CSV'
        )
        if not file_path:
            return
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                for iid in tree.get_children():
                    vals = tree.item(iid)['values']
                    writer.writerow(vals)
            messagebox.showinfo('Exported', f'Sales exported to {file_path}')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to export CSV: {e}')



    # --- Variable and widget initialization section ---
    win = tk.Toplevel(root)
    win.title('View Sales')
    win.geometry('1200x700')
    win.transient(root)
    win.grab_set()

    main_container = ttk.Frame(win, padding=12)
    main_container.pack(fill='both', expand=True)

    # Filters and controls
    filter_frame = ttk.Frame(main_container)
    filter_frame.pack(fill='x', pady=(0, 8))

    year_var = tk.StringVar(value='All')
    year_combo = ttk.Combobox(filter_frame, textvariable=year_var, width=8, state='readonly')
    year_combo.pack(side='left', padx=(0, 8))

    search_var = tk.StringVar()
    search_entry = ttk.Entry(filter_frame, textvariable=search_var, width=24)
    search_entry.pack(side='left', padx=(0, 8))

    return_var = tk.StringVar(value='All')
    return_combo = ttk.Combobox(filter_frame, textvariable=return_var, width=10, state='readonly', values=['All', 'Returned', 'Not Returned'])
    return_combo.pack(side='left', padx=(0, 8))

    show_deleted_var = tk.BooleanVar(value=False)
    show_deleted_cb = ttk.Checkbutton(filter_frame, text='Show Deleted', variable=show_deleted_var)
    show_deleted_cb.pack(side='left', padx=(0, 8))

    # Table
    cols = [
        'Date', 'Category', 'Subcategory', 'Quantity', 'SellingPrice',
        'VAT Rate', 'VAT Amount', 'Net', 'Gross',
        'Platform', 'ProductID', 'CustomerID', 'DocumentPath',
        'FXToBase', 'SellingPriceBase', 'SaleCurrency', 'Deleted'
    ]
    tree = ttk.Treeview(main_container, columns=cols, show='headings', height=20, selectmode='extended')
    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, width=90, minwidth=60)
    tree.pack(fill='both', expand=True)

    # Totals and status
    totals_var = tk.StringVar(value='')
    totals_label = ttk.Label(main_container, textvariable=totals_var, font=('', 10, 'bold'))
    totals_label.pack(fill='x', pady=(8, 0))

    selected_var = tk.StringVar(value='Selected: 0')
    selected_label = ttk.Label(main_container, textvariable=selected_var, font=('', 9))
    selected_label.pack(anchor='w', pady=(0, 8))

    # Initial data
    rows = [ _normalize_row_for_ui(r) for r in read_sales(include_deleted=show_deleted_var.get()) ]

    # Helper filter functions for analytics
    def compute_year_options(rows):
        years = set()
        for r in rows:
            try:
                y = str(r.get('Date', '')).split('-')[0]
                if y and y.isdigit():
                    years.add(y)
            except Exception:
                pass
        years = sorted(years, reverse=True)
        return ['All'] + years

    def row_matches_year(r, yy):
        if yy == 'All':
            return True
        try:
            return str(r.get('Date', '')).startswith(str(yy))
        except Exception:
            return False

    def row_matches_search(r, q):
        if not q:
            return True
        q = q.lower()
        for v in r.values():
            try:
                if q in str(v).lower():
                    return True
            except Exception:
                pass
        return False

    def row_matches_returned(r, return_filter, returned_ids):
        pid = (r.get('ProductID') or '').strip()
        if return_filter == 'All':
            return True
        elif return_filter == 'Returned':
            return pid in returned_ids
        elif return_filter == 'Not Returned':
            return pid not in returned_ids
        return True

    # --- Helper functions section (now after all variables/widgets are defined) ---
    def get_customer_name_mapping():
        """Create mapping from customer ID to customer name."""
        try:
            import db as db
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
        total_vat = 0.0
        total_net = 0.0
        total_gross = 0.0
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
                # If the row has an 'id' field (from DB), use it as iid so actions map to DB ids.
                iid_val = str(r.get('id')) if r.get('id') is not None else str(idx)
                tree.insert('', 0, iid=iid_val, values=vals, tags=(tag,))
                shown += 1
                # Only count non-returned sales in totals
                if not is_returned:
                    try:
                        total_sell += float(r.get('SellingPrice') or 0)
                        total_vat += float(r.get('VAT Amount') or 0)
                        total_net += float(r.get('Net') or 0)
                        total_gross += float(r.get('Gross') or 0)
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
        totals_var.set(f"Items: {shown}    Net: {total_net:.2f}    KDV: {total_vat:.2f}    Gross: {total_gross:.2f}    Total Selling (TRY): {total_sell:.2f}    Total Selling (USD): {total_sell_usd:.2f}{suffix}")
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

    def refresh():
        new_rows = [ _normalize_row_for_ui(r) for r in read_sales(include_deleted=show_deleted_var.get()) ]
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

        # Offer Void (recommended) vs Soft-delete
        if count == 1:
            choice_msg = 'Choose action for selected sale:\n\nYes = Void sale (mark void + optional reversal)\nNo = Soft-delete only (hide record)\nCancel = Abort'
        else:
            choice_msg = f'Choose action for {count} selected sales:\n\nYes = Void sales (mark void + optional reversal)\nNo = Soft-delete only (hide records)\nCancel = Abort'
        choice = messagebox.askyesnocancel('Delete / Void', choice_msg, icon='question')
        if choice is None:
            return

        # Gather DB ids from selection
        ids = []
        for iid in sel:
            try:
                ids.append(int(iid))
            except Exception:
                # fallback: try to map via ProductID value against current rows
                try:
                    vals = tree.item(iid).get('values', ())
                    pid_idx = cols.index('ProductID') if 'ProductID' in cols else 0
                    pidv = vals[pid_idx] if pid_idx < len(vals) else None
                    if pidv:
                        all_rows = read_sales(include_deleted=True)
                        found = next((r for r in all_rows if str(r.get('ProductID','')) == str(pidv)), None)
                        if found and found.get('id'):
                            ids.append(int(found.get('id')))
                except Exception:
                    pass
        if not ids:
            messagebox.showinfo('Nothing', 'No matching rows to delete')
            return

        try:
            import db as db
            any_done = False
            if choice is False:
                # Soft-delete all at once
                try:
                    db.mark_sale_deleted(ids)
                    any_done = True
                except Exception:
                    any_done = False
            else:
                # Void path: soft-delete then void per sale (ask per-sale for reversal and reason)
                for sid in ids:
                    try:
                        db.mark_sale_deleted([sid])
                        any_done = True
                        try:
                            create_rev = messagebox.askyesno('Reversal', f'Create reversal entry for sale id={sid}?', parent=win)
                        except Exception:
                            create_rev = False
                        try:
                            reason = simpledialog.askstring('Void Reason', f'Provide reason for voiding sale id={sid} (optional):', parent=win)
                        except Exception:
                            reason = None
                        try:
                            db.void_sale(sid, by=None, reason=reason, create_reversal=bool(create_rev))
                        except Exception:
                            pass
                    except Exception:
                        continue
            if any_done:
                refresh()
            return
        except Exception:
            # Fall back to CSV editing when DB path not available
            rows = read_sales()
            changed = False
            for r in rows:
                try:
                    if str(r.get('id')) in [str(x) for x in ids] or (r.get('ProductID') and str(r.get('ProductID')) in [str(x) for x in ids]):
                        r['Deleted'] = '1'
                        changed = True
                except Exception:
                    pass
            if changed:
                try:
                    write_sales(rows)
                except Exception:
                    pass
                refresh()

    def do_mark_returned():
        idx = get_selected_index()
        if idx is None:
            messagebox.showwarning('Select', 'Select a row first')
            return
        try:
            import db as db
            rows = [ _normalize_row_for_ui(r) for r in db.list_sales(include_deleted=True) ]
            rec = next((r for r in rows if r.get('id') == idx), None)
        except Exception:
            rec = None
        if not rec:
            messagebox.showerror('Error', 'Invalid selection or sale not found')
            return
        # Debug: print selection and record info
        try:
            print(f"[DEBUG] do_mark_returned selected id={idx} product_id={rec.get('product_id') or rec.get('ProductID')}")
        except Exception:
            pass
        # Helper to read either DB-style (snake_case) or UI-style (TitleCase) keys
        def _pick(*keys):
            for k in keys:
                try:
                    v = rec.get(k)
                except Exception:
                    v = None
                if v is not None and str(v).strip() != '':
                    return str(v).strip()
            return ''

        # Prevent duplicate returns for same product id
        existing = { (r.get('ProductID') or '').strip() for r in read_returns() }
        try:
            print(f"[DEBUG] existing returns PIDs count={len(existing)} sample={list(existing)[:5]}")
        except Exception:
            pass
        pid = _pick('product_id', 'ProductID')
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
            import db as db
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
                    import db as db
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

                # Write return directly into DB using normalized keys (support both DB and UI row shapes)
                import db as db
                # Use SaleCurrency for refund currency; fallback to default if missing
                refund_ccy = _pick('sale_currency', 'SaleCurrency') or ''
                if not refund_ccy:
                    try:
                        refund_ccy = db.get_default_sale_currency()
                    except Exception:
                        refund_ccy = ''

                # Build fields and insert using the normalized pick helper
                payload = {
                    'return_date': d,
                    'product_id': pid,
                    'sale_date': _pick('date', 'Date', 'sale_date', 'SaleDate'),
                    'category': _pick('category', 'Category'),
                    'subcategory': _pick('subcategory', 'Subcategory'),
                    'unit_price': _pick('selling_price', 'SellingPrice', 'unit_price', 'UnitPrice'),
                    'selling_price': _pick('selling_price', 'SellingPrice', 'unit_price', 'UnitPrice'),
                    'platform': _pick('platform', 'Platform'),
                    'refund_amount': float(refund),
                    'refund_currency': refund_ccy,
                    'restock': restock_final,
                    'reason': reason_var.get().strip(),
                    'doc_paths': doc_entry.get().strip(),
                }
                try:
                    print(f"[DEBUG] inserting return payload product_id={payload.get('product_id')} refund={payload.get('refund_amount')}")
                except Exception:
                    pass
                res = db.insert_return(payload)
                try:
                    print(f"[DEBUG] insert_return result={res}")
                except Exception:
                    pass
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
        try:
            import db as db
            rows = [ _normalize_row_for_ui(r) for r in db.list_sales(include_deleted=True) ]
            rec = next((r for r in rows if r.get('id') == idx), None)
        except Exception:
            rec = None
        if not rec:
            messagebox.showerror('Error', 'Invalid selection index')
            return
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
        # SellingPrice is stored per-unit; allow editing SellingPrice directly
        add_field('Selling Price (per unit):', 'SellingPrice')
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
                selling_price = float(entries['SellingPrice'].get().strip())
            except Exception:
                messagebox.showerror('Invalid selling price', 'Selling price must be a number')
                return
            platform = entries['Platform'].get().strip()
            pid = entries['ProductID'].get().strip()
            customer_id = entries['CustomerID'].get().strip()
            docp = entries['DocumentPath'].get().strip()

            # Persist changes via DB helper
            try:
                import db as db
                db.update_sale(idx, {
                    'date': d,
                    'category': cat,
                    'subcategory': sub,
                    'quantity': qty,
                    'selling_price': selling_price,
                    'platform': platform,
                    'product_id': pid,
                    'customer_id': customer_id,
                    'document_path': docp,
                })
            except Exception:
                # Fallback to CSV overwrite
                rows = read_sales()
                try:
                    found_i = next((i for i, r in enumerate(rows) if r.get('id') == idx), None)
                    if found_i is not None:
                        rows[found_i] = {
                            'Date': d,
                            'Category': cat,
                            'Subcategory': sub,
                            'Quantity': qty,
                            'SellingPrice': selling_price,
                            'Platform': platform,
                            'ProductID': pid,
                            'CustomerID': customer_id,
                            'DocumentPath': docp,
                        }
                        write_sales(rows)
                except Exception:
                    pass
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
        rec = next((r for r in rows if r.get('id') == idx), None)
        if not rec:
            messagebox.showerror('Error', 'Invalid selection index', parent=win)
            return
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
            # Prefer DB update
            try:
                import db as db
                db.update_sale(idx, {'document_path': format_docs(docs)})
            except Exception:
                rows2 = read_sales()
                # fallback to index-based update for CSV
                try:
                    if 0 <= idx < len(rows2):
                        rows2[idx]['DocumentPath'] = format_docs(docs)
                        write_sales(rows2)
                except Exception:
                    pass
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
        
        try:
            import db as db
            rows = [ _normalize_row_for_ui(r) for r in db.list_sales(include_deleted=True) ]
            rec = next((r for r in rows if r.get('id') == idx), None)
        except Exception:
            rec = None
        if not rec:
            messagebox.showerror('Error', 'Invalid selection or sale not found')
            return
        product_id = (rec.get('product_id') or rec.get('ProductID') or '').strip()
        if not product_id:
            messagebox.showwarning('No Product ID', 'This sale has no Product ID')
            return
        try:
            import db as db
            allocations = get_sale_batch_info(product_id)
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
                
                item_id = tree.insert('', 0, values=values)
                
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
    themed_button(secondary_frame, text='⬇️ Export CSV', variant='secondary',
              command=do_export_csv).pack(side=tk.LEFT, padx=4)
    themed_button(secondary_frame, text='↩️ Mark Returned', variant='secondary',
              command=do_mark_returned).pack(side=tk.LEFT, padx=(8, 4))
    themed_button(secondary_frame, text='🗑️ Delete', variant='danger',
              command=do_delete).pack(side=tk.LEFT, padx=4)
    def do_undelete():
        sel = tree.selection()
        if not sel:
            messagebox.showwarning('Select', 'Select at least one row first')
            return
        ids = []
        for iid in sel:
            try:
                ids.append(int(iid))
            except Exception:
                try:
                    vals = tree.item(iid).get('values', ())
                    pid_idx = cols.index('ProductID') if 'ProductID' in cols else 0
                    pidv = vals[pid_idx] if pid_idx < len(vals) else None
                    if pidv:
                        all_rows = read_sales(include_deleted=True)
                        found = next((r for r in all_rows if str(r.get('ProductID','')) == str(pidv)), None)
                        if found and found.get('id'):
                            ids.append(int(found.get('id')))
                except Exception:
                    pass
        if not ids:
            messagebox.showinfo('Nothing', 'No matching rows to undelete')
            return
        try:
            import db as db
            db.undelete_sales_by_ids(ids)
            refresh()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to undelete: {e}')

    themed_button(secondary_frame, text='♻️ Undelete', variant='primary',
              command=do_undelete).pack(side=tk.LEFT, padx=4)
    
    btn_frame.pack(fill='x', pady=8)

    # Bind filters after buttons defined
    return_combo.bind('<<ComboboxSelected>>', on_return_change)

    # Listen for <<ReturnUndone>> event to refresh sales view when a return is undone
    def on_return_undone(event=None):
        refresh()
    win.bind('<<ReturnUndone>>', on_return_undone)
