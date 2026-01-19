import sys
import os
import sqlite3

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import db.expenses_dao as db_exp
import db.connection as db_conn
from db import init_db

def verify_fix():
    print("Initializing DB...")
    init_db()
    
    # Test Data
    date = "2026-01-20"
    amount = 120.0
    vat_rate = 20.0
    vat_inclusive = True # Net = 100, VAT = 20
    
    print("\n--- Testing add_expense with keyword args ---")
    try:
        exp_id = db_exp.add_expense(
            date=date,
            amount=amount,
            category="Test Fix",
            notes="Testing VAT args",
            vat_rate=vat_rate,
            vat_inclusive=vat_inclusive,
            currency="USD"
        )
        print(f"Expense added successfully with ID: {exp_id}")
    except TypeError as e:
        print(f"FAILED: add_expense raised TypeError: {e}")
        return

    # Verify data
    with db_conn.get_cursor() as (conn, cur):
        cur.execute("SELECT amount, vat_rate, vat_amount, is_vat_inclusive, net_amount, gross_amount FROM expenses WHERE id=?", (exp_id,))
        row = cur.fetchone()
        print(f"Row data: {dict(row)}")
        assert row['amount'] == 120.0
        assert row['vat_rate'] == 20.0
        assert abs(row['vat_amount'] - 20.0) < 0.01
        assert row['is_vat_inclusive'] == 1
        assert abs(row['net_amount'] - 100.0) < 0.01
        assert row['gross_amount'] == 120.0
        print("Data verification PASSED")

    print("\n--- Testing edit_expense with keyword args ---")
    new_amount = 240.0 # Net 200, VAT 40
    try:
        db_exp.edit_expense(
            expense_id=exp_id,
            date=date,
            amount=new_amount,
            category="Test Fix Edited",
            notes="Edited notes",
            vat_rate=vat_rate,
            vat_inclusive=vat_inclusive,
            currency="USD"
        )
        print("Expense edited successfully")
    except TypeError as e:
        print(f"FAILED: edit_expense raised TypeError: {e}")
        return

    # Verify data after edit
    with db_conn.get_cursor() as (conn, cur):
        cur.execute("SELECT amount, vat_rate, vat_amount, is_vat_inclusive, net_amount, gross_amount FROM expenses WHERE id=?", (exp_id,))
        row = cur.fetchone()
        print(f"Row data after edit: {dict(row)}")
        assert row['amount'] == 240.0
        assert abs(row['vat_amount'] - 40.0) < 0.01
        assert abs(row['net_amount'] - 200.0) < 0.01
        assert row['gross_amount'] == 240.0
        print("Edit verification PASSED")

if __name__ == "__main__":
    verify_fix()
