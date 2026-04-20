import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sys

import db
from ui_payroll import PayrollFrame
from ui_bonus import BonusFrame
from ui_settings import SettingsFrame

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

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x650")

        self.conn = None

        # Ask data folder
        messagebox.showinfo("データ保存先", "データ保存先フォルダ（USB/SharePointのフォルダ）を選択してください。")
        folder = filedialog.askdirectory(title="データ保存先フォルダを選択")
        if not folder:
            messagebox.showerror("終了", "保存先が選択されなかったため終了します。")
            self.destroy()
            return

        data_dir = Path(folder)
        db_path = data_dir / "payroll.db"
        schema_path = resource_path("schema.sql")

        self.conn = db.connect(db_path)
        db.init_db(self.conn, schema_path)

        # UI layout
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        nb.add(PayrollFrame(nb, self.conn), text="月次給与")
        nb.add(BonusFrame(nb, self.conn), text="賞与")
        nb.add(SettingsFrame(nb, self.conn), text="各種設定")

if __name__ == "__main__":
    App().mainloop()