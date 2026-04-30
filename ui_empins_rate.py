# 雇用保険料設定画面

import ctypes
import tkinter as tk
from tkinter import ttk, messagebox

from ui_window_utils import center_window
from utils_rates import parse_percent_to_rate, format_rate_to_percent_text


def force_ime_off(widget):
    """Windows の IME を数値入力欄で OFF にする。"""
    try:
        hwnd = widget.winfo_id()
        imm32 = ctypes.WinDLL("imm32")
        h_imc = imm32.ImmGetContext(hwnd)
        if h_imc:
            imm32.ImmSetOpenStatus(h_imc, 0)
            imm32.ImmReleaseContext(hwnd, h_imc)
    except Exception:
        pass


def fmt_percent(v):
    try:
        return f"{float(v) * 100:.2f}%"
    except Exception:
        return ""


def fmt_start_month(v):
    s = (v or "").strip()
    try:
        y, m = s.split("-")
        return f"{int(y):04d} 年 {int(m):02d} 月"
    except Exception:
        return s


def _normalize_rate_text(var: tk.StringVar):
    s = var.get() or ""
    s2 = (
        s.replace("％", "%")
        .replace("．", ".")
        .replace("。", ".")
        .replace("，", ",")
        .replace(",", "")
        .strip()
    )
    if s2 != s:
        var.set(s2)


class EmpInsRateEditorDialog(tk.Toplevel):
    def __init__(self, parent, conn, start_month=None, on_saved=None):
        super().__init__(parent)
        self.conn = conn
        self.start_month = start_month
        self.on_saved = on_saved

        self.title("雇用保険料率")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.var_year = tk.StringVar()
        self.var_month = tk.StringVar()
        self.var_emp = tk.StringVar()
        self.var_er = tk.StringVar()
        self.var_note = tk.StringVar()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="適用開始月").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ym = ttk.Frame(frm)
        ym.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Entry(ym, textvariable=self.var_year, width=6).pack(side="left")
        ttk.Label(ym, text="年").pack(side="left", padx=(2, 6))
        ttk.Entry(ym, textvariable=self.var_month, width=4).pack(side="left")
        ttk.Label(ym, text="月").pack(side="left")

        ttk.Label(frm, text="従業員率").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        emp_rate_frm = ttk.Frame(frm)
        emp_rate_frm.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ent_emp = ttk.Entry(emp_rate_frm, textvariable=self.var_emp, width=10)
        ent_emp.pack(side="left")
        ttk.Label(emp_rate_frm, text="%").pack(side="left", padx=(4, 0))
        ent_emp.bind("<KeyRelease>", lambda e: _normalize_rate_text(self.var_emp))
        ent_emp.bind("<FocusIn>", lambda e: force_ime_off(ent_emp))

        ttk.Label(frm, text="会社率").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        er_rate_frm = ttk.Frame(frm)
        er_rate_frm.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ent_er = ttk.Entry(er_rate_frm, textvariable=self.var_er, width=10)
        ent_er.pack(side="left")
        ttk.Label(er_rate_frm, text="%").pack(side="left", padx=(4, 0))
        ent_er.bind("<KeyRelease>", lambda e: _normalize_rate_text(self.var_er))
        ent_er.bind("<FocusIn>", lambda e: force_ime_off(ent_er))

        ttk.Label(frm, text="メモ").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_note, width=17).grid(row=3, column=1, padx=5, pady=5, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=5, pady=(10, 0))
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")

        if self.start_month:
            self.load_rate()

        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.close())
        center_window(self, parent)
        self.after(10, lambda: self.focus_force())

    def load_rate(self):
        import db

        row = None
        for r in db.list_emp_ins_rates(self.conn):
            if r["start_month"] == self.start_month:
                row = r
                break

        if not row:
            messagebox.showerror("エラー", "雇用保険料率が見つかりません。")
            self.close()
            return

        try:
            y, m = str(row["start_month"]).split("-")
            self.var_year.set(str(int(y)))
            self.var_month.set(str(int(m)))
        except Exception:
            self.var_year.set("")
            self.var_month.set("")
        self.var_emp.set(format_rate_to_percent_text(row["employee_rate"]))
        self.var_er.set(format_rate_to_percent_text(row["employer_rate"]))
        self.var_note.set(row["note"] or "")

    def _get_start_month(self) -> str:
        year_text = (self.var_year.get() or "").strip()
        month_text = (self.var_month.get() or "").strip()

        if not year_text.isdigit() or len(year_text) != 4:
            raise ValueError("適用開始年は4桁の西暦で入力してください。")
        if not month_text.isdigit():
            raise ValueError("適用開始月は1～12で入力してください。")

        year = int(year_text)
        month = int(month_text)
        if not (1 <= month <= 12):
            raise ValueError("適用開始月は1～12で入力してください。")
        return f"{year:04d}-{month:02d}"

    def save(self):
        _normalize_rate_text(self.var_emp)
        _normalize_rate_text(self.var_er)

        try:
            start_month = self._get_start_month()
        except Exception as e:
            messagebox.showerror("入力エラー", str(e))
            return

        try:
            employee_rate = parse_percent_to_rate(self.var_emp.get())
            employer_rate = parse_percent_to_rate(self.var_er.get())
        except Exception:
            messagebox.showerror("入力エラー", "率は 0.55 または 0.55% のように「％単位」で入力してください。")
            return

        import db

        db.upsert_emp_ins_rate(
            self.conn,
            start_month,
            employee_rate,
            employer_rate,
            self.var_note.get().strip(),
        )

        if callable(self.on_saved):
            self.on_saved()

        self.close()

    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class EmpInsRateDialog(tk.Toplevel):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self.title("雇用保険料率登録・更新")
        self.geometry("650x325")
        self.transient(master)
        self.grab_set()

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(
            frm,
            columns=("start_month", "start_month_display", "employee_rate", "employer_rate", "note"),
            displaycolumns=("start_month_display", "employee_rate", "employer_rate", "note"),
            show="headings",
            height=10,
        )
        for c, t, w in [
            ("start_month_display", "適用開始月", 120),
            ("employee_rate", "従業員率(%)", 100),
            ("employer_rate", "会社率(%)", 100),
            ("note", "メモ", 260),
        ]:
            self.tree.heading(c, text=t)
            if c == "start_month_display":
                self.tree.column(c, width=w, anchor="center")
            elif c in ("employee_rate", "employer_rate"):
                self.tree.column(c, width=w, anchor="e")
            else:
                self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="新規作成", command=self.add_rate).pack(side="left", padx=5)
        ttk.Button(btns, text="編集", command=self.edit_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="削除", command=self.delete_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="閉じる", command=self.destroy).pack(side="right", padx=5)

        self.refresh()
        center_window(self, master)

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        import db

        for r in db.list_emp_ins_rates(self.conn):
            self.tree.insert(
                "",
                "end",
                values=(
                    r["start_month"],
                    fmt_start_month(r["start_month"]),
                    fmt_percent(r["employee_rate"]),
                    fmt_percent(r["employer_rate"]),
                    r["note"] or "",
                ),
            )

    def _selected_start_month(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return None
        return str(vals[0])

    def add_rate(self):
        dlg = EmpInsRateEditorDialog(self, self.conn, start_month=None, on_saved=self.refresh)
        self.wait_window(dlg)

    def edit_selected(self):
        start_month = self._selected_start_month()
        if start_month is None:
            messagebox.showinfo("確認", "行を選択してください。")
            return

        dlg = EmpInsRateEditorDialog(self, self.conn, start_month=start_month, on_saved=self.refresh)
        self.wait_window(dlg)

    def delete_selected(self):
        start_month = self._selected_start_month()
        if start_month is None:
            messagebox.showinfo("確認", "行を選択してください。")
            return

        display_month = fmt_start_month(start_month)
        if not messagebox.askyesno("削除確認", f"{display_month} の雇用保険料率を削除しますか？"):
            return

        import db

        db.delete_emp_ins_rate(self.conn, start_month)
        messagebox.showinfo("削除完了", "削除しました。")
        self.refresh()
