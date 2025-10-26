from .connection import DB_PATH,get_conn

def float_or_none(v):
    try:
        return float(v)
    except Exception:
        return None

def delete_database_file():
    try:
        if DB_PATH.exists():
            DB_PATH.unlink()
            return True
    except Exception:
        return False
    return False

def reset_all_tables(clear_product_codes=True):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('DELETE FROM imports')
    cur.execute('DELETE FROM inventory')
    cur.execute('DELETE FROM expenses')
    if clear_product_codes:
        cur.execute('DELETE FROM product_codes')
    conn.commit()
    conn.close()
