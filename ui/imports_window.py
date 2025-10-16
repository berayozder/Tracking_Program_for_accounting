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

    # Use a scrollable canvas for the form so bottom buttons remain visible
    content_outer = ttk.Frame(window)
    content_outer.pack(fill='both', expand=True)

    canvas = tk.Canvas(content_outer)
    canvas.pack(side='left', fill='both', expand=True)
    vsb = ttk.Scrollbar(content_outer, orient='vertical', command=canvas.yview)
    vsb.pack(side='right', fill='y')
    canvas.configure(yscrollcommand=vsb.set)

    content_frame = ttk.Frame(canvas)
    # Put content_frame into canvas
    canvas.create_window((0,0), window=content_frame, anchor='nw')

    def _on_frame_configure(event=None):
        try:
            canvas.configure(scrollregion=canvas.bbox('all'))
        except Exception:
            pass

    content_frame.bind('<Configure>', _on_frame_configure)

    tk.Label(content_frame, text="Date (YYYY-MM-DD):").pack(pady=5)
    date_entry = tk.Entry(content_frame, width=25)
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
    ttk.Label(content_frame, text="Order lines (optional, add multiple category/subcategory lines):").pack(pady=(8,4))
    lines_frame = ttk.Frame(content_frame)
    lines_frame.pack(fill='x', padx=8)
    lines_tree = ttk.Treeview(lines_frame, columns=('category','subcategory','qty','price'), show='headings', height=4)
    for c in ('category','subcategory','qty','price'):
        lines_tree.heading(c, text=c.title())
        lines_tree.column(c, width=100)
    lines_tree.pack(side='left', fill='x', expand=True)
    lines_scroll = ttk.Scrollbar(lines_frame, orient='vertical', command=lines_tree.yview)
    lines_tree.configure(yscrollcommand=lines_scroll.set)
    lines_scroll.pack(side='right', fill='y')

    line_buttons = ttk.Frame(content_frame)
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
        # Insert the validated line at top so newest lines appear first
        try:
            lines_tree.insert('', 0, values=(c, s, q, p))
        except Exception:
            # fallback to append if insert at 0 fails for some themes
            try:
                lines_tree.insert('', 'end', values=(c, s, q, p))
            except Exception:
                pass

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

    tk.Label(content_frame, text="Ordered Price (per unit):").pack(pady=5)
    price_entry = tk.Entry(content_frame, width=20)
    price_entry.pack(pady=5)

    # Currency selection with default from settings
    try:
        import db.db as _db  # local to avoid circular during module import
        _default_ccy = _db.get_default_import_currency()
    except Exception:
        _default_ccy = 'USD'
    ttk.Label(content_frame, text="Currency:").pack(pady=4)
    currency_var = tk.StringVar(value=_default_ccy)
    cur_cb = ttk.Combobox(window, values=['USD','TRY','EUR','GBP'], textvariable=currency_var, state='readonly', width=10)
    cur_cb.pack(pady=(0,6))

    # Suggested FX (fetched) + manual override
    ttk.Label(content_frame, text="Suggested FX (to base currency):").pack(pady=(6,2))
    suggested_fx_var = tk.StringVar(value='')
    suggested_fx_label = ttk.Label(content_frame, textvariable=suggested_fx_var)
    suggested_fx_label.pack()

    ttk.Label(content_frame, text="Override FX (leave empty to accept suggested):").pack(pady=(6,2))
    fx_entry = tk.Entry(content_frame, width=20)
    fx_entry.pack(pady=(0,6))

    # Note: import-level expenses are captured via the Expenses screen now;
    # they are not requested on the Record Import window.

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

    tk.Label(content_frame, text="Quantity: ").pack(pady=5)
    qty_entry = tk.Entry(content_frame, width=20)
    qty_entry.pack(pady=5)

    tk.Label(content_frame, text="Supplier (optional): ").pack(pady=5)
    supplier_entry = tk.Entry(content_frame, width=40)
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

    tk.Label(content_frame, text="Notes: ").pack(pady=5)
    notes_entry = tk.Entry(content_frame, width=40)
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
                c = str(r.get('category') or '').strip()
                s = str(r.get('subcategory') or '').strip()
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

        # Product code prompting for category/subcategory is handled per-import-line below
        # (so multi-line imports can request codes for each unique category/subcategory pair).

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
                    ln_cat = str(vals[0]) if vals and len(vals) > 0 else ''
                    ln_sub = str(vals[1]) if vals and len(vals) > 1 else ''
                    ln_qty = float(vals[2])
                    ln_price = float(vals[3])
                    lines.append({'category': ln_cat, 'subcategory': ln_sub, 'ordered_price': ln_price, 'quantity': ln_qty})
                except Exception:
                    continue

            # If import has multiple lines, ensure product code mappings exist for each unique category/subcategory pair
            if lines:
                # collect unique (category, subcategory) pairs
                pairs = []
                seen = set()
                for l in lines:
                    key = ( str(l.get('category') or '').strip(), str(l.get('subcategory') or '').strip() )
                    if key not in seen:
                        seen.add(key)
                        pairs.append(key)

                # find which pairs are missing codes
                missing = []
                cat_code_map = {}
                for (ln_cat, ln_sub) in pairs:
                    try:
                        codes = db.get_product_code(ln_cat, ln_sub)
                    except Exception:
                        codes = None
                    if codes:
                        continue
                    # check if category already has a cat_code; cache results
                    existing_cat_code = cat_code_map.get(ln_cat)
                    if existing_cat_code is None:
                        try:
                            existing_cat_code = db.get_cat_code_for_category(ln_cat)
                        except Exception:
                            existing_cat_code = None
                        cat_code_map[ln_cat] = existing_cat_code

                    missing.append((ln_cat, ln_sub, existing_cat_code))

                if missing:
                    # present a compact dialog to collect all missing codes at once
                    def collect_codes_dialog(missing_pairs):
                        dlg = tk.Toplevel(window)
                        dlg.title('Enter missing product codes')
                        try:
                            dlg.minsize(520, 220)
                        except Exception:
                            pass
                        frm = ttk.Frame(dlg, padding=(8,6))
                        frm.pack(fill='both', expand=True)
                        # header
                        ttk.Label(frm, text="Enter 1-3 digit codes (will be zero-padded to 3).", wraplength=480).grid(row=0, column=0, columnspan=4, sticky='w', pady=(0,6))
                        entries = []
                        cat_vars = {}
                        # column headers
                        hdr_frame = ttk.Frame(frm)
                        hdr_frame.grid(row=1, column=0, columnspan=4, sticky='ew', pady=(0,4))
                        ttk.Label(hdr_frame, text='Category', width=24).grid(row=0, column=0, padx=4)
                        ttk.Label(hdr_frame, text='Subcategory', width=20).grid(row=0, column=1, padx=4)
                        ttk.Label(hdr_frame, text='Cat Code', width=8).grid(row=0, column=2, padx=4)
                        ttk.Label(hdr_frame, text='Sub Code', width=8).grid(row=0, column=3, padx=4)

                        # scrollable area
                        canvas2 = tk.Canvas(frm, height=160)
                        vsb2 = ttk.Scrollbar(frm, orient='vertical', command=canvas2.yview)
                        inner = ttk.Frame(canvas2)
                        canvas2.create_window((0,0), window=inner, anchor='nw')
                        canvas2.configure(yscrollcommand=vsb2.set)
                        canvas2.grid(row=2, column=0, columnspan=3, sticky='nsew')
                        vsb2.grid(row=2, column=3, sticky='ns')
                        frm.grid_rowconfigure(2, weight=1)
                        frm.grid_columnconfigure(0, weight=1)

                        def _on_cfg(e=None):
                            try:
                                canvas2.configure(scrollregion=canvas2.bbox('all'))
                            except Exception:
                                pass

                        inner.bind('<Configure>', _on_cfg)

                        r = 0
                        for (cval, sval, existing_cat_code) in missing_pairs:
                            ttk.Label(inner, text=cval, width=24, anchor='w').grid(row=r, column=0, padx=4, pady=2, sticky='w')
                            ttk.Label(inner, text=(sval or '-'), width=20, anchor='w').grid(row=r, column=1, padx=4, pady=2, sticky='w')
                            if existing_cat_code:
                                # show existing cat code read-only
                                ttk.Label(inner, text=str(existing_cat_code), width=8).grid(row=r, column=2, padx=4, pady=2)
                                sub_ent = tk.Entry(inner, width=6)
                                sub_ent.grid(row=r, column=3, padx=4, pady=2)
                                entries.append((cval, sval, existing_cat_code, None, sub_ent))
                            else:
                                # reuse the same StringVar/Entry for categories that appear multiple times
                                if cval not in cat_vars:
                                    var = tk.StringVar()
                                    cat_vars[cval] = var
                                    cat_ent = tk.Entry(inner, width=6, textvariable=var)
                                    cat_ent.grid(row=r, column=2, padx=4, pady=2)
                                else:
                                    var = cat_vars[cval]
                                    # display label bound to the same var so user sees the shared value
                                    ttk.Label(inner, textvariable=var, width=8).grid(row=r, column=2, padx=4, pady=2)
                                sub_ent = tk.Entry(inner, width=6)
                                sub_ent.grid(row=r, column=3, padx=4, pady=2)
                                entries.append((cval, sval, None, var, sub_ent))
                            r += 1

                        # action buttons
                        btns = ttk.Frame(dlg, padding=(6,6))
                        btns.pack(fill='x')
                        def on_cancel():
                            dlg.destroy()
                        def on_ok():
                            results = []
                            for item in entries:
                                cval, sval, existing_cat_code, cat_ent_or_var, sub_ent = item
                                if existing_cat_code:
                                    sub_code = sub_ent.get().strip()
                                    if not (sub_code.isdigit() and 1 <= len(sub_code) <= 3):
                                        messagebox.showerror('Invalid', f'Invalid subcategory code for {cval}/{sval or "-"}', parent=dlg)
                                        return
                                    results.append((cval, sval, existing_cat_code, sub_code))
                                else:
                                    # cat_ent_or_var is a StringVar in this case
                                    cat_code = (cat_ent_or_var.get() or '').strip()
                                    sub_code = (sub_ent.get() or '').strip()
                                    if not (cat_code.isdigit() and 1 <= len(cat_code) <= 3):
                                        messagebox.showerror('Invalid', f'Invalid category code for {cval}', parent=dlg)
                                        return
                                    if not (sub_code.isdigit() and 1 <= len(sub_code) <= 3):
                                        messagebox.showerror('Invalid', f'Invalid subcategory code for {cval}/{sval or "-"}', parent=dlg)
                                        return
                                    results.append((cval, sval, cat_code, sub_code))
                            dlg.results = results
                            dlg.destroy()

                        themed_button(btns, text='Cancel', variant='secondary', command=on_cancel).pack(side='left')
                        themed_button(btns, text='Save codes', variant='primary', command=on_ok).pack(side='right')
                        dlg.transient(window)
                        dlg.grab_set()
                        window.wait_window(dlg)
                        return getattr(dlg, 'results', None)

                    collected = collect_codes_dialog(missing)
                    if not collected:
                        # user cancelled
                        return

                    # persist collected codes
                    for (cval, sval, cat_code, sub_code) in collected:
                        # cat_code may already be an existing code or newly provided string
                        try:
                            db.set_product_code(cval, sval, cat_code, sub_code, next_serial=1)
                        except Exception as e:
                            messagebox.showerror('Error', f'Failed to save product codes: {e}')
                            return

            # Expenses are handled separately via the Expenses window; do not collect here.
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

    # Bottom action bar with fixed Save/Cancel buttons
    action_bar = ttk.Frame(window, padding=8)
    action_bar.pack(side='bottom', fill='x')
    themed_button(action_bar, text="Cancel", variant='secondary', command=window.destroy).pack(side='left')
    themed_button(action_bar, text="Save Import", variant='primary', command=save_import).pack(side='right')


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
