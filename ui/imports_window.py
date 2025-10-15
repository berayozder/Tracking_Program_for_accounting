import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import db.db as db
from .theme import apply_theme, maximize_window
from .theme import ask_string, themed_button


def ensure_db():
    # make sure DB is initialized
    db.init_db()


def open_imports_window(root):
    ensure_db()

    window = tk.Toplevel(root)
    window.title("Record Import")
    window.geometry("500x600")
    try:
        window.minsize(480, 540)
    except Exception:
        pass
    try:
        apply_theme(window)
    except Exception:
        pass
    try:
        maximize_window(window)
    except Exception:
        pass

    tk.Label(window, text="Date (YYYY-MM-DD):").pack(pady=5)
    date_entry = tk.Entry(window, width=25)
    date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
    date_entry.pack(pady=5)

    # --- Category / Subcategory (plain text entries) ---
    tk.Label(window, text="Category:").pack(pady=5)
    category_entry = tk.Entry(window, width=40)
    category_entry.pack(pady=5)

    tk.Label(window, text="Subcategory (optional):").pack(pady=5)
    subcategory_entry = tk.Entry(window, width=40)
    subcategory_entry.pack(pady=5)

    # --- Multi-line support: a small list of lines for this import/order ---
    ttk.Label(window, text="Order lines (optional, add multiple category/subcategory lines):").pack(pady=(8,4))
    lines_frame = ttk.Frame(window)
    lines_frame.pack(fill='x', padx=8)
    lines_tree = ttk.Treeview(lines_frame, columns=('category','subcategory','qty','price'), show='headings', height=4)
    for c in ('category','subcategory','qty','price'):
        lines_tree.heading(c, text=c.title())
        lines_tree.column(c, width=100)
    lines_tree.pack(side='left', fill='x', expand=True)
    lines_scroll = ttk.Scrollbar(lines_frame, orient='vertical', command=lines_tree.yview)
    lines_tree.configure(yscrollcommand=lines_scroll.set)
    lines_scroll.pack(side='right', fill='y')

    line_buttons = ttk.Frame(window)
    line_buttons.pack(fill='x', padx=8, pady=(4,8))

    def add_line():
        c = category_entry.get().strip()
        s = subcategory_entry.get().strip()
        p = price_entry.get().strip()
        q = qty_entry.get().strip()
        if not c or not p or not q:
            messagebox.showwarning('Missing line', 'Category, Price and Quantity are required to add a line.')
            return
        try:
            float(p); float(q)
        except Exception:
            messagebox.showerror('Invalid', 'Price and Quantity must be numbers.')
            return
        lines_tree.insert('', 'end', values=(c, s, q, p))

    def remove_line():
        sel = lines_tree.selection()
        if not sel:
            return
        for iid in sel:
            try:
                lines_tree.delete(iid)
            except Exception:
                pass

    themed_button(line_buttons, text='➕ Add Line', variant='primary', command=add_line).pack(side='left', padx=4)
    themed_button(line_buttons, text='➖ Remove Line', variant='secondary', command=remove_line).pack(side='left', padx=4)

    # Product name and id removed per user request

    tk.Label(window, text="Ordered Price (per unit):").pack(pady=5)
    price_entry = tk.Entry(window, width=20)
    price_entry.pack(pady=5)

    # Currency selection with default from settings
    try:
        import db.db as _db  # local to avoid circular during module import
        _default_ccy = _db.get_default_import_currency()
    except Exception:
        _default_ccy = 'USD'
    ttk.Label(window, text="Currency:").pack(pady=4)
    currency_var = tk.StringVar(value=_default_ccy)
    cur_cb = ttk.Combobox(window, values=['USD','TRY','EUR','GBP'], textvariable=currency_var, state='readonly', width=10)
    cur_cb.pack(pady=(0,6))

    # Suggested FX (fetched) + manual override
    ttk.Label(window, text="Suggested FX (to base currency):").pack(pady=(6,2))
    suggested_fx_var = tk.StringVar(value='')
    suggested_fx_label = ttk.Label(window, textvariable=suggested_fx_var)
    suggested_fx_label.pack()

    ttk.Label(window, text="Override FX (leave empty to accept suggested):").pack(pady=(6,2))
    fx_entry = tk.Entry(window, width=20)
    fx_entry.pack(pady=(0,6))

    def fetch_and_show_fx(event=None):
        d = date_entry.get().strip()
        c = (currency_var.get() or '').strip().upper()
        try:
            if not d or not c:
                suggested_fx_var.set('')
                return
            r = db.get_rate_to_base(d, c)
            if r is None:
                suggested_fx_var.set('n/a')
            else:
                suggested_fx_var.set(f"1 {c} = {r:.6f} {db.get_base_currency()}")
        except Exception:
            suggested_fx_var.set('n/a')

    # Fetch FX initially and when date/currency change
    fetch_and_show_fx()
    date_entry.bind('<FocusOut>', fetch_and_show_fx)
    cur_cb.bind('<<ComboboxSelected>>', fetch_and_show_fx)

    tk.Label(window, text="Quantity: ").pack(pady=5)
    qty_entry = tk.Entry(window, width=20)
    qty_entry.pack(pady=5)

    tk.Label(window, text="Supplier (optional): ").pack(pady=5)
    supplier_entry = tk.Entry(window, width=40)
    supplier_entry.pack(pady=5)

    # --- Supplier suggestions dropdown (like category/subcategory) ---
    supplier_dropdown = {"win": None}

    def load_supplier_names():
        try:
            return db.get_supplier_name_suggestions()
        except Exception:
            return []

    def _destroy_supplier_dropdown():
        if supplier_dropdown["win"]:
            try:
                supplier_dropdown["win"].destroy()
            except Exception:
                pass
            supplier_dropdown["win"] = None

    def pick_supplier(evt=None):
        win = supplier_dropdown.get("win")
        if not win:
            return
        lb = getattr(win, 'listbox', None)
        if not lb:
            _destroy_supplier_dropdown()
            return
        sel = lb.curselection()
        if sel:
            supplier_entry.delete(0, tk.END)
            supplier_entry.insert(0, lb.get(sel[0]))
        _destroy_supplier_dropdown()
        # move focus to Notes after picking supplier
        try:
            notes_entry.focus_set()
        except Exception:
            pass

    def show_supplier_suggestions(event=None):
        q = supplier_entry.get().strip().lower()
        names = load_supplier_names()
        matches = [n for n in names if q and q in n.lower()]
        if matches:
            # create dropdown if needed
            if not (supplier_dropdown["win"] and tk.Toplevel.winfo_exists(supplier_dropdown["win"])):
                win = tk.Toplevel(window)
                win.wm_overrideredirect(True)
                win.attributes("-topmost", True)
                lb = tk.Listbox(win, height=min(8, len(matches)), exportselection=False)
                lb.pack()
                # Bind selection and enter/double-click
                lb.bind("<<ListboxSelect>>", pick_supplier)
                lb.bind("<Return>", pick_supplier)
                lb.bind("<Double-Button-1>", pick_supplier)
                win.listbox = lb
                supplier_dropdown["win"] = win
            else:
                win = supplier_dropdown["win"]
                lb = win.listbox
            # Populate
            lb.delete(0, tk.END)
            for m in matches[:8]:
                lb.insert(tk.END, m)
            # position under the supplier entry
            try:
                x = window.winfo_rootx() + supplier_entry.winfo_x()
                y = window.winfo_rooty() + supplier_entry.winfo_y() + supplier_entry.winfo_height()
                win.geometry(f"+{x}+{y}")
                win.deiconify()
            except Exception:
                pass
        else:
            _destroy_supplier_dropdown()

    def supplier_entry_keydown(event):
        # If dropdown visible, Down arrow moves focus to it and selects first item
        if event.keysym == 'Down' and supplier_dropdown["win"] and tk.Toplevel.winfo_exists(supplier_dropdown["win"]):
            try:
                lb = supplier_dropdown["win"].listbox
                lb.focus_set()
                if lb.size() > 0:
                    lb.selection_clear(0, tk.END)
                    lb.selection_set(0)
                    lb.activate(0)
            except Exception:
                pass
            return "break"  # prevent default cursor move
        elif event.keysym == 'Escape':
            _destroy_supplier_dropdown()
            return "break"
        return None

    supplier_entry.bind('<KeyRelease>', show_supplier_suggestions)
    supplier_entry.bind('<KeyPress>', supplier_entry_keydown)
    # Hide dropdown when focus leaves supplier entry
    supplier_entry.bind('<FocusOut>', lambda e: _destroy_supplier_dropdown())

    tk.Label(window, text="Notes: ").pack(pady=5)
    notes_entry = tk.Entry(window, width=40)
    notes_entry.pack(pady=5)

    # --- Suggestion dropdown placeholders ---
    cat_dropdown = {"win": None}
    sub_dropdown = {"win": None}

    # helpers to collect suggestions from DB
    def load_suggestions():
        cats = set()
        subs = set()
        try:
            rows = db.get_imports(limit=10000)
            for r in rows:
                c = (r.get('category') or '').strip()
                s = (r.get('subcategory') or '').strip()
                if c:
                    cats.add(c)
                if s:
                    subs.add(s)
        except Exception:
            pass
        return sorted(cats), sorted(subs)

    def show_cat_suggestions(event=None):
        q = category_entry.get().strip().lower()
        cats, subs = load_suggestions()
        matches = [c for c in cats if q in c.lower()]
        if matches:
            # create dropdown if needed
            if not (cat_dropdown["win"] and tk.Toplevel.winfo_exists(cat_dropdown["win"])):
                win = tk.Toplevel(window)
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
            # position under the entry
            x = window.winfo_rootx() + category_entry.winfo_x()
            y = window.winfo_rooty() + category_entry.winfo_y() + category_entry.winfo_height()
            win.geometry(f"+{x}+{y}")
            win.deiconify()
        else:
            if cat_dropdown["win"]:
                try:
                    cat_dropdown["win"].destroy()
                except Exception:
                    pass
                cat_dropdown["win"] = None

    def show_sub_suggestions(event=None):
        q = subcategory_entry.get().strip().lower()
        cats, subs = load_suggestions()
        matches = [s for s in subs if q in s.lower()]
        if matches:
            if not (sub_dropdown["win"] and tk.Toplevel.winfo_exists(sub_dropdown["win"])):
                win = tk.Toplevel(window)
                win.wm_overrideredirect(True)
                win.attributes("-topmost", True)
                lb = tk.Listbox(win, height=min(8, len(matches)), exportselection=False)
                lb.pack()
                lb.bind("<<ListboxSelect>>", pick_sub)
                win.listbox = lb
                sub_dropdown["win"] = win
            else:
                win = sub_dropdown["win"]
                lb = win.listbox
            lb.delete(0, tk.END)
            for m in matches[:8]:
                lb.insert(tk.END, m)
            x = window.winfo_rootx() + subcategory_entry.winfo_x()
            y = window.winfo_rooty() + subcategory_entry.winfo_y() + subcategory_entry.winfo_height()
            win.geometry(f"+{x}+{y}")
            win.deiconify()
        else:
            if sub_dropdown["win"]:
                try:
                    sub_dropdown["win"].destroy()
                except Exception:
                    pass
                sub_dropdown["win"] = None

    def pick_cat(evt):
        lb = evt.widget
        sel = lb.curselection()
        if sel:
            category_entry.delete(0, tk.END)
            category_entry.insert(0, lb.get(sel[0]))
        if cat_dropdown["win"]:
            try:
                cat_dropdown["win"].destroy()
            except Exception:
                pass
            cat_dropdown["win"] = None
        # return focus to subcategory so user can continue filling the form
        try:
            subcategory_entry.focus_set()
        except Exception:
            pass

    def pick_sub(evt):
        lb = evt.widget
        sel = lb.curselection()
        if sel:
            subcategory_entry.delete(0, tk.END)
            subcategory_entry.insert(0, lb.get(sel[0]))
        if sub_dropdown["win"]:
            try:
                sub_dropdown["win"].destroy()
            except Exception:
                pass
            sub_dropdown["win"] = None
        # after selecting subcategory, move focus to Ordered Price
        try:
            price_entry.focus_set()
        except Exception:
            pass

    category_entry.bind("<KeyRelease>", show_cat_suggestions)
    subcategory_entry.bind("<KeyRelease>", show_sub_suggestions)


    def save_import():
        # read category/subcategory from text entries
        category = category_entry.get().strip()
        subcategory = subcategory_entry.get().strip()
        price = price_entry.get().strip()
        qty = qty_entry.get().strip()
        supplier = supplier_entry.get().strip()
        notes = notes_entry.get().strip()
        cur = (currency_var.get() or 'USD').strip().upper()

        # basic presence check (we still allow writing a row even if some fields are empty)
        if not (category and price and qty):
            messagebox.showwarning("Missing info", "Please provide at least Category, Ordered Price and Quantity.")
            return

        try:
            price = float(price)
            qty = float(qty)
        except ValueError:
            messagebox.showerror("Invalid input", "Price and Quantity must be numbers.")
            return

        # Always write a row to DB imports table; use provided date or default to today
        provided_date = date_entry.get().strip()
        try:
            # basic validation: ensure format is YYYY-MM-DD
            datetime.strptime(provided_date, '%Y-%m-%d')
            row_date = provided_date
        except Exception:
            row_date = datetime.now().strftime('%Y-%m-%d')

        # Ensure product code mapping exists for category/subcategory (for future product IDs)
        try:
            codes = db.get_product_code(category, subcategory)
        except Exception:
            codes = None
        if not codes:
            # Check if the category already has a cat_code; if so, only ask for subcategory code.
            existing_cat_code = None
            try:
                existing_cat_code = db.get_cat_code_for_category(category)
            except Exception:
                existing_cat_code = None

            if existing_cat_code:
                # Ask only for subcategory code
                while True:
                    sub_code = ask_string(window, "Subcategory Code", f"Enter 3-digit code for subcategory '{subcategory or '-'}' (e.g., 002):")
                    if sub_code is None:
                        if not messagebox.askyesno("Missing code", "Subcategory code is required to generate product IDs later. Cancel saving import?", parent=window):
                            continue
                        else:
                            return
                    sub_code = sub_code.strip()
                    if sub_code.isdigit() and 1 <= len(sub_code) <= 3:
                        break
                    else:
                        messagebox.showerror("Invalid code", "Please enter 1-3 digits (will be zero-padded to 3).", parent=window)
                try:
                    db.set_product_code(category, subcategory, existing_cat_code, sub_code, next_serial=1)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save product codes: {e}")
                    return
            else:
                # Ask for both category and subcategory codes
                while True:
                    cat_code = ask_string(window, "Category Code", f"Enter 3-digit code for category '{category}' (e.g., 001):")
                    if cat_code is None:
                        if not messagebox.askyesno("Missing codes", "Category/Subcategory codes are required to generate product IDs later. Cancel saving import?", parent=window):
                            continue
                        else:
                            return
                    cat_code = cat_code.strip()
                    if cat_code.isdigit() and 1 <= len(cat_code) <= 3:
                        break
                    else:
                        messagebox.showerror("Invalid code", "Please enter 1-3 digits (will be zero-padded to 3).", parent=window)

                while True:
                    sub_code = ask_string(window, "Subcategory Code", f"Enter 3-digit code for subcategory '{subcategory or '-'}' (e.g., 002):")
                    if sub_code is None:
                        if not messagebox.askyesno("Missing codes", "Category/Subcategory codes are required to generate product IDs later. Cancel saving import?", parent=window):
                            continue
                        else:
                            return
                    sub_code = sub_code.strip()
                    if sub_code.isdigit() and 1 <= len(sub_code) <= 3:
                        break
                    else:
                        messagebox.showerror("Invalid code", "Please enter 1-3 digits (will be zero-padded to 3).", parent=window)

                try:
                    db.set_product_code(category, subcategory, cat_code, sub_code, next_serial=1)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save product codes: {e}")
                    return

        # insert into DB (db.add_import will also update inventory and link/create supplier if provided)
        try:
            # read optional FX override
            fx_override_val = None
            try:
                v = fx_entry.get().strip()
                fx_override_val = float(v) if v else None
            except Exception:
                fx_override_val = None
            # Collect lines from tree, if any
            lines = []
            for iid in lines_tree.get_children():
                vals = lines_tree.item(iid).get('values', ())
                try:
                    ln_cat = vals[0]
                    ln_sub = vals[1]
                    ln_qty = float(vals[2])
                    ln_price = float(vals[3])
                    lines.append({'category': ln_cat, 'subcategory': ln_sub, 'ordered_price': ln_price, 'quantity': ln_qty})
                except Exception:
                    continue

            if lines:
                db.add_import(row_date, price, qty, supplier, notes, '', '', cur, fx_override_val, lines=lines)
            else:
                db.add_import(row_date, price, qty, supplier, notes, category, subcategory, cur, fx_override_val)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save import: {e}")
            return
        # We no longer update products by product name; imports only record the category/subcategory.
        messagebox.showinfo("Saved", "Import saved.")
        window.destroy()

    themed_button(window, text="Save Import", variant='primary', command=save_import).pack(pady=15)


def update_inventory(category, subcategory, quantity):
    try:
        db.update_inventory(category, subcategory, quantity)
    except Exception:
        pass

def rebuild_inventory_from_imports():
    try:
        db.rebuild_inventory_from_imports()
    except Exception:
        pass
