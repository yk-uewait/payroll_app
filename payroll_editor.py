import tkinter as tk
from tkinter import ttk, messagebox
import app_settings
from ui_window_utils import center_window, enable_enter_key_navigation

def _to_int(s: str) -> int:
    s = (s or "").strip()
    if s == "":
        return 0
    # カンマ入力も許可（例：100,000）
    s = s.replace(",", "")
    try:
        return int(s)
    except ValueError:
        raise ValueError(f"数値として解釈できません: {s}")

class PayrollEditorDialog(tk.Toplevel):
    """
    給与の入力値（支給・控除・自由枠属性）を編集するダイアログ
    """
    def __init__(self, master, conn, payroll_id: int, pay_free_names: list[str] | None = None, deduct_free_names: list[str] | None = None):
        super().__init__(master)
        self.conn = conn
        self.payroll_id = payroll_id

        self.title("給与入力の編集")
        self.geometry(app_settings.get_window_geometry("payroll_editor"))
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

        import db
        self.row = db.get_payroll_by_id(conn, payroll_id)
        if not self.row:
            messagebox.showerror("エラー", "対象データが見つかりません。")
            self.destroy()
            return
        self.dynamic_item_vars = {}
        self.dynamic_item_sources = {}

        # 表示名（後でSettings化する。今回は暫定で固定）
        self.pay_free_names = pay_free_names or [f"支給自由{i}" for i in range(1, 6)]
        self.deduct_free_names = deduct_free_names or [f"控除自由{i}" for i in range(1, 6)]

        header = ttk.LabelFrame(self, text="対象")
        header.pack(fill="x", padx=10, pady=10)

        ttk.Label(header, text=f"社員番号: {self.row['employee_code']}").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(header, text=f"氏名: {self.row['name_kanji']}").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(header, text=f"部署: {self.row['department']}").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Label(header, text=f"対象月: {self.row['target_month']}").grid(row=0, column=3, padx=5, pady=5, sticky="w")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        # Notebookで「支給」「控除」「備考」
        nb = ttk.Notebook(body)
        nb.pack(fill="both", expand=True)

        self._active_scroll_canvas = None
        self.tab_pay = self._create_scrollable_tab(nb, "支給")
        self.tab_deduct = self._create_scrollable_tab(nb, "控除")
        self.tab_note = self._create_scrollable_tab(nb, "備考")

        self._build_pay_tab()
        self._build_deduct_tab()
        self._build_note_tab()
        self._bind_tab_scroll_events(self.tab_pay, self.tab_pay._scroll_canvas)
        self._bind_tab_scroll_events(self.tab_deduct, self.tab_deduct._scroll_canvas)
        self._bind_tab_scroll_events(self.tab_note, self.tab_note._scroll_canvas)

        # 入力合計（ダイアログ下部に固定表示）
        summary = ttk.LabelFrame(self, text="入力合計（税・社保はまだ）")
        summary.pack(fill="x", padx=10, pady=(0, 10))

        self.lbl_total_pay = ttk.Label(summary, text="総支給：0円")
        self.lbl_total_deduct = ttk.Label(summary, text="控除合計：0円")
        self.lbl_net = ttk.Label(summary, text="手取り：0円")
        self.lbl_dynamic_pay = ttk.Label(summary, text="動的支給合計（参考）：0円")
        self.lbl_dynamic_taxable = ttk.Label(summary, text="動的課税支給額（参考）：0円")
        self.lbl_dynamic_nontax = ttk.Label(summary, text="動的非課税支給額（参考）：0円")
        self.lbl_dynamic_emp_base = ttk.Label(summary, text="動的雇用保険対象額（参考）：0円")
        self.lbl_dynamic_social_base = ttk.Label(summary, text="動的社会保険対象額（参考）：0円")
        self.lbl_dynamic_custom_deduct = ttk.Label(summary, text="動的会社独自控除合計（参考）：0円")

        self.lbl_total_pay.pack(anchor="w", padx=10, pady=2)
        self.lbl_total_deduct.pack(anchor="w", padx=10, pady=2)
        self.lbl_net.pack(anchor="w", padx=10, pady=2)
        ttk.Separator(summary, orient="horizontal").pack(fill="x", padx=10, pady=4)
        self.lbl_dynamic_pay.pack(anchor="w", padx=10, pady=1)
        self.lbl_dynamic_taxable.pack(anchor="w", padx=10, pady=1)
        self.lbl_dynamic_nontax.pack(anchor="w", padx=10, pady=1)
        self.lbl_dynamic_emp_base.pack(anchor="w", padx=10, pady=1)
        self.lbl_dynamic_social_base.pack(anchor="w", padx=10, pady=1)
        self.lbl_dynamic_custom_deduct.pack(anchor="w", padx=10, pady=1)

        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=10, pady=10)
        ttk.Button(footer, text="保存", command=self.save).pack(side="right", padx=5)
        ttk.Button(footer, text="キャンセル", command=self._close).pack(side="right", padx=5)

        self._update_dynamic_totals()
        enable_enter_key_navigation(self)
        center_window(self, master)

    def _create_scrollable_tab(self, notebook, title: str):
        outer = ttk.Frame(notebook)
        notebook.add(outer, text=title)

        canvas = tk.Canvas(outer, highlightthickness=0)
        v_scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        h_scroll = ttk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        inner = ttk.Frame(canvas)
        inner._scroll_canvas = canvas
        canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def update_scrollregion(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_inner(event):
            canvas.itemconfigure(
                canvas_window,
                width=max(event.width, inner.winfo_reqwidth()),
                height=max(event.height, inner.winfo_reqheight()),
            )
            update_scrollregion()

        inner.bind("<Configure>", update_scrollregion)
        canvas.bind("<Configure>", resize_inner)

        for widget in (outer, canvas, inner):
            widget.bind("<Enter>", lambda event, c=canvas: self._activate_tab_scroll(c))
            widget.bind("<Leave>", lambda event: self._deactivate_tab_scroll())

        return inner

    def _activate_tab_scroll(self, canvas):
        self._active_scroll_canvas = canvas
        self.bind_all("<MouseWheel>", self._on_tab_mousewheel)
        self.bind_all("<Shift-MouseWheel>", self._on_tab_shift_mousewheel)
        self.bind_all("<Button-4>", self._on_tab_mousewheel)
        self.bind_all("<Button-5>", self._on_tab_mousewheel)

    def _deactivate_tab_scroll(self):
        self._active_scroll_canvas = None
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Shift-MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def _close(self):
        self._deactivate_tab_scroll()
        self.destroy()

    def _on_tab_mousewheel(self, event):
        canvas = self._active_scroll_canvas
        if canvas is None:
            return
        if getattr(event, "num", None) == 4:
            canvas.yview_scroll(-3, "units")
        elif getattr(event, "num", None) == 5:
            canvas.yview_scroll(3, "units")
        else:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _on_tab_shift_mousewheel(self, event):
        canvas = self._active_scroll_canvas
        if canvas is None:
            return
        canvas.xview_scroll(int(-10 * (event.delta / 120)), "units")
        return "break"

    def _bind_tab_scroll_events(self, widget, canvas):
        widget.bind("<MouseWheel>", lambda event, c=canvas: self._scroll_canvas_y(c, event), add="+")
        widget.bind("<Shift-MouseWheel>", lambda event, c=canvas: self._scroll_canvas_x(c, event), add="+")
        widget.bind("<Button-4>", lambda event, c=canvas: self._scroll_canvas_y(c, event), add="+")
        widget.bind("<Button-5>", lambda event, c=canvas: self._scroll_canvas_y(c, event), add="+")
        for child in widget.winfo_children():
            self._bind_tab_scroll_events(child, canvas)

    def _scroll_canvas_y(self, canvas, event):
        if getattr(event, "num", None) == 4:
            canvas.yview_scroll(-3, "units")
        elif getattr(event, "num", None) == 5:
            canvas.yview_scroll(3, "units")
        else:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _scroll_canvas_x(self, canvas, event):
        canvas.xview_scroll(int(-10 * (event.delta / 120)), "units")
        return "break"

    def _build_pay_tab(self):
        self.money_entries = []
        frm = ttk.Frame(self.tab_pay)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        self.vars = {}
        self._build_dynamic_items_section(frm, "pay")
        return

        # 固定支給
        fixed = ttk.LabelFrame(frm, text="固定支給（確定金額を入力）")
        fixed.pack(fill="x", pady=(0,10))

        self.vars = {}  # まとめて保持

        def add_money_row(parent, r, label, key):
            ttk.Label(parent, text=label).grid(row=r, column=0, padx=5, pady=5, sticky="w")
            v = tk.StringVar(value=str(self.row[key]))
            ent = ttk.Entry(parent, textvariable=v, width=18)
            ent.grid(row=r, column=1, padx=5, pady=5, sticky="w")
            ent.bind("<KeyRelease>", self._update_totals)
            self.money_entries.append(ent)
            ttk.Label(parent, text="円").grid(row=r, column=2, padx=5, pady=5, sticky="w")
            self.vars[key] = v

        add_money_row(fixed, 0, "役員報酬", "officer_pay")
        add_money_row(fixed, 1, "基本給", "base_salary")
        add_money_row(fixed, 2, "みなし残業手当", "deemed_ot")
        add_money_row(fixed, 3, "残業手当", "overtime_pay")
        add_money_row(fixed, 4, "特別手当", "special_allow")
        add_money_row(fixed, 5, "非課税交通費", "commute_nontax")

        # 自由支給＋属性
        free = ttk.LabelFrame(frm, text="自由支給（5枠）＋属性")
        free.pack(fill="both", expand=True)

        ttk.Label(free, text="項目").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(free, text="金額").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(free, text="課税").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Label(free, text="社保対象").grid(row=0, column=3, padx=5, pady=5, sticky="w")
        ttk.Label(free, text="雇保対象").grid(row=0, column=4, padx=5, pady=5, sticky="w")

        for i in range(1, 6):
            name = self.pay_free_names[i-1]
            key_amt = f"pay_free{i}"
            key_tax = f"pay_free{i}_is_taxable"
            key_soc = f"pay_free{i}_is_social_base"
            key_emp = f"pay_free{i}_is_employment_base"

            ttk.Label(free, text=name).grid(row=i, column=0, padx=5, pady=5, sticky="w")

            v_amt = tk.StringVar(value=str(self.row[key_amt]))
            ent = ttk.Entry(free, textvariable=v_amt, width=18)
            ent.grid(row=i, column=1, padx=5, pady=5, sticky="w")
            ent.bind("<KeyRelease>", self._update_totals)
            self.money_entries.append(ent)
            self.vars[key_amt] = v_amt


            v_tax = tk.IntVar(value=int(self.row[key_tax]))
            v_soc = tk.IntVar(value=int(self.row[key_soc]))
            v_emp = tk.IntVar(value=int(self.row[key_emp]))
            ttk.Checkbutton(free, variable=v_tax).grid(row=i, column=2, padx=5, pady=5, sticky="w")
            ttk.Checkbutton(free, variable=v_soc).grid(row=i, column=3, padx=5, pady=5, sticky="w")
            ttk.Checkbutton(free, variable=v_emp).grid(row=i, column=4, padx=5, pady=5, sticky="w")

            self.vars[key_tax] = v_tax
            self.vars[key_soc] = v_soc
            self.vars[key_emp] = v_emp

        # “よくある組合せ”ボタン（初心者向け）
        preset = ttk.Frame(frm)
        preset.pack(fill="x", pady=(10,0))
        # 合計表示（入力ベース）
        self._build_dynamic_items_section(frm, "pay")

    def _apply_preset(self, taxable: bool, social: bool, emp: bool):
        for i in range(1, 6):
            self.vars[f"pay_free{i}_is_taxable"].set(1 if taxable else 0)
            self.vars[f"pay_free{i}_is_social_base"].set(1 if social else 0)
            self.vars[f"pay_free{i}_is_employment_base"].set(1 if emp else 0)

    def _build_dynamic_items_section(self, parent, item_kind: str):
        import db

        items = [r for r in db.get_applicable_payroll_items(self.conn, int(self.row["employee_id"])) if r["item_kind"] == item_kind]
        title = "支給項目" if item_kind == "pay" else "その他控除項目"
        section = ttk.LabelFrame(parent, text=title)
        section.pack(fill="x", pady=(10, 0))

        if not items:
            ttk.Label(section, text="該当する項目はありません。").grid(row=0, column=0, padx=5, pady=5, sticky="w")
            return

        ttk.Label(section, text="項目").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(section, text="金額").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(section, text="状態").grid(row=0, column=3, padx=5, pady=5, sticky="w")

        saved_map = db.get_payroll_monthly_item_value_map(self.conn, self.payroll_id)
        target_month = self.row["target_month"]
        total_var = tk.StringVar(value="0")
        self.dynamic_item_vars[(item_kind, "_total")] = total_var

        for idx, item in enumerate(items, start=1):
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
                    amount = int(self.row[item["code"]] or 0)

            ttk.Label(section, text=item["name"]).grid(row=idx, column=0, padx=5, pady=4, sticky="w")
            var = tk.StringVar(value=str(amount))
            ent = ttk.Entry(section, textvariable=var, width=16, justify="right")
            ent.grid(row=idx, column=1, padx=5, pady=4, sticky="w")
            ttk.Label(section, text="円").grid(row=idx, column=2, padx=5, pady=4, sticky="w")
            status = "ロック" if locked else ("保存済" if saved else "標準/0")
            ttk.Label(section, text=status).grid(row=idx, column=3, padx=5, pady=4, sticky="w")
            if locked:
                ent.configure(state="disabled")
            var.trace_add("write", lambda *_: self._update_dynamic_totals())
            self.dynamic_item_vars[item_id] = var
            self.dynamic_item_sources[item_id] = {"item": item, "source": source, "locked": locked, "entry": ent}

        ttk.Label(section, text="合計").grid(row=len(items) + 1, column=0, padx=5, pady=(8, 5), sticky="e")
        ttk.Label(section, textvariable=total_var).grid(row=len(items) + 1, column=1, padx=5, pady=(8, 5), sticky="e")
        ttk.Label(section, text="円").grid(row=len(items) + 1, column=2, padx=5, pady=(8, 5), sticky="w")
        self._update_dynamic_totals()

    def _build_deduct_tab(self):
        frm = ttk.Frame(self.tab_deduct)
        frm.pack(fill="both", expand=True, padx=10, pady=10)
        self._build_tax_section(frm)
        self._build_dynamic_items_section(frm, "deduction")
        return

    def _build_tax_section(self, parent):
        section = ttk.LabelFrame(parent, text="税額")
        section.pack(fill="x", pady=(0, 10))

        def applied_value(applied_key, override_key):
            if override_key in self.row.keys() and self.row[override_key] is not None:
                return str(int(self.row[override_key] or 0))
            return str(int(self.row[applied_key] or 0)) if applied_key in self.row.keys() else "0"

        self.var_withholding_override = tk.StringVar(
            value=applied_value("withholding_tax_applied", "withholding_tax_override")
        )
        self.var_resident_override = tk.StringVar(
            value=applied_value("resident_tax_applied", "resident_tax_override")
        )
        self.var_withholding_reason = tk.StringVar(
            value=self.row["withholding_tax_override_reason"] if "withholding_tax_override_reason" in self.row.keys() and self.row["withholding_tax_override_reason"] else ""
        )
        self.var_resident_reason = tk.StringVar(
            value=self.row["resident_tax_override_reason"] if "resident_tax_override_reason" in self.row.keys() and self.row["resident_tax_override_reason"] else ""
        )

        for row_idx, (label, var) in enumerate((
            ("所得税", self.var_withholding_override),
            ("住民税", self.var_resident_override),
        )):
            ttk.Label(section, text=label).grid(row=row_idx, column=0, padx=5, pady=5, sticky="w")
            ent = ttk.Entry(section, textvariable=var, width=18, justify="right")
            ent.grid(row=row_idx, column=1, padx=5, pady=5, sticky="w")
            ent.bind("<KeyRelease>", self._update_dynamic_totals)
            ttk.Label(section, text="円").grid(row=row_idx, column=2, padx=5, pady=5, sticky="w")
            if label == "住民税":
                ttk.Button(section, text="住民税設定", command=self._open_resident_tax_annual).grid(
                    row=row_idx, column=3, padx=8, pady=5, sticky="w"
                )

    def _open_resident_tax_annual(self):
        from ui_resident_tax_annual import ResidentTaxAnnualFrame

        win = tk.Toplevel(self)
        win.title("住民税年次一括入力")
        win.geometry("1180x620")
        win.transient(self)
        frame = ResidentTaxAnnualFrame(win, self.conn)
        frame.pack(fill="both", expand=True)
        enable_enter_key_navigation(win)

    def _build_note_tab(self):
        frm = ttk.Frame(self.tab_note)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frm, text="備考（給与明細に出す予定のメモ）").pack(anchor="w")
        self.txt_note = tk.Text(frm, height=12)
        self.txt_note.pack(fill="both", expand=True, pady=(5,0))
        self.txt_note.insert("1.0", self.row["note"] or "")

    def _update_totals(self, event=None):
        def safe_int_by_key(key: str) -> int:
            var = self.vars.get(key)
            if var is None:
                return 0
            try:
                return _to_int(var.get())
            except Exception:
                return 0

        pay_keys = [
            "officer_pay", "base_salary", "deemed_ot", "overtime_pay", "special_allow", "commute_nontax",
            "pay_free1", "pay_free2", "pay_free3", "pay_free4", "pay_free5",
        ]
        deduct_keys = [
            "travel_saving", "deduct_free1", "deduct_free2", "deduct_free3", "deduct_free4", "deduct_free5",
        ]

        total_pay = sum(safe_int_by_key(k) for k in pay_keys)
        # 住民税（画面の上書きがあればそれ、無ければ自動値）
        resident_tax = 0
        if hasattr(self, "var_resident_override"):
            txt = (self.var_resident_override.get() or "").strip()
            if txt != "":
                try:
                    resident_tax = _to_int(txt)
                except Exception:
                    resident_tax = 0
            else:
                # 自動値
                if "resident_tax_auto" in self.row.keys():
                    resident_tax = int(self.row["resident_tax_auto"] or 0)

                # 所得税（源泉）
        withholding_tax = 0
        if hasattr(self, "var_withholding_override"):
            txt = (self.var_withholding_override.get() or "").strip()
            if txt != "":
                try:
                    withholding_tax = _to_int(txt)
                except Exception:
                    withholding_tax = 0
            else:
                if "withholding_tax_auto" in self.row.keys():
                    withholding_tax = int(self.row["withholding_tax_auto"] or 0)

        total_deduct = sum(safe_int_by_key(k) for k in deduct_keys) + resident_tax + withholding_tax
        net = total_pay - total_deduct

        self.lbl_total_pay.config(text=f"総支給：{total_pay:,}円")
        self.lbl_total_deduct.config(text=f"控除合計：{total_deduct:,}円")
        self.lbl_net.config(text=f"手取り：{net:,}円")

    def _update_dynamic_totals(self):
        totals = {
            "pay": 0,
            "deduction": 0,
            "taxable_pay": 0,
            "non_taxable_pay": 0,
            "employment_insurance_base": 0,
            "social_insurance_base": 0,
        }
        for item_id, meta in self.dynamic_item_sources.items():
            if not isinstance(item_id, int):
                continue
            item = meta["item"]
            var = self.dynamic_item_vars.get(item_id)
            if not var:
                continue
            try:
                amount = _to_int(var.get())
            except Exception:
                amount = 0
            item_kind = item["item_kind"]
            if item_kind in {"pay", "deduction"}:
                totals[item_kind] += amount
            if item_kind == "pay":
                if int(item["is_taxable"] or 0):
                    totals["taxable_pay"] += amount
                else:
                    totals["non_taxable_pay"] += amount
                if int(item["is_employment_insurance_base"] or 0):
                    totals["employment_insurance_base"] += amount
                if int(item["is_social_insurance_base"] or 0):
                    totals["social_insurance_base"] += amount
        for kind in ("pay", "deduction"):
            amount = totals[kind]
            total_var = self.dynamic_item_vars.get((kind, "_total"))
            if total_var:
                total_var.set(f"{amount:,}")
        if hasattr(self, "lbl_dynamic_pay"):
            try:
                income_tax = _to_int(self.var_withholding_override.get()) if hasattr(self, "var_withholding_override") else 0
            except Exception:
                income_tax = 0
            try:
                resident_tax = _to_int(self.var_resident_override.get()) if hasattr(self, "var_resident_override") else 0
            except Exception:
                resident_tax = 0
            total_deduction = totals["deduction"] + income_tax + resident_tax
            self.lbl_total_pay.config(text=f"支給合計：{totals['pay']:,}円")
            self.lbl_total_deduct.config(text=f"控除合計：{total_deduction:,}円")
            self.lbl_net.config(text=f"差引支給額：{totals['pay'] - total_deduction:,}円")
            self.lbl_dynamic_pay.config(text=f"動的支給合計（参考）：{totals['pay']:,}円")
            self.lbl_dynamic_taxable.config(text=f"動的課税支給額（参考）：{totals['taxable_pay']:,}円")
            self.lbl_dynamic_nontax.config(text=f"動的非課税支給額（参考）：{totals['non_taxable_pay']:,}円")
            self.lbl_dynamic_emp_base.config(text=f"動的雇用保険対象額（参考）：{totals['employment_insurance_base']:,}円")
            self.lbl_dynamic_social_base.config(text=f"動的社会保険対象額（参考）：{totals['social_insurance_base']:,}円")
            self.lbl_dynamic_custom_deduct.config(text=f"動的会社独自控除合計（参考）：{totals['deduction']:,}円")

    def _clear_resident_override(self):
        # 上書き入力を空にする（保存時に自動へ戻る）
        if hasattr(self, "var_resident_override"):
            self.var_resident_override.set("")
        if hasattr(self, "var_resident_reason"):
            self.var_resident_reason.set("")
        self._update_totals()

    def _clear_withholding_override(self):
        if hasattr(self, "var_withholding_override"):
            self.var_withholding_override.set("")
        if hasattr(self, "var_withholding_reason"):
            self.var_withholding_reason.set("")
        self._update_totals()

    def save(self):
        # 入力を辞書にまとめて、DBへ保存
        try:
            data = {}
            money_keys = [
                "officer_pay", "base_salary", "deemed_ot", "overtime_pay", "special_allow", "commute_nontax",
                "pay_free1", "pay_free2", "pay_free3", "pay_free4", "pay_free5",
                "travel_saving", "deduct_free1", "deduct_free2", "deduct_free3", "deduct_free4", "deduct_free5",
            ]
            for k in money_keys:
                data[k] = 0

            # チェックボックス（0/1）
            for i in range(1, 6):
                data[f"pay_free{i}_is_taxable"] = 0
                data[f"pay_free{i}_is_social_base"] = 0
                data[f"pay_free{i}_is_employment_base"] = 0

            data["note"] = self.txt_note.get("1.0", "end").strip()

        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            return

        import db
        dynamic_data = {}
        try:
            for item_id, meta in self.dynamic_item_sources.items():
                if not isinstance(item_id, int):
                    continue
                if meta.get("locked"):
                    continue
                item = meta["item"]
                amount = _to_int(self.dynamic_item_vars[item_id].get())
                dynamic_data[item_id] = (item, amount, meta.get("source") or "manual")
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            return

        db.update_payroll_inputs(self.conn, self.payroll_id, data)
        try:
            year, month = [int(x) for x in str(self.row["target_month"]).split("-")]
            for item_id, (item, amount, source) in dynamic_data.items():
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
            messagebox.showerror("保存エラー", f"動的支給控除明細の保存に失敗しました。\n{e}")
            return
        try:
            db.recalc_target_month(self.conn, str(self.row["target_month"]))
        except Exception as e:
            messagebox.showwarning("再計算エラー", f"保存後の自動再計算でエラーが発生しました。\n{e}")
        # 住民税 上書きの反映（空なら解除＝自動へ）
        override_text = (self.var_resident_override.get() or "").strip() if hasattr(self, "var_resident_override") else ""
        reason_text = (self.var_resident_reason.get() or "").strip() if hasattr(self, "var_resident_reason") else ""

        if override_text == "":
            db.override_resident_tax(self.conn, self.payroll_id, None, None)
        else:
            override_amount = _to_int(override_text)
            db.override_resident_tax(self.conn, self.payroll_id, override_amount, reason_text)
        
        # 所得税（源泉） 上書きの反映（空なら解除＝自動へ）
        wh_override_text = (self.var_withholding_override.get() or "").strip() if hasattr(self, "var_withholding_override") else ""
        wh_reason_text = (self.var_withholding_reason.get() or "").strip() if hasattr(self, "var_withholding_reason") else ""

        if wh_override_text == "":
            db.override_withholding_tax(self.conn, self.payroll_id, None, None)
        else:
            wh_override_amount = _to_int(wh_override_text)
            db.override_withholding_tax(self.conn, self.payroll_id, wh_override_amount, wh_reason_text)

        messagebox.showinfo("保存完了", "保存しました。")
        self._close()
