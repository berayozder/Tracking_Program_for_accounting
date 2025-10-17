import tkinter as tk
from tkinter import ttk
from datetime import datetime
import db as db
from .theme import apply_theme, stripe_treeview, maximize_window


def open_monthly_yearly_analytics_window(root):
    win = tk.Toplevel(root)
    win.title('📆 Monthly / Yearly Analysis')
    win.geometry('950x620')
    win.minsize(860, 520)
    try:
        maximize_window(win)
    except Exception:
        pass
    apply_theme(win)

    container = ttk.Frame(win, padding=16)
    container.pack(fill='both', expand=True)

    # Controls
    ctrl = ttk.Frame(container)
    ctrl.pack(fill='x', pady=(0, 12))
    ttk.Label(ctrl, text='Year:', font=('', 10, 'bold')).pack(side='left')

    this_year = int(datetime.now().strftime('%Y'))
    years = [str(y) for y in range(this_year, this_year - 6, -1)]
    year_var = tk.StringVar(value=str(this_year))
    year_cb = ttk.Combobox(ctrl, textvariable=year_var, values=years, width=8, state='readonly')
    year_cb.pack(side='left', padx=(8, 16))

    btn_refresh = ttk.Button(ctrl, text='Refresh', command=lambda: refresh_all())
    btn_refresh.pack(side='left')

    # Tabs
    nb = ttk.Notebook(container)
    tab_monthly = ttk.Frame(nb)
    tab_yearly = ttk.Frame(nb)
    nb.add(tab_monthly, text='📅 Monthly Overview')
    nb.add(tab_yearly, text='📈 Yearly Summary')
    nb.pack(fill='both', expand=True)

    # Base-currency note
    note = ttk.Label(container, text=f"Note: All amounts shown are in base currency ({db.get_base_currency()}).", foreground='#666')
    note.pack(fill='x', pady=(6, 0))

    # Monthly table (with returns impact)
    monthly_cols = ['Month', 'Revenue', 'COGS', 'Gross Profit', 'Expenses', 'Net Profit', 'Items Sold', 'Return Impact', 'Items Returned']
    monthly_tree = ttk.Treeview(tab_monthly, columns=monthly_cols, show='headings', style='Treeview')
    for c in monthly_cols:
        anchor = 'e' if c not in ('Month',) else 'center'
        width = 120 if c not in ('Month',) else 95
        monthly_tree.heading(c, text=c, anchor='center')
        monthly_tree.column(c, anchor=anchor, width=width, minwidth=70)
    vsm = ttk.Scrollbar(tab_monthly, orient='vertical', command=monthly_tree.yview)
    monthly_tree.configure(yscrollcommand=vsm.set)
    monthly_tree.pack(side='left', fill='both', expand=True)
    vsm.pack(side='right', fill='y')
    # Small badge/note near table
    ttk.Label(tab_monthly, text='Net of returns applied', foreground='#666').pack(fill='x', padx=4, pady=(0, 6))

    # Yearly table (with returns impact)
    yearly_cols = ['Year', 'Revenue', 'COGS', 'Gross Profit', 'Expenses', 'Net Profit', 'Imports Value', 'Items Sold', 'Return Impact', 'Items Returned']
    yearly_tree = ttk.Treeview(tab_yearly, columns=yearly_cols, show='headings', style='Treeview')
    for c in yearly_cols:
        anchor = 'e' if c not in ('Year',) else 'center'
        width = 120 if c != 'Year' else 85
        yearly_tree.heading(c, text=c, anchor='center')
        yearly_tree.column(c, anchor=anchor, width=width, minwidth=70)
    vsy = ttk.Scrollbar(tab_yearly, orient='vertical', command=yearly_tree.yview)
    yearly_tree.configure(yscrollcommand=vsy.set)
    yearly_tree.pack(side='left', fill='both', expand=True)
    vsy.pack(side='right', fill='y')
    ttk.Label(tab_yearly, text='Net of returns applied', foreground='#666').pack(fill='x', padx=4, pady=(0, 6))

    def format_money(v):
        try:
            return f"${float(v):.2f}"
        except Exception:
            return "$0.00"

    def refresh_monthly():
        for i in monthly_tree.get_children():
            monthly_tree.delete(i)
        try:
            y = int(year_var.get())
        except Exception:
            y = this_year
        rows = db.build_monthly_overview(y)
        total_rev = total_cogs = total_gp = total_exp = total_net = total_items = total_ret_net = total_items_ret = 0.0
        for r in rows:
            ym = r['ym']
            mm = ym[5:7]
            display = f"{ym}"
            total_rev += r['revenue']
            total_cogs += r['cogs']
            total_gp += r['gross_profit']
            total_exp += r['expenses']
            total_net += r['net_profit']
            total_items += r['items_sold']
            total_ret_net += r.get('returns_net_impact', 0.0)
            total_items_ret += r.get('items_returned', 0.0)
            vals = [
                display,
                format_money(r['revenue']),
                format_money(r['cogs']),
                format_money(r['gross_profit']),
                format_money(r['expenses']),
                format_money(r['net_profit']),
                f"{int(r['items_sold'])}",
                format_money(r.get('returns_net_impact', 0.0)),
                f"{int(r.get('items_returned', 0.0))}",
            ]
            iid = monthly_tree.insert('', 0, values=vals)
            # Color rows: net < 0 -> danger, high gp -> success
            if r['net_profit'] < 0:
                stripe_treeview(monthly_tree, iid, 'danger')
            elif r['gross_profit'] > 0 and r['gross_profit'] >= 0.3 * max(1.0, r['revenue']):
                stripe_treeview(monthly_tree, iid, 'success')
            # Totals footer
            monthly_tree.insert('', 0, values=[
                'TOTAL',
                format_money(total_rev),
                format_money(total_cogs),
                format_money(total_gp),
                format_money(total_exp),
                format_money(total_net),
                f"{int(total_items)}",
                format_money(total_ret_net),
                f"{int(total_items_ret)}",
            ])
        try:
            stripe_treeview(monthly_tree)
        except Exception:
            pass

    def refresh_yearly():
        for i in yearly_tree.get_children():
            yearly_tree.delete(i)
        rows = db.build_yearly_summary()
        for r in rows:
            vals = [
                r['year'],
                format_money(r['revenue']),
                format_money(r['cogs']),
                format_money(r['gross_profit']),
                format_money(r['expenses']),
                format_money(r['net_profit']),
                format_money(r['imports_value']),
                f"{int(r['items_sold'])}",
                format_money(r.get('returns_net_impact', 0.0)),
                f"{int(r.get('items_returned', 0.0))}",
            ]
            iid = yearly_tree.insert('', 0, values=vals)
            if r['net_profit'] < 0:
                stripe_treeview(yearly_tree, iid, 'danger')
            elif r['gross_profit'] > 0 and r['gross_profit'] >= 0.3 * max(1.0, r['revenue']):
                stripe_treeview(yearly_tree, iid, 'success')
        try:
            stripe_treeview(yearly_tree)
        except Exception:
            pass

    def refresh_all():
        refresh_monthly()
        refresh_yearly()

    year_cb.bind('<<ComboboxSelected>>', lambda e: refresh_all())

    refresh_all()

    # Drill-down: Double-click month/year to show Return Impact details
    def show_month_return_impact(event=None):
        sel = monthly_tree.selection()
        if not sel:
            return
        vals = monthly_tree.item(sel[0])['values']
        if not vals:
            return
        month = str(vals[0])
        if month == 'TOTAL':
            return
        # Build details from db.get_monthly_return_impact
        year = month[:4]
        impact = db.get_monthly_return_impact(int(year)).get(month, {})
        _open_return_impact_dialog(win, f"Return Impact - {month}", impact)

    def show_year_return_impact(event=None):
        sel = yearly_tree.selection()
        if not sel:
            return
        vals = yearly_tree.item(sel[0])['values']
        if not vals:
            return
        year = str(vals[0])
        impact = db.get_yearly_return_impact().get(year, {})
        _open_return_impact_dialog(win, f"Return Impact - {year}", impact)

    def _open_return_impact_dialog(parent, title, impact_dict):
        dlg = tk.Toplevel(parent)
        dlg.title(title)
        dlg.geometry('420x240')
        try:
            apply_theme(dlg)
        except Exception:
            pass
        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill='both', expand=True)
        refunds = float(impact_dict.get('returns_refunds', 0.0) or 0.0)
        cogs_rev = float(impact_dict.get('returns_cogs_reversed', 0.0) or 0.0)
        items_ret = int(float(impact_dict.get('items_returned', 0.0) or 0.0))
        net_imp = cogs_rev - refunds
        rows = [
            ("Refunds (reduce revenue)", refunds),
            ("COGS Reversed (restock)", cogs_rev),
            ("Net Impact", net_imp),
            ("Items Returned", items_ret),
        ]
        for label, val in rows:
            r = ttk.Frame(frame)
            r.pack(fill='x', pady=4)
            ttk.Label(r, text=label).pack(side='left')
            ttk.Label(r, text=f"{format_money(val) if label != 'Items Returned' else val}", anchor='e').pack(side='right')
        ttk.Button(frame, text='Close', command=dlg.destroy).pack(pady=(12,0))

    monthly_tree.bind('<Double-1>', show_month_return_impact)
    yearly_tree.bind('<Double-1>', show_year_return_impact)
