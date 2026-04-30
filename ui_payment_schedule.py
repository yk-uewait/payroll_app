import tkinter as tk
from tkinter import ttk, messagebox
from ui_window_utils import center_window

CLOSING_MODE_MAP = {
    "same_month": "当月",
    "next_month": "翌月",
}
# 逆引き（表示ラベル→キー）
CLOSING_MODE_REVERSE_MAP = {v: k for k, v in CLOSING_MODE_MAP.items()}

def closing_mode_label(mode: str) -> str:
    return CLOSING_MODE_MAP.get(mode, mode or "")


class PaymentScheduleEditorDialog(tk.Toplevel):
    def __init__(self, parent, conn, payment_schedule_id=None, on_saved=None):
        super().__init__(parent)
        self.conn = conn
        self.payment_schedule_id = payment_schedule_id
        self.on_saved = on_saved

        self.title("給与支給方式")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.var_name = tk.StringVar()
        self.var_closing_mode = tk.StringVar(value="same_month")
        self.var_pay_day = tk.IntVar(value=25)
        self.var_is_active = tk.IntVar(value=1)

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="名称").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frm, textvariable=self.var_name, width=28).grid(row=0, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(frm, text="支給タイミング").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Combobox(
            frm,
            textvariable=self.var_closing_mode,
            values=list(CLOSING_MODE_MAP.values()),  # ["当月", "翌月"]
            state="readonly",
            width=12,
        ).grid(row=1, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(frm, text="支給日").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Spinbox(frm, from_=1, to=31, textvariable=self.var_pay_day, width=8).grid(
            row=2, column=1, sticky="w", padx=5, pady=5
        )

        ttk.Checkbutton(frm, text="有効", variable=self.var_is_active).grid(
            row=3, column=1, sticky="w", padx=5, pady=5
        )

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", padx=5, pady=(10, 0))
        ttk.Button(btns, text="保存", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="閉じる", command=self.close).pack(side="left")

        if self.payment_schedule_id:
            self.load_schedule()

        self.bind("<Return>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.close())
        center_window(self, parent)
        self.after(10, lambda: self.focus_force())

    def load_schedule(self):
        import db

        row = db.get_payment_schedule_by_id(self.conn, self.payment_schedule_id)
        if not row:
            messagebox.showerror("エラー", "給与支給方式が見つかりません。")
            self.close()
            return

        self.var_name.set(row["schedule_name"] or "")
        mode_key = row["closing_mode"] or "same_month"  # DB上のキー
        self.var_closing_mode.set(CLOSING_MODE_MAP.get(mode_key, mode_key))

        self.var_pay_day.set(int(row["pay_day"] or 25))
        self.var_is_active.set(int(row["is_active"] or 0))

    def save(self):
        name = self.var_name.get().strip()
        closing_mode_label_str = self.var_closing_mode.get().strip()
        closing_mode = CLOSING_MODE_REVERSE_MAP.get(closing_mode_label_str, "")
        is_active = int(self.var_is_active.get() or 0)

        try:
            pay_day = int(self.var_pay_day.get() or 0)
        except Exception:
            messagebox.showerror("入力エラー", "支給日は数字で入力してください。")
            return

        if not name:
            messagebox.showerror("入力エラー", "名称は必須です。")
            return

        if closing_mode not in CLOSING_MODE_MAP.keys():
            messagebox.showerror("入力エラー", "支給タイミングが不正です。")
            return

        if not (1 <= pay_day <= 31):
            messagebox.showerror("入力エラー", "支給日は1～31で入力してください。")
            return

        import db

        try:
            db.upsert_payment_schedule(
                self.conn,
                schedule_name=name,
                closing_mode=closing_mode,
                pay_day=pay_day,
                is_active=is_active,
                payment_schedule_id=self.payment_schedule_id,
            )
        except Exception as e:
            messagebox.showerror("保存エラー", f"保存に失敗しました。\n詳細: {e}")
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


class PaymentScheduleFrame(ttk.Frame):
    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Button(top, text="追加", command=self.add_schedule).pack(side="left", padx=5)
        ttk.Button(top, text="更新", command=self.edit_selected).pack(side="left", padx=5)
        ttk.Button(top, text="有効/無効切替", command=self.toggle_active_selected).pack(side="left", padx=5)
        ttk.Button(top, text="再読み込み", command=self.refresh).pack(side="right", padx=5)

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        yscroll = ttk.Scrollbar(tree_frame, orient="vertical")

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("id", "name", "closing_mode", "pay_day", "is_active"),
            show="headings",
            height=14,
            yscrollcommand=yscroll.set,
        )
        yscroll.config(command=self.tree.yview)

        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="名称")
        self.tree.heading("closing_mode", text="支給タイミング")
        self.tree.heading("pay_day", text="支給日")
        self.tree.heading("is_active", text="有効")

        self.tree.column("id", width=60, anchor="e")
        self.tree.column("name", width=220, anchor="w")
        self.tree.column("closing_mode", width=110, anchor="center")
        self.tree.column("pay_day", width=90, anchor="e")
        self.tree.column("is_active", width=80, anchor="center")

        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self.on_double_click)

        self.refresh()

    def refresh(self):
        import db

        for i in self.tree.get_children():
            self.tree.delete(i)

        for r in db.list_payment_schedules_all(self.conn):
            self.tree.insert(
                "",
                "end",
                values=(
                    r["payment_schedule_id"],
                    r["schedule_name"],
                    closing_mode_label(r["closing_mode"]),
                    r["pay_day"],
                    "有効" if int(r["is_active"] or 0) == 1 else "無効",
                ),
            )

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return None
        return int(vals[0])

    def add_schedule(self):
        dlg = PaymentScheduleEditorDialog(self, self.conn, payment_schedule_id=None, on_saved=self.refresh)
        self.wait_window(dlg)

    def edit_selected(self):
        payment_schedule_id = self._selected_id()
        if payment_schedule_id is None:
            messagebox.showwarning("確認", "給与支給方式を選択してください。")
            return

        dlg = PaymentScheduleEditorDialog(
            self,
            self.conn,
            payment_schedule_id=payment_schedule_id,
            on_saved=self.refresh,
        )
        self.wait_window(dlg)

    def toggle_active_selected(self):
        payment_schedule_id = self._selected_id()
        if payment_schedule_id is None:
            messagebox.showwarning("確認", "給与支給方式を選択してください。")
            return

        import db

        row = db.get_payment_schedule_by_id(self.conn, payment_schedule_id)
        if not row:
            messagebox.showerror("エラー", "対象データが見つかりません。")
            return

        new_active = 0 if int(row["is_active"] or 0) == 1 else 1

        try:
            db.upsert_payment_schedule(
                self.conn,
                schedule_name=row["schedule_name"],
                closing_mode=row["closing_mode"],
                pay_day=int(row["pay_day"] or 0),
                is_active=new_active,
                payment_schedule_id=payment_schedule_id,
            )
        except Exception as e:
            messagebox.showerror("更新エラー", f"有効/無効の切替に失敗しました。\n詳細: {e}")
            return

        self.refresh()

    def on_double_click(self, event):
        self.edit_selected()
