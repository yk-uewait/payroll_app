import tkinter as tk
import re
from tkinter import ttk, messagebox

import app_settings
from ui_window_utils import apply_safe_geometry, show_centered_window, enable_enter_key_navigation


def _to_int(s: str) -> int:
    text = (s or "").strip().replace(",", "")
    if text == "":
        return 0
    try:
        return int(text)
    except ValueError:
        raise ValueError(f"金額は整数で入力してください: {s}")


def _format_amount(value) -> str:
    try:
        return f"{int(value or 0):,}"
    except Exception:
        return "0"


def _format_year_month(value: str) -> str:
    try:
        year, month = str(value).split("-", 1)
        return f"{int(year):04d} 年 {int(month):02d} 月"
    except Exception:
        return str(value or "")


def _remove_commas(var: tk.StringVar):
    var.set((var.get() or "").replace(",", ""))


def _format_amount_var(var: tk.StringVar, on_change=None):
    try:
        var.set(_format_amount(_to_int(var.get())))
    except ValueError:
        return
    if callable(on_change):
        on_change()


def _resident_tax_fiscal_year(target_month: str) -> int:
    year_text, month_text = str(target_month).split("-", 1)
    year = int(year_text)
    month = int(month_text)
    return year if month >= 6 else year - 1


class WithholdingOverrideDialog(tk.Toplevel):
    def __init__(self, parent, conn, payroll_id: int, row, on_changed=None):
        super().__init__(parent)
        self.withdraw()
        self.conn = conn
        self.payroll_id = payroll_id
        self.row = row
        self.on_changed = on_changed

        self.title("所得税 上書き")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.var_auto = tk.StringVar(value=_format_amount(row["withholding_tax_auto"] if "withholding_tax_auto" in row.keys() else 0))
        override = row["withholding_tax_override"] if "withholding_tax_override" in row.keys() else None
        self.var_override = tk.StringVar(value="" if override is None else _format_amount(override))
        self.var_reason = tk.StringVar(
            value=row["withholding_tax_override_reason"]
            if "withholding_tax_override_reason" in row.keys() and row["withholding_tax_override_reason"]
            else ""
        )
        self.var_applied = tk.StringVar(value=_format_amount(row["withholding_tax_applied"] if "withholding_tax_applied" in row.keys() else 0))

        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)

        rows = [
            ("自動計算額", self.var_auto, "readonly"),
            ("上書き額", self.var_override, "normal"),
            ("適用額", self.var_applied, "readonly"),
        ]
        for idx, (label, var, state) in enumerate(rows):
            ttk.Label(frm, text=label).grid(row=idx, column=0, padx=5, pady=5, sticky="w")
            ent = ttk.Entry(frm, textvariable=var, width=18, justify="right", state=state)
            ent.grid(row=idx, column=1, padx=5, pady=5, sticky="w")
            ttk.Label(frm, text="円").grid(row=idx, column=2, padx=5, pady=5, sticky="w")
            if state == "normal":
                self._bind_money_entry(ent, var)

        ttk.Label(frm, text="上書き理由").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_reason, width=36).grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=3, padx=5, pady=(12, 0), sticky="e")
        ttk.Button(btns, text="上書きを保存", command=self.save_override).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="上書きを解除", command=self.clear_override).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")

        self.bind("<Escape>", lambda event: self.close())
        enable_enter_key_navigation(self)
        show_centered_window(self, parent)
        self.after(10, self.focus_force)

    def _bind_money_entry(self, entry, var: tk.StringVar):
        entry.bind("<FocusIn>", lambda event: ( _remove_commas(var), event.widget.select_range(0, "end") ))
        entry.bind("<FocusOut>", lambda event: self._refresh_override_preview())
        entry.bind("<KeyRelease>", lambda event: self._refresh_override_preview(format_input=False))

    def _refresh_override_preview(self, format_input=True):
        text = (self.var_override.get() or "").strip()
        if text == "":
            self.var_applied.set(self.var_auto.get())
            return
        try:
            amount = _to_int(text)
        except ValueError:
            return
        if format_input:
            self.var_override.set(_format_amount(amount))
        self.var_applied.set(_format_amount(amount))

    def save_override(self):
        try:
            amount = _to_int(self.var_override.get())
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e), parent=self)
            return

        import db

        db.override_withholding_tax(self.conn, self.payroll_id, amount, self.var_reason.get().strip() or None)
        if callable(self.on_changed):
            self.on_changed()
        self.close()

    def clear_override(self):
        import db

        db.override_withholding_tax(self.conn, self.payroll_id, None, None)
        if callable(self.on_changed):
            self.on_changed()
        self.close()

    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class PayrollEditorDialog(tk.Toplevel):
    def __init__(self, master, conn, payroll_id: int):
        super().__init__(master)
        self.withdraw()
        self.conn = conn
        self.payroll_id = payroll_id
        self.dynamic_item_vars = {}
        self.dynamic_item_sources = {}
        self.attendance_vars = {}
        self.money_entries = []
        self.scroll_canvases = []

        self.title("支給控除金額の編集")
        self.geometry(app_settings.get_window_geometry("payroll_editor"))
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._load_row()
        if not self.row:
            messagebox.showerror("エラー", "対象データが見つかりません。", parent=self)
            self.destroy()
            return

        self._build_header()
        self._build_body()
        self._build_net_total()
        self._build_note()
        self._build_footer()

        self._update_totals()
        self._saved_snapshot = self._current_snapshot()
        enable_enter_key_navigation(self)
        show_centered_window(self, master)

    def _load_row(self):
        import db

        self.row = db.get_payroll_by_id(self.conn, self.payroll_id)
        self.attendance_time_mode = db.get_attendance_time_input_mode(self.conn)

    def _row_value(self, key: str, default=0):
        return self.row[key] if key in self.row.keys() and self.row[key] is not None else default

    def _build_header(self):
        header = ttk.LabelFrame(self, text="対象")
        header.pack(fill="x", padx=10, pady=10)

        values = [
            ("対象年月", _format_year_month(self._row_value("target_month", ""))),
            ("社員番号", self._row_value("employee_code", "")),
            ("社員名", self._row_value("name_kanji", "")),
            ("部署", self._row_value("department", "")),
            ("役職", self._row_value("position_name", "")),
            ("雇用区分", self._row_value("employment_type_name", "")),
        ]
        for idx, (label, value) in enumerate(values):
            ttk.Label(header, text=f"{label}: {value or ''}").grid(
                row=0,
                column=idx,
                padx=6,
                pady=4,
                sticky="w",
            )
            header.grid_columnconfigure(idx, weight=1)

    def _build_body(self):
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=0)
        body.grid_rowconfigure(0, weight=1)

        pay_area = ttk.LabelFrame(body, text="支給")
        pay_area.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        deduct_area = ttk.LabelFrame(body, text="控除")
        deduct_area.grid(row=0, column=1, sticky="nsew", padx=5)
        attendance_area = ttk.LabelFrame(body, text="勤怠")
        attendance_area.grid(row=0, column=2, sticky="nsew", padx=(5, 0))

        self.pay_inner = self._create_scrollable_area(pay_area)
        pay_canvas = self.scroll_canvases[-1]
        self.deduct_inner = self._create_scrollable_area(deduct_area)
        deduct_canvas = self.scroll_canvases[-1]
        self.attendance_inner = self._create_scrollable_area(attendance_area, width=240)
        attendance_canvas = self.scroll_canvases[-1]

        self._build_dynamic_items(self.pay_inner, "pay")
        self._build_system_deductions(self.deduct_inner)
        ttk.Separator(self.deduct_inner).grid(row=20, column=0, columnspan=3, sticky="ew", padx=5, pady=8)
        self._build_dynamic_items(self.deduct_inner, "deduction", start_row=21)
        self._build_attendance_items(self.attendance_inner)
        self._bind_scroll_recursive(self.pay_inner, pay_canvas)
        self._bind_scroll_recursive(self.deduct_inner, deduct_canvas)
        self._bind_scroll_recursive(self.attendance_inner, attendance_canvas)

        pay_total_frame = ttk.Frame(pay_area)
        pay_total_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(6, 8))
        self.lbl_total_pay = ttk.Label(pay_total_frame, text="支給合計: 0 円", font=("", 10, "bold"))
        self.lbl_total_pay.pack(side="right")

        deduct_total_frame = ttk.Frame(deduct_area)
        deduct_total_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(6, 8))
        self.lbl_total_deduct = ttk.Label(deduct_total_frame, text="控除合計: 0 円", font=("", 10, "bold"))
        self.lbl_total_deduct.pack(side="right")

    def _create_scrollable_area(self, parent, width=None):
        canvas = tk.Canvas(parent, highlightthickness=0, width=width)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        inner.bind("<Configure>", lambda event, c=canvas, s=scrollbar: self._sync_scroll_area(c, s))
        canvas.bind("<Configure>", lambda event, c=canvas, s=scrollbar, w=window_id: self._on_scroll_canvas_configure(c, s, w, event))
        self._bind_scroll_recursive(inner, canvas)
        canvas.bind("<MouseWheel>", lambda event, c=canvas: self._scroll_canvas(c, event), add="+")
        canvas.bind("<Button-4>", lambda event, c=canvas: self._scroll_canvas(c, event), add="+")
        canvas.bind("<Button-5>", lambda event, c=canvas: self._scroll_canvas(c, event), add="+")
        self.scroll_canvases.append(canvas)
        return inner

    def _on_scroll_canvas_configure(self, canvas, scrollbar, window_id, event):
        canvas.itemconfigure(window_id, width=event.width)
        self._sync_scroll_area(canvas, scrollbar)

    def _sync_scroll_area(self, canvas, scrollbar):
        canvas.configure(scrollregion=canvas.bbox("all"))
        if self._canvas_needs_vertical_scroll(canvas):
            if not scrollbar.winfo_ismapped():
                scrollbar.grid(row=0, column=1, sticky="ns")
        else:
            canvas.yview_moveto(0)
            scrollbar.grid_remove()

    def _canvas_needs_vertical_scroll(self, canvas) -> bool:
        bbox = canvas.bbox("all")
        if not bbox:
            return False
        content_height = max(0, bbox[3] - bbox[1])
        visible_height = max(0, canvas.winfo_height())
        return content_height > visible_height + 1

    def _bind_scroll_recursive(self, widget, canvas):
        widget.bind("<MouseWheel>", lambda event, c=canvas: self._scroll_canvas(c, event), add="+")
        widget.bind("<Button-4>", lambda event, c=canvas: self._scroll_canvas(c, event), add="+")
        widget.bind("<Button-5>", lambda event, c=canvas: self._scroll_canvas(c, event), add="+")
        for child in widget.winfo_children():
            self._bind_scroll_recursive(child, canvas)

    def _scroll_canvas(self, canvas, event):
        if not self._canvas_needs_vertical_scroll(canvas):
            canvas.yview_moveto(0)
            return "break"
        if getattr(event, "num", None) == 4:
            canvas.yview_scroll(-3, "units")
        elif getattr(event, "num", None) == 5:
            canvas.yview_scroll(3, "units")
        else:
            canvas.yview_scroll(int(-3 * (event.delta / 120)), "units")
        return "break"

    def _bind_money_entry(self, entry, var: tk.StringVar):
        entry.bind("<FocusIn>", lambda event: (_remove_commas(var), event.widget.select_range(0, "end")))
        entry.bind("<FocusOut>", lambda event: _format_amount_var(var, self._update_totals))
        entry.bind("<KeyRelease>", lambda event: self._update_totals())
        self.money_entries.append(entry)

    def _build_dynamic_items(self, parent, item_kind: str, start_row: int = 0):
        import db

        items = [
            r
            for r in db.get_applicable_payroll_items(self.conn, int(self.row["employee_id"]))
            if r["item_kind"] == item_kind
        ]
        saved_map = db.get_payroll_monthly_item_value_map(self.conn, self.payroll_id)
        target_month = self.row["target_month"]

        if not items:
            item_label = "支給項目" if item_kind == "pay" else "控除項目"
            message = f"{item_label}を追加したい場合は、「支給控除マスタ（中分類）」より項目の登録を行ってください。"
            if item_kind == "deduction":
                message = "追加項目を追加したい場合は、\n「支給控除マスタ（中分類）」より\n項目の登録を行ってください。"
            ttk.Label(
                parent,
                text=message,
                wraplength=220,
                justify="left",
            ).grid(row=start_row, column=0, columnspan=3, padx=(12, 5), pady=5, sticky="w")
            return

        for idx, item in enumerate(items, start=start_row):
            item_id = int(item["id"])
            saved = saved_map.get(item_id)
            source = "standard"
            locked = False
            if saved:
                amount = int(saved["amount"] or 0)
                source = saved["source"] or "manual"
                locked = bool(int(saved["is_locked"] or 0))
            else:
                amount = db.get_employee_standard_amount(self.conn, int(self.row["employee_id"]), item_id, target_month)
                if amount == 0 and item["code"] in {"officer_pay", "base_salary", "overtime_pay", "commute_nontax"}:
                    amount = int(self._row_value(item["code"], 0) or 0)

            ttk.Label(parent, text=item["name"]).grid(row=idx, column=0, padx=(12, 5), pady=4, sticky="w")
            var = tk.StringVar(value=_format_amount(amount))
            ent = ttk.Entry(parent, textvariable=var, width=16, justify="right")
            ent.grid(row=idx, column=1, padx=(5, 4), pady=4, sticky="w")
            ttk.Label(parent, text="円").grid(row=idx, column=2, padx=(0, 12), pady=4, sticky="w")
            if locked:
                ent.configure(state="disabled")
            else:
                self._bind_money_entry(ent, var)
            var.trace_add("write", lambda *_: self._update_totals())
            self.dynamic_item_vars[item_id] = var
            self.dynamic_item_sources[item_id] = {"item": item, "source": source, "locked": locked, "entry": ent}

        parent.grid_columnconfigure(0, weight=1)

    def _system_amount(self, key: str) -> int:
        return int(self._row_value(key, 0) or 0)

    def _build_system_deductions(self, parent):
        self.system_amount_vars = {}
        rows = [
            ("健康保険料", "health_ins_employee", None),
            ("介護保険料", "care_ins_employee", None),
            ("子ども・子育て支援金", "childcare_support_employee", None),
            ("厚生年金保険料", "pension_ins_employee", None),
            ("雇用保険料", "emp_ins_employee", None),
            ("所得税", "withholding_tax_applied", self.open_withholding_override),
            ("住民税", "resident_tax_applied", self.open_resident_tax_annual),
        ]
        for idx, (label, key, command) in enumerate(rows, start=0):
            if command:
                ttk.Button(parent, text=label, command=command, width=9).grid(row=idx, column=0, padx=(12, 5), pady=4, sticky="w")
            else:
                ttk.Label(parent, text=label).grid(row=idx, column=0, padx=(12, 5), pady=4, sticky="w")
            var = tk.StringVar(value=_format_amount(self._system_amount(key)))
            self.system_amount_vars[key] = var
            ttk.Label(parent, textvariable=var, anchor="e", width=16).grid(row=idx, column=1, padx=(5, 4), pady=4, sticky="w")
            ttk.Label(parent, text="円").grid(row=idx, column=2, padx=(0, 12), pady=4, sticky="w")
        parent.grid_columnconfigure(0, weight=0)
        parent.grid_columnconfigure(1, weight=0)

    def _format_attendance_day(self, value) -> str:
        try:
            number = float(value or 0)
            return str(int(number)) if number.is_integer() else f"{number:g}"
        except Exception:
            return "0"

    def _format_attendance_input(self, key: str, value) -> str:
        import db

        if key in {field for field, _label in db.ATTENDANCE_TIME_FIELDS}:
            return db.format_attendance_minutes(value, self.attendance_time_mode)
        if key in {field for field, _label in db.ATTENDANCE_DAY_FIELDS}:
            return self._format_attendance_day(value)
        return str(int(value or 0))

    def _build_attendance_items(self, parent):
        import db

        self.attendance_vars = {}
        saved = db.get_payroll_attendance(self.conn, self.payroll_id)
        categories = [
            ("日数", db.ATTENDANCE_DAY_FIELDS),
            ("回数", db.ATTENDANCE_COUNT_FIELDS),
            ("時間", db.ATTENDANCE_TIME_FIELDS),
        ]
        row = 0
        ttk.Label(parent, text=f"時間入力方式: {self.attendance_time_mode}").grid(
            row=row, column=0, columnspan=2, padx=5, pady=(4, 8), sticky="w"
        )
        row += 1
        for title, fields in categories:
            ttk.Label(parent, text=title, font=("", 10, "bold")).grid(
                row=row, column=0, columnspan=2, padx=5, pady=(8, 3), sticky="w"
            )
            row += 1
            for key, label in fields:
                ttk.Label(parent, text=label).grid(row=row, column=0, padx=(12, 5), pady=3, sticky="w")
                var = tk.StringVar(value=self._format_attendance_input(key, saved.get(key, 0)))
                ent = ttk.Entry(parent, textvariable=var, width=12, justify="right")
                ent.grid(row=row, column=1, padx=(5, 12), pady=3, sticky="e")
                self.attendance_vars[key] = {"var": var, "label": label}
                row += 1
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=0)

    def _parse_attendance_inputs(self) -> dict:
        import db

        data = {}
        day_fields = dict(db.ATTENDANCE_DAY_FIELDS)
        count_fields = dict(db.ATTENDANCE_COUNT_FIELDS)
        time_fields = dict(db.ATTENDANCE_TIME_FIELDS)
        for key, meta in self.attendance_vars.items():
            label = meta["label"]
            text = (meta["var"].get() or "").strip()
            try:
                if key in day_fields:
                    if text == "":
                        data[key] = 0
                    elif not re.fullmatch(r"\d+(\.\d+)?", text):
                        raise ValueError("日数は0以上の数値で入力してください。")
                    else:
                        data[key] = float(text)
                elif key in count_fields:
                    if text == "":
                        data[key] = 0
                    elif not re.fullmatch(r"\d+", text):
                        raise ValueError("回数は0以上の整数で入力してください。")
                    else:
                        data[key] = int(text)
                elif key in time_fields:
                    data[key] = db.parse_attendance_time_to_minutes(text, self.attendance_time_mode)
            except ValueError as e:
                raise ValueError(f"{label}: {e}") from e
        return data

    def _build_net_total(self):
        net_frame = ttk.Frame(self)
        net_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.lbl_net = ttk.Label(net_frame, text="差引支給額: 0 円", font=("", 11, "bold"))
        self.lbl_net.pack(side="right")

    def _build_note(self):
        note_frame = ttk.LabelFrame(self, text="備考")
        note_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.txt_note = tk.Text(note_frame, height=4, wrap="word")
        self.txt_note.pack(fill="x", expand=True, padx=8, pady=8)
        self.txt_note.insert("1.0", self._row_value("note", "") or "")

    def _build_footer(self):
        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(footer, text="前社員へ", command=lambda: self.navigate_employee(-1)).pack(side="left", padx=(0, 8))
        ttk.Button(footer, text="次社員へ", command=lambda: self.navigate_employee(1)).pack(side="left", padx=(0, 8))
        ttk.Button(footer, text="閉じる", command=self._close).pack(side="right")
        ttk.Button(footer, text="保存", command=self.save).pack(side="right", padx=(0, 8))

    def _dynamic_total(self, item_kind: str) -> int:
        total = 0
        for item_id, meta in self.dynamic_item_sources.items():
            if not isinstance(item_id, int) or meta["item"]["item_kind"] != item_kind:
                continue
            var = self.dynamic_item_vars.get(item_id)
            if var is None:
                continue
            try:
                total += _to_int(var.get())
            except ValueError:
                pass
        return total

    def _system_deduction_total(self) -> int:
        keys = [
            "health_ins_employee",
            "care_ins_employee",
            "childcare_support_employee",
            "pension_ins_employee",
            "emp_ins_employee",
            "withholding_tax_applied",
            "resident_tax_applied",
        ]
        return sum(self._system_amount(key) for key in keys)

    def _update_totals(self):
        pay_total = self._dynamic_total("pay")
        deduction_total = self._dynamic_total("deduction") + self._system_deduction_total()
        net = pay_total - deduction_total
        if hasattr(self, "lbl_total_pay"):
            self.lbl_total_pay.configure(text=f"支給合計: {pay_total:,} 円")
            self.lbl_total_deduct.configure(text=f"控除合計: {deduction_total:,} 円")
            self.lbl_net.configure(text=f"差引支給額: {net:,} 円")

    def _batch_payroll_ids(self) -> list[int]:
        import db

        rows = db.get_payroll_rows_by_pay_date(
            self.conn,
            str(self.row["target_month"]),
            str(self.row["pay_date_applied"]),
        )
        return [int(row["payroll_id"]) for row in rows]

    def navigate_employee(self, direction: int):
        if self._has_unsaved_changes():
            ok = messagebox.askyesno(
                "確認",
                "保存していない変更があります。保存せずに社員を移動しますか？",
                parent=self,
            )
            if not ok:
                return

        ids = self._batch_payroll_ids()
        if not ids or self.payroll_id not in ids:
            messagebox.showinfo("確認", "移動できる社員が見つかりません。", parent=self)
            return

        current_idx = ids.index(self.payroll_id)
        next_idx = current_idx + direction
        if next_idx < 0 or next_idx >= len(ids):
            messagebox.showinfo("確認", "これ以上移動できません。", parent=self)
            return

        self.payroll_id = ids[next_idx]
        self._reload_view()

    def _reload_view(self):
        old_geometry = self.geometry()
        self.withdraw()
        try:
            self.dynamic_item_vars = {}
            self.dynamic_item_sources = {}
            self.attendance_vars = {}
            self.money_entries = []
            self.scroll_canvases = []
            self._load_row()
            for child in self.winfo_children():
                child.destroy()
            self._build_header()
            self._build_body()
            self._build_net_total()
            self._build_note()
            self._build_footer()
            self._update_totals()
            self._saved_snapshot = self._current_snapshot()
            enable_enter_key_navigation(self)
            self.update_idletasks()
            self.geometry(old_geometry)
        finally:
            self.deiconify()

    def _current_snapshot(self):
        dynamic = {}
        for item_id, var in self.dynamic_item_vars.items():
            if isinstance(item_id, int):
                dynamic[item_id] = (var.get() or "").strip()
        attendance = {
            key: (meta["var"].get() or "").strip()
            for key, meta in getattr(self, "attendance_vars", {}).items()
        }
        note = self.txt_note.get("1.0", "end-1c") if hasattr(self, "txt_note") else ""
        return dynamic, attendance, note

    def _has_unsaved_changes(self) -> bool:
        return getattr(self, "_saved_snapshot", None) != self._current_snapshot()

    def refresh_tax_display(self):
        self._load_row()
        for key, var in getattr(self, "system_amount_vars", {}).items():
            var.set(_format_amount(self._system_amount(key)))
        self._update_totals()

    def open_withholding_override(self):
        dlg = WithholdingOverrideDialog(self, self.conn, self.payroll_id, self.row, on_changed=self.refresh_tax_display)
        self.wait_window(dlg)

    def open_resident_tax_annual(self):
        from ui_resident_tax_annual import ResidentTaxAnnualFrame

        fiscal_year = _resident_tax_fiscal_year(str(self.row["target_month"]))
        employee_id = int(self.row["employee_id"])

        win = tk.Toplevel(self)
        win.withdraw()
        win.title("住民税年次一括入力")
        apply_safe_geometry(win, "1180x620", parent=self)
        win.transient(self)
        frame = ResidentTaxAnnualFrame(
            win,
            self.conn,
            initial_fiscal_year=fiscal_year,
            focus_employee_id=employee_id,
        )
        frame.pack(fill="both", expand=True)
        enable_enter_key_navigation(win)
        show_centered_window(win, self)

    def save(self):
        try:
            data = {}
            money_keys = [
                "officer_pay",
                "base_salary",
                "deemed_ot",
                "overtime_pay",
                "special_allow",
                "commute_nontax",
            ]
            for key in money_keys:
                data[key] = 0
            data["note"] = self.txt_note.get("1.0", "end-1c").strip()

            dynamic_data = {}
            for item_id, meta in self.dynamic_item_sources.items():
                if not isinstance(item_id, int) or meta.get("locked"):
                    continue
                item = meta["item"]
                amount = _to_int(self.dynamic_item_vars[item_id].get())
                dynamic_data[item_id] = (item, amount, meta.get("source") or "manual")
            attendance_data = self._parse_attendance_inputs()
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e), parent=self)
            return

        import db

        db.update_payroll_inputs(self.conn, self.payroll_id, data)
        try:
            year, month = [int(x) for x in str(self.row["target_month"]).split("-")]
            for item_id, (item, amount, _source) in dynamic_data.items():
                db.upsert_payroll_monthly_item_value(
                    self.conn,
                    self.payroll_id,
                    int(self.row["employee_id"]),
                    year,
                    month,
                    item_id,
                    item["item_kind"],
                    amount,
                    "manual",
                    0,
                    None,
                )
        except Exception as e:
            messagebox.showerror("保存エラー", f"支給控除明細の保存に失敗しました。\n{e}", parent=self)
            return

        try:
            db.upsert_payroll_attendance(
                self.conn,
                self.payroll_id,
                int(self.row["employee_id"]),
                str(self.row["target_month"]),
                str(self.row["pay_date_applied"]),
                attendance_data,
            )
        except Exception as e:
            messagebox.showerror("保存エラー", f"勤怠情報の保存に失敗しました。\n{e}", parent=self)
            return

        try:
            db.recalc_target_month(self.conn, str(self.row["target_month"]))
        except Exception as e:
            messagebox.showwarning("再計算エラー", f"保存後の自動再計算でエラーが発生しました。\n{e}", parent=self)

        messagebox.showinfo("保存完了", "保存しました。", parent=self)
        self._saved_snapshot = self._current_snapshot()
        self._close()

    def _close(self):
        if self._has_unsaved_changes():
            ok = messagebox.askyesno(
                "確認",
                "保存していない変更があります。保存せずに閉じますか？",
                parent=self,
            )
            if not ok:
                return
        self.destroy()
