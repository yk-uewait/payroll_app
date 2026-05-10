import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from ui_window_utils import show_centered_window, enable_enter_key_navigation


class CreateMethodDialog(tk.Toplevel):
    def __init__(self, parent, item_label: str):
        super().__init__(parent)
        self.withdraw()
        self.result = None
        self.title(f"{item_label}データ作成")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text=f"{item_label}データの作成方法を選択してください").pack(anchor="w", pady=(0, 10))
        ttk.Button(frm, text="新規作成", command=lambda: self._choose("new")).pack(fill="x", pady=3)
        ttk.Button(frm, text="既存明細から複写", command=lambda: self._choose("copy")).pack(fill="x", pady=3)

        footer = ttk.Frame(frm)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Button(footer, text="閉じる", command=self._close).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._close)
        enable_enter_key_navigation(self)
        show_centered_window(self, parent)

    def _choose(self, value: str):
        self.result = value
        self._release_and_destroy()

    def _close(self):
        self.result = None
        self._release_and_destroy()

    def _release_and_destroy(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class YearMonthDialog(tk.Toplevel):
    def __init__(self, parent, title: str, source_options=None, initial_year: int | None = None, initial_month: int | None = None):
        super().__init__(parent)
        self.withdraw()
        self.result = None
        self.source_options = source_options or []
        self.source_map = {label: value for label, value in self.source_options}

        today = date.today()
        self.var_year = tk.StringVar(value=str(initial_year or today.year))
        self.var_month = tk.StringVar(value=str(initial_month or today.month))
        self.var_source = tk.StringVar(value=self.source_options[0][0] if self.source_options else "")

        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="作成する対象年月").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))
        ttk.Entry(frm, textvariable=self.var_year, width=8).grid(row=1, column=0, padx=(0, 4), sticky="w")
        ttk.Label(frm, text="年").grid(row=1, column=1, padx=(0, 12), sticky="w")
        ttk.Spinbox(frm, from_=1, to=12, textvariable=self.var_month, width=5).grid(row=1, column=2, padx=(0, 4), sticky="w")
        ttk.Label(frm, text="月").grid(row=1, column=3, sticky="w")

        row = 2
        if self.source_options:
            ttk.Label(frm, text="複写元").grid(row=row, column=0, columnspan=4, sticky="w", pady=(12, 4))
            self.cmb_source = ttk.Combobox(
                frm,
                textvariable=self.var_source,
                values=[label for label, _ in self.source_options],
                state="readonly",
                width=28,
            )
            self.cmb_source.grid(row=row + 1, column=0, columnspan=4, sticky="ew")
            row += 2

        footer = ttk.Frame(frm)
        footer.grid(row=row, column=0, columnspan=4, sticky="e", pady=(14, 0))
        ttk.Button(footer, text="閉じる", command=self._close).pack(side="right")
        ttk.Button(footer, text="作成", command=self._apply).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self._close)
        enable_enter_key_navigation(self)
        show_centered_window(self, parent)

    def _apply(self):
        year_text = (self.var_year.get() or "").strip()
        month_text = (self.var_month.get() or "").strip()
        if not year_text.isdigit() or len(year_text) != 4:
            messagebox.showerror("入力エラー", "年は4桁の西暦で入力してください。", parent=self)
            return
        if not month_text.isdigit():
            messagebox.showerror("入力エラー", "月は1から12の数字で入力してください。", parent=self)
            return

        month = int(month_text)
        if not (1 <= month <= 12):
            messagebox.showerror("入力エラー", "月は1から12の範囲で入力してください。", parent=self)
            return

        source_value = None
        if self.source_options:
            source_label = (self.var_source.get() or "").strip()
            source_value = self.source_map.get(source_label)
            if not source_value:
                messagebox.showerror("入力エラー", "複写元を選択してください。", parent=self)
                return

        self.result = (f"{int(year_text):04d}-{month:02d}", source_value)
        self._release_and_destroy()

    def _close(self):
        self.result = None
        self._release_and_destroy()

    def _release_and_destroy(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
