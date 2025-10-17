from .connection import get_conn
from .auth import _CURRENT_USER

def write_audit(action: str, entity: str, ref_id: str = '', details: str = ''):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('INSERT INTO audit_log (user, action, entity, ref_id, details) VALUES (?,?,?,?,?)',
                    (_CURRENT_USER.get('username'), action, entity, str(ref_id or ''), details))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_audit_logs(start_date: str = None, end_date: str = None, user: str = None,
                   action: str = None, entity: str = None, q: str = None, limit: int = 1000):
    conn = get_conn()
    cur = conn.cursor()
    where = []
    params = []
    if start_date:
        where.append("date(ts) >= date(?)")
        params.append(start_date)
    if end_date:
        where.append("date(ts) <= date(?)")
        params.append(end_date)
    if user:
        where.append("user = ?")
        params.append(user)
    if action:
        where.append("action = ?")
        params.append(action)
    if entity:
        where.append("entity = ?")
        params.append(entity)
    if q:
        where.append("(details LIKE ? OR ref_id LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])
    sql = "SELECT id, ts, user, action, entity, ref_id, details FROM audit_log"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY datetime(ts) DESC LIMIT ?"
    params.append(limit)
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_audit_distinct(field: str):
    if field not in ("user", "action", "entity"):
        return []
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT DISTINCT {field} FROM audit_log WHERE {field} IS NOT NULL AND {field} <> '' ORDER BY {field}")
    vals = [r[0] for r in cur.fetchall()]
    conn.close()
    return vals
