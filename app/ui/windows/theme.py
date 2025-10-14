import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import font as tkfont
from typing import Union, Optional
from pathlib import Path
import sys

# Try to use ttkbootstrap's "superhero" theme when available
_BOOTSTRAP_AVAILABLE = False
_THEME_APPLIED = False
try:
    import ttkbootstrap as tb  # type: ignore
    _BOOTSTRAP_AVAILABLE = True
except Exception:
    _BOOTSTRAP_AVAILABLE = False


COLORS = {
    'primary': '#007acc',
    'primary_dark': '#005a9e',
    'secondary': "#000059",
    'success': '#28a745',
    'warning': '#ffc107',
    'danger': '#dc3545',
    'light': "#515151",
    'dark': '#343a40',
    'accent': '#17a2b8',
}

FONTS = {
    'title': ('Arial', 20, 'bold'),
    'subtitle': ('Arial', 10),
    'label': ('', 11),
    'button': ('', 11, 'bold'),
    'small': ('Arial', 8),
}


def apply_theme(root: Union[tk.Tk, tk.Toplevel]):
    global _THEME_APPLIED
    # Prevent re-initializing theme/styles on child windows (would affect global app styles)
    if _THEME_APPLIED:
        return
    # Initialize ttkbootstrap superhero theme if available
    if _BOOTSTRAP_AVAILABLE:
        try:
            # Initialize bootstrap style (sets theme globally)
            tb.Style(theme="superhero")
        except Exception:
            # Fallback to default ttk theme selection
            pass

    style = ttk.Style()
    # If ttkbootstrap isn't available or failed, prefer a modern ttk theme
    try:
        if not _BOOTSTRAP_AVAILABLE:
            if 'clam' in style.theme_names():
                style.theme_use('clam')
    except Exception:
        pass

    # Detect dark mode if using ttkbootstrap superhero
    is_dark = _BOOTSTRAP_AVAILABLE

    # Color palette (tuned for readability)
    colors = {**COLORS,
              'fg': ('#e9ecef' if is_dark else '#212529'),
              'muted': ('#cfd8dc' if is_dark else '#495057')}

    # Global scaling to make text and widgets larger
    try:
        # 1.0 is default; 1.2-1.3 gives ~20-30% larger UI
        root.tk.call('tk', 'scaling', 1.25)
    except Exception:
        pass

    # Enlarge Tk named fonts (affects many widgets)
    try:
        for name, size in (
            ("TkDefaultFont", 11),
            ("TkTextFont", 11),
            ("TkHeadingFont", 12),
            ("TkMenuFont", 11),
            ("TkTooltipFont", 10),
        ):
            f = tkfont.nametofont(name)
            f.configure(size=size)
    except Exception:
        pass

    # Base paddings and styling
    try:
        style.configure('TLabel', padding=(3, 3), font=('', 11), foreground=colors['fg'])
        # Ensure default buttons have dark text on a light background (independent of COLORS overrides)
        style.configure('TButton', padding=(12, 10), font=FONTS['button'],
                        foreground='#212529', background='#e9ecef')
        style.configure('TEntry', padding=(6, 5), font=('', 11))
        style.configure('TCombobox', padding=(5, 4), font=('', 11))
        # hover effects for buttons
        style.map('TButton',
                  background=[('active', '#dfe3e7'), ('!disabled', '#e9ecef')],
                  relief=[('pressed', 'sunken'), ('!pressed', 'raised')])
    except Exception:
        pass

    # Primary button style (for main actions)
    try:
        # Explicit colors so text doesn't disappear on light/dark variants
        style.configure('Primary.TButton', 
                        padding=(12, 10),
                        font=FONTS['button'],
                        foreground='#ffffff',
                        background=colors['primary'])
        style.map('Primary.TButton',
                  background=[('!disabled', colors['primary']),
                              ('active', colors['primary_dark']),
                              ('pressed', colors['primary_dark'])],
                  foreground=[('disabled', '#aaaaaa'), ('!disabled', '#ffffff')])
    except Exception:
        pass

    _THEME_APPLIED = True

    # Secondary button style (Cancel/Close): light background with dark text for high contrast
    try:
        style.configure('Secondary.TButton',
                        padding=(10, 8),
                        font=('', 11),
                        background='#e9ecef',
                        foreground='#212529')
        style.map('Secondary.TButton',
                  background=[('active', '#dfe3e7'), ('!disabled', '#e9ecef')],
                  foreground=[('disabled', '#999999'), ('!disabled', '#212529')])
    except Exception:
        pass

    # Danger button style (for delete actions)
    try:
        style.configure('Danger.TButton',
                        padding=(10, 8),
                        font=FONTS['button'],
                        background=colors['danger'],
                        foreground='#ffffff')
        style.map('Danger.TButton',
                  background=[('active', '#b52a3a'), ('pressed', '#b52a3a')],
                  foreground=[('disabled', '#dddddd'), ('!disabled', '#ffffff')])
    except Exception:
        pass

    # Success button style (for save actions)
    try:
        style.configure('Success.TButton',
                        padding=(10, 8),
                        font=FONTS['button'],
                        background=colors['success'],
                        foreground='#ffffff')
        style.map('Success.TButton',
                  background=[('active', '#1d8f3b'), ('pressed', '#1d8f3b')],
                  foreground=[('disabled', '#dddddd'), ('!disabled', '#ffffff')])
    except Exception:
        pass

    # Section headers
    try:
        style.configure('Section.TLabel',
                        font=('', 12, 'bold'),
                        padding=(2, 6),
                        foreground=colors['fg'])
    except Exception:
        pass

    # Treeview appearance
    try:
        style.configure('Treeview', 
                       rowheight=30, 
                       borderwidth=0,
                       font=('', 11))
        style.configure('Treeview.Heading', 
                       padding=(10, 10), 
                       font=('', 11, 'bold'),
                       relief='flat')
        style.map('Treeview.Heading',
                 background=[('active', colors['light'])])
    except Exception:
        pass

    # LabelFrame styling
    try:
        style.configure('TLabelframe', 
                       borderwidth=1,
                       relief='solid')
        style.configure('TLabelframe.Label',
                       font=('', 12, 'bold'),
                       padding=(6, 3),
                       foreground=colors['fg'])
    except Exception:
        pass

    # Validation entry styles
    try:
        style.configure('Valid.TEntry',
                       fieldbackground='#d4edda',
                       bordercolor='#28a745')
        style.configure('Invalid.TEntry',
                       fieldbackground='#f8d7da',
                       bordercolor='#dc3545')
    except Exception:
        pass


def load_icon(name: str) -> Optional[tk.PhotoImage]:
    """Try to load an icon from assets; return None on failure.
    Accepts PNG files in assets/icons/<name>.png.
    """
    try:
        assets_dir = Path(__file__).resolve().parents[2] / 'assets' / 'icons'
        png_path = assets_dir / f'{name}.png'
        if png_path.exists():
            return tk.PhotoImage(file=str(png_path))
    except Exception:
        return None
    return None

def stripe_treeview(tree: ttk.Treeview, *args):
    """Utility to stripe rows OR tag a specific row.

    Usage:
      - stripe_treeview(tree): zebra stripe all rows
      - stripe_treeview(tree, iid, state): tag a specific row with a state in {'success','warning','danger','info'}
    """
    # Adaptive backgrounds for zebra striping based on theme
    odd_bg = '#2b2f3a' if _BOOTSTRAP_AVAILABLE else '#f7f7fb'
    even_bg = '#242836' if _BOOTSTRAP_AVAILABLE else '#ffffff'
    try:
        # Prepare common tags
        tree.tag_configure('oddrow', background=odd_bg)
        tree.tag_configure('evenrow', background=even_bg)
        tree.tag_configure('success', background='#d4edda', foreground='#155724')
        tree.tag_configure('warning', background='#fff3cd', foreground='#856404')
        tree.tag_configure('danger', background='#f8d7da', foreground='#721c24')
        tree.tag_configure('info', background='#d1ecf1', foreground='#0c5460')
        tree.tag_configure('returned', background='#fff3cd', foreground='#856404')
        tree.tag_configure('low_stock', background='#f8d7da', foreground='#721c24')
        tree.tag_configure('has_document', background='#d1ecf1', foreground='#0c5460')
    except Exception:
        pass

    # If called with (iid, state), tag that specific row
    if len(args) == 2:
        iid, state = args
        try:
            tree.item(iid, tags=(state,))
        except Exception:
            pass
        return

    # Default behavior: zebra stripe
    try:
        for i, iid in enumerate(tree.get_children()):
            tag = 'oddrow' if i % 2 else 'evenrow'
            tree.item(iid, tags=(tag,))
    except Exception:
        pass


def add_document_indicator(tree: ttk.Treeview, iid: str, has_document: bool):
    """Add visual indicator for rows with documents"""
    try:
        if has_document:
            values = list(tree.item(iid, 'values'))
            # Add paperclip emoji to indicate document
            if values and not str(values[0]).endswith(' 📎'):
                values[0] = str(values[0]) + ' 📎'
                tree.item(iid, values=values)
    except Exception:
        pass


def maximize_window(win: Union[tk.Tk, tk.Toplevel]):
    """Maximize a Tk window to fill the screen without forcing OS fullscreen.

    Cross-platform approach:
    - On Windows/Linux: try state('zoomed') first, fallback to geometry.
    - On macOS: use geometry to screen size (state('zoomed') is not supported).
    """
    try:
        win.update_idletasks()
    except Exception:
        pass


def themed_button(parent, text: str, variant: str = 'primary', outline: bool = False, command=None, **kwargs):
    """Create a button with consistent look across the app.

    If ttkbootstrap is available, returns a tb.Button with bootstyle like
    'primary', 'secondary', 'success', 'danger' and optional 'outline'.
    This produces slightly rounded corners consistent with the theme.

    Otherwise falls back to ttk.Button with mapped styles
    (Primary.TButton, Secondary.TButton, Success.TButton, Danger.TButton).
    """
    try:
        if _BOOTSTRAP_AVAILABLE:
            boot = variant.lower()
            if outline:
                boot = f"{boot} outline"
            return tb.Button(parent, text=text, command=command, bootstyle=boot, **kwargs)
    except Exception:
        pass
    # Fallback to ttk
    style_map = {
        'primary': 'Primary.TButton',
        'secondary': 'Secondary.TButton',
        'success': 'Success.TButton',
        'danger': 'Danger.TButton',
    }
    style = style_map.get(variant.lower(), 'TButton')
    return ttk.Button(parent, text=text, command=command, style=style, **kwargs)


def make_treeview_sortable(tree: ttk.Treeview, cols: list):
    """Attach clickable heading sort to a Treeview. Stable client-side sort, no data changes.
    Call as: make_treeview_sortable(tree, cols)
    """
    sort_state = {}

    def _coerce(v):
        if v is None:
            return ''
        s = str(v)
        # try datetime
        try:
            from datetime import datetime as _dt
            return _dt.strptime(s, '%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
        try:
            # also allow date-only
            from datetime import datetime as _dt
            return _dt.strptime(s, '%Y-%m-%d')
        except Exception:
            pass
        try:
            return float(s)
        except Exception:
            return s.lower()

    def sort_by(col):
        reverse = sort_state.get(col, False)
        items = [(iid, tree.item(iid)['values']) for iid in tree.get_children('')]
        try:
            idx = cols.index(col)
        except ValueError:
            idx = 0
        items.sort(key=lambda t: _coerce(t[1][idx] if idx < len(t[1]) else ''), reverse=reverse)
        for pos, (iid, _) in enumerate(items):
            tree.move(iid, '', pos)
        sort_state[col] = not reverse

    for c in cols:
        tree.heading(c, text=c, command=lambda cc=c: sort_by(cc))


def export_treeview_csv(parent: tk.Tk, tree: ttk.Treeview, cols: list, title: str = 'Export CSV'):
    """Export all visible rows from a Treeview to a CSV file selected by the user."""
    if not tree.get_children():
        try:
            messagebox = __import__('tkinter').messagebox
            messagebox.showinfo('Export', 'No rows to export', parent=parent)
        except Exception:
            pass
        return
    path = filedialog.asksaveasfilename(title=title, defaultextension='.csv',
                                        filetypes=[('CSV files', '*.csv')], parent=parent)
    if not path:
        return
    import csv
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for iid in tree.get_children(''):
            w.writerow(tree.item(iid)['values'])
    try:
        messagebox = __import__('tkinter').messagebox
        messagebox.showinfo('Export', 'Export complete', parent=parent)
    except Exception:
        pass


def add_buttons(parent, spec: list):
    """Create a vertical list of themed buttons.
    spec: list of tuples (label, variant, command, pack_kwargs optional dict)
    """
    for item in spec:
        if len(item) == 4 and isinstance(item[3], dict):
            label, variant, command, extra = item
            themed_button(parent, text=label, variant=variant, command=command).pack(**extra)
        else:
            label, variant, command = item
            themed_button(parent, text=label, variant=variant, command=command).pack(fill='x', pady=4)


# ---------- TTK dialog helpers (replace tk.simpledialog for better styling) ----------
from typing import Tuple


def ask_string(parent: Union[tk.Tk, tk.Toplevel], title: str, prompt: str, initialvalue: str = '') -> Optional[str]:
    """Show a themed text input dialog (OK/Cancel) and return the string or None."""
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.grab_set()
    dlg.resizable(False, False)
    try:
        apply_theme(dlg)
    except Exception:
        pass

    container = ttk.Frame(dlg, padding=12)
    container.pack(fill='both', expand=True)

    ttk.Label(container, text=prompt, wraplength=360).pack(anchor='w', pady=(0, 8))
    var = tk.StringVar(value=initialvalue)
    entry = ttk.Entry(container, textvariable=var, width=36)
    entry.pack(fill='x')
    entry.focus_set()

    result: dict = {'value': None}

    def on_ok():
        result['value'] = var.get()
        dlg.destroy()

    def on_cancel():
        result['value'] = None
        dlg.destroy()

    btns = ttk.Frame(container)
    btns.pack(fill='x', pady=(12, 0))
    ttk.Button(btns, text='Cancel', style='Secondary.TButton', command=on_cancel).pack(side='left')
    ttk.Button(btns, text='OK', style='Primary.TButton', command=on_ok).pack(side='right')

    dlg.bind('<Return>', lambda e: on_ok())
    dlg.bind('<Escape>', lambda e: on_cancel())

    parent_x = parent.winfo_rootx() if parent and parent.winfo_ismapped() else 100
    parent_y = parent.winfo_rooty() if parent and parent.winfo_ismapped() else 100
    try:
        dlg.geometry(f'+{parent_x + 40}+{parent_y + 60}')
    except Exception:
        pass

    dlg.wait_window()
    return result['value']


def ask_integer(parent: Union[tk.Tk, tk.Toplevel], title: str, prompt: str, initialvalue: int = 0, minvalue: Optional[int] = None, maxvalue: Optional[int] = None) -> Optional[int]:
    """Show a themed integer input dialog with optional min/max validation."""
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.grab_set()
    dlg.resizable(False, False)
    try:
        apply_theme(dlg)
    except Exception:
        pass

    container = ttk.Frame(dlg, padding=12)
    container.pack(fill='both', expand=True)

    ttk.Label(container, text=prompt, wraplength=360).pack(anchor='w', pady=(0, 8))
    var = tk.StringVar(value=str(initialvalue or ''))
    entry = ttk.Entry(container, textvariable=var, width=18)
    entry.pack(anchor='w')
    entry.focus_set()

    out: dict = {'value': None}

    def valid_int(s: str) -> Tuple[bool, Optional[int], str]:
        try:
            v = int(s)
        except Exception:
            return False, None, 'Enter a whole number'
        if minvalue is not None and v < minvalue:
            return False, None, f'Minimum is {minvalue}'
        if maxvalue is not None and v > maxvalue:
            return False, None, f'Maximum is {maxvalue}'
        return True, v, ''

    def on_ok():
        ok, v, msg = valid_int(var.get().strip())
        if not ok:
            try:
                messagebox = __import__('tkinter').messagebox
                messagebox.showerror('Invalid', msg, parent=dlg)
            except Exception:
                pass
            return
        out['value'] = v
        dlg.destroy()

    def on_cancel():
        out['value'] = None
        dlg.destroy()

    btns = ttk.Frame(container)
    btns.pack(fill='x', pady=(12, 0))
    ttk.Button(btns, text='Cancel', style='Secondary.TButton', command=on_cancel).pack(side='left')
    ttk.Button(btns, text='OK', style='Primary.TButton', command=on_ok).pack(side='right')

    dlg.bind('<Return>', lambda e: on_ok())
    dlg.bind('<Escape>', lambda e: on_cancel())
    try:
        dlg.geometry(f'+{parent.winfo_rootx() + 40}+{parent.winfo_rooty() + 60}')
    except Exception:
        pass
    dlg.wait_window()
    return out['value']
    try:
        if sys.platform.startswith('win') or sys.platform.startswith('linux'):
            try:
                win.state('zoomed')
                return
            except Exception:
                pass
        # Fallback / macOS path: set geometry to screen size
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        try:
            win.geometry(f"{sw}x{sh}+0+0")
        except Exception:
            pass
    except Exception:
        pass
