# 給与計算画面

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from datetime import date

import db
from utils_dates import parse_month, compute_pay_date

from payroll_batch_dialog import PayrollBatchDialog
from ui_window_utils import enable_enter_key_navigation

class PayrollFrame(ttk.Frame):
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

    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self._sort_state = {}
        self._batch_rows_raw = []

        top = ttk.LabelFrame(self, text="月次給与")
        top.pack(fill="x", padx=10, pady=10)

        self.var_display_basis = tk.StringVar(value="対象年月")
        self.var_year = tk.StringVar()

        ttk.Label(top, text="表示基準").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Combobox(
            top,
            textvariable=self.var_display_basis,
            values=["対象年月", "支払日"],
            width=10,
            state="readonly",
        ).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(top, text="年").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.cmb_year = ttk.Combobox(top, textvariable=self.var_year, width=8, state="readonly")
        self.cmb_year.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        ttk.Button(top, text="表示", command=self.refresh).grid(row=0, column=4, padx=5, pady=5)
        ttk.Button(top, text="新規作成", command=self.create_month).grid(row=0, column=5, padx=5, pady=5)
        ttk.Button(top, text="前月複写", command=self.copy_prev).grid(row=0, column=6, padx=5, pady=5)

        # --- Treeview + Scrollbars ---
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=10)

        xscroll = ttk.Scrollbar(tree_frame, orient="horizontal")
        yscroll = ttk.Scrollbar(tree_frame, orient="vertical")

        self.tree = ttk.Treeview(
            tree_frame,
            columns=(
                "target_month",
                "pay_date_applied",
                "employee_count",
                "taxable_pay_sum",
                "non_taxable_pay_sum",
                "gross_pay_sum",
                "social_ins_sum",
                "withholding_tax_sum",
                "resident_tax_sum",
                "other_deduct_sum",
                "total_deduct_sum",
                "net_pay_sum",
            ),
            show="headings",
            height=14,
            xscrollcommand=xscroll.set,
            yscrollcommand=yscroll.set,
        )

        xscroll.config(command=self.tree.xview)
        yscroll.config(command=self.tree.yview)

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        cols = [
            ("target_month", "対象年月", 90),
            ("pay_date_applied", "支払日", 120),
            ("employee_count", "人数", 40),
            ("taxable_pay_sum", "課税支給額", 100),
            ("non_taxable_pay_sum", "非課税支給額", 100),
            ("gross_pay_sum", "総支給額", 100),
            ("social_ins_sum", "社会保険料", 100),
            ("withholding_tax_sum", "源泉所得税", 100),
            ("resident_tax_sum", "住民税", 100),
            ("other_deduct_sum", "その他控除", 100),
            ("total_deduct_sum", "控除合計", 100),
            ("net_pay_sum", "差引支給額", 100),
        ]

        for c, t, w in cols:
            self.tree.heading(c, text=t, command=lambda col=c: self._sort_tree(col))
            anchor = "center" if c in {"target_month", "pay_date_applied"} else "e"
            self.tree.column(c, width=w, anchor=anchor)

        self.tree.bind("<Double-1>", lambda e: self.open_selected_batch())
        self.tree.bind("<Shift-MouseWheel>", self._on_tree_shift_mousewheel)
 
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="支給控除一覧表Excel（縦）", command=self.export_pay_deduct_month).pack(side="left", padx=5)
        ttk.Button(btns, text="賃金台帳Excel（年次・個人別）", command=self.export_wage_ledger_year).pack(side="left", padx=5)
        ttk.Button(btns, text="閉じる", command=self._close_window).pack(side="right", padx=5)

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
            SELECT DISTINCT substr(pay_date_applied,1,4) AS y FROM payroll_monthly
            UNION
            SELECT DISTINCT substr(target_month,1,4) AS y FROM payroll_monthly
            ORDER BY 1 DESC
        """)
        years = [r[0] for r in cur.fetchall() if r[0]]
        if not years:
            years = [str(date.today().year)]
        self.cmb_year["values"] = years
        self.var_year.set(years[0])

    def _get_target_month(self) -> str:
        initial_year = (self.var_year.get() or "").strip()
        if not initial_year.isdigit():
            initial_year = str(date.today().year)
        initial_value = f"{initial_year}-{date.today().month:02d}"

        s = simpledialog.askstring(
            "対象年月",
            "対象年月を YYYY-MM 形式で入力してください。",
            initialvalue=initial_value,
            parent=self,
        )
        if s is None:
            raise ValueError("処理をキャンセルしました。")

        target_month = (s or "").strip()
        parse_month(target_month)
        return target_month

    def create_month(self):
        try:
            m = self._get_target_month()
            mi = parse_month(m)
        except Exception as e:
            messagebox.showerror("入力エラー", str(e))
            return

        employees = db.list_employees(self.conn)
        if not employees:
            messagebox.showinfo("確認", "社員が未登録です。先に社員を登録してください。")
            return

        pay_date_by_emp = {}
        for e in employees:
            schedule_id = e["payment_schedule_id"]

            if schedule_id:
                sched = db.get_payment_schedule_by_id(self.conn, schedule_id)
                if sched:
                    pay_date = db.calc_pay_date(
                        m,
                        sched["closing_mode"],
                        sched["pay_day"]
                    )
                else:
                    # 念のため fallback
                    payday_day = int(e["payday_group"])
                    pay_date = compute_pay_date(m, payday_day).isoformat()
            else:
                # 旧データ fallback
                payday_day = int(e["payday_group"])
                pay_date = compute_pay_date(m, payday_day).isoformat()

            pay_date_by_emp[e["employee_id"]] = (pay_date, pay_date)

        db.ensure_monthly_records(
            self.conn,
            target_month=m,
            wage_period_start=mi.start.isoformat(),
            wage_period_end=mi.end.isoformat(),
            pay_date_by_employee=pay_date_by_emp,
        )        # 自動計算を一括反映（社保→雇保→住民→源泉）
        db.refresh_monthly_pay_dates(self.conn, m, pay_date_by_emp)
        
        try:
            db.recalc_target_month(self.conn, m)
        except Exception as e:
            # 税額表未配置などでもアプリ全体は止めない
            messagebox.showwarning(
                "自動計算",
                "自動計算の一部でエラーが発生しました。\n"
                "税額表Excelなどの配置を確認してください。\n\n"
                f"詳細: {e}",
            )

        self._load_years()
        self.var_year.set(m[:4])
        self.refresh()

    def copy_prev(self):
        try:
            m = self._get_target_month()
            y, mo = map(int, m.split("-"))
        except Exception as e:
            messagebox.showerror("入力エラー", str(e))
            return

        if mo == 1:
            prev = f"{y-1}-12"
        else:
            prev = f"{y}-{mo-1:02d}"

        target_label = self._format_target_month_label(m)
        prev_label = self._format_target_month_label(prev)
        ok = messagebox.askokcancel(
            "前月複写の確認",
            f"対象年月：{prev_label} の入力データが\n"
            f"対象年月：{target_label} に複写されます。\n"
            f"よろしいですか？"
        )
        if not ok:
            return

        cur_rows = db.get_payroll_rows(self.conn, m)
        if not cur_rows:
            messagebox.showinfo("確認", "当月分が未作成です。「当月分を作成/不足分を追加」を先に実行してください。")
            return

        prev_rows = db.get_payroll_rows(self.conn, prev)
        if not prev_rows:
            messagebox.showinfo("確認", f"前月（{prev}）のデータがありません。")
            return

        db.copy_prev_month_inputs(self.conn, m, prev)
        # 複写後に自動計算を反映
        try:
            db.recalc_target_month(self.conn, m)
        except Exception as e:
            messagebox.showwarning("自動計算", f"複写後の自動計算でエラーが発生しました。\n\n詳細: {e}")
        messagebox.showinfo("完了", f"前月（{prev}）の入力値を当月（{m}）へ複写しました。\n※住民税上書き・支払日上書きは複写しません。")
        self._load_years()
        self.var_year.set(m[:4])
        self.refresh()

    def refresh(self):
        def fmt_yen(v):
            if v is None or v == "":
                return ""
            try:
                return f"{int(v):,}"
            except Exception:
                return str(v)

        money_cols = {
            "taxable_pay_sum",
            "non_taxable_pay_sum",
            "gross_pay_sum",
            "social_ins_sum",
            "withholding_tax_sum",
            "resident_tax_sum",
            "other_deduct_sum",
            "total_deduct_sum",
            "net_pay_sum",
        }

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
            rows = db.get_payroll_batch_rows_by_target_year(self.conn, year)
        else:
            rows = db.get_payroll_batch_rows_by_paydate_year(self.conn, year)
        cols = self.tree["columns"]

        for r in rows:
            self._batch_rows_raw.append({
                "target_month": r["target_month"],
                "pay_date_applied": r["pay_date_applied"],
            })
            values = []
            for c in cols:
                v = r[c] if c in r.keys() else ""

                if v is None:
                    v = ""

                if c == "target_month":
                    v = self._format_target_month_label(v)
                elif c == "pay_date_applied":
                    v = self._format_pay_date_label(v)

                if c in money_cols:
                    v = fmt_yen(v)

                values.append(v)

            self.tree.insert("", "end", values=tuple(values))

    def _get_display_basis_key(self) -> str:
        label = (self.var_display_basis.get() or "").strip()
        if label == "支払日":
            return "paydate"
        return "target"

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

    def _selected_batch(self):
        sel = self.tree.selection()
        if not sel:
            return None, None

        item_id = sel[0]
        index = self.tree.index(item_id)
        if index < 0 or index >= len(self._batch_rows_raw):
            return None, None

        row = self._batch_rows_raw[index]
        return row["target_month"], row["pay_date_applied"]

    def open_selected_batch(self):
        target_month, pay_date_applied = self._selected_batch()
        if not target_month or not pay_date_applied:
            messagebox.showinfo("確認", "対象行を選択してください。")
            return
        
        dlg = PayrollBatchDialog(self, self.conn, target_month, pay_date_applied)
        self.wait_window(dlg)
        self.refresh()

    def export_pay_deduct_month(self):
        try:
            m = self._get_target_month()
        except Exception as e:
            messagebox.showerror("入力エラー", str(e))            
            return

        default_name = f"支給控除一覧_{m}.xlsx"
        path = filedialog.asksaveasfilename(
            title="支給控除一覧表（Excel）保存先",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return

        try:
            db.export_pay_deduct_report_month(self.conn, m, path)
        except Exception as e:
            messagebox.showerror("エラー", f"出力に失敗しました。\n詳細: {e}")
            return

        messagebox.showinfo("完了", f"出力しました。\n{path}")

    def export_wage_ledger_year(self):
        s = simpledialog.askstring("賃金台帳（年次）", "対象年（YYYY）を入力してください。例：2026")
        if s is None:
            return
        s = s.strip()
        if not s.isdigit() or len(s) != 4:
            messagebox.showerror("入力エラー", "対象年はYYYY（例：2026）で入力してください。")
            return

        year = int(s)
        default_name = f"賃金台帳_{year}.xlsx"
        path = filedialog.asksaveasfilename(
            title="賃金台帳（年次・個人別）保存先",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return

        try:
            db.export_wage_ledger_year(self.conn, year, path)
        except Exception as e:
            messagebox.showerror("エラー", f"出力に失敗しました。\n詳細: {e}")
            return

        messagebox.showinfo("完了", f"出力しました。\n{path}")
