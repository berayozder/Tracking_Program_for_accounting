import sys
from pathlib import Path

import os
import tempfile
import sqlite3
import importlib
import shutil


def setup_temp_db(tmp_path, monkeypatch):
    # create a temporary data directory and DB path
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_file = data_dir / "app.db"
    # monkeypatch DB_PATH in db.connection
    conn_mod = importlib.import_module('db.connection')
    monkeypatch.setattr(conn_mod, 'DATA_DIR', data_dir)
    monkeypatch.setattr(conn_mod, 'DB_PATH', db_file)
    return conn_mod, db_file


def test_db_end_to_end(tmp_path, monkeypatch):
    # Ensure project root is on sys.path so `import db` works under pytest
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    # Ensure we import fresh modules after monkeypatching DB_PATH
    conn_mod, db_file = setup_temp_db(tmp_path, monkeypatch)

    # Import db package and initialize DB schema via its init helper
    db = importlib.import_module('db')
    # init_db should be idempotent and create schema when needed
    if hasattr(db, 'init_db'):
        db.init_db()
    else:
        # Fall back to direct connection to ensure DB file is created
        conn = conn_mod.get_conn()
        conn.close()

    # Basic auth tests
    auth = importlib.import_module('db.auth')
    assert not auth.users_exist()
    ok = auth.create_user('testuser', 'password123', role='admin')
    assert ok is True
    assert auth.users_exist() is True
    assert auth.verify_user('testuser', 'password123') is True

    # Settings tests
    settings = importlib.import_module('db.settings')
    assert settings.get_base_currency()  # default value exists
    settings.set_setting('test.key', 'value1')
    assert settings.get_setting('test.key') == 'value1'

    # Imports/batches/allocations flow
    imports = importlib.import_module('db.imports_dao')
    db = importlib.import_module('db')

    # Create a fake import and batch using DAO
    conn = db.get_conn()
    cur = conn.cursor()
    # insert a top-level import
    cur.execute("INSERT INTO imports(date, ordered_price, quantity, supplier, category, subcategory, currency) VALUES (?,?,?,?,?,?,?)",
                ('2025-01-01', 10.0, 10.0, 'S1', 'cat', 'sub', 'TRY'))
    imp_id = cur.lastrowid
    conn.commit()
    conn.close()

    # create import batch via DAO
    bid = imports.create_import_batch(imp_id, '2025-01-01', 'cat', 'sub', 10.0, 1.0, 'S1', '', 'TRY', 1.0, 1.0, 10.0)
    assert isinstance(bid, int)

    # Add a sale row using sales DAO so sales are recorded in DB
    sales_mod = importlib.import_module('db.sales_dao')
    sale_row = {
        'date': '2025-10-15',
        'category': 'cat',
        'subcategory': 'sub',
        'quantity': 1.0,
        'selling_price': 15.0,
        'platform': 'test',
        'product_id': 'P-1',
        'customer_id': '',
        'sale_currency': settings.get_default_sale_currency()
    }
    sale_id = sales_mod.add_sale(sale_row)
    # add_sale returns new id (>0) on success
    assert isinstance(sale_id, int) and sale_id > 0

    # allocate the sale to available batches (this will update import_batches.remaining_quantity)
    allocs = imports.allocate_sale_to_batches('P-1', '2025-10-15', 'cat', 'sub', 1.0, 15.0)
    assert isinstance(allocs, list) and len(allocs) >= 1

    # Ensure at least one allocation references our batch id and decreased remaining_quantity
    found = False
    for a in allocs:
        if a.get('batch_id') == bid:
            found = True
            assert a.get('quantity_allocated') == 1 or float(a.get('quantity_allocated') or 0) >= 1
    assert found is True

    # Check remaining_quantity on the batch decreased by allocated amount (10 -> 9)
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute('SELECT remaining_quantity FROM import_batches WHERE id=?', (bid,))
    row = cur.fetchone()
    conn.close()
    assert row is not None
    remaining = float(row['remaining_quantity'] if isinstance(row, dict) else row[0])
    assert remaining == 9.0

    # Insert a return and ensure returns table can be read
    returns_mod = importlib.import_module('db.returns_dao') if importlib.util.find_spec('db.returns_dao') else None
    # If returns DAO exists, try inserting via generic SQL otherwise skip
    if returns_mod and hasattr(returns_mod, 'insert_return'):
        ret_id = returns_mod.insert_return({
            'return_date': '2025-10-16',
            'product_id': 'P-1',
            'sale_date': '2025-10-15',
            'category': 'cat',
            'subcategory': 'sub',
            'unit_price': 15.0,
            'selling_price': 15.0,
            'platform': 'test',
            'refund_amount': 15.0,
            'refund_currency': settings.get_default_sale_currency(),
            'restock': 1,
            'reason': 'test',
            'doc_paths': ''
        })
        # insert_return returns dict with id on success
        assert ret_id is not None

    # Basic analytics read access: batch utilization and profit analysis
    analytics_mod = importlib.import_module('db.analytics_dao') if importlib.util.find_spec('db.analytics_dao') else None
    # Call analytics functions from analytics module if present, otherwise fall back to db package
    try:
        if analytics_mod is not None:
            _ = analytics_mod.get_batch_utilization_report()
            _ = analytics_mod.get_profit_analysis_by_sale()
        else:
            if hasattr(db, 'get_batch_utilization_report'):
                _ = db.get_batch_utilization_report()
            if hasattr(db, 'get_profit_analysis_by_sale'):
                _ = db.get_profit_analysis_by_sale()
    except Exception:
        # Fail the test if these functions raise
        raise

    # cleanup: remove temp DB file
    try:
        if db_file.exists():
            db_file.unlink()
    except Exception:
        pass
