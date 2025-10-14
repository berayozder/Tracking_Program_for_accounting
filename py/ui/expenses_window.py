#expenses_window.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import py.db.db as db
from .theme import maximize_window


def open_expenses_window(root):
    db.init_db()

    window = tk.Toplevel(root)
    window.title("Record Expense")
    # Slightly reduced default height so action bar (Save) is visible on shorter screens
    window.geometry("620x680")
    try:
        window.minsize(560, 560)
    except Exception:
        pass
    try:
        maximize_window(window)
    except Exception:
        pass

    # Scrollable content area so bottom action bar is always visible
    content_container = ttk.Frame(window)
    content_container.pack(fill='both', expand=True)
    canvas = tk.Canvas(content_container, highlightthickness=0)
    scroll_y = ttk.Scrollbar(content_container, orient='vertical', command=canvas.yview)
    inner_frame = ttk.Frame(canvas)
    inner_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.create_window((0,0), window=inner_frame, anchor='nw')
    canvas.configure(yscrollcommand=scroll_y.set)
    canvas.pack(side=tk.LEFT, fill='both', expand=True)
    scroll_y.pack(side=tk.LEFT, fill='y')

    form_parent = inner_frame

    ttk.Label(form_parent, text="Date (YYYY-MM-DD):").pack(pady=4)
    date_entry = ttk.Entry(form_parent, width=25)
    date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
    date_entry.pack(pady=4)

    amount_row = ttk.Frame(form_parent)
    amount_row.pack(pady=4)
    ttk.Label(amount_row, text="Amount:").pack(side=tk.LEFT)
    amount_entry = ttk.Entry(amount_row, width=20)
    amount_entry.pack(side=tk.LEFT, padx=(6, 8))
    ttk.Label(amount_row, text='Currency:').pack(side=tk.LEFT)
    expense_ccy_var = tk.StringVar(value=(db.get_default_expense_currency() or db.get_base_currency() or 'USD'))
    expense_ccy = ttk.Combobox(amount_row, textvariable=expense_ccy_var, state='readonly', width=8,
                                values=['USD','TRY','EUR','GBP'])
    expense_ccy.pack(side=tk.LEFT, padx=(6, 0))

    # Remove Description; add optional Document attachment
    ttk.Label(form_parent, text='Attach Document (optional):').pack(pady=4)
    doc_frame = ttk.Frame(form_parent)
    doc_entry = ttk.Entry(doc_frame, width=36)
    doc_entry.pack(side=tk.LEFT, padx=(0, 6))
    def browse_doc():
        path = filedialog.askopenfilename(parent=window, title='Select document')
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

    is_import_var = tk.IntVar(value=0)
    cb = ttk.Checkbutton(form_parent, text="Import-related expense", variable=is_import_var)
    cb.pack(pady=6)

    # Import selection section will be created lazily only when checkbox is enabled
    import_section = None
    imports_frame = None
    filter_row = None
    imp_filter_var = tk.StringVar()
    imp_filter_entry = None
    canvas = None
    inner = None
    ctrl_row = None
    import_vars = []  # list of dicts: {'id': id, 'var': IntVar, 'cb': Checkbutton}
    selected_ids = set()  # persist selection across filtering

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
        q = cat_entry.get().strip().lower()
        cats = load_cat_suggestions()
        matches = [c for c in cats if q in c.lower()]
        if matches:
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
            x = window.winfo_rootx() + cat_entry.winfo_x()
            y = window.winfo_rooty() + cat_entry.winfo_y() + cat_entry.winfo_height()
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
            cat_entry.delete(0, tk.END)
            cat_entry.insert(0, lb.get(sel[0]))
        if cat_dropdown["win"]:
            try:
                cat_dropdown["win"].destroy()
            except Exception:
                pass
            cat_dropdown["win"] = None
        try:
            notes_entry.focus_set()
        except Exception:
            pass

    tk.Label(form_parent, text="Category (optional):").pack(pady=4)
    cat_entry = tk.Entry(form_parent, width=40)
    cat_entry.pack(pady=4)
    cat_entry.bind('<KeyRelease>', show_cat_suggestions)

    tk.Label(form_parent, text="Notes (optional):").pack(pady=4)
    notes_entry = tk.Entry(form_parent, width=40)
    notes_entry.pack(pady=4)

    # populate imports list for linking
    def _ensure_import_ui():
        nonlocal import_section, imports_frame, filter_row, imp_filter_entry, canvas, inner, ctrl_row
        if import_section and import_section.winfo_exists():
            return
        import_section = ttk.LabelFrame(form_parent, text="Link to Import(s) (optional):", padding=8, style='TLabelframe')
        import_section.pack(fill='both', expand=False, padx=4, pady=(4,0))
        imports_frame = ttk.Frame(import_section)
        imports_frame.pack(fill='both', expand=False)
        filter_row = ttk.Frame(import_section)
        ttk.Label(filter_row, text='Filter imports:').pack(side=tk.LEFT, padx=(0,6))
        imp_filter_entry = ttk.Entry(filter_row, textvariable=imp_filter_var, width=30)
        imp_filter_entry.pack(side=tk.LEFT, fill='x', expand=True)
        filter_row.pack(fill='x', pady=(0,4))
        canvas_height = 140
        canvas = tk.Canvas(imports_frame, height=canvas_height, highlightthickness=0)
        sb = ttk.Scrollbar(imports_frame, orient='vertical', command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0,0), window=inner, anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill='both', expand=True)
        sb.pack(side=tk.LEFT, fill='y')
        ctrl_row = ttk.Frame(import_section)
        ctrl_row.pack(fill='x', pady=(4,0))
        ttk.Button(ctrl_row, text='Select All', command=select_all_imports).pack(side=tk.LEFT, padx=(0,6))
        ttk.Button(ctrl_row, text='Clear', command=clear_all_imports).pack(side=tk.LEFT)
        imp_filter_entry.bind('<KeyRelease>', _on_imp_filter_change)

    def _destroy_import_ui():
        nonlocal import_section, imports_frame, filter_row, imp_filter_entry, canvas, inner, ctrl_row, import_vars
        if import_section and import_section.winfo_exists():
            try:
                import_section.destroy()
            except Exception:
                pass
        import_section = imports_frame = filter_row = imp_filter_entry = canvas = inner = ctrl_row = None
        import_vars = []

    def refresh_imports():
        nonlocal import_vars, selected_ids
        if not (import_section and import_section.winfo_exists()):
            return
        # capture current selections before rebuild
        if import_vars:
            try:
                selected_ids = {int(item['id']) for item in import_vars if int(item['var'].get()) == 1}
            except Exception:
                selected_ids = selected_ids
        for child in list(inner.winfo_children()):
            try:
                child.destroy()
            except Exception:
                pass
        import_vars = []
        rows = db.get_imports(limit=500)
        q = (imp_filter_var.get() or '').strip().lower()
        for r in rows:
            iid = r.get('id')
            label = f"{iid} - {r.get('date')} {r.get('category')}/{r.get('subcategory')} qty:{r.get('quantity')}"
            if q and q not in label.lower():
                continue
            var = tk.IntVar(value=0)
            cb = ttk.Checkbutton(inner, text=label, variable=var)
            cb.pack(anchor='w', fill='x')
            import_vars.append({'id': iid, 'var': var, 'cb': cb})
        # re-apply previous selections
        for item in import_vars:
            try:
                if int(item['id']) in selected_ids:
                    item['var'].set(1)
            except Exception:
                pass
        # re-apply enabled/disabled state based on toggle
        _set_checks(bool(is_import_var.get()))
    def _on_imp_filter_change(event=None):
        refresh_imports()

    def _set_checks(enabled: bool):
        for item in import_vars:
            try:
                if enabled:
                    # Enable by clearing the disabled state
                    item['cb'].state(['!disabled'])
                else:
                    # Disable by setting the disabled state
                    item['cb'].state(['disabled'])
            except Exception:
                try:
                    item['cb'].configure(state=('normal' if enabled else 'disabled'))
                except Exception:
                    pass

    def _set_import_section_visible(visible: bool):
        try:
            if visible:
                # Re-pack if currently hidden
                import_section.pack(fill='both', expand=False, padx=4, pady=(4,0))
            else:
                import_section.pack_forget()
        except Exception:
            pass

    def select_all_imports():
        for item in import_vars:
            try:
                item['var'].set(1)
            except Exception:
                pass

    def clear_all_imports():
        for item in import_vars:
            try:
                item['var'].set(0)
            except Exception:
                pass

    def on_import_toggle():
        enabled = bool(is_import_var.get())
        if enabled:
            _ensure_import_ui()
            refresh_imports()
            _set_checks(True)
        else:
            clear_all_imports()
            _destroy_import_ui()
    # initial state (unchecked -> no UI)
    on_import_toggle()

    def get_selected_import_ids():
        ids = []
        if not bool(is_import_var.get()):
            return ids
        for item in import_vars:
            try:
                if int(item['var'].get()) == 1:
                    ids.append(int(item['id']))
            except Exception:
                pass
        return ids


    def save_expense():
        d = date_entry.get().strip()
        try:
            datetime.strptime(d, '%Y-%m-%d')
        except Exception:
            messagebox.showerror('Invalid date', 'Please use YYYY-MM-DD')
            return
        amt = amount_entry.get().strip()
        try:
            amt = float(amt)
        except Exception:
            messagebox.showerror('Invalid amount', 'Amount must be a number')
            return
        document_path = doc_entry.get().strip()
        is_imp = bool(is_import_var.get())
        selected_import_ids = get_selected_import_ids()
        cat = cat_entry.get().strip()
        notes = notes_entry.get().strip()

        try:
            db.add_expense(d, amt, is_imp, None, cat, notes, document_path=document_path, import_ids=selected_import_ids, currency=expense_ccy_var.get())
            messagebox.showinfo('Saved', 'Expense saved')
            window.destroy()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save expense: {e}')

    is_import_var.trace_add('write', lambda *a: on_import_toggle())
    # Action bar (bottom) packed last so it never scrolls off
    action_bar = ttk.Frame(window)
    action_bar.pack(side=tk.BOTTOM, fill='x', pady=(4, 6))
    ttk.Separator(action_bar, orient='horizontal').pack(fill='x', side=tk.TOP, pady=(0,4))
    ttk.Button(action_bar, text='Save Expense', style='Primary.TButton', command=save_expense).pack(side=tk.RIGHT, padx=12)
    ttk.Button(action_bar, text='Cancel', command=window.destroy).pack(side=tk.RIGHT)

    # Ensure initial visibility/state respects checkbox (import section hidden until checked)
    on_import_toggle()

