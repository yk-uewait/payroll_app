import tkinter as tk
from tkinter import ttk

from ui_employees import EmployeesFrame
from ui_empins_rate import EmpInsRateDialog
from ui_payment_schedule import PaymentScheduleFrame
from ui_phase1_masters import (
    CompanySettingsDialog,
    EmployeeStandardValueFrame,
    NamedMasterFrame,
    PayrollCategoryFrame,
    PayrollItemFrame,
)
from ui_social_rate import SocialRateDialog
from ui_window_utils import center_window


class FramePopupWindow(tk.Toplevel):
    """ttk.Frame ベースの管理画面をポップアップ表示する共通ウィンドウ。"""

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

        ttk.Label(outer, text="各種設定", font=("", 14, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(outer, text="マスタ・設定系の機能をここから開きます。").pack(anchor="w", pady=(0, 16))

        btn_area = ttk.Frame(outer)
        btn_area.pack(anchor="nw")

        buttons = [
            ("社員管理", self.open_employees),
            ("給与支給方式の設定", self.open_payment_schedules),
            ("雇用保険料率の設定", self.open_empins_rate),
            ("社会保険料率の設定", self.open_social_rate),
            ("会社設定", self.open_company_settings),
            ("部署マスタ", self.open_departments),
            ("役職マスタ", self.open_positions),
            ("雇用区分マスタ", self.open_employment_types),
            ("支給控除カテゴリマスタ", self.open_payroll_categories),
            ("支給控除項目マスタ", self.open_payroll_items),
            ("社員別標準金額", self.open_employee_standard_values),
        ]
        for idx, (text, command) in enumerate(buttons):
            ttk.Button(btn_area, text=text, command=command, width=24).grid(
                row=idx // 2,
                column=idx % 2,
                padx=6,
                pady=6,
                sticky="w",
            )

    def open_employees(self):
        win = FramePopupWindow(self, title="社員管理", frame_class=EmployeesFrame, conn=self.conn, geometry="1100x560")
        win.focus()

    def open_payment_schedules(self):
        win = FramePopupWindow(self, title="給与支給方式", frame_class=PaymentScheduleFrame, conn=self.conn, geometry="630x325")
        win.focus()

    def open_empins_rate(self):
        dlg = EmpInsRateDialog(self, self.conn)
        self.wait_window(dlg)

    def open_social_rate(self):
        dlg = SocialRateDialog(self, self.conn)
        self.wait_window(dlg)

    def open_company_settings(self):
        dlg = CompanySettingsDialog(self, self.conn)
        self.wait_window(dlg)

    def open_departments(self):
        win = FramePopupWindow(
            self,
            title="部署マスタ",
            frame_class=lambda parent, conn: NamedMasterFrame(parent, conn, "departments", "部署マスタ"),
            conn=self.conn,
            geometry="650x420",
        )
        win.focus()

    def open_positions(self):
        win = FramePopupWindow(
            self,
            title="役職マスタ",
            frame_class=lambda parent, conn: NamedMasterFrame(parent, conn, "positions", "役職マスタ"),
            conn=self.conn,
            geometry="650x420",
        )
        win.focus()

    def open_employment_types(self):
        win = FramePopupWindow(
            self,
            title="雇用区分マスタ",
            frame_class=lambda parent, conn: NamedMasterFrame(parent, conn, "employment_types", "雇用区分マスタ"),
            conn=self.conn,
            geometry="650x420",
        )
        win.focus()

    def open_payroll_categories(self):
        win = FramePopupWindow(self, title="支給控除カテゴリマスタ", frame_class=PayrollCategoryFrame, conn=self.conn, geometry="820x440")
        win.focus()

    def open_payroll_items(self):
        win = FramePopupWindow(self, title="支給控除項目マスタ", frame_class=PayrollItemFrame, conn=self.conn, geometry="900x460")
        win.focus()

    def open_employee_standard_values(self):
        win = FramePopupWindow(self, title="社員別標準金額", frame_class=EmployeeStandardValueFrame, conn=self.conn, geometry="900x460")
        win.focus()
