import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from db.expenses_dao import get_expenses
from db.imports_dao import get_imports
from core.vat_utils import compute_vat
import csv
from datetime import datetime

def open_vat_report_window(root):
    window = tk.Toplevel(root)
    window.title("KDV Raporu (VAT Report)")
    window.geometry("950x600")

    nb = ttk.Notebook(window)
    nb.pack(fill='both', expand=True)

    for tab_name, fetch_func in [("Expenses", get_expenses), ("Imports", get_imports)]:
        frame = ttk.Frame(nb, padding=8)
        nb.add(frame, text=tab_name)

        # --- Filter Frame ---
        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill='x', pady=4)

        ttk.Label(filter_frame, text="Start Date (YYYY-MM-DD):").pack(side='left')
        start_entry = ttk.Entry(filter_frame, width=12)
        start_entry.pack(side='left', padx=4)
        ttk.Label(filter_frame, text="End Date (YYYY-MM-DD):").pack(side='left', padx=(8,0))
        end_entry = ttk.Entry(filter_frame, width=12)
        end_entry.pack(side='left', padx=4)
        
        ttk.Label(filter_frame, text="Category:").pack(side='left', padx=(8,0))
        category_entry = ttk.Entry(filter_frame, width=15)
        category_entry.pack(side='left', padx=4)

        # --- Treeview ---
        tree = ttk.Treeview(frame, columns=("date", "category", "net", "vat", "gross", "rate", "incl"), show="headings")
        tree.pack(fill='both', expand=True, pady=4)

        for col, txt in [("date", "Date"), ("category", "Category"), ("net", "Net Amount"),
                         ("vat", "VAT Amount"), ("gross", "Gross Amount"), ("rate", "VAT Rate (%)"),
                         ("incl", "VAT Inclusive")]:
            tree.heading(col, text=txt)

        # --- Totals Label ---
        total_lbl = ttk.Label(frame, text="", font=("Arial", 12, "bold"))
        total_lbl.pack(pady=4)

        # --- CSV Export Button ---
        def export_csv():
            file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                     filetypes=[("CSV Files", "*.csv")],
                                                     title="Save VAT Report")
            if not file_path:
                return
            try:
                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Date", "Category", "Net", "VAT", "Gross", "VAT Rate (%)", "Inclusive"])
                    for row_id in tree.get_children():
                        writer.writerow(tree.item(row_id)['values'])
                messagebox.showinfo("Export Complete", f"VAT report saved to {file_path}")
            except Exception as e:
                messagebox.showerror("Export Failed", str(e))

        ttk.Button(frame, text="Export CSV", command=export_csv).pack(pady=4)

        # --- Refresh Function ---
        def refresh_tree():
            tree.delete(*tree.get_children())
            try:
                rows = fetch_func()
                net_total = vat_total = gross_total = 0.0
                start_date = start_entry.get().strip()
                end_date = end_entry.get().strip()
                category_filter = category_entry.get().strip().lower()

                for r in rows:
                    # Filter by date
                    r_date = r.get('date')
                    if start_date:
                        try:
                            if datetime.strptime(r_date, "%Y-%m-%d") < datetime.strptime(start_date, "%Y-%m-%d"):
                                continue
                        except:
                            pass
                    if end_date:
                        try:
                            if datetime.strptime(r_date, "%Y-%m-%d") > datetime.strptime(end_date, "%Y-%m-%d"):
                                continue
                        except:
                            pass
                    # Filter by category
                    r_cat = r.get('category', r.get('subcategory', ''))
                    if category_filter and category_filter not in r_cat.lower():
                        continue

                    # Compute VAT
                    amount = r.get('amount') or r.get('net_amount') or 0
                    vat_rate = r.get('vat_rate', 0)
                    is_incl = r.get('is_vat_inclusive', True)
                    net, vat = compute_vat(amount, vat_rate, is_incl)
                    gross = net + vat

                    tree.insert('', 'end', values=(
                        r_date,
                        r_cat,
                        f"{net:.2f}",
                        f"{vat:.2f}",
                        f"{gross:.2f}",
                        f"{vat_rate:.2f}",
                        "Yes" if is_incl else "No"
                    ))

                    net_total += net
                    vat_total += vat
                    gross_total += gross

                total_lbl.config(text=f"Toplam Net: {net_total:.2f}   Toplam KDV: {vat_total:.2f}   Toplam Brüt: {gross_total:.2f}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        # Bind filter refresh
        ttk.Button(filter_frame, text="Filter", command=refresh_tree).pack(side='left', padx=6)

        # Initial population
        refresh_tree()
