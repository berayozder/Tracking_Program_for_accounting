import tkinter as tk
from tkinter import ttk, messagebox
import db.db as db
from .theme import stripe_treeview, maximize_window, themed_button

def open_batch_analytics_window(root):
    """
    Comprehensive Batch Tracking Analytics Window
    Shows:
    - Batch utilization report (imports with remaining quantities)
    - Profit analysis by sale (cost basis vs revenue)
    - FIFO allocation details
    - Inventory shortage tracking
    """
    win = tk.Toplevel(root)
    win.title('📊 Batch Tracking & Profit Analytics')
    win.geometry('1200x700')
    win.minsize(1000, 600)
    try:
        maximize_window(win)
    except Exception:
        pass
    
    # Apply theme to window
    from .theme import apply_theme
    apply_theme(win)
    
    # Main container with padding
    container = ttk.Frame(win, padding=16)
    container.pack(fill='both', expand=True)
    
    # Title and stats section
    title_frame = ttk.Frame(container)
    title_frame.pack(fill='x', pady=(0, 16))
    
    ttk.Label(title_frame, text='📊 Batch Tracking & Profit Analytics', 
             font=('', 14, 'bold')).pack(anchor='w')
    
    # Stats bar
    stats_frame = ttk.Frame(title_frame)
    stats_frame.pack(fill='x', pady=(8, 0))
    
    # Include expenses toggle
    include_expenses_var = tk.BooleanVar(value=False)
    toggle_frame = ttk.Frame(stats_frame)
    toggle_frame.pack(fill='x', pady=(0, 4))
    ttk.Checkbutton(toggle_frame, text='Include import-related expenses in costs', 
                    variable=include_expenses_var, command=lambda: refresh_all_data()).pack(side='left')
    
    stats_label = ttk.Label(stats_frame, text='Loading analytics...', font=('', 9))
    stats_label.pack(anchor='w')
    
    # Notebook for different views
    notebook = ttk.Notebook(container)
    notebook.pack(fill='both', expand=True)
    
    # =====================================================================================
    # TAB 1: BATCH UTILIZATION REPORT
    # =====================================================================================
    batch_frame = ttk.Frame(notebook)
    notebook.add(batch_frame, text='📦 Batch Utilization')
    
    # Batch table
    batch_table_frame = ttk.Frame(batch_frame, padding=8)
    batch_table_frame.pack(fill='both', expand=True)
    
    batch_cols = ['ID', 'Date', 'Category', 'Subcategory', 'Supplier', 'Original Qty', 
                  'Remaining Qty', 'Used %', 'Unit Cost', 'Cost Allocated', 'Revenue', 'Profit']
    batch_tree = ttk.Treeview(batch_table_frame, columns=batch_cols, show='headings', style='Treeview')
    
    # Configure batch columns
    batch_col_config = {
        'ID': {'width': 50, 'anchor': 'center'},
        'Date': {'width': 80, 'anchor': 'center'},
        'Category': {'width': 120, 'anchor': 'w'},
        'Subcategory': {'width': 120, 'anchor': 'w'},
        'Supplier': {'width': 100, 'anchor': 'w'},
        'Original Qty': {'width': 80, 'anchor': 'e'},
        'Remaining Qty': {'width': 80, 'anchor': 'e'},
        'Used %': {'width': 60, 'anchor': 'e'},
        'Unit Cost': {'width': 70, 'anchor': 'e'},
        'Cost Allocated': {'width': 90, 'anchor': 'e'},
        'Revenue': {'width': 80, 'anchor': 'e'},
        'Profit': {'width': 80, 'anchor': 'e'}
    }
    
    for col in batch_cols:
        config = batch_col_config.get(col, {'width': 100, 'anchor': 'w'})
        batch_tree.heading(col, text=col, anchor=config['anchor'])
        batch_tree.column(col, width=config['width'], anchor=config['anchor'], minwidth=50)
    
    # Batch scrollbars
    batch_scroll_v = ttk.Scrollbar(batch_table_frame, orient='vertical', command=batch_tree.yview)
    batch_scroll_h = ttk.Scrollbar(batch_table_frame, orient='horizontal', command=batch_tree.xview)
    batch_tree.configure(yscrollcommand=batch_scroll_v.set, xscrollcommand=batch_scroll_h.set)
    
    batch_tree.grid(row=0, column=0, sticky='nsew')
    batch_scroll_v.grid(row=0, column=1, sticky='ns')
    batch_scroll_h.grid(row=1, column=0, sticky='ew')
    
    batch_table_frame.columnconfigure(0, weight=1)
    batch_table_frame.rowconfigure(0, weight=1)
    
    # =====================================================================================
    # TAB 2: SALE PROFIT ANALYSIS
    # =====================================================================================
    profit_frame = ttk.Frame(notebook)
    notebook.add(profit_frame, text='💰 Sale Profit Analysis')
    
    # Profit table
    profit_table_frame = ttk.Frame(profit_frame, padding=8)
    profit_table_frame.pack(fill='both', expand=True)
    
    profit_cols = ['Product ID', 'Sale Date', 'Category', 'Subcategory', 'Qty', 
                   'Total Cost', 'Total Revenue', 'Total Profit', 'Margin %', 'Batches Used']
    profit_tree = ttk.Treeview(profit_table_frame, columns=profit_cols, show='headings', style='Treeview')
    
    # Configure profit columns
    profit_col_config = {
        'Product ID': {'width': 120, 'anchor': 'center'},
        'Sale Date': {'width': 80, 'anchor': 'center'},
        'Category': {'width': 120, 'anchor': 'w'},
        'Subcategory': {'width': 120, 'anchor': 'w'},
        'Qty': {'width': 50, 'anchor': 'e'},
        'Total Cost': {'width': 80, 'anchor': 'e'},
        'Total Revenue': {'width': 90, 'anchor': 'e'},
        'Total Profit': {'width': 80, 'anchor': 'e'},
        'Margin %': {'width': 70, 'anchor': 'e'},
        'Batches Used': {'width': 80, 'anchor': 'e'}
    }
    
    for col in profit_cols:
        config = profit_col_config.get(col, {'width': 100, 'anchor': 'w'})
        profit_tree.heading(col, text=col, anchor=config['anchor'])
        profit_tree.column(col, width=config['width'], anchor=config['anchor'], minwidth=50)
    
    # Profit scrollbars
    profit_scroll_v = ttk.Scrollbar(profit_table_frame, orient='vertical', command=profit_tree.yview)
    profit_scroll_h = ttk.Scrollbar(profit_table_frame, orient='horizontal', command=profit_tree.xview)
    profit_tree.configure(yscrollcommand=profit_scroll_v.set, xscrollcommand=profit_scroll_h.set)
    
    profit_tree.grid(row=0, column=0, sticky='nsew')
    profit_scroll_v.grid(row=0, column=1, sticky='ns')
    profit_scroll_h.grid(row=1, column=0, sticky='ew')
    
    profit_table_frame.columnconfigure(0, weight=1)
    profit_table_frame.rowconfigure(0, weight=1)
    
    # =====================================================================================
    # TAB 3: DETAILED SALE ALLOCATIONS
    # =====================================================================================
    detail_frame = ttk.Frame(notebook)
    notebook.add(detail_frame, text='🔍 Allocation Details')
    
    # Search section for detail view
    search_frame = ttk.LabelFrame(detail_frame, text='🔍 Search Sale Allocations', padding=8)
    search_frame.pack(fill='x', pady=(0, 8))
    
    search_var = tk.StringVar()
    ttk.Label(search_frame, text='Search Product ID:').pack(side='left', padx=(0, 8))
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=20)
    search_entry.pack(side='left', padx=(0, 8))
    
    def search_allocation_details():
        product_id = search_var.get().strip()
        if not product_id:
            messagebox.showwarning('Search', 'Please enter a Product ID to search')
            return
        
        try:
            allocations = db.get_sale_batch_info(product_id)
            populate_detail_tree(allocations, product_id)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to get allocation details: {e}')
    
    themed_button(search_frame, text='🔍 Search', variant='primary', command=search_allocation_details).pack(side='left')
    
    # Detail table
    detail_table_frame = ttk.Frame(detail_frame, padding=8)
    detail_table_frame.pack(fill='both', expand=True)
    
    detail_cols = ['Product ID', 'Sale Date', 'Batch ID', 'Batch Date', 'Supplier', 
                   'Qty from Batch', 'Unit Cost', 'Sale Price', 'Profit/Unit', 'Total Profit']
    detail_tree = ttk.Treeview(detail_table_frame, columns=detail_cols, show='headings', style='Treeview')
    
    # Configure detail columns
    for col in detail_cols:
        detail_tree.heading(col, text=col, anchor='w')
        detail_tree.column(col, width=100, anchor='w', minwidth=50)
    
    # Detail scrollbars
    detail_scroll_v = ttk.Scrollbar(detail_table_frame, orient='vertical', command=detail_tree.yview)
    detail_scroll_h = ttk.Scrollbar(detail_table_frame, orient='horizontal', command=detail_tree.xview)
    detail_tree.configure(yscrollcommand=detail_scroll_v.set, xscrollcommand=detail_scroll_h.set)
    
    detail_tree.grid(row=0, column=0, sticky='nsew')
    detail_scroll_v.grid(row=0, column=1, sticky='ns')
    detail_scroll_h.grid(row=1, column=0, sticky='ew')
    
    detail_table_frame.columnconfigure(0, weight=1)
    detail_table_frame.rowconfigure(0, weight=1)
    
    # =====================================================================================
    # TAB 4: CUSTOMER ANALYTICS
    # =====================================================================================
    customer_frame = ttk.Frame(notebook)
    notebook.add(customer_frame, text='👥 Customer Analytics')
    
    # Customer analytics table
    customer_table_frame = ttk.Frame(customer_frame, padding=8)
    customer_table_frame.pack(fill='both', expand=True)
    
    customer_cols = ['Customer Name', 'Customer ID', 'Total Sales', 'Total Revenue', 
                     'Total Profit', 'Avg Profit/Sale', 'Profit Margin %', 'Last Sale']
    customer_tree = ttk.Treeview(customer_table_frame, columns=customer_cols, show='headings', style='Treeview')
    
    # Configure customer columns
    customer_col_config = {
        'Customer Name': {'width': 150, 'anchor': 'w'},
        'Customer ID': {'width': 100, 'anchor': 'center'},
        'Total Sales': {'width': 80, 'anchor': 'e'},
        'Total Revenue': {'width': 100, 'anchor': 'e'},
        'Total Profit': {'width': 100, 'anchor': 'e'},
        'Avg Profit/Sale': {'width': 100, 'anchor': 'e'},
        'Profit Margin %': {'width': 100, 'anchor': 'e'},
        'Last Sale': {'width': 80, 'anchor': 'center'}
    }
    
    for col in customer_cols:
        config = customer_col_config.get(col, {'width': 100, 'anchor': 'w'})
        customer_tree.heading(col, text=col, anchor=config['anchor'])
        customer_tree.column(col, width=config['width'], anchor=config['anchor'], minwidth=50)
    
    # Customer scrollbars
    customer_scroll_v = ttk.Scrollbar(customer_table_frame, orient='vertical', command=customer_tree.yview)
    customer_scroll_h = ttk.Scrollbar(customer_table_frame, orient='horizontal', command=customer_tree.xview)
    customer_tree.configure(yscrollcommand=customer_scroll_v.set, xscrollcommand=customer_scroll_h.set)
    
    customer_tree.grid(row=0, column=0, sticky='nsew')
    customer_scroll_v.grid(row=0, column=1, sticky='ns')
    customer_scroll_h.grid(row=1, column=0, sticky='ew')
    
    customer_table_frame.columnconfigure(0, weight=1)
    customer_table_frame.rowconfigure(0, weight=1)
    
    # =====================================================================================
    # DATA LOADING AND REFRESH FUNCTIONS
    # =====================================================================================
    
    def populate_batch_tree():
        """Load and display batch utilization data."""
        for item in batch_tree.get_children():
            batch_tree.delete(item)
        
        try:
            if include_expenses_var.get():
                batches = db.get_batch_utilization_report_inclusive(include_expenses=True)
            else:
                batches = db.get_batch_utilization_report()
            
            for batch in batches:
                used_qty = batch['allocated_quantity']
                original_qty = batch['original_quantity']
                used_percent = (used_qty / original_qty * 100) if original_qty > 0 else 0
                
                # Color coding for utilization
                values = [
                    batch['id'],
                    batch['batch_date'],
                    batch['category'],
                    batch['subcategory'],
                    batch['supplier'],
                    f"{original_qty:.1f}",
                    f"{batch['remaining_quantity']:.1f}",
                    f"{used_percent:.1f}%",
                    f"${batch['unit_cost']:.2f}",
                    f"${batch['total_cost_allocated']:.2f}",
                    f"${batch['total_revenue']:.2f}",
                    f"${batch['total_profit']:.2f}"
                ]
                
                item_id = batch_tree.insert('', 'end', values=values)
                
                # Color code based on utilization
                if batch['remaining_quantity'] <= 0:
                    batch_tree.set(item_id, 'Remaining Qty', '✅ FULLY USED')
                elif used_percent >= 75:
                    stripe_treeview(batch_tree, item_id, 'warning')  # High utilization
                elif used_percent == 0:
                    stripe_treeview(batch_tree, item_id, 'danger')   # Unused
            
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load batch data: {e}')
    
    def populate_profit_tree():
        """Load and display sale profit analysis."""
        for item in profit_tree.get_children():
            profit_tree.delete(item)
        
        try:
            sales = db.get_profit_analysis_by_sale(include_expenses=include_expenses_var.get())
            
            for sale in sales:
                margin_pct = sale.get('profit_margin_percent', 0) or 0
                
                values = [
                    sale['product_id'],
                    sale['sale_date'],
                    sale['category'],
                    sale['subcategory'],
                    f"{sale['total_quantity']:.0f}",
                    f"${sale['total_cost']:.2f}",
                    f"${sale['total_revenue']:.2f}",
                    f"${sale['total_profit']:.2f}",
                    f"{margin_pct:.1f}%",
                    sale['batches_used']
                ]
                
                item_id = profit_tree.insert('', 'end', values=values)
                
                # Color code based on profit margin
                if sale['total_profit'] < 0:
                    stripe_treeview(profit_tree, item_id, 'danger')    # Loss
                elif margin_pct >= 50:
                    stripe_treeview(profit_tree, item_id, 'success')   # High profit
                elif margin_pct >= 25:
                    stripe_treeview(profit_tree, item_id, 'warning')   # Medium profit
                
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load profit data: {e}')
    
    def populate_detail_tree(allocations, product_id):
        """Load allocation details for specific product ID."""
        for item in detail_tree.get_children():
            detail_tree.delete(item)
        
        if not allocations:
            detail_tree.insert('', 'end', values=[
                product_id, 'N/A', 'N/A', 'N/A', 'N/A', 
                'No allocations found', 'N/A', 'N/A', 'N/A', 'N/A'
            ])
            return
        
        for alloc in allocations:
            total_profit = alloc['quantity_from_batch'] * alloc['profit_per_unit']
            
            values = [
                alloc['product_id'],
                alloc['sale_date'],
                alloc['batch_id'] or 'SHORTAGE',
                alloc.get('batch_date', 'N/A'),
                alloc.get('supplier', 'N/A'),
                f"{alloc['quantity_from_batch']:.1f}",
                f"${alloc['unit_cost']:.2f}",
                f"${alloc['unit_sale_price']:.2f}",
                f"${alloc['profit_per_unit']:.2f}",
                f"${total_profit:.2f}"
            ]
            
            item_id = detail_tree.insert('', 'end', values=values)
            
            # Color code shortages
            if alloc['batch_id'] is None:
                stripe_treeview(detail_tree, item_id, 'danger')
    
    def populate_customer_tree():
        """Load and display customer analytics data."""
        for item in customer_tree.get_children():
            customer_tree.delete(item)
        
        try:
            # Get all customers
            customers = db.read_customers()
            
            # Get all sales with batch allocation data
            sales = db.get_profit_analysis_by_sale()
            
            # Load sales data with customer IDs
            from pathlib import Path
            import csv
            SALES_CSV = Path(__file__).resolve().parents[2] / 'data' / 'sales.csv'
            
            sales_by_customer = {}
            if SALES_CSV.exists():
                with SALES_CSV.open('r', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        customer_id = row.get('CustomerID', '').strip()
                        product_id = row.get('ProductID', '').strip()
                        if customer_id and product_id:
                            if customer_id not in sales_by_customer:
                                sales_by_customer[customer_id] = []
                            sales_by_customer[customer_id].append(row)
            
            # Combine customer data with sales analytics
            for customer in customers:
                customer_id = customer.get('customer_id', '')
                customer_name = customer.get('name', 'Unknown')
                
                customer_sales = sales_by_customer.get(customer_id, [])
                
                # Calculate analytics
                total_sales = len(customer_sales)
                total_revenue = 0.0
                total_profit = 0.0
                last_sale_date = ''
                
                if customer_sales:
                    # Get profit data for this customer's sales
                    customer_product_ids = [s.get('ProductID', '') for s in customer_sales]
                    
                    for sale in sales:
                        if sale['product_id'] in customer_product_ids:
                            total_revenue += sale['total_revenue']
                            total_profit += sale['total_profit']
                    
                    # Find last sale date
                    customer_sales.sort(key=lambda x: x.get('Date', ''), reverse=True)
                    last_sale_date = customer_sales[0].get('Date', '') if customer_sales else ''
                
                avg_profit_per_sale = (total_profit / total_sales) if total_sales > 0 else 0.0
                profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0.0
                
                values = [
                    customer_name,
                    customer_id,
                    total_sales,
                    f"${total_revenue:.2f}",
                    f"${total_profit:.2f}",
                    f"${avg_profit_per_sale:.2f}",
                    f"{profit_margin:.1f}%",
                    last_sale_date
                ]
                
                item_id = customer_tree.insert('', 'end', values=values)
                
                # Color code based on customer value
                if total_sales == 0:
                    stripe_treeview(customer_tree, item_id, 'danger')      # No purchases
                elif total_sales >= 10:
                    stripe_treeview(customer_tree, item_id, 'success')     # High-value customer
                elif total_sales >= 5:
                    stripe_treeview(customer_tree, item_id, 'warning')     # Medium customer
                
        except Exception as e:
            messagebox.showerror('Error', f'Failed to load customer analytics: {e}')
    
    def refresh_all_data():
        """Refresh all analytics data."""
        try:
            # First ensure existing imports are migrated to batches
            migrated_count = db.migrate_existing_imports_to_batches()
            # Silent migration; removed console print
            # Backfill any missing unit costs in historical allocations
            try:
                db.backfill_allocation_unit_costs()
            except Exception:
                pass
            
            populate_batch_tree()
            populate_profit_tree()
            populate_customer_tree()
            
            # Update stats
            try:
                if include_expenses_var.get():
                    batches = db.get_batch_utilization_report_inclusive(include_expenses=True)
                    sales = db.get_profit_analysis_by_sale(include_expenses=True)
                else:
                    batches = db.get_batch_utilization_report()
                    sales = db.get_profit_analysis_by_sale()
                
                total_batches = len(batches)
                active_batches = len([b for b in batches if b['remaining_quantity'] > 0])
                total_sales = len(sales)
                total_profit = sum(s['total_profit'] for s in sales)
                
                stats_text = (f"📦 Batches: {total_batches} total, {active_batches} active  |  "
                             f"💰 Sales: {total_sales}  |  "
                             f"📈 Total Profit: ${total_profit:.2f}")
                stats_label.configure(text=stats_text)
            except Exception:
                stats_label.configure(text="Stats calculation error")
                
        except Exception as e:
            messagebox.showerror('Error', f'Failed to refresh data: {e}')
    
    # Action buttons
    button_frame = ttk.Frame(container)
    button_frame.pack(fill='x', pady=(16, 0))
    
    themed_button(button_frame, text='🔄 Refresh All Data', variant='primary',
               command=refresh_all_data).pack(side='left', padx=(0, 8))
    
    themed_button(button_frame, text='Close', variant='secondary',
               command=win.destroy).pack(side='right')
    
    # Load initial data
    refresh_all_data()