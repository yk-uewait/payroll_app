import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sys

import app_settings
import db
from ui_payroll import PayrollFrame
from ui_bonus import BonusFrame
from ui_settings import SettingsFrame
from ui_window_utils import center_window

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

class DataFileChoiceDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
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
        center_window(self, parent)
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
        self.geometry("1100x650")

        self.conn = None

        db_path = self._select_db_path()
        if not db_path:
            self.destroy()
            return

        schema_path = resource_path("schema.sql")

        self.conn = db.connect(db_path)
        db.init_db(self.conn, schema_path)
        self._remember_db_path(db_path)

        # UI layout
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        nb.add(PayrollFrame(nb, self.conn), text="月次給与")
        nb.add(BonusFrame(nb, self.conn), text="賞与")
        nb.add(SettingsFrame(nb, self.conn), text="各種設定")

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
            return Path(path) if path else None

        if dlg.result == "new":
            path = filedialog.asksaveasfilename(
                title="新しい給与データファイルを作成",
                initialdir=initial_dir,
                initialfile="payroll.db",
                defaultextension=".db",
                filetypes=[
                    ("SQLite DB", "*.db"),
                    ("SQLite", "*.sqlite *.sqlite3"),
                    ("すべてのファイル", "*.*"),
                ],
                parent=self,
            )
            return Path(path) if path else None

        return None

    def _remember_db_path(self, db_path: Path) -> None:
        app_settings.set_setting("last_db_path", str(db_path))
        app_settings.set_setting("last_db_dir", str(db_path.parent))

if __name__ == "__main__":
    App().mainloop()
