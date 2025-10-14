"""Compat shim for old import path.

This file preserves legacy imports (import py.db as db) after moving real implementation to app/db/db.py. All logic remains untouched in new location.
"""
from app.db.db import *  # type: ignore

