import tkinter as tk
from tkinter import ttk

from ui_employees import EmployeesFrame
from ui_payment_schedule import PaymentScheduleFrame
from ui_empins_rate import EmpInsRateDialog
from ui_social_rate import SocialRateDialog
from ui_window_utils import center_window


class FramePopupWindow(tk.Toplevel):
    """
    ttk.Frame ベースの既存画面を、そのままポップアップ表示するための共通ウィンドウ
    """
    def __init__(self, parent, title: str, frame_class, conn, geometry: str = "1100x700"):
        super().__init__(parent)
        self.conn = conn
        self.title(title)
        self.geometry(geometry)
        self.transient(parent)

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self.inner_frame = frame_class(container, conn)
        self.inner_frame.pack(fill="both", expand=True)
        center_window(self, parent)


class SettingsFrame(ttk.Frame):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(outer, text="各種設定", font=("", 14, "bold"))
        title.pack(anchor="w", pady=(0, 12))

        desc = ttk.Label(
            outer,
            text="マスタ・設定系の機能をここから開きます。",
        )
        desc.pack(anchor="w", pady=(0, 16))

        btn_area = ttk.Frame(outer)
        btn_area.pack(anchor="nw")

        ttk.Button(
            btn_area,
            text="社員管理",
            command=self.open_employees,
            width=24,
        ).grid(row=0, column=0, padx=6, pady=6, sticky="w")

        ttk.Button(
            btn_area,
            text="給与支給方式の設定",
            command=self.open_payment_schedules,
            width=24,
        ).grid(row=0, column=1, padx=6, pady=6, sticky="w")

        ttk.Button(
            btn_area,
            text="雇用保険料率の設定",
            command=self.open_empins_rate,
            width=24,
        ).grid(row=1, column=0, padx=6, pady=6, sticky="w")

        ttk.Button(
            btn_area,
            text="社会保険料率の設定",
            command=self.open_social_rate,
            width=24,
        ).grid(row=1, column=1, padx=6, pady=6, sticky="w")

    def open_employees(self):
        win = FramePopupWindow(
            self,
            title="社員管理",
            frame_class=EmployeesFrame,
            conn=self.conn,
            geometry="1100x700",
        )
        win.focus()

    def open_payment_schedules(self):
        win = FramePopupWindow(
            self,
            title="給与支給方式",
            frame_class=PaymentScheduleFrame,
            conn=self.conn,
            geometry="900x650",
        )
        win.focus()

    def open_empins_rate(self):
        dlg = EmpInsRateDialog(self, self.conn)
        self.wait_window(dlg)

    def open_social_rate(self):
        dlg = SocialRateDialog(self, self.conn)
        self.wait_window(dlg)
