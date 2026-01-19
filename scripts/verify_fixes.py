
import sqlite3
import os
import sys

# Configure path to be able to import from db/core
sys.path.append('/Users/berayozder/Desktop/Side_projects/Tracking_Program_for_accounting')
from db.connection import DB_PATH, init_db

def verify_schema_migrations():
    print(f"Connecting to database at {DB_PATH}...")
    init_db()  # This triggers the schema migration logic
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("\n--- Verifying sale_batch_allocations columns ---")
    cur.execute("PRAGMA table_info(sale_batch_allocations)")
    columns = [row['name'] for row in cur.fetchall()]
    
    expected_alloc_cols = ['quantity_from_batch', 'unit_cost', 'unit_sale_price', 'profit_per_unit']
    missing_alloc = [col for col in expected_alloc_cols if col not in columns]
    
    if missing_alloc:
        print(f"FAILED: Missing columns in sale_batch_allocations: {missing_alloc}")
    else:
        print("SUCCESS: All expected columns present in sale_batch_allocations.")

    print("\n--- Verifying returns columns ---")
    cur.execute("PRAGMA table_info(returns)")
    columns = [row['name'] for row in cur.fetchall()]
    
    expected_return_cols = ['unit_price', 'selling_price', 'platform', 'refund_amount', 
                            'refund_currency', 'refund_amount_base', 'restock', 'reason', 
                            'doc_paths', 'restock_processed']
    missing_returns = [col for col in expected_return_cols if col not in columns]
    
    if missing_returns:
        print(f"FAILED: Missing columns in returns: {missing_returns}")
    else:
        print("SUCCESS: All expected columns present in returns.")

    conn.close()

def verify_crypto_import():
    print("\n--- Verifying crypto_utils import ---")
    try:
        from core import crypto_utils
        print("SUCCESS: core.crypto_utils imported successfully.")
        
        # Check behavior when cryptography is missing (simulated if it was actually missing)
        # But here we just want to ensure the module doesn't crash on load
    except ImportError as e:
        print(f"FAILED: Import error: {e}")
    except Exception as e:
        print(f"FAILED: Unexpected error during import: {e}")

if __name__ == "__main__":
    verify_schema_migrations()
    verify_crypto_import()
