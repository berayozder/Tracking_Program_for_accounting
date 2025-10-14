import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pathlib import Path
import shutil
import os
import py.db.db as db
from .theme import maximize_window, themed_button


BACKUP_DIR = (Path(__file__).resolve().parents[1] / 'data' / 'backups')


def _fmt_bytes(n: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if n < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def _get_db_info():
    p = db.DB_PATH
    size = p.stat().st_size if p.exists() else 0
    return {
        'path': str(p),
        'exists': p.exists(),
        'size': size,
        'size_h': _fmt_bytes(size),
        'modified': datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S') if p.exists() else 'N/A'
    }


def open_backup_window(root):
    win = tk.Toplevel(root)
    win.title('Database Backup & Restore')
    win.geometry('640x360')
    try:
        win.minsize(560, 320)
    except Exception:
        pass
    try:
        maximize_window(win)
    except Exception:
        pass

    info = _get_db_info()

    info_frame = ttk.LabelFrame(win, text='Database', padding=12)
    info_frame.pack(fill='x', padx=12, pady=12)

    ttk.Label(info_frame, text=f"Path: {info['path']}").pack(anchor='w')
    ttk.Label(info_frame, text=f"Exists: {info['exists']}").pack(anchor='w')
    ttk.Label(info_frame, text=f"Size: {info['size_h']}").pack(anchor='w')
    ttk.Label(info_frame, text=f"Last Modified: {info['modified']}").pack(anchor='w')

    btns = ttk.Frame(win)
    btns.pack(fill='x', padx=12, pady=(0, 12))

    def backup_now():
        try:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            dest = BACKUP_DIR / f"app-{stamp}.db"
            shutil.copy2(db.DB_PATH, dest)
            db.write_audit('backup', 'database', str(dest), f"Backup created: {dest}")
            messagebox.showinfo('Backup', f'Backup created at:\n{dest}')
        except Exception as e:
            messagebox.showerror('Backup', f'Failed to backup: {e}')

    def restore_now():
        # admin only
        try:
            db.require_admin('restore', 'database')
        except Exception as e:
            messagebox.showerror('Restore', str(e))
            return
        path = filedialog.askopenfilename(title='Restore from backup',
                                          filetypes=[('DB files', '*.db'), ('All files', '*.*')])
        if not path:
            return
        if not messagebox.askyesno('Confirm Restore', 'This will replace the current database file. A backup of the current DB will be created first. Continue?'):
            return
        try:
            # backup current
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            current_backup = BACKUP_DIR / f"app-before-restore-{stamp}.db"
            if Path(db.DB_PATH).exists():
                shutil.copy2(db.DB_PATH, current_backup)
            # copy chosen file to DB path
            shutil.copy2(path, db.DB_PATH)
            db.write_audit('restore', 'database', str(path), f"Restored from: {path}")
            messagebox.showinfo('Restore', 'Restore complete. Please restart the application.')
        except Exception as e:
            messagebox.showerror('Restore', f'Failed to restore: {e}')

    themed_button(btns, text='💾 Backup Now', variant='primary', command=backup_now).pack(side='left')
    themed_button(btns, text='⤵️ Restore From File…', variant='danger', command=restore_now).pack(side='left', padx=8)

    themed_button(win, text='Close', variant='secondary', command=win.destroy).pack(pady=12)
