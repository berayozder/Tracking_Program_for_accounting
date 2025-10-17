import tkinter as tk
from tkinter import ttk, messagebox
import db as db
from .theme import stripe_treeview, apply_theme, maximize_window, themed_button


def open_suppliers_window(root):
    """Supplier Management Window (CSV-backed)."""
    win = tk.Toplevel(root)
    win.title('🏭 Supplier Management')
    win.geometry('900x600')
    win.minsize(800, 500)
    try:
        maximize_window(win)
    except Exception:
        pass

    apply_theme(win)

    container = ttk.Frame(win, padding=16)
    container.pack(fill='both', expand=True)

    # Title
    title_frame = ttk.Frame(container)
    title_frame.pack(fill='x', pady=(0, 12))
    ttk.Label(title_frame, text='🏭 Supplier Management', font=('', 14, 'bold')).pack(anchor='w')
    stats_label = ttk.Label(title_frame, text='Loading suppliers...', font=('', 9))
    stats_label.pack(anchor='w', pady=(4, 0))

    # Search
    filter_frame = ttk.LabelFrame(container, text='🔍 Search & Filters', padding=8)
    filter_frame.pack(fill='x', pady=(0, 12))
    search_var = tk.StringVar()
    ttk.Label(filter_frame, text='Search:').pack(side='left', padx=(0, 8))
    search_entry = ttk.Entry(filter_frame, textvariable=search_var, width=30)
    search_entry.pack(side='left', padx=(0, 16))
    search_var.trace('w', lambda *args: populate_tree())

    # Table
    table_frame = ttk.Frame(container)
    table_frame.pack(fill='both', expand=True, pady=(0, 12))
    cols = ['Supplier ID', 'Name', 'Email', 'Phone', 'Address', 'Payment Terms', 'Imports', 'Total Purchases', 'Last Purchase']
    tree = ttk.Treeview(table_frame, columns=cols, show='headings', style='Treeview')
    col_conf = {
        'Supplier ID': {'width': 90, 'anchor': 'center'},
        'Name': {'width': 180, 'anchor': 'w'},
        'Email': {'width': 180, 'anchor': 'w'},
        'Phone': {'width': 120, 'anchor': 'w'},
        'Address': {'width': 200, 'anchor': 'w'},
        'Payment Terms': {'width': 140, 'anchor': 'w'},
        'Imports': {'width': 70, 'anchor': 'e'},
        'Total Purchases': {'width': 120, 'anchor': 'e'},
        'Last Purchase': {'width': 100, 'anchor': 'center'},
    }
    for c in cols:
        cc = col_conf.get(c, {'width': 100, 'anchor': 'w'})
        tree.heading(c, text=c, anchor=cc['anchor'])
        tree.column(c, width=cc['width'], anchor=cc['anchor'], minwidth=50)

    v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
    h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
    tree.grid(row=0, column=0, sticky='nsew')
    v_scroll.grid(row=0, column=1, sticky='ns')
    h_scroll.grid(row=1, column=0, sticky='ew')
    table_frame.columnconfigure(0, weight=1)
    table_frame.rowconfigure(0, weight=1)

    def get_selected_supplier():
        sel = tree.selection()
        if not sel:
            return None
        sid = tree.item(sel[0])['values'][0]
        for s in db.read_suppliers():
            if (s.get('supplier_id', '') or '').strip() == sid:
                return s
        return None

    def populate_tree():
        for i in tree.get_children():
            tree.delete(i)
        # Ensure tag styles (odd/even and states) are configured; safe when tree is empty
        try:
            stripe_treeview(tree)
        except Exception:
            pass
        try:
            suppliers = db.read_suppliers()
            q = search_var.get().lower().strip()
            count = 0
            total = 0.0
            for s in suppliers:
                if q:
                    packed = f"{s.get('name','')} {s.get('email','')} {s.get('phone','')}`".lower()
                    if q not in packed:
                        continue
                summary = db.get_supplier_purchases_summary(s.get('supplier_id',''))
                total += summary['total_purchases']
                values = [
                    s.get('supplier_id',''),
                    s.get('name',''),
                    s.get('email',''),
                    s.get('phone',''),
                    s.get('address',''),
                    s.get('payment_terms',''),
                    summary['import_count'],
                    f"${summary['total_purchases']:.2f}",
                    summary['last_purchase'] or '',
                ]
                item_id = tree.insert('', 0, values=values)
                count += 1
                # Color by activity
                if summary['import_count'] == 0:
                    stripe_treeview(tree, item_id, 'danger')
                elif summary['total_purchases'] > 10000:
                    stripe_treeview(tree, item_id, 'success')
                elif summary['total_purchases'] > 3000:
                    stripe_treeview(tree, item_id, 'warning')
            # Apply zebra striping to all rows, preserving any state tags
            try:
                children = tree.get_children('')
                for idx, iid in enumerate(children):
                    existing = tree.item(iid, 'tags') or ()
                    odd_even = 'oddrow' if idx % 2 else 'evenrow'
                    # Put odd/even first so state tags can override if needed
                    new_tags = (odd_even,) + tuple(t for t in existing if t not in ('oddrow','evenrow'))
                    tree.item(iid, tags=new_tags)
            except Exception:
                pass
            stats_label.configure(text=f"Showing {count} suppliers  |  Total Purchases: ${total:.2f}")
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load suppliers: {e}')

    def do_add_supplier():
        dlg = tk.Toplevel(win)
        dlg.title('➕ Add Supplier')
        dlg.geometry('480x420')
        dlg.resizable(False, False)
        dlg.transient(win)
        dlg.grab_set()
        apply_theme(dlg)

        frm = ttk.Frame(dlg, padding=16)
        frm.pack(fill='both', expand=True)
        ttk.Label(frm, text='➕ Add Supplier', font=('', 12, 'bold')).pack(anchor='w', pady=(0, 12))

        entries = {}
        def add_row(label, key):
            row = ttk.Frame(frm)
            row.pack(fill='x', pady=4)
            ttk.Label(row, text=f'{label}:', width=16).pack(side='left')
            e = ttk.Entry(row)
            e.pack(side='right', fill='x', expand=True)
            entries[key] = e
        add_row('Name*', 'name')
        add_row('Email', 'email')
        add_row('Phone', 'phone')
        add_row('Address', 'address')
        add_row('Payment Terms', 'payment_terms')
        add_row('Notes', 'notes')

        def save():
            name = entries['name'].get().strip()
            if not name:
                messagebox.showwarning('Missing', 'Name is required', parent=dlg)
                return
            sid = db.add_supplier(
                name=name,
                email=entries['email'].get().strip(),
                phone=entries['phone'].get().strip(),
                address=entries['address'].get().strip(),
                payment_terms=entries['payment_terms'].get().strip(),
                notes=entries['notes'].get().strip(),
            )
            messagebox.showinfo('Success', f'Supplier created: {sid}', parent=dlg)
            dlg.destroy()
            populate_tree()

        btns = ttk.Frame(frm)
        btns.pack(fill='x', pady=(12, 0))
        themed_button(btns, text='Cancel', variant='secondary', command=dlg.destroy).pack(side='left')
        themed_button(btns, text='Save Supplier', variant='primary', command=save).pack(side='right')

    def do_edit_supplier():
        s = get_selected_supplier()
        if not s:
            messagebox.showwarning('Select', 'Select a supplier to edit')
            return
        dlg = tk.Toplevel(win)
        dlg.title(f"✏️ Edit Supplier: {s.get('name','')}")
        dlg.geometry('520x440')
        dlg.resizable(False, False)
        dlg.transient(win)
        dlg.grab_set()
        apply_theme(dlg)

        frm = ttk.Frame(dlg, padding=16)
        frm.pack(fill='both', expand=True)
        ttk.Label(frm, text=f"✏️ Edit Supplier: {s.get('name','')}", font=('', 12, 'bold')).pack(anchor='w', pady=(0, 8))

        entries = {}
        def add_row(label, key, val=''):
            row = ttk.Frame(frm)
            row.pack(fill='x', pady=4)
            ttk.Label(row, text=f'{label}:', width=16).pack(side='left')
            e = ttk.Entry(row)
            e.insert(0, str(val))
            e.pack(side='right', fill='x', expand=True)
            entries[key] = e
        add_row('Name*', 'name', s.get('name',''))
        add_row('Email', 'email', s.get('email',''))
        add_row('Phone', 'phone', s.get('phone',''))
        add_row('Address', 'address', s.get('address',''))
        add_row('Payment Terms', 'payment_terms', s.get('payment_terms',''))
        add_row('Notes', 'notes', s.get('notes',''))

        def save():
            name = entries['name'].get().strip()
            if not name:
                messagebox.showwarning('Missing', 'Name is required', parent=dlg)
                return
            ok = db.edit_supplier(
                supplier_id=s.get('supplier_id',''),
                name=name,
                email=entries['email'].get().strip(),
                phone=entries['phone'].get().strip(),
                address=entries['address'].get().strip(),
                payment_terms=entries['payment_terms'].get().strip(),
                notes=entries['notes'].get().strip(),
            )
            if ok:
                messagebox.showinfo('Success', 'Supplier updated', parent=dlg)
                dlg.destroy()
                populate_tree()
            else:
                messagebox.showerror('Error', 'Failed to update supplier', parent=dlg)

        btns = ttk.Frame(frm)
        btns.pack(fill='x', pady=(12, 0))
        themed_button(btns, text='Cancel', variant='secondary', command=dlg.destroy).pack(side='left')
        themed_button(btns, text='Save Changes', variant='primary', command=save).pack(side='right')

    def do_delete_supplier():
        s = get_selected_supplier()
        if not s:
            messagebox.showwarning('Select', 'Select a supplier to delete')
            return
        # If supplier has imports, warn but allow (imports keep supplier_id/name text)
        summary = db.get_supplier_purchases_summary(s.get('supplier_id',''))
        if summary['import_count'] > 0:
            if not messagebox.askyesno('Confirm Delete',
                f"Supplier has {summary['import_count']} imports totaling ${summary['total_purchases']:.2f}.\n\n"
                "Deleting will not change existing import rows. Proceed?"):
                return
        if db.delete_supplier(s.get('supplier_id','')):
            messagebox.showinfo('Deleted', 'Supplier deleted')
            populate_tree()
        else:
            messagebox.showerror('Error', 'Failed to delete supplier')

    # Actions
    btn_row = ttk.Frame(container)
    btn_row.pack(fill='x')
    left = ttk.Frame(btn_row)
    left.pack(side='left', fill='x', expand=True)
    right = ttk.Frame(btn_row)
    right.pack(side='right')
    themed_button(left, text='➕ Add Supplier', variant='primary', command=do_add_supplier).pack(side='left', padx=(0, 8))
    themed_button(left, text='✏️ Edit Supplier', variant='success', command=do_edit_supplier).pack(side='left', padx=4)
    themed_button(left, text='🔄 Refresh', variant='primary', command=populate_tree).pack(side='left', padx=4)
    themed_button(right, text='🗑️ Delete Supplier', variant='danger', command=do_delete_supplier).pack(side='left', padx=4)
    themed_button(right, text='Close', variant='secondary', command=win.destroy).pack(side='left', padx=(8, 0))

    populate_tree()
