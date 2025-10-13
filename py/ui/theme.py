import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from typing import Union

# Try to use ttkbootstrap's "superhero" theme when available
_BOOTSTRAP_AVAILABLE = False
try:
    import ttkbootstrap as tb  # type: ignore
    _BOOTSTRAP_AVAILABLE = True
except Exception:
    _BOOTSTRAP_AVAILABLE = False


def apply_theme(root: Union[tk.Tk, tk.Toplevel]):
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
    colors = {
        'primary': '#007acc',
        'primary_dark': '#005a9e',
        'secondary': '#6c757d',
        'success': '#28a745',
        'warning': '#ffc107',
        'danger': '#dc3545',
        'light': '#f8f9fa',
        'dark': '#343a40',
        'accent': '#17a2b8',
        'fg': ('#e9ecef' if is_dark else '#212529'),
        'muted': ('#cfd8dc' if is_dark else '#495057'),
    }

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
        style.configure('TButton', padding=(12, 10), font=('', 11, 'bold'))
        style.configure('TEntry', padding=(6, 5), font=('', 11))
        style.configure('TCombobox', padding=(5, 4), font=('', 11))
    except Exception:
        pass

    # Primary button style (for main actions)
    try:
        style.configure('Primary.TButton', 
                       padding=(12, 10),
                       font=('', 11, 'bold'),
                       foreground='#ffffff')
        style.map('Primary.TButton',
                 background=[('active', colors['primary_dark']),
                            ('pressed', colors['primary_dark'])])
    except Exception:
        pass

    # Secondary button style
    try:
        style.configure('Secondary.TButton',
                       padding=(10, 8),
                       font=('', 11))
    except Exception:
        pass

    # Danger button style (for delete actions)
    try:
        style.configure('Danger.TButton',
                       padding=(10, 8),
                       font=('', 11, 'bold'))
    except Exception:
        pass

    # Success button style (for save actions)
    try:
        style.configure('Success.TButton',
                       padding=(10, 8),
                       font=('', 11, 'bold'))
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
