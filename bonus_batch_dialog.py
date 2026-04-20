# bonus_batch_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox

import db


class BonusBatchDialog(tk.Toplevel):
    def __init__(self, master, conn, target_month: str, pay_date: str):
        super().__init__(master)
        self.conn = conn
        self.target_month = target_month
        self.pay_date = pay_date
        self.rows_data = []
        self.selected_employee_index = None
        self.employee_header_labels = []
        self.employee_value_widgets = []

        self.title(f"賞与明細 {target_month} / 支給日 {pay_date}")
        self.geometry("1450x760")
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()

        hdr = ttk.LabelFrame(self, text="対象")
        hdr.pack(fill="x", padx=10, pady=10)
        ttk.Label(hdr, text=f"対象年月: {target_month}").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(hdr, text=f"支給日: {pay_date}").grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self._build_matrix_area()

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="再読み込み", command=self.refresh).pack(side="left", padx=5)
        ttk.Button(btns, text="新規追加", command=self.add_bonus).pack(side="right", padx=5)
        ttk.Button(btns, text="選択社員を編集", command=self.edit_selected).pack(side="right", padx=5)
        ttk.Button(btns, text="選択社員を削除", command=self.delete_selected).pack(side="right", padx=5)
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

        rows = db.list_bonus_rows_by_pay_date(self.conn, self.target_month, self.pay_date)
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
            ("bonus_id", "BID", False),
            ("employee_code", "社員番号", False),
            ("name_kanji", "氏名", False),
            ("department", "部署", False),
            ("pay_date", "支給日", False),
            ("bonus_amount", "賞与額", True),
            ("health_care_display", "健保+介護", True),
            ("childcare_support_employee", "子ども子育て", True),
            ("pension_ins_employee", "厚年", True),
            ("emp_ins_employee", "雇保", True),
            ("social_ins_total_calc", "社保合計", True),
            ("withholding_tax_auto", "源泉(自動)", True),
            ("withholding_tax_override", "源泉(上書)", True),
            ("withholding_tax_applied", "源泉(適用)", True),
            ("net_amount", "差引支給額", True),
            ("note", "備考", False),
        ]

        ttk.Label(self.matrix_frame, text="項目", anchor="center", relief="solid", padding=4).grid(
            row=0, column=0, sticky="nsew"
        )

        self.employee_header_labels = []
        self.employee_value_widgets = []

        for col_idx, row in enumerate(self.rows_data, start=1):
            lbl = tk.Label(
                self.matrix_frame,
                text=f'{row["employee_code"]}\n{row["name_kanji"]}',
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
            ttk.Label(self.matrix_frame, text=title, anchor="w", relief="solid", padding=4).grid(
                row=row_idx, column=0, sticky="nsew"
            )

            line_widgets = []
            for col_idx, row in enumerate(self.rows_data, start=1):
                if key == "health_care_display":
                    value = int(row["health_ins_employee"] or 0) + int(row["care_ins_employee"] or 0)
                elif key == "net_amount":
                    value = (
                        int(row["bonus_amount"] or 0)
                        - int(row["social_ins_total_calc"] or 0)
                        - int(row["withholding_tax_applied"] or 0)
                    )
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

    def _selected_bonus_row(self):
        if self.selected_employee_index is None:
            return None
        if not (0 <= self.selected_employee_index < len(self.rows_data)):
            return None
        return self.rows_data[self.selected_employee_index]

    def edit_selected(self):
        row = self._selected_bonus_row()
        if not row:
            messagebox.showinfo("確認", "対象社員を選択してください。")
            return
        
        from ui_bonus import BonusEditorDialog

        dlg = BonusEditorDialog(self, self.conn, self.target_month, bonus_row=row)
        self.wait_window(dlg)
        self.refresh()
        self._refresh_parent_if_possible()

    def add_bonus(self):
        from ui_bonus import BonusEditorDialog

        dlg = BonusEditorDialog(
            self,
            self.conn,
            self.target_month,
            bonus_row=None,
            initial_pay_date=self.pay_date,
        )
        self.wait_window(dlg)
        self.refresh()
        self._refresh_parent_if_possible()

    def delete_selected(self):
        row = self._selected_bonus_row()
        if not row:
            messagebox.showinfo("確認", "対象社員を選択してください。")
            return

        emp_code = row["employee_code"] if "employee_code" in row.keys() else ""
        emp_name = row["name_kanji"] if "name_kanji" in row.keys() else ""
        pay_date = row["pay_date"] if "pay_date" in row.keys() else self.pay_date

        msg = (
            "選択した賞与明細を削除しますか？\n\n"
            f"社員番号: {emp_code}\n"
            f"氏名: {emp_name}\n"
            f"対象年月: {self.target_month}\n"
            f"支給日: {pay_date}"
        )
        if not messagebox.askyesno("削除確認", msg):
            return

        bonus_id = int(row["bonus_id"])
        db.delete_bonus(self.conn, bonus_id)

        # 明細削除後、親一覧（支給日ごとの一覧）も更新
        self._refresh_parent_if_possible()

        # いま開いている支給日グループを再読み込み
        self.refresh()

        # この支給日の明細が0件になったらダイアログを閉じる
        if not self.rows_data:
            messagebox.showinfo("削除完了", "この支給日の賞与明細は0件になりました。画面を閉じます。")
            self.destroy()
            return

        # 選択位置が末尾を超えた場合の補正
        if self.selected_employee_index is not None and self.selected_employee_index >= len(self.rows_data):
            self.selected_employee_index = len(self.rows_data) - 1
            self._apply_selection_highlight()

    def _refresh_parent_if_possible(self):
        """
        親画面が refresh() を持っていれば再読込する。
        BonusFrame から開いた明細ダイアログを想定。
        """
        parent = self.master
        if parent is not None and hasattr(parent, "refresh"):
            try:
                parent.refresh()
            except Exception:
                pass