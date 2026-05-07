import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sys

import app_settings
import db
from employee_io_dialog import EmployeeIODialog
from ui_payroll import PayrollFrame
from ui_bonus import BonusFrame
from ui_settings import SettingsFrame
from ui_window_utils import show_centered_window, enable_enter_key_navigation

def resource_path(relative_name: str) -> Path:
    """
    PyInstaller(onefile) で同梱したファイルの実パスを返す。
    通常実行時：この app.py と同じフォルダを参照
    exe実行時：PyInstaller の展開先（_MEIPASS）を参照
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_name
    return Path(__file__).parent / relative_name

APP_TITLE = "給与計算アプリ（プロトタイプ）"


def create_main_menubar(root):
    menubar = tk.Menu(root)

    file_menu = tk.Menu(menubar, tearoff=False)
    import_menu = tk.Menu(file_menu, tearoff=False)
    import_menu.add_command(label="社員データをインポート", command=root.open_employee_import)
    import_menu.add_command(label="給与データをインポート(未実装)", state="disabled")
    import_menu.add_command(label="住民税データをインポート(未実装)", state="disabled")
    file_menu.add_cascade(label="インポート", menu=import_menu)

    export_menu = tk.Menu(file_menu, tearoff=False)
    export_menu.add_command(label="給与明細(.xlsx)", command=root.export_payroll_detail_excel)
    export_menu.add_command(label="支給控除一覧(.xlsx)", command=root.export_pay_deduct_excel)
    export_menu.add_command(label="賃金台帳(.xlsx)", command=root.export_monthly_payroll_excel)
    file_menu.add_cascade(label="エクスポート", menu=export_menu)
    file_menu.add_separator()
    file_menu.add_command(label="終了", command=root.destroy)
    menubar.add_cascade(label="ファイル", menu=file_menu)

    view_menu = tk.Menu(menubar, tearoff=False)
    view_menu.add_command(label="画面サイズ設定", command=root.open_window_size_settings)
    menubar.add_cascade(label="表示", menu=view_menu)

    payroll_menu = tk.Menu(menubar, tearoff=False)
    payroll_menu.add_command(label="給与入力", command=root.open_monthly_input)
    payroll_menu.add_command(label="給与一覧", command=root.open_monthly_payroll_list)
    payroll_menu.add_command(label="住民税年次一括入力", command=root.open_resident_tax_annual)
    menubar.add_cascade(label="給与", menu=payroll_menu)

    bonus_menu = tk.Menu(menubar, tearoff=False)
    bonus_menu.add_command(label="賞与入力", command=root.open_bonus_input)
    bonus_menu.add_command(label="賞与一覧", command=root.open_bonus_list)
    menubar.add_cascade(label="賞与", menu=bonus_menu)

    help_menu = tk.Menu(menubar, tearoff=False)
    help_menu.add_command(label="操作マニュアル(未実装)", state="disabled")
    help_menu.add_command(label="バージョン情報", command=root.show_version_info)
    menubar.add_cascade(label="ヘルプ", menu=help_menu)

    root.config(menu=menubar)

class DataFileChoiceDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw()
        self.result = None

        self.title("データ選択")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="使用する給与データを選択してください。").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )

        ttk.Button(frm, text="既存データを開く", command=lambda: self._choose("open"), width=20).grid(
            row=1, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Label(frm, text="保存済みのデータファイルを選択します").grid(row=1, column=1, sticky="w", pady=6)

        ttk.Button(frm, text="新しいデータを作成", command=lambda: self._choose("new"), width=20).grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Label(frm, text="任意のファイル名で新しいデータを作成します").grid(row=2, column=1, sticky="w", pady=6)

        ttk.Button(frm, text="キャンセル", command=self._cancel, width=20).grid(
            row=3, column=0, sticky="w", padx=(0, 12), pady=(12, 0)
        )

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())
        enable_enter_key_navigation(self)
        show_centered_window(self, parent)
        self.after(10, self.focus_force)

    def _choose(self, result):
        self.result = result
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _cancel(self):
        self.result = None
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(app_settings.get_window_geometry("main"))

        self.conn = None

        db_path = self._select_db_path()
        if not db_path:
            self.destroy()
            return
        self.db_path = db_path

        schema_path = resource_path("schema.sql")

        self.conn = db.connect(db_path)
        db.init_db(self.conn, schema_path)
        self._remember_db_path(db_path)

        # UI layout
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.payroll_frame = PayrollFrame(self.notebook, self.conn)
        self.bonus_frame = BonusFrame(self.notebook, self.conn)
        self.settings_frame = SettingsFrame(self.notebook, self.conn, show_window_size_button=False)

        self.notebook.add(self.payroll_frame, text="給与")
        self.notebook.add(self.bonus_frame, text="賞与")
        self.notebook.add(self.settings_frame, text="各種設定")

        create_main_menubar(self)

    def open_employee_import(self):
        dlg = EmployeeIODialog(self, self.conn)
        self.wait_window(dlg)

    def export_pay_deduct_excel(self):
        self.payroll_frame.export_pay_deduct_month()

    def export_monthly_payroll_excel(self):
        self.payroll_frame.export_wage_ledger_year()

    def export_payroll_detail_excel(self):
        try:
            target_month = self.payroll_frame._get_target_month("給与明細(.xlsx)")
        except Exception as e:
            messagebox.showerror("入力エラー", str(e), parent=self)
            return

        path = filedialog.asksaveasfilename(
            title="給与明細(.xlsx)",
            defaultextension=".xlsx",
            initialfile=f"給与明細_{target_month}.xlsx",
            filetypes=[("Excel", "*.xlsx")],
            parent=self,
        )
        if not path:
            return

        try:
            db.export_wage_ledger_excel(self.conn, target_month, path)
        except Exception as e:
            messagebox.showerror("エラー", f"出力に失敗しました。\n詳細: {e}", parent=self)
            return
        messagebox.showinfo("完了", f"出力しました。\n{path}", parent=self)

    def open_window_size_settings(self):
        self.settings_frame.open_window_size_settings()

    def open_monthly_input(self):
        self.payroll_frame.open_selected_batch()

    def open_monthly_payroll_list(self):
        self.notebook.select(self.payroll_frame)

    def open_bonus_input(self):
        self.bonus_frame.add_bonus()

    def open_bonus_list(self):
        self.notebook.select(self.bonus_frame)

    def open_resident_tax_annual(self):
        self.settings_frame.open_resident_tax_annual()

    def show_version_info(self):
        messagebox.showinfo(
            "バージョン情報",
            f"アプリ名: {APP_TITLE}\nバージョン: プロトタイプ\nDBパス: {self.db_path}",
            parent=self,
        )

    def _initial_db_dir(self) -> str:
        last_dir = app_settings.get_setting("last_db_dir", "")
        if last_dir and Path(last_dir).exists():
            return last_dir

        last_path = app_settings.get_setting("last_db_path", "")
        if last_path:
            parent = Path(last_path).expanduser().parent
            if parent.exists():
                return str(parent)

        return str(Path.cwd())

    def _select_db_path(self) -> Path | None:
        dlg = DataFileChoiceDialog(self)
        self.wait_window(dlg)

        initial_dir = self._initial_db_dir()
        if dlg.result == "open":
            path = filedialog.askopenfilename(
                title="給与データファイルを選択",
                initialdir=initial_dir,
                filetypes=[
                    ("給与データ", "*.db *.sqlite *.sqlite3"),
                    ("すべてのファイル", "*.*"),
                ],
                parent=self,
            )
            return Path(path) if path else self._select_db_path()

        if dlg.result == "new":
            path = filedialog.asksaveasfilename(
                title="新しい給与データファイルを作成",
                initialdir=initial_dir,
                initialfile="任意のファイル名",
                defaultextension=".db",
                filetypes=[
                    ("SQLite DB", "*.db"),
                    ("SQLite", "*.sqlite *.sqlite3"),
                    ("すべてのファイル", "*.*"),
                ],
                parent=self,
            )
            return Path(path) if path else self._select_db_path()

        return None

    def _remember_db_path(self, db_path: Path) -> None:
        app_settings.set_setting("last_db_path", str(db_path))
        app_settings.set_setting("last_db_dir", str(db_path.parent))

if __name__ == "__main__":
    App().mainloop()
