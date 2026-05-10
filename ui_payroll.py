# 給与計算画面

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from datetime import date

import db
from utils_dates import parse_month, compute_pay_date

from payroll_batch_dialog import PayrollBatchDialog
from ui_create_dialogs import CreateMethodDialog, YearMonthDialog
from ui_window_utils import show_centered_window, enable_enter_key_navigation, apply_grid_treeview_style, refresh_grid_treeview


class WageLedgerExportOptionsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw()
        self.result = None

        self.title("賃金台帳(.xlsx)")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.var_year = tk.StringVar(value=str(date.today().year))
        self.var_basis = tk.StringVar(value="target")

        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="対象年").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_year, width=10).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        basis = ttk.LabelFrame(frm, text="出力基準")
        basis.grid(row=1, column=0, columnspan=2, padx=5, pady=(8, 5), sticky="ew")
        ttk.Radiobutton(basis, text="対象月", value="target", variable=self.var_basis).pack(anchor="w", padx=8, pady=4)
        ttk.Radiobutton(basis, text="支払日", value="paydate", variable=self.var_basis).pack(anchor="w", padx=8, pady=4)

        footer = ttk.Frame(frm)
        footer.grid(row=2, column=0, columnspan=2, sticky="e", padx=5, pady=(10, 0))
        ttk.Button(footer, text="OK", command=self.apply).pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="キャンセル", command=self.cancel).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda event: self.cancel())
        enable_enter_key_navigation(self)
        show_centered_window(self, parent)
        self.after(10, self.focus_force)

    def apply(self):
        year_text = (self.var_year.get() or "").strip()
        if not year_text.isdigit() or len(year_text) != 4:
            messagebox.showerror("入力エラー", "対象年はyyyy（例：2026）で入力してください。", parent=self)
            return
        self.result = (int(year_text), self.var_basis.get())
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def cancel(self):
        self.result = None
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

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

        # --- Treeview + Scrollbars ---
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(4, 6))

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
            ("pay_date_applied", "支払日", 120),
            ("employee_count", "人数", 46),
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
        ttk.Button(btns, text="新規作成", command=self.create_month).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="編集", command=self.open_selected_batch).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="削除", command=self.delete_selected_batch).pack(side="left", padx=(0, 8))
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

    def _get_target_month(self, dialog_title: str = "対象年月") -> str:
        initial_year = (self.var_year.get() or "").strip()
        if not initial_year.isdigit():
            initial_year = str(date.today().year)
        initial_value = f"{initial_year}-{date.today().month:02d}"

        s = simpledialog.askstring(
            dialog_title,
            "対象年月を yyyy-mm 形式で入力してください。",
            initialvalue=initial_value,
            parent=self,
        )
        if s is None:
            raise ValueError("処理をキャンセルしました。")

        target_month = (s or "").strip()
        parse_month(target_month)
        return target_month

    def create_month(self):
        dlg = CreateMethodDialog(self, "給与")
        self.wait_window(dlg)
        if dlg.result == "new":
            self._create_month_new_flow()
        elif dlg.result == "copy":
            self._create_month_copy_flow()

    def _ask_create_month(self, title: str, source_options=None):
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

    def _ensure_payroll_month_not_exists(self, target_month: str) -> bool:
        if db.payroll_month_exists(self.conn, target_month):
            messagebox.showwarning(
                "確認",
                "指定した対象年月には、すでに給与データが存在します。\n別の年月を指定してください。",
                parent=self,
            )
            return False
        return True

    def _create_month_new_flow(self):
        result = self._ask_create_month("給与データの新規作成")
        if not result:
            return
        m, _source = result
        if not self._ensure_payroll_month_not_exists(m):
            return
        self._create_month_records(m)

    def _create_month_copy_flow(self):
        source_months = db.list_payroll_copy_source_months(self.conn)
        if not source_months:
            messagebox.showinfo("確認", "複写元にできる給与データがありません。", parent=self)
            return
        source_options = [(self._format_target_month_label(m) + " 給与", m) for m in source_months]
        result = self._ask_create_month("給与データを既存明細から複写", source_options=source_options)
        if not result:
            return
        m, source_month = result
        if not self._ensure_payroll_month_not_exists(m):
            return
        self._create_month_records(m)
        db.copy_prev_month_inputs(self.conn, m, source_month)
        try:
            db.recalc_target_month(self.conn, m)
        except Exception as e:
            messagebox.showwarning("自動計算", f"複写後の自動計算でエラーが発生しました。\n\n詳細: {e}", parent=self)
        self._load_years()
        self.var_year.set(m[:4])
        self.refresh()

    def _create_month_records(self, m: str):
        try:
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

            iid = f"{r['target_month']}|{r['pay_date_applied']}"
            self.tree.insert("", "end", iid=iid, values=tuple(values))
        refresh_grid_treeview(self.tree)

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

        item_id = str(sel[0])
        parts = item_id.split("|", 1)
        if len(parts) != 2:
            return None, None
        return parts[0], parts[1]

    def open_selected_batch(self):
        target_month, pay_date_applied = self._selected_batch()
        if not target_month or not pay_date_applied:
            messagebox.showinfo("確認", "対象行を選択してください。")
            return
        
        dlg = PayrollBatchDialog(self, self.conn, target_month, pay_date_applied)
        self.wait_window(dlg)
        self.refresh()

    def delete_selected_batch(self):
        target_month, pay_date_applied = self._selected_batch()
        if not target_month or not pay_date_applied:
            messagebox.showwarning("確認", "削除する行を選択してください。")
            return

        ok = messagebox.askokcancel(
            "削除確認",
            "選択した給与データを削除しますか？",
            parent=self,
        )
        if not ok:
            return

        db.delete_payroll_batch(self.conn, target_month, pay_date_applied)
        self._load_years()
        self.refresh()

    def export_pay_deduct_month(self):
        try:
            m = self._get_target_month("支給控除一覧(.xlsx)")
        except Exception as e:
            messagebox.showerror("入力エラー", str(e))            
            return

        default_name = f"支給控除一覧_{m}.xlsx"
        path = filedialog.asksaveasfilename(
            title="支給控除一覧(.xlsx)",
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
        dlg = WageLedgerExportOptionsDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return

        year, basis = dlg.result
        basis_label = "対象月" if basis == "target" else "支払日"
        default_name = f"賃金台帳_{year}_{basis_label}.xlsx"
        path = filedialog.asksaveasfilename(
            title="賃金台帳（年次・個人別）保存先",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return

        try:
            db.export_wage_ledger_year(self.conn, year, path, basis=basis)
        except Exception as e:
            messagebox.showerror("エラー", f"出力に失敗しました。\n詳細: {e}")
            return

        messagebox.showinfo("完了", f"出力しました。\n{path}")
