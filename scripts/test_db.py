# test_db.py
# Run with: python scripts/test_db.py

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import db


def test_expense_crud():
    print("\n[TEST] Expense CRUD")
    # Add
    db.add_expense('2025-10-26', 100.0, False, None, 'TestCat', 'TestNote', document_path='', import_ids=None, currency='USD')
    expenses = db.get_expenses(limit=1)
    assert expenses, "Expense not added"
    expense_id = expenses[0]['id']
    print(f"Added expense id: {expense_id}")

    # Update
    db.edit_expense(expense_id, '2025-10-27', 200.0, False, None, 'TestCat2', 'UpdatedNote', document_path='', import_ids=None, currency='USD')
    updated = db.get_expenses(limit=1)[0]
    assert updated['amount'] == 200.0 and 'UpdatedNote' in updated['notes'], "Expense not updated"
    print(f"Updated expense id: {expense_id}")

    # Delete
    db.delete_expense(expense_id)
    deleted = db.get_expenses(limit=10)
    assert all(e['id'] != expense_id for e in deleted), "Expense not deleted (soft)"
    print(f"Deleted expense id: {expense_id}")

    # Undelete
    db.undelete_expense(expense_id)
    undeleted = db.get_expenses(limit=10)
    assert any(e['id'] == expense_id for e in undeleted), "Expense not undeleted"
    print(f"Undeleted expense id: {expense_id}")


def test_import_crud():
    print("\n[TEST] Import CRUD")
    # Add
    db.add_import('2025-10-26', 100.0, 10, 'TestSupplier', 'TestNote', 'TestCat', 'TestSub', 'USD', None, None, 0.0, False)
    imports = db.get_imports(limit=1)
    assert imports, "Import not added"
    import_id = imports[0]['id']
    print(f"Added import id: {import_id}")

    # Delete
    db.delete_import(import_id)
    deleted = db.get_imports(limit=10)
    assert all(i['id'] != import_id for i in deleted), "Import not deleted (soft)"
    print(f"Deleted import id: {import_id}")

    # Undelete
    db.undelete_import(import_id)
    undeleted = db.get_imports(limit=10)
    assert any(i['id'] == import_id for i in undeleted), "Import not undeleted"
    print(f"Undeleted import id: {import_id}")


def test_expense_import_currency_conversion():
    print("\n[TEST] Expense/Import Currency Conversion")
    # Add an import in USD
    db.add_import('2025-10-26', 100.0, 10, 'TestSupplier', 'TestNote', 'TestCat', 'TestSub', 'USD', None, None, 0.0, False)
    imports = db.get_imports(limit=1)
    assert imports, "Import not added"
    import_id = imports[0]['id']
    print(f"Added import id: {import_id} (USD)")

    # Add an expense in TRY linked to this import
    db.add_expense('2025-10-27', 1000.0, True, import_id, 'TestCat', 'ExpenseNote', document_path='', import_ids=[import_id], currency='TRY')
    expenses = db.get_expenses(limit=1)
    assert expenses, "Expense not added"
    expense_id = expenses[0]['id']
    print(f"Added expense id: {expense_id} (TRY)")

    # Recompute batches (should be automatic, but call explicitly for test)
    db.recompute_import_batches(import_id)

    # Fetch all batches for this category/subcategory and print them
    batch_info = db.get_available_batches('TestCat', 'TestSub')
    assert batch_info, "No batch info found"
    print("All batches for TestCat/TestSub:")
    for b in batch_info:
        print(b)
    # Filter for the batch with the correct import_id
    batches_for_import = [b for b in batch_info if b.get('import_id') == import_id]
    assert batches_for_import, f"No batch found for import_id={import_id}"
    batch = batches_for_import[0]
    print(f"Selected batch for import_id={import_id}: {batch}")
    # Check that unit_cost_base is not equal to unit_cost if currencies differ
    if batch['currency'] != db.get_base_currency():
        assert batch['unit_cost_base'] != batch['unit_cost'], "unit_cost_base should differ from unit_cost when currencies differ"
    print("Currency conversion for expense/import is handled correctly.")


def main():
    # Log in as admin for testing
    try:
        db.verify_user('admin', 'a')
        print('[DEBUG] Logged in as admin')
    except Exception as e:
        print(f'[DEBUG] Admin login failed: {e}')

    # Patch require_admin for testing (bypass admin check)
    import db.expenses_dao
    import db.imports_dao
    db.expenses_dao.require_admin = lambda *a, **kw: None
    db.imports_dao.require_admin = lambda *a, **kw: None
    db.require_admin = lambda *a, **kw: None

    test_expense_crud()
    test_import_crud()
    test_expense_import_currency_conversion()
    print("\nAll CRUD tests passed!")

if __name__ == "__main__":
    main()
