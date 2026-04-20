import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import db
from payroll_editor import PayrollEditorDialog


class PayrollBatchDialog(tk.Toplevel):
    """
    対象年月 + 支払日単位の社員明細一覧ダイアログ
    """
    def __init__(self, master, conn, target_month: str, pay_date_applied: str):
        super().__init__(master)
        self.conn = conn
        self.target_month = target_month
        self.pay_date_applied = pay_date_applied
        self.rows_data = []
        self.selected_employee_index = None
        self.employee_header_labels = []
        self.employee_value_widgets = []

        self.title(f"月次給与明細 {target_month} / 支払日 {pay_date_applied}")
        self.geometry("1500x760")
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()

        hdr = ttk.LabelFrame(self, text="対象")
        hdr.pack(fill="x", padx=10, pady=10)
        ttk.Label(hdr, text=f"対象年月: {target_month}").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(hdr, text=f"支払日: {pay_date_applied}").grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self._build_matrix_area()

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="再読み込み", command=self.refresh).pack(side="left", padx=5)
        ttk.Button(btns, text="選択社員を編集（支給・控除）", command=self.edit_selected).pack(side="right", padx=5)
        ttk.Button(btns, text="支払日を上書き/解除", command=self.override_paydate).pack(side="right", padx=5)
        ttk.Button(btns, text="閉じる", command=self.destroy).pack(side="right", padx=5)

        self.refresh()

    def _build_matrix_area(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(body, highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(body, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self.matrix_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.matrix_frame, anchor="nw")

        self.matrix_frame.bind("<Configure>", self._on_matrix_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_matrix_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.canvas_window, height=max(event.height, 1))

    def refresh(self):
        def fmt_yen(v):
            if v is None or v == "":
                return ""
            try:
                return f"{int(v):,}"
            except Exception:
                return str(v)

        rows = db.get_payroll_rows_by_pay_date(self.conn, self.target_month, self.pay_date_applied)
        self.rows_data = list(rows)

        if self.selected_employee_index is not None and self.selected_employee_index >= len(self.rows_data):
            self.selected_employee_index = None
        if self.selected_employee_index is None and self.rows_data:
            self.selected_employee_index = 0

        self._render_matrix(fmt_yen)

    def _render_matrix(self, fmt_yen):
        for child in self.matrix_frame.winfo_children():
            child.destroy()

        item_defs = [
            ("payroll_id", "PID", False),
            ("employee_code", "社員番号", False),
            ("name_kanji", "氏名", False),
            ("department", "部署", False),
            ("pay_date_auto", "支払日(自動)", False),
            ("pay_date_override", "支払日(上書き)", False),
            ("pay_date_applied", "支払日(適用)", False),
            ("emp_ins_base", "雇保基礎", True),
            ("emp_ins_employee", "雇保(従業員)", True),
            ("health_care_display", "健保+介護", True),
            ("childcare_support_employee", "子ども子育て", True),
            ("pension_ins_employee", "厚年(従業員)", True),
            ("social_ins_total_calc", "社保合計", True),
            ("resident_tax_auto", "住民税(自動)", True),
            ("resident_tax_override", "住民税(上書き)", True),
            ("resident_tax_applied", "住民税(適用)", True),
            ("withholding_tax_auto", "所得税(自動)", True),
            ("withholding_tax_override", "所得税(上書き)", True),
            ("withholding_tax_applied", "所得税(適用)", True),
            ("total_pay_input", "総支給(入力)", True),
            ("total_deduct_input", "控除合計(入力)", True),
            ("net_pay_input", "手取り(入力)", True),
        ]

        ttk.Label(
            self.matrix_frame,
            text="項目",
            anchor="center",
            relief="solid",
            padding=4
        ).grid(row=0, column=0, sticky="nsew")

        self.employee_header_labels = []
        self.employee_value_widgets = []

        for col_idx, row in enumerate(self.rows_data, start=1):
            label_text = f'{row["employee_code"]}\n{row["name_kanji"]}'
            lbl = tk.Label(
                self.matrix_frame,
                text=label_text,
                relief="solid",
                borderwidth=1,
                padx=6,
                pady=6,
                cursor="hand2",
                bg="#d9edf7" if col_idx - 1 == self.selected_employee_index else "#f0f0f0",
            )
            lbl.grid(row=0, column=col_idx, sticky="nsew")
            lbl.bind("<Button-1>", lambda e, idx=col_idx - 1: self._set_selected_employee_index(idx))
            lbl.bind("<Double-1>", lambda e, idx=col_idx - 1: self._set_selected_employee_index(idx, open_editor=True))
            self.employee_header_labels.append(lbl)

        for row_idx, (key, title, is_money) in enumerate(item_defs, start=1):
            ttk.Label(
                self.matrix_frame,
                text=title,
                anchor="w",
                relief="solid",
                padding=4
            ).grid(row=row_idx, column=0, sticky="nsew")

            line_widgets = []
            for col_idx, row in enumerate(self.rows_data, start=1):
                if key == "health_care_display":
                    value = int(row["health_ins_employee"] or 0) + int(row["care_ins_employee"] or 0)
                else:
                    value = row[key] if key in row.keys() else ""

                if value is None:
                    value = ""
                if is_money and value != "":
                    value = fmt_yen(value)

                lbl = tk.Label(
                    self.matrix_frame,
                    text=value,
                    relief="solid",
                    borderwidth=1,
                    padx=6,
                    pady=4,
                    anchor="e" if is_money else "w",
                    justify="left",
                    bg="#fcf8e3" if col_idx - 1 == self.selected_employee_index else "white",
                )
                lbl.grid(row=row_idx, column=col_idx, sticky="nsew")
                lbl.bind("<Button-1>", lambda e, idx=col_idx - 1: self._set_selected_employee_index(idx))
                lbl.bind("<Double-1>", lambda e, idx=col_idx - 1: self._set_selected_employee_index(idx, open_editor=True))
                line_widgets.append(lbl)
            self.employee_value_widgets.append(line_widgets)

        self.matrix_frame.grid_columnconfigure(0, weight=0, minsize=170)
        for col_idx in range(1, len(self.rows_data) + 1):
            self.matrix_frame.grid_columnconfigure(col_idx, weight=0, minsize=130)

        self._apply_selection_highlight()

    def _apply_selection_highlight(self):
        for idx, lbl in enumerate(self.employee_header_labels):
            lbl.configure(bg="#d9edf7" if idx == self.selected_employee_index else "#f0f0f0")

        for line_widgets in self.employee_value_widgets:
            for idx, lbl in enumerate(line_widgets):
                lbl.configure(bg="#fcf8e3" if idx == self.selected_employee_index else "white")
 
    def _set_selected_employee_index(self, idx: int, open_editor: bool = False):
        self.selected_employee_index = idx
        self._apply_selection_highlight()
        if open_editor:
            self.edit_selected()

    def _selected_payroll_row(self):
        if self.selected_employee_index is None:
            return None
        if self.selected_employee_index < 0 or self.selected_employee_index >= len(self.rows_data):
            return None
        return self.rows_data[self.selected_employee_index]

    def _selected_payroll_id(self):
        row = self._selected_payroll_row()
        if not row:
            return None
        return int(row["payroll_id"])

    def edit_selected(self):
        payroll_id = self._selected_payroll_id()
        if not payroll_id:
            messagebox.showinfo("確認", "対象社員を選択してください。")
            return

        pay_names = [f"支給自由{i}" for i in range(1, 6)]
        deduct_names = [f"控除自由{i}" for i in range(1, 6)]

        dlg = PayrollEditorDialog(self, self.conn, payroll_id, pay_names, deduct_names)
        self.wait_window(dlg)
        self.refresh()

    def override_paydate(self):
        payroll_id = self._selected_payroll_id()
        if not payroll_id:
            messagebox.showinfo("確認", "対象社員を選択してください。")
            return

        override = simpledialog.askstring(
            "支払日上書き",
            "上書きする支払日（YYYY-MM-DD）を入力。\n空欄を入力したい場合はキャンセル後に解除を選んでください。",
        )
        if override is None:
            return

        override = override.strip()
        if override == "":
            db.override_pay_date(self.conn, payroll_id, None, None, overridden_by="operator")
            self.refresh()
            return

        reason = simpledialog.askstring("上書き理由", "上書き理由（任意）")
        db.override_pay_date(self.conn, payroll_id, override, reason, overridden_by="operator")
        self.refresh()