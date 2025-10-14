import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import csv
from pathlib import Path
import db.db as db
import core.fx_rates as fx_rates

"""Record Sale UI writing to CSV.
CSV columns (canonical):
Date, Category, Subcategory, Quantity, UnitPrice, SellingPrice, Platform, ProductID, CustomerID, DocumentPath,
SaleFXToTRY, SellingPriceBase
"""

# Use the project data/sales.csv as per user request
SALES_CSV = Path(__file__).resolve().parents[2] / 'data' / 'sales.csv'
OLD_SALES_CSV = Path(__file__).resolve().parents[2] / 'sales.csv'


def ensure_sales_csv():
    # Ensure data directory exists and migrate old root sales.csv if present
    try:
        SALES_CSV.parent.mkdir(parents=True, exist_ok=True)
        if not SALES_CSV.exists() and OLD_SALES_CSV.exists():
            try:
                OLD_SALES_CSV.replace(SALES_CSV)
            except Exception:
                # fallback: copy content then remove old
                with OLD_SALES_CSV.open('r', newline='') as src, SALES_CSV.open('w', newline='') as dst:
                    dst.write(src.read())
                try:
                    OLD_SALES_CSV.unlink()
                except Exception:
                    pass
    except Exception:
        pass
    desired = ['Date', 'Category', 'Subcategory', 'Quantity', 'UnitPrice', 'SellingPrice', 'Platform', 'ProductID', 'CustomerID', 'DocumentPath', 'SaleFXToTRY', 'SellingPriceBase']
    if not SALES_CSV.exists():
        with SALES_CSV.open('w', newline='') as f:
            csv.writer(f).writerow(desired)
        return
    # migrate header if outdated
    try:
        with SALES_CSV.open('r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            with SALES_CSV.open('w', newline='') as f:
                csv.writer(f).writerow(desired)
            return
        header = rows[0]
        if header == desired:
            return
        data = rows[1:]
        # map existing rows to new header
        mapped = []
        for r in data:
            rowd = {header[i]: r[i] if i < len(r) else '' for i in range(len(header))}
            mapped.append({
                'Date': rowd.get('Date', ''),
                'Category': rowd.get('Category', ''),
                'Subcategory': rowd.get('Subcategory', ''),
                'Quantity': rowd.get('Quantity', ''),
                'UnitPrice': rowd.get('UnitPrice', ''),
                'SellingPrice': rowd.get('SellingPrice', ''),
                'Platform': rowd.get('Platform', ''),
                'ProductID': rowd.get('ProductID', ''),
                'CustomerID': rowd.get('CustomerID', ''),
                'DocumentPath': rowd.get('DocumentPath', ''),
                'SaleFXToTRY': rowd.get('SaleFXToTRY', ''),
                # Backward compatibility: migrate old SellingPriceUSD to SellingPriceBase
                'SellingPriceBase': rowd.get('SellingPriceBase', rowd.get('SellingPriceUSD', '')),
            })
        with SALES_CSV.open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=desired)
            w.writeheader()
            w.writerows(mapped)
    except Exception:
        # if migration fails silently, keep existing header; appends will still use desired order
        pass


def append_sale(row_dict):
    ensure_sales_csv()
    cols = ['Date', 'Category', 'Subcategory', 'Quantity', 'UnitPrice', 'SellingPrice', 'Platform', 'ProductID', 'CustomerID', 'DocumentPath', 'SaleFXToTRY', 'SellingPriceBase']
    with SALES_CSV.open('a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writerow({k: row_dict.get(k, '') for k in cols})


def open_sales_window(root):
    ensure_sales_csv()

    win = tk.Toplevel(root)
    win.title('💰 Record Sale')
    win.geometry('560x580')
    win.minsize(500, 520)
    try:
        from .theme import maximize_window
        maximize_window(win)
    except Exception:
        pass
    
    # Apply theme to window
    from .theme import apply_theme, themed_button, ask_string
    apply_theme(win)
    
    # Main container with padding
    container = ttk.Frame(win, padding=16)
    container.pack(fill='both', expand=True)
    # Build inventory category -> subcategory map from DB
    inv_rows = []
    try:
        inv_rows = db.get_inventory() or []
    except Exception:
        inv_rows = []
    cat_to_subs = {}
    for r in inv_rows:
        c = (r.get('category') or '').strip()
        s = (r.get('subcategory') or '').strip()
        if c:
            cat_to_subs.setdefault(c, set())
            if s:
                cat_to_subs[c].add(s)
    cat_list = sorted(cat_to_subs.keys())

    # Form section
    form_section = ttk.LabelFrame(container, text="📝 Sale Information", padding=16, style='TLabelframe')
    form_section.pack(fill='x', pady=(0, 16))
    
    # Date row
    date_frame = ttk.Frame(form_section)
    date_frame.pack(fill='x', pady=(0, 12))
    ttk.Label(date_frame, text='Date:', font=('', 9, 'bold')).pack(side='left', anchor='w')
    date_e = ttk.Entry(date_frame, width=20, font=('', 9))
    date_e.insert(0, datetime.now().strftime('%Y-%m-%d'))
    date_e.pack(side='right', anchor='e')
    
    # Options section
    options_frame = ttk.Frame(form_section)
    options_frame.pack(fill='x', pady=(0, 12))
    reduce_var = tk.BooleanVar(value=True)
    reduce_chk = ttk.Checkbutton(options_frame, text='✓ Reduce inventory by quantity', variable=reduce_var)
    reduce_chk.pack(anchor='w')


    # Category row
    cat_frame = ttk.Frame(form_section)
    cat_frame.pack(fill='x', pady=(0, 12))
    ttk.Label(cat_frame, text='Category:', font=('', 9, 'bold')).pack(side='left', anchor='w')
    cat_e = ttk.Combobox(cat_frame, values=cat_list, state='readonly' if cat_list else 'normal', 
                        width=30, font=('', 9))
    if cat_list:
        cat_e.set(cat_list[0])
    cat_e.pack(side='right', anchor='e')

    # Subcategory row
    sub_frame = ttk.Frame(form_section)
    sub_frame.pack(fill='x', pady=(0, 12))
    ttk.Label(sub_frame, text='Subcategory:', font=('', 9, 'bold')).pack(side='left', anchor='w')
    sub_e = ttk.Combobox(sub_frame, values=[], state='readonly', width=30, font=('', 9))
    sub_e.pack(side='right', anchor='e')

    def refresh_subs_for_cat(*args):
        c = cat_e.get().strip()
        subs = sorted(cat_to_subs.get(c, []))
        if subs:
            sub_e['values'] = subs
            sub_e.config(state='readonly')
            sub_e.set(subs[0])
        else:
            sub_e['values'] = []
            sub_e.set('')
            sub_e.config(state='normal')

    cat_e.bind('<<ComboboxSelected>>', refresh_subs_for_cat)
    refresh_subs_for_cat()

    # Quantity row
    qty_frame = ttk.Frame(form_section)
    qty_frame.pack(fill='x', pady=(0, 12))
    ttk.Label(qty_frame, text='Quantity:', font=('', 9, 'bold')).pack(side='left', anchor='w')
    qty_e = ttk.Entry(qty_frame, width=15, font=('', 9))
    qty_e.pack(side='right', anchor='e')

    # Unit Price row
    price_frame = ttk.Frame(form_section)
    price_frame.pack(fill='x', pady=(0, 12))
    ttk.Label(price_frame, text='Unit Price:', font=('', 9, 'bold')).pack(side='left', anchor='w')
    unit_e = ttk.Entry(price_frame, width=15, font=('', 9))
    unit_e.pack(side='right', anchor='e')

    # Sale Currency selector
    from .theme import apply_theme as _ap
    cur_frame = ttk.Frame(form_section)
    cur_frame.pack(fill='x', pady=(0, 12))
    ttk.Label(cur_frame, text='Sale Currency:', font=('', 9, 'bold')).pack(side='left', anchor='w')
    try:
        base_ccy = db.get_default_sale_currency()
    except Exception:
        base_ccy = 'TRY'
    sale_ccy_var = tk.StringVar(value=base_ccy)
    sale_ccy_cb = ttk.Combobox(cur_frame, values=['TRY','USD','EUR','GBP'], textvariable=sale_ccy_var, state='readonly', width=10)
    sale_ccy_cb.pack(side='right', anchor='e')

    # FX to TRY row (for USD analysis)
    fx_frame = ttk.Frame(form_section)
    fx_frame.pack(fill='x', pady=(0, 12))
    ttk.Label(fx_frame, text='FX rate to base (auto):', font=('', 9, 'bold')).pack(side='left', anchor='w')
    # Controls on the right: entry + Refresh
    right_fx = ttk.Frame(fx_frame)
    right_fx.pack(side='right', anchor='e')
    fx_e = ttk.Entry(right_fx, width=15, font=('', 9))
    fx_e.pack(side='left', padx=(0, 6))
    fx_status = ttk.Label(right_fx, text='', font=('', 8))
    fx_status.pack(side='right', padx=(6, 0))

    def _set_fx_value(val: float, source: str):
        fx_e.configure(state='normal')
        fx_e.delete(0, tk.END)
        fx_e.insert(0, f"{val:.4f}")
        fx_e.configure(state='readonly')
        try:
            fx_status.config(text=source)
        except Exception:
            pass

    def _set_fx_manual(message: str = 'Manual'):
        fx_e.configure(state='normal')
        # leave empty for user input
        try:
            fx_status.config(text=message)
        except Exception:
            pass

    def do_refresh_rate():
        d = date_e.get().strip()
        # If date is today, prefer fresh latest instead of cached
        today = datetime.now().strftime('%Y-%m-%d')
        if d == today:
            # fetch live for selected pair
            try:
                from_ccy = (sale_ccy_var.get() or 'TRY').upper()
                to_ccy = db.get_base_currency()
                # If using our helper, fallback to fx_rates for USD/TRY pairs
                r = db._get_rate_generic(d, from_ccy, to_ccy)
            except Exception:
                r = fx_rates.fetch_live_rate()
            if r is not None:
                # cache
                try:
                    if from_ccy == 'USD' and to_ccy == 'TRY':
                        fx_rates.set_rate(d, r)
                except Exception:
                    pass
                _set_fx_value(r, 'Live')
                return
        # Fallback to cached-or-fetch for other dates
        try:
            from_ccy = (sale_ccy_var.get() or 'TRY').upper()
            to_ccy = db.get_base_currency()
            r = db._get_rate_generic(d, from_ccy, to_ccy)
        except Exception:
            r = fx_rates.get_or_fetch_rate(d)
        if r is not None:
            _set_fx_value(r, 'Cached')
        else:
            _set_fx_manual('Offline - enter rate')

    refresh_btn = ttk.Button(right_fx, text='Refresh', command=do_refresh_rate)
    refresh_btn.pack(side='right')

    def auto_fill_fx():
        d = date_e.get().strip()
        today = datetime.now().strftime('%Y-%m-%d')
        # For today, try to force fresh value before reading cache
        if d == today:
            live = fx_rates.fetch_live_rate()
            if live is not None:
                fx_rates.set_rate(d, live)
                _set_fx_value(live, 'Live')
                return
        try:
            from_ccy = (sale_ccy_var.get() or 'TRY').upper()
            to_ccy = db.get_base_currency()
            r = db._get_rate_generic(d, from_ccy, to_ccy)
        except Exception:
            r = fx_rates.get_or_fetch_rate(d)
        if r is not None:
            _set_fx_value(r, 'Cached')
        else:
            # Allow manual entry if fetch failed
            _set_fx_manual('Offline - enter rate')

    # Auto-fetch when window opens and when date changes
    try:
        auto_fill_fx()
    except Exception:
        pass
    date_e.bind('<FocusOut>', lambda e: auto_fill_fx())
    date_e.bind('<Return>', lambda e: auto_fill_fx())

    # Platform row (Entry + auto-suggest dropdown)
    platform_frame = ttk.Frame(form_section)
    platform_frame.pack(fill='x', pady=(0, 0))
    ttk.Label(platform_frame, text='Platform:', font=('', 9, 'bold')).pack(side='left', anchor='w')
    def load_platform_suggestions():
        try:
            with SALES_CSV.open('r', newline='') as f:
                reader = csv.DictReader(f)
                vals = set()
                for row in reader:
                    v = (row.get('Platform') or '').strip()
                    if v:
                        vals.add(v)
                return sorted(vals)
        except Exception:
            return []

    platform_e = ttk.Entry(platform_frame, width=27, font=('', 9))
    platform_e.pack(side='right', anchor='e')

    plat_dropdown = {"win": None}

    def _destroy_plat_dropdown():
        if plat_dropdown["win"]:
            try:
                plat_dropdown["win"].destroy()
            except Exception:
                pass
            plat_dropdown["win"] = None

    def pick_platform(evt=None):
        winp = plat_dropdown.get("win")
        if not winp:
            return
        lb = getattr(winp, 'listbox', None)
        if not lb:
            _destroy_plat_dropdown()
            return
        sel = lb.curselection()
        if sel:
            platform_e.delete(0, tk.END)
            platform_e.insert(0, lb.get(sel[0]))
        _destroy_plat_dropdown()
        # After picking platform, move focus to customer (optional) or quantity
        try:
            customer_e.focus_set()
        except Exception:
            try:
                qty_e.focus_set()
            except Exception:
                pass

    def show_plat_suggestions(event=None):
        q = platform_e.get().strip().lower()
        names = load_platform_suggestions()
        # If query empty, show all; else filter
        matches = names if not q else [n for n in names if q in n.lower()]
        if matches:
            if not (plat_dropdown["win"] and tk.Toplevel.winfo_exists(plat_dropdown["win"])):
                winp = tk.Toplevel(win)
                winp.wm_overrideredirect(True)
                winp.attributes('-topmost', True)
                lb = tk.Listbox(winp, height=min(8, len(matches)), exportselection=False)
                lb.pack()
                lb.bind('<<ListboxSelect>>', pick_platform)
                lb.bind('<Return>', pick_platform)
                lb.bind('<Double-Button-1>', pick_platform)
                winp.listbox = lb
                plat_dropdown["win"] = winp
            else:
                winp = plat_dropdown["win"]
                lb = winp.listbox
            lb.delete(0, tk.END)
            for m in matches[:8]:
                lb.insert(tk.END, m)
            try:
                x = win.winfo_rootx() + platform_e.winfo_rootx() - win.winfo_x()
                y = win.winfo_rooty() + platform_e.winfo_rooty() - win.winfo_y() + platform_e.winfo_height()
                winp.geometry(f"+{x}+{y}")
                winp.deiconify()
            except Exception:
                pass
        else:
            _destroy_plat_dropdown()

    def platform_keydown(event):
        if event.keysym == 'Down' and plat_dropdown["win"] and tk.Toplevel.winfo_exists(plat_dropdown["win"]):
            try:
                lb = plat_dropdown["win"].listbox
                lb.focus_set()
                if lb.size() > 0:
                    lb.selection_clear(0, tk.END)
                    lb.selection_set(0)
                    lb.activate(0)
            except Exception:
                pass
            return 'break'
        elif event.keysym == 'Escape':
            _destroy_plat_dropdown()
            return 'break'
        return None

    # Show suggestions right away on focus and as the user types
    platform_e.bind('<FocusIn>', show_plat_suggestions)
    platform_e.bind('<KeyRelease>', show_plat_suggestions)
    platform_e.bind('<KeyPress>', platform_keydown)
    platform_e.bind('<FocusOut>', lambda e: _destroy_plat_dropdown())

    # Customer row (optional) with dropdown suggestions
    customer_frame = ttk.Frame(form_section)
    customer_frame.pack(fill='x', pady=(12, 0))
    ttk.Label(customer_frame, text='Customer (optional):', font=('', 9, 'bold')).pack(side='left', anchor='w')

    def load_customer_suggestions():
        try:
            return db.get_customer_name_suggestions()
        except Exception:
            return []

    customer_e = ttk.Entry(customer_frame, width=27, font=('', 9))
    customer_e.pack(side='right', anchor='e')

    cust_dropdown = {"win": None}

    def _destroy_cust_dropdown():
        if cust_dropdown["win"]:
            try:
                cust_dropdown["win"].destroy()
            except Exception:
                pass
            cust_dropdown["win"] = None

    def pick_customer(evt=None):
        winp = cust_dropdown.get("win")
        if not winp:
            return
        lb = getattr(winp, 'listbox', None)
        if not lb:
            _destroy_cust_dropdown()
            return
        sel = lb.curselection()
        if sel:
            customer_e.delete(0, tk.END)
            customer_e.insert(0, lb.get(sel[0]))
        _destroy_cust_dropdown()
        # After selecting customer, move focus to quantity
        try:
            qty_e.focus_set()
        except Exception:
            pass

    def show_cust_suggestions(event=None):
        q = customer_e.get().strip().lower()
        names = load_customer_suggestions()
        matches = [n for n in names if q and q in n.lower()]
        if matches:
            if not (cust_dropdown["win"] and tk.Toplevel.winfo_exists(cust_dropdown["win"])):
                winp = tk.Toplevel(win)
                winp.wm_overrideredirect(True)
                winp.attributes('-topmost', True)
                lb = tk.Listbox(winp, height=min(8, len(matches)), exportselection=False)
                lb.pack()
                lb.bind('<<ListboxSelect>>', pick_customer)
                lb.bind('<Return>', pick_customer)
                lb.bind('<Double-Button-1>', pick_customer)
                winp.listbox = lb
                cust_dropdown["win"] = winp
            else:
                winp = cust_dropdown["win"]
                lb = winp.listbox
            lb.delete(0, tk.END)
            for m in matches[:8]:
                lb.insert(tk.END, m)
            try:
                x = win.winfo_rootx() + customer_e.winfo_rootx() - win.winfo_x()
                y = win.winfo_rooty() + customer_e.winfo_rooty() - win.winfo_y() + customer_e.winfo_height()
                winp.geometry(f"+{x}+{y}")
                winp.deiconify()
            except Exception:
                pass
        else:
            _destroy_cust_dropdown()

    def customer_keydown(event):
        if event.keysym == 'Down' and cust_dropdown["win"] and tk.Toplevel.winfo_exists(cust_dropdown["win"]):
            try:
                lb = cust_dropdown["win"].listbox
                lb.focus_set()
                if lb.size() > 0:
                    lb.selection_clear(0, tk.END)
                    lb.selection_set(0)
                    lb.activate(0)
            except Exception:
                pass
            return 'break'
        elif event.keysym == 'Escape':
            _destroy_cust_dropdown()
            return 'break'
        return None

    customer_e.bind('<KeyRelease>', show_cust_suggestions)
    customer_e.bind('<KeyPress>', customer_keydown)
    customer_e.bind('<FocusOut>', lambda e: _destroy_cust_dropdown())

    # Product IDs are auto-generated; no manual entry widget

    def save_sale():
        d = date_e.get().strip()
        try:
            datetime.strptime(d, '%Y-%m-%d')
        except Exception:
            messagebox.showerror('Invalid date', 'Please use YYYY-MM-DD')
            return
        cat = cat_e.get().strip()
        if not cat:
            messagebox.showwarning('Missing', 'Category is required')
            return
        sub = sub_e.get().strip()
        if cat_list and cat not in cat_to_subs:
            if not messagebox.askyesno('Category not in inventory', 'Selected category is not in inventory. Continue?'):
                return
        if sub and cat_to_subs.get(cat) and sub not in cat_to_subs.get(cat):
            if not messagebox.askyesno('Subcategory not in inventory', 'Selected subcategory is not in inventory for this category. Continue?'):
                return
        try:
            qty = float(qty_e.get().strip())
        except Exception:
            messagebox.showerror('Invalid quantity', 'Quantity must be a number')
            return

        # Optionally check inventory and reduce quantity
        if reduce_var.get():
            try:
                inv_rows = db.get_inventory() or []
            except Exception:
                inv_rows = []
            # find matching inventory line
            match = None
            for r in inv_rows:
                rc = (r.get('category') or '').strip()
                rs = (r.get('subcategory') or '').strip()
                if rc == (cat or '') and rs == (sub or ''):
                    match = r
                    break
            current_qty = match.get('quantity') if match else None
            try:
                current_qty = float(current_qty) if current_qty is not None else None
            except Exception:
                current_qty = None

            # Confirm if resulting stock would be negative or if item not found
            if current_qty is None:
                proceed = messagebox.askyesno('Inventory not found', 'No matching inventory item found for this category/subcategory. Proceed and create/update inventory with negative or zero quantity?')
                if not proceed:
                    return
            else:
                if current_qty - qty < 0:
                    proceed = messagebox.askyesno('Low stock warning', f'This sale would reduce stock below zero (current: {current_qty}, sale: {qty}). Proceed anyway?')
                    if not proceed:
                        return
        try:
            unit = float(unit_e.get().strip())
        except Exception:
            messagebox.showerror('Invalid unit price', 'Unit price must be a number')
            return
        # FX to TRY validation
        try:
            fx_text = (fx_e.get() or '').strip()
            fx = float(fx_text)
        except Exception:
            # Try autofetch if not available
            try:
                from_ccy = (sale_ccy_var.get() or 'TRY').upper()
                to_ccy = db.get_base_currency()
                r = db._get_rate_generic(d, from_ccy, to_ccy)
            except Exception:
                r = fx_rates.get_or_fetch_rate(d)
            if r is None:
                messagebox.showerror('FX unavailable', 'Could not fetch FX rate for this date. Please try again later or enter manually.')
                return
            fx = float(r)
            fx_e.configure(state='normal')
            fx_e.delete(0, tk.END)
            fx_e.insert(0, f"{fx:.4f}")
            fx_e.configure(state='readonly')
        if fx <= 0:
            messagebox.showerror('Invalid FX', 'FX rate must be greater than 0')
            return
        platform = platform_e.get().strip()
        # Cache FX for this date if known USD/TRY pair
        try:
            from_ccy = (sale_ccy_var.get() or 'TRY').upper()
            to_ccy = db.get_base_currency()
            if from_ccy == 'USD' and to_ccy == 'TRY':
                fx_rates.upsert_rate(d, fx)
        except Exception:
            pass

        # Handle customer (optional)
        customer_name = customer_e.get().strip()
        customer_id = None
        if customer_name:
            try:
                # Find existing customer or create new one
                customer_id = db.find_or_create_customer(customer_name)
            except Exception as e:
                messagebox.showwarning('Customer Error', f'Could not process customer: {e}')
                # Continue without customer

            # Robust fallback: if a name was provided but no ID returned, explicitly create the customer
            if not customer_id:
                try:
                    customer_id = db.add_customer(customer_name)
                except Exception as e:
                    # As a last resort, proceed without linking the sale to a customer
                    messagebox.showwarning('Customer Warning', f"Customer couldn't be created automatically: {e}. The sale will be saved without linking to a customer.")

        # Generate product IDs based on category/subcategory codes and quantity
        product_ids = []
        # For ID generation, quantity must be a whole number
        if not float(qty).is_integer() or qty <= 0:
            messagebox.showerror('Invalid quantity', 'Quantity must be a positive whole number to generate product IDs.')
            return
        count = int(qty)
        # Use sale date's year for 2-digit prefix
        try:
            yy = datetime.strptime(d, '%Y-%m-%d').strftime('%y')
        except Exception:
            yy = datetime.now().strftime('%y')
        try:
            product_ids = db.generate_product_ids(cat, sub, count, year_prefix=yy)
        except Exception:
            product_ids = []
        if not product_ids:
            # No mapping exists; ask user to provide codes now
            if not messagebox.askyesno('Missing codes', 'No product code mapping exists for this category/subcategory. Define codes now?'):
                return
            # ask codes
            while True:
                cat_code = ask_string(win, 'Category Code', f"Enter 3-digit code for category '{cat}' (e.g., 001):")
                if cat_code is None:
                    if not messagebox.askyesno('Cancel?', 'Codes are required to generate product IDs. Cancel this sale?'):
                        continue
                    return
                cat_code = (cat_code or '').strip()
                if cat_code.isdigit() and 1 <= len(cat_code) <= 3:
                    break
                messagebox.showerror('Invalid code', 'Please enter 1-3 digits (will be zero-padded to 3).')
            while True:
                sub_code = ask_string(win, 'Subcategory Code', f"Enter 3-digit code for subcategory '{sub or '-'}' (e.g., 002):")
                if sub_code is None:
                    if not messagebox.askyesno('Cancel?', 'Codes are required to generate product IDs. Cancel this sale?'):
                        continue
                    return
                sub_code = (sub_code or '').strip()
                if sub_code.isdigit() and 1 <= len(sub_code) <= 3:
                    break
                messagebox.showerror('Invalid code', 'Please enter 1-3 digits (will be zero-padded to 3).')
            try:
                db.set_product_code(cat, sub, cat_code, sub_code, next_serial=1)
                product_ids = db.generate_product_ids(cat, sub, count, year_prefix=yy)
            except Exception as e:
                messagebox.showerror('Error', f'Failed to set/generate product codes: {e}')
                return
        # =====================================================================================
        # BATCH TRACKING: Allocate each sold item to batches using FIFO for cost tracking
        # =====================================================================================
        batch_allocations = []
        for pid in product_ids:
            # Allocate this individual item (quantity=1) to batches
            # Convert entered unit price to base currency using selected sale currency
            from_ccy = (sale_ccy_var.get() or 'TRY').upper()
            base_ccy = db.get_base_currency()
            unit_in_base = unit
            if from_ccy != (base_ccy or '').upper():
                try:
                    conv = db.convert_amount(d, unit, from_ccy, base_ccy)
                    if conv is not None:
                        unit_in_base = conv
                except Exception:
                    pass
            allocations = db.allocate_sale_to_batches(pid, d, cat, sub, 1, unit_in_base)
            batch_allocations.extend(allocations)
            
            # Write sale record (same as before)
            # SellingPriceBase holds the unit price in base currency
            try:
                usd_unit = unit_in_base
            except Exception:
                usd_unit = unit / fx
            append_sale({
                'Date': d,
                'Category': cat,
                'Subcategory': sub,
                'Quantity': 1,
                'UnitPrice': unit,
                'SellingPrice': unit,
                'Platform': platform,
                'ProductID': pid,
                'CustomerID': customer_id or '',
                'DocumentPath': '',
                'SaleFXToTRY': fx,
                'SellingPriceBase': usd_unit,
            })

        # Apply inventory reduction after saving sale (batch system handles this automatically)
        if reduce_var.get():
            try:
                db.update_inventory(cat, sub, -qty)
            except Exception as e:
                messagebox.showwarning('Inventory update failed', f'Failed to update inventory: {e}')
        
        # Show batch allocation summary to user
        if batch_allocations:
            total_cost = sum(alloc['total_cost'] for alloc in batch_allocations)
            total_profit = sum(alloc['total_profit'] for alloc in batch_allocations)
            batches_used = len(set(alloc['batch_id'] for alloc in batch_allocations if alloc['batch_id']))
            shortage_qty = sum(alloc['quantity_allocated'] for alloc in batch_allocations if alloc['batch_id'] is None)
            
            summary_msg = f"✅ Sale recorded with batch tracking:\n"
            summary_msg += f"📊 Items sold: {count}\n"
            summary_msg += f"💰 Total revenue: ${count * unit:.2f}\n"
            summary_msg += f"💸 Total cost basis: ${total_cost:.2f}\n"
            summary_msg += f"📈 Total profit: ${total_profit:.2f}\n"
            summary_msg += f"📦 Batches used: {batches_used}"
            
            if shortage_qty > 0:
                summary_msg += f"\n⚠️  Inventory shortage: {shortage_qty} items (zero cost basis)"
            
            if product_ids:
                if len(product_ids) == 1:
                    summary_msg += f"\n🏷️  Product ID: {product_ids[0]}"
                else:
                    summary_msg += f"\n🏷️  Product IDs: {product_ids[0]} to {product_ids[-1]}"
            
            messagebox.showinfo('Sale Completed with Batch Tracking', summary_msg)
        else:
            # Fallback: show simple confirmation if no batch allocations
            if product_ids:
                if len(product_ids) == 1:
                    msg = f"Sale recorded. Product ID: {product_ids[0]}"
                else:
                    msg = f"Sale recorded. First: {product_ids[0]}  Last: {product_ids[-1]}  (Total: {len(product_ids)})"
            else:
                msg = 'Sale recorded'
            messagebox.showinfo('Saved', msg)
        
        win.destroy()

    # Action buttons
    button_frame = ttk.Frame(container)
    button_frame.pack(fill='x', pady=(16, 0))
    
    themed_button(button_frame, text='Cancel', variant='secondary', command=win.destroy).pack(side='left')
    themed_button(button_frame, text='💰 Save Sale', variant='success', command=save_sale).pack(side='right')
