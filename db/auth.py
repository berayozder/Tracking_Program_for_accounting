from .connection import get_conn, get_cursor
import os
import hashlib
import hmac
from typing import Optional, Dict, Any

# ------------------------ SECURITY: USERS & AUTH ------------------------
_CURRENT_USER: Dict[str, Optional[str]] = {"username": None, "role": None}


def _pbkdf2_hash(password: str, salt: bytes, iterations: int = 120_000) -> bytes:
    """Return PBKDF2-HMAC-SHA256 hash of a password."""
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)


def create_user(username: str, password: str, role: str = 'user') -> bool:
    """Create a new user with hashed password and unique salt."""
    username, role = username.strip(), role.strip() or 'user'
    if not username or not password:
        return False

    salt = os.urandom(16)
    pwd_hash = _pbkdf2_hash(password, salt)

    try:
        with get_cursor() as (conn, cur):
            cur.execute(
                'INSERT INTO users (username, password_hash, salt, role) VALUES (?,?,?,?)',
                (username, pwd_hash, salt, role)
            )
            conn.commit()
            return True
    except Exception as e:
        print(f"[ERROR] Failed to create user: {e}")
        return False


def users_exist() -> bool:
    """Check if there is at least one user in the database."""
    with get_cursor() as (conn, cur):
        cur.execute('SELECT COUNT(*) AS c FROM users')
        row = cur.fetchone()
        return bool(row and (row['c'] or 0) > 0)


def verify_user(username: str, password: str) -> bool:
    """Verify a user's password and set _CURRENT_USER if valid."""
    username = username.strip()
    with get_cursor() as (conn, cur):
        cur.execute(
            'SELECT username, password_hash, salt, role FROM users WHERE username=?',
            (username,)
        )
        row = cur.fetchone()

    if not row:
        return False

    test_hash = _pbkdf2_hash(password, row['salt'])
    if not hmac.compare_digest(row['password_hash'], test_hash):
        return False

    _CURRENT_USER['username'] = row['username']
    _CURRENT_USER['role'] = row['role'] or 'user'
    return True


def set_current_user(username: Optional[str], role: Optional[str]):
    _CURRENT_USER['username'] = username
    _CURRENT_USER['role'] = role


def get_current_user() -> Dict[str, Optional[str]]:
    return {"username": _CURRENT_USER.get('username'), "role": _CURRENT_USER.get('role')}


def require_admin(action: str = '', entity: str = '', ref_id: str = ''):
    """Raise PermissionError if current user is not admin."""
    if (_CURRENT_USER.get('role') or 'user').lower() != 'admin':
        raise PermissionError("Admin privileges required")
