# 賞与計算画面（プロ方式：payroll_bonus 別テーブル）

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from datetime import date

import db
from utils_dates import parse_month
from bonus_batch_dialog import BonusBatchDialog
from ui_window_utils import center_window, enable_enter_key_navigation

class BonusEditorDialog(tk.Toplevel):
    """賞与 追加/編集（モーダル）"""

    def __init__(self, master, conn, target_month: str, bonus_row=None, initial_pay_date: str | None = None):
        super().__init__(master)
        self.conn = conn
        self.target_month = target_month
        self.bonus_row = bonus_row
        self.initial_pay_date = initial_pay_date

        self.title("賞与入力")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frm, text=f"対象年月: {target_month}").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,8))

        ttk.Label(frm, text="支払日").grid(row=1, column=0, sticky="w")
        self.var_pay_date = tk.StringVar(value="")
        ttk.Entry(frm, textvariable=self.var_pay_date, width=18).grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="YYYY-MM-DD").grid(row=1, column=2, sticky="w")
 
        # 社員選択（新規時のみ）
        self.emps = db.list_employees(conn)
        self.emp_map = {f'{e["employee_code"]} {e["name_kanji"]}': e["employee_id"] for e in self.emps}
        self.emp_keys = list(self.emp_map.keys())

        ttk.Label(frm, text="社員").grid(row=2, column=0, sticky="w")
        self.var_emp = tk.StringVar()
        cmb = ttk.Combobox(frm, textvariable=self.var_emp, values=self.emp_keys, state="readonly", width=28)
        cmb.grid(row=2, column=1, columnspan=3, sticky="w")

        ttk.Label(frm, text="賞与額").grid(row=3, column=0, sticky="w", pady=(6,0))
        self.var_amount = tk.StringVar(value="0")
        ent_amt = ttk.Entry(frm, textvariable=self.var_amount, width=18)
        ent_amt.grid(row=3, column=1, sticky="w", pady=(6,0))
        ttk.Label(frm, text="円").grid(row=3, column=2, sticky="w", pady=(6,0))

        ttk.Label(frm, text="備考").grid(row=4, column=0, sticky="w", pady=(6,0))
        self.var_note = tk.StringVar(value="")
        ttk.Entry(frm, textvariable=self.var_note, width=40).grid(row=4, column=1, columnspan=3, sticky="w", pady=(6,0))

        # 既存行なら社員固定
        if bonus_row is not None:
            label = f'{bonus_row["employee_code"]} {bonus_row["name_kanji"]}'
            self.var_emp.set(label)
            cmb.config(state="disabled")
            self.var_pay_date.set(bonus_row["pay_date"] or "")
            self.var_amount.set(str(int(bonus_row["bonus_amount"] or 0)))
            self.var_note.set(bonus_row["note"] or "")
        else:
            if self.emp_keys:
                self.var_emp.set(self.emp_keys[0])
            if self.initial_pay_date:
                self.var_pay_date.set(self.initial_pay_date)
            else:
                self.var_pay_date.set(f"{target_month}-01") 

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=4, sticky="e", pady=(12,0))
        ttk.Button(btns, text="保存", command=self.on_save).pack(side="right", padx=5)
        ttk.Button(btns, text="キャンセル", command=self.destroy).pack(side="right")

        self.wait_visibility()
        enable_enter_key_navigation(self)
        center_window(self, master)
        self.focus_set()

    def _to_int(self, s: str) -> int:
        s = (s or "").replace(",", "").strip()
        if s == "":
            return 0
        return int(float(s))

    def _normalize_pay_date(self, s: str) -> str:
        s = (s or "").strip()
        parts = s.split("-")
        if len(parts) != 3:
            raise ValueError("支払日は YYYY-MM-DD 形式で入力してください。")
        y, m, d = parts
        if not (y.isdigit() and m.isdigit() and d.isdigit()):
            raise ValueError("支払日は YYYY-MM-DD 形式で入力してください。")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    def on_save(self):
        emp_label = self.var_emp.get().strip()
        if not emp_label:
            messagebox.showerror("入力", "社員を選択してください。")
            return
        employee_id = self.emp_map.get(emp_label)
        if not employee_id:
            messagebox.showerror("入力", "社員が特定できません。")
            return
        try:
            amt = self._to_int(self.var_amount.get())
        except Exception:
            messagebox.showerror("入力", "賞与額は数値で入力してください。")
            return

        try:
            pay_date = self._normalize_pay_date(self.var_pay_date.get())
        except Exception as e:
            messagebox.showerror("入力", str(e))
            return
        
        note = self.var_note.get().strip() or None

        db.upsert_bonus(self.conn, self.target_month, pay_date, employee_id, amt, note)
        db.recalc_bonus_month(self.conn, self.target_month)
        self.destroy()


class BonusFrame(ttk.Frame):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self._sort_state = {}
        self._batch_rows_raw = []

        top = ttk.LabelFrame(self, text="賞与")
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
        ttk.Button(top, text="新規作成", command=self.add_bonus).grid(row=0, column=5, padx=5, pady=5)

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=10)

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
            ("pay_date", "支払日", 120),
            ("employee_count", "人数", 40),
            ("total_bonus_amount","賞与額",100),
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
            raise ValueError("支払日は YYYY-MM-DD 形式で入力してください。")

        y, m, d = parts
        if not (y.isdigit() and m.isdigit() and d.isdigit()):
            raise ValueError("支払日は YYYY-MM-DD 形式で入力してください。")

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
            ))

    def _selected_batch(self):
        sel = self.tree.selection()
        if not sel:
            return None, None
        item_id = sel[0]
        index = self.tree.index(item_id)
        if index < 0 or index >= len(self._batch_rows_raw):
            return None, None
        row = self._batch_rows_raw[index]
        return row["target_month"], row["pay_date"]

    def add_bonus(self):
        year_text = (self.var_year.get() or "").strip()
        if not year_text.isdigit():
            messagebox.showerror("入力エラー", "年を選択してください。")
            return

        pay_date = simpledialog.askstring(
            "新規作成",
            "支払日（YYYY-MM-DD）を入力してください。",
            initialvalue=f"{year_text}-{date.today().month:02d}-01",
            parent=self,
        )
        if pay_date is None:
            return

        try:
            pay_date = self._normalize_pay_date(pay_date)
        except Exception as e:
            messagebox.showerror("入力エラー", str(e))
            return

        m = f"{pay_date[:4]}-{pay_date[5:7]}"
        dlg = BonusBatchDialog(self, self.conn, m, pay_date)
        self.wait_window(dlg)
        self._load_years()
        self.var_year.set(pay_date[:4])
        self.refresh()

    def open_selected_batch(self):
        target_month, pay_date = self._selected_batch()
        if not target_month or not pay_date:
            messagebox.showinfo("確認", "対象行を選択してください。")
            return
        dlg = BonusBatchDialog(self, self.conn, target_month, pay_date)
        self.wait_window(dlg)
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
