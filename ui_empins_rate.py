# 雇用保険料設定画面

import ctypes
import tkinter as tk
from tkinter import ttk, messagebox
from utils_rates import parse_percent_to_rate, format_rate_to_percent_text
from ui_window_utils import center_window

def force_ime_off(widget):
    """
    WindowsのIMEをOFF（英数）に寄せる。
    率入力欄だけ英数にしたい用途向け。
    """
    try:
        hwnd = widget.winfo_id()
        imm32 = ctypes.WinDLL("imm32")
        h_imc = imm32.ImmGetContext(hwnd)
        if h_imc:
            imm32.ImmSetOpenStatus(h_imc, 0)  # 0=OFF
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

def _to_float_rate(s: str) -> float:
    s = (s or "").strip()
    if s == "":
        return 0.0

    # IME/全角・よくある記号を正規化
    s = (s.replace("％", "%")
           .replace("．", ".")
           .replace("。", ".")
           .replace("，", ",")
           .replace(",", "")
           .strip())

    # % は許容
    s = s.replace("%", "").strip()

    # 末尾が '.' で終わる等、変換途中の形は安全に扱う
    if s == ".":
        return 0.0
    if s.endswith("."):
        s = s[:-1]  # "0." -> "0" として読む

    v = float(s)

    # 4.995 や 9.15 を入力したら % とみなす
    if v > 1.0:
        v = v / 100.0

    return v

def _normalize_rate_text(var: tk.StringVar):
    s = var.get() or ""
    s2 = (s.replace("．", ".")
        .replace("。", ".")
        .replace("，", ",")
        .replace(",", "")
        .replace("％", "%")
        .strip())
    if s2 != s:
        var.set(s2)

class EmpInsRateDialog(tk.Toplevel):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self.title("雇用保険料率登録・更新")
        self.geometry("650x420")
        self.transient(master)
        self.grab_set()

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(frm, columns=("start_month", "employee_rate", "employer_rate", "note"), show="headings", height=10)
        for c, t, w in [
            ("start_month", "適用開始月", 120),
            ("employee_rate", "従業員率(%)", 100),
            ("employer_rate", "会社率(%)", 100),
            ("note", "メモ", 260),
        ]:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w)
            if c == "start_month":
                self.tree.column(c, width=w, anchor="center")
            elif c in ("employee_rate", "employer_rate"):
                self.tree.column(c, width=w, anchor="e")
            else:
                self.tree.column(c, width=w, anchor="w")            
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.load_selected())

        entry = ttk.LabelFrame(frm, text="登録/更新（％単位で入力：例 0.55 / 0.55%）")
        entry.pack(fill="x", pady=(10, 0))

        self.var_year = tk.StringVar()
        self.var_month = tk.StringVar()
        self.var_emp = tk.StringVar()
        self.var_er = tk.StringVar()
        self.var_note = tk.StringVar()

        # --- row 0 : 適用開始月 + 従業員率 ---
        ttk.Label(entry, text="適用開始月") \
            .grid(row=0, column=0, padx=1, pady=5, sticky="w")

        # 年・月をまとめる Frame
        ym = ttk.Frame(entry)
        ym.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Entry(ym, textvariable=self.var_year, width=6).pack(side="left")
        ttk.Label(ym, text="年").pack(side="left", padx=(2, 6))
        ttk.Entry(ym, textvariable=self.var_month, width=4).pack(side="left")
        ttk.Label(ym, text="月").pack(side="left")

        # 従業員率も Frame 化
        rate_h = ttk.Frame(entry)
        rate_h.grid(row=0, column=2, padx=(12, 0), pady=5, sticky="w")
        ttk.Label(rate_h, text="従業員率").pack(side="left", padx=(0, 2))
        ent_h = ttk.Entry(rate_h, textvariable=self.var_emp, width=6)
        ent_h.pack(side="left")
        ent_h.bind("<KeyRelease>", lambda e: _normalize_rate_text(self.var_emp))
        ent_h.bind("<FocusIn>", lambda e: force_ime_off(ent_h))

        # 会社率（従業員率の右）
        rate_er = ttk.Frame(entry)
        rate_er.grid(row=0, column=3, padx=(12, 0), pady=5, sticky="w")
        ttk.Label(rate_er, text="会社率").pack(side="left", padx=(0, 2))
        ent_er = ttk.Entry(rate_er, textvariable=self.var_er, width=6)
        ent_er.pack(side="left")
        ent_er.bind("<KeyRelease>", lambda e: _normalize_rate_text(self.var_er))
        ent_er.bind("<FocusIn>", lambda e: force_ime_off(ent_er))

        # --- row 2 : メモ ---
        ttk.Label(entry, text="メモ") \
            .grid(row=2, column=0, padx=1, pady=5, sticky="w")
        ttk.Entry(entry, textvariable=self.var_note, width=54) \
            .grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="w")


        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="閉じる", command=self.destroy).pack(side="right")
        ttk.Button(btns, text="削除", command=self.delete_selected).pack(side="right", padx=5)
        ttk.Button(btns, text="保存", command=self.save).pack(side="right", padx=5)
 
        self.refresh()
        center_window(self, master)

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        import db
        rows = db.list_emp_ins_rates(self.conn)
        for r in rows:
            self.tree.insert("", "end", values=(
                fmt_start_month(r["start_month"]),
                fmt_percent(r["employee_rate"]),
                fmt_percent(r["employer_rate"]),
                r["note"] or "",
            ))

    def load_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        v = self.tree.item(sel[0])["values"]
        display_month = str(v[0]).strip()
        raw = display_month.replace("年", "-").replace("月", "").replace(" ", "")
        parts = [x for x in raw.split("-") if x]
        if len(parts) >= 2:
            y, m = parts[0], parts[1]
        else:
            y, m = "", ""
        self.var_year.set(y)
        self.var_month.set(m)
        self.var_emp.set(v[1].replace("%", ""))
        self.var_er.set(v[2].replace("%", ""))
        self.var_note.set(v[3] if len(v) >= 4 else "")

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
            m = self._get_start_month()
        except Exception as e:
            messagebox.showerror("入力エラー", str(e))
            return
        try:
            # 仕様：常に「%」として解釈する（例：0.55 → 0.55% → 0.0055）
            emp = parse_percent_to_rate(self.var_emp.get())
            er = parse_percent_to_rate(self.var_er.get())
        except Exception:
            messagebox.showerror("入力エラー", "率は 0.55 または 0.55% のように「％単位」で入力してください。")
            return

        import db
        db.upsert_emp_ins_rate(self.conn, m, emp, er, self.var_note.get().strip())
        messagebox.showinfo("保存完了", "保存しました。")
        self.refresh()

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("確認", "行を選択してください。")
            return

        v = self.tree.item(sel[0])["values"]
        display_month = str(v[0])
        try:
            raw = display_month.replace("年", "-").replace("月", "").replace(" ", "")
            parts = [x for x in raw.split("-") if x]
            start_month = f"{int(parts[0]):04d}-{int(parts[1]):02d}"
        except Exception:
            messagebox.showerror("削除エラー", "適用開始月の読み取りに失敗しました。")
            return

        if not messagebox.askyesno("削除確認", f"{display_month} の雇用保険料率を削除しますか？"):
            return

        import db
        db.delete_emp_ins_rate(self.conn, start_month)
        messagebox.showinfo("削除完了", "削除しました。")
        self.refresh()
