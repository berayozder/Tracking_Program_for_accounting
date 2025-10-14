import tkinter as tk
from tkinter import ttk, messagebox
import db.db as db


def open_settings_window(root):
    win = tk.Toplevel(root)
    win.title('⚙️ Settings')
    win.geometry('420x260')
    try:
        win.minsize(380, 220)
    except Exception:
        pass

    try:
        from .theme import apply_theme, maximize_window
        apply_theme(win)
        maximize_window(win)
    except Exception:
        pass

    container = ttk.Frame(win, padding=16)
    container.pack(fill='both', expand=True)

    ttk.Label(container, text='Currency Settings', font=('', 11, 'bold')).pack(anchor='w', pady=(0, 8))

    form = ttk.Frame(container)
    form.pack(fill='x', pady=(0, 12))

    currencies = ['USD', 'TRY', 'EUR', 'GBP']

    # Base currency
    ttk.Label(form, text='Base currency:').grid(row=0, column=0, sticky='w', padx=(0, 8), pady=6)
    base_var = tk.StringVar(value=(db.get_base_currency() or 'USD').upper())
    base_combo = ttk.Combobox(form, textvariable=base_var, values=currencies, state='readonly', width=10)
    base_combo.grid(row=0, column=1, sticky='w')

    # Default import currency
    ttk.Label(form, text='Default import currency:').grid(row=1, column=0, sticky='w', padx=(0, 8), pady=6)
    def_imp_var = tk.StringVar(value=(db.get_default_import_currency() or 'USD').upper())
    def_imp_combo = ttk.Combobox(form, textvariable=def_imp_var, values=currencies, state='readonly', width=10)
    def_imp_combo.grid(row=1, column=1, sticky='w')

    # Default sale currency
    ttk.Label(form, text='Default sale currency:').grid(row=2, column=0, sticky='w', padx=(0, 8), pady=6)
    def_sale_var = tk.StringVar(value=(db.get_default_sale_currency() or 'TRY').upper())
    def_sale_combo = ttk.Combobox(form, textvariable=def_sale_var, values=currencies, state='readonly', width=10)
    def_sale_combo.grid(row=2, column=1, sticky='w')

    # Default expense currency
    ttk.Label(form, text='Default expense currency:').grid(row=3, column=0, sticky='w', padx=(0, 8), pady=6)
    def_exp_var = tk.StringVar(value=(db.get_default_expense_currency() or db.get_base_currency()).upper())
    def_exp_combo = ttk.Combobox(form, textvariable=def_exp_var, values=currencies, state='readonly', width=10)
    def_exp_combo.grid(row=3, column=1, sticky='w')

    # Info
    ttk.Label(container, text='Note: Profits and analytics are computed in the base currency.', foreground='#666').pack(anchor='w', pady=(4, 12))

    # Actions
    btns = ttk.Frame(container)
    btns.pack(fill='x')

    def on_save():
        try:
            b = (base_var.get() or 'USD').upper()
            di = (def_imp_var.get() or 'USD').upper()
            ds = (def_sale_var.get() or 'TRY').upper()
            db.set_setting('base_currency', b)
            db.set_setting('default_import_currency', di)
            db.set_setting('default_sale_currency', ds)
            db.set_setting('default_expense_currency', (def_exp_var.get() or b).upper())
            messagebox.showinfo('Saved', 'Settings saved. Newly opened windows will use updated defaults.')
            win.destroy()
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save settings: {e}')

    from .theme import themed_button
    themed_button(btns, text='Save', variant='primary', command=on_save).pack(side='right')
    themed_button(btns, text='Cancel', variant='secondary', command=win.destroy).pack(side='right', padx=(0, 8))

    form.columnconfigure(2, weight=1)
