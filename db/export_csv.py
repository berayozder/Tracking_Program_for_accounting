"""Export DB tables to CSV (migrated path usage updated).

Usage:
    python -m db.export_csv             # Export missing CSVs only
    python -m db.export_csv --overwrite # Force regenerate CSVs
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
import shutil

from . import db  # type: ignore


def _timestamp() -> str:
    return datetime.now().strftime('%Y%m%d-%H%M%S')


def _backup_if_exists(path: Path):
    if path.exists() and path.stat().st_size > 0:
        backup = path.with_suffix(path.suffix + f".bak-{_timestamp()}")
        shutil.copy2(path, backup)
        return backup
    return None


def export_imports(target: Path, overwrite: bool):
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, date, ordered_price, quantity, supplier, category, subcategory, currency, notes FROM imports ORDER BY id ASC')
    rows = cur.fetchall()
    conn.close()
    if target.exists() and target.stat().st_size > 0 and not overwrite:
        return 'imports.csv exists (skip)', 0
    _backup_if_exists(target)
    headers = ['ID','Date','OrderedPrice','Quantity','Supplier','Category','Subcategory','Currency','Notes']
    with target.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            try:
                notes = db.decrypt_str(r['notes'])  # type: ignore[attr-defined]
            except Exception:
                notes = r['notes']
            w.writerow([r['id'], r['date'], r['ordered_price'], r['quantity'], r['supplier'], r['category'], r['subcategory'], r['currency'], notes])
    return 'imports.csv exported', len(rows)


def export_expenses(target: Path, overwrite: bool):
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, date, amount, is_import_related, import_id, category, notes, document_path, currency FROM expenses ORDER BY id ASC')
    rows = cur.fetchall()
    links_map = {}
    try:
        cur.execute('SELECT expense_id, import_id FROM expense_import_links')
        for exp_id, imp_id in cur.fetchall():
            links_map.setdefault(exp_id, []).append(imp_id)
    except Exception:
        pass
    conn.close()
    if target.exists() and target.stat().st_size > 0 and not overwrite:
        return 'expenses.csv exists (skip)', 0
    _backup_if_exists(target)
    headers = ['ID','Date','Amount','IsImportRelated','PrimaryImportID','LinkedImportIDs','Category','Notes','DocumentPath','Currency']
    with target.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            try:
                notes = db.decrypt_str(r['notes'])  # type: ignore[attr-defined]
            except Exception:
                notes = r['notes']
            linked = links_map.get(r['id'], [])
            w.writerow([r['id'], r['date'], r['amount'], r['is_import_related'], r['import_id'], ';'.join(str(x) for x in linked), r['category'], notes, r['document_path'], r['currency']])
    return 'expenses.csv exported', len(rows)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description='Export DB tables to CSV (one-time backfill)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing non-empty CSV files')
    args = parser.parse_args(argv)
    data_dir = (Path(__file__).resolve().parents[1] / 'data')
    data_dir.mkdir(parents=True, exist_ok=True)
    imports_path = data_dir / 'imports.csv'
    expenses_path = data_dir / 'expenses.csv'
    imp_status, imp_count = export_imports(imports_path, args.overwrite)
    exp_status, exp_count = export_expenses(expenses_path, args.overwrite)
    print('RESULT:')
    print(f'  {imp_status} (rows={imp_count})')
    print(f'  {exp_status} (rows={exp_count})')
    print('Done.')


if __name__ == '__main__':  # pragma: no cover
    main()
