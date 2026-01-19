import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional
from .theme import themed_button

class DashboardWidget(ttk.Frame):
    """Base class for dashboard widgets."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

class MetricCard(DashboardWidget):
    """A card displaying a key metric (e.g., Total Sales)."""
    def __init__(self, parent, title: str, value: str, icon: str = "📊", trend: str = "", variant: str = "primary", **kwargs):
        super().__init__(parent, style='Card.TFrame', padding=20, **kwargs)
        
        # Header (Icon + Title)
        header = ttk.Frame(self, style='Card.TFrame')
        header.pack(fill='x', pady=(0, 10))
        
        # Icon bubble (simulated with label bg)
        # Using a unicode char for now, but in a real SaaS app we'd use an image/SVG
        ttk.Label(header, text=icon, font=("", 16), width=2, anchor='center').pack(side='left', padx=(0, 10))
        
        ttk.Label(header, text=title.upper(), font=("", 9, 'bold'), foreground='#64748b', style='Card.TLabel').pack(side='left', pady=(2,0))
        
        # Value
        val_lbl = ttk.Label(self, text=value, font=("", 26, 'bold'), style='Card.TLabel')
        val_lbl.pack(anchor='w')
        
        # Trend / subtext
        if trend:
            # Color based on trend direction
            fg = '#10b981' if '+' in trend or 'On' in trend else '#64748b'
            if '-' in trend: fg = '#ef4444'
            
            ttk.Label(self, text=trend, font=("", 9), foreground=fg, style='Card.TLabel').pack(anchor='w', pady=(4, 0))

class QuickActionCard(DashboardWidget):
    """A card containing a set of related action buttons."""
    def __init__(self, parent, title: str, icon: str, actions: list[tuple[str, Callable, str]], **kwargs):
        super().__init__(parent, style='Card.TFrame', padding=20, **kwargs)
        
        # Title
        hdr = ttk.Frame(self, style='Card.TFrame')
        hdr.pack(fill='x', pady=(0, 14))
        ttk.Label(hdr, text=f"{icon}  {title}", font=("", 11, 'bold'), style='Card.TLabel').pack(anchor='w')
        
        # Buttons
        for label, cmd, variant in actions:
            # Map old variants to new theme variants if needed, or rely on consistency
            v = 'secondary' if variant in ('secondary', 'info') else 'primary' 
            if 'Record' in label: v = 'primary'
            if 'View' in label: v = 'secondary'
            
            themed_button(self, text=label, command=cmd, variant=v).pack(fill='x', pady=3)

class RecentActivityList(DashboardWidget):
    """A list showing recent items."""
    def __init__(self, parent, title: str, items: list[str], view_all_cmd: Optional[Callable] = None, **kwargs):
        super().__init__(parent, style='Card.TFrame', padding=20, **kwargs)
        
        hdr = ttk.Frame(self, style='Card.TFrame')
        hdr.pack(fill='x', pady=(0, 14))
        ttk.Label(hdr, text=title, font=("", 11, 'bold'), style='Card.TLabel').pack(side='left')
        
        if view_all_cmd:
            btn = themed_button(hdr, text="View All", command=view_all_cmd, variant='link') 
            # Note: variant='link' currently falls back to Button, we handled that in theme.py as basic
            # Let's use a small primary outline notion or just text if possible?
            # For now standard button is safer.
            # actually let's implement a clickable label logic for "View All" to look cleaner
            lbl = ttk.Label(hdr, text="View All ›", font=("", 9, 'bold'), foreground='#4f46e5', cursor="hand2", style='Card.TLabel')
            lbl.pack(side='right')
            lbl.bind("<Button-1>", lambda e: view_all_cmd())
            
        if not items:
            ttk.Label(self, text="No recent activity", font=("", 9, 'italic'), foreground='#6c757d').pack(anchor='w')
        else:
            for item in items[:5]:
                # Simple row
                row = ttk.Frame(self)
                row.pack(fill='x', pady=2)
                ttk.Label(row, text="• " + item, font=("", 10)).pack(anchor='w')

