def center_window(window, parent=None):
    """Place a Tk/Toplevel window at the center of its parent or screen."""
    window.update_idletasks()

    width = window.winfo_width()
    height = window.winfo_height()
    if width <= 1:
        width = window.winfo_reqwidth()
    if height <= 1:
        height = window.winfo_reqheight()

    if parent is not None:
        parent.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        if parent_w <= 1 or parent_h <= 1:
            parent_w = parent.winfo_screenwidth()
            parent_h = parent.winfo_screenheight()
            parent_x = 0
            parent_y = 0
    else:
        parent_x = 0
        parent_y = 0
        parent_w = window.winfo_screenwidth()
        parent_h = window.winfo_screenheight()

    x = parent_x + max((parent_w - width) // 2, 0)
    y = parent_y + max((parent_h - height) // 2, 0)
    window.geometry(f"{width}x{height}+{x}+{y}")
