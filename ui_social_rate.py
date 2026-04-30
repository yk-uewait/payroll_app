# 社会保険料設定画面

import ctypes
import tkinter as tk
from tkinter import ttk, messagebox

from ui_window_utils import center_window
from utils_rates import parse_percent_to_rate, format_rate_to_percent_text


PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
    "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
    "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県",
    "福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]


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
        return f"{float(v) * 100:.3f}%"
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


def _rate_input(parent, row, label, var):
    ttk.Label(parent, text=label).grid(row=row, column=0, padx=5, pady=5, sticky="w")
    rate_frm = ttk.Frame(parent)
    rate_frm.grid(row=row, column=1, padx=5, pady=5, sticky="w")
    ent = ttk.Entry(rate_frm, textvariable=var, width=12, justify="right")
    ent.pack(side="left")
    ttk.Label(rate_frm, text="%").pack(side="left", padx=(4, 0))
    ent.bind("<KeyRelease>", lambda e: _normalize_rate_text(var))
    ent.bind("<FocusIn>", lambda e: force_ime_off(ent))
    return ent


class SocialRateEditorDialog(tk.Toplevel):
    def __init__(self, parent, conn, start_month=None, prefecture_name=None, on_saved=None):
        super().__init__(parent)
        self.conn = conn
        self.start_month = start_month
        self.prefecture_name = prefecture_name
        self.on_saved = on_saved

        self.title("社会保険料率")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.var_year = tk.StringVar()
        self.var_month = tk.StringVar()
        self.var_pref = tk.StringVar(value=PREFECTURES[0])
        self.var_h = tk.StringVar()
        self.var_c = tk.StringVar()
        self.var_child = tk.StringVar()
        self.var_p = tk.StringVar()
        self.var_note = tk.StringVar()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="適用開始月").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        month_frm = ttk.Frame(frm)
        month_frm.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Entry(month_frm, textvariable=self.var_year, width=6, justify="right").pack(side="left")
        ttk.Label(month_frm, text="年").pack(side="left", padx=(2, 6))
        ttk.Entry(month_frm, textvariable=self.var_month, width=4, justify="right").pack(side="left")
        ttk.Label(month_frm, text="月").pack(side="left", padx=(2, 0))

        ttk.Label(frm, text="都道府県").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Combobox(
            frm,
            textvariable=self.var_pref,
            values=PREFECTURES,
            width=14,
            state="readonly",
        ).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        _rate_input(frm, 2, "健康保険(全体)", self.var_h)
        _rate_input(frm, 3, "介護(全体)", self.var_c)
        _rate_input(frm, 4, "子ども・子育て(全体)", self.var_child)
        _rate_input(frm, 5, "厚年(全体)", self.var_p)

        ttk.Label(frm, text="メモ").grid(row=6, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_note, width=17).grid(row=6, column=1, padx=5, pady=5, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=2, sticky="e", padx=5, pady=(10, 0))
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")

        if self.start_month and self.prefecture_name:
            self.load_rate()

        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.close())
        center_window(self, parent)
        self.after(10, lambda: self.focus_force())

    def load_rate(self):
        import db

        row = None
        for r in db.list_social_ins_rates(self.conn):
            if r["start_month"] == self.start_month and (r["prefecture_name"] or "DEFAULT") == self.prefecture_name:
                row = r
                break

        if not row:
            messagebox.showerror("エラー", "社会保険料率が見つかりません。")
            self.close()
            return

        health_total = float(row["health_employee"] or 0) * 2
        child_total = float(row["childcare_employee"] or 0) * 2
        pension_total = float(row["pension_employee"] or 0) * 2
        care_total_display = health_total + (float(row["care_employee"] or 0) * 2)

        try:
            y, m = str(row["start_month"]).split("-")
            self.var_year.set(str(int(y)))
            self.var_month.set(str(int(m)))
        except Exception:
            self.var_year.set("")
            self.var_month.set("")
        self.var_pref.set(row["prefecture_name"] if row["prefecture_name"] in PREFECTURES else PREFECTURES[0])
        self.var_h.set(format_rate_to_percent_text(health_total, decimals=3))
        self.var_c.set(format_rate_to_percent_text(care_total_display, decimals=3))
        self.var_child.set(format_rate_to_percent_text(child_total, decimals=3))
        self.var_p.set(format_rate_to_percent_text(pension_total, decimals=3))
        self.var_note.set(row["note"] or "")

    def save(self):
        _normalize_rate_text(self.var_h)
        _normalize_rate_text(self.var_p)
        _normalize_rate_text(self.var_c)
        _normalize_rate_text(self.var_child)

        year_text = self.var_year.get().strip()
        month_text = self.var_month.get().strip()
        if not year_text.isdigit() or len(year_text) != 4:
            messagebox.showerror("入力エラー", "適用開始年は4桁の西暦で入力してください。")
            return
        if not month_text.isdigit():
            messagebox.showerror("入力エラー", "適用開始月は1～12で入力してください。")
            return
        year = int(year_text)
        month = int(month_text)
        if not (1 <= month <= 12):
            messagebox.showerror("入力エラー", "適用開始月は1～12で入力してください。")
            return
        start_month = f"{year:04d}-{month:02d}"

        try:
            health_total = parse_percent_to_rate(self.var_h.get())
            pension_total = parse_percent_to_rate(self.var_p.get())
            care_total_display = parse_percent_to_rate(self.var_c.get())
            child_total = parse_percent_to_rate(self.var_child.get())

            care_only_total = care_total_display - health_total
            if care_only_total < 0:
                messagebox.showerror("入力エラー", "介護(全体) は 健康保険(全体) 以上で入力してください。")
                return

            health_employee = round(health_total / 2.0, 10)
            pension_employee = round(pension_total / 2.0, 10)
            care_employee = round(care_only_total / 2.0, 10)
            childcare_employee = round(child_total / 2.0, 10)
            childcare_employer = round(child_total / 2.0, 10)

        except Exception:
            messagebox.showerror("入力エラー", "料率は 9.15 または 9.15% のように「％単位」で入力してください。")
            return

        import db

        db.upsert_social_ins_rate(
            self.conn,
            start_month,
            self.var_pref.get().strip() or PREFECTURES[0],
            health_employee,
            pension_employee,
            care_employee,
            childcare_employee,
            childcare_employer,
            0.0,
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


class SocialRateDialog(tk.Toplevel):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self.title("社会保険料率の設定")
        self.geometry("840x325")
        self.transient(master)
        self.grab_set()

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(
            frm,
            columns=("start_month", "start_month_display", "pref", "health", "child", "pension", "care", "note"),
            displaycolumns=("start_month_display", "pref", "health", "child", "pension", "care", "note"),
            show="headings",
            height=10,
        )

        for c, t, w in [
            ("start_month_display", "適用開始月", 120),
            ("pref", "都道府県", 72),
            ("health", "健保(全体)", 100),
            ("child", "子ども・子育て(全体)", 130),
            ("pension", "厚年(全体)", 100),
            ("care", "介護(全体)", 100),
            ("note", "メモ", 190),
        ]:
            self.tree.heading(c, text=t)
            if c in ("health", "child", "pension", "care"):
                anchor = "e"
            elif c == "note":
                anchor = "w"
            else:
                anchor = "center"
            self.tree.column(c, width=w, anchor=anchor, stretch=(c == "note"))
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

        for r in db.list_social_ins_rates(self.conn):
            health_total = float(r["health_employee"] or 0) * 2
            child_total = float(r["childcare_employee"] or 0) * 2
            pension_total = float(r["pension_employee"] or 0) * 2
            care_total_display = health_total + (float(r["care_employee"] or 0) * 2)

            self.tree.insert(
                "",
                "end",
                values=(
                    r["start_month"],
                    fmt_start_month(r["start_month"]),
                    r["prefecture_name"] or "DEFAULT",
                    fmt_percent(health_total),
                    fmt_percent(child_total),
                    fmt_percent(pension_total),
                    fmt_percent(care_total_display),
                    r["note"] or "",
                ),
            )

    def _selected_key(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return None
        return str(vals[0]), str(vals[2] or "DEFAULT")

    def add_rate(self):
        dlg = SocialRateEditorDialog(self, self.conn, on_saved=self.refresh)
        self.wait_window(dlg)

    def edit_selected(self):
        key = self._selected_key()
        if key is None:
            messagebox.showinfo("確認", "行を選択してください。")
            return

        start_month, prefecture_name = key
        dlg = SocialRateEditorDialog(
            self,
            self.conn,
            start_month=start_month,
            prefecture_name=prefecture_name,
            on_saved=self.refresh,
        )
        self.wait_window(dlg)

    def delete_selected(self):
        key = self._selected_key()
        if key is None:
            messagebox.showinfo("確認", "行を選択してください。")
            return

        start_month, prefecture_name = key
        if not messagebox.askyesno("削除確認", f"{start_month} {prefecture_name} の社会保険料率を削除しますか？"):
            return

        import db

        db.delete_social_ins_rate(self.conn, start_month, prefecture_name)
        messagebox.showinfo("削除完了", "削除しました。")
        self.refresh()
