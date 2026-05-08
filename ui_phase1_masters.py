import tkinter as tk
from tkinter import ttk, messagebox

import db
from ui_window_utils import show_centered_window, enable_enter_key_navigation


ITEM_KIND_LABELS = {
    "pay": "支給",
    "deduction": "控除",
    "system_deduction": "システム控除",
    "other": "その他",
}
ITEM_KIND_REVERSE_LABELS = {label: key for key, label in ITEM_KIND_LABELS.items()}

DEPARTMENT_TYPE_LABELS = {
    "office": "事業所",
    "department": "部署",
    "section": "課・係",
    "other": "その他",
}
DEPARTMENT_TYPE_REVERSE_LABELS = {label: key for key, label in DEPARTMENT_TYPE_LABELS.items()}


class CompanySettingsDialog(tk.Toplevel):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.withdraw()
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
        show_centered_window(self, parent)

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
        self.withdraw()
        self.conn = conn
        self.table = table
        self.row = row
        self.on_saved = on_saved
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.var_name = tk.StringVar()
        self.var_active = tk.IntVar(value=1)
        self.var_memo = tk.StringVar()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="名称").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_name, width=28).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(frm, text="有効", variable=self.var_active).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frm, text="メモ").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_memo, width=34).grid(row=2, column=1, padx=5, pady=5, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, columnspan=2, padx=5, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")

        if row:
            self.var_name.set(row["name"] or "")
            self.var_active.set(int(row["is_active"] or 0))
            self.var_memo.set(row["memo"] or "")
        enable_enter_key_navigation(self)
        show_centered_window(self, parent)

    def save(self):
        name = self.var_name.get().strip()
        if not name:
            messagebox.showerror("入力エラー", "名称は必須です。", parent=self)
            return
        db.upsert_named_master(
            self.conn,
            self.table,
            name,
            None,
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

        self.tree = ttk.Treeview(self, columns=("id", "name", "active", "memo"), displaycolumns=("name", "active", "memo"), show="headings", height=12)
        for col, label, width, anchor in [
            ("name", "名称", 180, "w"),
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
        ttk.Button(btns, text="上へ", command=lambda: self.move_selected("up")).pack(side="left", padx=5)
        ttk.Button(btns, text="下へ", command=lambda: self.move_selected("down")).pack(side="left", padx=5)
        ttk.Button(btns, text="無効化", command=self.disable_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="閉じる", command=self.close_window).pack(side="right", padx=5)
        self.refresh()
        enable_enter_key_navigation(self)

    def refresh(self, select_id=None):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in db.list_named_master(self.conn, self.table, include_inactive=True):
            self.tree.insert("", "end", iid=str(r["id"]), values=(r["id"], r["name"], "○" if r["is_active"] else "", r["memo"] or ""))
        if select_id is not None and self.tree.exists(str(select_id)):
            self.tree.selection_set(str(select_id))
            self.tree.see(str(select_id))

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

    def move_selected(self, direction):
        row = self._selected_row()
        if not row:
            messagebox.showinfo("確認", "行を選択してください。", parent=self)
            return
        db.move_display_order(self.conn, self.table, row["id"], direction, include_inactive=True)
        self.refresh(select_id=row["id"])

    def close_window(self):
        self.winfo_toplevel().destroy()


class DepartmentEditorDialog(tk.Toplevel):
    def __init__(self, parent, conn, row=None, on_saved=None):
        super().__init__(parent)
        self.withdraw()
        self.conn = conn
        self.row = row
        self.on_saved = on_saved
        self.title("部署・事業所マスタ")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self.var_name = tk.StringVar()
        self.var_type = tk.StringVar(value=DEPARTMENT_TYPE_LABELS["department"])
        self.var_parent = tk.StringVar(value="なし")
        self.var_active = tk.IntVar(value=1)
        self.var_memo = tk.StringVar()
        self.parent_options = [("なし", None)]

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="名称").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_name, width=30).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frm, text="種別").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Combobox(
            frm,
            textvariable=self.var_type,
            values=list(DEPARTMENT_TYPE_LABELS.values()),
            width=14,
            state="readonly",
        ).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frm, text="親所属").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Combobox(
            frm,
            textvariable=self.var_parent,
            values=self._load_parent_options(),
            width=34,
            state="readonly",
        ).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(frm, text="有効", variable=self.var_active).grid(row=3, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frm, text="メモ").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_memo, width=40).grid(row=4, column=1, padx=5, pady=5, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, padx=5, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")

        if row:
            self.var_name.set(row["name"] or "")
            self.var_type.set(DEPARTMENT_TYPE_LABELS.get(row["department_type"] if "department_type" in row.keys() else "department", "部署"))
            self.var_active.set(int(row["is_active"] or 0))
            self.var_memo.set(row["memo"] or "")
            self._set_parent(int(row["parent_department_id"] or 0) if "parent_department_id" in row.keys() else None)

        enable_enter_key_navigation(self)
        show_centered_window(self, parent)

    def _load_parent_options(self):
        self.parent_options = [("なし", None)]
        current_id = int(self.row["id"]) if self.row else None
        excluded = {current_id} if current_id else set()
        if current_id:
            excluded.update(db.get_department_descendant_ids(self.conn, current_id))
        for item in db.list_department_hierarchy(self.conn, include_inactive=False):
            if item["id"] in excluded:
                continue
            self.parent_options.append((item["full_name"], item["id"]))
        return [label for label, _ in self.parent_options]

    def _selected_parent_id(self):
        selected = self.var_parent.get()
        for label, row_id in self.parent_options:
            if label == selected:
                return row_id
        return None

    def _set_parent(self, parent_id):
        if not parent_id:
            self.var_parent.set("なし")
            return
        for label, row_id in self.parent_options:
            if row_id and int(row_id) == int(parent_id):
                self.var_parent.set(label)
                return
        self.var_parent.set("なし")

    def save(self):
        name = self.var_name.get().strip()
        if not name:
            messagebox.showerror("入力エラー", "名称は必須です。", parent=self)
            return
        try:
            db.upsert_department(
                self.conn,
                name,
                DEPARTMENT_TYPE_REVERSE_LABELS.get(self.var_type.get(), "department"),
                self._selected_parent_id(),
                int(self.var_active.get() or 0),
                self.var_memo.get().strip() or None,
                self.row["id"] if self.row else None,
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


class DepartmentMasterFrame(ttk.Frame):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        desc = (
            "部署・事業所・課など、社員の所属先を管理します。\n"
            "支店・営業所・本社を登録したい場合は、種別を「事業所」として登録してください。\n"
            "部署や課を事業所の下に紐づけることで、所属を階層的に管理できます。"
        )
        ttk.Label(self, text=desc, justify="left").pack(anchor="w", padx=10, pady=(10, 6))

        self.tree = ttk.Treeview(
            self,
            columns=("id", "type", "name", "parent", "active", "memo"),
            displaycolumns=("type", "name", "parent", "active", "memo"),
            show="headings",
            height=12,
        )
        for col, label, width, anchor in [
            ("type", "種別", 80, "center"),
            ("name", "名称", 220, "w"),
            ("parent", "親所属", 180, "w"),
            ("active", "有効", 50, "center"),
            ("memo", "メモ", 220, "w"),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor=anchor, stretch=(col == "memo"))
        self.tree.pack(fill="both", expand=True, padx=10, pady=(4, 5))
        self.tree.bind("<Double-1>", lambda event: self.edit_selected())

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="新規作成", command=self.add).pack(side="left", padx=5)
        ttk.Button(btns, text="編集", command=self.edit_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="上へ", command=lambda: self.move_selected("up")).pack(side="left", padx=5)
        ttk.Button(btns, text="下へ", command=lambda: self.move_selected("down")).pack(side="left", padx=5)
        ttk.Button(btns, text="無効化", command=self.disable_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="閉じる", command=self.close_window).pack(side="right", padx=5)
        self.refresh()
        enable_enter_key_navigation(self)

    def refresh(self, select_id=None):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item in db.list_department_hierarchy(self.conn, include_inactive=True):
            self.tree.insert(
                "",
                "end",
                iid=str(item["id"]),
                values=(
                    item["id"],
                    item["department_type_label"],
                    item["display_name"],
                    item["parent_name"],
                    "○" if item["is_active"] else "",
                    item["memo"],
                ),
            )
        if select_id is not None and self.tree.exists(str(select_id)):
            self.tree.selection_set(str(select_id))
            self.tree.see(str(select_id))

    def _selected_row(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        return db.get_named_master_by_id(self.conn, "departments", int(vals[0])) if vals else None

    def add(self):
        dlg = DepartmentEditorDialog(self, self.conn, on_saved=self.refresh)
        self.wait_window(dlg)

    def edit_selected(self):
        row = self._selected_row()
        if not row:
            messagebox.showinfo("確認", "行を選択してください。", parent=self)
            return
        dlg = DepartmentEditorDialog(self, self.conn, row=row, on_saved=self.refresh)
        self.wait_window(dlg)

    def disable_selected(self):
        row = self._selected_row()
        if not row:
            messagebox.showinfo("確認", "行を選択してください。", parent=self)
            return
        if messagebox.askyesno("確認", f"{row['name']} を無効化しますか？", parent=self):
            db.soft_delete_named_master(self.conn, "departments", row["id"])
            self.refresh()

    def move_selected(self, direction):
        row = self._selected_row()
        if not row:
            messagebox.showinfo("確認", "行を選択してください。", parent=self)
            return
        db.move_department_display_order(self.conn, row["id"], direction, include_inactive=True)
        self.refresh(select_id=row["id"])

    def close_window(self):
        self.winfo_toplevel().destroy()


class PayrollCategoryEditorDialog(tk.Toplevel):
    def __init__(self, parent, conn, row=None, on_saved=None):
        super().__init__(parent)
        self.withdraw()
        self.conn = conn
        self.row = row
        self.on_saved = on_saved
        self.title("支給控除マスタ（大分類）")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.var_name = tk.StringVar()
        self.var_kind = tk.StringVar(value=ITEM_KIND_LABELS["pay"])
        self.var_active = tk.IntVar(value=1)
        self.var_memo = tk.StringVar()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        for i, (label, widget) in enumerate([
            ("大分類名", ttk.Entry(frm, textvariable=self.var_name, width=24)),
            ("区分", ttk.Combobox(frm, textvariable=self.var_kind, values=list(ITEM_KIND_LABELS.values()), width=18, state="readonly")),
            ("メモ", ttk.Entry(frm, textvariable=self.var_memo, width=34)),
        ]):
            ttk.Label(frm, text=label).grid(row=i, column=0, padx=5, pady=5, sticky="w")
            widget.grid(row=i, column=1, padx=5, pady=5, sticky="w")
        ttk.Checkbutton(frm, text="有効", variable=self.var_active).grid(row=3, column=1, padx=5, pady=5, sticky="w")
        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", padx=5, pady=(10, 0))
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")
        if row:
            self.var_name.set(row["name"])
            self.var_kind.set(ITEM_KIND_LABELS.get(row["item_kind"], row["item_kind"]))
            self.var_active.set(int(row["is_active"] or 0))
            self.var_memo.set(row["memo"] or "")
        enable_enter_key_navigation(self)
        show_centered_window(self, parent)

    def save(self):
        name = self.var_name.get().strip()
        if not name:
            messagebox.showerror("入力エラー", "大分類名は必須です。", parent=self)
            return
        item_kind = ITEM_KIND_REVERSE_LABELS.get(self.var_kind.get().strip(), "")
        if not item_kind:
            messagebox.showerror("入力エラー", "区分を選択してください。", parent=self)
            return
        db.upsert_payroll_item_category(
            self.conn,
            None,
            name,
            item_kind,
            None,
            int(self.var_active.get()),
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


class PayrollCategoryFrame(ttk.Frame):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        desc = (
            "この画面では、支給・控除項目をまとめる分類を設定します。\n"
            "例：基本給系、手当、残業代、通勤手当、控除、システム控除\n"
            "通常は初期設定のままで使用できます。"
        )
        ttk.Label(self, text=desc, justify="left").pack(anchor="w", padx=10, pady=(10, 5))
        self.tree = ttk.Treeview(
            self,
            columns=("id", "kind", "name", "active", "memo"),
            displaycolumns=("kind", "name", "active", "memo"),
            show="headings",
            height=12,
        )
        for col, label, width, anchor in [
            ("kind", "区分", 110, "center"),
            ("name", "大分類名", 170, "w"),
            ("active", "有効", 50, "center"),
            ("memo", "メモ", 220, "w"),
        ]:
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
        ttk.Button(btns, text="上へ", command=lambda: self.move_selected("up")).pack(side="left", padx=5)
        ttk.Button(btns, text="下へ", command=lambda: self.move_selected("down")).pack(side="left", padx=5)
        ttk.Button(btns, text="無効化", command=self.disable_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="閉じる", command=lambda: self.winfo_toplevel().destroy()).pack(side="right", padx=5)

    def refresh(self, select_id=None):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in db.list_payroll_item_categories(self.conn, include_inactive=True):
            self.tree.insert(
                "",
                "end",
                iid=str(r["id"]),
                values=(
                    r["id"],
                    ITEM_KIND_LABELS.get(r["item_kind"], r["item_kind"]),
                    r["name"],
                    "○" if r["is_active"] else "",
                    r["memo"] or "",
                ),
            )
        if select_id is not None and self.tree.exists(str(select_id)):
            self.tree.selection_set(str(select_id))
            self.tree.see(str(select_id))

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

    def move_selected(self, direction):
        row = self._selected_row()
        if not row:
            messagebox.showinfo("確認", "行を選択してください。", parent=self)
            return
        db.move_display_order(self.conn, "payroll_item_categories", row["id"], direction, include_inactive=True)
        self.refresh(select_id=row["id"])


class PayrollItemEditorDialog(tk.Toplevel):
    def __init__(self, parent, conn, row=None, on_saved=None):
        super().__init__(parent)
        self.withdraw()
        self.conn = conn
        self.row = row
        self.on_saved = on_saved
        self.title("支給控除マスタ（中分類）")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.var_name = tk.StringVar()
        self.var_kind = tk.StringVar(value=ITEM_KIND_LABELS["pay"])
        self.var_category = tk.StringVar()
        self.var_system = tk.IntVar(value=0)
        self.var_active = tk.IntVar(value=1)
        self.var_taxable = tk.IntVar(value=0)
        self.var_social = tk.IntVar(value=0)
        self.var_emp = tk.IntVar(value=0)
        self.var_commute = tk.IntVar(value=0)
        self.var_memo = tk.StringVar()
        self.category_options = []

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="中分類名（給与明細に表示される項目名）").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_name, width=24).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frm, text="区分").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Combobox(
            frm,
            textvariable=self.var_kind,
            values=[ITEM_KIND_LABELS[k] for k in ("pay", "deduction", "system_deduction")],
            width=18,
            state="readonly",
        ).grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(frm, text="大分類").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Combobox(frm, textvariable=self.var_category, values=self.load_categories(), width=22, state="readonly").grid(row=2, column=1, padx=5, pady=5, sticky="w")
        checks = ttk.Frame(frm)
        checks.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky="w")
        for text, var in [("有効", self.var_active), ("課税対象", self.var_taxable), ("社会保険対象", self.var_social), ("雇用保険対象", self.var_emp), ("通勤手当", self.var_commute)]:
            ttk.Checkbutton(checks, text=text, variable=var).pack(side="left", padx=(0, 8))
        ttk.Label(frm, text="メモ").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frm, textvariable=self.var_memo, width=36).grid(row=4, column=1, padx=5, pady=5, sticky="w")
        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, padx=5, pady=(10, 0), sticky="e")
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")
        if row:
            self.load_row(row)
        enable_enter_key_navigation(self)
        show_centered_window(self, parent)

    def load_categories(self):
        rows = db.list_payroll_item_categories(self.conn)
        name_counts = {}
        for r in rows:
            name_counts[r["name"]] = name_counts.get(r["name"], 0) + 1
        self.category_options = [
            (r["name"] if name_counts[r["name"]] == 1 else f'{r["name"]}（ID {r["id"]}）', r["id"])
            for r in rows
        ]
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
        self.var_name.set(row["name"])
        self.var_kind.set(ITEM_KIND_LABELS.get(row["item_kind"], row["item_kind"]))
        self.set_category(row["category_id"])
        self.var_system.set(int(row["is_system"] or 0))
        self.var_active.set(int(row["is_active"] or 0))
        self.var_taxable.set(int(row["is_taxable"] or 0))
        self.var_social.set(int(row["is_social_insurance_base"] or 0))
        self.var_emp.set(int(row["is_employment_insurance_base"] or 0))
        self.var_commute.set(int(row["is_commute"] or 0))
        self.var_memo.set(row["memo"] or "")

    def save(self):
        name = self.var_name.get().strip()
        if not name:
            messagebox.showerror("入力エラー", "中分類名は必須です。", parent=self)
            return
        item_kind = ITEM_KIND_REVERSE_LABELS.get(self.var_kind.get().strip(), "")
        if not item_kind:
            messagebox.showerror("入力エラー", "区分を選択してください。", parent=self)
            return
        db.upsert_payroll_item(
            self.conn, None, name, item_kind,
            self.category_id(), 1 if item_kind == "system_deduction" else 0, int(self.var_active.get()), int(self.var_taxable.get()),
            int(self.var_social.get()), int(self.var_emp.get()), int(self.var_commute.get()), None,
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
        desc = (
            "この画面では、給与明細や月次入力画面に表示する支給・控除項目を設定します。\n"
            "例：基本給、役員報酬、住宅手当、資格手当、社宅控除、食事代控除\n"
            "追加した項目は、部署・役職・雇用区分などの条件に応じて表示できます。"
        )
        ttk.Label(self, text=desc, justify="left").pack(anchor="w", padx=10, pady=(10, 5))
        self.tree = ttk.Treeview(
            self,
            columns=("id", "kind", "category", "name", "taxable", "social", "emp", "commute", "active", "memo"),
            displaycolumns=("kind", "category", "name", "taxable", "social", "emp", "commute", "active", "memo"),
            show="headings",
            height=12,
        )
        for col, label, width, anchor in [
            ("kind", "区分", 100, "center"),
            ("category", "大分類", 130, "w"),
            ("name", "中分類名", 150, "w"),
            ("taxable", "課税", 60, "center"),
            ("social", "社保", 60, "center"),
            ("emp", "雇保", 60, "center"),
            ("commute", "通勤", 60, "center"),
            ("active", "有効", 50, "center"),
            ("memo", "メモ", 180, "w"),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor=anchor, stretch=(col in {"name", "category", "memo"}))
        self.tree.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        self.tree.bind("<Double-1>", lambda e: self.edit_selected())
        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btns, text="新規作成", command=self.add).pack(side="left", padx=5)
        ttk.Button(btns, text="編集", command=self.edit_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="上へ", command=lambda: self.move_selected("up")).pack(side="left", padx=5)
        ttk.Button(btns, text="下へ", command=lambda: self.move_selected("down")).pack(side="left", padx=5)
        ttk.Button(btns, text="無効化", command=self.disable_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="閉じる", command=lambda: self.winfo_toplevel().destroy()).pack(side="right", padx=5)
        self.refresh()
        enable_enter_key_navigation(self)

    def refresh(self, select_id=None):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in db.list_payroll_items(self.conn, include_inactive=True):
            self.tree.insert(
                "",
                "end",
                iid=str(r["id"]),
                values=(
                    r["id"],
                    ITEM_KIND_LABELS.get(r["item_kind"], r["item_kind"]),
                    r["category_name"] or "",
                    r["name"],
                    "○" if r["is_taxable"] else "",
                    "○" if r["is_social_insurance_base"] else "",
                    "○" if r["is_employment_insurance_base"] else "",
                    "○" if r["is_commute"] else "",
                    "○" if r["is_active"] else "",
                    r["memo"] or "",
                ),
            )
        if select_id is not None and self.tree.exists(str(select_id)):
            self.tree.selection_set(str(select_id))
            self.tree.see(str(select_id))

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

    def move_selected(self, direction):
        row = self._selected_row()
        if not row:
            messagebox.showinfo("確認", "行を選択してください。", parent=self)
            return
        db.move_display_order(self.conn, "payroll_items", row["id"], direction, include_inactive=True)
        self.refresh(select_id=row["id"])


class EmployeeStandardValueDialog(tk.Toplevel):
    def __init__(self, parent, conn, on_saved=None):
        super().__init__(parent)
        self.withdraw()
        self.conn = conn
        self.on_saved = on_saved
        self.title("社員別標準金額")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.employee_options = [(f'{r["employee_code"]} {r["name_kanji"]}', r["employee_id"]) for r in db.list_employees(conn)]
        item_rows = db.list_payroll_items(conn)
        item_name_counts = {}
        for r in item_rows:
            item_name_counts[r["name"]] = item_name_counts.get(r["name"], 0) + 1
        self.item_options = [
            (r["name"] if item_name_counts[r["name"]] == 1 else f'{r["name"]}（ID {r["id"]}）', r["id"])
            for r in item_rows
        ]
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
        show_centered_window(self, parent)

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
