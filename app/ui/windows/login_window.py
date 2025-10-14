import tkinter as tk
from tkinter import ttk, messagebox
import db


def open_login_dialog(root) -> bool:
    """Show a modal login. If no users exist, prompt to create admin first.
    Returns True if a user is authenticated and set; False otherwise.
    """
    # Bootstrap admin if db empty
    if not db.users_exist():
        if not _bootstrap_admin(root):
            return False

    dlg = tk.Toplevel(root)
    dlg.title('Login')
    dlg.geometry('360x200')
    try:
        dlg.minsize(320, 180)
    except Exception:
        pass
    dlg.transient(root)
    dlg.grab_set()

    try:
        from .theme import apply_theme
        apply_theme(dlg)
    except Exception:
        pass

    frm = ttk.Frame(dlg, padding=16)
    frm.pack(fill='both', expand=True)

    ttk.Label(frm, text='Username:').pack(anchor='w', pady=(0, 4))
    user_e = ttk.Entry(frm)
    user_e.pack(fill='x', pady=(0, 8))
    user_e.focus_set()

    ttk.Label(frm, text='Password:').pack(anchor='w', pady=(0, 4))
    pass_e = ttk.Entry(frm, show='•')
    pass_e.pack(fill='x', pady=(0, 12))

    auth_ok = {'ok': False}

    def do_login():
        u = user_e.get().strip()
        p = pass_e.get().strip()
        if not (u and p):
            messagebox.showwarning('Missing', 'Enter username and password', parent=dlg)
            return
        if db.verify_user(u, p):
            auth_ok['ok'] = True
            dlg.destroy()
        else:
            messagebox.showerror('Login failed', 'Invalid credentials', parent=dlg)

    btns = ttk.Frame(frm)
    btns.pack(fill='x')
    ttk.Button(btns, text='Cancel', command=lambda: dlg.destroy()).pack(side='left')
    ttk.Button(btns, text='Login', style='Primary.TButton', command=do_login).pack(side='right')

    dlg.wait_window()
    return bool(auth_ok['ok'])


def _bootstrap_admin(root) -> bool:
    """Prompt to create the first admin account."""
    dlg = tk.Toplevel(root)
    dlg.title('Create Admin')
    dlg.geometry('380x240')
    try:
        dlg.minsize(340, 220)
    except Exception:
        pass
    dlg.transient(root)
    dlg.grab_set()

    try:
        from .theme import apply_theme
        apply_theme(dlg)
    except Exception:
        pass

    frm = ttk.Frame(dlg, padding=16)
    frm.pack(fill='both', expand=True)
    ttk.Label(frm, text='Create administrator account', font=('', 12, 'bold')).pack(anchor='w', pady=(0, 8))

    ttk.Label(frm, text='Admin username:').pack(anchor='w')
    user_e = ttk.Entry(frm)
    user_e.pack(fill='x', pady=(0, 8))
    user_e.insert(0, 'admin')

    ttk.Label(frm, text='Password:').pack(anchor='w')
    pass_e = ttk.Entry(frm, show='•')
    pass_e.pack(fill='x', pady=(0, 8))

    ttk.Label(frm, text='Confirm password:').pack(anchor='w')
    pass2_e = ttk.Entry(frm, show='•')
    pass2_e.pack(fill='x', pady=(0, 12))

    done = {'ok': False}

    def do_create():
        u = user_e.get().strip()
        p1 = pass_e.get().strip()
        p2 = pass2_e.get().strip()
        if not (u and p1 and p2):
            messagebox.showwarning('Missing', 'All fields required', parent=dlg)
            return
        if p1 != p2:
            messagebox.showerror('Mismatch', 'Passwords do not match', parent=dlg)
            return
        if not db.create_user(u, p1, role='admin'):
            messagebox.showerror('Error', 'Failed to create admin (username may exist)', parent=dlg)
            return
        done['ok'] = True
        dlg.destroy()

    btns = ttk.Frame(frm)
    btns.pack(fill='x')
    ttk.Button(btns, text='Cancel', command=lambda: dlg.destroy()).pack(side='left')
    ttk.Button(btns, text='Create', style='Primary.TButton', command=do_create).pack(side='right')

    dlg.wait_window()
    return bool(done['ok'])
