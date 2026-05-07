import tkinter as tk
from tkinter import ttk
import re
import sys


_GEOMETRY_RE = re.compile(r"^\s*(\d+)x(\d+)([+-]\d+)?([+-]\d+)?\s*$")


def _parse_geometry_size(geometry: str) -> tuple[int, int] | None:
    match = _GEOMETRY_RE.match(geometry or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _primary_bounds(window) -> tuple[int, int, int, int]:
    return 0, 0, window.winfo_screenwidth(), window.winfo_screenheight()


def _virtual_bounds(window) -> tuple[int, int, int, int]:
    if sys.platform.startswith("win"):
        try:
            import ctypes

            user32 = ctypes.windll.user32
            x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            y = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
            width = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            height = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            if width > 1 and height > 1:
                return x, y, width, height
        except Exception:
            pass

    try:
        x = window.winfo_vrootx()
        y = window.winfo_vrooty()
        width = window.winfo_vrootwidth()
        height = window.winfo_vrootheight()
        if width > 1 and height > 1:
            return x, y, width, height
    except tk.TclError:
        pass
    return _primary_bounds(window)


def _monitor_bounds_for_point(window, x: int, y: int) -> tuple[int, int, int, int]:
    """Return the monitor work area for a point, falling back to virtual desktop."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes

            class POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            user32 = ctypes.windll.user32
            monitor = user32.MonitorFromPoint(POINT(x, y), 2)  # MONITOR_DEFAULTTONEAREST
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                rect = info.rcWork
                return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        except Exception:
            pass
    return _virtual_bounds(window)


def _target_bounds(window, parent=None) -> tuple[int, int, int, int]:
    if parent is None:
        return _primary_bounds(window)

    try:
        parent.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        if parent_w > 1 and parent_h > 1:
            return _monitor_bounds_for_point(
                window,
                parent_x + parent_w // 2,
                parent_y + parent_h // 2,
            )
    except tk.TclError:
        pass
    return _primary_bounds(window)


def _safe_size(width: int, height: int, margin: int, bounds: tuple[int, int, int, int]) -> tuple[int, int]:
    _, _, display_w, display_h = bounds
    max_w = max(100, display_w - margin * 2)
    max_h = max(100, display_h - margin * 2)
    return min(width, max_w), min(height, max_h)


def _clamp_position(x: int, y: int, width: int, height: int, margin: int, bounds: tuple[int, int, int, int]) -> tuple[int, int]:
    display_x, display_y, display_w, display_h = bounds
    min_x = display_x + margin
    min_y = display_y + margin
    max_x = display_x + display_w - width - margin
    max_y = display_y + display_h - height - margin
    if max_x < min_x:
        x = display_x + max(0, (display_w - width) // 2)
    else:
        x = max(min_x, min(x, max_x))
    if max_y < min_y:
        y = display_y + max(0, (display_h - height) // 2)
    else:
        y = max(min_y, min(y, max_y))
    return x, y


def center_window(window, parent=None, margin: int = 40):
    """Place a Tk/Toplevel window at the center of its parent or screen."""
    window.update_idletasks()

    width = window.winfo_width()
    height = window.winfo_height()
    if width <= 1:
        width = window.winfo_reqwidth()
    if height <= 1:
        height = window.winfo_reqheight()
    bounds = _target_bounds(window, parent)
    width, height = _safe_size(width, height, margin, bounds)

    if parent is not None:
        parent.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        if parent_w <= 1 or parent_h <= 1:
            parent_x, parent_y, parent_w, parent_h = bounds
    else:
        parent_x, parent_y, parent_w, parent_h = bounds

    x = parent_x + max((parent_w - width) // 2, 0)
    y = parent_y + max((parent_h - height) // 2, 0)
    x, y = _clamp_position(x, y, width, height, margin, bounds)
    window.geometry(f"{width}x{height}+{x}+{y}")


def apply_safe_geometry(window, geometry: str, parent=None, margin: int = 40):
    """Apply a requested geometry without enlarging it, shrinking only if needed."""
    parsed = _parse_geometry_size(geometry)
    if parsed is None:
        window.geometry(geometry)
        center_window(window, parent, margin=margin)
        return

    bounds = _target_bounds(window, parent)
    width, height = _safe_size(parsed[0], parsed[1], margin, bounds)

    if parent is not None:
        parent.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        if parent_w <= 1 or parent_h <= 1:
            parent_x, parent_y, parent_w, parent_h = bounds
    else:
        parent_x, parent_y, parent_w, parent_h = bounds

    x = parent_x + max((parent_w - width) // 2, 0)
    y = parent_y + max((parent_h - height) // 2, 0)
    x, y = _clamp_position(x, y, width, height, margin, bounds)
    window.geometry(f"{width}x{height}+{x}+{y}")


def show_centered_window(window, parent=None, margin: int = 40):
    """Center a withdrawn Toplevel and show it after the position is fixed."""
    center_window(window, parent, margin=margin)
    try:
        window.deiconify()
        window.lift()
    except tk.TclError:
        pass


def enable_enter_key_navigation(root_or_frame):
    """Enable Enter-to-next-field and Enter-to-invoke-button under a widget tree."""

    entry_classes = [tk.Entry, tk.Spinbox, ttk.Entry]
    if hasattr(ttk, "Spinbox"):
        entry_classes.append(ttk.Spinbox)
    entry_classes = tuple(entry_classes)
    button_classes = (tk.Button, ttk.Button)

    def has_own_return_binding(widget) -> bool:
        try:
            return bool(widget.bind("<Return>"))
        except tk.TclError:
            return True

    def focus_next(widget):
        next_widget = widget.tk_focusNext()
        if next_widget:
            next_widget.focus_set()

    def bind_widget(widget):
        if isinstance(widget, tk.Text):
            return

        if isinstance(widget, ttk.Combobox):
            try:
                widget.configure(takefocus=True)
            except tk.TclError:
                pass
            if not has_own_return_binding(widget):
                widget.bind("<Return>", lambda event: event.widget.after_idle(lambda w=event.widget: focus_next(w)))
            return

        if isinstance(widget, entry_classes):
            try:
                widget.configure(takefocus=True)
            except tk.TclError:
                pass
            if not has_own_return_binding(widget):
                widget.bind("<Return>", lambda event: (focus_next(event.widget), "break")[1])
            return

        if isinstance(widget, button_classes):
            try:
                widget.configure(takefocus=True)
            except tk.TclError:
                pass
            if not has_own_return_binding(widget):
                widget.bind("<Return>", lambda event: (event.widget.invoke(), "break")[1])

    def walk(widget):
        bind_widget(widget)
        for child in widget.winfo_children():
            walk(child)

    walk(root_or_frame)
