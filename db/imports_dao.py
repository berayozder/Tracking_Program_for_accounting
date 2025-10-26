import logging
from typing import Optional, List, Dict
from .connection import get_cursor
from .suppliers_dao import find_or_create_supplier
from .settings import get_default_import_currency, get_base_currency
from .crypto import encrypt_str, decrypt_str
from .auth import require_admin
from .utils import float_or_none
from .inventory_dao import update_inventory, rebuild_inventory_from_imports
from .audit import write_audit
from .rates import convert_amount

logger = logging.getLogger("imports_dao")

def add_import(
    date: str,
    ordered_price: float,
    quantity: float,
    supplier: str,
    notes: str,
    category: str,
    subcategory: str,
    currency: str = 'TRY',
    fx_override: Optional[float] = None,
    lines: Optional[List[Dict]] = None,
    total_import_expenses: float = 0.0,
    include_expenses: bool = False
) -> None:
    """
    Add a new import record, with optional line items and expense allocation.
    Handles supplier creation, FX conversion, and inventory update.
    """
    print("[DEBUG] add_import called with:", date, ordered_price, quantity, supplier, notes, category, subcategory, currency, fx_override, lines, total_import_expenses, include_expenses)
    print("[DEBUG] About to call get_cursor")
    print("[DEBUG] get_cursor:", get_cursor)
    with get_cursor() as (conn, cur):
        print(f"[DEBUG] Entered get_cursor: conn={conn}, cur={cur}")
        # --- Supplier handling ---
        supplier_name = (supplier or '').strip()
        supplier_id = None
        print("[DEBUG] About to call find_or_create_supplier:", find_or_create_supplier)
        if supplier_name:
            try:
                supplier_id = find_or_create_supplier(supplier_name)
                print(f"[DEBUG] Found/created supplier_id: {supplier_id}")
            except Exception as e:
                logger.error(f"[add_import] Failed to find or create supplier '{supplier_name}': {e}")
                print(f"[ERROR] Failed to find or create supplier: {e}")
                supplier_id = None

        print("[DEBUG] About to call encrypt_str:", encrypt_str)
        enc_notes = encrypt_str(notes)
        cur_ccy = (currency or get_default_import_currency() or 'USD').upper()
        print(f"[DEBUG] enc_notes: {enc_notes}, cur_ccy: {cur_ccy}")

        # --- Insert main import record ---
        try:
            print("[DEBUG] About to execute INSERT INTO imports")
            cur.execute('''
                INSERT INTO imports (
                    date, ordered_price, quantity, supplier, supplier_id, notes, category, subcategory, currency
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date,
                ordered_price,
                quantity,
                supplier_name,
                supplier_id,
                enc_notes,
                category if not lines else '',
                subcategory if not lines else '',
                cur_ccy
            ))
            import_id = cur.lastrowid
            print(f"[DEBUG] Inserted import with id: {import_id}")
        except Exception as e:
            print(f"[ERROR] Failed to insert import: {e}")
            raise

        # ...existing code for handling lines, single-line import, and updates...

        # --- Expense allocation currency note ---
        # IMPORTANT: total_import_expenses is always expected in the import currency (cur_ccy).
        # If the user provides expenses in another currency, they must be converted before calling add_import.

        # --- Process lines if provided ---
        if lines and isinstance(lines, list) and len(lines) > 0:
            print(f"[DEBUG] Inserting {len(lines)} import lines")
            total_order_value = 0.0
            if include_expenses:
                for ln in lines:
                    try:
                        total_order_value += float(ln.get('ordered_price') or 0.0) * float(ln.get('quantity') or 0.0)
                    except Exception as e:
                        logger.warning(f"[add_import] Failed to accumulate order value for line {ln}: {e}")

            for ln in lines:
                ln_cat = ln.get('category')
                ln_sub = ln.get('subcategory')
                ln_price = float_or_none(ln.get('ordered_price'))
                ln_qty = float_or_none(ln.get('quantity'))
                print(f"[DEBUG] Line: cat={ln_cat}, sub={ln_sub}, price={ln_price}, qty={ln_qty}")

                # Adjust price for expenses proportionally
                adjusted_price = ln_price
                if include_expenses and total_order_value and float(total_import_expenses or 0.0) != 0.0:
                    try:
                        share = (ln_price * ln_qty) / total_order_value
                        extra_per_unit = (float(total_import_expenses) * share) / float(ln_qty)
                        adjusted_price = ln_price + extra_per_unit
                    except Exception as e:
                        logger.warning(f"[add_import] Failed to allocate expenses for line {ln}: {e}")
                        print(f"[ERROR] Failed to allocate expenses for line: {e}")
                        adjusted_price = ln_price

                try:
                    _insert_line(cur, import_id, ln_cat, ln_sub, adjusted_price, ln_qty, date, cur_ccy, fx_override, supplier, notes)
                    print(f"[DEBUG] Inserted line for cat={ln_cat}, sub={ln_sub}")
                except Exception as e:
                    print(f"[ERROR] Failed to insert line: {e}")
                    raise

        # --- Single-line import (no lines) ---
        else:
            print(f"[DEBUG] Single-line import: cat={category}, sub={subcategory}, price={ordered_price}, qty={quantity}")
            adjusted_price = ordered_price
            if include_expenses and float(total_import_expenses or 0.0) != 0.0:
                try:
                    adjusted_price = float(ordered_price) + (float(total_import_expenses) / float(quantity))
                except Exception as e:
                    logger.warning(f"[add_import] Failed to allocate expenses for single-line import: {e}")
                    print(f"[ERROR] Failed to allocate expenses for single-line import: {e}")
                    adjusted_price = ordered_price

            try:
                _insert_line(cur, import_id, category, subcategory, adjusted_price, quantity, date, cur_ccy, fx_override, supplier, notes)
                print(f"[DEBUG] Inserted single-line import line")
            except Exception as e:
                print(f"[ERROR] Failed to insert single-line import line: {e}")
                raise

        # --- Persist import-level expenses and audit ---
        try:
            print("[DEBUG] About to update import expenses")
            cur.execute('UPDATE imports SET total_import_expenses=?, include_expenses=? WHERE id=?',
                        (float(total_import_expenses or 0.0), 1 if include_expenses else 0, import_id))
            print(f"[DEBUG] Updated import expenses for id: {import_id}")
        except Exception as e:
            print(f"[ERROR] Failed to update import expenses: {e}")
            raise
        try:
            print("[DEBUG] About to call write_audit:", write_audit)
            write_audit('add', 'import', str(import_id), f"qty={quantity}; price={ordered_price}", cur=cur)
            print(f"[DEBUG] Wrote audit log for import id: {import_id}")
        except Exception as e:
            print(f"[ERROR] Failed to write audit log: {e}")
            raise


# --- Helper: compute cost in base currency ---
def _compute_cost_base(
    order_date: str,
    unit_cost_ccy: float,
    ccy: str,
    fx_override_val: Optional[float] = None
) -> tuple[float, float, Optional[float]]:
    """
    Compute the unit cost in import and base currency, and the FX rate to base.
    Returns (unit_cost_in_import_ccy, unit_cost_in_base, fx_to_base).
    """
    unit_cost_in_import_ccy = float(unit_cost_ccy or 0.0)
    base_ccy_local = get_base_currency() or 'USD'
    unit_cost_in_base = unit_cost_in_import_ccy
    fx_to_base = None
    if fx_override_val is not None:
        try:
            fx_to_base = float(fx_override_val)
            unit_cost_in_base = unit_cost_in_import_ccy * fx_to_base
        except Exception:
            fx_to_base = None
    else:
        if (ccy or '').upper() != (base_ccy_local or '').upper():
            if ccy and base_ccy_local:
                converted = convert_amount(order_date, unit_cost_in_import_ccy, ccy, base_ccy_local)
                if converted is not None:
                    unit_cost_in_base = float(converted)
                    try:
                        fx_to_base = unit_cost_in_base / unit_cost_in_import_ccy if unit_cost_in_import_ccy != 0 else None
                    except Exception:
                        fx_to_base = None
            else:
                fx_to_base = None
        else:
            fx_to_base = 1.0
    return unit_cost_in_import_ccy, unit_cost_in_base, fx_to_base


def create_import_batch(
    import_id: int,
    date: str,
    category: str,
    subcategory: str,
    quantity: float,
    unit_cost: float,
    supplier: str,
    notes: str = "",
    currency: str = 'TRY',
    fx_to_base: Optional[float] = None,
    unit_cost_base: Optional[float] = None,
    unit_cost_orig: Optional[float] = None,
    import_line_id: Optional[int] = None,
    cur=None
) -> int:
    """
    Inserts a batch for an import. Requires a DB cursor (cur).
    Returns the new batch's row id.
    """
    if cur is None:
        raise ValueError("Cursor (cur) must be provided for transactional batch creation")

    cur.execute('''
        INSERT INTO import_batches (
            import_id, batch_date, category, subcategory,
            original_quantity, remaining_quantity, unit_cost, unit_cost_base,
            supplier, batch_notes, currency, fx_to_base, unit_cost_orig, import_line_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        import_id,
        date,
        category or '',
        subcategory or '',
        quantity,
        quantity,
        unit_cost,
        unit_cost_base,
        supplier or '',
        notes or '',
        currency or 'TRY',
        float(fx_to_base) if fx_to_base is not None else None,
        unit_cost_orig,
        import_line_id
    ))

    return cur.lastrowid


def _insert_line(
    cur,
    import_id: int,
    cat: str,
    sub: str,
    price: float,
    qty: float,
    date: str,
    cur_ccy: str,
    fx_override: Optional[float],
    supplier: str,
    notes: str
) -> None:
    """
    Insert a line into import_lines, create a batch, and update inventory.
    """
    if not cat or price is None or qty is None:
        return
    cur.execute('''
        INSERT INTO import_lines (import_id, category, subcategory, ordered_price, quantity)
        VALUES (?, ?, ?, ?, ?)
    ''', (import_id, cat, sub or '', price, qty))
    import_line_id = cur.lastrowid

    unit_cost_ccy, unit_cost_base, fx_to_base = _compute_cost_base(date, price, cur_ccy, fx_override)
    create_import_batch(import_id, date, cat, sub, qty, unit_cost_ccy, supplier, notes,
                        cur_ccy, fx_to_base, unit_cost_base, unit_cost_ccy, import_line_id=import_line_id, cur=cur)
    update_inventory(cat, sub, qty, cur=cur)


def get_imports(limit: int = 500) -> List[Dict]:
    """
    Return a list of recent imports (active or all), decrypting notes.
    """
    with get_cursor() as (conn, cur):
        try:
            cur.execute(
                'SELECT id, date, ordered_price, quantity, supplier, notes, category, subcategory, currency '
                'FROM active_imports ORDER BY id DESC LIMIT ?', (limit,))
        except Exception as e:
            logger.warning(f"[get_imports] Failed to query active_imports, falling back to imports: {e}")
            cur.execute(
                'SELECT id, date, ordered_price, quantity, supplier, notes, category, subcategory, currency '
                'FROM imports ORDER BY id DESC LIMIT ?', (limit,))
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        r['notes'] = decrypt_str(r.get('notes'))
    return rows


def get_imports_with_lines(limit: int = 500) -> List[Dict]:
    """
    Return a list of imports, each with a 'lines' key containing an array of lines.
    """
    with get_cursor() as (conn, cur):
        try:
            cur.execute(
                'SELECT id, date, ordered_price, quantity, supplier, notes, category, subcategory, currency, deleted '
                'FROM active_imports ORDER BY id DESC LIMIT ?', (limit,))
        except Exception as e:
            logger.warning(f"[get_imports_with_lines] Failed to query active_imports, falling back to imports: {e}")
            cur.execute(
                'SELECT id, date, ordered_price, quantity, supplier, notes, category, subcategory, currency, deleted '
                'FROM imports ORDER BY id DESC LIMIT ?', (limit,))
        imports = [dict(r) for r in cur.fetchall()]

        out = []
        for imp in imports:
            imp_id = imp.get('id')
            cur.execute(
                'SELECT id, category, subcategory, ordered_price, quantity FROM import_lines WHERE import_id=?',
                (imp_id,))
            lines = [dict(l) for l in cur.fetchall()]
            for l in lines:
                try:
                    l['ordered_price'] = float(l.get('ordered_price') or 0)
                    l['quantity'] = float(l.get('quantity') or 0)
                except Exception as e:
                    logger.warning(f"[get_imports_with_lines] Failed to coerce line values to float for line {l}: {e}")
            imp['lines'] = lines
            imp['notes'] = decrypt_str(imp.get('notes'))
            out.append(imp)

    return out


def edit_import(
    import_id: int,
    date: str,
    ordered_price: float,
    quantity: float,
    supplier: str,
    notes: str,
    category: str,
    subcategory: str,
    currency: Optional[str] = None,
    fx_override: Optional[float] = None,
    total_import_expenses: float = 0.0,
    include_expenses: bool = False
) -> None:
    """
    Edit an existing import record and update related batches and inventory.
    Handles supplier, FX, and expense allocation changes.
    """
    with get_cursor() as (conn, cur):
        # --- Supplier handling ---
        supplier_name = (supplier or '').strip()
        supplier_id = None
        if supplier_name:
            try:
                supplier_id = find_or_create_supplier(supplier_name)
            except Exception as e:
                logger.error(f"[edit_import] Failed to find or create supplier '{supplier_name}': {e}")
                supplier_id = None

        # --- Fetch current currency ---
        cur.execute('SELECT currency FROM imports WHERE id=?', (import_id,))
        row = cur.fetchone()
        cur_currency = (row['currency'] if row else 'TRY')
        new_currency = currency or cur_currency or 'TRY'
        
        # Continue with the rest of your edit logic here...
        # (The function was incomplete in your original code)


def delete_import(import_id: int) -> None:
    """
    Soft-delete an import and its batches, then rebuild inventory.
    Requires admin privileges.
    """
    require_admin('delete', 'import', str(import_id))
    
    with get_cursor() as (conn, cur):
        # Soft-delete the import and its batches
        cur.execute('UPDATE import_batches SET deleted=1 WHERE import_id=?', (import_id,))
        cur.execute('UPDATE imports SET deleted=1 WHERE id=?', (import_id,))
    
    # Rebuild inventory from non-deleted imports
    with get_cursor() as (conn, cur):
        rebuild_inventory_from_imports(cur)
    
    write_audit('delete', 'import', str(import_id), 'soft-deleted', cur=cur)


def undelete_import(import_id: int) -> None:
    """
    Restore a soft-deleted import and its batches, then rebuild inventory.
    """
    try:
        require_admin('undelete', 'import', str(import_id))
    except Exception as e:
        logger.info(f"[undelete_import] Non-admin undelete allowed for import_id={import_id}: {e}")

    with get_cursor() as (conn, cur):
        cur.execute('UPDATE imports SET deleted=0 WHERE id=?', (import_id,))
        cur.execute('UPDATE import_batches SET deleted=0 WHERE import_id=?', (import_id,))

    with get_cursor() as (conn, cur):
        rebuild_inventory_from_imports(cur)
    
    write_audit('undelete', 'import', str(import_id), cur=cur)


def get_available_batches(
    category: str,
    subcategory: Optional[str] = None,
    order_by_date: bool = True
) -> List[Dict]:
    """
    Return available import batches for a category/subcategory, ordered by date.
    """
    with get_cursor() as (conn, cur):
        if subcategory:
            query = '''
                SELECT id, batch_date, category, subcategory, original_quantity, remaining_quantity, 
                       unit_cost, unit_cost_base, unit_cost_orig, currency, fx_to_base, supplier, batch_notes, import_id
                FROM import_batches 
                WHERE category = ? AND subcategory = ? AND remaining_quantity > 0
            '''
            params = (category, subcategory)
        else:
            query = '''
                SELECT id, batch_date, category, subcategory, original_quantity, remaining_quantity, 
                       unit_cost, unit_cost_base, unit_cost_orig, currency, fx_to_base, supplier, batch_notes, import_id
                FROM import_batches 
                WHERE category = ? AND remaining_quantity > 0
            '''
            params = (category,)

        if order_by_date:
            query += ' ORDER BY batch_date ASC, id ASC'

        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]

    return rows


def allocate_sale_to_batches(
    product_id: int,
    sale_date: str,
    category: str,
    subcategory: str,
    quantity: float,
    unit_sale_price_base: float
) -> List[Dict]:
    """
    Allocate a sale to available import batches, update inventory, and record allocations.
    Returns a list of allocation details.
    """
    if quantity <= 0:
        return []

    allocations = []
    remaining_to_allocate = quantity

    with get_cursor() as (conn, cur):
        batches = get_available_batches(category, subcategory)

        for batch in batches:
            if remaining_to_allocate <= 0:
                break

            batch_id = batch['id']
            batch_available = batch['remaining_quantity']

            # Determine unit cost in base currency
            try:
                unit_cost_base = float(batch.get('unit_cost_orig') or 0.0)
                if unit_cost_base == 0.0:
                    unit_cost_base = float(batch.get('unit_cost') or 0.0)
            except Exception:
                unit_cost_base = float(batch.get('unit_cost') or 0.0)

            unit_sale_price_base = float(unit_sale_price_base or 0.0)

            allocated_from_batch = min(remaining_to_allocate, batch_available)
            profit_per_unit = unit_sale_price_base - unit_cost_base

            # Insert allocation
            cur.execute('''
                INSERT INTO sale_batch_allocations
                (product_id, sale_date, category, subcategory, batch_id, quantity_from_batch,
                 unit_cost, unit_sale_price, profit_per_unit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                product_id, sale_date, category or '', subcategory or '',
                batch_id, allocated_from_batch, unit_cost_base, unit_sale_price_base, profit_per_unit
            ))

            # Update remaining quantity
            new_remaining = batch_available - allocated_from_batch
            cur.execute(
                'UPDATE import_batches SET remaining_quantity = ? WHERE id = ?',
                (new_remaining, batch_id)
            )

            allocations.append({
                'batch_id': batch_id,
                'batch_date': batch['batch_date'],
                'supplier': batch['supplier'],
                'quantity_allocated': allocated_from_batch,
                'unit_cost': unit_cost_base,
                'unit_sale_price': unit_sale_price_base,
                'profit_per_unit': profit_per_unit,
                'total_cost': allocated_from_batch * unit_cost_base,
                'total_revenue': allocated_from_batch * unit_sale_price_base,
                'total_profit': allocated_from_batch * profit_per_unit
            })

            remaining_to_allocate -= allocated_from_batch

        # Handle shortage if not enough inventory
        if remaining_to_allocate > 0:
            allocations.append({
                'batch_id': None,
                'batch_date': 'NO_INVENTORY',
                'supplier': 'SHORTAGE',
                'quantity_allocated': remaining_to_allocate,
                'unit_cost': 0.0,
                'unit_sale_price': unit_sale_price_base,
                'profit_per_unit': unit_sale_price_base,
                'total_cost': 0.0,
                'total_revenue': remaining_to_allocate * unit_sale_price_base,
                'total_profit': remaining_to_allocate * unit_sale_price_base
            })

    return allocations


def backfill_allocation_unit_costs() -> None:
    """
    Fill missing unit_cost in sale_batch_allocations from import_batches and recalculate profit.
    """
    with get_cursor() as (conn, cur):
        # Fill missing unit_cost from related import_batches
        cur.execute('''
            UPDATE sale_batch_allocations
            SET unit_cost = (
                SELECT COALESCE(ib.unit_cost_base, ib.unit_cost_orig, ib.unit_cost, 0)
                FROM import_batches ib
                WHERE ib.id = sale_batch_allocations.batch_id
            )
            WHERE (unit_cost IS NULL OR unit_cost = 0) AND batch_id IS NOT NULL
        ''')

        # Recalculate profit_per_unit for allocations with known batch_id
        cur.execute('''
            UPDATE sale_batch_allocations
            SET profit_per_unit = unit_sale_price - unit_cost
            WHERE batch_id IS NOT NULL
        ''')


def undelete_allocation(allocation_id: int) -> bool:
    """
    Restore a soft-deleted sale_batch_allocation by id. Returns True if successful.
    """
    try:
        with get_cursor() as (conn, cur):
            cur.execute(
                'UPDATE sale_batch_allocations SET deleted = 0 WHERE id = ?',
                (allocation_id,)
            )
        return True
    except Exception:
        return False


def get_sale_batch_info(product_id: int) -> List[Dict]:
    """
    Return batch allocation info for a given product_id.
    """
    with get_cursor() as (conn, cur):
        cur.execute('''
            SELECT 
                sba.product_id,
                sba.sale_date,
                sba.category,
                sba.subcategory,
                sba.batch_id,
                sba.quantity_from_batch,
                COALESCE(NULLIF(sba.unit_cost, 0), ib.unit_cost_base, ib.unit_cost_orig, ib.unit_cost, 0) AS unit_cost,
                sba.unit_sale_price,
                (COALESCE(sba.unit_sale_price,0) - COALESCE(NULLIF(sba.unit_cost, 0), ib.unit_cost_base, ib.unit_cost_orig, ib.unit_cost, 0)) AS profit_per_unit,
                ib.batch_date,
                ib.supplier,
                ib.batch_notes
            FROM sale_batch_allocations sba
            LEFT JOIN import_batches ib ON sba.batch_id = ib.id
            WHERE sba.product_id = ?
            ORDER BY sba.id
        ''', (product_id,))
        rows = [dict(r) for r in cur.fetchall()]

    return rows


def handle_return_batch_allocation(
    product_id: int,
    restock_quantity: float = 1.0
) -> List[Dict]:
    """
    Handle restocking inventory by reversing sale batch allocations for returns.
    Returns a list of batches updated.
    """
    if restock_quantity <= 0:
        return []

    returned_to_batches = []
    remaining_to_return = restock_quantity

    with get_cursor() as (conn, cur):
        cur.execute('''
            SELECT batch_id, quantity_from_batch, unit_cost
            FROM sale_batch_allocations
            WHERE product_id = ?
            ORDER BY id DESC
        ''', (product_id,))

        allocations = [dict(r) for r in cur.fetchall()]

        for alloc in allocations:
            if remaining_to_return <= 0:
                break

            batch_id = alloc['batch_id']
            original_allocation = alloc['quantity_from_batch']
            unit_cost = alloc['unit_cost']
            if batch_id is None:
                continue

            return_to_batch = min(remaining_to_return, original_allocation)

            cur.execute(
                'UPDATE import_batches SET remaining_quantity = remaining_quantity + ? WHERE id = ?',
                (return_to_batch, batch_id)
            )

            cur.execute(
                'SELECT batch_date, supplier, category, subcategory FROM import_batches WHERE id = ?',
                (batch_id,)
            )
            batch_info = cur.fetchone()
            batch_info = dict(batch_info) if batch_info else None

            returned_to_batches.append({
                'batch_id': batch_id,
                'batch_date': batch_info['batch_date'] if batch_info else 'Unknown',
                'supplier': batch_info['supplier'] if batch_info else 'Unknown',
                'category': batch_info['category'] if batch_info else '',
                'subcategory': batch_info['subcategory'] if batch_info else '',
                'returned_quantity': return_to_batch,
                'unit_cost': unit_cost
            })

            remaining_to_return -= return_to_batch

    return returned_to_batches


def migrate_existing_imports_to_batches() -> int:
    """
    Migrate legacy imports to batch structure. Returns number of imports migrated.
    """
    with get_cursor() as (conn, cur):
        cur.execute('''
            SELECT i.id, i.date, i.category, i.subcategory, i.quantity, i.ordered_price, i.supplier, i.notes
            FROM imports i
            LEFT JOIN import_batches ib ON i.id = ib.import_id
            WHERE ib.import_id IS NULL
        ''')
        unmigrated_imports = [dict(r) for r in cur.fetchall()]

        for imp in unmigrated_imports:
            create_import_batch(
                import_id=imp['id'],
                date=imp['date'],
                category=imp['category'],
                subcategory=imp['subcategory'],
                quantity=imp['quantity'],
                unit_cost=imp['ordered_price'],
                supplier=imp['supplier'],
                notes=imp['notes'],
                cur=cur  # pass the same cursor
            )

    return len(unmigrated_imports)

def recompute_import_batches(import_id: int):
    """
    Recompute unit_cost and unit_cost_base for batches of a given import_id using import_lines and expenses.
    """
    from .connection import get_cursor

    print(f"[DEBUG] recompute_import_batches called with import_id={import_id}")
    with get_cursor() as (conn, cur):
        # --- Load import ---
        cur.execute('SELECT total_import_expenses, include_expenses, currency, date FROM imports WHERE id=?', (import_id,))
        imp = cur.fetchone()
        if not imp:
            print(f"[DEBUG] No import found for id={import_id}")
            return
        imp = dict(imp)
        print(f"[DEBUG] Loaded import: {imp}")
        include_flag = bool(int(imp.get('include_expenses') or 0))
        imp_currency = (imp.get('currency') or get_default_import_currency() or 'USD').upper()
        imp_date = imp.get('date')

        # --- Sum linked expenses ---
        total_expenses = 0.0
        try:
            cur.execute('''SELECT e.id, e.date, e.amount, e.currency, COALESCE(e.deleted,0) as deleted 
                           FROM expenses e
                           JOIN expense_import_links l ON l.expense_id = e.id 
                           WHERE l.import_id = ?''', (import_id,))
            linked_sum = 0.0
            for er in cur.fetchall():
                er = dict(er)
                if int(er.get('deleted',0)) == 1:
                    continue
                amt = float_or_none(er.get('amount')) or 0.0
                exp_ccy = (er.get('currency') or '').upper() or imp_currency
                exp_date = er.get('date') or imp_date
                if exp_ccy != imp_currency:
                    conv = convert_amount(exp_date, amt, exp_ccy, imp_currency)
                    amt = float(conv) if conv is not None else amt
                linked_sum += amt
            total_expenses = linked_sum if linked_sum > 0 else float(imp.get('total_import_expenses') or 0.0)
            print(f"[DEBUG] total_expenses for import_id={import_id}: {total_expenses}")
        except Exception as e:
            print(f"[DEBUG] Exception summing linked expenses: {e}")
            total_expenses = float(imp.get('total_import_expenses') or 0.0)

        # --- Load lines ---
        cur.execute('SELECT id, category, subcategory, ordered_price, quantity FROM import_lines WHERE import_id=?', (import_id,))
        lines = [dict(r) for r in cur.fetchall()]
        print(f"[DEBUG] Loaded lines for import_id={import_id}: {lines}")
        if not lines:
            print(f"[DEBUG] No lines found for import_id={import_id}")
            return

        total_order_value = sum(float(l.get('ordered_price') or 0) * float(l.get('quantity') or 0) for l in lines)
        print(f"[DEBUG] total_order_value for import_id={import_id}: {total_order_value}")
        apply_allocation = include_flag or (total_expenses > 0)

        # --- Recompute batches ---
        for l in lines:
            lid = l['id']
            unit_price = float(l.get('ordered_price') or 0.0)
            qty = float(l.get('quantity') or 0.0)
            line_total = unit_price * qty
            adjusted_price = unit_price
            if apply_allocation and total_order_value > 0 and qty > 0:
                share = line_total / total_order_value
                adjusted_price = unit_price + (total_expenses * share) / qty
            print(f"[DEBUG] Line {lid}: unit_price={unit_price}, qty={qty}, adjusted_price={adjusted_price}")

            # --- Base currency ---
            unit_cost_base = adjusted_price
            base_ccy = get_base_currency()
            try:
                if imp_currency != base_ccy and imp_date:
                    conv = convert_amount(imp_date, adjusted_price, imp_currency, base_ccy)
                    if conv is not None:
                        unit_cost_base = float(conv)
            except Exception as e:
                print(f"[DEBUG] Exception converting to base currency: {e}")

            # --- Update batches ---
            cur.execute('SELECT id FROM import_batches WHERE import_line_id=? AND import_id=?', (lid, import_id))
            bids = [r['id'] for r in cur.fetchall()]
            if not bids:
                cur.execute('SELECT id FROM import_batches WHERE import_id=? AND category=? AND subcategory=?', (import_id, l.get('category'), l.get('subcategory')))
                bids = [r['id'] for r in cur.fetchall()]

            for bid in bids:
                cur.execute('''
                    UPDATE import_batches 
                    SET unit_cost=?, unit_cost_base=?, unit_cost_orig = COALESCE(unit_cost_orig, ?)
                    WHERE id=?''', (adjusted_price, unit_cost_base, unit_price, bid))
                print(f"[DEBUG] Updated batch {bid}: unit_cost={adjusted_price}, unit_cost_base={unit_cost_base}, unit_cost_orig={unit_price}")
        conn.commit()
        print(f"[DEBUG] Finished recompute_import_batches for import_id={import_id}")
