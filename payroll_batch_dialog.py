import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import db
import app_settings
from payroll_editor import PayrollEditorDialog
from ui_window_utils import show_centered_window, enable_enter_key_navigation
from utils_dates import compute_pay_date, parse_month


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


class PayrollBatchDialog(tk.Toplevel):
    """
    対象年月 + 支払日単位の社員明細一覧ダイアログ
    """
    def __init__(self, master, conn, target_month: str, pay_date_applied: str):
        super().__init__(master)
        self.withdraw()
        self.conn = conn
        self.target_month = target_month
        self.pay_date_applied = pay_date_applied
        self.rows_data = []
        self.selected_employee_index = None
        self.employee_header_labels = []
        self.employee_value_widgets = []
        self.output_data_by_payroll_id = {}
        self.department_options = []
        self.department_label_to_id = {}
        self.var_department_filter = tk.StringVar(value="全社")

        self.title("給与支給控除一覧表")
        self.geometry(app_settings.get_window_geometry("payroll_batch"))
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

        hdr = ttk.LabelFrame(self, text="対象")
        hdr.pack(fill="x", padx=10, pady=10)
        ttk.Label(hdr, text="対象年月").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(hdr, text=_format_year_month(target_month)).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(hdr, text="支給日").grid(row=0, column=2, padx=(20, 5), pady=5, sticky="w")
        ttk.Label(hdr, text=_format_year_month_day(pay_date_applied)).grid(row=0, column=3, padx=5, pady=5, sticky="w")
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
        ttk.Button(btns, text="未計算社員を追加", command=self.add_missing_employees).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self._close).pack(side="right")

        self.refresh()
        enable_enter_key_navigation(self)
        show_centered_window(self, master)

    def _build_matrix_area(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        self.header_canvas = tk.Canvas(body, highlightthickness=0, height=44)
        self.canvas = tk.Canvas(body, highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(body, orient="horizontal", command=self._xview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self._on_xscroll)

        self.header_canvas.grid(row=0, column=0, sticky="ew")
        ttk.Frame(body, width=16).grid(row=0, column=1, sticky="ns")
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.v_scroll.grid(row=1, column=1, sticky="ns")
        self.h_scroll.grid(row=2, column=0, sticky="ew")
        body.grid_rowconfigure(1, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self.header_frame = ttk.Frame(self.header_canvas)
        self.header_window = self.header_canvas.create_window((0, 0), window=self.header_frame, anchor="nw")
        self.matrix_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.matrix_frame, anchor="nw")

        self.header_frame.bind("<Configure>", self._on_header_configure)
        self.header_canvas.bind("<Configure>", self._on_header_canvas_configure)
        self.matrix_frame.bind("<Configure>", self._on_matrix_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.header_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.header_canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self.header_canvas.bind("<Button-4>", self._on_mousewheel)
        self.header_canvas.bind("<Button-5>", self._on_mousewheel)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)
        self.matrix_frame.bind("<MouseWheel>", self._on_mousewheel)
        self.matrix_frame.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        self.matrix_frame.bind("<Button-4>", self._on_mousewheel)
        self.matrix_frame.bind("<Button-5>", self._on_mousewheel)

    def _on_matrix_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_header_configure(self, event=None):
        self.header_canvas.configure(scrollregion=self.header_canvas.bbox("all"))
        self._resize_header_canvas()

    def _on_header_canvas_configure(self, event):
        self._resize_header_canvas(event.width)

    def _resize_header_canvas(self, canvas_width=None):
        canvas_width = canvas_width or self.header_canvas.winfo_width()
        req_width = self.header_frame.winfo_reqwidth()
        req_height = max(self.header_frame.winfo_reqheight(), 1)
        self.header_canvas.itemconfigure(
            self.header_window,
            width=max(canvas_width, req_width),
            height=req_height,
        )
        self.header_canvas.configure(height=req_height)
        self.header_canvas.configure(scrollregion=self.header_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._resize_canvas_window(event.width, event.height)

    def _xview(self, *args):
        self.canvas.xview(*args)
        self.header_canvas.xview(*args)

    def _on_xscroll(self, first, last):
        self.h_scroll.set(first, last)
        self.header_canvas.xview_moveto(first)

    def _resize_canvas_window(self, canvas_width=None, canvas_height=None):
        canvas_width = canvas_width or self.canvas.winfo_width()
        canvas_height = canvas_height or self.canvas.winfo_height()
        self.canvas.itemconfigure(
            self.canvas_window,
            width=max(canvas_width, self.matrix_frame.winfo_reqwidth()),
            height=max(canvas_height, self.matrix_frame.winfo_reqheight()),
        )
        self._on_matrix_configure()

    def _on_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            self.canvas.yview_scroll(-3, "units")
        elif getattr(event, "num", None) == 5:
            self.canvas.yview_scroll(3, "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _on_shift_mousewheel(self, event):
        move = int(-10 * (event.delta / 120))
        self.canvas.xview_scroll(move, "units")
        self.header_canvas.xview_scroll(move, "units")
        return "break"

    def _close(self):
        self.destroy()

    def _bind_scroll_events(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        widget.bind("<Button-4>", self._on_mousewheel)
        widget.bind("<Button-5>", self._on_mousewheel)

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

        rows = db.get_payroll_rows_by_pay_date(self.conn, self.target_month, self.pay_date_applied)
        self.rows_data = [row for row in rows if self._row_matches_department_filter(row)]
        self.output_data_by_payroll_id = {}
        for row in self.rows_data:
            payroll_id = int(row["payroll_id"])
            try:
                self.output_data_by_payroll_id[payroll_id] = db.build_payroll_output_data(self.conn, row)
            except Exception:
                self.output_data_by_payroll_id[payroll_id] = {}

        if self.selected_employee_index is not None and self.selected_employee_index >= len(self.rows_data):
            self.selected_employee_index = None
        if self.selected_employee_index is None and self.rows_data:
            self.selected_employee_index = 0

        self._render_matrix(fmt_yen)

    def _render_matrix(self, fmt_yen):
        for child in self.header_frame.winfo_children():
            child.destroy()
        for child in self.matrix_frame.winfo_children():
            child.destroy()

        def row_def(source, key, title, is_money, row_kind="data", emphasis=False):
            return {
                "source": source,
                "key": key,
                "title": title,
                "is_money": is_money,
                "row_kind": row_kind,
                "emphasis": emphasis,
            }

        item_defs = [
            row_def("field", "department", "部署", False),
            row_def("separator", "pay", "", False, row_kind="separator"),
            *self._build_pay_item_defs(),
            row_def("output", "non_taxable_pay", "非課税支給額計", True, emphasis=True),
            row_def("output", "taxable_pay", "課税支給額計", True, emphasis=True),
            row_def("output", "total_pay", "支給金額合計", True, emphasis=True),
            row_def("separator", "deduction", "", False, row_kind="separator"),
            row_def("field", "emp_ins_employee", "雇用保険料", True),
            row_def("field", "health_care_display", "健康保険料", True),
            row_def("field", "childcare_support_employee", "子ども・子育て支援金", True),
            row_def("field", "pension_ins_employee", "厚生年金保険料", True),
            row_def("field", "social_ins_total_calc", "社会保険料合計", True, emphasis=True),
            row_def("field", "resident_tax_applied", "住民税", True),
            row_def("field", "withholding_tax_applied", "所得税", True),
            *self._build_deduction_item_defs(),
            row_def("output", "total_deduction", "控除合計額", True, emphasis=True),
            row_def("separator", "net", "", False, row_kind="separator"),
            row_def("output", "net_pay", "差引支給額", True, emphasis=True),
        ]

        corner_lbl = ttk.Label(
            self.header_frame,
            text="社員番号\n名前",
            anchor="center",
            justify="center",
            relief="solid",
            padding=4
        )
        corner_lbl.grid(row=0, column=0, sticky="nsew")
        self._bind_scroll_events(corner_lbl)

        self.employee_header_labels = []
        self.employee_value_widgets = []
        self.matrix_row_styles = []

        for col_idx, row in enumerate(self.rows_data, start=1):
            label_text = f'{row["employee_code"]}\n{row["name_kanji"]}'
            lbl = tk.Label(
                self.header_frame,
                text=label_text,
                relief="solid",
                borderwidth=1,
                padx=6,
                pady=6,
                bg="#d9edf7" if col_idx - 1 == self.selected_employee_index else "#f0f0f0",
            )
            lbl.grid(row=0, column=col_idx, sticky="nsew")
            lbl.bind("<Button-1>", lambda e, idx=col_idx - 1: self._set_selected_employee_index(idx))
            lbl.bind("<Double-1>", lambda e, idx=col_idx - 1: self._set_selected_employee_index(idx, open_editor=True))
            self._bind_scroll_events(lbl)
            self.employee_header_labels.append(lbl)

        for row_idx, item_def in enumerate(item_defs):
            source = item_def["source"]
            key = item_def["key"]
            title = item_def["title"]
            is_money = item_def["is_money"]
            row_kind = item_def["row_kind"]
            emphasis = item_def["emphasis"]
            if row_kind == "separator":
                sep_lbl = tk.Frame(self.matrix_frame, bg="#cbd5e1", height=2)
                sep_lbl.grid(row=row_idx, column=0, sticky="ew")
                self._bind_scroll_events(sep_lbl)

                line_widgets = []
                for col_idx, _row in enumerate(self.rows_data, start=1):
                    sep = tk.Frame(self.matrix_frame, bg="#cbd5e1", height=2)
                    sep.grid(row=row_idx, column=col_idx, sticky="ew")
                    self._bind_scroll_events(sep)
                    line_widgets.append(sep)
                self.employee_value_widgets.append(line_widgets)
                self.matrix_row_styles.append({"row_kind": row_kind, "emphasis": False, "bg": "#cbd5e1"})
                continue

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
            self._bind_scroll_events(title_lbl)

            line_widgets = []
            for col_idx, row in enumerate(self.rows_data, start=1):
                value = self._matrix_value(row, source, key)

                if value is None:
                    value = ""
                if is_money and value != "":
                    value = fmt_yen(value)

                lbl = tk.Label(
                    self.matrix_frame,
                    text=value,
                    relief="flat",
                    borderwidth=0,
                    highlightthickness=1,
                    highlightbackground="#e5e7eb",
                    padx=6,
                    pady=4,
                    anchor="e" if is_money else "w",
                    justify="left",
                    bg=value_bg,
                    font=font,
                )
                lbl.grid(row=row_idx, column=col_idx, sticky="nsew")
                lbl.bind("<Button-1>", lambda e, idx=col_idx - 1: self._set_selected_employee_index(idx))
                lbl.bind("<Double-1>", lambda e, idx=col_idx - 1: self._set_selected_employee_index(idx, open_editor=True))
                self._bind_scroll_events(lbl)
                line_widgets.append(lbl)
            self.employee_value_widgets.append(line_widgets)
            self.matrix_row_styles.append({"row_kind": row_kind, "emphasis": emphasis, "bg": value_bg})

        self.matrix_frame.grid_columnconfigure(0, weight=0, minsize=170)
        self.header_frame.grid_columnconfigure(0, weight=0, minsize=170)
        for col_idx in range(1, len(self.rows_data) + 1):
            self.matrix_frame.grid_columnconfigure(col_idx, weight=0, minsize=130)
            self.header_frame.grid_columnconfigure(col_idx, weight=0, minsize=130)

        self._apply_selection_highlight()
        self.header_frame.update_idletasks()
        self.matrix_frame.update_idletasks()
        self._resize_header_canvas()
        self._resize_canvas_window()

    def _build_pay_item_defs(self):
        seen = {}
        hidden_codes = {f"pay_free{i}" for i in range(1, 6)}
        hidden_names = {f"支給自由{i}" for i in range(1, 6)}
        for row in self.rows_data:
            output = self.output_data_by_payroll_id.get(int(row["payroll_id"]), {})
            for item in output.get("pay_items", []) or []:
                code = str(item.get("code") or "")
                name = str(item.get("name") or "")
                if code in hidden_codes or name in hidden_names:
                    continue
                item_key = item.get("item_id") or item.get("code") or item.get("name")
                if item_key not in seen:
                    seen[item_key] = {
                        "key": item_key,
                        "name": name,
                        "display_order": int(item.get("display_order") or 0),
                    }
        return [
            {
                "source": "pay_item",
                "key": item["key"],
                "title": item["name"],
                "is_money": True,
                "row_kind": "data",
                "emphasis": False,
            }
            for item in sorted(seen.values(), key=lambda x: (x["display_order"], x["name"]))
        ]

    def _build_deduction_item_defs(self):
        seen = {}
        hidden_codes = {"travel_saving"} | {f"deduct_free{i}" for i in range(1, 6)}
        hidden_names = {"旅行積立", "旅行積立金"} | {f"控除自由{i}" for i in range(1, 6)}
        for row in self.rows_data:
            output = self.output_data_by_payroll_id.get(int(row["payroll_id"]), {})
            for item in output.get("deduction_items", []) or []:
                code = str(item.get("code") or "")
                name = str(item.get("name") or "")
                if code in hidden_codes or name in hidden_names:
                    continue
                item_key = item.get("item_id") or item.get("code") or item.get("name")
                if item_key not in seen:
                    seen[item_key] = {
                        "key": item_key,
                        "name": name,
                        "display_order": int(item.get("display_order") or 0),
                    }
        return [
            {
                "source": "deduction_item",
                "key": item["key"],
                "title": item["name"],
                "is_money": True,
                "row_kind": "data",
                "emphasis": False,
            }
            for item in sorted(seen.values(), key=lambda x: (x["display_order"], x["name"]))
        ]

    def _matrix_value(self, row, source, key):
        if source == "field":
            if key == "health_care_display":
                return int(row["health_ins_employee"] or 0) + int(row["care_ins_employee"] or 0)
            return row[key] if key in row.keys() else ""
        if source == "separator":
            return ""

        output = self.output_data_by_payroll_id.get(int(row["payroll_id"]), {})
        if source == "output":
            return output.get(key, row[key] if key in row.keys() else "")
        if source == "pay_item":
            for item in output.get("pay_items", []) or []:
                item_key = item.get("item_id") or item.get("code") or item.get("name")
                if item_key == key:
                    return item.get("amount", 0)
            return 0
        if source == "deduction_item":
            for item in output.get("deduction_items", []) or []:
                item_key = item.get("item_id") or item.get("code") or item.get("name")
                if item_key == key:
                    return item.get("amount", 0)
            return 0
        return ""

    def _apply_selection_highlight(self):
        for idx, lbl in enumerate(self.employee_header_labels):
            lbl.configure(bg="#d9edf7" if idx == self.selected_employee_index else "#f0f0f0")

        for row_idx, line_widgets in enumerate(self.employee_value_widgets):
            style = self.matrix_row_styles[row_idx] if row_idx < len(self.matrix_row_styles) else {}
            row_kind = style.get("row_kind")
            emphasis = style.get("emphasis")
            default_bg = style.get("bg", "white")
            for idx, lbl in enumerate(line_widgets):
                if row_kind == "separator":
                    lbl.configure(bg=default_bg)
                elif idx == self.selected_employee_index:
                    lbl.configure(bg="#fcf8e3")
                else:
                    lbl.configure(bg=default_bg)
 
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

        dlg = PayrollEditorDialog(self, self.conn, payroll_id)
        self.wait_window(dlg)
        self.refresh()

    def add_missing_employees(self):
        missing = self._missing_employees_for_this_pay_date()
        if not missing:
            messagebox.showinfo("確認", "この支払日に追加できる未計算社員はいません。")
            return

        preview = "\n".join(f"- {e['employee_code']} {e['name_kanji']}" for e, _ in missing[:10])
        if len(missing) > 10:
            preview += f"\n...ほか {len(missing) - 10} 名"
        ok = messagebox.askyesno(
            "未計算社員の追加",
            f"以下の未計算社員を追加します。\n\n{preview}\n\nよろしいですか？",
        )
        if not ok:
            return

        month_info = parse_month(self.target_month)
        cur = self.conn.cursor()
        for employee, pay_date in missing:
            cur.execute(
                """
                INSERT OR IGNORE INTO payroll_monthly(
                  target_month, employee_id,
                  wage_period_start, wage_period_end,
                  pay_date_auto, pay_date_applied
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    self.target_month,
                    int(employee["employee_id"]),
                    month_info.start.isoformat(),
                    month_info.end.isoformat(),
                    pay_date,
                    pay_date,
                ),
            )
        self.conn.commit()

        try:
            db.recalc_target_month(self.conn, self.target_month)
        except Exception as e:
            messagebox.showwarning("自動計算", f"追加後の自動計算でエラーが発生しました。\n\n詳細: {e}")

        if self.master is not None and hasattr(self.master, "refresh"):
            try:
                self.master.refresh()
            except Exception:
                pass
        self.refresh()
        messagebox.showinfo("完了", f"{len(missing)} 名を追加しました。")

    def _missing_employees_for_this_pay_date(self):
        existing_employee_ids = {
            int(row[0])
            for row in self.conn.execute(
                "SELECT employee_id FROM payroll_monthly WHERE target_month = ?",
                (self.target_month,),
            ).fetchall()
        }
        missing = []
        filter_ids = self._department_filter_ids()
        for employee in db.list_employees(self.conn):
            employee_id = int(employee["employee_id"])
            if employee_id in existing_employee_ids:
                continue
            if filter_ids is not None:
                try:
                    employee_dept_id = int(employee["department_id"] or 0)
                except Exception:
                    employee_dept_id = 0
                if employee_dept_id not in filter_ids:
                    continue
            pay_date = self._calc_employee_pay_date(employee)
            if pay_date == self.pay_date_applied:
                missing.append((employee, pay_date))
        return missing

    def _calc_employee_pay_date(self, employee):
        schedule_id = employee["payment_schedule_id"] if "payment_schedule_id" in employee.keys() else None
        if schedule_id:
            schedule = db.get_payment_schedule_by_id(self.conn, int(schedule_id))
            if schedule:
                return db.calc_pay_date(
                    self.target_month,
                    schedule["closing_mode"],
                    int(schedule["pay_day"]),
                )

        payday_day = int(employee["payday_group"] or 0)
        return compute_pay_date(self.target_month, payday_day).isoformat()

    def override_paydate(self):
        payroll_id = self._selected_payroll_id()
        if not payroll_id:
            messagebox.showinfo("確認", "対象社員を選択してください。")
            return

        override = simpledialog.askstring(
            "支払日上書き",
            "上書きする支払日（yyyy-mm-dd）を入力。\n空欄を入力したい場合はキャンセル後に解除を選んでください。",
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
