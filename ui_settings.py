import tkinter as tk
from tkinter import ttk

import app_settings
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
from ui_resident_tax_annual import ResidentTaxAnnualFrame
from ui_social_rate import SocialRateDialog
from ui_window_utils import center_window, enable_enter_key_navigation


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
        enable_enter_key_navigation(self)
        center_window(self, parent)


class WindowSizeSettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("画面サイズ設定")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        current_label = app_settings.WINDOW_SIZE_PRESETS[app_settings.get_window_size_key()]["label"]
        self.var_size = tk.StringVar(value=current_label)

        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="画面サイズ").pack(anchor="w", pady=(0, 8))
        for label in ("小", "中", "大"):
            ttk.Radiobutton(frm, text=label, value=label, variable=self.var_size).pack(anchor="w", pady=3)

        footer = ttk.Frame(frm)
        footer.pack(fill="x", pady=(14, 0))
        ttk.Button(footer, text="適用", command=self.apply).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="キャンセル", command=self.destroy).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        enable_enter_key_navigation(self)
        center_window(self, parent)

    def apply(self):
        app_settings.set_window_size_by_label(self.var_size.get())
        self.master.winfo_toplevel().geometry(app_settings.get_window_geometry("main"))
        self.destroy()


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
            ("画面サイズ設定", self.open_window_size_settings),
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
        buttons.append(("住民税年次一括入力", self.open_resident_tax_annual))
        for idx, (text, command) in enumerate(buttons):
            ttk.Button(btn_area, text=text, command=command, width=24).grid(
                row=idx // 2,
                column=idx % 2,
                padx=6,
                pady=6,
                sticky="w",
            )
        ttk.Frame(outer).pack(fill="both", expand=True)
        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Button(footer, text="閉じる", command=self._close_window).pack(side="right")
        enable_enter_key_navigation(self)

    def _close_window(self):
        self.winfo_toplevel().destroy()

    def open_window_size_settings(self):
        dlg = WindowSizeSettingsDialog(self)
        self.wait_window(dlg)

    def open_employees(self):
        win = FramePopupWindow(self, title="社員管理", frame_class=EmployeesFrame, conn=self.conn, geometry="1100x560")
        win.focus()

    def open_resident_tax_annual(self):
        win = FramePopupWindow(self, title="住民税年次一括入力", frame_class=ResidentTaxAnnualFrame, conn=self.conn, geometry="1180x590")
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
