# py/main.py
import tkinter as tk
from tkinter import messagebox, ttk
from ui.imports_window import open_imports_window
from ui.view_imports_window import open_view_imports_window
from ui.view_inventory_window import open_view_inventory_window
from ui.expenses_window import open_expenses_window
from ui.view_expenses_window import open_view_expenses_window
from ui.sales_window import open_sales_window
from ui.view_sales_window import open_view_sales_window
from ui.view_returns_window import open_view_returns_window
from ui.manage_product_codes_window import open_manage_product_codes_window
from ui.batch_analytics_window import open_batch_analytics_window
from ui.customers_window import open_customers_window
from ui.suppliers_window import open_suppliers_window
from ui.theme import apply_theme
import db


def open_not_ready():
    messagebox.showinfo("Coming soon", "This section is not ready yet.")


def main():
    # initialize DB and migrate CSV data
    db.init_db(migrate_csv=True)

    root = tk.Tk()
    root.title("Product Tracker")
    root.geometry("700x620")
    root.minsize(640, 560)
    root.resizable(True, True)
    # Apply global ttk theme
    apply_theme(root)

    # Container with padding
    container = ttk.Frame(root, padding=(20, 20, 20, 20))
    container.pack(fill='both', expand=True)

    # Header with improved styling
    header = ttk.Frame(container)
    header.pack(fill='x', pady=(0, 16))
    title_label = ttk.Label(header, text="Product Tracking Program", font=("Arial", 20, "bold"))
    title_label.pack(anchor='w')
    subtitle_label = ttk.Label(header, text="Manage imports, inventory, sales, expenses, and returns", 
                              font=("Arial", 10), foreground="#555")
    subtitle_label.pack(anchor='w', pady=(4, 0))
    
    # Quick stats bar
    stats_frame = ttk.LabelFrame(container, text="Quick Stats", padding=12, style='TLabelframe')
    stats_frame.pack(fill='x', pady=(0, 16))
    
    # Placeholder stats (you can connect these to real data later)
    stats_left = ttk.Frame(stats_frame)
    stats_left.pack(side='left', fill='x', expand=True)
    ttk.Label(stats_left, text="📊 Dashboard", font=("Arial", 9, "bold")).pack(side='left', padx=(0, 20))
    ttk.Label(stats_left, text="Recent Activity: View your latest transactions", 
             foreground="#666", font=("Arial", 9)).pack(side='left')
    
    ttk.Separator(container, orient='horizontal').pack(fill='x', pady=(0, 16))

    # Sections
    sections = ttk.Frame(container)
    sections.pack(fill='both', expand=True)

    # Imports & Inventory
    sec_ii = ttk.LabelFrame(sections, text="📦 Imports & Inventory", padding=16, style='TLabelframe')
    sec_ii.grid(row=0, column=0, sticky='nsew', padx=(0, 12), pady=(0, 12))
    ttk.Button(sec_ii, text="Record Import", style='Primary.TButton',
              command=lambda: open_imports_window(root)).grid(row=0, column=0, sticky='ew', pady=(0, 8))
    ttk.Button(sec_ii, text="View Imports", 
              command=lambda: open_view_imports_window(root)).grid(row=1, column=0, sticky='ew', pady=4)
    ttk.Button(sec_ii, text="View Inventory", 
              command=lambda: open_view_inventory_window(root)).grid(row=2, column=0, sticky='ew', pady=(4, 0))
    sec_ii.columnconfigure(0, weight=1)

    # Sales & Returns
    sec_sr = ttk.LabelFrame(sections, text="💰 Sales & Returns", padding=16, style='TLabelframe')
    sec_sr.grid(row=0, column=1, sticky='nsew', padx=(12, 0), pady=(0, 12))
    ttk.Button(sec_sr, text="Record Sale", style='Primary.TButton',
              command=lambda: open_sales_window(root)).grid(row=0, column=0, sticky='ew', pady=(0, 8))
    ttk.Button(sec_sr, text="View Sales", 
              command=lambda: open_view_sales_window(root)).grid(row=1, column=0, sticky='ew', pady=4)
    ttk.Button(sec_sr, text="View Returns", 
              command=lambda: open_view_returns_window(root)).grid(row=2, column=0, sticky='ew', pady=(4, 0))
    sec_sr.columnconfigure(0, weight=1)

    # Expenses
    sec_ex = ttk.LabelFrame(sections, text="💳 Expenses", padding=16, style='TLabelframe')
    sec_ex.grid(row=1, column=0, sticky='nsew', padx=(0, 12), pady=(0, 12))
    ttk.Button(sec_ex, text="Record Expense", style='Primary.TButton',
              command=lambda: open_expenses_window(root)).grid(row=0, column=0, sticky='ew', pady=(0, 8))
    ttk.Button(sec_ex, text="View Expenses", 
              command=lambda: open_view_expenses_window(root)).grid(row=1, column=0, sticky='ew', pady=(4, 0))
    sec_ex.columnconfigure(0, weight=1)

    # Administration
    sec_ad = ttk.LabelFrame(sections, text="⚙️ Administration", padding=16, style='TLabelframe')
    sec_ad.grid(row=1, column=1, sticky='nsew', padx=(12, 0), pady=(0, 12))
    ttk.Button(sec_ad, text="Batch Analytics", style='Primary.TButton',
              command=lambda: open_batch_analytics_window(root)).grid(row=0, column=0, sticky='ew', pady=(0, 8))
    ttk.Button(sec_ad, text="Manage Customers", 
              command=lambda: open_customers_window(root)).grid(row=1, column=0, sticky='ew', pady=(4, 8))
    ttk.Button(sec_ad, text="Manage Suppliers", 
              command=lambda: open_suppliers_window(root)).grid(row=2, column=0, sticky='ew', pady=(0, 8))
    ttk.Button(sec_ad, text="Manage Product Codes", 
              command=lambda: open_manage_product_codes_window(root)).grid(row=3, column=0, sticky='ew', pady=(4, 0))
    sec_ad.columnconfigure(0, weight=1)

    # Make grid responsive
    sections.columnconfigure(0, weight=1)
    sections.columnconfigure(1, weight=1)
    sections.rowconfigure(0, weight=1)
    sections.rowconfigure(1, weight=1)

    # Footer
    ttk.Separator(container, orient='horizontal').pack(fill='x', pady=(12, 12))
    footer = ttk.Frame(container)
    footer.pack(fill='x')
    
    # Version info on left
    ttk.Label(footer, text="Version 1.0 • Product Tracker", 
             font=("Arial", 8), foreground="#888").pack(side='left')
    
    # Exit button on right with secondary style
    ttk.Button(footer, text="Exit", style='Secondary.TButton', 
              command=root.destroy).pack(side='right')

    root.mainloop()


if __name__ == "__main__":
    main()
