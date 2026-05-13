# bonus_batch_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox

import app_settings
import db
from ui_window_utils import show_centered_window, enable_enter_key_navigation


SEPARATOR_COLOR = "#cbd5e1"
SEPARATOR_HEIGHT = 2
LABEL_COLUMN_WIDTH = 170
EMPLOYEE_COLUMN_WIDTH = 130
DEPARTMENT_WRAP_LENGTH = EMPLOYEE_COLUMN_WIDTH - 12


def format_department_for_matrix_display(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    delimiter = "＞" if "＞" in text else ">" if ">" in text else None
    if not delimiter:
        return text
    parts = [part.strip() for part in text.split(delimiter) if part.strip()]
    if not parts:
        return text
    lines = []
    for idx, part in enumerate(parts):
        suffix = " ＞" if idx < len(parts) - 1 else ""
        lines.append(f"{'  ' * idx}{part}{suffix}")
    return "\n".join(lines)


def _format_year_month(value: str) -> str:
    try:
        year, month = str(value).split("-", 1)
        return f"{int(year):04d} 年 {int(month):02d} 月"
    except Exception:
        return str(value or "")


def _format_year_month_day(value: str) -> str:
    try:
        year, month, day = str(value).split("-", 2)
        return f"{int(year):04d} 年 {int(month):02d} 月 {int(day):02d} 日"
    except Exception:
        return str(value or "")


class BonusBatchDialog(tk.Toplevel):
    def __init__(self, master, conn, target_month: str, pay_date: str):
        super().__init__(master)
        self.withdraw()
        self.conn = conn
        self.target_month = target_month
        self.pay_date = pay_date
        self.rows_data = []
        self.selected_employee_index = None
        self.employee_header_labels = []
        self.employee_value_widgets = []
        self.matrix_row_styles = []
        self.department_options = []
        self.department_label_to_id = {}
        self.var_department_filter = tk.StringVar(value="全社")

        self.title("賞与支給控除一覧表")
        self.geometry(app_settings.get_window_geometry("bonus_batch"))
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()

        hdr = ttk.LabelFrame(self, text="対象")
        hdr.pack(fill="x", padx=10, pady=10)
        ttk.Label(hdr, text="対象年月").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(hdr, text=_format_year_month(target_month)).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(hdr, text="支給日").grid(row=0, column=2, padx=(20, 5), pady=5, sticky="w")
        ttk.Label(hdr, text=_format_year_month_day(pay_date)).grid(row=0, column=3, padx=5, pady=5, sticky="w")
        ttk.Label(hdr, text="部署").grid(row=0, column=4, padx=(20, 5), pady=5, sticky="w")
        self.cmb_department_filter = ttk.Combobox(
            hdr,
            textvariable=self.var_department_filter,
            state="readonly",
            width=28,
        )
        self.cmb_department_filter.grid(row=0, column=5, padx=5, pady=5, sticky="w")
        self._load_department_filter_options()
        self.cmb_department_filter.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        self._build_matrix_area()

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="編集", command=self.edit_selected).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="未入力社員を追加", command=self.add_bonus).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="選択社員を削除", command=self.delete_selected).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.destroy).pack(side="right", padx=5)

        self.refresh()
        enable_enter_key_navigation(self)
        show_centered_window(self, master)

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
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self.matrix_frame.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)

    def _on_matrix_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(
            self.canvas_window,
            width=max(event.width, self.matrix_frame.winfo_reqwidth()),
            height=max(event.height, self.matrix_frame.winfo_reqheight()),
        )
        self._on_matrix_configure()

    def _on_shift_mousewheel(self, event):
        self.canvas.xview_scroll(int(-10 * (event.delta / 120)), "units")
        return "break"

    def _load_department_filter_options(self):
        self.department_options = [("全社", None)]
        self.department_label_to_id = {"全社": None}
        try:
            for item in db.list_department_hierarchy(self.conn, include_inactive=False):
                label = item.get("display_name") or item.get("full_name") or item.get("name") or ""
                if not label:
                    continue
                self.department_options.append((label, int(item["id"])))
                self.department_label_to_id[label] = int(item["id"])
        except Exception:
            pass
        self.cmb_department_filter["values"] = [label for label, _dept_id in self.department_options]
        if self.var_department_filter.get() not in self.department_label_to_id:
            self.var_department_filter.set("全社")

    def _selected_department_id(self):
        return self.department_label_to_id.get(self.var_department_filter.get())

    def _department_filter_ids(self):
        dept_id = self._selected_department_id()
        if not dept_id:
            return None
        try:
            ids = db.get_department_descendant_ids(self.conn, int(dept_id))
        except Exception:
            ids = set()
        ids.add(int(dept_id))
        return ids

    def _row_matches_department_filter(self, row) -> bool:
        filter_ids = self._department_filter_ids()
        if filter_ids is None:
            return True
        try:
            row_dept_id = int(row["department_id"] or 0)
        except Exception:
            row_dept_id = 0
        return row_dept_id in filter_ids

    def refresh(self):
        def fmt_yen(v):
            if v is None or v == "":
                return ""
            try:
                return f"{int(v):,}"
            except Exception:
                return str(v)

        rows = db.list_bonus_rows_by_pay_date(self.conn, self.target_month, self.pay_date)
        self.rows_data = [row for row in rows if self._row_matches_department_filter(row)]

        if self.selected_employee_index is not None and self.selected_employee_index >= len(self.rows_data):
            self.selected_employee_index = None
        if self.selected_employee_index is None and self.rows_data:
            self.selected_employee_index = 0

        self._render_matrix(fmt_yen)

    def _row_def(self, key, title, is_money, row_kind="data", emphasis=False):
        return {
            "key": key,
            "title": title,
            "is_money": is_money,
            "row_kind": row_kind,
            "emphasis": emphasis,
        }

    def _render_matrix(self, fmt_yen):
        for child in self.matrix_frame.winfo_children():
            child.destroy()

        item_defs = [
            self._row_def("department", "部署", False),
            self._row_def("separator_pay", "", False, row_kind="separator"),
            self._row_def("bonus_amount", "賞与支給額", True, emphasis=True),
            self._row_def("bonus_total", "支給金額合計", True, emphasis=True),
            self._row_def("separator_deduction", "", False, row_kind="separator"),
            self._row_def("health_ins_employee", "健康保険料", True),
            self._row_def("care_ins_employee", "介護保険料", True),
            self._row_def("childcare_support_employee", "子ども・子育て支援金", True),
            self._row_def("pension_ins_employee", "厚生年金保険料", True),
            self._row_def("social_ins_total_calc", "社会保険料合計", True, emphasis=True),
            self._row_def("emp_ins_employee", "雇用保険料", True),
            self._row_def("withholding_tax_applied", "所得税", True),
            self._row_def("deduction_total", "控除合計額", True, emphasis=True),
            self._row_def("separator_net", "", False, row_kind="separator"),
            self._row_def("net_amount", "差引支給額", True, emphasis=True),
            self._row_def("note", "備考", False),
        ]

        ttk.Label(
            self.matrix_frame,
            text="社員番号\n名前",
            anchor="center",
            justify="center",
            relief="solid",
            padding=4,
        ).grid(row=0, column=0, sticky="nsew")

        self.employee_header_labels = []
        self.employee_value_widgets = []
        self.matrix_row_styles = []

        for col_idx, row in enumerate(self.rows_data, start=1):
            lbl = tk.Label(
                self.matrix_frame,
                text=f'{row["employee_code"]}\n{row["name_kanji"]}',
                relief="solid",
                borderwidth=1,
                padx=6,
                pady=6,
                bg="#d9edf7" if col_idx - 1 == self.selected_employee_index else "#f0f0f0",
            )
            lbl.grid(row=0, column=col_idx, sticky="nsew")
            lbl.bind("<Button-1>", lambda e, idx=col_idx - 1: self._set_selected_employee_index(idx))
            lbl.bind("<Double-1>", lambda e, idx=col_idx - 1: self._set_selected_employee_index(idx, open_editor=True))
            lbl.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
            self.employee_header_labels.append(lbl)

        for row_idx, item_def in enumerate(item_defs, start=1):
            if item_def["row_kind"] == "separator":
                sep_lbl = tk.Frame(self.matrix_frame, bg=SEPARATOR_COLOR, height=SEPARATOR_HEIGHT)
                sep_lbl.grid(row=row_idx, column=0, sticky="ew")
                sep_lbl.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
                line_widgets = []
                for col_idx, _row in enumerate(self.rows_data, start=1):
                    sep = tk.Frame(self.matrix_frame, bg=SEPARATOR_COLOR, height=SEPARATOR_HEIGHT)
                    sep.grid(row=row_idx, column=col_idx, sticky="ew")
                    sep.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
                    line_widgets.append(sep)
                self.employee_value_widgets.append(line_widgets)
                self.matrix_row_styles.append({"row_kind": "separator", "emphasis": False, "bg": SEPARATOR_COLOR})
                continue

            title = item_def["title"]
            is_money = item_def["is_money"]
            emphasis = item_def["emphasis"]
            title_bg = "#f8fafc" if emphasis else "#f0f0f0"
            value_bg = "#f8fafc" if emphasis else "white"
            font = ("TkDefaultFont", 9, "bold") if emphasis else ("TkDefaultFont", 9)

            title_lbl = tk.Label(
                self.matrix_frame,
                text=title,
                anchor="w",
                relief="flat",
                borderwidth=0,
                highlightthickness=1,
                highlightbackground="#e5e7eb",
                padx=6,
                pady=4,
                bg=title_bg,
                font=font,
            )
            title_lbl.grid(row=row_idx, column=0, sticky="nsew")
            title_lbl.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)

            line_widgets = []
            for col_idx, row in enumerate(self.rows_data, start=1):
                value = self._matrix_value(row, item_def["key"])
                if value is None:
                    value = ""
                if is_money and value != "":
                    value = fmt_yen(value)
                is_department_row = item_def["key"] == "department"
                if is_department_row:
                    value = format_department_for_matrix_display(value)

                lbl = tk.Label(
                    self.matrix_frame,
                    text=value,
                    relief="flat",
                    borderwidth=0,
                    highlightthickness=1,
                    highlightbackground="#e5e7eb",
                    padx=6,
                    pady=4,
                    anchor="e" if is_money else "nw" if is_department_row else "w",
                    justify="left",
                    wraplength=DEPARTMENT_WRAP_LENGTH if is_department_row else 0,
                    bg=value_bg,
                    font=font,
                )
                lbl.grid(row=row_idx, column=col_idx, sticky="nsew")
                lbl.bind("<Button-1>", lambda e, idx=col_idx - 1: self._set_selected_employee_index(idx))
                lbl.bind("<Double-1>", lambda e, idx=col_idx - 1: self._set_selected_employee_index(idx, open_editor=True))
                lbl.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
                line_widgets.append(lbl)

            self.employee_value_widgets.append(line_widgets)
            self.matrix_row_styles.append({"row_kind": "data", "emphasis": emphasis, "bg": value_bg})

        self.matrix_frame.grid_columnconfigure(0, weight=0, minsize=LABEL_COLUMN_WIDTH)
        for col_idx in range(1, len(self.rows_data) + 1):
            self.matrix_frame.grid_columnconfigure(col_idx, weight=0, minsize=EMPLOYEE_COLUMN_WIDTH)

        self._apply_selection_highlight()
        self.matrix_frame.update_idletasks()
        self.canvas.itemconfigure(
            self.canvas_window,
            width=max(self.canvas.winfo_width(), self.matrix_frame.winfo_reqwidth()),
            height=max(self.canvas.winfo_height(), self.matrix_frame.winfo_reqheight()),
        )
        self._on_matrix_configure()

    def _matrix_value(self, row, key):
        bonus = int(row["bonus_amount"] or 0)
        social = (
            int(row["health_ins_employee"] or 0)
            + int(row["care_ins_employee"] or 0)
            + int(row["childcare_support_employee"] or 0)
            + int(row["pension_ins_employee"] or 0)
        )
        emp_ins = int(row["emp_ins_employee"] or 0)
        withholding = int(row["withholding_tax_applied"] or 0)
        deduction_total = social + emp_ins + withholding

        if key == "bonus_total":
            return bonus
        if key == "social_ins_total_calc":
            return social
        if key == "deduction_total":
            return deduction_total
        if key == "net_amount":
            return bonus - deduction_total
        return row[key] if key in row.keys() else ""

    def _apply_selection_highlight(self):
        for idx, lbl in enumerate(self.employee_header_labels):
            lbl.configure(bg="#d9edf7" if idx == self.selected_employee_index else "#f0f0f0")
        for row_style, line_widgets in zip(self.matrix_row_styles, self.employee_value_widgets):
            if row_style["row_kind"] == "separator":
                for lbl in line_widgets:
                    lbl.configure(bg=SEPARATOR_COLOR)
                continue
            base_bg = "#f8fafc" if row_style.get("emphasis") else "white"
            for idx, lbl in enumerate(line_widgets):
                lbl.configure(bg="#fcf8e3" if idx == self.selected_employee_index else base_bg)

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

        existing_ids = {
            int(row[0])
            for row in self.conn.execute(
                "SELECT employee_id FROM payroll_bonus WHERE target_month = ?",
                (self.target_month,),
            ).fetchall()
        }
        all_employees = db.list_employees(self.conn)
        filter_ids = self._department_filter_ids()
        missing_ids = set()
        for employee in all_employees:
            employee_id = int(employee["employee_id"])
            if employee_id in existing_ids:
                continue
            if filter_ids is not None:
                try:
                    employee_dept_id = int(employee["department_id"] or 0)
                except Exception:
                    employee_dept_id = 0
                if employee_dept_id not in filter_ids:
                    continue
            missing_ids.add(employee_id)
        if not missing_ids:
            messagebox.showinfo("確認", "追加できる未入力社員がいません。", parent=self)
            return

        dlg = BonusEditorDialog(
            self,
            self.conn,
            self.target_month,
            bonus_row=None,
            initial_pay_date=self.pay_date,
            employee_ids=missing_ids,
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
            f"名前: {emp_name}\n"
            f"対象年月: {self.target_month}\n"
            f"支給日: {pay_date}"
        )
        if not messagebox.askyesno("削除確認", msg):
            return

        bonus_id = int(row["bonus_id"])
        db.delete_bonus(self.conn, bonus_id)
        self._refresh_parent_if_possible()
        self.refresh()

        if not self.rows_data:
            messagebox.showinfo("削除完了", "この支給日の賞与明細は0件になりました。画面を閉じます。")
            self.destroy()
            return

        if self.selected_employee_index is not None and self.selected_employee_index >= len(self.rows_data):
            self.selected_employee_index = len(self.rows_data) - 1
            self._apply_selection_highlight()

    def _refresh_parent_if_possible(self):
        parent = self.master
        if parent is not None and hasattr(parent, "refresh"):
            try:
                parent.refresh()
            except Exception:
                pass
