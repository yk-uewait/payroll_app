import tkinter as tk
from tkinter import ttk, messagebox
from ui_window_utils import show_centered_window, enable_enter_key_navigation

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

class _LegacyEmployeeEditorDialog(tk.Toplevel):
    def __init__(self, parent, conn, employee_id: int, on_saved=None):
        super().__init__(parent)
        self.withdraw()
        self.conn = conn
        self.employee_id = employee_id
        self.on_saved = on_saved

        self.title("社員編集")
        self.resizable(False, False)
        self.transient(parent)   # 親の上に表示
        self.grab_set()          # モーダル化

        # 変数
        self.var_code = tk.StringVar()
        self.var_name = tk.StringVar()
        self.var_dept = tk.StringVar()
        self.var_department_id = tk.StringVar()
        self.var_position_id = tk.StringVar()
        self.var_employment_type_id = tk.StringVar()
        self.department_options = []
        self.position_options = []
        self.employment_type_options = []
        self.var_payment_schedule_id = tk.StringVar()
        self.payment_schedule_options = []
        self.var_std_health = tk.StringVar(value="0")
        self.var_std_pension = tk.StringVar(value="0")
        self.var_social_insurance_target = tk.IntVar(value=0)
        self.var_employment_insurance_target = tk.IntVar(value=1)
        self.var_tax_type = tk.StringVar(value="甲")
        self.var_dependents = tk.IntVar(value=0)
        self.var_pref = tk.StringVar()
        self.var_address_city = tk.StringVar()
        self.var_address_detail = tk.StringVar()
        self.var_birth_y = tk.StringVar()
        self.var_birth_m = tk.StringVar()
        self.var_birth_d = tk.StringVar()
        self.var_hire_y = tk.StringVar()
        self.var_hire_m = tk.StringVar()
        self.var_hire_d = tk.StringVar()
        self.var_leave_y = tk.StringVar()
        self.var_leave_m = tk.StringVar()
        self.var_leave_d = tk.StringVar()
        self.var_retirement_processed = tk.IntVar(value=0)
        self.txt_memo = None

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        # フォーム
        ttk.Label(frm, text="社員番号").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        e_code = ttk.Entry(frm, textvariable=self.var_code, width=20)
        e_code.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(frm, text="氏名").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.var_name, width=20).grid(row=0, column=3, sticky="w", padx=5, pady=5)

        ttk.Label(frm, text="部署・事業所").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.cmb_department = ttk.Combobox(
            frm,
            textvariable=self.var_department_id,
            values=self.load_named_master_options("departments", self.department_options),
            width=28,
            state="readonly",
        )
        self.cmb_department.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(frm, text="給与支給方式").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        self.cmb_payment_schedule = ttk.Combobox(
            frm,
            textvariable=self.var_payment_schedule_id,
            values=self.load_payment_schedule_options(),
            width=18,
            state="readonly"
        )
        self.cmb_payment_schedule.grid(row=1, column=3, sticky="w", padx=5, pady=5)

        ttk.Label(frm, text="源泉区分").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Combobox(frm, values=["甲", "乙"], textvariable=self.var_tax_type, width=5, state="readonly")\
            .grid(row=2, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(frm, text="扶養人数").grid(row=2, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.var_dependents, width=6, justify="right")\
            .grid(row=2, column=3, sticky="w", padx=5, pady=5)        

        ttk.Label(frm, text="役職").grid(row=9, column=0, sticky="w", padx=5, pady=5)
        self.cmb_position = ttk.Combobox(
            frm,
            textvariable=self.var_position_id,
            values=self.load_named_master_options("positions", self.position_options),
            width=18,
            state="readonly",
        )
        self.cmb_position.grid(row=9, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(frm, text="雇用区分").grid(row=9, column=2, sticky="w", padx=5, pady=5)
        self.cmb_employment_type = ttk.Combobox(
            frm,
            textvariable=self.var_employment_type_id,
            values=self.load_named_master_options("employment_types", self.employment_type_options),
            width=18,
            state="readonly",
        )
        self.cmb_employment_type.grid(row=9, column=3, sticky="w", padx=5, pady=5)

        ttk.Label(frm, text="標準報酬月額（健保）").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.var_std_health, width=20, justify="right")\
            .grid(row=3, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(frm, text="標準報酬月額（厚年）").grid(row=3, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.var_std_pension, width=20, justify="right")\
            .grid(row=3, column=3, sticky="w", padx=5, pady=5)
        
        ttk.Label(frm, text="所属都道府県").grid(row=4, column=0, sticky="w", padx=5, pady=5)

        ttk.Combobox(
            frm,
            textvariable=self.var_pref,
            values=[
                "北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県",
                "茨城県","栃木県","群馬県","埼玉県","千葉県","東京都","神奈川県",
                "新潟県","富山県","石川県","福井県","山梨県","長野県",
                "岐阜県","静岡県","愛知県","三重県",
                "滋賀県","京都府","大阪府","兵庫県","奈良県","和歌山県",
                "鳥取県","島根県","岡山県","広島県","山口県",
                "徳島県","香川県","愛媛県","高知県",
                "福岡県","佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県"
            ],
            width=20,
            state="readonly"
        ).grid(row=4, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(frm, text="市区町村").grid(row=4, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.var_address_city, width=20).grid(row=4, column=3, sticky="w", padx=5, pady=5)

        ttk.Label(frm, text="それ以降の住所").grid(row=5, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.var_address_detail, width=52).grid(row=5, column=1, columnspan=3, sticky="ew", padx=5, pady=5)

        ttk.Label(frm, text="生年月日").grid(row=6, column=0, sticky="w", padx=5, pady=5)
        birth_frm = ttk.Frame(frm)
        birth_frm.grid(row=6, column=1, sticky="w", padx=5, pady=5)
        ttk.Entry(birth_frm, textvariable=self.var_birth_y, width=6, justify="right").pack(side="left")
        ttk.Label(birth_frm, text="年").pack(side="left", padx=(2, 8))
        ttk.Entry(birth_frm, textvariable=self.var_birth_m, width=4, justify="right").pack(side="left")
        ttk.Label(birth_frm, text="月").pack(side="left", padx=(2, 8))
        ttk.Entry(birth_frm, textvariable=self.var_birth_d, width=4, justify="right").pack(side="left")
        ttk.Label(birth_frm, text="日").pack(side="left", padx=(2, 0))

        ttk.Label(frm, text="入社日").grid(row=7, column=0, sticky="w", padx=5, pady=5)
        hire_frm = ttk.Frame(frm)
        hire_frm.grid(row=7, column=1, sticky="w", padx=5, pady=5)
        ttk.Entry(hire_frm, textvariable=self.var_hire_y, width=6, justify="right").pack(side="left")
        ttk.Label(hire_frm, text="年").pack(side="left", padx=(2, 8))
        ttk.Entry(hire_frm, textvariable=self.var_hire_m, width=4, justify="right").pack(side="left")
        ttk.Label(hire_frm, text="月").pack(side="left", padx=(2, 8))
        ttk.Entry(hire_frm, textvariable=self.var_hire_d, width=4, justify="right").pack(side="left")
        ttk.Label(hire_frm, text="日").pack(side="left", padx=(2, 0))

        ttk.Label(frm, text="退職日").grid(row=7, column=2, sticky="w", padx=5, pady=5)
        leave_frm = ttk.Frame(frm)
        leave_frm.grid(row=7, column=3, sticky="w", padx=5, pady=5)
        ttk.Entry(leave_frm, textvariable=self.var_leave_y, width=6, justify="right").pack(side="left")
        ttk.Label(leave_frm, text="年").pack(side="left", padx=(2, 8))
        ttk.Entry(leave_frm, textvariable=self.var_leave_m, width=4, justify="right").pack(side="left")
        ttk.Label(leave_frm, text="月").pack(side="left", padx=(2, 8))
        ttk.Entry(leave_frm, textvariable=self.var_leave_d, width=4, justify="right").pack(side="left")
        ttk.Label(leave_frm, text="日").pack(side="left", padx=(2, 0))
        ttk.Checkbutton(leave_frm, text="退職処理済み", variable=self.var_retirement_processed)\
            .pack(side="left", padx=(14, 0))

        ttk.Label(frm, text="メモ").grid(row=8, column=0, sticky="nw", padx=5, pady=5)
        self.txt_memo = tk.Text(frm, width=48, height=3, wrap="word")
        self.txt_memo.grid(row=8, column=1, columnspan=3, sticky="ew", padx=5, pady=5)

        # ボタン
        btns = ttk.Frame(frm)
        btns.grid(row=10, column=0, columnspan=4, sticky="e", padx=5, pady=(10, 0))
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")

        # 読み込み
        if self.employee_id:
            self.load_employee()

        # 編集は社員番号を基本変更不可にしたい場合はここで disabled にする
        # e_code.configure(state="disabled")

        # Enterで保存
        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.close())

        # フォーカス
        enable_enter_key_navigation(self)
        show_centered_window(self, parent)
        self.after(10, lambda: self.focus_force())

    def load_payment_schedule_options(self):
        import db

        rows = db.list_payment_schedules(self.conn)
        self.payment_schedule_options = []
        for r in rows:
            label = r["schedule_name"]
            self.payment_schedule_options.append((label, r["payment_schedule_id"]))
        return [x[0] for x in self.payment_schedule_options]

    def load_named_master_options(self, table: str, target_options: list):
        import db

        target_options.clear()
        target_options.append(("", None))
        if table == "departments":
            rows = db.list_department_hierarchy(self.conn, include_inactive=False)
            for r in rows:
                target_options.append((r["full_name"], r["id"]))
        else:
            rows = db.list_named_master(self.conn, table)
            for r in rows:
                target_options.append((r["name"], r["id"]))
        return [x[0] for x in target_options]

    def _selected_master_id(self, var: tk.StringVar, options: list):
        selected = var.get().strip()
        for label, row_id in options:
            if label == selected:
                return row_id
        return None

    def _set_master_by_id(self, var: tk.StringVar, options: list, row_id):
        if not row_id:
            var.set("")
            return
        for label, option_id in options:
            if option_id and int(option_id) == int(row_id):
                var.set(label)
                return
        var.set("")

    def _split_date_to_vars(self, date_str, var_y, var_m, var_d):
        if not date_str:
            var_y.set("")
            var_m.set("")
            var_d.set("")
            return
        try:
            y, m, d = date_str.split("-")
            var_y.set(str(int(y)))
            var_m.set(str(int(m)))
            var_d.set(str(int(d)))
        except Exception:
            var_y.set("")
            var_m.set("")
            var_d.set("")

    def _build_date_from_vars(self, var_y, var_m, var_d):
        y = (var_y.get() or "").strip()
        m = (var_m.get() or "").strip()
        d = (var_d.get() or "").strip()

        if not y and not m and not d:
            return None

        if not y or not m or not d:
            raise ValueError("日付が途中までしか入力されていません。")

        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    def _parse_money_var(self, var: tk.StringVar) -> int:
        text = (var.get() or "").replace(",", "").strip()
        if text == "":
            return 0
        if not text.isdigit():
            raise ValueError("標準報酬月額は数字で入力してください。")
        return int(text)

    def _reset_dirty_state(self):
        return None

    def get_selected_payment_schedule_id(self):
        selected_label = self.var_payment_schedule_id.get().strip()
        for label, schedule_id in self.payment_schedule_options:
            if label == selected_label:
                return schedule_id
        return None

    def set_payment_schedule_by_id(self, payment_schedule_id):
        if not payment_schedule_id:
            self.var_payment_schedule_id.set("")
            return

        for label, schedule_id in self.payment_schedule_options:
            if int(schedule_id) == int(payment_schedule_id):
                self.var_payment_schedule_id.set(label)
                return

        self.var_payment_schedule_id.set("")

    def load_employee(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT employee_id, employee_code, name_kanji, department, department_id, position_id, employment_type_id,
                   payday_group, payment_schedule_id, work_prefecture_name,
                   COALESCE(address_city, '') AS address_city,
                   COALESCE(address_detail, '') AS address_detail,
                   COALESCE(std_monthly_wage, 0) AS std_monthly_wage,
                   COALESCE(std_pension_wage, 0) AS std_pension_wage,
                   COALESCE(is_social_insurance_target, 0) AS is_social_insurance_target,
                   COALESCE(is_employment_insurance_target, 1) AS is_employment_insurance_target,
                   COALESCE(tax_type, '甲') AS tax_type,
                   COALESCE(dependents_count, 0) AS dependents_count,
                   birth_date,
                   hire_date,
                   leave_date,
                   COALESCE(retirement_processed, 0) AS retirement_processed,
                   memo
            FROM employees
            WHERE employee_id = ?
            """,
            (self.employee_id,),
        )
        r = cur.fetchone()
        if not r:
            messagebox.showerror("エラー", "社員情報が見つかりません。")
            self.close()
            return

        self.var_code.set(r["employee_code"])
        self.var_name.set(r["name_kanji"])
        self.var_dept.set(r["department"] or "")
        self._set_master_by_id(self.var_department_id, self.department_options, r["department_id"] if "department_id" in r.keys() else None)
        self._set_master_by_id(self.var_position_id, self.position_options, r["position_id"] if "position_id" in r.keys() else None)
        self._set_master_by_id(self.var_employment_type_id, self.employment_type_options, r["employment_type_id"] if "employment_type_id" in r.keys() else None)
        if r["payment_schedule_id"]:
            self.set_payment_schedule_by_id(r["payment_schedule_id"])
        else:
            old_payday = int(r["payday_group"] or 25)
            for label, schedule_id in self.payment_schedule_options:
                if "25" in label and old_payday == 25:
                    self.var_payment_schedule_id.set(label)
                    break
                if "15" in label and old_payday == 15:
                    self.var_payment_schedule_id.set(label)
                    break
        self.var_std_health.set(f'{int(r["std_monthly_wage"] or 0):,}')
        self.var_std_pension.set(f'{int(r["std_pension_wage"] or 0):,}')
        self.var_social_insurance_target.set(int(r["is_social_insurance_target"] or 0))
        self.var_employment_insurance_target.set(int(r["is_employment_insurance_target"] or 0))
        self.var_tax_type.set(r["tax_type"] or "甲")
        self.var_dependents.set(int(r["dependents_count"] or 0))
        self.var_pref.set(r["work_prefecture_name"] or "")
        self.var_address_city.set(r["address_city"] or "")
        self.var_address_detail.set(r["address_detail"] or "")
        self._split_date_to_vars(r["birth_date"], self.var_birth_y, self.var_birth_m, self.var_birth_d)
        self._split_date_to_vars(r["hire_date"], self.var_hire_y, self.var_hire_m, self.var_hire_d)
        self._split_date_to_vars(r["leave_date"], self.var_leave_y, self.var_leave_m, self.var_leave_d)
        self.var_retirement_processed.set(int(r["retirement_processed"] or 0))
        self.txt_memo.delete("1.0", "end")
        self.txt_memo.insert("1.0", r["memo"] or "")
        self._reset_dirty_state()

    def save(self):
        import db
        try:
            code = db.normalize_employee_code(self.var_code.get())
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e), parent=self)
            return
        self.var_code.set(code)
        name = self.var_name.get().strip()
        department_id = self._selected_master_id(self.var_department_id, self.department_options)
        position_id = self._selected_master_id(self.var_position_id, self.position_options)
        employment_type_id = self._selected_master_id(self.var_employment_type_id, self.employment_type_options)
        dept = self.var_department_id.get().strip()
        payment_schedule_id = self.get_selected_payment_schedule_id()

        try:
            std_health = self._parse_money_var(self.var_std_health)
            std_pension = self._parse_money_var(self.var_std_pension)
            tax_type = self.var_tax_type.get().strip() or "甲"
            deps = int(self.var_dependents.get() or 0)
            pref = self.var_pref.get().strip()
            address_city = self.var_address_city.get().strip()
            address_detail = self.var_address_detail.get().strip()
            birth = self._build_date_from_vars(self.var_birth_y, self.var_birth_m, self.var_birth_d)
            hire_date = self._build_date_from_vars(self.var_hire_y, self.var_hire_m, self.var_hire_d)
            leave_date = self._build_date_from_vars(self.var_leave_y, self.var_leave_m, self.var_leave_d)
            retirement_processed = int(self.var_retirement_processed.get() or 0)
            memo = self.txt_memo.get("1.0", "end-1c").strip() or None

        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            return
        except Exception:
            messagebox.showerror("入力エラー", "標準報酬月額または日付の入力内容を確認してください。")
            return

        if not code or not name:
            messagebox.showerror("入力エラー", "社員番号と氏名は必須です。")
            return
        
        if not payment_schedule_id:
            messagebox.showerror("入力エラー", "給与支給方式を選択してください。")
            return

        from datetime import datetime

        for label, value in [
            ("生年月日", birth),
            ("入社日", hire_date),
            ("退職日", leave_date),
        ]:
            if value:
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except Exception:
                    messagebox.showerror("入力エラー", f"{label}は yyyy-mm-dd 形式で入力してください。")
                    return

        # 入社日・退職日の前後関係チェック
        if hire_date and leave_date:
            hire_dt = datetime.strptime(hire_date, "%Y-%m-%d").date()
            leave_dt = datetime.strptime(leave_date, "%Y-%m-%d").date()
            if leave_dt < hire_dt:
                messagebox.showerror("入力エラー", "退職日は入社日以降の日付を入力してください。")
                return
        
        if birth and hire_date:
            birth_dt = datetime.strptime(birth, "%Y-%m-%d").date()
            hire_dt = datetime.strptime(hire_date, "%Y-%m-%d").date()
            if hire_dt <= birth_dt:
                messagebox.showerror("入力エラー", "入社日は生年月日より後の日付を入力してください。")
                return

        duplicate = self.conn.execute(
            """
            SELECT employee_id
            FROM employees
            WHERE employee_code = ?
              AND COALESCE(is_deleted, 0) = 0
              AND (? IS NULL OR employee_id <> ?)
            """,
            (code, self.employee_id, self.employee_id),
        ).fetchone()
        if duplicate:
            messagebox.showerror("入力エラー", "同じ社員番号の社員が既に登録されています。", parent=self)
            return

        try:
            db.upsert_employee(
                self.conn,
                code, name, dept, 0,
                std_health, std_pension,
                tax_type, deps, pref,
                address_city,
                address_detail,
                birth,
                payment_schedule_id,
                hire_date,
                leave_date=leave_date,
                retirement_processed=retirement_processed,
                memo=memo,
                department_id=department_id,
                position_id=position_id,
                employment_type_id=employment_type_id,
                employee_id=self.employee_id,
            )
        except Exception as e:
            messagebox.showerror("保存エラー", str(e), parent=self)
            return

        if callable(self.on_saved):
            self.on_saved()

        self.close()

    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

class EmployeeEditorDialog(tk.Toplevel):
    def __init__(self, parent, conn, employee_id: int, on_saved=None, employee_filter="active"):
        super().__init__(parent)
        self.withdraw()
        self.conn = conn
        self.employee_id = employee_id
        self.employee_filter = employee_filter or "active"
        self.on_saved = on_saved
        self.title("社員編集")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.var_code = tk.StringVar()
        self.var_name = tk.StringVar()
        self.var_name_kana = tk.StringVar()
        self.var_department_id = tk.StringVar()
        self.var_position_id = tk.StringVar()
        self.var_employment_type_id = tk.StringVar()
        self.department_options = []
        self.position_options = []
        self.employment_type_options = []
        self.var_payment_schedule_id = tk.StringVar()
        self.payment_schedule_options = []
        self.var_std_health = tk.StringVar(value="0")
        self.var_std_pension = tk.StringVar(value="0")
        self.var_social_insurance_target = tk.IntVar(value=0)
        self.var_employment_insurance_target = tk.IntVar(value=1)
        self.var_tax_type = tk.StringVar(value="甲")
        self.var_dependents = tk.IntVar(value=0)
        self.var_social_prefecture = tk.StringVar()
        self.var_address_postal_code = tk.StringVar()
        self.var_address_prefecture = tk.StringVar()
        self.var_address_city = tk.StringVar()
        self.var_address_detail = tk.StringVar()
        self.var_resident_tax_municipality = tk.StringVar()
        self.var_phone = tk.StringVar()
        self.var_email = tk.StringVar()
        self.var_bank_name = tk.StringVar()
        self.var_bank_branch_name = tk.StringVar()
        self.var_bank_account_type = tk.StringVar()
        self.var_bank_account_number = tk.StringVar()
        self.var_bank_account_holder = tk.StringVar()
        self.var_birth_y = tk.StringVar()
        self.var_birth_m = tk.StringVar()
        self.var_birth_d = tk.StringVar()
        self.var_hire_y = tk.StringVar()
        self.var_hire_m = tk.StringVar()
        self.var_hire_d = tk.StringVar()
        self.var_on_leave = tk.IntVar(value=0)
        self.var_leave_start_y = tk.StringVar()
        self.var_leave_start_m = tk.StringVar()
        self.var_leave_start_d = tk.StringVar()
        self.var_leave_expected_end_y = tk.StringVar()
        self.var_leave_expected_end_m = tk.StringVar()
        self.var_leave_expected_end_d = tk.StringVar()
        self.var_leave_memo = tk.StringVar()
        self.var_leave_y = tk.StringVar()
        self.var_leave_m = tk.StringVar()
        self.var_leave_d = tk.StringVar()
        self.var_retirement_processed = tk.IntVar(value=0)
        self.txt_memo = None
        self._initial_state = None

        self._build_layout()
        if self.employee_id:
            self.load_employee()
        else:
            self._reset_dirty_state()
            self._update_navigation_buttons()

        self.bind("<Escape>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)
        enable_enter_key_navigation(self)
        self.geometry("640x720")
        show_centered_window(self, parent)
        self.after(10, lambda: self.focus_force())

    def _build_layout(self):
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)
        outer.grid_rowconfigure(0, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        self.notebook = ttk.Notebook(outer)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        self._tab_canvases = {}
        self._tab_forms = {}

        basic_tab, basic_form = self._create_scroll_tab("基本情報")
        payroll_tab, payroll_form = self._create_scroll_tab("給与・税社保")
        address_tab, address_form = self._create_scroll_tab("住所・振込・メモ")

        self._build_basic_section(basic_form)
        self._build_employment_section(basic_form)
        self._build_attendance_status_section(basic_form)
        self._build_insurance_target_section(payroll_form)
        self._build_payment_calc_section(payroll_form)
        self._build_social_insurance_section(payroll_form)
        self._build_income_tax_section(payroll_form)
        self._build_resident_tax_section(payroll_form)
        self._build_insurance_explanation_section(payroll_form)
        self._build_address_section(address_form)
        self._build_bank_section(address_form)
        self._build_memo_section(address_form)

        btns = ttk.Frame(outer, padding=(10, 8))
        btns.grid(row=1, column=0, sticky="ew")
        self.btn_prev_employee = ttk.Button(btns, text="前社員へ", command=lambda: self._move_employee(-1))
        self.btn_prev_employee.pack(side="left", padx=(0, 8))
        self.btn_next_employee = ttk.Button(btns, text="次社員へ", command=lambda: self._move_employee(1))
        self.btn_next_employee.pack(side="left")
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="right")
        ttk.Button(btns, text="保存", command=self.save).pack(side="right", padx=(0, 8))

    def _create_scroll_tab(self, title):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=title)
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        canvas = tk.Canvas(tab, highlightthickness=0)
        v_scroll = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        h_scroll = ttk.Scrollbar(tab, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        form = ttk.Frame(canvas, padding=10)
        window_id = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda _e, c=canvas: c.configure(scrollregion=c.bbox("all")))
        canvas.bind(
            "<Configure>",
            lambda event, c=canvas, f=form, w=window_id: c.itemconfigure(w, width=max(event.width, f.winfo_reqwidth())),
        )
        self._tab_canvases[str(tab)] = canvas
        self._tab_forms[str(tab)] = form
        self._bind_scroll(canvas)
        self._bind_scroll(form)
        return tab, form

    def _section(self, parent, title):
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.pack(fill="x", expand=True, pady=(0, 8))
        self._bind_scroll(frame)
        return frame

    def _bind_scroll(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        widget.bind("<Shift-MouseWheel>", self._on_shift_mousewheel, add="+")
        widget.bind("<Button-4>", self._on_mousewheel, add="+")
        widget.bind("<Button-5>", self._on_mousewheel, add="+")

    def _bind_new_widget(self, widget):
        self._bind_scroll(widget)
        return widget

    def _label(self, parent, text, row, column=0):
        label = ttk.Label(parent, text=text)
        label.grid(row=row, column=column, sticky="w", padx=5, pady=4)
        self._bind_scroll(label)
        return label

    def _entry(self, parent, var, row, column=1, width=22, **kwargs):
        ent = ttk.Entry(parent, textvariable=var, width=width, **kwargs)
        ent.grid(row=row, column=column, sticky="w", padx=5, pady=4)
        return self._bind_new_widget(ent)

    def _combo(self, parent, var, values, row, column=1, width=22):
        cmb = ttk.Combobox(parent, textvariable=var, values=values, width=width, state="readonly")
        cmb.grid(row=row, column=column, sticky="w", padx=5, pady=4)
        return self._bind_new_widget(cmb)

    def _date_fields(self, parent, row, column, vars_tuple):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=column, sticky="w", padx=5, pady=4)
        y, m, d = vars_tuple
        for var, suffix, width in ((y, "年", 6), (m, "月", 4), (d, "日", 4)):
            self._bind_new_widget(ttk.Entry(frame, textvariable=var, width=width, justify="right")).pack(side="left")
            self._bind_new_widget(ttk.Label(frame, text=suffix)).pack(side="left", padx=(2, 8 if suffix != "日" else 0))
        self._bind_scroll(frame)
        return frame

    def _build_basic_section(self, parent):
        frame = self._section(parent, "基本情報")
        frame.grid_columnconfigure(2, minsize=30)
        self._label(frame, "社員番号", 0, 0)
        self._entry(frame, self.var_code, 0, 1)
        self._label(frame, "氏名", 0, 3)
        self._entry(frame, self.var_name, 0, 4)
        self._label(frame, "フリガナ", 1, 0)
        self._entry(frame, self.var_name_kana, 1, 1)
        self._label(frame, "生年月日", 1, 3)
        self._date_fields(frame, 1, 4, (self.var_birth_y, self.var_birth_m, self.var_birth_d))
        self._label(frame, "入社日", 2, 0)
        self._label(frame, "退職日", 2, 3)
        chk = ttk.Checkbutton(frame, text="退職処理済み", variable=self.var_retirement_processed)
        chk.configure(text="退職処理")
        note = ttk.Label(frame, text="チェックすると退職扱いとなります", foreground="#555555")

    def _build_employment_section(self, parent):
        frame = self._section(parent, "所属・雇用")
        self._label(frame, "部署・事業所", 0, 0)
        self.cmb_department = self._combo(frame, self.var_department_id, self.load_named_master_options("departments", self.department_options), 0, 1, width=42)
        self.cmb_department.grid_configure(columnspan=3, sticky="ew")
        self._label(frame, "役職", 1, 0)
        self.cmb_position = self._combo(frame, self.var_position_id, self.load_named_master_options("positions", self.position_options), 1, 1, width=14)
        self._label(frame, "雇用区分", 1, 2)
        self.cmb_employment_type = self._combo(frame, self.var_employment_type_id, self.load_named_master_options("employment_types", self.employment_type_options), 1, 3, width=14)
        self._label(frame, "給与支給方式", 2, 0)
        self.cmb_payment_schedule = self._combo(frame, self.var_payment_schedule_id, self.load_payment_schedule_options(), 2, 1, width=22)

    def _build_basic_section(self, parent):
        frame = self._section(parent, "基本情報")
        frame.grid_columnconfigure(2, minsize=30)
        self._label(frame, "社員番号", 0, 0)
        self._entry(frame, self.var_code, 0, 1)
        self._label(frame, "氏名", 0, 3)
        self._entry(frame, self.var_name, 0, 4)
        self._label(frame, "フリガナ", 1, 0)
        self._entry(frame, self.var_name_kana, 1, 1)
        self._label(frame, "生年月日", 1, 3)
        self._date_fields(frame, 1, 4, (self.var_birth_y, self.var_birth_m, self.var_birth_d))

    def _build_attendance_status_section(self, parent):
        frame = self._section(parent, "在籍情報・休職退職情報")
        frame.grid_columnconfigure(2, minsize=30)
        self._label(frame, "入社日", 0, 0)
        self._date_fields(frame, 0, 1, (self.var_hire_y, self.var_hire_m, self.var_hire_d))
        sep1 = ttk.Separator(frame, orient="horizontal")
        sep1.grid(row=1, column=0, columnspan=5, sticky="ew", padx=5, pady=(8, 6))
        self._bind_scroll(sep1)
        self._label(frame, "休職開始日", 2, 0)
        self._date_fields(frame, 2, 1, (self.var_leave_start_y, self.var_leave_start_m, self.var_leave_start_d))
        self._label(frame, "休職終了予定日", 2, 3)
        self._date_fields(frame, 2, 4, (self.var_leave_expected_end_y, self.var_leave_expected_end_m, self.var_leave_expected_end_d))
        self._label(frame, "休職理由・メモ", 3, 0)
        self._entry(frame, self.var_leave_memo, 3, 1, width=42).grid_configure(columnspan=4, sticky="ew")
        leave_chk = ttk.Checkbutton(frame, text="休職中", variable=self.var_on_leave)
        leave_chk.grid(row=4, column=1, sticky="w", padx=5, pady=4)
        self._bind_scroll(leave_chk)
        sep2 = ttk.Separator(frame, orient="horizontal")
        sep2.grid(row=5, column=0, columnspan=5, sticky="ew", padx=5, pady=(8, 6))
        self._bind_scroll(sep2)
        self._label(frame, "退職日", 6, 0)
        self._date_fields(frame, 6, 1, (self.var_leave_y, self.var_leave_m, self.var_leave_d))
        retire_chk = ttk.Checkbutton(frame, text="退職済", variable=self.var_retirement_processed)
        retire_chk.grid(row=7, column=1, sticky="w", padx=5, pady=4)
        self._bind_scroll(retire_chk)

    def _build_payment_calc_section(self, parent):
        frame = self._section(parent, "給与計算")
        frame.grid_columnconfigure(2, minsize=30)
        self._label(frame, "標準報酬月額（健保）", 0, 0)
        ent_health = self._entry(frame, self.var_std_health, 0, 1, width=10, justify="right")
        self._bind_money_format(ent_health, self.var_std_health)
        self._label(frame, "標準報酬月額（厚年）", 0, 3)
        ent_pension = self._entry(frame, self.var_std_pension, 0, 4, width=10, justify="right")
        self._bind_money_format(ent_pension, self.var_std_pension)

    def _build_insurance_target_section(self, parent):
        frame = self._section(parent, "保険加入")
        social = ttk.Checkbutton(frame, text="社会保険加入対象", variable=self.var_social_insurance_target)
        social.grid(row=0, column=0, sticky="w", padx=5, pady=4)
        self._bind_scroll(social)
        social_note = ttk.Label(frame, text="チェックが入っている場合、標準報酬月額をもとに社会保険料を計算します。", foreground="#555555", wraplength=620)
        social_note.grid(row=1, column=0, columnspan=4, sticky="w", padx=24, pady=(0, 4))
        self._bind_scroll(social_note)

        employment = ttk.Checkbutton(frame, text="雇用保険加入対象", variable=self.var_employment_insurance_target)
        employment.grid(row=2, column=0, sticky="w", padx=5, pady=4)
        self._bind_scroll(employment)
        employment_note = ttk.Label(frame, text="チェックが入っている場合、雇用保険対象額をもとに雇用保険料を計算します。", foreground="#555555", wraplength=620)
        employment_note.grid(row=3, column=0, columnspan=4, sticky="w", padx=24, pady=(0, 4))
        self._bind_scroll(employment_note)

    def _build_social_insurance_section(self, parent):
        frame = self._section(parent, "社会保険")
        note = ttk.Label(frame, text="協会けんぽ等の社会保険料率判定に使用します。社員住所ではありません。", foreground="#555555", wraplength=620)
        note.grid(row=0, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 6))
        self._bind_scroll(note)
        self._label(frame, "都道府県", 1, 0)
        self._combo(frame, self.var_social_prefecture, PREFECTURES, 1, 1, width=12)

    def _build_income_tax_section(self, parent):
        frame = self._section(parent, "所得税")
        frame.grid_columnconfigure(2, minsize=30)
        self._label(frame, "甲乙区分", 0, 0)
        self._combo(frame, self.var_tax_type, ["甲", "乙"], 0, 1, width=4)
        self._label(frame, "扶養人数", 0, 3)
        self._entry(frame, self.var_dependents, 0, 4, width=8, justify="right")

    def _build_resident_tax_section(self, parent):
        frame = self._section(parent, "住民税")
        note = ttk.Label(frame, text="住民税一括入力画面の並び替え・確認用に使用します。", foreground="#555555", wraplength=620)
        note.grid(row=0, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 6))
        self._bind_scroll(note)
        self._label(frame, "市区町村", 1, 0)
        self._entry(frame, self.var_resident_tax_municipality, 1, 1, width=28)

    def _build_insurance_explanation_section(self, parent):
        frame = self._section(parent, "保険料計算の説明")
        for row, (label, value) in enumerate((
            ("社会保険料", "「社会保険加入対象」がONで、標準報酬月額が設定されている場合に計算します。"),
            ("雇用保険料", "「雇用保険加入対象」がONの場合、雇用保険対象額をもとに計算します。"),
            ("介護保険料", "社会保険加入対象者のうち、生年月日から介護保険対象年齢に該当する場合に計算します。"),
        )):
            self._label(frame, label, row, 0)
            value_label = ttk.Label(frame, text=value, wraplength=560)
            value_label.grid(row=row, column=1, sticky="w", padx=5, pady=4)
            self._bind_scroll(value_label)

    def _build_address_section(self, parent):
        frame = self._section(parent, "住所・連絡先")
        frame.grid_columnconfigure(2, minsize=24)
        self._label(frame, "郵便番号", 0, 0)
        self._entry(frame, self.var_address_postal_code, 0, 1, width=14)
        self._label(frame, "都道府県", 0, 3)
        self._combo(frame, self.var_address_prefecture, PREFECTURES, 0, 4, width=10)
        self._label(frame, "市区町村", 1, 0)
        self._entry(frame, self.var_address_city, 1, 1, width=23)
        self._label(frame, "番地・建物名", 1, 3)
        self._entry(frame, self.var_address_detail, 1, 4, width=36)
        self._label(frame, "電話番号", 2, 0)
        self._entry(frame, self.var_phone, 2, 1, width=18)
        self._label(frame, "メールアドレス", 2, 3)
        self._entry(frame, self.var_email, 2, 4, width=36)

    def _build_bank_section(self, parent):
        frame = self._section(parent, "振込先")
        self._label(frame, "銀行名", 0, 0)
        self._entry(frame, self.var_bank_name, 0, 1, width=24)
        self._label(frame, "支店名", 0, 2)
        self._entry(frame, self.var_bank_branch_name, 0, 3, width=20)
        self._label(frame, "口座種別", 1, 0)
        self._combo(frame, self.var_bank_account_type, ["普通", "当座", "貯蓄", "その他"], 1, 1, width=8)
        self._label(frame, "口座番号", 1, 2)
        self._entry(frame, self.var_bank_account_number, 1, 3, width=13)
        self._label(frame, "口座名義", 2, 0)
        self._entry(frame, self.var_bank_account_holder, 2, 1, width=24)

    def _build_memo_section(self, parent):
        frame = self._section(parent, "メモ")
        self.txt_memo = tk.Text(frame, width=72, height=3, wrap="word")
        self.txt_memo.grid(row=0, column=0, columnspan=4, sticky="ew", padx=5, pady=4)
        self._bind_scroll(self.txt_memo)

    def _on_canvas_configure(self, event):
        canvas = event.widget
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _current_canvas(self):
        try:
            selected = self.notebook.select()
            canvas = self._tab_canvases.get(str(selected))
            if canvas is not None:
                return canvas
        except Exception:
            pass
        return next(iter(self._tab_canvases.values()), None)

    def _on_mousewheel(self, event):
        if getattr(event, "state", 0) & 0x0001:
            return self._on_shift_mousewheel(event)
        if getattr(event, "num", None) == 4:
            units = -3
        elif getattr(event, "num", None) == 5:
            units = 3
        else:
            units = int(-3 * (event.delta / 120))
        canvas = self._current_canvas()
        if canvas is not None:
            canvas.yview_scroll(units, "units")
        return "break"

    def _on_shift_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            units = -3
        elif getattr(event, "num", None) == 5:
            units = 3
        else:
            units = int(-3 * (event.delta / 120))
        canvas = self._current_canvas()
        if canvas is not None:
            canvas.xview_scroll(units, "units")
        return "break"

    def _parse_money_var(self, var: tk.StringVar) -> int:
        text = (var.get() or "").replace(",", "").strip()
        if text == "":
            return 0
        if not text.isdigit():
            raise ValueError("標準報酬月額は数字で入力してください。")
        return int(text)

    def _format_money_var(self, var: tk.StringVar):
        var.set(f"{self._parse_money_var(var):,}")

    def _bind_money_format(self, entry, var: tk.StringVar):
        def on_focus_in(_event):
            var.set((var.get() or "").replace(",", ""))
            entry.select_range(0, "end")

        def on_focus_out(_event):
            try:
                self._format_money_var(var)
            except ValueError:
                pass

        entry.bind("<FocusIn>", on_focus_in, add="+")
        entry.bind("<FocusOut>", on_focus_out, add="+")

    def _collect_state(self):
        return {
            "code": self.var_code.get(),
            "name": self.var_name.get(),
            "name_kana": self.var_name_kana.get(),
            "department": self.var_department_id.get(),
            "position": self.var_position_id.get(),
            "employment_type": self.var_employment_type_id.get(),
            "payment_schedule": self.var_payment_schedule_id.get(),
            "std_health": (self.var_std_health.get() or "").replace(",", "").strip(),
            "std_pension": (self.var_std_pension.get() or "").replace(",", "").strip(),
            "social_target": int(self.var_social_insurance_target.get() or 0),
            "employment_target": int(self.var_employment_insurance_target.get() or 0),
            "tax_type": self.var_tax_type.get(),
            "dependents": int(self.var_dependents.get() or 0),
            "social_prefecture": self.var_social_prefecture.get(),
            "address_postal_code": self.var_address_postal_code.get(),
            "address_prefecture": self.var_address_prefecture.get(),
            "address_city": self.var_address_city.get(),
            "address_detail": self.var_address_detail.get(),
            "resident_tax_municipality": self.var_resident_tax_municipality.get(),
            "phone": self.var_phone.get(),
            "email": self.var_email.get(),
            "bank_name": self.var_bank_name.get(),
            "bank_branch_name": self.var_bank_branch_name.get(),
            "bank_account_type": self.var_bank_account_type.get(),
            "bank_account_number": self.var_bank_account_number.get(),
            "bank_account_holder": self.var_bank_account_holder.get(),
            "birth": (self.var_birth_y.get(), self.var_birth_m.get(), self.var_birth_d.get()),
            "hire": (self.var_hire_y.get(), self.var_hire_m.get(), self.var_hire_d.get()),
            "on_leave": int(self.var_on_leave.get() or 0),
            "leave_start": (self.var_leave_start_y.get(), self.var_leave_start_m.get(), self.var_leave_start_d.get()),
            "leave_expected_end": (
                self.var_leave_expected_end_y.get(),
                self.var_leave_expected_end_m.get(),
                self.var_leave_expected_end_d.get(),
            ),
            "leave_memo": self.var_leave_memo.get(),
            "leave": (self.var_leave_y.get(), self.var_leave_m.get(), self.var_leave_d.get()),
            "retirement_processed": int(self.var_retirement_processed.get() or 0),
            "memo": self.txt_memo.get("1.0", "end-1c") if self.txt_memo is not None else "",
        }

    def _reset_dirty_state(self):
        self._initial_state = self._collect_state()

    def _has_unsaved_changes(self) -> bool:
        return self._initial_state is not None and self._collect_state() != self._initial_state

    def load_payment_schedule_options(self):
        import db
        rows = db.list_payment_schedules(self.conn)
        self.payment_schedule_options = [(r["schedule_name"], r["payment_schedule_id"]) for r in rows]
        return [x[0] for x in self.payment_schedule_options]

    def load_named_master_options(self, table: str, target_options: list):
        import db
        target_options.clear()
        target_options.append(("", None))
        if table == "departments":
            rows = db.list_department_hierarchy(self.conn, include_inactive=False)
            for r in rows:
                target_options.append((r["full_name"], r["id"]))
        else:
            rows = db.list_named_master(self.conn, table)
            for r in rows:
                target_options.append((r["name"], r["id"]))
        return [x[0] for x in target_options]

    def _selected_master_id(self, var: tk.StringVar, options: list):
        selected = var.get().strip()
        for label, row_id in options:
            if label == selected:
                return row_id
        return None

    def _set_master_by_id(self, var: tk.StringVar, options: list, row_id):
        if not row_id:
            var.set("")
            return
        for label, option_id in options:
            if option_id and int(option_id) == int(row_id):
                var.set(label)
                return
        var.set("")

    def _split_date_to_vars(self, date_str, var_y, var_m, var_d):
        if not date_str:
            var_y.set("")
            var_m.set("")
            var_d.set("")
            return
        try:
            y, m, d = date_str.split("-")
            var_y.set(str(int(y)))
            var_m.set(str(int(m)))
            var_d.set(str(int(d)))
        except Exception:
            var_y.set("")
            var_m.set("")
            var_d.set("")

    def _build_date_from_vars(self, var_y, var_m, var_d):
        y = (var_y.get() or "").strip()
        m = (var_m.get() or "").strip()
        d = (var_d.get() or "").strip()
        if not y and not m and not d:
            return None
        if not y or not m or not d:
            raise ValueError("日付が途中までしか入力されていません。")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    def get_selected_payment_schedule_id(self):
        selected_label = self.var_payment_schedule_id.get().strip()
        for label, schedule_id in self.payment_schedule_options:
            if label == selected_label:
                return schedule_id
        return None

    def set_payment_schedule_by_id(self, payment_schedule_id):
        if not payment_schedule_id:
            self.var_payment_schedule_id.set("")
            return
        for label, schedule_id in self.payment_schedule_options:
            if int(schedule_id) == int(payment_schedule_id):
                self.var_payment_schedule_id.set(label)
                return
        self.var_payment_schedule_id.set("")

    def _employee_navigation_ids(self):
        cur = self.conn.cursor()
        where = ["COALESCE(is_deleted, 0) = 0"]
        if self.employee_filter == "active":
            where.append("COALESCE(retirement_processed, 0) = 0")
            where.append("COALESCE(is_on_leave, 0) = 0")
        elif self.employee_filter == "leave":
            where.append("COALESCE(retirement_processed, 0) = 0")
            where.append("COALESCE(is_on_leave, 0) = 1")
        elif self.employee_filter == "retired":
            where.append("COALESCE(retirement_processed, 0) = 1")
        where_sql = " AND ".join(where)
        cur.execute(
            f"""
            SELECT employee_id
            FROM employees
            WHERE {where_sql}
            ORDER BY
              CASE WHEN employee_code GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9]' THEN 0 ELSE 1 END,
              employee_code,
              employee_id
            """
        )
        return [int(row["employee_id"]) for row in cur.fetchall()]

    def _update_navigation_buttons(self):
        if not hasattr(self, "btn_prev_employee") or not hasattr(self, "btn_next_employee"):
            return
        state_prev = "disabled"
        state_next = "disabled"
        if self.employee_id:
            ids = self._employee_navigation_ids()
            try:
                index = ids.index(int(self.employee_id))
                if index > 0:
                    state_prev = "normal"
                if index < len(ids) - 1:
                    state_next = "normal"
            except ValueError:
                pass
        self.btn_prev_employee.configure(state=state_prev)
        self.btn_next_employee.configure(state=state_next)

    def _confirm_discard_changes(self, message=None):
        if not self._has_unsaved_changes():
            return True
        return messagebox.askyesno(
            "確認",
            message or "変更内容が保存されていません。保存せずに社員を切り替えますか？",
            parent=self,
        )

    def _move_employee(self, direction):
        if not self.employee_id:
            return
        if not self._confirm_discard_changes():
            return
        ids = self._employee_navigation_ids()
        try:
            index = ids.index(int(self.employee_id))
        except ValueError:
            self._update_navigation_buttons()
            return
        next_index = index + direction
        if next_index < 0 or next_index >= len(ids):
            self._update_navigation_buttons()
            return
        self.employee_id = ids[next_index]
        self.load_employee()

    def load_employee(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT employee_id, employee_code, name_kanji, COALESCE(name_kana, '') AS name_kana,
                   department, department_id, position_id, employment_type_id,
                   payday_group, payment_schedule_id, work_prefecture_name,
                   COALESCE(address_postal_code, '') AS address_postal_code,
                   COALESCE(address_prefecture, '') AS address_prefecture,
                   COALESCE(address_city, '') AS address_city,
                   COALESCE(address_detail, '') AS address_detail,
                   COALESCE(resident_tax_municipality, '') AS resident_tax_municipality,
                   COALESCE(phone, '') AS phone,
                   COALESCE(email, '') AS email,
                   COALESCE(bank_name, '') AS bank_name,
                   COALESCE(bank_branch_name, '') AS bank_branch_name,
                   COALESCE(bank_account_type, '') AS bank_account_type,
                   COALESCE(bank_account_number, '') AS bank_account_number,
                   COALESCE(bank_account_holder, '') AS bank_account_holder,
                   COALESCE(std_monthly_wage, 0) AS std_monthly_wage,
                   COALESCE(std_pension_wage, 0) AS std_pension_wage,
                   COALESCE(is_social_insurance_target, 0) AS is_social_insurance_target,
                   COALESCE(is_employment_insurance_target, 1) AS is_employment_insurance_target,
                   COALESCE(tax_type, '甲') AS tax_type,
                   COALESCE(dependents_count, 0) AS dependents_count,
                   birth_date, hire_date,
                   COALESCE(is_on_leave, 0) AS is_on_leave,
                   leave_start_date, leave_expected_end_date, COALESCE(leave_memo, '') AS leave_memo,
                   leave_date,
                   COALESCE(retirement_processed, 0) AS retirement_processed,
                   memo
            FROM employees
            WHERE employee_id = ?
            """,
            (self.employee_id,),
        )
        r = cur.fetchone()
        if not r:
            messagebox.showerror("エラー", "社員情報が見つかりません。")
            self.close()
            return

        self.var_code.set(r["employee_code"])
        self.var_name.set(r["name_kanji"])
        self.var_name_kana.set(r["name_kana"] or "")
        self._set_master_by_id(self.var_department_id, self.department_options, r["department_id"] if "department_id" in r.keys() else None)
        self._set_master_by_id(self.var_position_id, self.position_options, r["position_id"] if "position_id" in r.keys() else None)
        self._set_master_by_id(self.var_employment_type_id, self.employment_type_options, r["employment_type_id"] if "employment_type_id" in r.keys() else None)
        if r["payment_schedule_id"]:
            self.set_payment_schedule_by_id(r["payment_schedule_id"])
        else:
            old_payday = int(r["payday_group"] or 25)
            for label, _schedule_id in self.payment_schedule_options:
                if str(old_payday) in label:
                    self.var_payment_schedule_id.set(label)
                    break
        self.var_std_health.set(f'{int(r["std_monthly_wage"] or 0):,}')
        self.var_std_pension.set(f'{int(r["std_pension_wage"] or 0):,}')
        self.var_social_insurance_target.set(int(r["is_social_insurance_target"] or 0))
        self.var_employment_insurance_target.set(int(r["is_employment_insurance_target"] or 0))
        self.var_tax_type.set(r["tax_type"] or "甲")
        self.var_dependents.set(int(r["dependents_count"] or 0))
        self.var_social_prefecture.set(r["work_prefecture_name"] or "")
        self.var_address_postal_code.set(r["address_postal_code"] or "")
        self.var_address_prefecture.set(r["address_prefecture"] or "")
        self.var_address_city.set(r["address_city"] or "")
        self.var_address_detail.set(r["address_detail"] or "")
        self.var_resident_tax_municipality.set(r["resident_tax_municipality"] or "")
        self.var_phone.set(r["phone"] or "")
        self.var_email.set(r["email"] or "")
        self.var_bank_name.set(r["bank_name"] or "")
        self.var_bank_branch_name.set(r["bank_branch_name"] or "")
        self.var_bank_account_type.set(r["bank_account_type"] or "")
        self.var_bank_account_number.set(r["bank_account_number"] or "")
        self.var_bank_account_holder.set(r["bank_account_holder"] or "")
        self._split_date_to_vars(r["birth_date"], self.var_birth_y, self.var_birth_m, self.var_birth_d)
        self._split_date_to_vars(r["hire_date"], self.var_hire_y, self.var_hire_m, self.var_hire_d)
        self.var_on_leave.set(int(r["is_on_leave"] or 0))
        self._split_date_to_vars(r["leave_start_date"], self.var_leave_start_y, self.var_leave_start_m, self.var_leave_start_d)
        self._split_date_to_vars(
            r["leave_expected_end_date"],
            self.var_leave_expected_end_y,
            self.var_leave_expected_end_m,
            self.var_leave_expected_end_d,
        )
        self.var_leave_memo.set(r["leave_memo"] or "")
        self._split_date_to_vars(r["leave_date"], self.var_leave_y, self.var_leave_m, self.var_leave_d)
        self.var_retirement_processed.set(int(r["retirement_processed"] or 0))
        self.txt_memo.delete("1.0", "end")
        self.txt_memo.insert("1.0", r["memo"] or "")
        self._reset_dirty_state()
        self._update_navigation_buttons()

    def save(self):
        import db
        try:
            code = db.normalize_employee_code(self.var_code.get())
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e), parent=self)
            return
        self.var_code.set(code)
        name = self.var_name.get().strip()
        department_id = self._selected_master_id(self.var_department_id, self.department_options)
        position_id = self._selected_master_id(self.var_position_id, self.position_options)
        employment_type_id = self._selected_master_id(self.var_employment_type_id, self.employment_type_options)
        dept = self.var_department_id.get().strip()
        payment_schedule_id = self.get_selected_payment_schedule_id()

        try:
            std_health = self._parse_money_var(self.var_std_health)
            std_pension = self._parse_money_var(self.var_std_pension)
            tax_type = self.var_tax_type.get().strip() or "甲"
            deps = int(self.var_dependents.get() or 0)
            birth = self._build_date_from_vars(self.var_birth_y, self.var_birth_m, self.var_birth_d)
            hire_date = self._build_date_from_vars(self.var_hire_y, self.var_hire_m, self.var_hire_d)
            is_on_leave = int(self.var_on_leave.get() or 0)
            leave_start_date = self._build_date_from_vars(self.var_leave_start_y, self.var_leave_start_m, self.var_leave_start_d)
            leave_expected_end_date = self._build_date_from_vars(
                self.var_leave_expected_end_y,
                self.var_leave_expected_end_m,
                self.var_leave_expected_end_d,
            )
            leave_memo = self.var_leave_memo.get().strip()
            leave_date = self._build_date_from_vars(self.var_leave_y, self.var_leave_m, self.var_leave_d)
            retirement_processed = int(self.var_retirement_processed.get() or 0)
            memo = self.txt_memo.get("1.0", "end-1c").strip() or None
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            return
        except Exception:
            messagebox.showerror("入力エラー", "標準報酬月額または日付の入力内容を確認してください。")
            return

        if not code or not name:
            messagebox.showerror("入力エラー", "社員番号と氏名は必須です。")
            return
        if not payment_schedule_id:
            messagebox.showerror("入力エラー", "給与支給方式を選択してください。")
            return

        from datetime import datetime
        for label, value in [
            ("生年月日", birth),
            ("入社日", hire_date),
            ("休職開始日", leave_start_date),
            ("休職終了予定日", leave_expected_end_date),
            ("退職日", leave_date),
        ]:
            if value:
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except Exception:
                    messagebox.showerror("入力エラー", f"{label}は yyyy-mm-dd 形式で入力してください。")
                    return
        if hire_date and leave_date:
            if datetime.strptime(leave_date, "%Y-%m-%d").date() < datetime.strptime(hire_date, "%Y-%m-%d").date():
                messagebox.showerror("入力エラー", "退職日は入社日以降の日付を入力してください。")
                return
        if birth and hire_date:
            if datetime.strptime(hire_date, "%Y-%m-%d").date() <= datetime.strptime(birth, "%Y-%m-%d").date():
                messagebox.showerror("入力エラー", "入社日は生年月日より後の日付を入力してください。")
                return

        duplicate = self.conn.execute(
            """
            SELECT employee_id
            FROM employees
            WHERE employee_code = ?
              AND COALESCE(is_deleted, 0) = 0
              AND (? IS NULL OR employee_id <> ?)
            """,
            (code, self.employee_id, self.employee_id),
        ).fetchone()
        if duplicate:
            messagebox.showerror("入力エラー", "同じ社員番号の社員が既に登録されています。", parent=self)
            return

        try:
            db.upsert_employee(
                self.conn,
                code,
                name,
                dept,
                0,
                std_health,
                std_pension,
                tax_type,
                deps,
                self.var_social_prefecture.get().strip(),
                self.var_address_postal_code.get().strip(),
                self.var_address_prefecture.get().strip(),
                self.var_address_city.get().strip(),
                self.var_address_detail.get().strip(),
                self.var_resident_tax_municipality.get().strip(),
                birth,
                payment_schedule_id,
                hire_date,
                is_on_leave,
                leave_start_date,
                leave_expected_end_date,
                leave_memo,
                leave_date,
                retirement_processed,
                memo,
                department_id,
                position_id,
                employment_type_id,
                name_kana=self.var_name_kana.get().strip(),
                phone=self.var_phone.get().strip(),
                email=self.var_email.get().strip(),
                bank_name=self.var_bank_name.get().strip(),
                bank_branch_name=self.var_bank_branch_name.get().strip(),
                bank_account_type=self.var_bank_account_type.get().strip(),
                bank_account_number=self.var_bank_account_number.get().strip(),
                bank_account_holder=self.var_bank_account_holder.get().strip(),
                is_social_insurance_target=int(self.var_social_insurance_target.get() or 0),
                is_employment_insurance_target=int(self.var_employment_insurance_target.get() or 0),
                employee_id=self.employee_id,
            )
        except Exception as e:
            messagebox.showerror("保存エラー", str(e), parent=self)
            return
        if callable(self.on_saved):
            self.on_saved()
        if not self.employee_id:
            row = self.conn.execute(
                "SELECT employee_id FROM employees WHERE employee_code = ?",
                (code,),
            ).fetchone()
            if row:
                self.employee_id = int(row["employee_id"])
        self._format_money_var(self.var_std_health)
        self._format_money_var(self.var_std_pension)
        self._reset_dirty_state()
        self._update_navigation_buttons()
        messagebox.showinfo("保存完了", "保存しました。", parent=self)

    def close(self):
        if not self._confirm_discard_changes("保存せずに閉じますか？"):
            return
        self._reset_dirty_state()
        if self._has_unsaved_changes():
            if not messagebox.askyesno("確認", "変更内容が保存されていません。保存せずに閉じますか？", parent=self):
                return
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class EmployeesFrame(ttk.Frame):
    COLUMNS = ("id", "code", "name", "dept", "pref", "city", "address", "payday", "birth_date", "tax_type", "deps", "memo")
    DISPLAY_COLUMNS = ("code", "name", "dept", "payday", "birth_date", "tax_type", "deps", "memo")

    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self._sort_state = {"active": {}, "retired": {}}
        self.trees = {}

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.trees["active"] = self._build_tree_tab("active", "在職中")
        self.trees["retired"] = self._build_tree_tab("retired", "退職者")

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(btn_frame, text="新規作成", command=self.add_employee).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="編集", command=self.edit_selected).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="削除", command=self.delete_selected).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="閉じる", command=self.close_window).pack(side="right", padx=5)

        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._clear_tab_selection())
        self.refresh()
        enable_enter_key_navigation(self)

    def _build_tree_tab(self, tab_key: str, label: str):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=label)

        tree = ttk.Treeview(
            frame,
            columns=self.COLUMNS,
            displaycolumns=self.DISPLAY_COLUMNS,
            show="headings",
            height=12,
        )

        for c, t, w in [
            ("id", "ID", 60),
            ("code", "社員番号", 76),
            ("name", "氏名", 96),
            ("dept", "部署・事業所", 130),
            ("pref", "都道府県", 84),
            ("city", "市区町村", 110),
            ("address", "住所", 180),
            ("payday", "給与支給方式", 116),
            ("birth_date", "生年月日", 150),
            ("tax_type", "源泉", 54),
            ("deps", "扶養", 54),
            ("memo", "メモ", 220),
        ]:
            tree.heading(c, text=t, command=lambda col=c, key=tab_key: self._sort_tree(key, col))
            anchor = "w" if c == "memo" else "center"
            stretch = c == "memo"
            tree.column(c, width=w, anchor=anchor, stretch=stretch)

        tree.pack(fill="both", expand=True)
        tree.bind("<Double-1>", self.on_double_click)
        return tree

    def refresh(self):
        import db
        for tree in self.trees.values():
            for i in tree.get_children():
                tree.delete(i)

        for r in db.list_employees(self.conn):
            is_retired = int(r["retirement_processed"] or 0) if "retirement_processed" in r.keys() else 0
            tree = self.trees["retired"] if is_retired else self.trees["active"]
            tree.insert(
                "",
                "end",
                values=(
                    r["employee_id"],
                    r["employee_code"],
                    r["name_kanji"],
                    r["department"],
                    r["work_prefecture_name"] if "work_prefecture_name" in r.keys() else "",
                    r["address_city"] if "address_city" in r.keys() else "",
                    r["address_detail"] if "address_detail" in r.keys() else "",
                    db.get_employee_payment_schedule_display(r, self.conn),
                    self._format_birth_date(r["birth_date"] if "birth_date" in r.keys() else ""),
                    r["tax_type"] if "tax_type" in r.keys() else "甲",
                    r["dependents_count"] if "dependents_count" in r.keys() else 0,
                    (r["memo"] if "memo" in r.keys() else "") or "",
                ),
            )

    def _current_tree_key(self):
        selected_tab = self.notebook.select()
        for key, tree in self.trees.items():
            if str(tree.master) == str(selected_tab):
                return key
        return "active"

    def _current_tree(self):
        return self.trees[self._current_tree_key()]

    def _clear_tab_selection(self):
        for tree in self.trees.values():
            tree.selection_remove(tree.selection())

    def _format_birth_date(self, value):
        s = (value or "").strip()
        if not s:
            return ""
        try:
            y, m, d = s.split("-")
            return f"{int(y):04d} 年 {int(m):02d} 月 {int(d):02d} 日"
        except Exception:
            return s

    def _sort_value(self, col_name: str, value):
        if value is None:
            return (3, "")

        s = str(value).strip()
        if s == "":
            return (3, "")

        if col_name in {"id", "deps"}:
            try:
                return (0, int(str(value).replace(",", "")))
            except Exception:
                return (2, s)

        if col_name == "code":
            raw = str(value).replace(",", "").strip()
            if raw.isdigit():
                return (0, int(raw))

        if col_name == "birth_date":
            normalized = s.replace("\u5e74", "-").replace("\u6708", "-").replace("\u65e5", "")
            parts = normalized.split("-")
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                return (1, f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}")

        return (2, s)

    def _sort_tree(self, tab_key: str, col_name: str):
        tree = self.trees[tab_key]
        rows = []
        cols = tree["columns"]
        for item_id in tree.get_children(""):
            values = tree.item(item_id, "values")
            row_map = {cols[i]: values[i] for i in range(len(cols))}
            rows.append((item_id, row_map))

        reverse = self._sort_state[tab_key].get(col_name, False)
        rows.sort(key=lambda x: self._sort_value(col_name, x[1].get(col_name, "")), reverse=reverse)

        for idx, (item_id, _) in enumerate(rows):
            tree.move(item_id, "", idx)

        self._sort_state[tab_key][col_name] = not reverse

    def open_io_dialog(self):
        from employee_io_dialog import EmployeeIODialog

        dlg = EmployeeIODialog(self, self.conn, on_completed=self.refresh)
        self.wait_window(dlg)

    def delete_selected(self):
        tree = self._current_tree()
        sel = tree.selection()
        if not sel:
            messagebox.showerror("削除エラー", "削除する社員を選択してください。")
            return

        vals = tree.item(sel[0], "values")
        if not vals:
            messagebox.showerror("削除エラー", "削除対象の社員情報を取得できませんでした。")
            return

        employee_id = int(vals[0])
        employee_label = f"{vals[1]} {vals[2]}".strip()
        if not messagebox.askyesno("削除確認", "選択した社員を削除しますか？"):
            return

        second_message = (
            "この操作は一覧上は非表示になります。将来復元機能を追加する予定ですが、"
            "現時点では簡単には戻せません。必要に応じて事前にCSVエクスポートでバックアップしてください。"
            "本当に削除しますか？"
        )
        if not messagebox.askyesno("最終確認", second_message):
            return

        try:
            import db

            deleted = db.soft_delete_employee(self.conn, employee_id)
            if not deleted:
                messagebox.showerror("削除エラー", f"社員を削除できませんでした: {employee_label}")
                return
        except Exception as e:
            messagebox.showerror("削除エラー", str(e))
            return

        self.refresh()
        messagebox.showinfo("削除完了", f"社員を一覧から非表示にしました: {employee_label}")

    def close_window(self):
        self.winfo_toplevel().destroy()

    def add_employee(self):
        """新規追加"""
        dlg = EmployeeEditorDialog(self, self.conn, employee_id=None, on_saved=self.refresh)
        self.wait_window(dlg)

    def edit_selected(self):
        """選択社員を編集"""
        tree = self._current_tree()
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("確認", "社員を選択してください。")
            return

        vals = tree.item(sel[0], "values")
        if not vals:
            return

        emp_id = int(vals[0])
        self.open_editor(emp_id)

    def on_double_click(self, event):
        tree = event.widget
        sel = tree.selection()
        if not sel:
            return
        vals = tree.item(sel[0], "values")
        if not vals:
            return
        emp_id = int(vals[0])
        self.open_editor(emp_id)

    def open_editor(self, employee_id: int):
        dlg = EmployeeEditorDialog(self, self.conn, employee_id=employee_id, on_saved=self.refresh)
        self.wait_window(dlg)

    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self.status_filter = tk.StringVar(value="active")
        self._sort_state = {"active": {}, "leave": {}, "retired": {}, "all": {}}
        self.trees = {}

        filter_frame = ttk.LabelFrame(self, text="表示条件", padding=(10, 6))
        filter_frame.pack(fill="x", padx=10, pady=(10, 0))
        for text, value in (
            ("在職者", "active"),
            ("休職者", "leave"),
            ("退職者", "retired"),
            ("すべて", "all"),
        ):
            ttk.Radiobutton(
                filter_frame,
                text=text,
                value=value,
                variable=self.status_filter,
                command=self.refresh,
            ).pack(side="left", padx=(0, 16))

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self._setup_list_treeview_style()
        self._tree_column_lines = []
        self.tree = self._build_tree(tree_frame)
        self.trees = {key: self.tree for key in ("active", "leave", "retired", "all")}

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=5, pady=5)
        ttk.Button(btn_frame, text="新規作成", command=self.add_employee).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="編集", command=self.edit_selected).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="削除", command=self.delete_selected).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="閉じる", command=self.close_window).pack(side="right", padx=5)

        self.refresh()
        enable_enter_key_navigation(self)

    def _setup_list_treeview_style(self):
        style = ttk.Style(self)
        style.configure(
            "ListGrid.Treeview",
            rowheight=26,
            borderwidth=1,
            relief="solid",
            background="#ffffff",
            fieldbackground="#ffffff",
            bordercolor="#d8dee6",
            lightcolor="#edf1f5",
            darkcolor="#d8dee6",
        )
        style.configure(
            "ListGrid.Treeview.Heading",
            padding=(6, 5),
            relief="solid",
            borderwidth=1,
            background="#f3f5f7",
            bordercolor="#d8dee6",
            lightcolor="#edf1f5",
            darkcolor="#d8dee6",
        )
        style.map(
            "ListGrid.Treeview",
            background=[("selected", "#dbeafe")],
            foreground=[("selected", "#111827")],
        )

    def _build_tree(self, parent):
        frame = ttk.Frame(parent, padding=1, relief="solid", borderwidth=1)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(
            frame,
            columns=self.COLUMNS,
            displaycolumns=self.DISPLAY_COLUMNS,
            show="headings",
            height=12,
            style="ListGrid.Treeview",
        )
        tree.tag_configure("row_odd", background="#ffffff")
        tree.tag_configure("row_even", background="#f8fafc")
        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(frame, orient="horizontal")

        def on_xscroll(*args):
            tree.xview(*args)
            self.after_idle(self._update_tree_column_lines)

        def set_xscroll(first, last):
            x_scroll.set(first, last)
            self.after_idle(self._update_tree_column_lines)

        x_scroll.configure(command=on_xscroll)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=set_xscroll)
        for c, t, w in [
            ("id", "ID", 60),
            ("code", "社員番号", 76),
            ("name", "氏名", 96),
            ("dept", "部署・事業所", 130),
            ("pref", "都道府県", 84),
            ("city", "市区町村", 110),
            ("address", "住所", 180),
            ("payday", "給与支給方式", 116),
            ("birth_date", "生年月日", 150),
            ("tax_type", "源泉", 54),
            ("deps", "扶養", 54),
            ("memo", "メモ", 220),
        ]:
            tree.heading(c, text=t, command=lambda col=c: self._sort_tree(self._current_tree_key(), col))
            anchor = "w" if c == "memo" else "center"
            stretch = c == "memo"
            tree.column(c, width=w, anchor=anchor, stretch=stretch)
        tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        tree.bind("<Double-1>", self.on_double_click)
        tree.bind("<Configure>", lambda _e: self.after_idle(self._update_tree_column_lines), add="+")
        tree.bind("<ButtonPress-1>", lambda _e: self.after_idle(self._update_tree_column_lines), add="+")
        tree.bind("<B1-Motion>", lambda _e: self.after_idle(self._update_tree_column_lines), add="+")
        tree.bind("<ButtonRelease-1>", lambda _e: self.after_idle(self._update_tree_column_lines), add="+")
        return tree

    def _first_visible_tree_item_bbox(self, col):
        for item_id in self.tree.get_children(""):
            bbox = self.tree.bbox(item_id, col)
            if bbox:
                return bbox
        return None

    def _select_tree_row_at_y(self, y):
        row_id = self.tree.identify_row(y)
        if row_id:
            self.tree.selection_set(row_id)
            self.tree.focus(row_id)
        return row_id

    def _on_tree_column_line_click(self, event):
        y = event.widget.winfo_y() + event.y
        self._select_tree_row_at_y(y)
        return "break"

    def _on_tree_column_line_double_click(self, event):
        y = event.widget.winfo_y() + event.y
        row_id = self._select_tree_row_at_y(y)
        if row_id:
            vals = self.tree.item(row_id, "values")
            if vals:
                self.open_editor(int(vals[0]))
        return "break"

    def _on_tree_column_line_mousewheel(self, event):
        self.tree.event_generate("<MouseWheel>", delta=event.delta)
        return "break"

    def _update_tree_column_lines(self):
        if not hasattr(self, "tree"):
            return
        tree = self.tree
        if not tree.winfo_exists():
            return

        display_columns = list(self.DISPLAY_COLUMNS)
        needed = max(0, len(display_columns) - 1)
        while len(self._tree_column_lines) < needed:
            line = tk.Frame(tree, bg="#e5e7eb", width=1, cursor="")
            line.bind("<Button-1>", self._on_tree_column_line_click)
            line.bind("<Double-1>", self._on_tree_column_line_double_click)
            line.bind("<MouseWheel>", self._on_tree_column_line_mousewheel)
            self._tree_column_lines.append(line)
        for line in self._tree_column_lines[needed:]:
            line.place_forget()

        first_bbox = self._first_visible_tree_item_bbox(display_columns[0]) if display_columns else None
        y_start = first_bbox[1] if first_bbox else 24
        line_height = max(0, tree.winfo_height() - y_start)
        if line_height <= 0:
            return

        total_width = sum(int(tree.column(col, "width")) for col in display_columns)
        x_offset = int(total_width * tree.xview()[0]) if total_width > 0 else 0
        x_pos = 0
        for idx, col in enumerate(display_columns[:-1]):
            bbox = self._first_visible_tree_item_bbox(col)
            if bbox:
                x = bbox[0] + bbox[2] - 1
            else:
                x_pos += int(tree.column(col, "width"))
                x = x_pos - x_offset - 1
            line = self._tree_column_lines[idx]
            if 0 <= x <= tree.winfo_width():
                line.place(x=x, y=y_start, width=1, height=line_height)
                line.lift()
            else:
                line.place_forget()

    def _employee_status(self, row):
        if int(row.get("retirement_processed", 0) or 0):
            return "retired"
        if int(row.get("is_on_leave", 0) or 0):
            return "leave"
        return "active"

    def refresh(self):
        import db
        tree = self.tree
        for item_id in tree.get_children():
            tree.delete(item_id)
        selected_filter = self.status_filter.get() or "active"
        visible_index = 0
        for r in db.list_employees(self.conn):
            status = self._employee_status(r)
            if selected_filter != "all" and status != selected_filter:
                continue
            row_tag = "row_even" if visible_index % 2 else "row_odd"
            tree.insert(
                "",
                "end",
                tags=(row_tag,),
                values=(
                    r["employee_id"],
                    r["employee_code"],
                    r["name_kanji"],
                    r["department"],
                    r["work_prefecture_name"] if "work_prefecture_name" in r.keys() else "",
                    r["address_city"] if "address_city" in r.keys() else "",
                    r["address_detail"] if "address_detail" in r.keys() else "",
                    db.get_employee_payment_schedule_display(r, self.conn),
                    self._format_birth_date(r["birth_date"] if "birth_date" in r.keys() else ""),
                    r["tax_type"] if "tax_type" in r.keys() else "甲",
                    r["dependents_count"] if "dependents_count" in r.keys() else 0,
                    (r["memo"] if "memo" in r.keys() else "") or "",
                ),
            )
            visible_index += 1
        self.after_idle(self._update_tree_column_lines)

    def _current_tree_key(self):
        return self.status_filter.get() or "active"

    def _current_tree(self):
        return self.tree

    def _clear_tab_selection(self):
        self.tree.selection_remove(self.tree.selection())

    def add_employee(self):
        dlg = EmployeeEditorDialog(
            self,
            self.conn,
            employee_id=None,
            on_saved=self.refresh,
            employee_filter=self._current_tree_key(),
        )
        self.wait_window(dlg)

    def edit_selected(self):
        tree = self._current_tree()
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("確認", "社員を選択してください。")
            return
        vals = tree.item(sel[0], "values")
        if not vals:
            return
        self.open_editor(int(vals[0]))

    def on_double_click(self, event):
        tree = event.widget
        sel = tree.selection()
        if not sel:
            return
        vals = tree.item(sel[0], "values")
        if not vals:
            return
        self.open_editor(int(vals[0]))

    def open_editor(self, employee_id: int):
        dlg = EmployeeEditorDialog(
            self,
            self.conn,
            employee_id=employee_id,
            on_saved=self.refresh,
            employee_filter=self._current_tree_key(),
        )
        self.wait_window(dlg)
