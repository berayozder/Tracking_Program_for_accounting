import logging
from typing import List, Optional, Dict
from .connection import get_conn
from .auth import _CURRENT_USER

# Configure logging for this module
logger = logging.getLogger(__name__)


def write_audit(action: str, entity: str, ref_id: Optional[str] = None, details: str = "") -> None:
    """
    Write an audit log entry.

    Args:
        action (str): The action performed.
        entity (str): The entity on which the action was performed.
        ref_id (Optional[str]): Optional reference ID related to the entity.
        details (str): Additional details about the action.
    """
    ref_id = str(ref_id) if ref_id else ""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO audit_log (user, action, entity, ref_id, details) VALUES (?, ?, ?, ?, ?)",
                (_CURRENT_USER.get("username"), action, entity, ref_id, details),
            )
    except Exception as e:
        logger.error("Failed to write audit log: %s", e)


def get_audit_logs(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: Optional[str] = None,
    action: Optional[str] = None,
    entity: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 1000,
) -> List[Dict]:
    """
    Fetch audit logs with optional filtering.

    Args:
        start_date (Optional[str]): Filter logs from this date (YYYY-MM-DD).
        end_date (Optional[str]): Filter logs up to this date (YYYY-MM-DD).
        user (Optional[str]): Filter by user.
        action (Optional[str]): Filter by action.
        entity (Optional[str]): Filter by entity.
        q (Optional[str]): Search term in details or ref_id.
        limit (int): Max number of records to return.

    Returns:
        List[Dict]: List of audit log entries as dictionaries.
    """
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

    try:
        with get_conn() as conn:
            conn.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
        return rows
    except Exception as e:
        logger.error("Failed to fetch audit logs: %s", e)
        return []


def get_audit_distinct(field: str) -> List[str]:
    """
    Get distinct values for a field in the audit log.

    Args:
        field (str): Must be one of 'user', 'action', 'entity'.

    Returns:
        List[str]: List of distinct values.
    """
    allowed_fields = {"user", "action", "entity"}
    if field not in allowed_fields:
        logger.warning("Invalid field requested for distinct values: %s", field)
        return []

    sql = f"SELECT DISTINCT {field} FROM audit_log WHERE {field} IS NOT NULL AND {field} <> '' ORDER BY {field}"

    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(sql)
            vals = [r[0] for r in cur.fetchall()]
        return vals
    except Exception as e:
        logger.error("Failed to fetch distinct values for %s: %s", field, e)
        return []
