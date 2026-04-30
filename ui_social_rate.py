# 社会保険料設定画面
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
        return f"{float(v) * 100:.3f}%"
    except Exception:
        return ""

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

class SocialRateDialog(tk.Toplevel):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self.geometry("840x460")
        self.transient(master)
        self.grab_set()

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(
            frm,
            columns=("start_month", "pref", "health", "child", "pension", "care", "note"),
            show="headings",
            height=10
        )
        
        for c, t, w in [
            ("start_month", "適用開始月", 100),
            ("pref", "都道府県", 110),
            ("health", "健保(全体)", 110),
            ("child", "子ども･子育て(全体)", 110),
            ("pension", "厚年(全体)", 110),
            ("care", "介護(全体)", 110),
            ("note", "メモ", 240),
        ]:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True)

        # ---- 入力欄（全体料率を入力） ----
        self.title("社会保険料率（開始月つき・全体）")

        entry = ttk.LabelFrame(frm, text="登録/更新（％単位で入力：例 9.15 / 9.15%）")
        entry.pack(fill="x", pady=(10, 0))

        self.var_month = tk.StringVar()
        self.var_pref = tk.StringVar(value="DEFAULT")
        self.var_h = tk.StringVar()            # 健保（全体）
        self.var_p = tk.StringVar()            # 厚年（全体）
        self.var_c = tk.StringVar(value="0")   # 介護（全体）
        self.var_child = tk.StringVar(value="0")
        self.var_note = tk.StringVar()

        row0 = ttk.Frame(entry)
        row0.grid(row=0, column=0, columnspan=8, sticky="w")

        ttk.Label(row0, text="開始月").pack(side="left", padx=(5, 2), pady=5)
        ent_m = ttk.Entry(row0, textvariable=self.var_month, width=12, justify="right")
        ent_m.pack(side="left", padx=(0, 2), pady=5)
        ttk.Label(row0, text="(YYYY-MM)").pack(side="left", padx=(0, 5), pady=5)

        ttk.Label(row0, text="都道府県").pack(side="left", padx=(12, 2), pady=5)
        ttk.Combobox(
            row0,
            textvariable=self.var_pref,
            values=[
                "DEFAULT",
                "北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県",
                "茨城県","栃木県","群馬県","埼玉県","千葉県","東京都","神奈川県",
                "新潟県","富山県","石川県","福井県","山梨県","長野県",
                "岐阜県","静岡県","愛知県","三重県",
                "滋賀県","京都府","大阪府","兵庫県","奈良県","和歌山県",
                "鳥取県","島根県","岡山県","広島県","山口県",
                "徳島県","香川県","愛媛県","高知県",
                "福岡県","佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県"
            ],
            width=14,
            state="readonly"
        ).pack(side="left", padx=(0, 5), pady=5)

        ttk.Label(entry, text="健保(全体)").grid(row=1, column=0, padx=(8, 2), pady=5, sticky="w")
        ent_h = ttk.Entry(entry, textvariable=self.var_h, width=12, justify="right")
        ent_h.grid(row=1, column=1, padx=(0, 8), pady=5, sticky="w")
        ent_h.bind("<KeyRelease>", lambda e: _normalize_rate_text(self.var_h))
        ent_h.bind("<FocusIn>", lambda e: force_ime_off(ent_h))

        ttk.Label(entry, text="介護(全体)").grid(row=1, column=2, padx=(8, 2), pady=5, sticky="w")
        ent_c = ttk.Entry(entry, textvariable=self.var_c, width=12, justify="right")
        ent_c.grid(row=1, column=3, padx=(0, 8), pady=5, sticky="w")
        ent_c.bind("<KeyRelease>", lambda e: _normalize_rate_text(self.var_c))
        ent_c.bind("<FocusIn>", lambda e: force_ime_off(ent_c))

        ttk.Label(entry, text="子ども･子育て(全体)").grid(row=1, column=4, padx=(8, 2), pady=5, sticky="w")
        ent_child = ttk.Entry(entry, textvariable=self.var_child, width=12, justify="right")
        ent_child.grid(row=1, column=5, padx=(0, 8), pady=5, sticky="w")
        ent_child.bind("<KeyRelease>", lambda e: _normalize_rate_text(self.var_child))
        ent_child.bind("<FocusIn>", lambda e: force_ime_off(ent_child))
        
        ttk.Label(entry, text="厚年(全体)").grid(row=1, column=6, padx=(8, 2), pady=5, sticky="w")
        ent_p = ttk.Entry(entry, textvariable=self.var_p, width=12, justify="right")
        ent_p.grid(row=1, column=7, padx=(0, 8), pady=5, sticky="w")
        ent_p.bind("<KeyRelease>", lambda e: _normalize_rate_text(self.var_p))
        ent_p.bind("<FocusIn>", lambda e: force_ime_off(ent_p))

        row_note = ttk.Frame(entry)
        row_note.grid(row=2, column=0, columnspan=8, sticky="w")

        ttk.Label(row_note, text="メモ").pack(side="left", padx=(5, 2), pady=5)
        ttk.Entry(row_note, textvariable=self.var_note, width=50, justify="right").pack(
            side="left", padx=(0, 5), pady=5
        )

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="選択行を読み込み", command=self.load_selected).pack(side="left")
        ttk.Button(btns, text="保存（追加/更新）", command=self.save).pack(side="right")

        self.refresh()
        center_window(self, master)

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        import db
        rows = db.list_social_ins_rates(self.conn)

        for r in rows:
            health_total = float(r["health_employee"] or 0) * 2
            child_total = float(r["childcare_employee"] or 0) * 2
            pension_total = float(r["pension_employee"] or 0) * 2
            care_total_display = health_total + (float(r["care_employee"] or 0) * 2)

            self.tree.insert("", "end", values=(
                r["start_month"],
                r["prefecture_name"] or "DEFAULT",
                fmt_percent(health_total),
                fmt_percent(child_total),
                fmt_percent(pension_total),
                fmt_percent(care_total_display),
                r["note"] or "",
            ))

    def load_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("確認", "行を選択してください。")
            return

        v = self.tree.item(sel[0])["values"]

        self.var_month.set(v[0])
        self.var_pref.set(v[1])
        self.var_h.set(str(v[2]).replace("%", ""))
        self.var_child.set(str(v[3]).replace("%", ""))
        self.var_p.set(str(v[4]).replace("%", ""))
        self.var_c.set(str(v[5]).replace("%", ""))
        self.var_note.set(v[6])

    def save(self):
        _normalize_rate_text(self.var_h)
        _normalize_rate_text(self.var_p)
        _normalize_rate_text(self.var_c)
        _normalize_rate_text(self.var_child)
 
        m = self.var_month.get().strip()
        if len(m) != 7 or m[4] != "-":
            messagebox.showerror("入力エラー", "開始月は YYYY-MM 形式で入力してください。")
            return
        try:
            h_total = parse_percent_to_rate(self.var_h.get())        # 健保のみ全体率
            p_total = parse_percent_to_rate(self.var_p.get())        # 厚年全体率
            care_total_display = parse_percent_to_rate(self.var_c.get())   # 介護対象者の健保込み全体率
            child_total = parse_percent_to_rate(self.var_child.get())      # 子ども･子育て全体率

            # 介護の実計算用率 = 介護欄 - 健保欄
            care_only_total = care_total_display - h_total

            if care_only_total < 0:
                messagebox.showerror(
                    "入力エラー",
                    "介護(全体) は 健保(全体) 以上で入力してください。"
                )
                return

            # 本人負担は全体の1/2
            h = round(h_total / 2.0, 10)
            p = round(p_total / 2.0, 10)
            c = round(care_only_total / 2.0, 10)
            child_emp = round(child_total / 2.0, 10)
            child_er = round(child_total / 2.0, 10)

        except Exception:
            messagebox.showerror("入力エラー", "料率は 9.15 または 9.15% のように「％単位」で入力してください。")
            return

        import db
        db.upsert_social_ins_rate(
            self.conn,
            m,
            self.var_pref.get().strip() or "DEFAULT",
            h,
            p,
            c,
            child_emp,
            child_er,
            self.var_note.get().strip()
        )

        messagebox.showinfo("保存完了", "保存しました。")
        self.refresh()
