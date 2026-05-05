import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

import db
from ui_window_utils import enable_enter_key_navigation


def _to_int(value: str) -> int:
    text = (value or "").strip().replace(",", "")
    if text == "":
        return 0
    if not text.isdigit():
        raise ValueError(f"金額は0以上の整数で入力してください: {value}")
    return int(text)


def _format_amount(value: int | str | None, *, blank_if_empty: bool = False) -> str:
    text = ("" if value is None else str(value)).strip()
    if text == "" and blank_if_empty:
        return ""
    return f"{_to_int(text):,}"


def _parse_month(value: str) -> tuple[int, int]:
    text = (value or "").strip()
    parts = text.split("-")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError("年月は yyyy-mm 形式で入力してください。")
    year = int(parts[0])
    month = int(parts[1])
    if month < 1 or month > 12:
        raise ValueError("月は01から12で入力してください。")
    return year, month


def _month_range(start_month: str, end_month: str) -> list[str]:
    y, m = _parse_month(start_month)
    ey, em = _parse_month(end_month)
    if (y, m) > (ey, em):
        raise ValueError("開始対象月は終了対象月以前にしてください。")
    months = []
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return months


class ResidentTaxAnnualFrame(ttk.Frame):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self.months = []
        self.employees = []
        self.amount_vars = {}
        self.total_vars = {}
        self.row_widgets = {}
        self.selected_employee_id = None
        self.sort_key = None
        self.sort_desc = False

        current_year = date.today().year
        self.var_year = tk.StringVar(value=str(current_year))
        self.var_start_month = tk.StringVar(value=f"{current_year:04d}-06")
        self.var_end_month = tk.StringVar(value=f"{current_year + 1:04d}-05")
        self.var_june_amount = tk.StringVar(value="")
        self.var_rest_amount = tk.StringVar(value="")

        self._build_controls()
        self._build_grid()
        self._build_footer()
        self.load()
        enable_enter_key_navigation(self)

    def _build_controls(self):
        top = ttk.LabelFrame(self, text="対象期間")
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="年度").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ent_year = ttk.Entry(top, textvariable=self.var_year, width=8)
        ent_year.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ent_year.bind("<FocusOut>", lambda event: self._sync_months_from_year())

        ttk.Label(top, text="開始対象月").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Entry(top, textvariable=self.var_start_month, width=10).grid(row=0, column=3, padx=5, pady=5, sticky="w")
        ttk.Label(top, text="終了対象月").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        ttk.Entry(top, textvariable=self.var_end_month, width=10).grid(row=0, column=5, padx=5, pady=5, sticky="w")

        ttk.Button(top, text="表示", command=self.load).grid(row=0, column=6, padx=5, pady=5)
        ttk.Button(top, text="保存", command=self.save).grid(row=0, column=7, padx=5, pady=5)
        ttk.Button(top, text="給与へ反映", command=self.apply_to_monthly).grid(row=0, column=8, padx=5, pady=5)

        helper = ttk.LabelFrame(self, text="入力補助")
        helper.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(helper, text="6月分").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ent_june = ttk.Entry(helper, textvariable=self.var_june_amount, width=12, justify="right")
        ent_june.grid(row=0, column=1, padx=5, pady=5)
        ent_june.bind("<FocusOut>", lambda event: self._format_amount_var(self.var_june_amount, blank_if_empty=True))
        ttk.Label(helper, text="7月〜翌5月分").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ent_rest = ttk.Entry(helper, textvariable=self.var_rest_amount, width=12, justify="right")
        ent_rest.grid(row=0, column=3, padx=5, pady=5)
        ent_rest.bind("<FocusOut>", lambda event: self._format_amount_var(self.var_rest_amount, blank_if_empty=True))
        ttk.Button(helper, text="選択社員へ適用", command=self.expand_selected).grid(row=0, column=4, padx=5, pady=5)

    def _build_grid(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.canvas = tk.Canvas(body, highlightthickness=0)
        self.v_scroll = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(body, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")
        self.h_scroll.grid(row=1, column=0, sticky="ew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self.grid_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", self._on_grid_configure)
        self._bind_scroll_events(self.grid_frame)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_scroll_events(self.canvas)

    def _build_footer(self):
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(footer, text="閉じる", command=self._close_window).pack(side="right")

    def _close_window(self):
        self.winfo_toplevel().destroy()

    def _bind_scroll_events(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        widget.bind("<Control-MouseWheel>", self._on_shift_mousewheel)
        widget.bind("<Button-4>", self._on_mousewheel)
        widget.bind("<Button-5>", self._on_mousewheel)

    def _on_grid_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(
            self.canvas_window,
            width=max(event.width, self.grid_frame.winfo_reqwidth()),
            height=max(event.height, self.grid_frame.winfo_reqheight()),
        )
        self._on_grid_configure()

    def _on_mousewheel(self, event):
        if getattr(event, "state", 0) & 0x0005:
            return self._on_shift_mousewheel(event)
        if getattr(event, "num", None) == 4:
            units = -3
        elif getattr(event, "num", None) == 5:
            units = 3
        else:
            units = int(-3 * (event.delta / 120))
        self.canvas.yview_scroll(units, "units")
        return "break"

    def _on_shift_mousewheel(self, event):
        units = int(-10 * (event.delta / 120))
        self.canvas.xview_scroll(units, "units")
        return "break"

    def _format_amount_var(self, var: tk.StringVar, *, blank_if_empty: bool = False):
        try:
            var.set(_format_amount(var.get(), blank_if_empty=blank_if_empty))
        except ValueError:
            pass

    def _sync_months_from_year(self):
        year_text = (self.var_year.get() or "").strip()
        if year_text.isdigit() and len(year_text) == 4:
            year = int(year_text)
            self.var_start_month.set(f"{year:04d}-06")
            self.var_end_month.set(f"{year + 1:04d}-05")

    def _load_employees(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT e.employee_id, e.employee_code, e.name_kanji,
                   COALESCE(e.address_city, '') AS address_city
            FROM employees e
            WHERE COALESCE(e.is_deleted, 0) = 0
            ORDER BY e.employee_id
            """
        )
        self.employees = cur.fetchall()

    def _sort_employees(self):
        if not self.sort_key:
            return
        if self.sort_key == "annual_total":
            current_values = self._capture_amount_values()

            def total_for_employee(row):
                employee_id = int(row["employee_id"])
                total = 0
                for month in self.months:
                    try:
                        total += _to_int(current_values.get((employee_id, month), "0"))
                    except ValueError:
                        pass
                return total

            self.employees = sorted(self.employees, key=total_for_employee, reverse=self.sort_desc)
            return
        self.employees = sorted(
            self.employees,
            key=lambda r: str(r[self.sort_key] or ""),
            reverse=self.sort_desc,
        )

    def _capture_amount_values(self):
        values = {}
        for employee_id, month_vars in self.amount_vars.items():
            for month, var in month_vars.items():
                values[(employee_id, month)] = var.get()
        return values

    def _sort_by(self, key: str):
        current_values = self._capture_amount_values()
        if self.sort_key == key:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_key = key
            self.sort_desc = False
        self._sort_employees()
        self._render_table(current_values)

    def load(self):
        try:
            self.months = _month_range(self.var_start_month.get(), self.var_end_month.get())
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            return
        self._load_employees()
        self._sort_employees()
        self._render_table()

    def _direct_amount_map(self):
        if not self.months:
            return {}
        rows = db.list_resident_tax_for_period(self.conn, self.months[0], self.months[-1])
        return {(int(r["employee_id"]), r["start_month"]): int(r["amount"] or 0) for r in rows}

    def _render_table(self, value_overrides=None):
        for child in self.grid_frame.winfo_children():
            child.destroy()
        self.amount_vars = {}
        self.total_vars = {}
        self.row_widgets = {}
        amount_map = self._direct_amount_map()
        value_overrides = value_overrides or {}

        headers = [
            ("社員コード", "employee_code"),
            ("氏名", "name_kanji"),
            ("市区町村", "address_city"),
            ("合計金額", "annual_total"),
        ]
        month_headers = [f"{int(m.split('-')[1])}月" for m in self.months]
        for col, (title, sort_key) in enumerate(headers):
            label = ttk.Label(self.grid_frame, text=title, relief="solid", padding=4, anchor="center")
            label.grid(row=0, column=col, sticky="nsew")
            label.bind("<Button-1>", lambda event, key=sort_key: self._sort_by(key))
            label.bind("<Enter>", lambda event, w=label: w.configure(background="#dff1ff", cursor="hand2"))
            label.bind("<Leave>", lambda event, w=label: w.configure(background="SystemButtonFace", cursor=""))
            self._bind_scroll_events(label)
        for col, title in enumerate(month_headers, start=len(headers)):
            label = ttk.Label(self.grid_frame, text=title, relief="solid", padding=4, anchor="center")
            label.grid(row=0, column=col, sticky="nsew")
            self._bind_scroll_events(label)

        for row_idx, employee in enumerate(self.employees, start=1):
            employee_id = int(employee["employee_id"])
            values = [
                employee["employee_code"],
                employee["name_kanji"],
                employee["address_city"],
            ]
            for col, value in enumerate(values):
                label = ttk.Label(self.grid_frame, text=value or "", relief="solid", padding=4)
                label.grid(row=row_idx, column=col, sticky="nsew")
                label.bind("<Button-1>", lambda event, eid=employee_id: self._select_employee(eid))
                self._bind_scroll_events(label)
                self._add_row_widget(employee_id, label)

            self.amount_vars[employee_id] = {}
            total_var = tk.StringVar(value="0")
            self.total_vars[employee_id] = total_var
            total_label = ttk.Label(self.grid_frame, textvariable=total_var, relief="solid", padding=4, anchor="e")
            total_label.grid(row=row_idx, column=3, sticky="nsew")
            total_label.bind("<Button-1>", lambda event, eid=employee_id: self._select_employee(eid))
            self._bind_scroll_events(total_label)
            self._add_row_widget(employee_id, total_label)
            for offset, month in enumerate(self.months):
                override = value_overrides.get((employee_id, month))
                raw_amount = amount_map.get((employee_id, month))
                value = override if override is not None else ("" if raw_amount is None else _format_amount(raw_amount))
                var = tk.StringVar(value=value)
                ent = tk.Entry(self.grid_frame, textvariable=var, width=10, justify="right", relief="solid", bd=1)
                ent.grid(row=row_idx, column=4 + offset, sticky="nsew", padx=1, pady=1)
                ent.bind("<FocusIn>", lambda event, eid=employee_id: self._select_employee(eid))
                ent.bind("<FocusOut>", lambda event, eid=employee_id, v=var: self._on_amount_focus_out(eid, v))
                ent.bind("<KeyRelease>", lambda event, eid=employee_id: self._update_employee_total(eid))
                self._bind_scroll_events(ent)
                self._add_row_widget(employee_id, ent)
                self.amount_vars[employee_id][month] = var

            self._update_employee_total(employee_id)
        widths = {0: 80, 1: 90, 2: 100, 3: 70}
        for col in range(4 + len(self.months)):
            self.grid_frame.grid_columnconfigure(col, weight=0, minsize=widths.get(col, 45))
        self.grid_frame.update_idletasks()
        self._refresh_selected_row()
        enable_enter_key_navigation(self.grid_frame)
        self._on_grid_configure()

    def _add_row_widget(self, employee_id: int, widget):
        self.row_widgets.setdefault(employee_id, []).append(widget)

    def _refresh_selected_row(self):
        selected_bg = "#fff3c4"
        normal_bg = "white"
        for employee_id, widgets in self.row_widgets.items():
            bg = selected_bg if employee_id == self.selected_employee_id else normal_bg
            for widget in widgets:
                try:
                    widget.configure(background=bg)
                    if isinstance(widget, tk.Entry):
                        widget.configure(readonlybackground=bg)
                except tk.TclError:
                    pass

    def _on_amount_focus_out(self, employee_id: int, var: tk.StringVar):
        self._format_amount_var(var, blank_if_empty=True)
        self._update_employee_total(employee_id)

    def _update_employee_total(self, employee_id: int):
        total = 0
        for var in self.amount_vars.get(employee_id, {}).values():
            try:
                total += _to_int(var.get())
            except ValueError:
                pass
        total_var = self.total_vars.get(employee_id)
        if total_var:
            total_var.set(f"{total:,}")

    def _select_employee(self, employee_id: int):
        self.selected_employee_id = employee_id
        self._refresh_selected_row()

    def _expand_to_employee(self, employee_id: int, june_amount: int, rest_amount: int):
        if employee_id not in self.amount_vars:
            return
        for idx, month in enumerate(self.months):
            self.amount_vars[employee_id][month].set(_format_amount(june_amount if idx == 0 else rest_amount))
        self._update_employee_total(employee_id)

    def expand_selected(self):
        if self.selected_employee_id is None:
            messagebox.showinfo("確認", "対象社員を選択してください。")
            return
        try:
            june_amount = _to_int(self.var_june_amount.get())
            rest_amount = _to_int(self.var_rest_amount.get())
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            return
        self._expand_to_employee(self.selected_employee_id, june_amount, rest_amount)

    def save(self):
        try:
            note = f"{self.var_year.get()}年度住民税"
            for employee_id, month_vars in self.amount_vars.items():
                values = {month: _to_int(var.get()) for month, var in month_vars.items()}
                db.upsert_resident_tax_annual_values(self.conn, employee_id, values, note)
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            return
        for month_vars in self.amount_vars.values():
            for var in month_vars.values():
                self._format_amount_var(var, blank_if_empty=True)
        for employee_id in self.amount_vars:
            self._update_employee_total(employee_id)
        messagebox.showinfo("保存完了", "住民税年度通知額を保存しました。")

    def apply_to_monthly(self):
        if not self.months:
            messagebox.showinfo("確認", "対象期間を表示してください。")
            return
        db.apply_resident_tax_auto_for_period(self.conn, self.months[0], self.months[-1])
        messagebox.showinfo("反映完了", "対象期間の給与へ住民税を反映しました。")
