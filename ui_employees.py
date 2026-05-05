import tkinter as tk
from tkinter import ttk, messagebox
from ui_window_utils import center_window, enable_enter_key_navigation

class EmployeeEditorDialog(tk.Toplevel):
    def __init__(self, parent, conn, employee_id: int, on_saved=None):
        super().__init__(parent)
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

        ttk.Label(frm, text="部署").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.cmb_department = ttk.Combobox(
            frm,
            textvariable=self.var_department_id,
            values=self.load_named_master_options("departments", self.department_options),
            width=18,
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
        center_window(self, parent)
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

        rows = db.list_named_master(self.conn, table)
        target_options.clear()
        target_options.append(("", None))
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

    def save(self):
        code = self.var_code.get().strip()
        name = self.var_name.get().strip()
        department_id = self._selected_master_id(self.var_department_id, self.department_options)
        position_id = self._selected_master_id(self.var_position_id, self.position_options)
        employment_type_id = self._selected_master_id(self.var_employment_type_id, self.employment_type_options)
        dept = self.var_department_id.get().strip()
        payment_schedule_id = self.get_selected_payment_schedule_id()

        try:
            std_health = int((self.var_std_health.get() or "0").replace(",", ""))
            std_pension = int((self.var_std_pension.get() or "0").replace(",", ""))
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

        import db
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
            leave_date,
            retirement_processed,
            memo,
            department_id,
            position_id,
            employment_type_id,
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

class EmployeesFrame(ttk.Frame):
    COLUMNS = ("id", "code", "name", "dept", "pref", "city", "address", "payday", "birth_date", "tax_type", "deps", "memo")
    DISPLAY_COLUMNS = ("code", "name", "dept", "pref", "city", "address", "payday", "birth_date", "tax_type", "deps", "memo")

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
        ttk.Button(btn_frame, text="追加", command=self.add_employee).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="編集", command=self.edit_selected).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="削除", command=self.delete_selected).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="インポート/エクスポート", command=self.open_io_dialog).pack(side="left", padx=5)
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
            ("dept", "部署", 96),
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
