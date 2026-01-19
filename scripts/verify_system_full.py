import sys
import os
import logging
from datetime import datetime
import sqlite3

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('verify_system_full')

# Mock Auth
from db import auth
auth.set_current_user('admin', 'admin')

# Patch Settings to avoid FX issues (Single Currency Mode for Test)
import db.settings
def mock_currency(*args, **kwargs): return 'USD'
db.settings.get_base_currency = mock_currency
db.settings.get_default_sale_currency = mock_currency
db.settings.get_default_import_currency = mock_currency

# Import DB headers
import db
from db.connection import init_db
from db.schema import init_db_schema
# Import all DAOs
from db.imports_dao import add_import, allocate_sale_to_batches
from db.sales_dao import add_sale
from db.expenses_dao import add_expense
from db.returns_dao import insert_return
from db.customers_dao import find_or_create_customer, get_customer_sales_summary
from db.suppliers_dao import find_or_create_supplier, get_supplier_purchases_summary
from db.inventory_dao import get_inventory, update_inventory, rebuild_inventory_from_imports
from db.analytics_dao import build_monthly_overview, get_profit_analysis_by_sale

TEST_DB = 'data/verify_full_system.db'
# Patch DB_PATH
import db.connection
db.connection.DB_PATH = TEST_DB

def setup_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    with db.connection.get_conn() as conn:
        init_db_schema(conn)
    logger.info(f"Initialized test DB at {TEST_DB}")

def test_end_to_end_workflow():
    logger.info("--- Starting End-to-End System Verification ---")
    
    today = datetime.now().strftime('%Y-%m-%d')
    year = int(datetime.now().strftime('%Y'))
    month = datetime.now().strftime('%Y-%m')

    # --- 1. Supplier & Import ---
    logger.info("Step 1: Supplier & Import")
    sup_name = "Global Supplies"
    sup_id = find_or_create_supplier(sup_name)
    assert sup_id, "Failed to create supplier"
    
    # Import 100 units @ $10.00 = $1000 Total Cost
    # Simple import (unit_cost = ordered_price = 10.00)
    cat = "Electronics"
    sub = "Gadget"
    db.set_product_code(cat, sub, "123", "001", next_serial=1)
    
    imp_id = add_import(
        date=today,
        ordered_price=10.0,
        quantity=100,
        supplier=sup_name,
        notes="Batch A",
        category=cat,
        subcategory=sub,
        currency="USD"
    )
    assert imp_id, "Import failed"
    
    # Verify Inventory
    inv = get_inventory()
    item = next((i for i in inv if i['category'] == cat), None)
    assert item['quantity'] == 100.0, f"Inventory mismatch. Expected 100, got {item['quantity']}"
    
    # Verify Supplier Summary
    sup_summary = get_supplier_purchases_summary(sup_id)
    # ordered_price (10) * quantity (100) = 1000
    assert sup_summary['total_purchases'] == 1000.0, f"Supplier summary mismatch. Expected 1000, got {sup_summary['total_purchases']}"

    # --- 2. Customer & Sales ---
    logger.info("Step 2: Customer & Sales")
    cust_name = "John Doe"
    cust_id = find_or_create_customer(cust_name)
    
    # Sell 50 units @ $20.00 = $1000 Revenue
    # COGS = 50 * 10 = $500
    # Profit = $500
    pids = db.generate_product_ids(cat, sub, 1) # Just generates ID string pattern
    # We need specific product IDs for sales if we want to track them individually?
    # db.add_sale takes product_id.
    # We will simulate bulk sale via allocate but add_sale usually is per-item or handled by UI loop.
    # For verification, let's treat it as one "transaction" representing 50 units but we need to call allocate for each? 
    # allocate_sale_to_batches takes 'quantity'.
    
    # Let's say we sell 1 unit 50 times? No, allocate can handle quantity=50.
    # But add_sale usually expects single product_id.
    # The system seems to be designed for serialized tracking (one row per serial).
    # IF we use bulk quantity in allocate, we might confuse the 'sale_batch_allocations' grouping if we don't have matching product_ids?
    # However, 'allocate_sale_to_batches' logic writes 'quantity_from_batch'.
    # Let's simulate selling 50 units as a SINGLE line item with a dummy product_id representing the 'bulk' or 50 distinct IDs?
    # In this system, `sales` table tracks `quantity` per row.
    
    pid_base = "123001" # Mock PID
    
    # Allocating 50 units
    allocs = allocate_sale_to_batches(pid_base, today, cat, sub, 50, 20.0)
    assert len(allocs) > 0, "Allocation failed"
    
    # Add Sale Record
    sale_id = add_sale({
        'date': today,
        'category': cat,
        'subcategory': sub,
        'quantity': 50,
        'selling_price': 1000.0, # 50 * 20
        'product_id': pid_base,
        'customer_id': cust_id,
        'sale_currency': 'USD',
        'vat_rate': 0.0,
        'vat_amount': 0.0,
        'is_vat_inclusive': 0,
        'fx_to_base': 1.0,
        'selling_price_base': 1000.0
    })
    
    # Manually update inventory (UI does this)
    update_inventory(cat, sub, -50)
    
    inv = get_inventory()
    item = next((i for i in inv if i['category'] == cat), None)
    assert item['quantity'] == 50.0, f"Post-sale inventory mismatch. Expected 50, got {item['quantity']}"
    
    # Verify Customer Summary
    cust_summary = get_customer_sales_summary(cust_id)
    assert cust_summary['total_revenue'] == 1000.0, f"Customer spent mismatch. Expected 1000, got {cust_summary['total_revenue']}"

    # --- 3. Expense ---
    logger.info("Step 3: Expenses")
    exp_val = 150.0
    add_expense(
        date=today,
        amount=exp_val,
        category="Rent",
        notes="Shop Rent",
        currency="USD"
    )

    # --- 4. Analytics Check (Mid-flow) ---
    logger.info("Step 4: Mid-flow Analytics")
    overview = build_monthly_overview(year)
    m_data = next((m for m in overview if m['ym'] == month), None)
    
    # Rev: 1000
    # COGS: 500
    # GP: 500
    # Exp: 150
    # Net: 350
    assert m_data['revenue'] == 1000.0, f"Rev Expected 1000, got {m_data['revenue']}"
    assert m_data['cogs'] == 500.0, f"COGS Expected 500, got {m_data['cogs']}"
    assert m_data['net_profit'] == 350.0, f"Net Expected 350, got {m_data['net_profit']}"

    # --- 5. Returns (Refunding 10 units) ---
    logger.info("Step 5: Returns")
    # Refund 10 units. Restock them.
    # Refund Amount = 10 * $20 = $200.
    # COGS Reversed = 10 * $10 = $100.
    #
    # New Stats:
    # Rev: 1000 - 200 = 800
    # COGS: 500 - 100 = 400
    # GP: 400
    # Net: 400 - 150 = 250
    # Inventory: 50 + 10 = 60
    
    for _ in range(10):
        insert_return({
            'return_date': today,
            'product_id': pid_base,
            'refund_amount': 20.0, # 20 per unit
            'refund_currency': 'USD',
            'restock': '1',
            'category': cat,
            'subcategory': sub
        })
    
    # Verify Inventory Restock
    inv = get_inventory()
    item = next((i for i in inv if i['category'] == cat), None)
    assert item['quantity'] == 60.0, f"Restock inventory mismatch. Expected 60, got {item['quantity']}"

    # --- 6. Inventory Rebuild Check ---
    # Ensure rebuild uses batch 'remaining_quantity' correctly
    # Batch was 100. Sold 50 (Rem 50). Restocked 10 (Rem 60).
    # Rebuild should show 60.
    rebuild_inventory_from_imports()
    inv = get_inventory()
    item = next((i for i in inv if i['category'] == cat), None)
    assert item['quantity'] == 60.0, f"Rebuild mismatch. Expected 60, got {item['quantity']}"

    # --- 7. Final Analytics Check ---
    logger.info("Step 7: Final Analytics")
    overview = build_monthly_overview(year)
    m_data = next((m for m in overview if m['ym'] == month), None)
    
    assert m_data['revenue'] == 800.0, f"Final Rev Expected 800, got {m_data['revenue']}"
    assert m_data['cogs'] == 400.0, f"Final COGS Expected 400, got {m_data['cogs']}"
    assert m_data['gross_profit'] == 400.0, f"Final GP Expected 400, got {m_data['gross_profit']}"
    assert m_data['net_profit'] == 250.0, f"Final Net Expected 250, got {m_data['net_profit']}"
    
    print("ALL SYSTEM CHECKS PASSED")

if __name__ == "__main__":
    setup_db()
    test_end_to_end_workflow()
