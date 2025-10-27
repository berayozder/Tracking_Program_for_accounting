import tkinter as tk
from tkinter import ttk, messagebox
import db as db
from .theme import stripe_treeview, maximize_window, themed_button

def open_customers_window(root):
    import csv
    def do_export_csv():
        file_path = tk.filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
            title='Export Customers to CSV'
        )
        if not file_path:
            return
        columns = [tree.heading(col)['text'] for col in tree['columns']]
        data = []
        for iid in tree.get_children():
            values = tree.item(iid)['values']
            data.append(values)
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(data)
            tk.messagebox.showinfo('Exported', f'Customers exported to {file_path}')
        except Exception as e:
            tk.messagebox.showerror('Error', f'Failed to export CSV: {e}')
    """
    Customer Management Window
    Shows all customers with their details and allows editing contact information
    """
    win = tk.Toplevel(root)
    try:
        maximize_window(win)
    except Exception:
        pass
    win.title('👥 Customer Management')
    win.geometry('900x600')
    win.minsize(800, 500)
    
    # Apply theme to window
    from .theme import apply_theme
    apply_theme(win)
    
    # Main container with padding
    container = ttk.Frame(win, padding=16)
    container.pack(fill='both', expand=True)
    
    # Title and stats section
    title_frame = ttk.Frame(container)
    title_frame.pack(fill='x', pady=(0, 16))
    
    ttk.Label(title_frame, text='👥 Customer Management', 
             font=('', 14, 'bold')).pack(anchor='w')
    
    stats_label = ttk.Label(title_frame, text='Loading customers...', font=('', 9))
    stats_label.pack(anchor='w', pady=(4, 0))
    
    # Search and filter section
    filter_frame = ttk.LabelFrame(container, text='🔍 Search & Filters', padding=8)
    filter_frame.pack(fill='x', pady=(0, 12))
    
    search_var = tk.StringVar()
    ttk.Label(filter_frame, text='Search:').pack(side='left', padx=(0, 8))
    search_entry = ttk.Entry(filter_frame, textvariable=search_var, width=30)
    search_entry.pack(side='left', padx=(0, 16))
    
    def on_search_change(*args):
        populate_tree()
    search_var.trace('w', on_search_change)
    
    # Table container
    table_frame = ttk.Frame(container)
    table_frame.pack(fill='both', expand=True, pady=(0, 12))
    
    # Customer table
    cols = ['Customer ID', 'Name', 'Email', 'Phone', 'Address', 'Sales Count', 'Total Revenue', 'Created']
    tree = ttk.Treeview(table_frame, columns=cols, show='headings', style='Treeview')
    
    # Configure columns
    col_config = {
        'Customer ID': {'width': 80, 'anchor': 'center'},
        'Name': {'width': 150, 'anchor': 'w'},
        'Email': {'width': 180, 'anchor': 'w'},
        'Phone': {'width': 120, 'anchor': 'w'},
        'Address': {'width': 200, 'anchor': 'w'},
        'Sales Count': {'width': 80, 'anchor': 'e'},
        'Total Revenue': {'width': 100, 'anchor': 'e'},
        'Created': {'width': 80, 'anchor': 'center'}
    }
    
    for col in cols:
        config = col_config.get(col, {'width': 100, 'anchor': 'w'})
        tree.heading(col, text=col, anchor=config['anchor'])
        tree.column(col, width=config['width'], anchor=config['anchor'], minwidth=50)
    
    # Scrollbars
    v_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
    h_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
    
    tree.grid(row=0, column=0, sticky='nsew')
    v_scroll.grid(row=0, column=1, sticky='ns')
    h_scroll.grid(row=1, column=0, sticky='ew')
    
    table_frame.columnconfigure(0, weight=1)
    table_frame.rowconfigure(0, weight=1)
    
    # Helper functions
    def get_selected_customer():
        """Get selected customer data."""
        selection = tree.selection()
        if not selection:
            return None
        item = tree.item(selection[0])
        customer_id = item['values'][0]
        
        customers = db.read_customers()
        for customer in customers:
            if customer.get('customer_id', '').strip() == customer_id:
                return customer
        return None
    
    def populate_tree():
        """Load and display customer data."""
        for item in tree.get_children():
            tree.delete(item)
        # Ensure tag styles (odd/even and states) are configured
        try:
            stripe_treeview(tree)
        except Exception:
            pass
        
        try:
            customers = db.read_customers()
            search_text = search_var.get().lower().strip()
            
            shown_count = 0
            total_revenue = 0.0
            
            for customer in customers:
                # Apply search filter
                if search_text:
                    searchable = f"{customer.get('name', '')} {customer.get('email', '')} {customer.get('phone', '')}".lower()
                    if search_text not in searchable:
                        continue
                
                # Get sales summary for this customer
                try:
                    sales_summary = db.get_customer_sales_summary(customer.get('customer_id', ''))
                    sales_count = sales_summary['sales_count']
                    customer_revenue = sales_summary['total_revenue']
                    total_revenue += customer_revenue
                except Exception:
                    sales_count = 0
                    customer_revenue = 0.0
                
                values = [
                    customer.get('customer_id', ''),
                    customer.get('name', ''),
                    customer.get('email', ''),
                    customer.get('phone', ''),
                    customer.get('address', ''),
                    sales_count,
                    f"${customer_revenue:.2f}",
                    customer.get('created_date', '')
                ]
                
                item_id = tree.insert('', 0, values=values)
                shown_count += 1
                
                # Color code based on sales activity
                if sales_count > 10:
                    stripe_treeview(tree, item_id, 'success')  # High-value customer
                elif sales_count > 5:
                    stripe_treeview(tree, item_id, 'warning')  # Medium customer
                elif sales_count == 0:
                    stripe_treeview(tree, item_id, 'danger')   # No purchases yet
            # Apply zebra striping across rows while preserving state tags
            try:
                children = tree.get_children('')
                for idx, iid in enumerate(children):
                    existing = tree.item(iid, 'tags') or ()
                    odd_even = 'oddrow' if idx % 2 else 'evenrow'
                    new_tags = (odd_even,) + tuple(t for t in existing if t not in ('oddrow','evenrow'))
                    tree.item(iid, tags=new_tags)
            except Exception:
                pass
            
            # Update stats
            all_customers_count = len(customers)
            stats_text = f"👥 Showing {shown_count} of {all_customers_count} customers  |  💰 Combined Revenue: ${total_revenue:.2f}"
            stats_label.configure(text=stats_text)
            
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load customers: {e}')
    
    def do_add_customer():
        """Add new customer dialog."""
        dlg = tk.Toplevel(win)
        dlg.title('➕ Add New Customer')
        dlg.geometry('400x350')
        dlg.resizable(False, False)
        dlg.transient(win)
        dlg.grab_set()
        
        from .theme import apply_theme
        apply_theme(dlg)
        
        container = ttk.Frame(dlg, padding=16)
        container.pack(fill='both', expand=True)
        
        ttk.Label(container, text='➕ Add New Customer', font=('', 12, 'bold')).pack(anchor='w', pady=(0, 16))
        
        # Entry fields
        entries = {}
        
        def add_field(label, key, required=False):
            frame = ttk.Frame(container)
            frame.pack(fill='x', pady=4)
            label_text = f"{label}{'*' if required else ''}:"
            ttk.Label(frame, text=label_text, width=15).pack(side='left', anchor='w')
            entry = ttk.Entry(frame, width=30)
            entry.pack(side='right', anchor='e', expand=True, fill='x')
            entries[key] = entry
            return entry
        
        name_entry = add_field('Name', 'name', required=True)
        add_field('Email', 'email')
        add_field('Phone', 'phone')
        add_field('Address', 'address')
        add_field('Notes', 'notes')
        
        name_entry.focus()  # Focus on name field
        
        def save_customer():
            name = entries['name'].get().strip()
            if not name:
                messagebox.showwarning('Missing Name', 'Customer name is required', parent=dlg)
                return
            
            try:
                customer_id = db.add_customer(
                    name=name,
                    email=entries['email'].get().strip(),
                    phone=entries['phone'].get().strip(),
                    address=entries['address'].get().strip(),
                    notes=entries['notes'].get().strip()
                )
                messagebox.showinfo('Success', f'Customer added successfully!\nCustomer ID: {customer_id}', parent=dlg)
                dlg.destroy()
                populate_tree()
            except Exception as e:
                messagebox.showerror('Error', f'Failed to add customer: {e}', parent=dlg)
        
        # Buttons
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill='x', pady=(16, 0))
        
        themed_button(btn_frame, text='Cancel', variant='secondary', command=dlg.destroy).pack(side='left')
        themed_button(btn_frame, text='Save Customer', variant='primary', 
            command=save_customer).pack(side='right')
    
    def do_edit_customer():
        """Edit selected customer dialog."""
        customer = get_selected_customer()
        if not customer:
            messagebox.showwarning('Select Customer', 'Please select a customer to edit')
            return
        
        dlg = tk.Toplevel(win)
        dlg.title(f'✏️ Edit Customer: {customer.get("name", "")}')
        dlg.geometry('500x400')
        dlg.resizable(False, False)
        dlg.transient(win)
        dlg.grab_set()
        
        from .theme import apply_theme
        apply_theme(dlg)
        
        container = ttk.Frame(dlg, padding=16)
        container.pack(fill='both', expand=True)
        
        ttk.Label(container, text=f'✏️ Edit Customer: {customer.get("name", "")}', 
                 font=('', 12, 'bold')).pack(anchor='w', pady=(0, 8))
        
        # Show customer ID (read-only)
        id_frame = ttk.Frame(container)
        id_frame.pack(fill='x', pady=4)
        ttk.Label(id_frame, text='Customer ID:', width=15).pack(side='left', anchor='w')
        ttk.Label(id_frame, text=customer.get('customer_id', ''), 
                 font=('', 9, 'bold')).pack(side='left', anchor='w', padx=(8, 0))
        
        # Entry fields
        entries = {}
        
        def add_field(label, key, value=''):
            frame = ttk.Frame(container)
            frame.pack(fill='x', pady=4)
            ttk.Label(frame, text=f"{label}:", width=15).pack(side='left', anchor='w')
            entry = ttk.Entry(frame, width=35)
            entry.insert(0, str(value))
            entry.pack(side='right', anchor='e', expand=True, fill='x')
            entries[key] = entry
            return entry
        
        add_field('Name', 'name', customer.get('name', ''))
        add_field('Email', 'email', customer.get('email', ''))
        add_field('Phone', 'phone', customer.get('phone', ''))
        add_field('Address', 'address', customer.get('address', ''))
        add_field('Notes', 'notes', customer.get('notes', ''))
        
        # Sales summary (read-only)
        try:
            sales_summary = db.get_customer_sales_summary(customer.get('customer_id', ''))
            
            summary_frame = ttk.LabelFrame(container, text='📊 Sales Summary', padding=8)
            summary_frame.pack(fill='x', pady=(16, 8))
            
            ttk.Label(summary_frame, text=f"Total Sales: {sales_summary['sales_count']}").pack(anchor='w')
            ttk.Label(summary_frame, text=f"Total Revenue: ${sales_summary['total_revenue']:.2f}").pack(anchor='w')
            
            if sales_summary['recent_sales']:
                ttk.Label(summary_frame, text=f"Last Sale: {sales_summary['recent_sales'][0].get('Date', 'N/A')}").pack(anchor='w')
        except Exception:
            pass
        
        def save_changes():
            name = entries['name'].get().strip()
            if not name:
                messagebox.showwarning('Missing Name', 'Customer name is required', parent=dlg)
                return
            
            try:
                success = db.edit_customer(
                    customer_id=customer.get('customer_id', ''),
                    name=name,
                    email=entries['email'].get().strip(),
                    phone=entries['phone'].get().strip(),
                    address=entries['address'].get().strip(),
                    notes=entries['notes'].get().strip()
                )
                
                if success:
                    messagebox.showinfo('Success', 'Customer updated successfully!', parent=dlg)
                    dlg.destroy()
                    populate_tree()
                else:
                    messagebox.showerror('Error', 'Failed to update customer', parent=dlg)
            except Exception as e:
                messagebox.showerror('Error', f'Failed to update customer: {e}', parent=dlg)
        
        # Buttons
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill='x', pady=(16, 0))
        
        themed_button(btn_frame, text='Cancel', variant='secondary', command=dlg.destroy).pack(side='left')
        themed_button(btn_frame, text='Save Changes', variant='primary', 
            command=save_changes).pack(side='right')
    
    def do_delete_customer():
        """Delete selected customer."""
        customer = get_selected_customer()
        if not customer:
            messagebox.showwarning('Select Customer', 'Please select a customer to delete')
            return
        
        # Check if customer has sales
        try:
            sales_summary = db.get_customer_sales_summary(customer.get('customer_id', ''))
            if sales_summary['sales_count'] > 0:
                if not messagebox.askyesno('Confirm Delete', 
                    f"Customer '{customer.get('name', '')}' has {sales_summary['sales_count']} sales records.\n\n" +
                    "Deleting the customer will not affect sales records, but sales will show as 'Unknown Customer'.\n\n" +
                    "Are you sure you want to delete this customer?"):
                    return
        except Exception:
            pass
        
        if messagebox.askyesno('Confirm Delete', f"Delete customer '{customer.get('name', '')}'?"):
            try:
                success = db.delete_customer(customer.get('customer_id', ''))
                if success:
                    messagebox.showinfo('Success', 'Customer deleted successfully!')
                    populate_tree()
                else:
                    messagebox.showerror('Error', 'Failed to delete customer')
            except Exception as e:
                messagebox.showerror('Error', f'Failed to delete customer: {e}')
    
    # Action buttons
    button_frame = ttk.Frame(container)
    button_frame.pack(fill='x', pady=(16, 0))
    
    # Primary actions (left side)
    primary_frame = ttk.Frame(button_frame)
    primary_frame.pack(side='left', fill='x', expand=True)
    
    themed_button(primary_frame, text='➕ Add Customer', variant='primary',
               command=do_add_customer).pack(side='left', padx=(0, 8))
    themed_button(primary_frame, text='✏️ Edit Customer', variant='success',
               command=do_edit_customer).pack(side='left', padx=4)
    themed_button(primary_frame, text='🔄 Refresh', variant='primary',
               command=populate_tree).pack(side='left', padx=4)
    
    # Secondary actions (right side)
    secondary_frame = ttk.Frame(button_frame)
    secondary_frame.pack(side='right')
    
    themed_button(secondary_frame, text='⬇️ Export CSV', variant='secondary', command=do_export_csv).pack(side='left', padx=4)
    themed_button(secondary_frame, text='🗑️ Delete Customer', variant='danger',
               command=do_delete_customer).pack(side='left', padx=4)
    themed_button(secondary_frame, text='Close', variant='secondary',
               command=win.destroy).pack(side='left', padx=(8, 0))
    
    # Load initial data
    populate_tree()