import tkinter as tk
from tkinter import ttk, messagebox
from ui_window_utils import center_window

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
    月次給与の入力値（支給・控除・自由枠属性）を編集するダイアログ
    """
    def __init__(self, master, conn, payroll_id: int, pay_free_names: list[str] | None = None, deduct_free_names: list[str] | None = None):
        super().__init__(master)
        self.conn = conn
        self.payroll_id = payroll_id

        self.title("月次入力の編集")
        self.geometry("900x750")
        self.resizable(True, True)
        self.transient(master)
        self.grab_set()

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

        self.tab_pay = ttk.Frame(nb)
        self.tab_deduct = ttk.Frame(nb)
        self.tab_note = ttk.Frame(nb)
        nb.add(self.tab_pay, text="支給")
        nb.add(self.tab_deduct, text="控除")
        nb.add(self.tab_note, text="備考")

        self._build_pay_tab()
        self._build_deduct_tab()
        self._build_note_tab()

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
        ttk.Button(footer, text="キャンセル", command=self.destroy).pack(side="right", padx=5)

        self._update_totals()
        center_window(self, master)

    def _build_pay_tab(self):
        self.money_entries = []
        frm = ttk.Frame(self.tab_pay)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

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
        title = "動的支給明細（参考入力）" if item_kind == "pay" else "動的控除明細（参考入力）"
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

        fixed = ttk.LabelFrame(frm, text="控除（確定金額を入力）")
        fixed.pack(fill="x", pady=(0,10))

        def add_money_row(parent, r, label, key):
            ttk.Label(parent, text=label).grid(row=r, column=0, padx=5, pady=5, sticky="w")
            v = tk.StringVar(value=str(self.row[key]))
            ent = ttk.Entry(parent, textvariable=v, width=18)
            ent.grid(row=r, column=1, padx=5, pady=5, sticky="w")
            ent.bind("<KeyRelease>", self._update_totals)
            self.money_entries.append(ent)
            ttk.Label(parent, text="円").grid(row=r, column=2, padx=5, pady=5, sticky="w")
            self.vars[key] = v

        add_money_row(fixed, 0, "旅行積立金（常設）", "travel_saving")

        # 住民税（自動反映＋上書き）
        res = ttk.LabelFrame(frm, text="住民税（通知額の自動反映＋上書き）")
        res.pack(fill="x", pady=(10, 10))

        auto_val = int(self.row["resident_tax_auto"]) if "resident_tax_auto" in self.row.keys() else 0
        ttk.Label(res, text=f"自動（通知額）：{auto_val:,}円").grid(row=0, column=0, padx=5, pady=5, sticky="w")

        ttk.Label(res, text="上書き（任意）").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        init_override = ""
        if "resident_tax_override" in self.row.keys() and self.row["resident_tax_override"] is not None:
            init_override = str(int(self.row["resident_tax_override"]))

        self.var_resident_override = tk.StringVar(value=init_override)
        ent_res = ttk.Entry(res, textvariable=self.var_resident_override, width=18)
        ent_res.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ent_res.bind("<KeyRelease>", self._update_totals)  # 入力のたびに合計更新

        ttk.Label(res, text="円").grid(row=1, column=2, padx=5, pady=5, sticky="w")

        ttk.Label(res, text="上書き理由（任意）").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        init_reason = ""
        if "resident_tax_override_reason" in self.row.keys() and self.row["resident_tax_override_reason"]:
            init_reason = self.row["resident_tax_override_reason"]

        self.var_resident_reason = tk.StringVar(value=init_reason)
        ttk.Entry(res, textvariable=self.var_resident_reason, width=50).grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="w")

        ttk.Button(res, text="上書きを解除（自動に戻す）", command=self._clear_resident_override).grid(row=1, column=3, padx=5, pady=5, sticky="w")

                # 所得税（源泉）（自動反映＋上書き）
        wh = ttk.LabelFrame(frm, text="所得税（源泉）（自動反映＋上書き）")
        wh.pack(fill="x", pady=(10, 10))

        auto_wh = int(self.row["withholding_tax_auto"]) if "withholding_tax_auto" in self.row.keys() else 0
        ttk.Label(wh, text=f"自動：{auto_wh:,}円").grid(row=0, column=0, padx=5, pady=5, sticky="w")

        ttk.Label(wh, text="上書き（任意）").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        init_wh_override = ""
        if "withholding_tax_override" in self.row.keys() and self.row["withholding_tax_override"] is not None:
            init_wh_override = str(int(self.row["withholding_tax_override"]))

        self.var_withholding_override = tk.StringVar(value=init_wh_override)
        ent_wh = ttk.Entry(wh, textvariable=self.var_withholding_override, width=18)
        ent_wh.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ent_wh.bind("<KeyRelease>", self._update_totals)
        ttk.Label(wh, text="円").grid(row=1, column=2, padx=5, pady=5, sticky="w")

        ttk.Label(wh, text="上書き理由（任意）").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        init_wh_reason = ""
        if "withholding_tax_override_reason" in self.row.keys() and self.row["withholding_tax_override_reason"]:
            init_wh_reason = self.row["withholding_tax_override_reason"]

        self.var_withholding_reason = tk.StringVar(value=init_wh_reason)
        ttk.Entry(wh, textvariable=self.var_withholding_reason, width=50).grid(
            row=2, column=1, columnspan=3, padx=5, pady=5, sticky="w"
        )

        ttk.Button(wh, text="上書きを解除（自動に戻す）", command=self._clear_withholding_override).grid(
            row=1, column=3, padx=5, pady=5, sticky="w"
        )

        free = ttk.LabelFrame(frm, text="その他控除（5枠）")
        free.pack(fill="x")

        for i in range(1, 6):
            name = self.deduct_free_names[i-1]
            add_money_row(free, i-1, name, f"deduct_free{i}")

        self._build_dynamic_items_section(frm, "deduction")

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
                data[k] = _to_int(self.vars[k].get())

            # チェックボックス（0/1）
            for i in range(1, 6):
                data[f"pay_free{i}_is_taxable"] = int(self.vars[f"pay_free{i}_is_taxable"].get())
                data[f"pay_free{i}_is_social_base"] = int(self.vars[f"pay_free{i}_is_social_base"].get())
                data[f"pay_free{i}_is_employment_base"] = int(self.vars[f"pay_free{i}_is_employment_base"].get())

            data["note"] = self.txt_note.get("1.0", "end").strip()

        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            return

        import db
        dynamic_data = {}
        fixed_sync = {}
        fixed_sync_codes = {"officer_pay", "base_salary", "overtime_pay", "commute_nontax"}
        try:
            for item_id, meta in self.dynamic_item_sources.items():
                if not isinstance(item_id, int):
                    continue
                if meta.get("locked"):
                    continue
                item = meta["item"]
                amount = _to_int(self.dynamic_item_vars[item_id].get())
                dynamic_data[item_id] = (item, amount, meta.get("source") or "manual")
                if item["code"] in fixed_sync_codes:
                    fixed_sync[item["code"]] = amount
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            return

        for key, amount in fixed_sync.items():
            if key in data:
                data[key] = amount

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
        self.destroy()
