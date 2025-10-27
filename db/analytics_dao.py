from .connection import get_cursor
from typing import Dict
from .settings import get_default_sale_currency,get_base_currency,get_default_import_currency
from .rates import convert_amount


def get_profit_analysis_by_sale(include_expenses: bool = False):
    # Compute aggregated sale profit. For include_expenses=True we prefer the
    # adjusted unit_cost stored in import_batches.unit_cost (payment-weighted).
    # For include_expenses=False prefer the original import price stored in
    # import_batches.unit_cost_orig (fallbacking to unit_cost_base/unit_cost).
    if not include_expenses:
        # Non-inclusive: prefer original import price stored on batch, then fall back
        # to base/unit_cost and finally any recorded allocation cost.
        cost_expr = "COALESCE(ib.unit_cost_orig, ib.unit_cost_base, ib.unit_cost, NULLIF(sba.unit_cost,0), 0)"
    else:
        # Inclusive: prefer adjusted batch unit_cost (payment-weighted), then fallbacks.
        cost_expr = "COALESCE(ib.unit_cost, ib.unit_cost_base, ib.unit_cost_orig, NULLIF(sba.unit_cost,0), 0)"
    with get_cursor() as (conn, cur):
        cur.execute(f'''
                SELECT 
                    sba.product_id,
                    sba.sale_date,
                    sba.category,
                    sba.subcategory,
                    SUM(sba.quantity_from_batch) as total_quantity,
                    ROUND(SUM(sba.quantity_from_batch * {cost_expr}), 2) as total_cost,
                    ROUND(SUM(sba.quantity_from_batch * sba.unit_sale_price), 2) as total_revenue,
                    ROUND(SUM(sba.quantity_from_batch * (sba.unit_sale_price - {cost_expr})), 2) as total_profit,
                    ROUND(
                        SUM(sba.quantity_from_batch * (sba.unit_sale_price - {cost_expr})) 
                        / NULLIF(SUM(sba.quantity_from_batch * {cost_expr}), 0) * 100
                    , 2) as profit_margin_percent,
                    COUNT(DISTINCT sba.batch_id) as batches_used
                FROM sale_batch_allocations sba
                LEFT JOIN import_batches ib ON sba.batch_id = ib.id
                WHERE (sba.deleted IS NULL OR sba.deleted = 0)
                GROUP BY sba.product_id
                ORDER BY sba.sale_date DESC
            ''')
        rows = [dict(r) for r in cur.fetchall()]

    # Fetch detailed allocations using a fresh connection (avoid closed cursor)
    # Use the same cost selection logic as the aggregate query so detailed
    # allocation costs reflect the include_expenses flag consistently.
    if not include_expenses:
        cost_expr_alloc = "COALESCE(ib.unit_cost_orig, ib.unit_cost_base, ib.unit_cost, NULLIF(sba.unit_cost,0), 0)"
    else:
        cost_expr_alloc = "COALESCE(ib.unit_cost, ib.unit_cost_base, ib.unit_cost_orig, NULLIF(sba.unit_cost,0), 0)"
    with get_cursor() as (conn_a, cur_a):
        cur_a.execute(f'''
            SELECT 
                sba.product_id,
                sba.sale_date,
                sba.category,
                sba.subcategory,
                sba.quantity_from_batch,
                sba.unit_sale_price,
                {cost_expr_alloc} AS unit_cost,
                ib.import_id
            FROM sale_batch_allocations sba
            LEFT JOIN import_batches ib ON sba.batch_id = ib.id
            WHERE (sba.deleted IS NULL OR sba.deleted = 0)
            ORDER BY sba.sale_date DESC
        ''')
        allocs = [dict(r) for r in cur_a.fetchall()]
    agg: Dict[str, Dict[str, float]] = {}
    sale_date: Dict[str, str] = {}
    category_map: Dict[str, str] = {}
    subcategory_map: Dict[str, str] = {}
    for a in allocs:
        pid = a['product_id']
        if not pid:
            continue
        q = float(a['quantity_from_batch'] or 0.0)
        unit_sale = float(a['unit_sale_price'] or 0.0)
        unit_cost = float(a['unit_cost'] or 0.0)
        eff_cost = unit_cost
        d = agg.setdefault(pid, {'qty': 0.0, 'cost': 0.0, 'rev': 0.0})
        d['qty'] += q
        d['cost'] += q * eff_cost
        d['rev'] += q * unit_sale
        sale_date[pid] = sale_date.get(pid) or a.get('sale_date')
        category_map[pid] = category_map.get(pid) or a.get('category')
        subcategory_map[pid] = subcategory_map.get(pid) or a.get('subcategory')
    rows = []
    for pid, d in agg.items():
        cost = float(d['cost'])
        rev = float(d['rev'])
        profit = rev - cost
        margin = (profit / cost * 100.0) if cost > 0 else 0.0
        per_unit_cost = (cost / d['qty']) if float(d['qty']) > 0 else 0.0
        per_unit_sale = (rev / d['qty']) if float(d['qty']) > 0 else 0.0
        rows.append({
            'product_id': pid,
            'sale_date': sale_date.get(pid),
            'category': category_map.get(pid),
            'subcategory': subcategory_map.get(pid),
            'total_quantity': float(d['qty']),
            'total_cost': round(cost, 2),
            'total_revenue': round(rev, 2),
            'total_profit': round(profit, 2),
            'per_unit_cost': round(per_unit_cost, 6),
            'per_unit_sale': round(per_unit_sale, 6),
            'profit_margin_percent': round(margin, 2),
            'batches_used': None,
        })
    try:
        with get_cursor() as (conn2, cur2):
            cur2.execute('SELECT product_id, COUNT(DISTINCT batch_id) as bc FROM sale_batch_allocations GROUP BY product_id')
            for r in cur2.fetchall():
                for row in rows:
                    if row['product_id'] == r['product_id']:
                        row['batches_used'] = r['bc']
    except Exception:
        pass
    # Apply returns adjustments so per-sale profit analysis reflects refunds/restocks
    try:
        with get_cursor() as (conn3, cur3):
            cur3.execute("SELECT product_id, refund_amount, refund_currency, return_date, COALESCE(refund_amount_base,0) as refund_amount_base, COALESCE(restock,0) as restock FROM returns WHERE (deleted IS NULL OR deleted = 0)")
            returns = cur3.fetchall()
            if returns:
                # Build quick index for rows by product_id
                idx = {r['product_id']: r for r in rows}
                for rr in returns:
                    pid = rr['product_id']
                    if not pid:
                        continue
                    # Prefer refund amount in sale currency; convert if necessary
                    try:
                        raw_refund = float(rr['refund_amount'] or 0.0)
                    except Exception:
                        raw_refund = 0.0
                    refund_ccy = (rr.get('refund_currency') or get_default_sale_currency()) if isinstance(rr, dict) else (rr[2] or get_default_sale_currency())
                    return_date = rr.get('return_date') if isinstance(rr, dict) else (rr[3] if len(rr) > 3 else '')
                    # Try convert refund amount into sale currency
                    try:
                        sale_ccy = get_default_sale_currency()
                        converted = convert_amount(return_date or '', raw_refund, (refund_ccy or '').upper(), (sale_ccy or '').upper())
                        refund_amt = float(converted) if converted is not None else float(rr['refund_amount_base'] or 0.0)
                    except Exception:
                        try:
                            refund_amt = float(rr['refund_amount_base'] or 0.0)
                        except Exception:
                            refund_amt = 0.0
                    restock_flag = 1 if int(rr['restock'] or 0) else 0
                    target = idx.get(pid)
                    if not target:
                        # No aggregated sale for this product (maybe legacy CSV sale); skip
                        continue
                    # Reduce revenue so reports reflect refund
                    target['total_revenue'] = round(float(target.get('total_revenue', 0.0)) - float(refund_amt or 0.0), 2)
                    # Decrease quantity by 1 (a returned unit)
                    try:
                        orig_qty = float(target.get('total_quantity', 0.0))
                        target['total_quantity'] = orig_qty - 1.0
                    except Exception:
                        target['total_quantity'] = 0.0
                    if target['total_quantity'] < 0:
                        target['total_quantity'] = 0.0

                # Apply profit adjustment rules requested:
                # - Non-restocked: profit(total) = profit(total) - saleprice (refund amount in base)
                # - Restocked: profit(total) = profit(total) - profit(product) (per-unit profit)
                try:
                    current_profit = float(target.get('total_profit', 0.0))
                except Exception:
                    current_profit = 0.0
                if restock_flag:
                    # For restocked returns, we want the net profit to decrease by one unit's profit
                    # (per_unit_sale - per_unit_cost). To guarantee this, adjust revenue by
                    # per_unit_sale and cost by per_unit_cost. Prefer precomputed per_unit fields
                    # stored in `target`; otherwise compute from allocations.
                    try:
                        per_unit_cost = float(target.get('per_unit_cost', 0.0))
                        per_unit_sale = float(target.get('per_unit_sale', 0.0))
                    except Exception:
                        per_unit_cost = 0.0
                        per_unit_sale = 0.0

                    if (not per_unit_cost or not per_unit_sale):
                        # Fallback: derive per-unit sale and cost from allocations
                        try:
                            with get_cursor() as (conn_p, cur_p):
                                cur_p.execute('''
                                    SELECT SUM(COALESCE(sba.quantity_from_batch,0) * COALESCE(sba.unit_sale_price,0)) AS tot_rev,
                                           SUM(COALESCE(sba.quantity_from_batch,0)) AS tot_qty,
                                           SUM(COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_base, ib.unit_cost_orig, ib.unit_cost, 0) * COALESCE(sba.quantity_from_batch,0)) AS tot_cost
                                    FROM sale_batch_allocations sba
                                    LEFT JOIN import_batches ib ON sba.batch_id = ib.id
                                    WHERE sba.product_id = ?
                                ''', (pid,))
                                rowp = cur_p.fetchone()
                                tot_rev = float(rowp['tot_rev'] if rowp and rowp['tot_rev'] is not None else 0.0)
                                tot_qty = float(rowp['tot_qty'] if rowp and rowp['tot_qty'] is not None else 0.0)
                                tot_cost = float(rowp['tot_cost'] if rowp and rowp['tot_cost'] is not None else 0.0)
                                if tot_qty > 0:
                                    per_unit_sale = per_unit_sale or (tot_rev / tot_qty)
                                    per_unit_cost = per_unit_cost or (tot_cost / tot_qty)
                        except Exception:
                            per_unit_sale = per_unit_sale or 0.0
                            per_unit_cost = per_unit_cost or 0.0

                    # Ensure revenue reflects per_unit_sale (we previously subtracted refund_amt)
                    try:
                        # current total_revenue already had refund_amt subtracted earlier
                        cur_rev = float(target.get('total_revenue', 0.0))
                        # compute adjusted revenue as original_rev - per_unit_sale
                        # so add back the earlier refund_amt and subtract per_unit_sale
                        adj_rev = cur_rev + float(refund_amt or 0.0) - float(per_unit_sale or 0.0)
                        target['total_revenue'] = round(max(0.0, adj_rev), 2)
                    except Exception:
                        target['total_revenue'] = round(float(target.get('total_revenue', 0.0)), 2)

                    # Reduce total_cost by per-unit cost (item returned to stock)
                    try:
                        target['total_cost'] = round(float(target.get('total_cost', 0.0)) - float(per_unit_cost or 0.0), 2)
                        if target['total_cost'] < 0:
                            target['total_cost'] = 0.0
                    except Exception:
                        target['total_cost'] = 0.0

                    # Recompute profit as revenue - cost; net effect = -per_unit_profit
                    try:
                        tr = float(target.get('total_revenue', 0.0))
                        tc = float(target.get('total_cost', 0.0))
                        target['total_profit'] = round(tr - tc, 2)
                        target['profit_margin_percent'] = round((target['total_profit'] / tc * 100.0), 2) if tc > 0 else 0.0
                    except Exception:
                        target['total_profit'] = round(float(target.get('total_profit', 0.0)) - (float(per_unit_sale or 0.0) - float(per_unit_cost or 0.0)), 2)
                else:
                    # Non-restock: product refunded but not restocked
                    try:
                        per_unit_refund = float(refund_amt or 0.0)
                    except Exception:
                        per_unit_refund = 0.0

                    # Reduce revenue and profit accordingly
                    try:
                        target['total_revenue'] = round(float(target.get('total_revenue', 0.0)) - per_unit_refund, 2)
                        if target['total_revenue'] < 0:
                            target['total_revenue'] = 0.0
                    except Exception:
                        target['total_revenue'] = 0.0

                    # Recalculate profit (no cost adjustment since item not restocked)
                    tr = float(target.get('total_revenue', 0.0))
                    tc = float(target.get('total_cost', 0.0))
                    target['total_profit'] = round(tr - tc, 2)
                    target['profit_margin_percent'] = round((target['total_profit'] / tc * 100.0), 2) if tc > 0 else 0.0
                # Recompute profit margin percent relative to total_cost
                try:
                    tc = float(target.get('total_cost', 0.0))
                    tp = float(target.get('total_profit', 0.0))
                    target['profit_margin_percent'] = round((tp / tc * 100.0) if tc > 0 else 0.0, 2)
                except Exception:
                    target['profit_margin_percent'] = 0.0
    except Exception:
        pass

    return rows


def _get_exact_cogs_for_product(product_id: str) -> float:
    try:
        with get_cursor() as (conn, cur):
            cur.execute('''
                SELECT 
                    SUM(COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_base, ib.unit_cost_orig, ib.unit_cost, 0) * COALESCE(sba.quantity_from_batch,0)) AS total_cost
                FROM sale_batch_allocations sba
                LEFT JOIN import_batches ib ON sba.batch_id = ib.id
                WHERE sba.product_id = ?
            ''', (product_id,))
            row = cur.fetchone()
            return float(row['total_cost'] or 0.0) if row else 0.0
    except Exception:
        return 0.0

def get_monthly_sales_profit(year: int):
    with get_cursor() as (conn, cur):
        cur.execute('''
        SELECT strftime('%Y-%m', sale_date) as ym,
               SUM(COALESCE(unit_sale_price,0) * COALESCE(quantity_from_batch,0)) as revenue,
               SUM(COALESCE(unit_cost,0) * COALESCE(quantity_from_batch,0)) as cogs,
               SUM((COALESCE(unit_sale_price,0) - COALESCE(unit_cost,0)) * COALESCE(quantity_from_batch,0)) as gross_profit,
               SUM(COALESCE(quantity_from_batch,0)) as items_sold
        FROM sale_batch_allocations
        WHERE strftime('%Y', sale_date) = ?
        GROUP BY ym
        ORDER BY ym
    ''', (str(year),))
        rows = cur.fetchall()
    result = {}
    for r in rows:
        k = r['ym']
        result[k] = {
            'revenue': float(r['revenue'] or 0.0),
            'cogs': float(r['cogs'] or 0.0),
            'gross_profit': float(r['gross_profit'] or 0.0),
            'items_sold': float(r['items_sold'] or 0.0),
        }
    # Apply returns adjustments (prefer DB table, fallback to CSV)
    try:
        with get_cursor() as (conn2, cur2):
            cur2.execute("SELECT COUNT(1) AS c FROM returns WHERE (deleted IS NULL OR deleted = 0)")
            has_returns = (cur2.fetchone() or {}).get('c', 0) > 0
    except Exception:
        has_returns = False

    if has_returns:
        try:
            with get_cursor() as (conn2, cur2):
                cur2.execute('''
                    SELECT return_date, strftime('%Y-%m', return_date) as ym, product_id,
                           COALESCE(refund_amount_base, 0) as refund_amount_base,
                           COALESCE(restock, 0) as restock
                    FROM returns
                    WHERE strftime('%Y', return_date) = ?
                ''', (str(year),))
                for rr in cur2.fetchall():
                    ym = rr['ym']
                    pid = rr['product_id']
                    refund_amt = float(rr['refund_amount_base'] or 0.0)
                    restock_flag = 1 if int(rr['restock'] or 0) else 0
                    bucket = result.setdefault(ym, {'revenue': 0.0, 'cogs': 0.0, 'gross_profit': 0.0, 'items_sold': 0.0})
                    bucket['revenue'] -= refund_amt
                    bucket['items_sold'] -= 1.0
                    if restock_flag and pid:
                        try:
                            with get_cursor() as (conn2b, cur2b):
                                cur2b.execute('''
                                    SELECT 
                                        SUM(COALESCE(sba.quantity_from_batch,0)) AS tq,
                                        SUM(COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_base, ib.unit_cost_orig, ib.unit_cost, 0) * COALESCE(sba.quantity_from_batch,0)) AS tc
                                    FROM sale_batch_allocations sba
                                    LEFT JOIN import_batches ib ON sba.batch_id = ib.id
                                    WHERE sba.product_id = ?
                                ''', (pid,))
                                rowc = cur2b.fetchone()
                                tq = float(rowc['tq'] or 0.0) if rowc else 0.0
                                tc = float(rowc['tc'] or 0.0) if rowc else 0.0
                                per_unit = (tc / tq) if tq > 0 else 0.0
                                bucket['cogs'] -= per_unit
                        except Exception:
                            pass
        except Exception:
            pass
    for k, v in result.items():
        v['gross_profit'] = float(v.get('revenue', 0.0)) - float(v.get('cogs', 0.0))
    return result


def get_monthly_imports_value(year: int):
    with get_cursor() as (conn, cur):
        cur.execute('''
        SELECT date, strftime('%Y-%m', date) as ym, ordered_price, quantity, COALESCE(currency,'') as currency
        FROM imports
        WHERE strftime('%Y', date) = ?
        ORDER BY date
    ''', (str(year),))
        rows = cur.fetchall()
    totals = {}
    base = get_base_currency()
    for r in rows:
        ym = r['ym']
        amt = float(r['ordered_price'] or 0.0) * float(r['quantity'] or 0.0)
        from_ccy = (r['currency'] or get_default_import_currency() or base).upper()
        date_str = r['date']
        try:
            conv = convert_amount(date_str, amt, from_ccy, base)
            val = conv if conv is not None else amt if from_ccy == base else 0.0
        except Exception:
            val = amt if from_ccy == base else 0.0
        totals[ym] = totals.get(ym, 0.0) + float(val or 0.0)
    return totals


def get_monthly_expenses(year: int):
    with get_cursor() as (conn, cur):
        cur.execute('''
        SELECT date, strftime('%Y-%m', date) as ym, COALESCE(amount,0) as amount, COALESCE(currency,'') as currency
        FROM expenses
        WHERE (deleted IS NULL OR deleted = 0) AND strftime('%Y', date) = ?
        ORDER BY date
    ''', (str(year),))
        rows = cur.fetchall()
    totals = {}
    base = get_base_currency()
    for r in rows:
        ym = r['ym']
        amt = float(r['amount'] or 0.0)
        from_ccy = (r['currency'] or base).upper()
        date_str = r['date']
        try:
            conv = convert_amount(date_str, amt, from_ccy, base)
            val = conv if conv is not None else amt if from_ccy == base else 0.0
        except Exception:
            val = amt if from_ccy == base else 0.0
        totals[ym] = totals.get(ym, 0.0) + float(val or 0.0)
    return totals


def get_yearly_sales_profit():
    with get_cursor() as (conn, cur):
        cur.execute('''
        SELECT strftime('%Y', sale_date) as y,
               SUM(COALESCE(unit_sale_price,0) * COALESCE(quantity_from_batch,0)) as revenue,
               SUM(COALESCE(unit_cost,0) * COALESCE(quantity_from_batch,0)) as cogs,
               SUM((COALESCE(unit_sale_price,0) - COALESCE(unit_cost,0)) * COALESCE(quantity_from_batch,0)) as gross_profit,
               SUM(COALESCE(quantity_from_batch,0)) as items_sold
        FROM sale_batch_allocations
        GROUP BY y
        ORDER BY y
    ''')
        rows = cur.fetchall()
    base_res = {r['y']: {
        'revenue': float(r['revenue'] or 0.0),
        'cogs': float(r['cogs'] or 0.0),
        'gross_profit': float(r['gross_profit'] or 0.0),
        'items_sold': float(r['items_sold'] or 0.0),
    } for r in rows}
    # Apply returns adjustments (prefer DB table, fallback to CSV)
    try:
        with get_cursor() as (conn2, cur2):
            cur2.execute("SELECT COUNT(1) AS c FROM returns")
            has_returns = (cur2.fetchone() or {}).get('c', 0) > 0
    except Exception:
        has_returns = False

    if has_returns:
        try:
            with get_cursor() as (conn2, cur2):
                cur2.execute('''
                    SELECT return_date, strftime('%Y', return_date) as y, product_id,
                           COALESCE(refund_amount_base, 0) as refund_amount_base,
                           COALESCE(restock, 0) as restock
                    FROM returns
                ''')
                for rr in cur2.fetchall():
                    y = rr['y']
                    pid = rr['product_id']
                    refund_amt = float(rr['refund_amount_base'] or 0.0)
                    restock_flag = 1 if int(rr['restock'] or 0) else 0
                    bucket = base_res.setdefault(y, {'revenue': 0.0, 'cogs': 0.0, 'gross_profit': 0.0, 'items_sold': 0.0})
                    bucket['revenue'] -= refund_amt
                    bucket['items_sold'] -= 1.0
                    if restock_flag and pid:
                        try:
                            with get_cursor() as (conn3, cur3):
                                cur3.execute('''
                                    SELECT 
                                        SUM(COALESCE(sba.quantity_from_batch,0)) AS tq,
                                        SUM(COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_base, ib.unit_cost_orig, ib.unit_cost, 0) * COALESCE(sba.quantity_from_batch,0)) AS tc
                                    FROM sale_batch_allocations sba
                                    LEFT JOIN import_batches ib ON sba.batch_id = ib.id
                                    WHERE sba.product_id = ?
                                ''', (pid,))
                                rowc = cur3.fetchone()
                                tq = float(rowc['tq'] or 0.0) if rowc else 0.0
                                tc = float(rowc['tc'] or 0.0) if rowc else 0.0
                                per_unit = (tc / tq) if tq > 0 else 0.0
                                bucket['cogs'] -= per_unit
                        except Exception:
                            pass
        except Exception:
            pass
    else:
        # No legacy CSV fallback: if returns table is empty we simply return the base_res as-is.
        pass
    for y, v in base_res.items():
        v['gross_profit'] = float(v.get('revenue', 0.0)) - float(v.get('cogs', 0.0))
    return base_res


def get_yearly_expenses():
    with get_cursor() as (conn, cur):
        cur.execute('''
        SELECT date, strftime('%Y', date) as y, COALESCE(amount,0) as amount, COALESCE(currency,'') as currency
        FROM expenses
        WHERE (deleted IS NULL OR deleted = 0)
        ORDER BY date
    ''')
        rows = cur.fetchall()
    totals = {}
    base = get_base_currency()
    for r in rows:
        y = r['y']
        amt = float(r['amount'] or 0.0)
        from_ccy = (r['currency'] or base).upper()
        date_str = r['date']
        try:
            conv = convert_amount(date_str, amt, from_ccy, base)
            val = conv if conv is not None else amt if from_ccy == base else 0.0
        except Exception:
            val = amt if from_ccy == base else 0.0
        totals[y] = totals.get(y, 0.0) + float(val or 0.0)
    # DB-only: returns aggregated above; legacy CSV fallback removed.
    return totals


def get_yearly_return_impact():
    out = {}
    # Prefer DB table
    try:
        with get_cursor() as (conn2, cur2):
            cur2.execute("SELECT COUNT(1) AS c FROM returns")
            has_returns = (cur2.fetchone() or {}).get('c', 0) > 0
    except Exception:
        has_returns = False

    if has_returns:
        try:
            with get_cursor() as (conn2, cur2):
                cur2.execute('''
                    SELECT strftime('%Y', return_date) as y, product_id,
                           COALESCE(refund_amount_base, 0) as refund_amount_base,
                           COALESCE(restock, 0) as restock
                    FROM returns
                ''')
                for rr in cur2.fetchall():
                    y = rr['y']
                    bucket = out.setdefault(y, {'returns_refunds': 0.0, 'returns_cogs_reversed': 0.0, 'items_returned': 0.0})
                    bucket['returns_refunds'] += float(rr['refund_amount_base'] or 0.0)
                    bucket['items_returned'] += 1.0
                    if int(rr['restock'] or 0):
                        pid = rr['product_id']
                        if pid:
                            try:
                                with get_cursor() as (conn3, cur3):
                                    cur3.execute('''
                                        SELECT 
                                            SUM(COALESCE(sba.quantity_from_batch,0)) AS tq,
                                            SUM(COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_orig, ib.unit_cost, 0) * COALESCE(sba.quantity_from_batch,0)) AS tc
                                        FROM sale_batch_allocations sba
                                        LEFT JOIN import_batches ib ON sba.batch_id = ib.id
                                        WHERE sba.product_id = ?
                                    ''', (pid,))
                                    rowc = cur3.fetchone()
                                    tq = float(rowc['tq'] or 0.0) if rowc else 0.0
                                    tc = float(rowc['tc'] or 0.0) if rowc else 0.0
                                    per_unit = (tc / tq) if tq > 0 else 0.0
                                    bucket['returns_cogs_reversed'] += per_unit
                            except Exception:
                                pass
        except Exception:
            return out
        return out
    # DB-only: do not attempt to read legacy CSV files for returns.
    # The `out` value above is built using the `returns` table; if DB access
    # failed earlier, we return the (possibly-empty) `out` value. This avoids
    # any runtime dependency on legacy CSV files.
    return out


def get_monthly_return_impact(year: int):
    """Return a dict keyed by YYYY-MM with aggregated returns impact from the returns table.

    This is DB-only and does not attempt to read legacy CSV files.
    """
    out = {}
    try:
        with get_cursor() as (conn, cur):
            cur.execute('''
            SELECT strftime('%Y-%m', return_date) as ym, product_id,
                   COALESCE(refund_amount_base, 0) as refund_amount_base,
                   COALESCE(restock, 0) as restock
            FROM returns
            WHERE strftime('%Y', return_date) = ?
        ''', (str(year),))
            for rr in cur.fetchall():
                ym = rr['ym']
                bucket = out.setdefault(ym, {'returns_refunds': 0.0, 'returns_cogs_reversed': 0.0, 'items_returned': 0.0})
                bucket['returns_refunds'] += float(rr['refund_amount_base'] or 0.0)
                bucket['items_returned'] += 1.0
                if int(rr['restock'] or 0):
                    pid = rr['product_id']
                    if pid:
                        try:
                            with get_cursor() as (conn2, cur2):
                                cur2.execute('''
                                    SELECT 
                                        SUM(COALESCE(sba.quantity_from_batch,0)) AS tq,
                                        SUM(COALESCE(NULLIF(sba.unit_cost,0), ib.unit_cost_orig, ib.unit_cost, 0) * COALESCE(sba.quantity_from_batch,0)) AS tc
                                    FROM sale_batch_allocations sba
                                    LEFT JOIN import_batches ib ON sba.batch_id = ib.id
                                    WHERE sba.product_id = ?
                                ''', (pid,))
                                rowc = cur2.fetchone()
                                tq = float(rowc['tq'] or 0.0) if rowc else 0.0
                                tc = float(rowc['tc'] or 0.0) if rowc else 0.0
                                per_unit = (tc / tq) if tq > 0 else 0.0
                                bucket['returns_cogs_reversed'] += per_unit
                        except Exception:
                            pass
        
    except Exception:
        pass
    return out


def get_yearly_imports_value():
    with get_cursor() as (conn, cur):
        cur.execute('''
        SELECT date, strftime('%Y', date) as y, ordered_price, quantity, COALESCE(currency,'') as currency
        FROM imports
        ORDER BY date
    ''')
        rows = cur.fetchall()
    totals = {}
    base = get_base_currency()
    for r in rows:
        y = r['y']
        amt = float(r['ordered_price'] or 0.0) * float(r['quantity'] or 0.0)
        from_ccy = (r['currency'] or get_default_import_currency() or base).upper()
        date_str = r['date']
        try:
            conv = convert_amount(date_str, amt, from_ccy, base)
            val = conv if conv is not None else amt if from_ccy == base else 0.0
        except Exception:
            val = amt if from_ccy == base else 0.0
        totals[y] = totals.get(y, 0.0) + float(val or 0.0)
    return totals


def build_monthly_overview(year: int):
    sales = get_monthly_sales_profit(year)
    expenses = get_monthly_expenses(year)
    returns_impact = get_monthly_return_impact(year)
    months = [f"{year}-{m:02d}" for m in range(1, 13)]
    rows = []
    for ym in months:
        s = sales.get(ym, {})
        revenue = float(s.get('revenue', 0.0))
        cogs = float(s.get('cogs', 0.0))
        gp = float(s.get('gross_profit', 0.0))
        items = float(s.get('items_sold', 0.0))
        exp = float(expenses.get(ym, 0.0))
        net = gp - exp
        ri = returns_impact.get(ym, {'returns_refunds': 0.0, 'returns_cogs_reversed': 0.0, 'items_returned': 0.0})
        rows.append({
            'ym': ym,
            'revenue': revenue,
            'cogs': cogs,
            'gross_profit': gp,
            'expenses': exp,
            'net_profit': net,
            'items_sold': items,
            'returns_refunds': float(ri['returns_refunds']),
            'returns_cogs_reversed': float(ri['returns_cogs_reversed']),
            'returns_net_impact': float(ri['returns_cogs_reversed']) - float(ri['returns_refunds']),
            'items_returned': float(ri['items_returned']),
        })
    return rows


def build_yearly_summary():
    sales = get_yearly_sales_profit()
    expenses = get_yearly_expenses()
    imports = get_yearly_imports_value()
    returns_impact = get_yearly_return_impact()
    years = sorted(set(list(sales.keys()) + list(expenses.keys()) + list(imports.keys())))
    rows = []
    for y in years:
        s = sales.get(y, {})
        revenue = float(s.get('revenue', 0.0))
        cogs = float(s.get('cogs', 0.0))
        gp = float(s.get('gross_profit', 0.0))
        items = float(s.get('items_sold', 0.0))
        exp = float(expenses.get(y, 0.0))
        net = gp - exp
        ri = returns_impact.get(y, {'returns_refunds': 0.0, 'returns_cogs_reversed': 0.0, 'items_returned': 0.0})
        rows.append({
            'year': y,
            'revenue': revenue,
            'cogs': cogs,
            'gross_profit': gp,
            'expenses': exp,
            'net_profit': net,
            'imports_value': float(imports.get(y, 0.0)),
            'items_sold': items,
            'returns_refunds': float(ri['returns_refunds']),
            'returns_cogs_reversed': float(ri['returns_cogs_reversed']),
            'returns_net_impact': float(ri['returns_cogs_reversed']) - float(ri['returns_refunds']),
            'items_returned': float(ri['items_returned']),
        })
    return rows

def get_batch_utilization_report_inclusive(include_expenses: bool = False):
    with get_cursor() as (conn, cur):
        cur.execute('''
        SELECT 
            ib.id,
            ib.import_id,
            ib.batch_date,
            ib.category,
            ib.subcategory,
            ib.supplier,
            ib.original_quantity,
            ib.remaining_quantity,
            ib.unit_cost,
            (ib.original_quantity - ib.remaining_quantity) as allocated_quantity,
            COALESCE(SUM(sba.quantity_from_batch * sba.unit_sale_price), 0) as total_revenue,
            COALESCE(SUM(sba.quantity_from_batch * sba.profit_per_unit), 0) as total_profit_unadj
        FROM import_batches ib
        LEFT JOIN sale_batch_allocations sba ON ib.id = sba.batch_id
        GROUP BY ib.id
        ORDER BY ib.batch_date DESC
    ''')
        rows_raw = [dict(r) for r in cur.fetchall()]
    # For inclusive view we want to present payment-weighted unit costs. Those are
    # computed and stored in import_batches.unit_cost by recompute_import_batches.
    # If include_expenses is False the caller should use `get_batch_utilization_report`
    # which prefers `unit_cost_orig`. Here we simply expose the stored unit_cost
    # (which should be the adjusted price when recompute has been run for that import).
    out = []
    for r in rows_raw:
        unit_cost = float(r['unit_cost'] or 0.0)
        allocated_qty = float(r['allocated_quantity'] or 0.0)
        total_cost_allocated = allocated_qty * unit_cost
        out.append({
            'id': r['id'],
            'batch_date': r['batch_date'],
            'category': r['category'],
            'subcategory': r['subcategory'],
            'supplier': r['supplier'],
            'original_quantity': float(r['original_quantity']),
            'remaining_quantity': float(r['remaining_quantity']),
            'unit_cost': unit_cost,
            'allocated_quantity': allocated_qty,
            'total_cost_allocated': round(total_cost_allocated, 2),
            'total_revenue': float(r['total_revenue'] or 0.0),
            'total_profit': float(r['total_profit_unadj'] or 0.0),
        })
    return out



def get_batch_utilization_report():
    with get_cursor() as (conn, cur):
        cur.execute('''
        SELECT 
            ib.id,
            ib.batch_date,
            ib.category,
            ib.subcategory,
            ib.supplier,
            ib.original_quantity,
            ib.remaining_quantity,
                COALESCE(ib.unit_cost_orig, ib.unit_cost_base, ib.unit_cost, 0) AS unit_cost,
            ib.original_quantity - ib.remaining_quantity as allocated_quantity,
            ROUND((ib.original_quantity - ib.remaining_quantity) * COALESCE(ib.unit_cost_orig, ib.unit_cost_base, ib.unit_cost), 2) as total_cost_allocated,
            COALESCE(SUM(sba.quantity_from_batch * sba.unit_sale_price), 0) as total_revenue,
            COALESCE(SUM(sba.quantity_from_batch * sba.profit_per_unit), 0) as total_profit
        FROM import_batches ib
        LEFT JOIN sale_batch_allocations sba ON ib.id = sba.batch_id AND (sba.deleted IS NULL OR sba.deleted = 0)
        GROUP BY ib.id
        ORDER BY ib.batch_date DESC
    ''')
        rows = [dict(r) for r in cur.fetchall()]
    # Apply returns adjustments per batch: if a returned product maps to a batch allocation,
    # subtract refund_amount_base from that batch's revenue and profit. If restock is true,
    # increment remaining_quantity and reduce allocated_quantity accordingly (reporting only).
    try:
        with get_cursor() as (conn2, cur2):
            # Fetch returns with refund_amount_base and product_id/restock
            # Only consider non-deleted returns
            cur2.execute("SELECT id, product_id, refund_amount_base, restock, sale_date FROM returns WHERE (deleted IS NULL OR deleted = 0)")
            returns = cur2.fetchall()
            # Build a map of batch adjustments keyed by batch_id
            batch_adj = {}
            for ret in returns:
                try:
                    rid = ret['id'] if isinstance(ret, dict) else ret[0]
                    pid = ret['product_id'] if isinstance(ret, dict) else ret[1]
                    refund_base = float(ret['refund_amount_base'] or 0.0) if isinstance(ret, dict) else float(ret[2] or 0.0)
                    restock = int(ret['restock'] if isinstance(ret, dict) else ret[3] or 0)
                except Exception:
                    # row might be sqlite3.Row
                    try:
                        pid = ret['product_id']
                        refund_base = float(ret['refund_amount_base'] or 0.0)
                        restock = int(ret['restock'] or 0)
                    except Exception:
                        continue
                if not pid:
                    continue
                # Prefer allocations matching the original sale_date when available (credit the exact batch)
                sale_date = None
                try:
                    sale_date = ret['sale_date'] if isinstance(ret, dict) else ret[4]
                except Exception:
                    sale_date = None
                if sale_date:
                    cur2.execute('''
                        SELECT batch_id, quantity_from_batch, unit_cost, unit_sale_price
                        FROM sale_batch_allocations
                        WHERE product_id = ? AND sale_date = ? AND (deleted IS NULL OR deleted = 0)
                        ORDER BY id DESC
                    ''', (pid, sale_date))
                else:
                    # Fallback: allocations for this product ordered by id DESC (latest allocations first)
                    cur2.execute('''
                        SELECT batch_id, quantity_from_batch, unit_cost, unit_sale_price
                        FROM sale_batch_allocations
                        WHERE product_id = ? AND (deleted IS NULL OR deleted = 0) ORDER BY id DESC
                    ''', (pid,))
                allocs = cur2.fetchall()
                remaining_refund = refund_base
                remaining_units = 1.0  # assume 1 unit returned per return row; extend if returns store quantity
                for a in allocs:
                    batch_id = a['batch_id'] if isinstance(a, dict) else a[0]
                    qty_from_batch = float(a['quantity_from_batch'] if isinstance(a, dict) else a[1] or 0.0)
                    unit_cost = float(a['unit_cost'] if isinstance(a, dict) else a[2] or 0.0)
                    unit_sale = float(a['unit_sale_price'] if isinstance(a, dict) else a[3] or 0.0)
                    if batch_id is None:
                        continue
                    # Attribute one unit (or as much as available) to this batch
                    used_units = min(remaining_units, qty_from_batch)
                    if used_units <= 0:
                        continue
                    # Prepare batch adjustment entry
                    b = batch_adj.setdefault(batch_id, {'rev_delta': 0.0, 'profit_delta': 0.0, 'remaining_delta': 0.0, 'allocated_delta': 0.0})
                    # Subtract proportional revenue (use per-unit sale price)
                    rev_delta = used_units * unit_sale * -1.0
                    b['rev_delta'] += rev_delta
                    # If restock, add units back to remaining_quantity and remove from allocated
                    if restock:
                        # For restocked returns we assume import_batches has already been updated when the return
                        # was recorded (insert_return persists the restock). Do not apply remaining/allocated
                        # deltas again here to avoid double-counting. We still subtract revenue via rev_delta.
                        break
            # Apply adjustments to rows list — recompute cost & profit from adjusted revenue and allocated quantities
            for i, row in enumerate(rows):
                bid = row.get('id')
                adj = batch_adj.get(bid)
                if not adj:
                    continue
                try:
                    # adjust revenue
                    new_revenue = float(row.get('total_revenue', 0.0)) + float(adj.get('rev_delta', 0.0))
                    # adjust quantities
                    new_allocated = float(row.get('allocated_quantity', 0.0)) + float(adj.get('allocated_delta', 0.0))
                    new_remaining = float(row.get('remaining_quantity', 0.0)) + float(adj.get('remaining_delta', 0.0))
                    # recompute cost allocated from adjusted allocated quantity
                    unit_cost = float(row.get('unit_cost', 0.0))
                    new_total_cost_allocated = round(max(0.0, new_allocated) * unit_cost, 2)
                    # derive profit as revenue - cost
                    new_total_profit = round(float(new_revenue) - float(new_total_cost_allocated), 6)

                    row['total_revenue'] = new_revenue
                    row['allocated_quantity'] = new_allocated
                    row['remaining_quantity'] = new_remaining
                    row['total_cost_allocated'] = new_total_cost_allocated
                    row['total_profit'] = new_total_profit
                except Exception:
                    pass
    except Exception:
        pass

    return rows