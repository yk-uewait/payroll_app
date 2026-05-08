import tkinter as tk
from tkinter import ttk

import app_settings
from ui_employees import EmployeesFrame
from ui_empins_rate import EmpInsRateDialog
from ui_payment_schedule import PaymentScheduleFrame
from ui_phase1_masters import (
    CompanySettingsDialog,
    EmployeeStandardValueFrame,
    DepartmentMasterFrame,
    NamedMasterFrame,
    PayrollCategoryFrame,
    PayrollItemFrame,
)
from ui_resident_tax_annual import ResidentTaxAnnualFrame
from ui_social_rate import SocialRateDialog
from ui_window_utils import apply_safe_geometry, show_centered_window, enable_enter_key_navigation


class FramePopupWindow(tk.Toplevel):
    """ttk.Frame ベースの管理画面をポップアップ表示する共通ウィンドウ。"""

    def __init__(self, parent, title: str, frame_class, conn, geometry: str = "1100x700"):
        super().__init__(parent)
        self.withdraw()
        self.conn = conn
        self.title(title)
        self.geometry(geometry)
        self.transient(parent)

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self.inner_frame = frame_class(container, conn)
        self.inner_frame.pack(fill="both", expand=True)
        enable_enter_key_navigation(self)
        show_centered_window(self, parent)


class WindowSizeSettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw()
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
        show_centered_window(self, parent)

    def apply(self):
        app_settings.set_window_size_by_label(self.var_size.get())
        apply_safe_geometry(self.master.winfo_toplevel(), app_settings.get_window_geometry("main"))
        self.destroy()


class SettingsFrame(ttk.Frame):
    def __init__(self, master, conn, show_window_size_button: bool = True):
        super().__init__(master)
        self.conn = conn

        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="各種設定", font=("", 14, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(outer, text="アプリで使用する会社情報、組織、給与項目、税・保険関連の設定を行います。").pack(anchor="w", pady=(0, 12))

        list_area = ttk.LabelFrame(outer, text="設定項目", padding=8)
        list_area.pack(fill="both", expand=True)
        canvas = tk.Canvas(list_area, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_area, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(canvas_window, width=e.width))

        self._add_section(scroll_frame, "会社・組織")
        self._add_setting_row(scroll_frame, "会社設定", self.open_company_settings, "会社名、住所、電話番号など、帳票に表示する会社情報を設定します。")
        self._add_setting_row(scroll_frame, "社員管理", self.open_employees, "社員番号、氏名、所属、給与支給方式など、給与計算に使う社員情報を管理します。")
        self._add_setting_row(scroll_frame, "部署・事業所マスタ", self.open_departments, "部署・事業所・課など、社員の所属先を階層的に設定します。給与項目の表示条件にも使用できます。")
        self._add_setting_row(scroll_frame, "役職マスタ", self.open_positions, "社員に紐づける役職を設定します。役職ごとの手当表示などに使用できます。")
        self._add_setting_row(scroll_frame, "雇用区分マスタ", self.open_employment_types, "役員、正社員、契約社員、パートなどの雇用区分を設定します。")

        self._add_section(scroll_frame, "支給控除")
        self._add_setting_row(scroll_frame, "給与支給方式の設定", self.open_payment_schedules, "当月払い、翌月払い、支給日など、社員に紐づける給与支給方式を設定します。")
        self._add_setting_row(scroll_frame, "支給控除マスタ（大分類）", self.open_payroll_categories, "支給・控除項目をまとめる分類です。通常は初期設定のままで使用できます。")
        self._add_setting_row(scroll_frame, "支給控除マスタ（中分類）", self.open_payroll_items, "給与明細や月次入力画面に表示する実際の支給・控除項目です。普段はこちらを使用します。")
        self._add_setting_row(
            scroll_frame,
            "社員別標準金額設定",
            self.open_employee_standard_values,
            "社員ごとに基本給・通勤手当・手当などの標準額を設定します。\n特定社員に独自の金額を持たせたい場合に使用し、毎月の月次入力時に初期値として反映されます。",
        )

        self._add_section(scroll_frame, "税・保険・年次処理")
        self._add_setting_row(scroll_frame, "雇用保険料率の設定", self.open_empins_rate, "給与計算で使用する雇用保険料率を設定します。")
        self._add_setting_row(scroll_frame, "社会保険料率の設定", self.open_social_rate, "健康保険、介護保険、厚生年金などの社会保険料率を設定します。")
        self._add_setting_row(scroll_frame, "住民税年次一括入力", self.open_resident_tax_annual, "年度ごとの住民税額を、社員一覧で12か月分まとめて入力します。")
        self._bind_mousewheel(canvas, scroll_frame)

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Button(footer, text="閉じる", command=self._close_window).pack(side="right")
        enable_enter_key_navigation(self)

    def _add_section(self, parent, title: str):
        ttk.Label(parent, text=f"■ {title}", font=("", 11, "bold")).pack(anchor="w", pady=(12, 6))

    def _add_setting_row(self, parent, text: str, command, description: str):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=3)
        ttk.Button(row, text=text, command=command, width=26).pack(side="left", padx=(0, 14), anchor="n")
        ttk.Label(row, text=description, wraplength=620, justify="left").pack(side="left", fill="x", expand=True, anchor="w")

    def _bind_mousewheel(self, canvas, root_widget):
        def on_mousewheel(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        def bind_recursive(widget):
            widget.bind("<MouseWheel>", on_mousewheel, add="+")
            widget.bind("<Button-4>", on_mousewheel, add="+")
            widget.bind("<Button-5>", on_mousewheel, add="+")
            for child in widget.winfo_children():
                bind_recursive(child)

        bind_recursive(root_widget)
        canvas.bind("<MouseWheel>", on_mousewheel, add="+")
        canvas.bind("<Button-4>", on_mousewheel, add="+")
        canvas.bind("<Button-5>", on_mousewheel, add="+")

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
            title="部署・事業所マスタ",
            frame_class=DepartmentMasterFrame,
            conn=self.conn,
            geometry="850x520",
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
        win = FramePopupWindow(self, title="支給控除マスタ（大分類）", frame_class=PayrollCategoryFrame, conn=self.conn, geometry="860x500")
        win.focus()

    def open_payroll_items(self):
        win = FramePopupWindow(self, title="支給控除マスタ（中分類）", frame_class=PayrollItemFrame, conn=self.conn, geometry="980x500")
        win.focus()

    def open_employee_standard_values(self):
        win = FramePopupWindow(self, title="社員別標準金額設定", frame_class=EmployeeStandardValueFrame, conn=self.conn, geometry="900x460")
        win.focus()
