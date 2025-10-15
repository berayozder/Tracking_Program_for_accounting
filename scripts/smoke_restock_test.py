import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from db import db

# Prepare DB
db.init_db()
conn = db.get_conn()
cur = conn.cursor()
# Clean tables for test
cur.execute("DELETE FROM sale_batch_allocations")
cur.execute("DELETE FROM import_batches")
cur.execute("DELETE FROM returns")
conn.commit()

# Insert an import batch
cur.execute('''INSERT INTO import_batches(import_id, batch_date, category, subcategory, original_quantity, remaining_quantity, unit_cost, unit_cost_orig)
               VALUES(?,?,?,?,?,?,?,?)''', (1, '2025-01-01', 'cat', 'sub', 10.0, 9.0, 2.0, 2.0))
batch_id = cur.lastrowid
# Insert a sale allocation for 1 unit
cur.execute('''INSERT INTO sale_batch_allocations(product_id, sale_date, category, subcategory, batch_id, quantity_from_batch, unit_cost, unit_sale_price, profit_per_unit)
               VALUES(?,?,?,?,?,?,?,?,?)''', ('P-TEST', '2025-10-15', 'cat', 'sub', batch_id, 1.0, 2.0, 5.0, 3.0))
conn.commit()

print('Before:')
print('Batch report:', db.get_batch_utilization_report())
print('Profit analysis:', db.get_profit_analysis_by_sale())

# Insert restock return via insert_return
ret = {
    'return_date': '2025-10-15',
    'product_id': 'P-TEST',
    'sale_date': '2025-10-15',
    'category': 'cat',
    'subcategory': 'sub',
    'unit_price': 5.0,
    'selling_price': 5.0,
    'platform': 'test',
    'refund_amount': 5.0,
    'refund_currency': db.get_default_sale_currency(),
    'restock': 1,
    'reason': 'test restock',
    'doc_paths': ''
}

print('\nInserting restock return...')
res = db.insert_return(ret)
print('insert_return result:', res)

print('\nAfter:')
print('Batch report:', db.get_batch_utilization_report())
print('Profit analysis:', db.get_profit_analysis_by_sale())

print('\nDone')
