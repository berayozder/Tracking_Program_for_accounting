from .connection import get_conn
import os
import hashlib
import hmac
from typing import Optional, Dict, Any

# ------------------------ SECURITY: USERS & AUTH ------------------------
_CURRENT_USER: Dict[str, Any] = {"username": None, "role": None}


def _pbkdf2_hash(password: str, salt: bytes, iterations: int = 120_000) -> bytes:
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)


def create_user(username: str, password: str, role: str = 'user') -> bool:
    if not username or not password:
        return False
    conn = get_conn()
    cur = conn.cursor()
    salt = os.urandom(16)
    pwd_hash = _pbkdf2_hash(password, salt)
    try:
        cur.execute('INSERT INTO users (username, password_hash, salt, role) VALUES (?,?,?,?)',
                    (username.strip(), pwd_hash, salt, role.strip() or 'user'))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def users_exist() -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) as c FROM users')
    row = cur.fetchone()
    conn.close()
    return bool(row and (row['c'] or 0) > 0)


def verify_user(username: str, password: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT username, password_hash, salt, role FROM users WHERE username=?', (username.strip(),))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    salt = row['salt']
    expected = row['password_hash']
    test = _pbkdf2_hash(password, salt)
    if not hmac.compare_digest(expected, test):
        return False
    _CURRENT_USER['username'] = row['username']
    _CURRENT_USER['role'] = row['role'] or 'user'
    return True


def set_current_user(username: Optional[str], role: Optional[str]):
    _CURRENT_USER['username'] = username
    _CURRENT_USER['role'] = role


def get_current_user() -> Dict[str, Optional[str]]:
    return {"username": _CURRENT_USER.get('username'), "role": _CURRENT_USER.get('role')}


def require_admin(action: str, entity: str, ref_id: str = ''):
    role = (_CURRENT_USER.get('role') or 'user').lower()
    if role != 'admin':
        raise PermissionError('Admin privileges required')
