
import sqlite3
import os

def check_migrations():
    db_path = "accounting_data.db"
    
    # If the file doesn't exist yet, that's fine, schema init will create it
    if not os.path.exists(db_path):
        print(f"[INFO] Database {db_path} does not exist yet. Running pure schema init check...")
        import db.schema
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        db.schema.init_db_schema(conn)
        # Check in memory
        cur = conn.cursor()
    else:
        print(f"[INFO] Checking existing database: {db_path}")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # Run schema init to trigger migrations
        import db.schema
        db.schema.init_db_schema(conn)
        cur = conn.cursor()

    # 1. Check expenses columns
    print("Checking 'expenses' table columns...")
    cur.execute("PRAGMA table_info(expenses)")
    cols = {row[1] for row in cur.fetchall()}
    required_expenses = ['amount', 'notes', 'currency', 'deleted']
    missing = [c for c in required_expenses if c not in cols]
    if missing:
        print(f"[ERROR] Missing columns in expenses: {missing}")
    else:
        print("[PASS] All required expenses columns present.")

    # 2. Check sale_batch_allocations columns
    print("Checking 'sale_batch_allocations' table columns...")
    cur.execute("PRAGMA table_info(sale_batch_allocations)")
    cols = {row[1] for row in cur.fetchall()}
    required_sba = ['deleted', 'product_id']
    missing = [c for c in required_sba if c not in cols]
    if missing:
        print(f"[ERROR] Missing columns in sale_batch_allocations: {missing}")
    else:
        print("[PASS] All required sale_batch_allocations columns present.")

    conn.close()

if __name__ == "__main__":
    check_migrations()
