import tkinter as tk
from tkinter import ttk, messagebox
import py.db.db as db
from .theme import maximize_window, themed_button, ask_integer, stripe_treeview, apply_theme


def open_manage_product_codes_window(root):
    win = tk.Toplevel(root)
    win.title('Manage Product Codes')
    win.geometry('720x420')
    try:
        win.minsize(640, 360)
    except Exception:
        pass
    try:
        maximize_window(win)
    except Exception:
        pass
    # Apply theme for consistent look
    try:
        apply_theme(win)
    except Exception:
        pass

    cols = ['Category', 'Subcategory', 'CatCode', 'SubCode', 'NextSerial']
    tree = ttk.Treeview(win, columns=cols, show='headings')
    for c in cols:
        tree.heading(c, text=c)
        width = 140 if c not in ('CatCode', 'SubCode') else 100
        tree.column(c, width=width, anchor=tk.CENTER)
    tree.pack(expand=True, fill='both')

    # Column sorting helper
    sort_state = {}

    def _coerce_for_sort(col_name, value):
        v = '' if value is None else str(value)
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

    def load():
        for r in tree.get_children():
            tree.delete(r)
        # Ensure stripe tags are configured
        try:
            stripe_treeview(tree)
        except Exception:
            pass
        rows = db.get_all_product_codes()
        for idx, r in enumerate(rows):
            tree.insert('', tk.END, iid=str(idx), values=[
                r.get('category', ''),
                r.get('subcategory', ''),
                str(r.get('cat_code', '')).zfill(3),
                str(r.get('sub_code', '')).zfill(3),
                r.get('next_serial', 1),
            ])
        # Apply zebra striping across all rows
        try:
            stripe_treeview(tree)
        except Exception:
            pass

    def add_or_edit(existing=None):
        dlg = tk.Toplevel(win)
        dlg.title('Edit Codes' if existing else 'Add Codes')
        dlg.geometry('420x320')

        entries = {}

        def field(label, key, default=''):
            ttk.Label(dlg, text=label).pack(pady=4)
            e = ttk.Entry(dlg, width=36)
            e.insert(0, default)
            e.pack(pady=2)
            entries[key] = e

        field('Category', 'category', (existing or {}).get('category', ''))
        field('Subcategory', 'subcategory', (existing or {}).get('subcategory', ''))
        field('Category Code (3 digits)', 'cat_code', str((existing or {}).get('cat_code', '')).zfill(3))
        field('Subcategory Code (3 digits)', 'sub_code', str((existing or {}).get('sub_code', '')).zfill(3))
        field('Next Serial (>=1)', 'next_serial', str((existing or {}).get('next_serial', 1)))

        def save():
            cat = entries['category'].get().strip()
            sub = entries['subcategory'].get().strip()
            cat_code = entries['cat_code'].get().strip()
            sub_code = entries['sub_code'].get().strip()
            try:
                next_serial = int(entries['next_serial'].get().strip())
            except Exception:
                next_serial = 1
            if not cat:
                messagebox.showwarning('Missing', 'Category is required', parent=dlg)
                return
            if not (cat_code.isdigit() and 1 <= len(cat_code) <= 3):
                messagebox.showerror('Invalid', 'Category code must be 1-3 digits', parent=dlg)
                return
            if not (sub_code.isdigit() and 1 <= len(sub_code) <= 3):
                messagebox.showerror('Invalid', 'Subcategory code must be 1-3 digits', parent=dlg)
                return
            try:
                db.set_product_code(cat, sub, cat_code, sub_code, next_serial)
            except Exception as e:
                messagebox.showerror('Error', f'Failed to save: {e}', parent=dlg)
                return
            dlg.destroy()
            load()
        # Button row with Cancel and Save
        btns = ttk.Frame(dlg)
        btns.pack(fill='x', pady=8)
        themed_button(btns, text='Cancel', variant='secondary', command=dlg.destroy).pack(side=tk.LEFT)
        themed_button(btns, text='Save', variant='primary', command=save).pack(side=tk.RIGHT)

    def get_selected():
        sel = tree.selection()
        if not sel:
            return None
        vals = tree.item(sel[0], 'values')
        return {
            'category': vals[0],
            'subcategory': vals[1],
            'cat_code': vals[2],
            'sub_code': vals[3],
            'next_serial': int(vals[4]) if vals[4] else 1,
        }

    def delete_selected():
        item = get_selected()
        if not item:
            messagebox.showwarning('Select', 'Select a row first', parent=win)
            return
        if not messagebox.askyesno('Confirm', f"Delete mapping for {item['category']} / {item['subcategory']}?", parent=win):
            return
        try:
            db.delete_product_code(item['category'], item['subcategory'])
        except Exception as e:
            messagebox.showerror('Error', f'Failed to delete: {e}', parent=win)
            return
        load()

    def reset_serial():
        item = get_selected()
        if not item:
            messagebox.showwarning('Select', 'Select a row first', parent=win)
            return
        new_serial = ask_integer(win, 'Reset Serial', 'Enter new next serial (>=1):', minvalue=1)
        if new_serial is None:
            return
        try:
            db.update_next_serial(item['category'], item['subcategory'], new_serial)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to update serial: {e}', parent=win)
            return
        load()

    btns = ttk.Frame(win)
    themed_button(btns, text='Refresh', variant='secondary', command=load).pack(side=tk.LEFT, padx=6)
    themed_button(btns, text='Add', variant='primary', command=lambda: add_or_edit(None)).pack(side=tk.LEFT, padx=6)
    themed_button(btns, text='Edit', variant='success', command=lambda: add_or_edit(get_selected())).pack(side=tk.LEFT, padx=6)
    themed_button(btns, text='Reset Serial', variant='secondary', command=reset_serial).pack(side=tk.LEFT, padx=6)
    themed_button(btns, text='Delete', variant='danger', command=delete_selected).pack(side=tk.LEFT, padx=6)
    btns.pack(pady=8)

    load()
