import tkinter as tk
from tkinter import ttk, messagebox

import db
from ui_window_utils import center_window, enable_enter_key_navigation


ITEM_KIND_LABELS = {
    "pay": "支給",
    "deduction": "控除",
    "system_deduction": "システム控除",
    "other": "その他",
}


class CompanySettingsDialog(tk.Toplevel):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        self.title("会社設定")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.var_name = tk.StringVar()
        self.var_kana = tk.StringVar()
        self.var_postal = tk.StringVar()
        self.var_address = tk.StringVar()
        self.var_phone = tk.StringVar()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        fields = [
            ("会社名", self.var_name, 36),
            ("会社名カナ", self.var_kana, 36),
            ("郵便番号", self.var_postal, 16),
            ("住所", self.var_address, 48),
            ("電話番号", self.var_phone, 20),
        ]
        for row, (label, var, width) in enumerate(fields):
            ttk.Label(frm, text=label).grid(row=row, column=0, padx=5, pady=5, sticky="w")
            ttk.Entry(frm, textvariable=var, width=width).grid(row=row, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(frm, text="メモ").grid(row=5, column=0, padx=5, pady=5, sticky="nw")
        self.txt_memo = tk.Text(frm, width=48, height=4, wrap="word")
        self.txt_memo.grid(row=5, column=1, padx=5, pady=5, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, padx=5, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")

        self.load()
        self.bind("<Escape>", lambda e: self.close())
        enable_enter_key_navigation(self)
        center_window(self, parent)

    def load(self):
        row = db.get_company_settings(self.conn)
        if not row:
            return
        self.var_name.set(row["company_name"] or "")
        self.var_kana.set(row["company_kana"] or "")
        self.var_postal.set(row["postal_code"] or "")
        self.var_address.set(row["address"] or "")
        self.var_phone.set(row["phone"] or "")
        self.txt_memo.delete("1.0", "end")
        self.txt_memo.insert("1.0", row["memo"] or "")

    def save(self):
        db.upsert_company_settings(
            self.conn,
            self.var_name.get().strip(),
            self.var_kana.get().strip(),
            self.var_postal.get().strip(),
            self.var_address.get().strip(),
            self.var_phone.get().strip(),
            self.txt_memo.get("1.0", "end-1c").strip() or None,
        )
        self.close()

    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class NamedMasterEditorDialog(tk.Toplevel):
    def __init__(self, parent, conn, title, table, row=None, on_saved=None):
        super().__init__(parent)
        self.conn = conn
        self.table = table
        self.row = row
        self.on_saved = on_saved
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.var_name = tk.StringVar()
        self.var_order = tk.StringVar(value="0")
        self.var_active = tk.IntVar(value=1)
        self.var_memo = tk.StringVar()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="名称").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_name, width=28).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frm, text="表示順").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_order, width=8, justify="right").grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(frm, text="有効", variable=self.var_active).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frm, text="メモ").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_memo, width=34).grid(row=3, column=1, padx=5, pady=5, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, padx=5, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")

        if row:
            self.var_name.set(row["name"] or "")
            self.var_order.set(str(row["display_order"] or 0))
            self.var_active.set(int(row["is_active"] or 0))
            self.var_memo.set(row["memo"] or "")
        enable_enter_key_navigation(self)
        center_window(self, parent)

    def save(self):
        name = self.var_name.get().strip()
        if not name:
            messagebox.showerror("入力エラー", "名称は必須です。", parent=self)
            return
        try:
            order = int(self.var_order.get() or 0)
        except Exception:
            messagebox.showerror("入力エラー", "表示順は数字で入力してください。", parent=self)
            return
        db.upsert_named_master(
            self.conn,
            self.table,
            name,
            order,
            int(self.var_active.get() or 0),
            self.var_memo.get().strip() or None,
            self.row["id"] if self.row else None,
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


class NamedMasterFrame(ttk.Frame):
    def __init__(self, master, conn, table, title):
        super().__init__(master)
        self.conn = conn
        self.table = table
        self.title = title

        self.tree = ttk.Treeview(self, columns=("id", "name", "order", "active", "memo"), displaycolumns=("name", "order", "active", "memo"), show="headings", height=12)
        for col, label, width, anchor in [
            ("name", "名称", 180, "w"),
            ("order", "表示順", 70, "center"),
            ("active", "有効", 60, "center"),
            ("memo", "メモ", 260, "w"),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor=anchor, stretch=(col == "memo"))
        self.tree.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="新規作成", command=self.add).pack(side="left", padx=5)
        ttk.Button(btns, text="編集", command=self.edit_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="無効化", command=self.disable_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="閉じる", command=self.close_window).pack(side="right", padx=5)
        self.refresh()
        enable_enter_key_navigation(self)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in db.list_named_master(self.conn, self.table, include_inactive=True):
            self.tree.insert("", "end", values=(r["id"], r["name"], r["display_order"], "○" if r["is_active"] else "", r["memo"] or ""))

    def _selected_row(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        return db.get_named_master_by_id(self.conn, self.table, int(vals[0])) if vals else None

    def add(self):
        dlg = NamedMasterEditorDialog(self, self.conn, self.title, self.table, on_saved=self.refresh)
        self.wait_window(dlg)

    def edit_selected(self):
        row = self._selected_row()
        if not row:
            messagebox.showinfo("確認", "行を選択してください。", parent=self)
            return
        dlg = NamedMasterEditorDialog(self, self.conn, self.title, self.table, row=row, on_saved=self.refresh)
        self.wait_window(dlg)

    def disable_selected(self):
        row = self._selected_row()
        if not row:
            messagebox.showinfo("確認", "行を選択してください。", parent=self)
            return
        if messagebox.askyesno("確認", f"{row['name']} を無効化しますか？", parent=self):
            db.soft_delete_named_master(self.conn, self.table, row["id"])
            self.refresh()

    def close_window(self):
        self.winfo_toplevel().destroy()


class PayrollCategoryEditorDialog(tk.Toplevel):
    def __init__(self, parent, conn, row=None, on_saved=None):
        super().__init__(parent)
        self.conn = conn
        self.row = row
        self.on_saved = on_saved
        self.title("支給控除カテゴリ")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.var_code = tk.StringVar()
        self.var_name = tk.StringVar()
        self.var_kind = tk.StringVar(value="pay")
        self.var_order = tk.StringVar(value="0")
        self.var_active = tk.IntVar(value=1)
        self.var_memo = tk.StringVar()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        for i, (label, widget) in enumerate([
            ("コード", ttk.Entry(frm, textvariable=self.var_code, width=24)),
            ("名称", ttk.Entry(frm, textvariable=self.var_name, width=24)),
            ("区分", ttk.Combobox(frm, textvariable=self.var_kind, values=list(ITEM_KIND_LABELS.keys()), width=18, state="readonly")),
            ("表示順", ttk.Entry(frm, textvariable=self.var_order, width=8, justify="right")),
            ("メモ", ttk.Entry(frm, textvariable=self.var_memo, width=34)),
        ]):
            ttk.Label(frm, text=label).grid(row=i, column=0, padx=5, pady=5, sticky="w")
            widget.grid(row=i, column=1, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(frm, text="有効", variable=self.var_active).grid(row=5, column=1, padx=5, pady=5, sticky="w")
        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, sticky="e", padx=5, pady=(10, 0))
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")
        if row:
            self.var_code.set(row["code"])
            self.var_name.set(row["name"])
            self.var_kind.set(row["item_kind"])
            self.var_order.set(str(row["display_order"] or 0))
            self.var_active.set(int(row["is_active"] or 0))
            self.var_memo.set(row["memo"] or "")
        enable_enter_key_navigation(self)
        center_window(self, parent)

    def save(self):
        try:
            order = int(self.var_order.get() or 0)
        except Exception:
            messagebox.showerror("入力エラー", "表示順は数字で入力してください。", parent=self)
            return
        db.upsert_payroll_item_category(self.conn, self.var_code.get().strip(), self.var_name.get().strip(), self.var_kind.get(), order, int(self.var_active.get()), self.var_memo.get().strip() or None, self.row["id"] if self.row else None)
        if callable(self.on_saved):
            self.on_saved()
        self.close()

    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class PayrollCategoryFrame(ttk.Frame):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self.tree = ttk.Treeview(self, columns=("id", "code", "name", "kind", "order", "active", "memo"), displaycolumns=("code", "name", "kind", "order", "active", "memo"), show="headings", height=12)
        for col, label, width, anchor in [("code", "コード", 130, "w"), ("name", "名称", 140, "w"), ("kind", "区分", 110, "center"), ("order", "表示順", 70, "center"), ("active", "有効", 50, "center"), ("memo", "メモ", 220, "w")]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor=anchor, stretch=(col == "memo"))
        self.tree.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())
        self._buttons()
        self.refresh()
        enable_enter_key_navigation(self)

    def _buttons(self):
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="新規作成", command=self.add).pack(side="left", padx=5)
        ttk.Button(btns, text="編集", command=self.edit_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="無効化", command=self.disable_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="閉じる", command=lambda: self.winfo_toplevel().destroy()).pack(side="right", padx=5)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in db.list_payroll_item_categories(self.conn, include_inactive=True):
            self.tree.insert("", "end", values=(r["id"], r["code"], r["name"], ITEM_KIND_LABELS.get(r["item_kind"], r["item_kind"]), r["display_order"], "○" if r["is_active"] else "", r["memo"] or ""))

    def _selected_row(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        row_id = int(vals[0])
        return next((r for r in db.list_payroll_item_categories(self.conn, include_inactive=True) if int(r["id"]) == row_id), None)

    def add(self):
        dlg = PayrollCategoryEditorDialog(self, self.conn, on_saved=self.refresh)
        self.wait_window(dlg)

    def edit_selected(self):
        row = self._selected_row()
        if not row:
            messagebox.showinfo("確認", "行を選択してください。", parent=self)
            return
        dlg = PayrollCategoryEditorDialog(self, self.conn, row=row, on_saved=self.refresh)
        self.wait_window(dlg)

    def disable_selected(self):
        row = self._selected_row()
        if row and messagebox.askyesno("確認", f"{row['name']} を無効化しますか？", parent=self):
            db.soft_delete_payroll_item_category(self.conn, row["id"])
            self.refresh()


class PayrollItemEditorDialog(tk.Toplevel):
    def __init__(self, parent, conn, row=None, on_saved=None):
        super().__init__(parent)
        self.conn = conn
        self.row = row
        self.on_saved = on_saved
        self.title("支給控除項目")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.var_code = tk.StringVar()
        self.var_name = tk.StringVar()
        self.var_kind = tk.StringVar(value="pay")
        self.var_category = tk.StringVar()
        self.var_system = tk.IntVar(value=0)
        self.var_active = tk.IntVar(value=1)
        self.var_taxable = tk.IntVar(value=0)
        self.var_social = tk.IntVar(value=0)
        self.var_emp = tk.IntVar(value=0)
        self.var_commute = tk.IntVar(value=0)
        self.var_order = tk.StringVar(value="0")
        self.var_memo = tk.StringVar()
        self.category_options = []

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="コード").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_code, width=24).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frm, text="名称").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_name, width=24).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frm, text="区分").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Combobox(frm, textvariable=self.var_kind, values=["pay", "deduction", "system_deduction"], width=18, state="readonly").grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frm, text="カテゴリ").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        ttk.Combobox(frm, textvariable=self.var_category, values=self.load_categories(), width=22, state="readonly").grid(row=3, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frm, text="表示順").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_order, width=8, justify="right").grid(row=4, column=1, padx=5, pady=5, sticky="w")
        checks = ttk.Frame(frm)
        checks.grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        for text, var in [("システム", self.var_system), ("有効", self.var_active), ("課税", self.var_taxable), ("社保基礎", self.var_social), ("雇保基礎", self.var_emp), ("通勤", self.var_commute)]:
            ttk.Checkbutton(checks, text=text, variable=var).pack(side="left", padx=(0, 8))
        ttk.Label(frm, text="メモ").grid(row=6, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_memo, width=36).grid(row=6, column=1, padx=5, pady=5, sticky="w")
        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=2, padx=5, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")
        if row:
            self.load_row(row)
        enable_enter_key_navigation(self)
        center_window(self, parent)

    def load_categories(self):
        self.category_options = [(f'{r["code"]} {r["name"]}', r["id"]) for r in db.list_payroll_item_categories(self.conn)]
        return [x[0] for x in self.category_options]

    def category_id(self):
        selected = self.var_category.get()
        for label, row_id in self.category_options:
            if label == selected:
                return row_id
        return None

    def set_category(self, category_id):
        for label, row_id in self.category_options:
            if category_id and int(row_id) == int(category_id):
                self.var_category.set(label)
                return

    def load_row(self, row):
        self.var_code.set(row["code"])
        self.var_name.set(row["name"])
        self.var_kind.set(row["item_kind"])
        self.set_category(row["category_id"])
        self.var_system.set(int(row["is_system"] or 0))
        self.var_active.set(int(row["is_active"] or 0))
        self.var_taxable.set(int(row["is_taxable"] or 0))
        self.var_social.set(int(row["is_social_insurance_base"] or 0))
        self.var_emp.set(int(row["is_employment_insurance_base"] or 0))
        self.var_commute.set(int(row["is_commute"] or 0))
        self.var_order.set(str(row["display_order"] or 0))
        self.var_memo.set(row["memo"] or "")

    def save(self):
        try:
            order = int(self.var_order.get() or 0)
        except Exception:
            messagebox.showerror("入力エラー", "表示順は数字で入力してください。", parent=self)
            return
        db.upsert_payroll_item(
            self.conn, self.var_code.get().strip(), self.var_name.get().strip(), self.var_kind.get(),
            self.category_id(), int(self.var_system.get()), int(self.var_active.get()), int(self.var_taxable.get()),
            int(self.var_social.get()), int(self.var_emp.get()), int(self.var_commute.get()), order,
            self.var_memo.get().strip() or None, self.row["id"] if self.row else None,
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


class PayrollItemFrame(ttk.Frame):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self.tree = ttk.Treeview(self, columns=("id", "code", "name", "kind", "category", "system", "active", "order"), displaycolumns=("code", "name", "kind", "category", "system", "active", "order"), show="headings", height=12)
        for col, label, width, anchor in [("code", "コード", 130, "w"), ("name", "名称", 150, "w"), ("kind", "区分", 100, "center"), ("category", "カテゴリ", 130, "w"), ("system", "システム", 70, "center"), ("active", "有効", 50, "center"), ("order", "表示順", 70, "center")]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor=anchor, stretch=(col in {"name", "category"}))
        self.tree.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="新規作成", command=self.add).pack(side="left", padx=5)
        ttk.Button(btns, text="編集", command=self.edit_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="無効化", command=self.disable_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="閉じる", command=lambda: self.winfo_toplevel().destroy()).pack(side="right", padx=5)
        self.refresh()
        enable_enter_key_navigation(self)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in db.list_payroll_items(self.conn, include_inactive=True):
            self.tree.insert("", "end", values=(r["id"], r["code"], r["name"], ITEM_KIND_LABELS.get(r["item_kind"], r["item_kind"]), r["category_name"] or "", "○" if r["is_system"] else "", "○" if r["is_active"] else "", r["display_order"]))

    def _selected_row(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        row_id = int(vals[0])
        return next((r for r in db.list_payroll_items(self.conn, include_inactive=True) if int(r["id"]) == row_id), None)

    def add(self):
        dlg = PayrollItemEditorDialog(self, self.conn, on_saved=self.refresh)
        self.wait_window(dlg)

    def edit_selected(self):
        row = self._selected_row()
        if not row:
            messagebox.showinfo("確認", "行を選択してください。", parent=self)
            return
        dlg = PayrollItemEditorDialog(self, self.conn, row=row, on_saved=self.refresh)
        self.wait_window(dlg)

    def disable_selected(self):
        row = self._selected_row()
        if row and messagebox.askyesno("確認", f"{row['name']} を無効化しますか？", parent=self):
            db.soft_delete_payroll_item(self.conn, row["id"])
            self.refresh()


class EmployeeStandardValueDialog(tk.Toplevel):
    def __init__(self, parent, conn, on_saved=None):
        super().__init__(parent)
        self.conn = conn
        self.on_saved = on_saved
        self.title("社員別標準金額")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.employee_options = [(f'{r["employee_code"]} {r["name_kanji"]}', r["employee_id"]) for r in db.list_employees(conn)]
        self.item_options = [(f'{r["code"]} {r["name"]}', r["id"]) for r in db.list_payroll_items(conn)]
        self.var_employee = tk.StringVar()
        self.var_item = tk.StringVar()
        self.var_start = tk.StringVar()
        self.var_amount = tk.StringVar(value="0")
        self.var_active = tk.IntVar(value=1)
        self.var_memo = tk.StringVar()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        for row, (label, widget) in enumerate([
            ("社員", ttk.Combobox(frm, textvariable=self.var_employee, values=[x[0] for x in self.employee_options], width=30, state="readonly")),
            ("項目", ttk.Combobox(frm, textvariable=self.var_item, values=[x[0] for x in self.item_options], width=30, state="readonly")),
            ("開始月", ttk.Entry(frm, textvariable=self.var_start, width=10)),
            ("金額", ttk.Entry(frm, textvariable=self.var_amount, width=14, justify="right")),
            ("メモ", ttk.Entry(frm, textvariable=self.var_memo, width=34)),
        ]):
            ttk.Label(frm, text=label).grid(row=row, column=0, padx=5, pady=5, sticky="w")
            widget.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(frm, text="有効", variable=self.var_active).grid(row=5, column=1, padx=5, pady=5, sticky="w")
        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, padx=5, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")
        enable_enter_key_navigation(self)
        center_window(self, parent)

    def _selected_id(self, var, options):
        selected = var.get()
        for label, row_id in options:
            if label == selected:
                return row_id
        return None

    def save(self):
        employee_id = self._selected_id(self.var_employee, self.employee_options)
        item_id = self._selected_id(self.var_item, self.item_options)
        if not employee_id or not item_id:
            messagebox.showerror("入力エラー", "社員と項目を選択してください。", parent=self)
            return
        start_month = self.var_start.get().strip()
        if len(start_month) != 7 or start_month[4] != "-":
            messagebox.showerror("入力エラー", "開始月は yyyy-mm 形式で入力してください。", parent=self)
            return
        try:
            amount = int((self.var_amount.get() or "0").replace(",", ""))
        except Exception:
            messagebox.showerror("入力エラー", "金額は数字で入力してください。", parent=self)
            return
        db.upsert_employee_payroll_item_standard_value(
            self.conn,
            employee_id,
            item_id,
            start_month,
            amount,
            int(self.var_active.get() or 0),
            self.var_memo.get().strip() or None,
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


class EmployeeStandardValueFrame(ttk.Frame):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        self.tree = ttk.Treeview(self, columns=("employee", "item", "start", "amount", "active", "memo"), show="headings", height=12)
        for col, label, width, anchor in [
            ("employee", "社員", 170, "w"),
            ("item", "項目", 170, "w"),
            ("start", "開始月", 90, "center"),
            ("amount", "金額", 100, "e"),
            ("active", "有効", 50, "center"),
            ("memo", "メモ", 220, "w"),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor=anchor, stretch=(col == "memo"))
        self.tree.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="新規作成", command=self.add).pack(side="left", padx=5)
        ttk.Button(btns, text="閉じる", command=lambda: self.winfo_toplevel().destroy()).pack(side="right", padx=5)
        self.refresh()
        enable_enter_key_navigation(self)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for employee in db.list_employees(self.conn):
            for r in db.list_employee_payroll_item_standard_values(self.conn, employee["employee_id"]):
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        f'{employee["employee_code"]} {employee["name_kanji"]}',
                        r["item_name"],
                        r["start_month"],
                        f'{int(r["amount"] or 0):,}',
                        "○" if r["is_active"] else "",
                        r["memo"] or "",
                    ),
                )

    def add(self):
        dlg = EmployeeStandardValueDialog(self, self.conn, on_saved=self.refresh)
        self.wait_window(dlg)
