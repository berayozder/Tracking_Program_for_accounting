"""Root application entry."""
import tkinter as tk
from tkinter import ttk, messagebox

import db.db as db
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
from ui.monthly_yearly_analytics_window import open_monthly_yearly_analytics_window
from ui.theme import apply_theme, maximize_window, themed_button, add_buttons, install_basic_shortcuts
from ui.login_window import open_login_dialog
from ui.audit_log_window import open_audit_log_window
from ui.backup_window import open_backup_window
from ui.settings_window import open_settings_window


def main():
    db.init_db()
    root = tk.Tk()
    root.title("Product Tracker")
    root.geometry("980x720")
    root.minsize(880, 600)
    apply_theme(root)
    # Global keyboard shortcuts (Ctrl/Cmd + A/C/X/V, S, Q, Esc)
    install_basic_shortcuts(root)
    try:
        maximize_window(root)
    except Exception:
        pass
    # Ensure base currency is configured on first run. We require an initial base currency to be set
    # and then make it immutable in settings to preserve historical data integrity.
    try:
        from db.db import get_setting
        if not get_setting('base_currency'):
            # Simple modal prompt for base currency
            def ask_base_currency():
                from ui.settings_window import open_settings_window
                messagebox.showinfo('Initial Setup', 'Please choose the application base currency. This will be locked for historical consistency.')
                open_settings_window(root)
            ask_base_currency()
    except Exception:
        pass

    if not open_login_dialog(root):
        try:
            root.destroy()
        except tk.TclError:
            pass
        return
    menubar = tk.Menu(root)
    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="Exit", command=root.destroy)
    menubar.add_cascade(label="File", menu=file_menu)
    reports_menu = tk.Menu(menubar, tearoff=0)
    reports_menu.add_command(label="Batch Analytics", command=lambda: open_batch_analytics_window(root))
    reports_menu.add_command(label="Monthly/Yearly Analysis", command=lambda: open_monthly_yearly_analytics_window(root))
    menubar.add_cascade(label="Reports", menu=reports_menu)
    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label="About", command=lambda: messagebox.showinfo("About", "Product Tracker"))
    menubar.add_cascade(label="Help", menu=help_menu)
    root.config(menu=menubar)
    container = ttk.Frame(root, padding=(16, 16, 16, 8))
    container.pack(fill='both', expand=True)
    header = ttk.Frame(container)
    header.pack(fill='x', pady=(0, 16))
    ttk.Label(header, text="Product Tracking Program", font=("Arial", 20, "bold")).pack(anchor='w')
    ttk.Label(header, text="Manage imports, inventory, sales, expenses, and returns", font=("Arial", 10), foreground="#555").pack(anchor='w', pady=(4, 0))
    # Persistent top navigation toolbar
    toolbar = ttk.Frame(container)
    toolbar.pack(fill='x', pady=(0, 12))
    themed_button(toolbar, text='➕ Import', variant='primary', command=lambda: open_imports_window(root)).pack(side='left', padx=(0, 6))
    themed_button(toolbar, text='🛒 Sale', variant='primary', command=lambda: open_sales_window(root)).pack(side='left', padx=6)
    themed_button(toolbar, text='💸 Expense', variant='primary', command=lambda: open_expenses_window(root)).pack(side='left', padx=6)
    themed_button(toolbar, text='📦 Inventory', variant='secondary', command=lambda: open_view_inventory_window(root)).pack(side='left', padx=6)
    themed_button(toolbar, text='📊 Analytics', variant='secondary', command=lambda: open_batch_analytics_window(root)).pack(side='left', padx=6)
    themed_button(toolbar, text='⚙️ Settings', variant='secondary', command=lambda: open_settings_window(root)).pack(side='left', padx=6)
    themed_button(toolbar, text='🔐 Audit Log', variant='secondary', command=lambda: open_audit_log_window(root)).pack(side='left', padx=6)
    # Spacer
    ttk.Label(toolbar, text='').pack(side='left', expand=True, fill='x')
    themed_button(toolbar, text='💾 Backup', variant='secondary', command=lambda: open_backup_window(root)).pack(side='right', padx=6)
    themed_button(toolbar, text='🔁 Returns', variant='secondary', command=lambda: open_view_returns_window(root)).pack(side='right', padx=6)
    stats_frame = ttk.LabelFrame(container, text="Quick Stats", padding=12, style='TLabelframe')
    stats_frame.pack(fill='x', pady=(0, 16))
    stats_left = ttk.Frame(stats_frame)
    stats_left.pack(side='left', fill='x', expand=True)
    ttk.Label(stats_left, text="📊 Dashboard", font=("Arial", 9, "bold")).pack(side='left', padx=(0, 20))
    ttk.Label(stats_left, text="Recent Activity: View your latest transactions", foreground="#666", font=("Arial", 9)).pack(side='left')
    ttk.Separator(container, orient='horizontal').pack(fill='x', pady=(0, 16))
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
    # Scrollable container for home sections to ensure bottom buttons remain visible
    home_canvas = tk.Canvas(tab_home, highlightthickness=0)
    vsb = ttk.Scrollbar(tab_home, orient='vertical', command=home_canvas.yview)
    home_wrapper = ttk.Frame(home_canvas)
    def _on_configure(event):
        home_canvas.configure(scrollregion=home_canvas.bbox('all'))
    home_wrapper.bind('<Configure>', _on_configure)
    home_canvas.create_window((0,0), window=home_wrapper, anchor='nw')
    home_canvas.configure(yscrollcommand=vsb.set)
    home_canvas.pack(side='left', fill='both', expand=True)
    vsb.pack(side='right', fill='y')
    sections = ttk.Frame(home_wrapper)
    sections.pack(fill='both', expand=True, padx=4, pady=4)
    # Mousewheel support
    def _on_mousewheel(event):
        home_canvas.yview_scroll(int(-1*(event.delta/120)), 'units')
    home_canvas.bind_all('<MouseWheel>', _on_mousewheel)
    HOME_BTN_WIDTH = 24  # consistent wider buttons
    sec_ii = ttk.LabelFrame(sections, text="📦 Imports & Inventory", padding=16, style='TLabelframe')
    sec_ii.grid(row=0, column=0, sticky='nsew', padx=(0, 12), pady=(0, 12))
    sec_ii.columnconfigure(0, weight=1)
    themed_button(sec_ii, text="➕ Record Import", variant='primary', command=lambda: open_imports_window(root)).grid(row=0, column=0, sticky='ew', pady=(0, 8))
    themed_button(sec_ii, text="📄 View Imports", variant='secondary', command=lambda: open_view_imports_window(root)).grid(row=1, column=0, sticky='ew', pady=4)
    themed_button(sec_ii, text="📦 View Inventory", variant='secondary', command=lambda: open_view_inventory_window(root)).grid(row=2, column=0, sticky='ew', pady=(4, 0))
    sec_sr = ttk.LabelFrame(sections, text="💰 Sales & Returns", padding=16, style='TLabelframe')
    sec_sr.grid(row=0, column=1, sticky='nsew', padx=(12, 0), pady=(0, 12))
    sec_sr.columnconfigure(0, weight=1)
    themed_button(sec_sr, text="🛒 Record Sale", variant='primary', command=lambda: open_sales_window(root)).grid(row=0, column=0, sticky='ew', pady=(0, 8))
    themed_button(sec_sr, text="🧾 View Sales", variant='secondary', command=lambda: open_view_sales_window(root)).grid(row=1, column=0, sticky='ew', pady=4)
    themed_button(sec_sr, text="↩️ View Returns", variant='secondary', command=lambda: open_view_returns_window(root)).grid(row=2, column=0, sticky='ew', pady=(4, 0))
    sec_ex = ttk.LabelFrame(sections, text="💳 Expenses", padding=16, style='TLabelframe')
    sec_ex.grid(row=1, column=0, sticky='nsew', padx=(0, 12), pady=(0, 12))
    sec_ex.columnconfigure(0, weight=1)
    themed_button(sec_ex, text="💸 Record Expense", variant='primary', command=lambda: open_expenses_window(root)).grid(row=0, column=0, sticky='ew', pady=(0, 8))
    themed_button(sec_ex, text="📑 View Expenses", variant='secondary', command=lambda: open_view_expenses_window(root)).grid(row=1, column=0, sticky='ew', pady=(4, 0))
    sec_ad = ttk.LabelFrame(sections, text="⚙️ Administration", padding=16, style='TLabelframe')
    sec_ad.grid(row=1, column=1, sticky='nsew', padx=(12, 0), pady=(0, 12))
    sec_ad.columnconfigure(0, weight=1)
    themed_button(sec_ad, text="📊 Batch Analytics", variant='primary', command=lambda: open_batch_analytics_window(root)).grid(row=0, column=0, sticky='ew', pady=(0, 8))
    themed_button(sec_ad, text="👥 Manage Customers", variant='secondary', command=lambda: open_customers_window(root)).grid(row=1, column=0, sticky='ew', pady=(4, 8))
    themed_button(sec_ad, text="🏢 Manage Suppliers", variant='secondary', command=lambda: open_suppliers_window(root)).grid(row=2, column=0, sticky='ew', pady=(0, 8))
    themed_button(sec_ad, text="📈 Monthly/Yearly Analysis", variant='secondary', command=lambda: open_monthly_yearly_analytics_window(root)).grid(row=3, column=0, sticky='ew', pady=(0, 8))
    themed_button(sec_ad, text="🔢 Manage Product Codes", variant='secondary', command=lambda: open_manage_product_codes_window(root)).grid(row=4, column=0, sticky='ew', pady=(4, 0))
    themed_button(sec_ad, text="Audit Log", variant='secondary', command=lambda: open_audit_log_window(root)).grid(row=5, column=0, sticky='ew', pady=(8, 8))
    themed_button(sec_ad, text="Backup/Restore", variant='secondary', command=lambda: open_backup_window(root)).grid(row=6, column=0, sticky='ew')
    sections.columnconfigure(0, weight=1)
    sections.columnconfigure(1, weight=1)
    sections.rowconfigure(0, weight=1)
    sections.rowconfigure(1, weight=1)
    # Populate Imports tab with its own buttons
    imports_panel = ttk.Frame(tab_imports)
    imports_panel.pack(fill='both', expand=True, padx=8, pady=8)
    ttk.Label(imports_panel, text="Imports", font=("Arial", 14, 'bold')).pack(anchor='w', pady=(0, 8))
    imp_btns = ttk.Frame(imports_panel)
    imp_btns.pack(fill='x')
    themed_button(imp_btns, text='➕ Record Import', variant='primary', width=HOME_BTN_WIDTH, command=lambda: open_imports_window(root)).pack(side='left', padx=(0, 6))
    themed_button(imp_btns, text='📄 View Imports', variant='secondary', width=HOME_BTN_WIDTH, command=lambda: open_view_imports_window(root)).pack(side='left', padx=6)
    themed_button(imp_btns, text='📦 View Inventory', variant='secondary', width=HOME_BTN_WIDTH, command=lambda: open_view_inventory_window(root)).pack(side='left', padx=6)

    # Populate Sales tab
    sales_panel = ttk.Frame(tab_sales)
    sales_panel.pack(fill='both', expand=True, padx=8, pady=8)
    ttk.Label(sales_panel, text="Sales", font=("Arial", 14, 'bold')).pack(anchor='w', pady=(0, 8))
    sales_btns = ttk.Frame(sales_panel)
    sales_btns.pack(fill='x')
    themed_button(sales_btns, text='🛒 Record Sale', variant='primary', width=HOME_BTN_WIDTH, command=lambda: open_sales_window(root)).pack(side='left', padx=(0, 6))
    themed_button(sales_btns, text='🧾 View Sales', variant='secondary', width=HOME_BTN_WIDTH, command=lambda: open_view_sales_window(root)).pack(side='left', padx=6)
    themed_button(sales_btns, text='↩️ View Returns', variant='secondary', width=HOME_BTN_WIDTH, command=lambda: open_view_returns_window(root)).pack(side='left', padx=6)

    # Populate Expenses tab
    expenses_panel = ttk.Frame(tab_expenses)
    expenses_panel.pack(fill='both', expand=True, padx=8, pady=8)
    ttk.Label(expenses_panel, text="Expenses", font=("Arial", 14, 'bold')).pack(anchor='w', pady=(0, 8))
    exp_btns = ttk.Frame(expenses_panel)
    exp_btns.pack(fill='x')
    themed_button(exp_btns, text='💸 Record Expense', variant='primary', width=HOME_BTN_WIDTH, command=lambda: open_expenses_window(root)).pack(side='left', padx=(0, 6))
    themed_button(exp_btns, text='📑 View Expenses', variant='secondary', width=HOME_BTN_WIDTH, command=lambda: open_view_expenses_window(root)).pack(side='left', padx=6)

    # Populate Admin tab
    admin_panel = ttk.Frame(tab_admin)
    admin_panel.pack(fill='both', expand=True, padx=8, pady=8)
    ttk.Label(admin_panel, text="Administration", font=("Arial", 14, 'bold')).pack(anchor='w', pady=(0, 8))
    admin_btns = ttk.Frame(admin_panel)
    admin_btns.pack(fill='x')
    themed_button(admin_btns, text='\u2699\ufe0f Settings', variant='secondary', width=HOME_BTN_WIDTH, command=lambda: open_settings_window(root)).pack(side='left', padx=(0, 6))
    themed_button(admin_btns, text='🔢 Product Codes', variant='secondary', width=HOME_BTN_WIDTH, command=lambda: open_manage_product_codes_window(root)).pack(side='left', padx=6)
    themed_button(admin_btns, text='👥 Customers', variant='secondary', width=HOME_BTN_WIDTH, command=lambda: open_customers_window(root)).pack(side='left', padx=6)
    themed_button(admin_btns, text='🏢 Suppliers', variant='secondary', width=HOME_BTN_WIDTH, command=lambda: open_suppliers_window(root)).pack(side='left', padx=6)
    themed_button(admin_btns, text='📊 Batch Analytics', variant='primary', width=HOME_BTN_WIDTH, command=lambda: open_batch_analytics_window(root)).pack(side='left', padx=6)
    themed_button(admin_btns, text='📈 Monthly/Yearly', variant='secondary', width=HOME_BTN_WIDTH, command=lambda: open_monthly_yearly_analytics_window(root)).pack(side='left', padx=6)
    themed_button(admin_btns, text='Audit Log', variant='secondary', width=HOME_BTN_WIDTH, command=lambda: open_audit_log_window(root)).pack(side='left', padx=6)
    themed_button(admin_btns, text='Backup/Restore', variant='secondary', width=HOME_BTN_WIDTH, command=lambda: open_backup_window(root)).pack(side='left', padx=6)

    root.mainloop()


if __name__ == '__main__':  # pragma: no cover
    main()
