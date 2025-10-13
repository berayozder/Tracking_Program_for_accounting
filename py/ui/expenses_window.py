#expenses_window.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import db


def open_expenses_window(root):
    db.init_db(migrate_csv=False)

    window = tk.Toplevel(root)
    window.title("Record Expense")
    window.geometry("460x520")

    ttk.Label(window, text="Date (YYYY-MM-DD):").pack(pady=4)
    date_entry = ttk.Entry(window, width=25)
    date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
    date_entry.pack(pady=4)

    ttk.Label(window, text="Amount:").pack(pady=4)
    amount_entry = ttk.Entry(window, width=20)
    amount_entry.pack(pady=4)

    # Remove Description; add optional Document attachment
    ttk.Label(window, text='Attach Document (optional):').pack(pady=4)
    doc_frame = ttk.Frame(window)
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
    cb = ttk.Checkbutton(window, text="Import-related expense", variable=is_import_var)
    cb.pack(pady=6)

    ttk.Label(window, text="Link to Import (optional):").pack(pady=4)
    import_combo = ttk.Combobox(window, values=[], state='disabled')
    import_combo.pack(pady=4)

    import_preview = ttk.Label(window, text='')
    import_preview.pack(pady=2)

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

    tk.Label(window, text="Category (optional):").pack(pady=4)
    cat_entry = tk.Entry(window, width=40)
    cat_entry.pack(pady=4)
    cat_entry.bind('<KeyRelease>', show_cat_suggestions)

    tk.Label(window, text="Notes (optional):").pack(pady=4)
    notes_entry = tk.Entry(window, width=40)
    notes_entry.pack(pady=4)

    # populate imports list for linking
    def refresh_imports():
        rows = db.get_imports(limit=500)
        choices = []
        for r in rows:
            choices.append(f"{r.get('id')} - {r.get('date')} {r.get('category')}/{r.get('subcategory')} qty:{r.get('quantity')}")
        import_combo['values'] = choices
    refresh_imports()

    def on_import_toggle():
        if is_import_var.get():
            import_combo.config(state='readonly')
        else:
            import_combo.set('')
            import_combo.config(state='disabled')
            import_preview.config(text='')


    def on_import_select(evt=None):
        sel = import_combo.get()
        import_preview.config(text=sel)


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
        imp_sel = import_combo.get().strip()
        imp_id = None
        if imp_sel:
            try:
                imp_id = int(imp_sel.split(' - ', 1)[0])
            except Exception:
                imp_id = None
        cat = cat_entry.get().strip()
        notes = notes_entry.get().strip()

        try:
            db.add_expense(d, amt, is_imp, imp_id, cat, notes, document_path=document_path)
            messagebox.showinfo('Saved', 'Expense saved')
            window.destroy()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save expense: {e}')

    import_combo.bind('<<ComboboxSelected>>', on_import_select)
    is_import_var.trace_add('write', lambda *a: on_import_toggle())
    ttk.Button(window, text='Save Expense', command=save_expense).pack(pady=12)

