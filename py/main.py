"""Legacy launcher shim.

Allows running `python py/main.py` while actual entry point moved to app/main.py.
"""
from app.main import *  # type: ignore

