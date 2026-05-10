# 賞与計算画面（プロ方式：payroll_bonus 別テーブル）

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from datetime import date

import db
from utils_dates import parse_month
from bonus_batch_dialog import BonusBatchDialog
from ui_create_dialogs import CreateMethodDialog, YearMonthDialog
from ui_window_utils import show_centered_window, enable_enter_key_navigation, apply_grid_treeview_style, refresh_grid_treeview

class BonusEditorDialog(tk.Toplevel):
    """賞与支給控除金額の追加/編集"""

    DEDUCTION_FIELDS = [
        ("health_ins", "健康保険料", "health_ins_auto", "health_ins_override", "health_ins_employee"),
        ("care_ins", "介護保険料", "care_ins_auto", "care_ins_override", "care_ins_employee"),
        ("childcare", "子ども・子育て支援金", "childcare_support_auto", "childcare_support_override", "childcare_support_employee"),
        ("pension", "厚生年金保険料", "pension_ins_auto", "pension_ins_override", "pension_ins_employee"),
        ("emp_ins", "雇用保険料", "emp_ins_auto", "emp_ins_override", "emp_ins_employee"),
        ("withholding", "所得税", "withholding_tax_auto", "withholding_tax_override", "withholding_tax_applied"),
    ]

    def __init__(
        self,
        master,
        conn,
        target_month: str,
        bonus_row=None,
        initial_pay_date: str | None = None,
        employee_ids: set[int] | None = None,
    ):
        super().__init__(master)
        self.withdraw()
        self.conn = conn
        self.target_month = target_month
        self.bonus_row = bonus_row
        self.initial_pay_date = initial_pay_date
        self.override_vars = {}
        self.applied_vars = {}
        self.auto_vars = {}

        self.title("賞与支給控除金額の編集")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.emps = db.list_employees(conn)
        if employee_ids is not None:
            self.emps = [e for e in self.emps if int(e["employee_id"]) in employee_ids]
        self.emp_map = {f'{e["employee_code"]} {e["name_kanji"]}': e["employee_id"] for e in self.emps}
        self.emp_keys = list(self.emp_map.keys())

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        self.var_pay_date = tk.StringVar(value="")
        self.var_emp = tk.StringVar()
        self.var_amount = tk.StringVar(value="0")
        self.var_note = tk.StringVar(value="")
        self.var_social_total = tk.StringVar(value="0")
        self.var_deduction_total = tk.StringVar(value="0")
        self.var_net = tk.StringVar(value="0")

        self._build_basic_frame(frm)
        self._build_pay_frame(frm)
        self._build_deduction_frame(frm)
        self._build_net_frame(frm)
        self._build_note_frame(frm)
        self._build_footer(frm)

        self._load_row_values()
        self._bind_recalc_events()
        self._refresh_totals()
        self._saved_snapshot = self._current_snapshot()

        enable_enter_key_navigation(self)
        show_centered_window(self, master)
        self.focus_set()

    def _build_basic_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="基本情報")
        frame.pack(fill="x", pady=(0, 8))

        ttk.Label(frame, text="対象年月").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Label(frame, text=self.target_month).grid(row=0, column=1, padx=6, pady=4, sticky="w")

        ttk.Label(frame, text="支給日").grid(row=0, column=2, padx=6, pady=4, sticky="w")
        ttk.Entry(frame, textvariable=self.var_pay_date, width=16).grid(row=0, column=3, padx=6, pady=4, sticky="w")

        ttk.Label(frame, text="社員").grid(row=1, column=0, padx=6, pady=4, sticky="w")
        self.cmb_emp = ttk.Combobox(frame, textvariable=self.var_emp, values=self.emp_keys, state="readonly", width=32)
        self.cmb_emp.grid(row=1, column=1, columnspan=3, padx=6, pady=4, sticky="w")

    def _build_pay_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="支給")
        frame.pack(fill="x", pady=(0, 8))
        ttk.Label(frame, text="賞与支給額").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Entry(frame, textvariable=self.var_amount, width=16, justify="right").grid(row=0, column=1, padx=6, pady=4, sticky="w")
        ttk.Label(frame, text="円").grid(row=0, column=2, padx=(0, 6), pady=4, sticky="w")

    def _build_deduction_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="控除")
        frame.pack(fill="x", pady=(0, 8))
        headers = ["項目", "自動計算額", "上書き額", "適用額"]
        for col, text in enumerate(headers):
            ttk.Label(frame, text=text).grid(row=0, column=col, padx=6, pady=(4, 2), sticky="w")

        for row_idx, (code, title, auto_key, override_key, applied_key) in enumerate(self.DEDUCTION_FIELDS, start=1):
            ttk.Label(frame, text=title).grid(row=row_idx, column=0, padx=6, pady=3, sticky="w")
            self.auto_vars[code] = tk.StringVar(value="0")
            self.override_vars[code] = tk.StringVar(value="")
            self.applied_vars[code] = tk.StringVar(value="0")
            ttk.Label(frame, textvariable=self.auto_vars[code], anchor="e", width=14).grid(row=row_idx, column=1, padx=6, pady=3, sticky="e")
            ttk.Entry(frame, textvariable=self.override_vars[code], width=14, justify="right").grid(row=row_idx, column=2, padx=6, pady=3, sticky="w")
            ttk.Label(frame, textvariable=self.applied_vars[code], anchor="e", width=14).grid(row=row_idx, column=3, padx=6, pady=3, sticky="e")

        sep_row = len(self.DEDUCTION_FIELDS) + 1
        ttk.Separator(frame, orient="horizontal").grid(row=sep_row, column=0, columnspan=4, sticky="ew", padx=6, pady=(6, 3))
        ttk.Label(frame, text="社会保険料合計").grid(row=sep_row + 1, column=0, padx=6, pady=3, sticky="w")
        ttk.Label(frame, textvariable=self.var_social_total, anchor="e", width=14).grid(row=sep_row + 1, column=3, padx=6, pady=3, sticky="e")
        ttk.Label(frame, text="控除合計額").grid(row=sep_row + 2, column=0, padx=6, pady=3, sticky="w")
        ttk.Label(frame, textvariable=self.var_deduction_total, anchor="e", width=14).grid(row=sep_row + 2, column=3, padx=6, pady=3, sticky="e")

    def _build_net_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="差引")
        frame.pack(fill="x", pady=(0, 8))
        ttk.Label(frame, text="差引支給額").grid(row=0, column=0, padx=6, pady=4, sticky="w")
        ttk.Label(frame, textvariable=self.var_net, anchor="e", width=16).grid(row=0, column=1, padx=6, pady=4, sticky="e")

    def _build_note_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="備考")
        frame.pack(fill="x", pady=(0, 8))
        ttk.Entry(frame, textvariable=self.var_note, width=58).pack(fill="x", padx=6, pady=6)

    def _build_footer(self, parent):
        footer = ttk.Frame(parent)
        footer.pack(fill="x", pady=(4, 0))
        ttk.Button(footer, text="閉じる", command=self._close).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="保存", command=self.on_save).pack(side="right")

    def _load_row_values(self):
        if self.bonus_row is not None:
            label = f'{self.bonus_row["employee_code"]} {self.bonus_row["name_kanji"]}'
            self.var_emp.set(label)
            self.cmb_emp.config(state="disabled")
            self.var_pay_date.set(self.bonus_row["pay_date"] or "")
            self.var_amount.set(self._format_amount(self.bonus_row["bonus_amount"] or 0))
            self.var_note.set(self.bonus_row["note"] or "")
        else:
            if self.emp_keys:
                self.var_emp.set(self.emp_keys[0])
            self.var_pay_date.set(self.initial_pay_date or f"{self.target_month}-01")

        row = self.bonus_row
        for code, _title, auto_key, override_key, applied_key in self.DEDUCTION_FIELDS:
            auto = self._row_int(row, auto_key)
            applied = self._row_int(row, applied_key)
            if auto == 0 and applied:
                auto = applied
            override = self._row_raw(row, override_key)
            self.auto_vars[code].set(self._format_amount(auto))
            self.override_vars[code].set("" if override is None else self._format_amount(override))
            self.applied_vars[code].set(self._format_amount(applied))

    def _bind_recalc_events(self):
        self.var_amount.trace_add("write", lambda *_: self._refresh_totals())
        for var in self.override_vars.values():
            var.trace_add("write", lambda *_: self._refresh_totals())

    def _row_raw(self, row, key):
        if row is None or key not in row.keys():
            return None
        return row[key]

    def _row_int(self, row, key) -> int:
        value = self._row_raw(row, key)
        return int(value or 0)

    def _format_amount(self, value) -> str:
        try:
            return f"{int(value):,}"
        except Exception:
            return "0"

    def _to_int(self, s: str) -> int:
        s = (s or "").replace(",", "").strip()
        if s == "":
            return 0
        if not s.lstrip("-").isdigit():
            raise ValueError("金額は円単位の整数で入力してください。")
        return int(s)

    def _to_optional_int(self, s: str) -> int | None:
        s = (s or "").replace(",", "").strip()
        if s == "":
            return None
        if not s.lstrip("-").isdigit():
            raise ValueError("上書き額は円単位の整数で入力してください。")
        return int(s)

    def _normalize_pay_date(self, s: str) -> str:
        s = (s or "").strip()
        parts = s.split("-")
        if len(parts) != 3:
            raise ValueError("支給日は yyyy-mm-dd 形式で入力してください。")
        y, m, d = parts
        if not (y.isdigit() and m.isdigit() and d.isdigit()):
            raise ValueError("支給日は yyyy-mm-dd 形式で入力してください。")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    def _refresh_totals(self):
        social = 0
        deduction = 0
        try:
            for code, _title, _auto_key, _override_key, _applied_key in self.DEDUCTION_FIELDS:
                auto = self._to_int(self.auto_vars[code].get())
                override = self._to_optional_int(self.override_vars[code].get())
                applied = auto if override is None else override
                self.applied_vars[code].set(self._format_amount(applied))
                if code in {"health_ins", "care_ins", "childcare", "pension"}:
                    social += applied
                deduction += applied
            bonus = self._to_int(self.var_amount.get())
            self.var_social_total.set(self._format_amount(social))
            self.var_deduction_total.set(self._format_amount(deduction))
            self.var_net.set(self._format_amount(bonus - deduction))
        except Exception:
            return

    def _current_snapshot(self):
        return {
            "pay_date": self.var_pay_date.get(),
            "employee": self.var_emp.get(),
            "amount": self.var_amount.get(),
            "note": self.var_note.get(),
            "overrides": {k: v.get() for k, v in self.override_vars.items()},
        }

    def _has_unsaved_changes(self) -> bool:
        return self._current_snapshot() != getattr(self, "_saved_snapshot", None)

    def on_save(self):
        emp_label = self.var_emp.get().strip()
        if not emp_label:
            messagebox.showerror("入力", "社員を選択してください。", parent=self)
            return
        employee_id = self.emp_map.get(emp_label)
        if not employee_id:
            messagebox.showerror("入力", "社員が特定できません。", parent=self)
            return

        try:
            amt = self._to_int(self.var_amount.get())
            pay_date = self._normalize_pay_date(self.var_pay_date.get())
            overrides = {
                "health_ins_override": self._to_optional_int(self.override_vars["health_ins"].get()),
                "care_ins_override": self._to_optional_int(self.override_vars["care_ins"].get()),
                "childcare_support_override": self._to_optional_int(self.override_vars["childcare"].get()),
                "pension_ins_override": self._to_optional_int(self.override_vars["pension"].get()),
                "emp_ins_override": self._to_optional_int(self.override_vars["emp_ins"].get()),
                "withholding_tax_override": self._to_optional_int(self.override_vars["withholding"].get()),
            }
        except Exception as e:
            messagebox.showerror("入力", str(e), parent=self)
            return

        note = self.var_note.get().strip() or None
        db.upsert_bonus(self.conn, self.target_month, pay_date, employee_id, amt, note)
        row = db.get_bonus_by_employee_month(self.conn, self.target_month, employee_id)
        if row is None:
            messagebox.showerror("保存", "保存した賞与データを確認できませんでした。", parent=self)
            return
        db.update_bonus_overrides(self.conn, int(row["bonus_id"]), overrides)
        try:
            db.recalc_bonus_month(self.conn, self.target_month)
        except Exception as e:
            messagebox.showwarning("自動計算", f"保存後の自動計算でエラーが発生しました。\n\n詳細: {e}", parent=self)

        self.bonus_row = db.get_bonus_by_employee_month(self.conn, self.target_month, employee_id)
        self._saved_snapshot = self._current_snapshot()
        messagebox.showinfo("保存完了", "保存しました。", parent=self)
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


class BonusFrame(ttk.Frame):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self._sort_state = {}
        self._batch_rows_raw = []

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=(8, 4))

        self.var_display_basis = tk.StringVar(value="対象年月")
        self.var_year = tk.StringVar()

        ttk.Label(top, text="表示基準").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.cmb_display_basis = ttk.Combobox(
            top,
            textvariable=self.var_display_basis,
            values=["対象年月", "支払日"],
            width=10,
            state="readonly",
        )
        self.cmb_display_basis.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(top, text="年").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.cmb_year = ttk.Combobox(top, textvariable=self.var_year, width=8, state="readonly")
        self.cmb_year.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        self.cmb_display_basis.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        self.cmb_year.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(4, 6))

        xscroll = ttk.Scrollbar(tree_frame, orient="horizontal")
        yscroll = ttk.Scrollbar(tree_frame, orient="vertical")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=(
                "target_month",
                "pay_date",
                "employee_count",
                "total_bonus_amount",
                "total_social_ins",
                "total_withholding_tax",
                "total_net_amount",
            ),
            show="headings",
            height=11,
            xscrollcommand=xscroll.set,
            yscrollcommand=yscroll.set,
        )
        apply_grid_treeview_style(self.tree, xscroll=xscroll)
        yscroll.config(command=self.tree.yview)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        cols = [
            ("target_month", "対象年月", 90),
            ("pay_date", "支払日", 120),
            ("employee_count", "人数", 40),
            ("total_bonus_amount","賞与支給額",100),
            ("total_social_ins","社会保険料",100),
            ("total_withholding_tax","源泉所得税",100),
            ("total_net_amount", "差引支給額合計", 100),
        ]

        for c, t, w in cols:
            self.tree.heading(c, text=t, command=lambda col=c: self._sort_tree(col))
            anchor = "center" if c in {"target_month", "pay_date"} else "e"
            self.tree.column(c, width=w, anchor=anchor)

        self.tree.bind("<Double-1>", lambda e: self.open_selected_batch())
        self.tree.bind("<Shift-MouseWheel>", self._on_tree_shift_mousewheel)

        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(footer, text="新規作成", command=self.add_bonus).pack(side="left", padx=(0, 8))
        ttk.Button(footer, text="編集", command=self.open_selected_batch).pack(side="left", padx=(0, 8))
        ttk.Button(footer, text="削除", command=self.delete_selected_batch).pack(side="left", padx=(0, 8))
        ttk.Button(footer, text="閉じる", command=self._close_window).pack(side="right", padx=5)

        self._load_years()
        self.refresh()
        enable_enter_key_navigation(self)

    def _close_window(self):
        self.winfo_toplevel().destroy()

    def _on_tree_shift_mousewheel(self, event):
        self.tree.xview_scroll(int(-10 * (event.delta / 120)), "units")
        return "break"

    def _load_years(self):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT DISTINCT substr(pay_date, 1, 4) AS y FROM payroll_bonus
            UNION
            SELECT DISTINCT substr(target_month, 1, 4) AS y FROM payroll_bonus
            ORDER BY 1 DESC
        """)
        years = [r[0] for r in cur.fetchall() if r[0]]
        if not years:
            years = [str(date.today().year)]
        self.cmb_year["values"] = years
        self.var_year.set(years[0])

    def _format_target_month_label(self, ym: str) -> str:
        s = (ym or "").strip()
        try:
            y, m = s.split("-")
            return f"{int(y):04d} 年 {int(m):02d} 月"
        except Exception:
            return s

    def _format_pay_date_label(self, ymd: str) -> str:
        s = (ymd or "").strip()
        try:
            y, m, d = s.split("-")
            return f"{int(y):04d} 年 {int(m):02d} 月 {int(d):02d} 日"
        except Exception:
            return s    

    def _get_display_basis_key(self) -> str:
        label = (self.var_display_basis.get() or "").strip()
        if label == "支払日":
            return "paydate"
        return "target"

    def _normalize_pay_date(self, s: str) -> str:
        s = (s or "").strip()
        parts = s.split("-")
        if len(parts) != 3:
            raise ValueError("支払日は yyyy-mm-dd 形式で入力してください。")

        y, m, d = parts
        if not (y.isdigit() and m.isdigit() and d.isdigit()):
            raise ValueError("支払日は yyyy-mm-dd 形式で入力してください。")

        y = int(y)
        m = int(m)
        d = int(d)
        if not (1 <= m <= 12):
            raise ValueError("支払日の月は 1～12 で入力してください。")
        if not (1 <= d <= 31):
            raise ValueError("支払日の日は 1～31 で入力してください。")

        return f"{y:04d}-{m:02d}-{d:02d}"    

    def refresh(self):
        def fmt_yen(v):
            if v is None or v == "":
                return ""
            try:
                return f"{int(v):,}"
            except Exception:
                return str(v)

        for i in self.tree.get_children():
            self.tree.delete(i)
        self._batch_rows_raw = []

        year_text = (self.var_year.get() or "").strip()
        if not year_text.isdigit():
            messagebox.showerror("入力エラー", "対象年は4桁の西暦で入力してください。")
            return

        year = int(year_text)
        basis = self._get_display_basis_key()
        if basis == "target":
            rows = db.list_bonus_batch_rows_by_target_year(self.conn, year)
        else:
            rows = db.list_bonus_batch_rows_by_paydate_year(self.conn, year)

        for r in rows:
            self._batch_rows_raw.append({
                "target_month": r["target_month"],
                "pay_date": r["pay_date"],
            })
            self.tree.insert("", "end", values=(
                self._format_target_month_label(r["target_month"]),
                self._format_pay_date_label(r["pay_date"]),
                int(r["employee_count"] or 0),
                fmt_yen(r["total_bonus_amount"] or 0),
                fmt_yen(r["total_social_ins"] or 0),
                fmt_yen(r["total_withholding_tax"] or 0),
                fmt_yen(r["total_net_amount"] or 0),
            ), iid=f"{r['target_month']}|{r['pay_date']}")
        refresh_grid_treeview(self.tree)

    def _selected_batch(self):
        sel = self.tree.selection()
        if not sel:
            return None, None
        item_id = str(sel[0])
        parts = item_id.split("|", 1)
        if len(parts) != 2:
            return None, None
        return parts[0], parts[1]

    def add_bonus(self):
        dlg = CreateMethodDialog(self, "賞与")
        self.wait_window(dlg)
        if dlg.result == "new":
            self._add_bonus_new_flow()
        elif dlg.result == "copy":
            self._add_bonus_copy_flow()

    def _ask_bonus_month(self, title: str, source_options=None):
        initial_year = int(self.var_year.get()) if (self.var_year.get() or "").isdigit() else date.today().year
        dlg = YearMonthDialog(
            self,
            title,
            source_options=source_options,
            initial_year=initial_year,
            initial_month=date.today().month,
        )
        self.wait_window(dlg)
        return dlg.result

    def _ensure_bonus_month_not_exists(self, target_month: str) -> bool:
        if db.bonus_month_exists(self.conn, target_month):
            messagebox.showwarning(
                "確認",
                "指定した対象年月には、すでに賞与データが存在します。\n別の年月を指定してください。",
                parent=self,
            )
            return False
        return True

    def _add_bonus_new_flow(self):
        result = self._ask_bonus_month("賞与データの新規作成")
        if not result:
            return
        target_month, _source = result
        if not self._ensure_bonus_month_not_exists(target_month):
            return
        pay_date = f"{target_month}-01"
        dlg = BonusBatchDialog(self, self.conn, target_month, pay_date)
        self.wait_window(dlg)
        self._load_years()
        self.var_year.set(target_month[:4])
        self.refresh()

    def _add_bonus_copy_flow(self):
        source_months = db.list_bonus_copy_source_months(self.conn)
        if not source_months:
            messagebox.showinfo("確認", "複写元にできる賞与データがありません。", parent=self)
            return
        source_options = [(self._format_target_month_label(m) + " 賞与", m) for m in source_months]
        result = self._ask_bonus_month("賞与データを既存明細から複写", source_options=source_options)
        if not result:
            return
        target_month, source_month = result
        if not self._ensure_bonus_month_not_exists(target_month):
            return
        pay_date = f"{target_month}-01"
        copied = db.copy_prev_bonus_inputs(self.conn, target_month, pay_date, source_month)
        if copied <= 0:
            messagebox.showinfo("確認", "選択した複写元の賞与データがありません。", parent=self)
            return
        try:
            db.recalc_bonus_month(self.conn, target_month)
        except Exception as e:
            messagebox.showwarning("自動計算", f"複写後の自動計算でエラーが発生しました。\n\n詳細: {e}", parent=self)
        self._load_years()
        self.var_year.set(target_month[:4])
        self.refresh()

    def open_selected_batch(self):
        target_month, pay_date = self._selected_batch()
        if not target_month or not pay_date:
            messagebox.showinfo("確認", "対象行を選択してください。")
            return
        dlg = BonusBatchDialog(self, self.conn, target_month, pay_date)
        self.wait_window(dlg)
        self.refresh()

    def copy_prev_bonus(self):
        year_text = (self.var_year.get() or "").strip()
        if not year_text.isdigit():
            messagebox.showerror("入力エラー", "年を選択してください。")
            return

        pay_date = simpledialog.askstring(
            "前月複写",
            "複写先の支払日（yyyy-mm-dd）を入力してください。",
            initialvalue=f"{year_text}-{date.today().month:02d}-01",
            parent=self,
        )
        if pay_date is None:
            return

        try:
            pay_date = self._normalize_pay_date(pay_date)
            target_month = f"{pay_date[:4]}-{pay_date[5:7]}"
            prev_month = db._prev_month(target_month)
        except Exception as e:
            messagebox.showerror("入力エラー", str(e))
            return

        ok = messagebox.askokcancel(
            "前月複写の確認",
            f"前月（{prev_month}）の賞与入力を、支払日 {pay_date} に複写します。\nよろしいですか？",
            parent=self,
        )
        if not ok:
            return

        copied = db.copy_prev_bonus_inputs(self.conn, target_month, pay_date, prev_month)
        if copied <= 0:
            messagebox.showinfo("確認", f"前月（{prev_month}）の賞与データがありません。")
            return
        try:
            db.recalc_bonus_month(self.conn, target_month)
        except Exception as e:
            messagebox.showwarning("自動計算", f"複写後の自動計算でエラーが発生しました。\n\n詳細: {e}")
        messagebox.showinfo("完了", f"前月（{prev_month}）の賞与入力を複写しました。")
        self._load_years()
        self.var_year.set(pay_date[:4])
        self.refresh()

    def delete_selected_batch(self):
        target_month, pay_date = self._selected_batch()
        if not target_month or not pay_date:
            messagebox.showwarning("確認", "削除する行を選択してください。")
            return

        ok = messagebox.askokcancel(
            "削除確認",
            "選択した賞与データを削除しますか？",
            parent=self,
        )
        if not ok:
            return

        db.delete_bonus_batch(self.conn, target_month, pay_date)
        self._load_years()
        self.refresh()

    def _sort_value(self, value):
        if value is None:
            return (2, "")
        s = str(value).replace(",", "").strip()
        if s == "":
            return (2, "")
        try:
            return (0, int(s))
        except Exception:
            return (1, str(value))

    def _sort_tree(self, col_name: str):
        rows = []
        cols = self.tree["columns"]
        for item_id in self.tree.get_children(""):
            values = self.tree.item(item_id, "values")
            row_map = {cols[i]: values[i] for i in range(len(cols))}
            rows.append((item_id, row_map))

        reverse = self._sort_state.get(col_name, False)
        rows.sort(key=lambda x: self._sort_value(x[1].get(col_name, "")), reverse=reverse)

        for idx, (item_id, _) in enumerate(rows):
            self.tree.move(item_id, "", idx)

        self._sort_state[col_name] = not reverse
