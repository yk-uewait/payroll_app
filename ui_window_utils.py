import tkinter as tk
from tkinter import ttk


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


def show_centered_window(window, parent=None):
    """Center a withdrawn Toplevel and show it after the position is fixed."""
    center_window(window, parent)
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
