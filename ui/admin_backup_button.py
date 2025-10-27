import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from pathlib import Path
import threading
import shutil
import zipfile
import os

BACKUP_DIR = Path(__file__).resolve().parents[1] / 'data' / 'backups'
DATA_DIR = Path(__file__).resolve().parents[1] / 'data'
BACKUP_KEEP = 5  # Number of backups to keep


def zip_data_folder():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    zip_path = BACKUP_DIR / f"data-backup-{stamp}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in DATA_DIR.glob('*'):
            if file.is_file() and file.name != 'backups':
                zipf.write(file, arcname=file.name)
    # Remove old backups
    backups = sorted(BACKUP_DIR.glob('data-backup-*.zip'), key=os.path.getmtime, reverse=True)
    for old in backups[BACKUP_KEEP:]:
        try:
            old.unlink()
        except Exception:
            pass
    return zip_path


def backup_now_callback(parent):
    def do_backup():
        try:
            zip_path = zip_data_folder()
            parent.after(0, lambda: messagebox.showinfo('Backup', f'Backup created at:\n{zip_path}'))
        except Exception as e:
            parent.after(0, lambda: messagebox.showerror('Backup', f'Failed to backup: {e}'))
    threading.Thread(target=do_backup, daemon=True).start()


def add_backup_button_to_frame(frame, parent):
    # Use ttk.Button or themed_button for consistent appearance
    from .theme import themed_button
    row = frame.grid_size()[1]
    btn = themed_button(frame, text='🗄️ One-Click Data Backup', variant='primary', command=lambda: backup_now_callback(parent))
    btn.grid(row=row, column=0, columnspan=2, sticky='ew', pady=8, padx=0)
    return btn

# For scheduled/automatic backup, you can call backup_now_callback periodically from your mainloop or a scheduler.
