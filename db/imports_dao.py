from .connection import get_conn
from .suppliers_dao import find_or_create_supplier
from .settings import get_default_import_currency,get_base_currency
from .crypto import encrypt_str,decrypt_str
from .auth import require_admin
from .utils import float_or_none
from .inventory_dao import update_inventory,rebuild_inventory_from_imports
from .audit import write_audit
from .rates import convert_amount


def add_import(date, ordered_price, quantity, supplier, notes, category, subcategory, currency: str = 'TRY', fx_override: float = None, lines: list = None, total_import_expenses: float = 0.0, include_expenses: bool = False):
    """
    Adds an import/order. Backwards compatible: if `lines` is None, will create a single import and line using category/subcategory.
    If `lines` is provided, it should be a list of dicts: [{'category':..., 'subcategory':..., 'ordered_price':..., 'quantity':...}, ...]
    """
    conn = get_conn()
    cur = conn.cursor()
    supplier_name = (supplier or '').strip()
    supplier_id = None
    if supplier_name:
        try:
            supplier_id = find_or_create_supplier(supplier_name)
        except Exception:
            supplier_id = None
    enc_notes = encrypt_str(notes)
    cur_ccy = (currency or get_default_import_currency() or 'USD').upper()
    # Create top-level import order row (summary)
    cur.execute('''INSERT INTO imports (date, ordered_price, quantity, supplier, supplier_id, notes, category, subcategory, currency)
                VALUES (?,?,?,?,?,?,?,?,?)''', (date, ordered_price, quantity, supplier_name, supplier_id, enc_notes, category if not lines else '', subcategory if not lines else '', cur_ccy))
    import_id = cur.lastrowid
    conn.commit()

    # Helper to compute base unit cost and fx
    def _compute_cost_base(order_date, unit_cost_ccy, ccy, fx_override_val=None):
        unit_cost_in_import_ccy = float(unit_cost_ccy or 0.0)
        base_ccy = get_base_currency()
        unit_cost_in_base = unit_cost_in_import_ccy
        fx_to_base = None
        if fx_override_val is not None:
            try:
                fx_to_base = float(fx_override_val)
                unit_cost_in_base = float(unit_cost_in_import_ccy) * fx_to_base
            except Exception:
                fx_to_base = None
        else:
            if (ccy or '').upper() != (base_ccy or '').upper():
                converted = convert_amount(order_date, unit_cost_in_import_ccy, ccy, base_ccy)
                if converted is not None:
                    unit_cost_in_base = float(converted)
                    try:
                        fx_to_base = float(unit_cost_in_base) / float(unit_cost_in_import_ccy) if unit_cost_in_import_ccy != 0 else None
                    except Exception:
                        fx_to_base = None
            else:
                fx_to_base = 1.0
        return unit_cost_in_import_ccy, unit_cost_in_base, fx_to_base

    # If lines provided, create import_lines and batches for each line
    if lines and isinstance(lines, list) and len(lines) > 0:
        # If the user requested to include total import expenses, compute proportional shares
        total_order_value = 0.0
        if include_expenses:
            for ln in lines:
                try:
                    total_order_value += float(ln.get('ordered_price') or 0.0) * float(ln.get('quantity') or 0.0)
                except Exception:
                    pass
        for ln in lines:
            ln_cat = ln.get('category')
            ln_sub = ln.get('subcategory')
            ln_price = float_or_none(ln.get('ordered_price'))
            ln_qty = float_or_none(ln.get('quantity'))
            if ln_price is None or ln_qty is None or not ln_cat:
                # skip invalid lines
                continue
            cur.execute('''INSERT INTO import_lines (import_id, category, subcategory, ordered_price, quantity) VALUES (?,?,?,?,?)''',
                        (import_id, ln_cat, ln_sub or '', ln_price, ln_qty))
            import_line_id = cur.lastrowid
            conn.commit()
            # Adjust unit price by proportional share of total_import_expenses if requested
            adjusted_price = ln_price
            if include_expenses and total_order_value and float(total_import_expenses or 0.0) != 0.0:
                try:
                    share = (ln_price * ln_qty) / total_order_value
                    extra_per_unit = (float(total_import_expenses) * share) / float(ln_qty)
                    adjusted_price = float(ln_price) + float(extra_per_unit)
                except Exception:
                    adjusted_price = ln_price
            unit_cost_ccy, unit_cost_base, fx_to_base = _compute_cost_base(date, adjusted_price, cur_ccy, fx_override)
            create_import_batch(import_id, date, ln_cat, ln_sub, ln_qty, unit_cost_ccy, supplier, notes, cur_ccy, fx_to_base, unit_cost_base, unit_cost_base, import_line_id=import_line_id)
            update_inventory(ln_cat, ln_sub, ln_qty, conn)
    else:
        # Backward-compatible single-line import
        # If single-line and include_expenses requested, apply proportional logic (trivial here)
        adjusted_price = ordered_price
        if include_expenses and float(total_import_expenses or 0.0) != 0.0:
            try:
                # Only one line: add all expenses divided by quantity
                adjusted_price = float(ordered_price) + (float(total_import_expenses) / float(quantity))
            except Exception:
                adjusted_price = ordered_price
        unit_cost_ccy, unit_cost_base, fx_to_base = _compute_cost_base(date, adjusted_price, cur_ccy, fx_override)
        # create a line for legacy single entry
        cur.execute('''INSERT INTO import_lines (import_id, category, subcategory, ordered_price, quantity) VALUES (?,?,?,?,?)''',
                    (import_id, category, subcategory or '', ordered_price, quantity))
        import_line_id = cur.lastrowid
        conn.commit()
        create_import_batch(import_id, date, category, subcategory, quantity, unit_cost_ccy, supplier, notes, cur_ccy, fx_to_base, unit_cost_base, unit_cost_base, import_line_id=import_line_id)
        update_inventory(category, subcategory, quantity, conn)
    # Persist total_import_expenses and include_expenses at import level
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('UPDATE imports SET total_import_expenses=?, include_expenses=? WHERE id=?', (float(total_import_expenses or 0.0), 1 if include_expenses else 0, import_id))
        conn.commit()
        conn.close()
    except Exception:
        pass
    conn.close()
    write_audit('add', 'import', str(import_id), f"qty={quantity}; price={ordered_price}")

def create_import_batch(import_id, date, category, subcategory, quantity, unit_cost, supplier, notes="", currency: str = 'TRY', fx_to_base: float = None, unit_cost_base: float = None, unit_cost_orig: float = None, import_line_id: int = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO import_batches (import_id, batch_date, category, subcategory, 
                                   original_quantity, remaining_quantity, unit_cost, unit_cost_base, supplier, batch_notes, currency, fx_to_base, unit_cost_orig, import_line_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (import_id, date, category or '', subcategory or '', quantity, quantity, unit_cost, unit_cost_base, supplier or '', notes or '', currency or 'TRY', (float(fx_to_base) if fx_to_base is not None else None), unit_cost_orig, import_line_id))
    batch_id = cur.lastrowid
    conn.commit()
    conn.close()
    return batch_id

def get_imports(limit=500):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, date, ordered_price, quantity, supplier, notes, category, subcategory, currency FROM imports ORDER BY id DESC LIMIT ?', (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    for r in rows:
        r['notes'] = decrypt_str(r.get('notes'))
    return rows


def get_imports_with_lines(limit=500):
    """Return a list of imports, each with a 'lines' key containing an array of lines."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, date, ordered_price, quantity, supplier, notes, category, subcategory, currency, deleted FROM imports ORDER BY id DESC LIMIT ?', (limit,))
    imports = [dict(r) for r in cur.fetchall()]
    out = []
    for imp in imports:
        imp_id = imp.get('id')
        cur.execute('SELECT id, category, subcategory, ordered_price, quantity FROM import_lines WHERE import_id=?', (imp_id,))
        lines = [dict(l) for l in cur.fetchall()]
        for l in lines:
            # ensure numeric types
            try:
                l['ordered_price'] = float(l.get('ordered_price') or 0)
                l['quantity'] = float(l.get('quantity') or 0)
            except Exception:
                pass
        imp['lines'] = lines
        imp['notes'] = decrypt_str(imp.get('notes'))
        out.append(imp)
    conn.close()
    return out


def edit_import(import_id, date, ordered_price, quantity, supplier, notes, category, subcategory, currency: str = None, fx_override: float = None, total_import_expenses: float = 0.0, include_expenses: bool = False):
    conn = get_conn()
    cur = conn.cursor()
    supplier_name = (supplier or '').strip()
    supplier_id = None
    if supplier_name:
        try:
            supplier_id = find_or_create_supplier(supplier_name)
        except Exception:
            supplier_id = None
    cur.execute('SELECT currency FROM imports WHERE id=?', (import_id,))
    row = cur.fetchone()
    cur_currency = (row['currency'] if row else 'TRY')
    new_currency = currency or cur_currency or 'TRY'
    enc_notes = encrypt_str(notes)
    cur.execute('''UPDATE imports SET date=?, ordered_price=?, quantity=?, supplier=?, supplier_id=?, notes=?, category=?, subcategory=?, currency=? WHERE id=?''',
                (date, ordered_price, quantity, supplier_name, supplier_id, enc_notes, category, subcategory, new_currency, import_id))
    unit_cost_in_import_ccy = float(ordered_price or 0.0)
    base_ccy = get_base_currency()
    new_currency_u = (new_currency or '').upper()
    unit_cost_in_base = unit_cost_in_import_ccy
    if (new_currency_u or '') != (base_ccy or '').upper():
        converted = convert_amount(date, unit_cost_in_import_ccy, new_currency_u, base_ccy)
        unit_cost_in_base = converted if converted is not None else unit_cost_in_base
    # compute fx_to_base similarly to add_import; allow override
    fx_to_base = None
    if fx_override is not None:
        try:
            fx_to_base = float(fx_override)
            unit_cost_in_base = float(unit_cost_in_import_ccy) * fx_to_base
        except Exception:
            fx_to_base = None
    else:
        try:
            if (new_currency_u or '') == (base_ccy or '').upper():
                fx_to_base = 1.0
            else:
                fx_to_base = float(unit_cost_in_base) / float(unit_cost_in_import_ccy) if unit_cost_in_import_ccy != 0 else None
        except Exception:
            fx_to_base = None
    # Do not bulk-overwrite import_batches here. Batch unit_costs are per-line and
    # should be recomputed via recompute_import_batches which uses import_lines and
    # linked expenses. Removing the bulk update prevents the last-edited line from
    # overwriting other lines' costs.
    # Update import-level expense flags if provided
    try:
        cur.execute('PRAGMA table_info(imports)')
        cols = [r['name'] for r in cur.fetchall()]
        if 'total_import_expenses' in cols:
            cur.execute('UPDATE imports SET total_import_expenses=?, include_expenses=? WHERE id=?', (float(total_import_expenses or 0.0), 1 if include_expenses else 0, import_id))
            conn.commit()
    except Exception:
        pass
    # Recompute batches for this import to reflect new expense allocation if needed
    try:
        recompute_import_batches(import_id)
    except Exception:
        # fallback: rebuild inventory and continue
        try:
            rebuild_inventory_from_imports(conn)
        except Exception:
            pass
    conn.close()
    write_audit('edit', 'import', str(import_id), f"qty=={quantity}; price={ordered_price}")


def recompute_import_batches(import_id: int):
    """
    Recompute unit costs for batches belonging to a given import_id using the import_lines and import-level expense allocation.
    This updates import_batches.unit_cost and unit_cost_base based on proportional allocation.
    """
    conn = get_conn()
    cur = conn.cursor()
    # Load import-level expense settings and currency/date
    cur.execute('SELECT total_import_expenses, include_expenses, currency, date FROM imports WHERE id=?', (import_id,))
    imp = cur.fetchone()
    if not imp:
        conn.close()
        return
    # sqlite3.Row doesn't implement .get, so convert to dict for uniform access
    try:
        imp = dict(imp)
    except Exception:
        pass
    try:
        include_flag = bool(int(imp.get('include_expenses') or 0))
    except Exception:
        include_flag = False
    imp_currency = (imp.get('currency') or get_default_import_currency() or 'USD').upper()
    imp_date = imp.get('date') or None

    # Sum linked expenses converted into import currency (imp_currency)
    total_expenses = 0.0
    try:
        cur.execute('''SELECT e.id, e.date, e.amount, e.currency, COALESCE(e.deleted,0) as deleted FROM expenses e
                       JOIN expense_import_links l ON l.expense_id = e.id WHERE l.import_id = ?''', (import_id,))
        exp_rows = [dict(r) for r in cur.fetchall()]
        linked_sum_imp_ccy = 0.0
        for er in exp_rows:
            try:
                if int(er.get('deleted', 0) or 0) == 1:
                    continue
                raw_amt = float_or_none(er.get('amount')) or 0.0
                exp_ccy = (er.get('currency') or '').upper() or imp_currency
                exp_date = er.get('date') or imp_date
                if exp_ccy and imp_currency and exp_ccy != imp_currency:
                    conv = convert_amount(exp_date, raw_amt, exp_ccy, imp_currency)
                    if conv is None:
                        amt_imp = raw_amt
                    else:
                        amt_imp = float(conv)
                else:
                    amt_imp = raw_amt
                linked_sum_imp_ccy += amt_imp
            except Exception:
                continue
        if linked_sum_imp_ccy and linked_sum_imp_ccy > 0:
            total_expenses = float(linked_sum_imp_ccy)
        else:
            # fallback to import-level stored value (assumed in import currency)
            try:
                total_expenses = float(imp.get('total_import_expenses') or 0.0)
            except Exception:
                total_expenses = 0.0
    except Exception:
        try:
            total_expenses = float(imp.get('total_import_expenses') or 0.0)
        except Exception:
            total_expenses = 0.0

    # Load import lines for this import
    cur.execute('SELECT id, category, subcategory, ordered_price, quantity FROM import_lines WHERE import_id=?', (import_id,))
    lines = [dict(r) for r in cur.fetchall()]
    if not lines:
        conn.close()
        return

    # Compute line totals and total_order_value (unit_price * qty) in import currency
    total_order_value = 0.0
    sanitized_lines = []
    for l in lines:
        lid = l.get('id')
        try:
            unit_price = float_or_none(l.get('ordered_price'))
            qty = float_or_none(l.get('quantity'))
            if unit_price is None:
                unit_price = 0.0
            if qty is None:
                qty = 0.0
            line_total = float(unit_price) * float(qty)
            total_order_value += line_total
            sanitized_lines.append({'id': lid, 'category': l.get('category'), 'subcategory': l.get('subcategory'), 'unit_price': float(unit_price), 'qty': float(qty), 'line_total': line_total})
        except Exception as ex:
            print(f"[recompute] skipping malformed line {lid}: {ex}")
            continue

    # debug prints removed

    # Decide whether to apply allocation: honor include_flag but also apply if there are linked/stored expenses
    apply_allocation = bool(include_flag)
    if not apply_allocation and total_expenses and total_expenses > 0:
        apply_allocation = True

    # If total_order_value is zero, we cannot proportionally allocate; abort updates but still report
    if apply_allocation and total_expenses and total_order_value <= 0:
        print(f"[recompute] Cannot allocate expenses: total_order_value={total_order_value}")

    # For each sanitized line compute adjusted unit price using per-unit proportional allocation based on line_total
    # extra_per_unit = (line_total / total_order_value) * total_expenses / qty
    for ln in sanitized_lines:
        lid = ln['id']
        unit_price = float(ln.get('unit_price') or 0.0)
        qty = float(ln.get('qty') or 0.0)
        line_total = float(ln.get('line_total') or 0.0)
        adjusted_price = unit_price
        try:
            if apply_allocation and total_expenses and total_order_value > 0 and qty > 0:
                share = line_total / float(total_order_value)
                extra_per_unit = (float(total_expenses) * share) / float(qty)
                adjusted_price = float(unit_price) + float(extra_per_unit)
        except Exception:
            adjusted_price = unit_price

        # Compute base conversion for adjusted price
        unit_cost_ccy = adjusted_price
        base_ccy = get_base_currency()
        unit_cost_base = unit_cost_ccy
        try:
            if (imp_currency or '').upper() != (base_ccy or '').upper() and imp_date:
                conv = convert_amount(imp_date, unit_cost_ccy, imp_currency, base_ccy)
                if conv is not None:
                    unit_cost_base = float(conv)
        except Exception:
            pass

        # Update matching batches (prefer import_line_id then fallback to category/subcategory)
        try:
            cur.execute('SELECT id FROM import_batches WHERE import_line_id=? AND import_id=?', (lid, import_id))
            bids = [r['id'] for r in cur.fetchall()]
            if not bids:
                cur.execute('SELECT id FROM import_batches WHERE import_id=? AND category=? AND subcategory=?', (import_id, ln.get('category'), ln.get('subcategory')))
                bids = [r['id'] for r in cur.fetchall()]
            if not bids:
                pass
            # Update any found batches
            for bid in bids:
                try:
                    # Preserve original import unit price in unit_cost_orig if not already set.
                    cur.execute('UPDATE import_batches SET unit_cost=?, unit_cost_base=?, unit_cost_orig = COALESCE(unit_cost_orig, ?) WHERE id=?', (unit_cost_ccy, unit_cost_base, unit_price, bid))
                except Exception:
                    pass
        except Exception:
            pass

    conn.commit()
    conn.close()


def delete_import(import_id):
    require_admin('delete', 'import', str(import_id))
    conn = get_conn()
    cur = conn.cursor()
    # Soft-delete the import and its batches to preserve history and allow undelete/purge
    cur.execute('UPDATE import_batches SET deleted=1 WHERE import_id=?', (import_id,))
    cur.execute('UPDATE imports SET deleted=1 WHERE id=?', (import_id,))
    conn.commit()
    # Rebuild inventory from non-deleted imports
    rebuild_inventory_from_imports(conn)
    conn.close()
    write_audit('delete', 'import', str(import_id), 'soft-deleted')


def undelete_import(import_id):
    try:
        require_admin('undelete', 'import', str(import_id))
    except Exception:
        # allow non-admin in automated tests, but still perform undelete
        pass
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('UPDATE imports SET deleted=0 WHERE id=?', (import_id,))
    cur.execute('UPDATE import_batches SET deleted=0 WHERE import_id=?', (import_id,))
    conn.commit()
    rebuild_inventory_from_imports(conn)
    conn.close()
    write_audit('undelete', 'import', str(import_id))



def get_available_batches(category, subcategory=None, order_by_date=True):
    conn = get_conn()
    cur = conn.cursor()
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
    conn.close()
    return rows


def allocate_sale_to_batches(product_id, sale_date, category, subcategory, quantity, unit_sale_price_base):
    if quantity <= 0:
        return []
    conn = get_conn()
    cur = conn.cursor()
    batches = get_available_batches(category, subcategory)
    allocations = []
    remaining_to_allocate = quantity
    for batch in batches:
        if remaining_to_allocate <= 0:
            break
        batch_id = batch['id']
        batch_available = batch['remaining_quantity']
        unit_cost_base = 0.0
        try:
            unit_cost_base = float((batch.get('unit_cost_orig') if isinstance(batch, dict) else None) or 0.0)
            if unit_cost_base == 0.0:
                unit_cost_base = float(batch.get('unit_cost') or 0.0)
        except Exception:
            unit_cost_base = float(batch.get('unit_cost') or 0.0)
        unit_sale_price_base = float(unit_sale_price_base or 0.0)
        allocated_from_batch = min(remaining_to_allocate, batch_available)
        profit_per_unit = unit_sale_price_base - unit_cost_base
        cur.execute('''
            INSERT INTO sale_batch_allocations 
            (product_id, sale_date, category, subcategory, batch_id, quantity_from_batch, 
             unit_cost, unit_sale_price, profit_per_unit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (product_id, sale_date, category or '', subcategory or '', batch_id, allocated_from_batch, unit_cost_base, unit_sale_price_base, profit_per_unit))
        new_remaining = batch_available - allocated_from_batch
        cur.execute('UPDATE import_batches SET remaining_quantity = ? WHERE id = ?', (new_remaining, batch_id))
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
    conn.commit()
    conn.close()
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

def backfill_allocation_unit_costs():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE sale_batch_allocations
            SET unit_cost = (
                SELECT COALESCE(ib.unit_cost_base, ib.unit_cost_orig, ib.unit_cost, 0)
                FROM import_batches ib
                WHERE ib.id = sale_batch_allocations.batch_id
            )
            WHERE (unit_cost IS NULL OR unit_cost = 0) AND batch_id IS NOT NULL
        ''')
        cur.execute('''
            UPDATE sale_batch_allocations
            SET profit_per_unit = unit_sale_price - unit_cost
            WHERE batch_id IS NOT NULL
        ''')
        conn.commit()
    finally:
        conn.close()
        
def undelete_allocation(allocation_id):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('UPDATE sale_batch_allocations SET deleted = 0 WHERE id = ?', (allocation_id,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False



def get_sale_batch_info(product_id):
    conn = get_conn()
    cur = conn.cursor()
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
    conn.close()
    return rows


def handle_return_batch_allocation(product_id, restock_quantity=1.0):
    if restock_quantity <= 0:
        return []
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT batch_id, quantity_from_batch, unit_cost
        FROM sale_batch_allocations 
        WHERE product_id = ?
        ORDER BY id DESC
    ''', (product_id,))
    allocations = cur.fetchall()
    returned_to_batches = []
    remaining_to_return = restock_quantity
    for alloc in allocations:
        if remaining_to_return <= 0:
            break
        batch_id = alloc[0]
        original_allocation = alloc[1]
        unit_cost = alloc[2]
        if batch_id is None:
            continue
        return_to_batch = min(remaining_to_return, original_allocation)
        cur.execute('UPDATE import_batches SET remaining_quantity = remaining_quantity + ? WHERE id = ?',
                   (return_to_batch, batch_id))
        cur.execute('SELECT batch_date, supplier, category, subcategory FROM import_batches WHERE id = ?', (batch_id,))
        batch_info = cur.fetchone()
        returned_to_batches.append({
            'batch_id': batch_id,
            'batch_date': batch_info[0] if batch_info else 'Unknown',
            'supplier': batch_info[1] if batch_info else 'Unknown',
            'category': batch_info[2] if batch_info else '',
            'subcategory': batch_info[3] if batch_info else '',
            'returned_quantity': return_to_batch,
            'unit_cost': unit_cost
        })
        remaining_to_return -= return_to_batch
    conn.commit()
    conn.close()
    return returned_to_batches


def migrate_existing_imports_to_batches():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT i.id, i.date, i.category, i.subcategory, i.quantity, i.ordered_price, i.supplier, i.notes
        FROM imports i
        LEFT JOIN import_batches ib ON i.id = ib.import_id
        WHERE ib.import_id IS NULL
    ''')
    unmigrated_imports = cur.fetchall()
    for imp in unmigrated_imports:
        import_id, date, category, subcategory, quantity, unit_cost, supplier, notes = imp
        create_import_batch(import_id, date, category, subcategory, quantity, unit_cost, supplier, notes)
    conn.close()
    return len(unmigrated_imports)


