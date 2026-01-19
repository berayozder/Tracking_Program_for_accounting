
import os
import sys
import sqlite3
from datetime import datetime

# Adjust path to include project root
sys.path.append(os.getcwd())

from db.connection import get_cursor, init_db
from db.returns_dao import list_returns
from db.sales_dao import add_sale
from db.imports_dao import allocate_sale_to_batches, create_import_batch, update_inventory

def verify_returns_schema():
    print("--- Verifying Returns Schema ---")
    try:
        # This will trigger schema init if not up to date
        with get_cursor() as (conn, cur):
            # We need to manually call init_db_schema if main.py usually does it
            from db.schema import init_db_schema
            init_db_schema(conn)
        
        # Test listing returns (should fail if 'deleted' column missing)
        returns = list_returns()
        print(f"✅ list_returns() successful. Found {len(returns)} returns.")
    except Exception as e:
        print(f"❌ list_returns() failed: {e}")
        raise

def verify_sales_flow():
    print("\n--- Verifying Sales Flow ---")
    try:
        # Setup: Create a dummy import batch so we have inventory
        cat = "TestCat"
        sub = "TestSub"
        pid = f"TestPID_{datetime.now().timestamp()}"
        
        with get_cursor() as (conn, cur):
            # Create import batch
            create_import_batch(
                import_id=9999, 
                date='2025-01-01', 
                category=cat, 
                subcategory=sub, 
                quantity=10, 
                unit_cost=100.0, 
                unit_cost_base=100.0,
                supplier='TestSupp', 
                cur=cur
            )
            update_inventory(cat, sub, 10, cur=cur)
        
        # 1. Insert Sale (Simulate UI first step)
        sale_data = {
            'date': '2025-01-02',
            'category': cat,
            'subcategory': sub,
            'quantity': 1,
            'selling_price': 150.0,
            'sale_currency': 'TRY',
            'product_id': pid,
            'customer_id': 'CUST_1',
            'fx_to_base': 1.0,
            'selling_price_base': 150.0
        }
        sale_id = add_sale(sale_data)
        if not sale_id:
            print("❌ add_sale failed to return ID.")
            return

        print(f"✅ add_sale successful. Sale ID: {sale_id}")

        # 2. Allocate (Simulate UI second step)
        allocations = allocate_sale_to_batches(
            product_id=pid,
            sale_date='2025-01-02',
            category=cat,
            subcategory=sub,
            quantity=1,
            unit_sale_price_base=150.0,
            sale_id=sale_id # Passing the ID!
        )
        
        print(f"✅ allocate_sale_to_batches successful. Allocations: {len(allocations)}")
        if allocations and allocations[0].get('batch_id'):
            print("   -> Allocation linked to batch properly.")
        else:
             print("   -> Allocation outcome ambiguous (maybe no inventory found?).")

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_returns_schema()
    verify_sales_flow()
