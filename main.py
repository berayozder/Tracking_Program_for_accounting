"""Root application entry."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import db as db
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
from ui.vat_report_window import open_vat_report_window
from ui.login_window import open_login_dialog
from ui.audit_log_window import open_audit_log_window
from ui.backup_window import open_backup_window
from ui.settings_window import open_settings_window
from ui.trash_window import open_trash_window
from ui.admin_backup_button import add_backup_button_to_frame

# Global shutdown flag
app_exiting = False

def safe_shutdown(root):
    global app_exiting
    if app_exiting:
        return
    app_exiting = True
    try:
        root.destroy()
    except Exception:
        pass

def main():
    db.init_db()
    root = tk.Tk()
    root.title("Product Tracker")
    root.geometry("980x720")
    root.minsize(880, 600)
    apply_theme(root)
    install_basic_shortcuts(root)
    try:
        maximize_window(root)
    except Exception:
        pass
    try:
        from db import get_setting, set_setting
        try:
            _base = get_setting('base_currency')
        except Exception:
            _base = None
        if not _base or not str(_base).strip():
            try:
                root.option_add('*Button.background', '#1E90FF')
                root.option_add('*Button.foreground', '#1E90FF')
                root.option_add('*TButton.background', '#1E90FF')
                root.option_add('*TButton.foreground', '#1E90FF')
            except Exception:
                pass
            try:
                dlg = tk.Toplevel(root); dlg.transient(root); dlg.grab_set()
                ttk.Label(dlg, text='Enter base currency (e.g. USD):').pack(padx=12, pady=(12,0))
                e = ttk.Entry(dlg); e.insert(0, 'USD'); e.pack(padx=12, pady=8)
                def _save():
                    v = e.get().strip().upper()
                    if v:
                        try: set_setting('base_currency', v)
                        except Exception: pass
                    try: dlg.destroy()
                    except Exception: pass
                def _cancel():
                    try: dlg.destroy()
                    except Exception: pass
                frm = ttk.Frame(dlg); frm.pack(fill='x', padx=12, pady=(0,12))
                themed_button(frm, text='Save', variant='primary', command=_save).pack(side='left')
                _cf = tk.Frame(frm, bg='white', bd=1, relief='solid')
                _cl = tk.Label(_cf, text='Cancel', bg='white', fg='#222')
                _cl.pack(padx=10, pady=6)
                _cf.pack(side='right', padx=(6,0))
                _cf.bind('<Button-1>', lambda e: _cancel())
                _cl.bind('<Button-1>', lambda e: _cancel())
                dlg.wait_window()
            except Exception:
                v = simpledialog.askstring('Initial Setup — Base Currency', 'Enter base currency (e.g. USD):', initialvalue='USD', parent=root)
                if v:
                    try: set_setting('base_currency', v.strip().upper())
                    except Exception: pass
    except Exception:
        pass

    if not open_login_dialog(root):
        safe_shutdown(root)
        return
    menubar = tk.Menu(root)
    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="Exit", command=lambda: safe_shutdown(root))
    menubar.add_cascade(label="File", menu=file_menu)
    reports_menu = tk.Menu(menubar, tearoff=0)
    reports_menu.add_command(label="Batch Analytics", command=lambda: open_batch_analytics_window(root))
    reports_menu.add_command(label="Monthly/Yearly Analysis", command=lambda: open_monthly_yearly_analytics_window(root))
    reports_menu.add_command(label="KDV Raporu (VAT Report)", command=lambda: open_vat_report_window(root))
    menubar.add_cascade(label="Reports", menu=reports_menu)
    help_menu = tk.Menu(menubar, tearoff=0)
    help_menu.add_command(label="About", command=lambda: messagebox.showinfo("About", "Product Tracker"))
    menubar.add_cascade(label="Help", menu=help_menu)
    root.config(menu=menubar)

    # --- Notebook/tabbed interface ---
    notebook = ttk.Notebook(root)
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

    # Example Home tab content with ALL main actions
    ttk.Label(tab_home, text="Welcome to Product Tracker!", font=("Arial", 16, "bold")).pack(pady=16)

    # Improved Home tab layout: grouped, 2-column, grid-based
    home_container = ttk.Frame(tab_home)
    home_container.pack(fill='both', expand=True, padx=12, pady=12)

    # Section: Imports & Inventory
    imports_frame = ttk.LabelFrame(home_container, text="📦 Imports & Inventory", padding=16)
    imports_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 16), pady=(0, 16))
    themed_button(imports_frame, text='➕ Record Import', command=lambda: open_imports_window(root)).grid(row=0, column=0, sticky='ew', pady=4)
    themed_button(imports_frame, text='📄 View Imports', command=lambda: open_view_imports_window(root)).grid(row=1, column=0, sticky='ew', pady=4)
    themed_button(imports_frame, text='📦 View Inventory', command=lambda: open_view_inventory_window(root)).grid(row=2, column=0, sticky='ew', pady=4)

    # Section: Sales & Returns
    sales_frame = ttk.LabelFrame(home_container, text="💰 Sales & Returns", padding=16)
    sales_frame.grid(row=0, column=1, sticky='nsew', padx=(0, 0), pady=(0, 16))
    themed_button(sales_frame, text='🛒 Record Sale', command=lambda: open_sales_window(root)).grid(row=0, column=0, sticky='ew', pady=4)
    themed_button(sales_frame, text='🧾 View Sales', command=lambda: open_view_sales_window(root)).grid(row=1, column=0, sticky='ew', pady=4)
    themed_button(sales_frame, text='↩️ View Returns', command=lambda: open_view_returns_window(root)).grid(row=2, column=0, sticky='ew', pady=4)

    # Section: Expenses
    expenses_frame = ttk.LabelFrame(home_container, text="💳 Expenses", padding=16)
    expenses_frame.grid(row=1, column=0, sticky='nsew', padx=(0, 16), pady=(0, 16))
    themed_button(expenses_frame, text='💸 Record Expense', command=lambda: open_expenses_window(root)).grid(row=0, column=0, sticky='ew', pady=4)
    themed_button(expenses_frame, text='📑 View Expenses', command=lambda: open_view_expenses_window(root)).grid(row=1, column=0, sticky='ew', pady=4)

    # Section: Analytics & Codes
    analytics_frame = ttk.LabelFrame(home_container, text="📊 Analytics & Codes", padding=16)
    analytics_frame.grid(row=1, column=1, sticky='nsew', padx=(0, 0), pady=(0, 16))
    themed_button(analytics_frame, text='📊 Batch Analytics', command=lambda: open_batch_analytics_window(root)).grid(row=0, column=0, sticky='ew', pady=4)
    themed_button(analytics_frame, text='📈 Monthly/Yearly Analysis', command=lambda: open_monthly_yearly_analytics_window(root)).grid(row=1, column=0, sticky='ew', pady=4)
    themed_button(analytics_frame, text='🔢 Manage Product Codes', command=lambda: open_manage_product_codes_window(root)).grid(row=2, column=0, sticky='ew', pady=4)

    # Add one-click backup button at the top of the Admin tab
    backup_btn_frame = ttk.Frame(tab_admin)
    backup_btn_frame.pack(fill='x', pady=(8, 0))
    add_backup_button_to_frame(backup_btn_frame, root)

    # Section: Admin & Other
    admin_frame = ttk.LabelFrame(tab_admin, text="⚙️ Admin & Other", padding=16)
    admin_frame.pack(fill='both', expand=True, padx=0, pady=(0, 0))
    themed_button(admin_frame, text='👥 Manage Customers', command=lambda: open_customers_window(root)).grid(row=0, column=0, sticky='ew', pady=4, padx=(0, 8))
    themed_button(admin_frame, text='🏢 Manage Suppliers', command=lambda: open_suppliers_window(root)).grid(row=0, column=1, sticky='ew', pady=4, padx=(8, 0))
    themed_button(admin_frame, text='⚙️ Settings', command=lambda: open_settings_window(root)).grid(row=1, column=0, sticky='ew', pady=4, padx=(0, 8))
    themed_button(admin_frame, text='Audit Log', command=lambda: open_audit_log_window(root)).grid(row=1, column=1, sticky='ew', pady=4, padx=(8, 0))
    themed_button(admin_frame, text='KDV Raporu (VAT Report)', command=lambda: open_vat_report_window(root)).grid(row=2, column=0, sticky='ew', pady=4, padx=(0, 8))
    themed_button(admin_frame, text='Backup/Restore', command=lambda: open_backup_window(root)).grid(row=2, column=1, sticky='ew', pady=4, padx=(8, 0))
    themed_button(admin_frame, text='🗑️ Trash', command=lambda: open_trash_window(root)).grid(row=3, column=0, sticky='ew', pady=4, padx=(0, 8))

    # Make columns expand evenly
    home_container.columnconfigure(0, weight=1)
    home_container.columnconfigure(1, weight=1)
    admin_frame.columnconfigure(0, weight=1)
    admin_frame.columnconfigure(1, weight=1)

    # Example Imports tab content
    themed_button(tab_imports, text='Record Import', command=lambda: open_imports_window(root)).pack(pady=8)
    themed_button(tab_imports, text='View Imports', command=lambda: open_view_imports_window(root)).pack(pady=8)
    themed_button(tab_imports, text='View Inventory', command=lambda: open_view_inventory_window(root)).pack(pady=8)

    # Example Sales tab content
    themed_button(tab_sales, text='Record Sale', command=lambda: open_sales_window(root)).pack(pady=8)
    themed_button(tab_sales, text='View Sales', command=lambda: open_view_sales_window(root)).pack(pady=8)
    themed_button(tab_sales, text='View Returns', command=lambda: open_view_returns_window(root)).pack(pady=8)

    # Example Expenses tab content
    themed_button(tab_expenses, text='Record Expense', command=lambda: open_expenses_window(root)).pack(pady=8)
    themed_button(tab_expenses, text='View Expenses', command=lambda: open_view_expenses_window(root)).pack(pady=8)

    # Example Admin tab content
    themed_button(tab_admin, text='Settings', command=lambda: open_settings_window(root)).pack(pady=8)
    themed_button(tab_admin, text='Product Codes', command=lambda: open_manage_product_codes_window(root)).pack(pady=8)
    themed_button(tab_admin, text='Customers', command=lambda: open_customers_window(root)).pack(pady=8)
    themed_button(tab_admin, text='Suppliers', command=lambda: open_suppliers_window(root)).pack(pady=8)
    themed_button(tab_admin, text='Batch Analytics', command=lambda: open_batch_analytics_window(root)).pack(pady=8)
    themed_button(tab_admin, text='Monthly/Yearly', command=lambda: open_monthly_yearly_analytics_window(root)).pack(pady=8)
    themed_button(tab_admin, text='Audit Log', command=lambda: open_audit_log_window(root)).pack(pady=8)
    themed_button(tab_admin, text='Backup/Restore', command=lambda: open_backup_window(root)).pack(pady=8)
    themed_button(tab_admin, text='Trash', command=lambda: open_trash_window(root)).pack(pady=8)

    root.protocol("WM_DELETE_WINDOW", lambda: safe_shutdown(root))
    root.mainloop()

if __name__ == '__main__':  # pragma: no cover
    main()
