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


def _top_offset_position(width: int, height: int, margin: int, bounds: tuple[int, int, int, int], top_ratio: float) -> tuple[int, int]:
    display_x, display_y, display_w, display_h = bounds
    x = display_x + max((display_w - width) // 2, 0)
    y = display_y + int(display_h * top_ratio)
    return _clamp_position(x, y, width, height, margin, bounds)


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


def apply_safe_geometry(window, geometry: str, parent=None, margin: int = 40, top_ratio: float | None = None):
    """Apply a requested geometry without enlarging it, shrinking only if needed."""
    parsed = _parse_geometry_size(geometry)
    if parsed is None:
        window.geometry(geometry)
        center_window(window, parent, margin=margin)
        return

    bounds = _target_bounds(window, parent)
    width, height = _safe_size(parsed[0], parsed[1], margin, bounds)

    if parent is None and top_ratio is not None:
        x, y = _top_offset_position(width, height, margin, bounds, top_ratio)
        window.geometry(f"{width}x{height}+{x}+{y}")
        return

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


def setup_grid_treeview_style(widget):
    style = ttk.Style(widget)
    style.configure(
        "ListGrid.Treeview",
        rowheight=26,
        borderwidth=1,
        relief="solid",
        background="#ffffff",
        fieldbackground="#ffffff",
        bordercolor="#d8dee6",
        lightcolor="#edf1f5",
        darkcolor="#d8dee6",
    )
    style.configure(
        "ListGrid.Treeview.Heading",
        padding=(6, 5),
        relief="solid",
        borderwidth=1,
        background="#f3f5f7",
        bordercolor="#d8dee6",
        lightcolor="#edf1f5",
        darkcolor="#d8dee6",
    )
    style.map(
        "ListGrid.Treeview",
        background=[("selected", "#dbeafe")],
        foreground=[("selected", "#111827")],
    )


def _treeview_display_columns(tree):
    display_columns = tree["displaycolumns"]
    if display_columns in ("#all", "", None):
        return list(tree["columns"])
    display_columns = list(display_columns)
    if display_columns == ["#all"]:
        return list(tree["columns"])
    return display_columns


def _first_visible_treeview_item_bbox(tree, col):
    for item_id in tree.get_children(""):
        bbox = tree.bbox(item_id, col)
        if bbox:
            return bbox
    return None


def _update_treeview_grid_lines(tree):
    if not tree.winfo_exists():
        return
    display_columns = _treeview_display_columns(tree)
    lines = getattr(tree, "_grid_column_lines", [])
    needed = max(0, len(display_columns) - 1)
    while len(lines) < needed:
        line = tk.Frame(tree, bg="#e5e7eb", width=1)

        def select_row(event, t=tree):
            y = event.widget.winfo_y() + event.y
            row_id = t.identify_row(y)
            if row_id:
                t.selection_set(row_id)
                t.focus(row_id)
            return "break"

        def double_click(event, t=tree):
            y = event.widget.winfo_y() + event.y
            row_id = t.identify_row(y)
            if row_id:
                t.selection_set(row_id)
                t.focus(row_id)
                t.event_generate("<Double-1>", x=1, y=y)
            return "break"

        def mousewheel(event, t=tree):
            try:
                t.event_generate("<MouseWheel>", delta=event.delta)
            except tk.TclError:
                pass
            return "break"

        line.bind("<Button-1>", select_row)
        line.bind("<Double-1>", double_click)
        line.bind("<MouseWheel>", mousewheel)
        lines.append(line)
    tree._grid_column_lines = lines
    for line in lines[needed:]:
        line.place_forget()

    if not tree.get_children(""):
        for line in lines:
            line.place_forget()
        return

    first_bbox = _first_visible_treeview_item_bbox(tree, display_columns[0]) if display_columns else None
    y_start = first_bbox[1] if first_bbox else 24
    line_height = max(0, tree.winfo_height() - y_start)
    if line_height <= 0:
        return

    total_width = sum(int(tree.column(col, "width")) for col in display_columns)
    x_offset = int(total_width * tree.xview()[0]) if total_width > 0 else 0
    x_pos = 0
    for idx, col in enumerate(display_columns[:-1]):
        bbox = _first_visible_treeview_item_bbox(tree, col)
        if bbox:
            x = bbox[0] + bbox[2] - 1
        else:
            x_pos += int(tree.column(col, "width"))
            x = x_pos - x_offset - 1
        line = lines[idx]
        if 0 <= x <= tree.winfo_width():
            line.place(x=x, y=y_start, width=1, height=line_height)
            line.lift()
        else:
            line.place_forget()


def refresh_grid_treeview(tree):
    for index, item_id in enumerate(tree.get_children("")):
        tree.item(item_id, tags=("row_even" if index % 2 else "row_odd",))
    tree.after_idle(lambda: _update_treeview_grid_lines(tree))


def apply_grid_treeview_style(tree, xscroll=None):
    setup_grid_treeview_style(tree)
    tree.configure(style="ListGrid.Treeview")
    tree.tag_configure("row_odd", background="#ffffff")
    tree.tag_configure("row_even", background="#f8fafc")
    if not hasattr(tree, "_grid_column_lines"):
        tree._grid_column_lines = []
    if xscroll is not None:
        def on_xscroll(*args):
            tree.xview(*args)
            tree.after_idle(lambda: _update_treeview_grid_lines(tree))

        def set_xscroll(first, last):
            xscroll.set(first, last)
            tree.after_idle(lambda: _update_treeview_grid_lines(tree))

        xscroll.configure(command=on_xscroll)
        tree.configure(xscrollcommand=set_xscroll)

    tree.bind("<Configure>", lambda _e: tree.after_idle(lambda: _update_treeview_grid_lines(tree)), add="+")
    tree.bind("<ButtonPress-1>", lambda _e: tree.after_idle(lambda: _update_treeview_grid_lines(tree)), add="+")
    tree.bind("<B1-Motion>", lambda _e: tree.after_idle(lambda: _update_treeview_grid_lines(tree)), add="+")
    tree.bind("<ButtonRelease-1>", lambda _e: tree.after_idle(lambda: _update_treeview_grid_lines(tree)), add="+")
    tree.after_idle(lambda: _update_treeview_grid_lines(tree))
