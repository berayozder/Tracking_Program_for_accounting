# py/main.py
"""Application entry point.

This file can be invoked in two safe ways:
    1. From the project root:  python -m py.main   (recommended)
    2. From the project root:  python py/main.py

Running it from inside the py/ directory (cd py && python main.py) used to break
absolute imports like `import py.db.db as db` because the parent directory (the
project root) was not on sys.path, so the package name `py` could not be
resolved. The small bootstrap block below ensures the project root is added to
sys.path before any intra-package imports occur.
"""

import sys, pathlib  # noqa: E401 (kept intentionally minimal and early)
_PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))

import tkinter as tk  # noqa: E402
from tkinter import messagebox, ttk  # noqa: E402
from ui.imports_window import open_imports_window  # noqa: E402
from ui.view_imports_window import open_view_imports_window  # noqa: E402
from ui.view_inventory_window import open_view_inventory_window  # noqa: E402
from ui.expenses_window import open_expenses_window  # noqa: E402
from ui.view_expenses_window import open_view_expenses_window  # noqa: E402
from ui.sales_window import open_sales_window  # noqa: E402
from ui.view_sales_window import open_view_sales_window  # noqa: E402
from ui.view_returns_window import open_view_returns_window  # noqa: E402
from ui.manage_product_codes_window import open_manage_product_codes_window  # noqa: E402
from ui.batch_analytics_window import open_batch_analytics_window  # noqa: E402
from ui.customers_window import open_customers_window  # noqa: E402
from ui.suppliers_window import open_suppliers_window  # noqa: E402
from ui.monthly_yearly_analytics_window import open_monthly_yearly_analytics_window  # noqa: E402
from ui.theme import apply_theme, FONTS, maximize_window, themed_button, add_buttons  # noqa: E402
from ui.login_window import open_login_dialog  # noqa: E402
from ui.audit_log_window import open_audit_log_window  # noqa: E402
from ui.backup_window import open_backup_window  # noqa: E402
from ui.settings_window import open_settings_window  # noqa: E402
import py.db.db as db  # noqa: E402


def open_not_ready():
    messagebox.showinfo("Coming soon", "This section is not ready yet.")


def main():
    # initialize DB and migrate CSV data
    db.init_db()

    root = tk.Tk()
    root.title("Product Tracker")
    root.geometry("980x720")
    root.minsize(880, 600)
    root.resizable(True, True)
    # Apply global ttk theme
    apply_theme(root)
    # Maximize main window by default
    try:
        maximize_window(root)
    except Exception:
        pass

    # Login before showing main UI
    if not open_login_dialog(root):
        root.destroy()
        return

    # Menu bar
    menubar = tk.Menu(root)
    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="Exit", command=root.destroy)
    menubar.add_cascade(label="File", menu=file_menu)
    reports_menu = tk.Menu(menubar, tearoff=0)
    reports_menu.add_command(label="Batch Analytics", command=lambda: open_batch_analytics_window(root))
    reports_menu.add_command(label="Monthly/Yearly Analysis", command=lambda: open_monthly_yearly_analytics_window(root))
    menubar.add_cascade(label="Reports", menu=reports_menu)
    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label="About", command=lambda: messagebox.showinfo("About", "Product Tracker\nModern themed UI with ttkbootstrap"))
    menubar.add_cascade(label="Help", menu=help_menu)
    root.config(menu=menubar)

    # Container with padding
    container = ttk.Frame(root, padding=(16, 16, 16, 8))
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

    # Notebook for navigation
    notebook = ttk.Notebook(container)
    notebook.pack(fill='both', expand=True)

    tab_home = ttk.Frame(notebook, padding=12)
    tab_imports = ttk.Frame(notebook, padding=12)
    tab_sales = ttk.Frame(notebook, padding=12)
    tab_expenses = ttk.Frame(notebook, padding=12)
    tab_admin = ttk.Frame(notebook, padding=12)
    notebook.add(tab_home, text='🏠 Home')
    notebook.add(tab_imports, text='📦 Imports')
    notebook.add(tab_sales, text='💰 Sales')
    notebook.add(tab_expenses, text='💳 Expenses')
    notebook.add(tab_admin, text='⚙️ Admin')

    # Home tab content
    sections = ttk.Frame(tab_home)
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
    ttk.Button(sec_ad, text="Monthly/Yearly Analysis", 
              command=lambda: open_monthly_yearly_analytics_window(root)).grid(row=3, column=0, sticky='ew', pady=(0, 8))
    ttk.Button(sec_ad, text="Manage Product Codes", 
              command=lambda: open_manage_product_codes_window(root)).grid(row=4, column=0, sticky='ew', pady=(4, 0))
    # New admin quick actions
    themed_button(sec_ad, text="Audit Log", variant='secondary', command=lambda: open_audit_log_window(root)).grid(row=5, column=0, sticky='ew', pady=(8, 8))
    themed_button(sec_ad, text="Backup/Restore", variant='secondary', command=lambda: open_backup_window(root)).grid(row=6, column=0, sticky='ew')
    sec_ad.columnconfigure(0, weight=1)

    # Make grid responsive
    sections.columnconfigure(0, weight=1)
    sections.columnconfigure(1, weight=1)
    sections.rowconfigure(0, weight=1)
    sections.rowconfigure(1, weight=1)

    # Imports tab content
    imports_frame = ttk.Frame(tab_imports)
    imports_frame.pack(fill='both', expand=True)
    imp_box = ttk.LabelFrame(imports_frame, text="📦 Imports & Inventory", padding=16, style='TLabelframe')
    imp_box.pack(fill='x', padx=8, pady=8)
    add_buttons(imp_box, [
        ("Record Import", 'primary', lambda: open_imports_window(root), {'fill': 'x', 'pady': (0, 8)}),
        ("View Imports", 'secondary', lambda: open_view_imports_window(root)),
        ("View Inventory", 'secondary', lambda: open_view_inventory_window(root), {'fill': 'x', 'pady': (4, 0)}),
    ])

    # Sales tab content
    sales_frame = ttk.Frame(tab_sales)
    sales_frame.pack(fill='both', expand=True)
    sales_box = ttk.LabelFrame(sales_frame, text="💰 Sales & Returns", padding=16, style='TLabelframe')
    sales_box.pack(fill='x', padx=8, pady=8)
    add_buttons(sales_box, [
        ("Record Sale", 'primary', lambda: open_sales_window(root), {'fill': 'x', 'pady': (0, 8)}),
        ("View Sales", 'secondary', lambda: open_view_sales_window(root)),
        ("View Returns", 'secondary', lambda: open_view_returns_window(root), {'fill': 'x', 'pady': (4, 0)}),
    ])

    # Expenses tab content
    expenses_frame = ttk.Frame(tab_expenses)
    expenses_frame.pack(fill='both', expand=True)
    ex_box = ttk.LabelFrame(expenses_frame, text="💳 Expenses", padding=16, style='TLabelframe')
    ex_box.pack(fill='x', padx=8, pady=8)
    add_buttons(ex_box, [
        ("Record Expense", 'primary', lambda: open_expenses_window(root), {'fill': 'x', 'pady': (0, 8)}),
        ("View Expenses", 'secondary', lambda: open_view_expenses_window(root)),
    ])

    # Admin tab content
    admin_frame = ttk.Frame(tab_admin)
    admin_frame.pack(fill='both', expand=True)
    ad_box = ttk.LabelFrame(admin_frame, text="⚙️ Administration", padding=16, style='TLabelframe')
    ad_box.pack(fill='x', padx=8, pady=8)
    add_buttons(ad_box, [
        ("Batch Analytics", 'primary', lambda: open_batch_analytics_window(root), {'fill': 'x', 'pady': (0, 8)}),
        ("Manage Customers", 'secondary', lambda: open_customers_window(root)),
        ("Manage Suppliers", 'secondary', lambda: open_suppliers_window(root)),
        ("Monthly/Yearly Analysis", 'secondary', lambda: open_monthly_yearly_analytics_window(root)),
        ("Manage Product Codes", 'secondary', lambda: open_manage_product_codes_window(root)),
        ("Audit Log", 'secondary', lambda: open_audit_log_window(root)),
        ("Backup/Restore", 'secondary', lambda: open_backup_window(root)),
        ("Settings", 'secondary', lambda: open_settings_window(root)),
    ])

    # Status bar
    ttk.Separator(container, orient='horizontal').pack(fill='x', pady=(8, 4))
    status = ttk.Frame(container)
    status.pack(fill='x')
    db_path = str(db.DB_PATH)
    status_left = ttk.Label(status, text=f"DB: {db_path}", font=FONTS['small'], foreground="#888")
    status_left.pack(side='left')
    status_right_var = tk.StringVar(value='')
    user_var = tk.StringVar(value='')
    ttk.Label(status, textvariable=user_var, font=FONTS['small'], foreground="#888").pack(side='right', padx=(0, 12))
    ttk.Label(status, textvariable=status_right_var, font=FONTS['small'], foreground="#888").pack(side='right')

    def update_status():
        try:
            yearly = db.build_yearly_summary()
            cur_year = str(__import__('datetime').datetime.now().year)
            y = yearly.get(cur_year, {})
            net = y.get('net_profit')
            if net is not None:
                status_right_var.set(f"Net Profit {cur_year}: {net:.2f}")
        except Exception:
            status_right_var.set('')
        try:
            info = db.get_current_user()
            if info.get('username'):
                user_var.set(f"User: {info.get('username')} ({info.get('role')})")
            else:
                user_var.set('')
        except Exception:
            user_var.set('')
        root.after(60000, update_status)
    update_status()

    root.mainloop()


if __name__ == "__main__":
    main()
