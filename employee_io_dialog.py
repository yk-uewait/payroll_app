import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import db
from ui_window_utils import show_centered_window, enable_enter_key_navigation


class EmployeeIODialog(tk.Toplevel):
    def __init__(self, parent, conn, on_completed=None):
        super().__init__(parent)
        self.withdraw()
        self.conn = conn
        self.on_completed = on_completed

        self.title("インポート/エクスポート")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        rows = [
            ("インポート", self.import_csv, "CSVファイルから社員情報を取り込みます"),
            ("エクスポート", self.export_csv, "現在の社員情報をCSVファイルに出力します"),
            ("テンプレート出力", self.export_template, "CSV作成用の見本ヘッダーを出力します"),
            ("閉じる", self.close, ""),
        ]

        for row_idx, (label, command, description) in enumerate(rows):
            ttk.Button(frm, text=label, command=command, width=18).grid(
                row=row_idx, column=0, sticky="w", padx=(0, 12), pady=6
            )
            if description:
                ttk.Label(frm, text=description).grid(row=row_idx, column=1, sticky="w", pady=6)

        self.bind("<Escape>", lambda e: self.close())
        enable_enter_key_navigation(self)
        show_centered_window(self, parent)
        self.after(10, self.focus_force)

    def _notify_completed(self):
        if callable(self.on_completed):
            self.on_completed()

    def _load_csv_rows(self, path: str) -> list[dict]:
        last_error = None
        for encoding in ("utf-8-sig", "cp932", "utf-8"):
            try:
                with open(path, "r", encoding=encoding, newline="") as f:
                    return list(csv.DictReader(f))
            except Exception as e:
                last_error = e
        raise ValueError(f"CSVを読み込めませんでした。\n{last_error}")

    def _save_rows(self, path: str, rows: list[dict]):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=db.EMPLOYEE_CSV_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in db.EMPLOYEE_CSV_COLUMNS})

    def import_csv(self):
        path = filedialog.askopenfilename(
            title="社員情報CSVのインポート",
            filetypes=[("CSV", "*.csv"), ("All Files", "*.*")],
            parent=self,
        )
        if not path:
            return

        try:
            rows = self._load_csv_rows(path)
            if not rows:
                messagebox.showwarning("インポート", "CSVに取込対象のデータがありません。", parent=self)
                return
            imported = db.import_employees_from_csv_rows(self.conn, rows)
        except Exception as e:
            messagebox.showerror("インポートエラー", str(e), parent=self)
            return

        self._notify_completed()
        messagebox.showinfo("インポート完了", f"{imported}件の社員情報を取り込みました。", parent=self)

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            title="社員情報CSVのエクスポート",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="社員情報.csv",
            parent=self,
        )
        if not path:
            return

        try:
            rows = db.list_employee_export_rows(self.conn)
            self._save_rows(path, rows)
        except Exception as e:
            messagebox.showerror("エクスポートエラー", str(e), parent=self)
            return

        messagebox.showinfo("エクスポート完了", "社員情報をCSVファイルに出力しました。", parent=self)

    def export_template(self):
        path = filedialog.asksaveasfilename(
            title="社員情報CSVテンプレートの出力",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="社員情報テンプレート.csv",
            parent=self,
        )
        if not path:
            return

        try:
            self._save_rows(path, [])
        except Exception as e:
            messagebox.showerror("テンプレート出力エラー", str(e), parent=self)
            return

        messagebox.showinfo("テンプレート出力完了", "CSVテンプレートを出力しました。", parent=self)

    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
