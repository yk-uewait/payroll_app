import sqlite3
import json
from pathlib import Path
from datetime import datetime
import calendar
from openpyxl import load_workbook
import math
import re
import app_settings

DB_PATH = Path(__file__).resolve().parent / "payroll.db"

ATTENDANCE_DAY_FIELDS = [
    ("scheduled_work_days", "所定労働日数"),
    ("work_days", "労働日数"),
    ("weekday_work_days", "平日出勤日数"),
    ("holiday_work_days", "休日出勤日数"),
    ("paid_leave_days", "有給取得日数"),
    ("special_leave_days", "特休取得日数"),
    ("absence_days", "欠勤日数"),
    ("substitute_leave_taken_days", "振休取得日数"),
    ("substitute_leave_remaining_days", "振休残日数"),
]
ATTENDANCE_COUNT_FIELDS = [
    ("late_count", "遅刻回数"),
    ("early_leave_count", "早退回数"),
]
ATTENDANCE_TIME_FIELDS = [
    ("scheduled_work_minutes", "所定労働時間"),
    ("work_minutes", "労働時間数"),
    ("non_scheduled_work_minutes", "所定外労働時間"),
    ("overtime_minutes", "時間外労働時間"),
    ("holiday_work_minutes", "休日労働時間"),
    ("night_work_minutes", "深夜労働時間"),
    ("holiday_night_work_minutes", "休日深夜労働時間"),
    ("late_early_leave_minutes", "遅刻早退時間"),
    ("total_overtime_minutes", "総残業時間"),
]
ATTENDANCE_FIELDS = ATTENDANCE_DAY_FIELDS + ATTENDANCE_COUNT_FIELDS + ATTENDANCE_TIME_FIELDS
WAGE_LEDGER_ATTENDANCE_FIELDS = [
    ("scheduled_work_days", "所定労働日数"),
    ("work_days", "労働日数"),
    ("work_minutes", "労働時間数"),
    ("overtime_minutes", "時間外労働時間"),
    ("holiday_work_minutes", "休日労働時間"),
    ("night_work_minutes", "深夜労働時間"),
    ("paid_leave_days", "有給取得日数"),
    ("absence_days", "欠勤日数"),
    ("late_count", "遅刻回数"),
    ("early_leave_count", "早退回数"),
    ("late_early_leave_minutes", "遅刻早退時間"),
    ("total_overtime_minutes", "総残業時間"),
]

EMPLOYEE_CSV_COLUMNS = [
    "社員番号",
    "氏名",
    "フリガナ",
    "部署",
    "給与支給方式",
    "給与支給方式ID",
    "支給日",
    "標準報酬月額（健保）",
    "標準報酬月額（厚年）",
    "社会保険加入対象",
    "雇用保険加入対象",
    "生年月日",
    "入社日",
    "退職日",
    "退職処理済み",
    "源泉",
    "扶養人数",
    "都道府県",
    "郵便番号",
    "住所都道府県",
    "市区町村",
    "住所",
    "住民税市区町村",
    "電話番号",
    "メールアドレス",
    "銀行名",
    "支店名",
    "口座種別",
    "口座番号",
    "口座名義",
    "メモ",
]

def get_employee_payment_schedule_display(e, conn):
    if e["payment_schedule_id"]:
        sched = get_payment_schedule_by_id(conn, e["payment_schedule_id"])
        if sched:
            return sched["schedule_name"]
    return f"{e['payday_group']}日"

def calc_pay_date(target_month: str, closing_mode: str, pay_day: int) -> str:
    y, m = map(int, target_month.split("-"))

    month_offset = 0
    if closing_mode == "next_month":
        month_offset = 1
    elif closing_mode == "two_months_later":
        month_offset = 2

    for _ in range(month_offset):
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1

    last_day = calendar.monthrange(y, m)[1]
    d = min(int(pay_day), last_day)
    return f"{y:04d}-{m:02d}-{d:02d}"

def list_payment_schedules(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM payment_schedules
        WHERE is_active = 1
        ORDER BY pay_day, payment_schedule_id
        """
    )
    return cur.fetchall()

def get_payment_schedule_by_id(conn, payment_schedule_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM payment_schedules
        WHERE payment_schedule_id = ?
        """,
        (payment_schedule_id,),
    )
    return cur.fetchone()

def upsert_payment_schedule(
    conn,
    schedule_name: str,
    closing_mode: str,
    pay_day: int,
    is_active: int = 1,
    payment_schedule_id: int | None = None,
    memo: str | None = None,
):
    cur = conn.cursor()
    if payment_schedule_id is None:
        cur.execute(
            """
            INSERT INTO payment_schedules(
                schedule_name, closing_mode, pay_day, is_active, memo
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (schedule_name, closing_mode, pay_day, is_active, memo),
        )
    else:
        cur.execute(
            """
            UPDATE payment_schedules
            SET schedule_name=?,
                closing_mode=?,
                pay_day=?,
                is_active=?,
                memo=?,
                updated_at=datetime('now')
            WHERE payment_schedule_id=?
            """,
            (schedule_name, closing_mode, pay_day, is_active, memo, payment_schedule_id),
        )
    conn.commit()

def list_payment_schedules_all(conn, include_inactive: bool = False):
    cur = conn.cursor()
    if include_inactive:
        cur.execute(
            """
            SELECT *
            FROM payment_schedules
            ORDER BY is_active DESC, pay_day ASC, payment_schedule_id ASC
            """
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM payment_schedules
            WHERE is_active = 1
            ORDER BY pay_day ASC, payment_schedule_id ASC
            """
        )
    return cur.fetchall()

def soft_delete_payment_schedule(conn, payment_schedule_id: int) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE payment_schedules
        SET is_active = 0,
            updated_at = datetime('now')
        WHERE payment_schedule_id = ? AND is_active = 1
        """,
        (payment_schedule_id,),
    )
    conn.commit()
    return cur.rowcount > 0

def set_payment_schedule_active(conn, payment_schedule_id: int, is_active: int) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE payment_schedules
        SET is_active = ?,
            updated_at = datetime('now')
        WHERE payment_schedule_id = ?
        """,
        (int(is_active or 0), payment_schedule_id),
    )
    conn.commit()
    return cur.rowcount > 0

def connect(db_path) -> sqlite3.Connection:
    """
    指定されたDBパスへ接続する。
    app.py から保存先フォルダを選ばせる運用用。
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def create_connection():
    """
    db.py と同じフォルダの payroll.db に接続する簡易用。
    テストや単体実行向け。
    """
    return connect(DB_PATH)

def row_get(r, key, default=None):
    """sqlite3.Row / dict 両対応の安全なgetter"""
    try:
        # sqlite3.Row は r[key] で取れる
        return r[key]
    except Exception:
        try:
            # dict 等なら get がある
            return r.get(key, default)
        except Exception:
            return default
        
WITHHOLDING_YEAR_DEFAULT = 2026  # 令和8年

def normalize_employee_code(employee_code) -> str:
    code = str(employee_code or "").strip()
    if not code:
        raise ValueError("社員番号を入力してください。")
    if not code.isdigit():
        raise ValueError("社員番号は数字で入力してください。")
    if len(code) > 5:
        raise ValueError("社員番号は5桁以内で入力してください。")
    number = int(code)
    if number < 1 or number > 99999:
        raise ValueError("社員番号は1〜99999の範囲で入力してください。")
    return f"{number:05d}"

def _normalize_existing_employee_codes(conn):
    rows = conn.execute(
        """
        SELECT employee_id, employee_code
        FROM employees
        WHERE employee_code IS NOT NULL AND TRIM(employee_code) <> ''
        """
    ).fetchall()
    targets = {}
    for row in rows:
        raw = str(row["employee_code"]).strip()
        if raw.isdigit() and len(raw) <= 5 and 1 <= int(raw) <= 99999:
            normalized = f"{int(raw):05d}"
            targets.setdefault(normalized, []).append((int(row["employee_id"]), raw))

    conflicted = {
        code
        for code, items in targets.items()
        if len({raw for _employee_id, raw in items}) > 1
    }
    for normalized, items in targets.items():
        if normalized in conflicted:
            continue
        for employee_id, raw in items:
            if raw != normalized:
                conn.execute(
                    "UPDATE employees SET employee_code = ?, updated_at = datetime('now') WHERE employee_id = ?",
                    (normalized, employee_id),
                )

# Dynamic payroll item migration flags.
# Keep tax/insurance calculations on the legacy fixed-column path until each
# area is verified in a later phase.
USE_DYNAMIC_ITEMS_FOR_TOTALS = True
USE_DYNAMIC_ITEMS_FOR_EMPLOYMENT_INSURANCE = True
USE_DYNAMIC_ITEMS_FOR_TAXABLE_PAY = True
USE_DYNAMIC_ITEMS_FOR_SOCIAL_INSURANCE_BASE = False


def round_half_up(value: float) -> int:
    """0.5以上切り上げ、0.5未満切り捨て"""
    return int(math.floor(value + 0.5))

def round_down(value: float) -> int:
    """小数点以下切り捨て"""
    return int(math.floor(value))

def get_age_on_date(birth_date_str: str | None, target_date_str: str) -> int | None:
    """
    birth_date_str: 'yyyy-mm-dd'
    target_date_str: 'yyyy-mm' または 'yyyy-mm-dd'
    """
    if not birth_date_str:
        return None

    try:
        birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
    except Exception:
        return None

    try:
        if len(target_date_str) == 7:
            y, m = map(int, target_date_str.split("-"))
            last_day = calendar.monthrange(y, m)[1]
            target_date = datetime.strptime(f"{target_date_str}-{last_day:02d}", "%Y-%m-%d").date()
        else:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    except Exception:
        return None

    age = target_date.year - birth_date.year
    if (target_date.month, target_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age

def is_care_insurance_applicable(birth_date_str: str | None, target_date_str: str) -> bool:
    age = get_age_on_date(birth_date_str, target_date_str)
    if age is None:
        return False
    return 40 <= age < 65

def init_db(conn: sqlite3.Connection, schema_path: Path) -> None:
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()

    # 既存DBに必要な列がなければ追加
    ensure_schema_migrations(conn)
    seed_payment_schedules(conn)
    seed_phase1_masters(conn)

def seed_payment_schedules(conn):
    cur = conn.cursor()
    seeds = [
        ("当月25日払い", "same_month", 25),
        ("翌月15日払い", "next_month", 15),
    ]
    for schedule_name, closing_mode, pay_day in seeds:
        cur.execute(
            """
            INSERT OR IGNORE INTO payment_schedules(schedule_name, closing_mode, pay_day)
            VALUES (?, ?, ?)
            """,
            (schedule_name, closing_mode, pay_day),
        )
    conn.commit()    

def _upsert_seed(conn, table: str, key_col: str, key_val, values: dict):
    cols = [key_col] + list(values.keys())
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"""
        INSERT OR IGNORE INTO {table}({", ".join(cols)})
        VALUES ({placeholders})
    """
    conn.execute(sql, [key_val] + list(values.values()))

def seed_phase1_masters(conn):
    conn.execute(
        """
        INSERT OR IGNORE INTO company_settings(id, company_name)
        VALUES (1, '')
        """
    )

    for idx, name in enumerate(["役員", "正社員", "契約社員", "パート", "アルバイト"], start=1):
        _upsert_seed(
            conn,
            "employment_types",
            "name",
            name,
            {"display_order": idx * 10, "is_active": 1, "memo": None},
        )

    categories = [
        ("basic_pay", "基本給系", "pay", 10),
        ("officer_pay", "役員報酬系", "pay", 20),
        ("allowance", "手当", "pay", 30),
        ("overtime", "残業代", "pay", 40),
        ("commute", "通勤手当", "pay", 50),
        ("deduction", "控除", "deduction", 60),
        ("system_deduction", "システム控除", "system_deduction", 70),
        ("other", "その他", "other", 90),
    ]
    for code, name, kind, order in categories:
        _upsert_seed(
            conn,
            "payroll_item_categories",
            "code",
            code,
            {"name": name, "item_kind": kind, "display_order": order, "is_active": 1, "memo": None},
        )

    cat_map = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM payroll_item_categories")}
    items = [
        ("officer_pay", "役員報酬", "pay", "officer_pay", 0, 1, 1, 1, 0, 0, 10),
        ("base_salary", "基本給", "pay", "basic_pay", 0, 1, 1, 1, 1, 0, 20),
        ("overtime_pay", "残業手当", "pay", "overtime", 0, 1, 1, 1, 1, 0, 30),
        ("commute_nontax", "非課税通勤手当", "pay", "commute", 0, 1, 0, 1, 1, 1, 40),
        ("health_ins_employee", "健康保険料", "system_deduction", "system_deduction", 1, 1, 0, 0, 0, 0, 1010),
        ("care_ins_employee", "介護保険料", "system_deduction", "system_deduction", 1, 1, 0, 0, 0, 0, 1020),
        ("childcare_support_employee", "子ども・子育て支援金", "system_deduction", "system_deduction", 1, 1, 0, 0, 0, 0, 1030),
        ("pension_ins_employee", "厚生年金保険料", "system_deduction", "system_deduction", 1, 1, 0, 0, 0, 0, 1040),
        ("emp_ins_employee", "雇用保険料", "system_deduction", "system_deduction", 1, 1, 0, 0, 0, 0, 1050),
        ("withholding_tax", "源泉所得税", "system_deduction", "system_deduction", 1, 1, 0, 0, 0, 0, 1060),
        ("resident_tax", "住民税", "system_deduction", "system_deduction", 1, 1, 0, 0, 0, 0, 1070),
    ]
    for code, name, kind, cat_code, is_system, is_active, taxable, social, emp, commute, order in items:
        _upsert_seed(
            conn,
            "payroll_items",
            "code",
            code,
            {
                "name": name,
                "item_kind": kind,
                "category_id": cat_map.get(cat_code),
                "is_system": is_system,
                "is_active": is_active,
                "is_taxable": taxable,
                "is_social_insurance_base": social,
                "is_employment_insurance_base": emp,
                "is_commute": commute,
                "display_order": order,
                "memo": None,
            },
        )
    item_map = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM payroll_items")}
    employment_map = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM employment_types")}
    assignment_seeds = [
        ("officer_pay", "employment_type", employment_map.get("役員"), "include", 10),
        ("base_salary", "employment_type", employment_map.get("役員"), "exclude", 20),
        ("base_salary", "all", None, "include", 21),
        ("overtime_pay", "employment_type", employment_map.get("役員"), "exclude", 30),
        ("overtime_pay", "all", None, "include", 31),
        ("commute_nontax", "all", None, "include", 40),
    ]
    for item_code, target_type, employment_type_id, action, order in assignment_seeds:
        item_id = item_map.get(item_code)
        if not item_id:
            continue
        existing = conn.execute(
            """
            SELECT id
            FROM payroll_item_assignments
            WHERE item_id = ?
              AND target_type = ?
              AND COALESCE(employment_type_id, 0) = COALESCE(?, 0)
              AND action = ?
            """,
            (item_id, target_type, employment_type_id, action),
        ).fetchone()
        if not existing:
            conn.execute(
                """
                INSERT INTO payroll_item_assignments(
                  item_id, target_type, employment_type_id, action, is_active, display_order
                )
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (item_id, target_type, employment_type_id, action, order),
            )
    conn.commit()

def upsert_employee(
    conn,
    employee_code,
    name_kanji,
    department,
    payday_group,
    std_health,
    std_pension,
    tax_type="甲",
    dependents_count=0,
    work_prefecture_name="",
    address_postal_code="",
    address_prefecture="",
    address_city="",
    address_detail="",
    resident_tax_municipality="",
    birth_date=None,
    payment_schedule_id=None,
    hire_date=None,
    is_on_leave=0,
    leave_start_date=None,
    leave_expected_end_date=None,
    leave_memo="",
    leave_date=None,
    retirement_processed=0,
    memo=None,
    department_id=None,
    position_id=None,
    employment_type_id=None,
    name_kana="",
    phone="",
    email="",
    bank_name="",
    bank_branch_name="",
    bank_account_type="",
    bank_account_number="",
    bank_account_holder="",
    is_social_insurance_target=0,
    is_employment_insurance_target=1,
):
    employee_code = normalize_employee_code(employee_code)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO employees(
          employee_code, name_kanji, name_kana, department, payday_group,
          std_monthly_wage, std_pension_wage, is_social_insurance_target, is_employment_insurance_target,
          tax_type, dependents_count, work_prefecture_name,
          address_postal_code, address_prefecture, address_city, address_detail, resident_tax_municipality,
          phone, email, bank_name, bank_branch_name, bank_account_type, bank_account_number, bank_account_holder,
          birth_date,
          payment_schedule_id, hire_date, is_on_leave, leave_start_date, leave_expected_end_date, leave_memo,
          leave_date, retirement_processed, memo,
          department_id, position_id, employment_type_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(employee_code) DO UPDATE SET
          name_kanji=excluded.name_kanji,
          name_kana=excluded.name_kana,
          department=excluded.department,
          payday_group=excluded.payday_group,
          is_deleted=0,
          deleted_at=NULL,
          std_monthly_wage=excluded.std_monthly_wage,
          std_pension_wage=excluded.std_pension_wage,
          is_social_insurance_target=excluded.is_social_insurance_target,
          is_employment_insurance_target=excluded.is_employment_insurance_target,
          tax_type=excluded.tax_type,
          dependents_count=excluded.dependents_count,
          work_prefecture_name=excluded.work_prefecture_name,
          address_postal_code=excluded.address_postal_code,
          address_prefecture=excluded.address_prefecture,
          address_city=excluded.address_city,
          address_detail=excluded.address_detail,
          resident_tax_municipality=excluded.resident_tax_municipality,
          phone=excluded.phone,
          email=excluded.email,
          bank_name=excluded.bank_name,
          bank_branch_name=excluded.bank_branch_name,
          bank_account_type=excluded.bank_account_type,
          bank_account_number=excluded.bank_account_number,
          bank_account_holder=excluded.bank_account_holder,
          birth_date=excluded.birth_date,
          payment_schedule_id=excluded.payment_schedule_id,
          hire_date=excluded.hire_date,
          is_on_leave=excluded.is_on_leave,
          leave_start_date=excluded.leave_start_date,
          leave_expected_end_date=excluded.leave_expected_end_date,
          leave_memo=excluded.leave_memo,
          leave_date=excluded.leave_date,
          retirement_processed=excluded.retirement_processed,
          memo=excluded.memo,
          department_id=excluded.department_id,
          position_id=excluded.position_id,
          employment_type_id=excluded.employment_type_id,
          updated_at=datetime('now')
        """,
        (
            employee_code,
            name_kanji,
            name_kana,
            department,
            payday_group,
            std_health,
            std_pension,
            int(is_social_insurance_target or 0),
            int(is_employment_insurance_target or 0),
            tax_type,
            dependents_count,
            work_prefecture_name,
            address_postal_code,
            address_prefecture,
            address_city,
            address_detail,
            resident_tax_municipality,
            phone,
            email,
            bank_name,
            bank_branch_name,
            bank_account_type,
            bank_account_number,
            bank_account_holder,
            birth_date,
            payment_schedule_id,
            hire_date,
            int(is_on_leave or 0),
            leave_start_date,
            leave_expected_end_date,
            leave_memo or "",
            leave_date,
            int(retirement_processed or 0),
            memo,
            department_id,
            position_id,
            employment_type_id,
        ),
    )
    conn.commit()

def get_employee_department_snapshot(conn, employee_id: int) -> tuple[int | None, str]:
    row = conn.execute(
        """
        SELECT department_id, department
        FROM employees
        WHERE employee_id = ?
        """,
        (employee_id,),
    ).fetchone()
    if not row:
        return None, ""
    department_id = row_get(row, "department_id", None)
    fallback_name = row_get(row, "department", "") or ""
    if department_id:
        return int(department_id), get_department_full_name(conn, department_id) or fallback_name
    return None, fallback_name


def _backfill_department_snapshots(conn, table_name: str) -> None:
    if not _table_exists(conn, table_name):
        return
    rows = conn.execute(
        f"""
        SELECT
          t.rowid AS snapshot_rowid,
          t.employee_id,
          t.department_id_snapshot,
          t.department_name_snapshot,
          e.department_id AS current_department_id,
          e.department AS legacy_department
        FROM {table_name} t
        JOIN employees e ON e.employee_id = t.employee_id
        WHERE t.department_id_snapshot IS NULL
           OR COALESCE(t.department_name_snapshot, '') = ''
        """
    ).fetchall()
    for row in rows:
        snapshot_id = row_get(row, "department_id_snapshot", None) or row_get(row, "current_department_id", None)
        legacy_name = row_get(row, "legacy_department", "") or ""
        snapshot_name = row_get(row, "department_name_snapshot", "") or ""
        if snapshot_id and not snapshot_name:
            snapshot_name = get_department_full_name(conn, snapshot_id) or legacy_name
        elif not snapshot_name:
            snapshot_name = legacy_name

        updates = []
        params = []
        if row_get(row, "department_id_snapshot", None) is None:
            updates.append("department_id_snapshot=?")
            params.append(int(snapshot_id) if snapshot_id else None)
        if not (row_get(row, "department_name_snapshot", "") or "").strip():
            updates.append("department_name_snapshot=?")
            params.append(snapshot_name)
        if updates:
            params.append(row_get(row, "snapshot_rowid"))
            conn.execute(
                f"UPDATE {table_name} SET {', '.join(updates)}, updated_at=datetime('now') WHERE rowid=?",
                params,
            )


def _row_with_current_department_name(conn, r) -> dict:
    row = dict(r)
    snapshot_name = (row.get("department_name_snapshot") or "").strip()
    if snapshot_name:
        row["department"] = snapshot_name
        return row

    snapshot_id = row.get("department_id_snapshot")
    if snapshot_id:
        row["department"] = get_department_full_name(conn, snapshot_id) or row.get("department", "")
        return row

    department_id = row.get("department_id")
    if department_id:
        row["department"] = get_department_full_name(conn, department_id) or row.get("department", "")
    return row


def list_employees(conn, include_deleted: bool = False):
    cur = conn.cursor()
    if include_deleted:
        cur.execute(
            """
            SELECT *
            FROM employees
            ORDER BY
              CASE WHEN employee_code GLOB '[0-9][0-9][0-9][0-9][0-9]' THEN 0 ELSE 1 END,
              employee_code,
              employee_id
            """
        )
    else:
        cur.execute(
            """
            SELECT *
            FROM employees
            WHERE COALESCE(is_deleted, 0) = 0
            ORDER BY
              CASE WHEN employee_code GLOB '[0-9][0-9][0-9][0-9][0-9]' THEN 0 ELSE 1 END,
              employee_code,
              employee_id
            """
        )
    rows = cur.fetchall()
    return [_row_with_current_department_name(conn, r) for r in rows]

def soft_delete_employee(conn, employee_id: int) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE employees
        SET is_deleted = 1,
            deleted_at = datetime('now'),
            updated_at = datetime('now')
        WHERE employee_id = ? AND COALESCE(is_deleted, 0) = 0
        """,
        (employee_id,),
    )
    conn.commit()
    return cur.rowcount > 0

def get_company_settings(conn):
    conn.execute("INSERT OR IGNORE INTO company_settings(id, company_name) VALUES (1, '')")
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT * FROM company_settings WHERE id = 1")
    return cur.fetchone()

def upsert_company_settings(
    conn,
    company_name,
    company_kana="",
    postal_code="",
    address="",
    phone="",
    memo=None,
    attendance_time_input_mode="60進法",
    attendance_time_round_unit="1分",
    attendance_time_round_method="なし",
):
    if attendance_time_input_mode not in {"60進法", "10進法"}:
        attendance_time_input_mode = "60進法"
    if attendance_time_round_unit not in {"1分", "5分", "10分", "15分", "30分"}:
        attendance_time_round_unit = "1分"
    if attendance_time_round_method not in {"なし", "切り捨て", "切り上げ", "四捨五入"}:
        attendance_time_round_method = "なし"
    conn.execute(
        """
        INSERT INTO company_settings(
          id, company_name, company_kana, postal_code, address, phone, memo,
          attendance_time_input_mode, attendance_time_round_unit, attendance_time_round_method
        )
        VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          company_name=excluded.company_name,
          company_kana=excluded.company_kana,
          postal_code=excluded.postal_code,
          address=excluded.address,
          phone=excluded.phone,
          memo=excluded.memo,
          attendance_time_input_mode=excluded.attendance_time_input_mode,
          attendance_time_round_unit=excluded.attendance_time_round_unit,
          attendance_time_round_method=excluded.attendance_time_round_method,
          updated_at=datetime('now')
        """,
        (
            company_name,
            company_kana,
            postal_code,
            address,
            phone,
            memo,
            attendance_time_input_mode,
            attendance_time_round_unit,
            attendance_time_round_method,
        ),
    )
    conn.commit()

def get_attendance_time_input_mode(conn) -> str:
    row = get_company_settings(conn)
    mode = row_get(row, "attendance_time_input_mode", "60進法") if row else "60進法"
    return mode if mode in {"60進法", "10進法"} else "60進法"

def parse_attendance_time_to_minutes(value: str, mode: str) -> int:
    text = (value or "").strip()
    if text == "":
        return 0
    if text.startswith("-"):
        raise ValueError("時間はマイナス入力できません。")
    if mode == "10進法":
        if not re.fullmatch(r"\d+(\.\d{1,2})?", text):
            raise ValueError("10進法の時間は 1.50 のように小数第2位までで入力してください。")
        return int(round(float(text) * 60))
    if not re.fullmatch(r"\d+:\d{1,2}", text):
        raise ValueError("60進法の時間は 1:30 のように入力してください。")
    hours_text, minutes_text = text.split(":", 1)
    minutes = int(minutes_text)
    if minutes >= 60:
        raise ValueError("60進法の分は0から59で入力してください。")
    return int(hours_text) * 60 + minutes

def format_attendance_minutes(minutes, mode: str) -> str:
    minutes = int(minutes or 0)
    if mode == "10進法":
        return f"{minutes / 60:.2f}"
    hours, mins = divmod(minutes, 60)
    return f"{hours}:{mins:02d}"

def _attendance_defaults() -> dict:
    data = {key: 0 for key, _label in ATTENDANCE_FIELDS}
    return data

def get_payroll_attendance(conn, payroll_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM payroll_monthly_attendance WHERE payroll_id=?",
        (payroll_id,),
    ).fetchone()
    data = _attendance_defaults()
    if row:
        for key, _label in ATTENDANCE_FIELDS:
            data[key] = row_get(row, key, 0) or 0
        data["id"] = row["id"]
        data["payroll_id"] = row["payroll_id"]
    return data

def upsert_payroll_attendance(
    conn,
    payroll_id: int,
    employee_id: int,
    target_month: str,
    pay_date: str,
    values: dict,
):
    data = _attendance_defaults()
    for key in data:
        data[key] = values.get(key, 0) or 0
    columns = [key for key, _label in ATTENDANCE_FIELDS]
    insert_cols = ["payroll_id", "employee_id", "target_month", "pay_date", *columns]
    placeholders = ", ".join(["?"] * len(insert_cols))
    update_set = ", ".join([f"{col}=excluded.{col}" for col in ["employee_id", "target_month", "pay_date", *columns]])
    sql = f"""
        INSERT INTO payroll_monthly_attendance({", ".join(insert_cols)})
        VALUES ({placeholders})
        ON CONFLICT(payroll_id) DO UPDATE SET
          {update_set},
          updated_at=datetime('now')
    """
    params = [payroll_id, employee_id, target_month, pay_date] + [data[col] for col in columns]
    conn.execute(sql, params)
    conn.commit()

def format_attendance_value_for_output(conn, key: str, value) -> str:
    if key in {field for field, _label in ATTENDANCE_TIME_FIELDS}:
        return format_attendance_minutes(value, get_attendance_time_input_mode(conn))
    if key in {field for field, _label in ATTENDANCE_DAY_FIELDS}:
        try:
            number = float(value or 0)
            return str(int(number)) if number.is_integer() else f"{number:g}"
        except Exception:
            return "0"
    return str(int(value or 0))

def list_named_master(conn, table: str, include_inactive: bool = False):
    if table not in {"departments", "positions", "employment_types"}:
        raise ValueError("invalid master table")
    where = "" if include_inactive else "WHERE is_active = 1"
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT *
        FROM {table}
        {where}
        ORDER BY is_active DESC, display_order ASC, id ASC
        """
    )
    return cur.fetchall()

DEPARTMENT_TYPE_LABELS = {
    "office": "事業所",
    "department": "部署",
    "section": "課・係",
    "other": "その他",
}
DEPARTMENT_TYPE_REVERSE_LABELS = {label: key for key, label in DEPARTMENT_TYPE_LABELS.items()}

def department_type_label(value: str | None) -> str:
    return DEPARTMENT_TYPE_LABELS.get(value or "department", value or "部署")

def list_department_hierarchy(conn, include_inactive: bool = False):
    where = "" if include_inactive else "WHERE is_active = 1"
    rows = conn.execute(
        f"""
        SELECT *,
               COALESCE(parent_department_id, 0) AS parent_id,
               COALESCE(department_type, 'department') AS type_value
        FROM departments
        {where}
        ORDER BY is_active DESC, display_order ASC, id ASC
        """
    ).fetchall()
    by_parent = {}
    by_id = {}
    for row in rows:
        row_id = int(row["id"])
        parent_id = row["parent_department_id"] if "parent_department_id" in row.keys() else None
        by_parent.setdefault(int(parent_id or 0), []).append(row)
        by_id[row_id] = row

    ordered = []
    visited = set()

    def walk(parent_id: int, depth: int, path_names: list[str]):
        for row in by_parent.get(parent_id, []):
            row_id = int(row["id"])
            if row_id in visited:
                continue
            visited.add(row_id)
            name = row["name"] or ""
            full_name = " > ".join([*path_names, name]) if path_names else name
            parent_id_value = int(row["parent_department_id"] or 0) if "parent_department_id" in row.keys() else 0
            ordered.append(
                {
                    "row": row,
                    "id": row_id,
                    "name": name,
                    "display_name": f"{'    ' * depth}{name}",
                    "full_name": full_name,
                    "depth": depth,
                    "parent_id": parent_id_value,
                    "parent_name": " > ".join(path_names),
                    "department_type": row["type_value"],
                    "department_type_label": department_type_label(row["type_value"]),
                    "is_active": int(row["is_active"] or 0),
                    "memo": row["memo"] or "",
                }
            )
            walk(row_id, depth + 1, [*path_names, name])

    walk(0, 0, [])
    for row in rows:
        if int(row["id"]) not in visited:
            walk(int(row["parent_department_id"] or 0), 0, [])
            if int(row["id"]) not in visited:
                name = row["name"] or ""
                ordered.append(
                    {
                        "row": row,
                        "id": int(row["id"]),
                        "name": name,
                        "display_name": name,
                        "full_name": name,
                        "depth": 0,
                        "parent_id": int(row["parent_department_id"] or 0) if "parent_department_id" in row.keys() else 0,
                        "parent_name": "",
                        "department_type": row["type_value"],
                        "department_type_label": department_type_label(row["type_value"]),
                        "is_active": int(row["is_active"] or 0),
                        "memo": row["memo"] or "",
                    }
                )
                visited.add(int(row["id"]))
    return ordered

def get_department_descendant_ids(conn, department_id: int) -> set[int]:
    rows = conn.execute("SELECT id, parent_department_id FROM departments").fetchall()
    children = {}
    for row in rows:
        children.setdefault(int(row["parent_department_id"] or 0), []).append(int(row["id"]))
    result = set()

    def walk(row_id: int):
        for child_id in children.get(row_id, []):
            if child_id in result:
                continue
            result.add(child_id)
            walk(child_id)

    walk(int(department_id))
    return result

def move_department_display_order(conn, row_id: int, direction: str, include_inactive: bool = True) -> bool:
    if direction not in {"up", "down"}:
        raise ValueError("direction must be up or down")
    selected = conn.execute(
        "SELECT id, parent_department_id FROM departments WHERE id=?",
        (row_id,),
    ).fetchone()
    if not selected:
        return False
    where = "" if include_inactive else "AND is_active = 1"
    rows = conn.execute(
        f"""
        SELECT id, COALESCE(display_order, 0) AS display_order
        FROM departments
        WHERE COALESCE(parent_department_id, 0) = ?
        {where}
        ORDER BY is_active DESC, COALESCE(display_order, 0) ASC, id ASC
        """,
        (int(selected["parent_department_id"] or 0),),
    ).fetchall()
    for idx, row in enumerate(rows, start=1):
        conn.execute("UPDATE departments SET display_order=?, updated_at=datetime('now') WHERE id=?", (idx * 10, row["id"]))
    conn.commit()

    rows = conn.execute(
        f"""
        SELECT id, COALESCE(display_order, 0) AS display_order
        FROM departments
        WHERE COALESCE(parent_department_id, 0) = ?
        {where}
        ORDER BY is_active DESC, COALESCE(display_order, 0) ASC, id ASC
        """,
        (int(selected["parent_department_id"] or 0),),
    ).fetchall()
    ids = [int(row["id"]) for row in rows]
    try:
        idx = ids.index(int(row_id))
    except ValueError:
        return False
    target_idx = idx - 1 if direction == "up" else idx + 1
    if target_idx < 0 or target_idx >= len(rows):
        return False

    current = rows[idx]
    target = rows[target_idx]
    conn.execute("UPDATE departments SET display_order=?, updated_at=datetime('now') WHERE id=?", (target["display_order"], current["id"]))
    conn.execute("UPDATE departments SET display_order=?, updated_at=datetime('now') WHERE id=?", (current["display_order"], target["id"]))
    conn.commit()
    return True

def upsert_department(conn, name: str, department_type: str = "department", parent_department_id=None,
                      is_active: int = 1, memo=None, row_id=None):
    department_type = department_type if department_type in DEPARTMENT_TYPE_LABELS else "department"
    parent_id = int(parent_department_id) if parent_department_id else None
    if row_id is not None:
        row_id = int(row_id)
        if parent_id == row_id or (parent_id and parent_id in get_department_descendant_ids(conn, row_id)):
            raise ValueError("親所属に自分自身または配下の所属は選択できません。")

    if row_id is None:
        display_order = get_next_display_order(conn, "departments")
        conn.execute(
            """
            INSERT INTO departments(name, department_type, parent_department_id, display_order, is_active, memo)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, department_type, parent_id, display_order, is_active, memo),
        )
    else:
        current = conn.execute("SELECT display_order FROM departments WHERE id=?", (row_id,)).fetchone()
        display_order = int(row_get(current, "display_order", 0) or 0)
        conn.execute(
            """
            UPDATE departments
            SET name=?, department_type=?, parent_department_id=?, display_order=?, is_active=?, memo=?, updated_at=datetime('now')
            WHERE id=?
            """,
            (name, department_type, parent_id, display_order, is_active, memo, row_id),
        )
    conn.commit()

def get_department_full_name(conn, department_id) -> str:
    if not department_id:
        return ""
    names = {}
    parents = {}
    for item in list_department_hierarchy(conn, include_inactive=True):
        names[item["id"]] = item["name"]
        parents[item["id"]] = item["parent_id"]
    current = int(department_id)
    parts = []
    visited = set()
    while current and current not in visited:
        visited.add(current)
        name = names.get(current)
        if name:
            parts.append(name)
        current = parents.get(current, 0)
    return " > ".join(reversed(parts))

def get_named_master_by_id(conn, table: str, row_id: int):
    if table not in {"departments", "positions", "employment_types"}:
        raise ValueError("invalid master table")
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
    return cur.fetchone()

def upsert_named_master(conn, table: str, name: str, display_order: int = 0, is_active: int = 1, memo=None, row_id=None):
    if table not in {"departments", "positions", "employment_types"}:
        raise ValueError("invalid master table")
    if row_id is None:
        if display_order is None:
            display_order = get_next_display_order(conn, table)
        conn.execute(
            f"""
            INSERT INTO {table}(name, display_order, is_active, memo)
            VALUES (?, ?, ?, ?)
            """,
            (name, display_order, is_active, memo),
        )
    else:
        if display_order is None:
            current = conn.execute(f"SELECT display_order FROM {table} WHERE id=?", (row_id,)).fetchone()
            display_order = int(row_get(current, "display_order", 0) or 0)
        conn.execute(
            f"""
            UPDATE {table}
            SET name=?, display_order=?, is_active=?, memo=?, updated_at=datetime('now')
            WHERE id=?
            """,
            (name, display_order, is_active, memo, row_id),
        )
    conn.commit()

def _validate_display_order_table(table: str) -> None:
    if table not in {"departments", "positions", "employment_types", "payroll_item_categories", "payroll_items", "payroll_item_assignments"}:
        raise ValueError("invalid display_order table")

def get_next_display_order(conn, table: str) -> int:
    _validate_display_order_table(table)
    row = conn.execute(f"SELECT COALESCE(MAX(display_order), 0) AS max_order FROM {table}").fetchone()
    return int(row_get(row, "max_order", 0) or 0) + 10

def remove_departments_name_unique_constraint(conn) -> None:
    indexes = conn.execute("PRAGMA index_list(departments)").fetchall()
    has_name_unique = False
    for idx in indexes:
        if not int(row_get(idx, "unique", 0) or 0):
            continue
        index_name = row_get(idx, "name", "")
        cols = conn.execute(f"PRAGMA index_info({index_name})").fetchall()
        if [row_get(col, "name", "") for col in cols] == ["name"]:
            has_name_unique = True
            break
    if not has_name_unique:
        return

    conn.execute("ALTER TABLE departments RENAME TO departments_old")
    conn.execute(
        """
        CREATE TABLE departments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          parent_department_id INTEGER,
          department_type TEXT NOT NULL DEFAULT 'department',
          display_order INTEGER NOT NULL DEFAULT 0,
          is_active INTEGER NOT NULL DEFAULT 1,
          memo TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        INSERT INTO departments(
          id, name, parent_department_id, department_type, display_order,
          is_active, memo, created_at, updated_at
        )
        SELECT
          id, name, parent_department_id, COALESCE(department_type, 'department'),
          COALESCE(display_order, 0), COALESCE(is_active, 1), memo,
          COALESCE(created_at, datetime('now')), COALESCE(updated_at, datetime('now'))
        FROM departments_old
        """
    )
    conn.execute("DROP TABLE departments_old")
    conn.commit()

def _display_order_rows(conn, table: str, include_inactive: bool = True):
    _validate_display_order_table(table)
    where = "" if include_inactive else "WHERE is_active = 1"
    return conn.execute(
        f"""
        SELECT id, COALESCE(display_order, 0) AS display_order
        FROM {table}
        {where}
        ORDER BY is_active DESC, COALESCE(display_order, 0) ASC, id ASC
        """
    ).fetchall()

def normalize_display_order(conn, table: str, include_inactive: bool = True) -> None:
    rows = _display_order_rows(conn, table, include_inactive)
    for idx, row in enumerate(rows, start=1):
        conn.execute(f"UPDATE {table} SET display_order=?, updated_at=datetime('now') WHERE id=?", (idx * 10, row["id"]))
    conn.commit()

def move_display_order(conn, table: str, row_id: int, direction: str, include_inactive: bool = True) -> bool:
    if direction not in {"up", "down"}:
        raise ValueError("direction must be up or down")
    normalize_display_order(conn, table, include_inactive)
    rows = _display_order_rows(conn, table, include_inactive)
    ids = [int(row["id"]) for row in rows]
    try:
        idx = ids.index(int(row_id))
    except ValueError:
        return False

    target_idx = idx - 1 if direction == "up" else idx + 1
    if target_idx < 0 or target_idx >= len(rows):
        return False

    current = rows[idx]
    target = rows[target_idx]
    conn.execute(f"UPDATE {table} SET display_order=?, updated_at=datetime('now') WHERE id=?", (target["display_order"], current["id"]))
    conn.execute(f"UPDATE {table} SET display_order=?, updated_at=datetime('now') WHERE id=?", (current["display_order"], target["id"]))
    conn.commit()
    return True

def soft_delete_named_master(conn, table: str, row_id: int) -> bool:
    if table not in {"departments", "positions", "employment_types"}:
        raise ValueError("invalid master table")
    cur = conn.cursor()
    cur.execute(
        f"UPDATE {table} SET is_active=0, updated_at=datetime('now') WHERE id=? AND is_active=1",
        (row_id,),
    )
    conn.commit()
    return cur.rowcount > 0

def set_named_master_active(conn, table: str, row_id: int, is_active: int) -> bool:
    if table not in {"departments", "positions", "employment_types"}:
        raise ValueError("invalid master table")
    cur = conn.cursor()
    cur.execute(
        f"UPDATE {table} SET is_active=?, updated_at=datetime('now') WHERE id=?",
        (int(is_active or 0), row_id),
    )
    conn.commit()
    return cur.rowcount > 0

def list_payroll_item_categories(conn, include_inactive: bool = False):
    where = "" if include_inactive else "WHERE is_active = 1"
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT *
        FROM payroll_item_categories
        {where}
        ORDER BY is_active DESC, display_order ASC, id ASC
        """
    )
    return cur.fetchall()

def _generate_unique_code(conn, table: str, prefix: str) -> str:
    if table not in {"payroll_item_categories", "payroll_items"}:
        raise ValueError("invalid code generation target")

    rows = conn.execute(f"SELECT id, code FROM {table}").fetchall()
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)$")
    max_number = 0
    existing = set()
    for row in rows:
        code = (row_get(row, "code", "") or "").strip()
        if code:
            existing.add(code)
        match = pattern.match(code)
        if match:
            max_number = max(max_number, int(match.group(1)))
        max_number = max(max_number, int(row_get(row, "id", 0) or 0))

    number = max_number + 1
    while True:
        code = f"{prefix}_{number:06d}"
        if code not in existing:
            return code
        number += 1

def ensure_payroll_item_codes(conn) -> None:
    for table, prefix in (("payroll_item_categories", "CAT"), ("payroll_items", "ITEM")):
        rows = conn.execute(
            f"SELECT id FROM {table} WHERE code IS NULL OR TRIM(code) = '' ORDER BY id"
        ).fetchall()
        for row in rows:
            code = _generate_unique_code(conn, table, prefix)
            conn.execute(f"UPDATE {table} SET code=?, updated_at=datetime('now') WHERE id=?", (code, row["id"]))
    conn.commit()

def upsert_payroll_item_category(conn, code=None, name="", item_kind="pay", display_order=0, is_active=1, memo=None, row_id=None):
    if row_id is None:
        if display_order is None:
            display_order = get_next_display_order(conn, "payroll_item_categories")
        code = (code or "").strip() or _generate_unique_code(conn, "payroll_item_categories", "CAT")
        conn.execute(
            """
            INSERT INTO payroll_item_categories(code, name, item_kind, display_order, is_active, memo)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (code, name, item_kind, display_order, is_active, memo),
        )
    else:
        if display_order is None:
            current = conn.execute("SELECT display_order FROM payroll_item_categories WHERE id=?", (row_id,)).fetchone()
            display_order = int(row_get(current, "display_order", 0) or 0)
        conn.execute(
            """
            UPDATE payroll_item_categories
            SET name=?, item_kind=?, display_order=?, is_active=?, memo=?, updated_at=datetime('now')
            WHERE id=?
            """,
            (name, item_kind, display_order, is_active, memo, row_id),
        )
    conn.commit()

def soft_delete_payroll_item_category(conn, row_id: int) -> bool:
    cur = conn.cursor()
    cur.execute("UPDATE payroll_item_categories SET is_active=0, updated_at=datetime('now') WHERE id=? AND is_active=1", (row_id,))
    conn.commit()
    return cur.rowcount > 0

def set_payroll_item_category_active(conn, row_id: int, is_active: int) -> bool:
    cur = conn.cursor()
    cur.execute(
        "UPDATE payroll_item_categories SET is_active=?, updated_at=datetime('now') WHERE id=?",
        (int(is_active or 0), row_id),
    )
    conn.commit()
    return cur.rowcount > 0

def list_payroll_items(conn, include_inactive: bool = False):
    where = "" if include_inactive else "WHERE pi.is_active = 1"
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT pi.*, c.name AS category_name, c.code AS category_code,
               COALESCE(c.display_order, 999999) AS category_display_order
        FROM payroll_items pi
        LEFT JOIN payroll_item_categories c ON c.id = pi.category_id
        {where}
        ORDER BY pi.is_active DESC,
                 CASE pi.item_kind
                   WHEN 'pay' THEN 1
                   WHEN 'deduction' THEN 2
                   WHEN 'system_deduction' THEN 3
                   ELSE 9
                 END,
                 COALESCE(c.display_order, 999999) ASC,
                 pi.display_order ASC,
                 pi.id ASC
        """
    )
    return cur.fetchall()

def upsert_payroll_item(conn, code=None, name="", item_kind="pay", category_id=None, is_system=0, is_active=1,
                        is_taxable=0, is_social_insurance_base=0, is_employment_insurance_base=0,
                        is_commute=0, display_order=0, memo=None, row_id=None):
    if row_id is None:
        if display_order is None:
            display_order = get_next_display_order(conn, "payroll_items")
        code = (code or "").strip() or _generate_unique_code(conn, "payroll_items", "ITEM")
        conn.execute(
            """
            INSERT INTO payroll_items(
              code, name, item_kind, category_id, is_system, is_active, is_taxable,
              is_social_insurance_base, is_employment_insurance_base, is_commute,
              display_order, memo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (code, name, item_kind, category_id, is_system, is_active, is_taxable,
             is_social_insurance_base, is_employment_insurance_base, is_commute, display_order, memo),
        )
    else:
        if display_order is None:
            current = conn.execute("SELECT display_order FROM payroll_items WHERE id=?", (row_id,)).fetchone()
            display_order = int(row_get(current, "display_order", 0) or 0)
        conn.execute(
            """
            UPDATE payroll_items
            SET name=?, item_kind=?, category_id=?, is_system=?, is_active=?, is_taxable=?,
                is_social_insurance_base=?, is_employment_insurance_base=?, is_commute=?,
                display_order=?, memo=?, updated_at=datetime('now')
            WHERE id=?
            """,
            (name, item_kind, category_id, is_system, is_active, is_taxable,
             is_social_insurance_base, is_employment_insurance_base, is_commute, display_order, memo, row_id),
        )
    conn.commit()

def soft_delete_payroll_item(conn, row_id: int) -> bool:
    cur = conn.cursor()
    cur.execute("UPDATE payroll_items SET is_active=0, updated_at=datetime('now') WHERE id=? AND is_active=1", (row_id,))
    conn.commit()
    return cur.rowcount > 0

def set_payroll_item_active(conn, row_id: int, is_active: int) -> bool:
    cur = conn.cursor()
    cur.execute(
        "UPDATE payroll_items SET is_active=?, updated_at=datetime('now') WHERE id=?",
        (int(is_active or 0), row_id),
    )
    conn.commit()
    return cur.rowcount > 0

def upsert_employee_payroll_item_standard_value(conn, employee_id: int, item_id: int, start_month: str,
                                                amount: int, is_active: int = 1, memo=None):
    conn.execute(
        """
        INSERT INTO employee_payroll_item_standard_values(
          employee_id, item_id, start_month, amount, is_active, memo
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(employee_id, item_id, start_month) DO UPDATE SET
          amount=excluded.amount,
          is_active=excluded.is_active,
          memo=excluded.memo,
          updated_at=datetime('now')
        """,
        (employee_id, item_id, start_month, amount, is_active, memo),
    )
    conn.commit()

def list_employee_payroll_item_standard_values(conn, employee_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT v.*, i.code AS item_code, i.name AS item_name, i.item_kind
        FROM employee_payroll_item_standard_values v
        JOIN payroll_items i ON i.id = v.item_id
        WHERE v.employee_id = ?
        ORDER BY v.is_active DESC, v.start_month DESC, i.display_order ASC
        """,
        (employee_id,),
    )
    return cur.fetchall()

def delete_employee_payroll_item_standard_value(conn, row_id: int) -> bool:
    cur = conn.cursor()
    cur.execute("DELETE FROM employee_payroll_item_standard_values WHERE id = ?", (row_id,))
    conn.commit()
    return cur.rowcount > 0

def set_employee_payroll_item_standard_value_active(conn, row_id: int, is_active: int) -> bool:
    cur = conn.cursor()
    cur.execute(
        "UPDATE employee_payroll_item_standard_values SET is_active=?, updated_at=datetime('now') WHERE id=?",
        (int(is_active or 0), row_id),
    )
    conn.commit()
    return cur.rowcount > 0

def upsert_payroll_monthly_item_value(conn, monthly_id: int, employee_id: int, year: int, month: int,
                                      item_id: int, item_kind: str, amount: int, source: str = "manual",
                                      is_locked: int = 0, memo=None, commit: bool = True):
    row = conn.execute(
        """
        SELECT is_locked
        FROM payroll_monthly_item_values
        WHERE monthly_id = ? AND item_id = ?
        """,
        (monthly_id, item_id),
    ).fetchone()
    if row and int(row["is_locked"] or 0):
        return False
    conn.execute(
        """
        INSERT INTO payroll_monthly_item_values(
          monthly_id, employee_id, year, month, item_id, item_kind, amount, source, is_locked, memo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(monthly_id, item_id) DO UPDATE SET
          amount=excluded.amount,
          source=excluded.source,
          is_locked=excluded.is_locked,
          memo=excluded.memo,
          updated_at=datetime('now')
        """,
        (monthly_id, employee_id, year, month, item_id, item_kind, amount, source, is_locked, memo),
    )
    if commit:
        conn.commit()
    return True

def list_payroll_monthly_item_values(conn, monthly_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT v.*, i.code AS item_code, i.name AS item_name, i.display_order
        FROM payroll_monthly_item_values v
        JOIN payroll_items i ON i.id = v.item_id
        WHERE v.monthly_id = ?
        ORDER BY i.display_order ASC, v.id ASC
        """,
        (monthly_id,),
    )
    return cur.fetchall()

def _employee_context(conn, employee_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT employee_id, department_id, position_id, employment_type_id
        FROM employees
        WHERE employee_id = ?
        """,
        (employee_id,),
    )
    return cur.fetchone()

def get_applicable_payroll_items(conn, employee_id: int, include_system: bool = False):
    """
    Return active payroll items applicable to an employee.
    System deductions are excluded by default so existing automatic calculation remains authoritative.
    """
    emp = _employee_context(conn, employee_id)
    if not emp:
        return []

    item_filter = "" if include_system else "AND item_kind != 'system_deduction'"
    items = conn.execute(
        f"""
        SELECT *
        FROM payroll_items
        WHERE is_active = 1
          {item_filter}
        ORDER BY display_order ASC, id ASC
        """
    ).fetchall()
    assignments = conn.execute(
        """
        SELECT *
        FROM payroll_item_assignments
        WHERE is_active = 1
        ORDER BY display_order ASC, id ASC
        """
    ).fetchall()

    def matches(a):
        tt = a["target_type"]
        if tt == "all":
            return True
        if tt == "employee":
            return a["employee_id"] == employee_id
        if tt == "department":
            return emp["department_id"] and a["department_id"] == emp["department_id"]
        if tt == "position":
            return emp["position_id"] and a["position_id"] == emp["position_id"]
        if tt == "employment_type":
            return emp["employment_type_id"] and a["employment_type_id"] == emp["employment_type_id"]
        if tt == "department_position":
            return (
                emp["department_id"]
                and emp["position_id"]
                and a["department_id"] == emp["department_id"]
                and a["position_id"] == emp["position_id"]
            )
        return False

    result = []
    for item in items:
        all_item_assignments = [a for a in assignments if a["item_id"] == item["id"]]
        item_assignments = [a for a in all_item_assignments if matches(a)]
        if not all_item_assignments:
            result.append(item)
            continue
        employee_exclude = any(a["target_type"] == "employee" and a["action"] == "exclude" for a in item_assignments)
        if employee_exclude:
            continue
        employee_include = any(a["target_type"] == "employee" and a["action"] == "include" for a in item_assignments)
        group_include = any(a["target_type"] in {"department", "position", "employment_type", "department_position"} and a["action"] == "include" for a in item_assignments)
        all_include = any(a["target_type"] == "all" and a["action"] == "include" for a in item_assignments)
        group_exclude = any(a["target_type"] in {"department", "position", "employment_type", "department_position"} and a["action"] == "exclude" for a in item_assignments)
        if employee_include or (group_include and not group_exclude) or (all_include and not group_exclude):
            result.append(item)
    return result

def get_employee_standard_amount(conn, employee_id: int, item_id: int, target_month: str) -> int:
    row = conn.execute(
        """
        SELECT amount
        FROM employee_payroll_item_standard_values
        WHERE employee_id = ?
          AND item_id = ?
          AND is_active = 1
          AND start_month <= ?
        ORDER BY start_month DESC, id DESC
        LIMIT 1
        """,
        (employee_id, item_id, target_month),
    ).fetchone()
    return int(row["amount"] or 0) if row else 0

def get_payroll_monthly_item_value_map(conn, monthly_id: int):
    rows = list_payroll_monthly_item_values(conn, monthly_id)
    return {int(r["item_id"]): r for r in rows}

def _empty_dynamic_payroll_totals() -> dict:
    return {
        "has_dynamic_items": False,
        "total_pay": 0,
        "taxable_pay": 0,
        "social_insurance_base": 0,
        "employment_insurance_base": 0,
        "commute_pay": 0,
        "non_taxable_pay": 0,
        "total_custom_deduction": 0,
        "item_details": [],
    }

def calculate_dynamic_payroll_item_totals(
    conn,
    monthly_id: int,
    employee_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
) -> dict:
    """
    Aggregate monthly detail rows for the phased dynamic payroll-item migration.

    System deductions are intentionally excluded from total_custom_deduction so
    existing social insurance, employment insurance, withholding tax, and
    resident tax handling stays authoritative.
    """
    totals = _empty_dynamic_payroll_totals()
    params = [monthly_id]
    where = ["v.monthly_id = ?"]
    if employee_id is not None:
        where.append("v.employee_id = ?")
        params.append(employee_id)
    if year is not None:
        where.append("v.year = ?")
        params.append(year)
    if month is not None:
        where.append("v.month = ?")
        params.append(month)

    rows = conn.execute(
        f"""
        SELECT
          v.id AS value_id,
          v.monthly_id,
          v.employee_id,
          v.year,
          v.month,
          v.item_id,
          COALESCE(v.item_kind, i.item_kind) AS effective_item_kind,
          v.amount,
          v.source,
          v.is_locked,
          i.code AS item_code,
          i.name AS item_name,
          i.item_kind AS master_item_kind,
          i.is_active,
          i.is_taxable,
          i.is_social_insurance_base,
          i.is_employment_insurance_base,
          i.is_commute,
          i.display_order
        FROM payroll_monthly_item_values v
        LEFT JOIN payroll_items i ON i.id = v.item_id
        WHERE {" AND ".join(where)}
        ORDER BY COALESCE(i.display_order, 999999), v.id
        """,
        tuple(params),
    ).fetchall()

    totals["has_dynamic_items"] = bool(rows)
    for row in rows:
        amount = int(row_get(row, "amount", 0) or 0)
        item_kind = row_get(row, "effective_item_kind", "") or ""
        detail = {
            "value_id": row_get(row, "value_id"),
            "item_id": row_get(row, "item_id"),
            "code": row_get(row, "item_code"),
            "name": row_get(row, "item_name"),
            "item_kind": item_kind,
            "amount": amount,
            "display_order": int(row_get(row, "display_order", 0) or 0),
            "source": row_get(row, "source"),
            "is_locked": int(row_get(row, "is_locked", 0) or 0),
        }
        totals["item_details"].append(detail)

        if item_kind == "pay":
            totals["total_pay"] += amount
            if int(row_get(row, "is_taxable", 0) or 0):
                totals["taxable_pay"] += amount
            else:
                totals["non_taxable_pay"] += amount
            if int(row_get(row, "is_social_insurance_base", 0) or 0):
                totals["social_insurance_base"] += amount
            if int(row_get(row, "is_employment_insurance_base", 0) or 0):
                totals["employment_insurance_base"] += amount
            if int(row_get(row, "is_commute", 0) or 0):
                totals["commute_pay"] += amount
        elif item_kind == "deduction":
            totals["total_custom_deduction"] += amount

    return totals

def has_dynamic_item_values(
    conn,
    monthly_id: int,
    employee_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
) -> bool:
    where = ["monthly_id = ?"]
    params = [monthly_id]
    if employee_id is not None:
        where.append("employee_id = ?")
        params.append(employee_id)
    if year is not None:
        where.append("year = ?")
        params.append(year)
    if month is not None:
        where.append("month = ?")
        params.append(month)
    row = conn.execute(
        f"SELECT 1 FROM payroll_monthly_item_values WHERE {' AND '.join(where)} LIMIT 1",
        tuple(params),
    ).fetchone()
    return row is not None

def has_dynamic_payroll_items(conn, monthly_id: int) -> bool:
    return has_dynamic_item_values(conn, monthly_id)

def get_dynamic_totals_for_payroll_row(conn, r) -> dict:
    target_month = row_get(r, "target_month", "") or ""
    year = month = None
    if len(target_month) == 7 and "-" in target_month:
        try:
            year, month = (int(x) for x in target_month.split("-", 1))
        except Exception:
            year = month = None
    return calculate_dynamic_payroll_item_totals(
        conn,
        int(row_get(r, "payroll_id", 0) or 0),
        int(row_get(r, "employee_id", 0) or 0) or None,
        year,
        month,
    )

def get_fixed_payroll_row_totals(r) -> dict:
    total_pay = (
        int(row_get(r, "officer_pay", 0) or 0)
        + int(row_get(r, "base_salary", 0) or 0)
        + int(row_get(r, "deemed_ot", 0) or 0)
        + int(row_get(r, "overtime_pay", 0) or 0)
        + int(row_get(r, "special_allow", 0) or 0)
        + int(row_get(r, "commute_nontax", 0) or 0)
    )
    taxable_pay = (
        int(row_get(r, "officer_pay", 0) or 0)
        + int(row_get(r, "base_salary", 0) or 0)
        + int(row_get(r, "deemed_ot", 0) or 0)
        + int(row_get(r, "overtime_pay", 0) or 0)
        + int(row_get(r, "special_allow", 0) or 0)
    )
    non_taxable_pay = int(row_get(r, "commute_nontax", 0) or 0)
    employment_insurance_base = taxable_pay
    social_insurance_base = total_pay
    total_custom_deduction = 0

    return {
        "has_dynamic_items": False,
        "total_pay": max(0, total_pay),
        "taxable_pay": max(0, taxable_pay),
        "social_insurance_base": max(0, social_insurance_base),
        "employment_insurance_base": max(0, employment_insurance_base),
        "commute_pay": int(row_get(r, "commute_nontax", 0) or 0),
        "non_taxable_pay": max(0, non_taxable_pay),
        "total_custom_deduction": max(0, total_custom_deduction),
        "item_details": [],
    }

def get_effective_payroll_row_totals(conn, r) -> dict:
    if USE_DYNAMIC_ITEMS_FOR_TOTALS:
        dynamic = get_dynamic_totals_for_payroll_row(conn, r)
        if dynamic["has_dynamic_items"]:
            return dynamic
    return get_fixed_payroll_row_totals(r)

def _system_deduction_total_from_row(r) -> int:
    health = int(row_get(r, "health_ins_employee", 0) or 0)
    care = int(row_get(r, "care_ins_employee", 0) or 0)
    childcare = int(row_get(r, "childcare_support_employee", 0) or 0)
    pension = int(row_get(r, "pension_ins_employee", 0) or 0)
    emp = int(row_get(r, "emp_ins_employee", 0) or 0)
    withholding = int(row_get(r, "withholding_tax_applied", 0) or 0)
    resident = int(row_get(r, "resident_tax_applied", 0) or 0)
    return max(0, health + care + childcare + pension + emp + withholding + resident)

def build_payroll_calculation_basis(conn, r) -> dict:
    """
    Unified payroll calculation basis.

    Dynamic item rows take over pay/custom-deduction totals when at least one
    row exists, even when every amount is zero. System deductions continue to
    use the existing saved values.
    """
    dynamic = get_dynamic_totals_for_payroll_row(conn, r)
    fixed = get_fixed_payroll_row_totals(r)
    use_dynamic = bool(dynamic["has_dynamic_items"] and USE_DYNAMIC_ITEMS_FOR_TOTALS)
    source = dynamic if use_dynamic else fixed

    system_deduction_total = _system_deduction_total_from_row(r)
    total_pay = int(source["total_pay"] or 0)
    custom_deduction_total = int(source["total_custom_deduction"] or 0)
    total_deduction = system_deduction_total + custom_deduction_total
    net_pay = total_pay - total_deduction

    return {
        "use_dynamic_items": use_dynamic,
        "total_pay": total_pay,
        "taxable_pay": int(source["taxable_pay"] or 0),
        "non_taxable_pay": int(source["non_taxable_pay"] or 0),
        "commute_pay": int(source["commute_pay"] or 0),
        "employment_insurance_base": int(source["employment_insurance_base"] or 0),
        "social_insurance_base": int(source["social_insurance_base"] or 0),
        "custom_deduction_total": custom_deduction_total,
        "system_deduction_total": system_deduction_total,
        "health_insurance": int(row_get(r, "health_ins_employee", 0) or 0),
        "nursing_care_insurance": int(row_get(r, "care_ins_employee", 0) or 0),
        "pension_insurance": int(row_get(r, "pension_ins_employee", 0) or 0),
        "child_care_contribution": int(row_get(r, "childcare_support_employee", 0) or 0),
        "employment_insurance": int(row_get(r, "emp_ins_employee", 0) or 0),
        "income_tax": int(row_get(r, "withholding_tax_applied", 0) or 0),
        "resident_tax": int(row_get(r, "resident_tax_applied", 0) or 0),
        "total_deduction": total_deduction,
        "net_pay": net_pay,
        "item_details": source.get("item_details", []),
    }

def _row_with_calculation_basis(conn, r) -> dict:
    row = _row_with_current_department_name(conn, r)
    basis = build_payroll_calculation_basis(conn, r)
    row["use_dynamic_items"] = 1 if basis["use_dynamic_items"] else 0
    row["dynamic_social_insurance_base"] = basis["social_insurance_base"]
    row["total_pay_input"] = basis["total_pay"]
    row["total_deduct_input"] = basis["custom_deduction_total"]
    row["net_pay_input"] = basis["total_pay"] - basis["custom_deduction_total"]
    row["taxable_pay"] = basis["taxable_pay"]
    row["non_taxable_pay"] = basis["non_taxable_pay"]
    row["employment_insurance_base_calc"] = basis["employment_insurance_base"]
    row["system_deduction_total"] = basis["system_deduction_total"]
    row["total_deduction_calc"] = basis["total_deduction"]
    row["net_pay_calc"] = basis["net_pay"]
    return row

def _aggregate_payroll_basis_rows(rows, conn):
    grouped = {}
    for r in rows:
        key = (r["target_month"], r["pay_date_applied"])
        b = build_payroll_calculation_basis(conn, r)
        if key not in grouped:
            grouped[key] = {
                "target_month": r["target_month"],
                "pay_date_applied": r["pay_date_applied"],
                "employee_count": 0,
                "taxable_pay_sum": 0,
                "non_taxable_pay_sum": 0,
                "gross_pay_sum": 0,
                "social_ins_sum": 0,
                "withholding_tax_sum": 0,
                "resident_tax_sum": 0,
                "other_deduct_sum": 0,
                "total_deduct_sum": 0,
                "net_pay_sum": 0,
                "dynamic_employee_count": 0,
            }
        g = grouped[key]
        g["employee_count"] += 1
        g["taxable_pay_sum"] += b["taxable_pay"]
        g["non_taxable_pay_sum"] += b["non_taxable_pay"]
        g["gross_pay_sum"] += b["total_pay"]
        g["social_ins_sum"] += int(row_get(r, "social_ins_total_calc", 0) or 0)
        g["withholding_tax_sum"] += b["income_tax"]
        g["resident_tax_sum"] += b["resident_tax"]
        g["other_deduct_sum"] += b["custom_deduction_total"]
        g["total_deduct_sum"] += b["total_deduction"]
        g["net_pay_sum"] += b["net_pay"]
        if b["use_dynamic_items"]:
            g["dynamic_employee_count"] += 1
    return [grouped[k] for k in sorted(grouped.keys(), key=lambda x: (x[1] or "", x[0] or ""))]

def _system_deduction_items_for_output(r) -> list[dict]:
    return [
        {"code": "health_ins_employee", "name": "健康保険料", "amount": int(row_get(r, "health_ins_employee", 0) or 0), "display_order": 10},
        {"code": "care_ins_employee", "name": "介護保険料", "amount": int(row_get(r, "care_ins_employee", 0) or 0), "display_order": 20},
        {"code": "childcare_support_employee", "name": "子ども・子育て支援金", "amount": int(row_get(r, "childcare_support_employee", 0) or 0), "display_order": 30},
        {"code": "pension_ins_employee", "name": "厚生年金保険料", "amount": int(row_get(r, "pension_ins_employee", 0) or 0), "display_order": 40},
        {"code": "emp_ins_employee", "name": "雇用保険料", "amount": int(row_get(r, "emp_ins_employee", 0) or 0), "display_order": 50},
        {"code": "withholding_tax_applied", "name": "源泉所得税", "amount": int(row_get(r, "withholding_tax_applied", 0) or 0), "display_order": 60},
        {"code": "resident_tax_applied", "name": "住民税", "amount": int(row_get(r, "resident_tax_applied", 0) or 0), "display_order": 70},
    ]

def _fixed_pay_items_for_output(r) -> list[dict]:
    items = [
        ("officer_pay", "役員報酬", 10),
        ("base_salary", "基本給", 20),
        ("deemed_ot", "みなし残業手当", 30),
        ("overtime_pay", "残業手当", 40),
        ("special_allow", "特別手当", 50),
        ("commute_nontax", "非課税通勤手当", 60),
    ]
    out = [
        {"code": code, "name": name, "amount": int(row_get(r, code, 0) or 0), "display_order": order}
        for code, name, order in items
    ]
    return out

def _fixed_deduction_items_for_output(r) -> list[dict]:
    return []

def _payroll_output_source_row(conn, payroll_id: int):
    row = conn.execute(
        """
        SELECT
          p.*,
          e.employee_code,
          e.name_kanji,
          e.department,
          e.department_id,
          e.position_id,
          e.employment_type_id,
          COALESCE(d.name, e.department, '') AS department_name,
          COALESCE(pos.name, '') AS position_name,
          COALESCE(et.name, '') AS employment_type_name
        FROM payroll_monthly p
        JOIN employees e ON e.employee_id = p.employee_id
        LEFT JOIN departments d ON d.id = e.department_id
        LEFT JOIN positions pos ON pos.id = e.position_id
        LEFT JOIN employment_types et ON et.id = e.employment_type_id
        WHERE p.payroll_id = ?
        """,
        (payroll_id,),
    ).fetchone()
    return _row_with_current_department_name(conn, row) if row else None

def build_payroll_output_data(conn, payroll_or_row) -> dict:
    payroll_id = int(row_get(payroll_or_row, "payroll_id", payroll_or_row) or 0)
    r = _payroll_output_source_row(conn, payroll_id)
    if not r:
        raise ValueError("対象の給与データが見つかりません。")

    basis = build_payroll_calculation_basis(conn, r)
    if basis["use_dynamic_items"]:
        pay_items = [
            {
                "item_id": d.get("item_id"),
                "code": d.get("code"),
                "name": d.get("name") or "",
                "amount": int(d.get("amount") or 0),
                "display_order": int(d.get("display_order") or 0),
            }
            for d in basis["item_details"]
            if d.get("item_kind") == "pay"
        ]
        deduction_items = [
            {
                "item_id": d.get("item_id"),
                "code": d.get("code"),
                "name": d.get("name") or "",
                "amount": int(d.get("amount") or 0),
                "display_order": int(d.get("display_order") or 0),
            }
            for d in basis["item_details"]
            if d.get("item_kind") == "deduction"
        ]
    else:
        pay_items = _fixed_pay_items_for_output(r)
        deduction_items = _fixed_deduction_items_for_output(r)

    pay_items.sort(key=lambda x: (int(x.get("display_order") or 0), str(x.get("name") or "")))
    deduction_items.sort(key=lambda x: (int(x.get("display_order") or 0), str(x.get("name") or "")))
    system_deductions = _system_deduction_items_for_output(r)

    target_month = row_get(r, "target_month", "") or ""
    year = month = None
    if len(target_month) == 7 and "-" in target_month:
        try:
            year, month = (int(x) for x in target_month.split("-", 1))
        except Exception:
            pass

    return {
        "payroll_id": payroll_id,
        "employee_id": int(row_get(r, "employee_id", 0) or 0),
        "employee_code": row_get(r, "employee_code", "") or "",
        "employee_name": row_get(r, "name_kanji", "") or "",
        "department_name": row_get(r, "department", "") or "",
        "position_name": row_get(r, "position_name", "") or "",
        "employment_type_name": row_get(r, "employment_type_name", "") or "",
        "target_month": target_month,
        "year": year,
        "month": month,
        "pay_date": row_get(r, "pay_date_applied", "") or "",
        "use_dynamic_items": basis["use_dynamic_items"],
        "pay_items": pay_items,
        "deduction_items": deduction_items,
        "system_deductions": system_deductions,
        "total_pay": basis["total_pay"],
        "taxable_pay": basis["taxable_pay"],
        "non_taxable_pay": basis["non_taxable_pay"],
        "employment_insurance_base": basis["employment_insurance_base"],
        "social_insurance_base": basis["social_insurance_base"],
        "custom_deduction_total": basis["custom_deduction_total"],
        "system_deduction_total": basis["system_deduction_total"],
        "health_insurance": basis["health_insurance"],
        "nursing_care_insurance": basis["nursing_care_insurance"],
        "child_care_contribution": basis["child_care_contribution"],
        "pension_insurance": basis["pension_insurance"],
        "employment_insurance": basis["employment_insurance"],
        "income_tax": basis["income_tax"],
        "resident_tax": basis["resident_tax"],
        "total_deduction": basis["total_deduction"],
        "net_pay": basis["net_pay"],
        "note": row_get(r, "note", "") or "",
    }

def get_payroll_output_data_for_month(conn, target_month: str) -> list[dict]:
    rows = get_payroll_rows(conn, target_month)
    return [build_payroll_output_data(conn, r) for r in rows]

def _normalize_employee_csv_date(value: str | None) -> str | None:
    s = (value or "").strip()
    if not s:
        return None
    parts = s.replace("/", "-").split("-")
    if len(parts) != 3 or not all(p.strip().isdigit() for p in parts):
        raise ValueError(f"日付形式が不正です: {value}")
    y, m, d = (int(p) for p in parts)
    return f"{y:04d}-{m:02d}-{d:02d}"

def _employee_csv_cell(row: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        if key in row and row[key] is not None:
            return str(row[key]).strip()
    return default

def _employee_csv_bool(value: str | None) -> int:
    s = (value or "").strip().lower()
    if s in {"1", "true", "yes", "y", "on", "済", "済み", "はい", "退職済み"}:
        return 1
    return 0

def resolve_employee_payment_schedule_id(conn, row: dict) -> int | None:
    raw_id = _employee_csv_cell(
        row,
        "payment_schedule_id",
        "給与支給方式ID",
        "schedule_id",
        default="",
    )
    if raw_id.isdigit():
        return int(raw_id)

    schedule_name = _employee_csv_cell(
        row,
        "payment_schedule",
        "payment_schedule_name",
        "給与支給方式",
        "給与支給方式名",
        default="",
    )
    schedules = list_payment_schedules(conn)
    if schedule_name:
        for sched in schedules:
            if sched["schedule_name"] == schedule_name:
                return int(sched["payment_schedule_id"])

    payday = _employee_csv_cell(
        row,
        "payday_group",
        "payday",
        "支給日区分",
        "支給日",
        default="",
    )
    if payday.isdigit():
        for sched in schedules:
            if payday in str(sched["schedule_name"]):
                return int(sched["payment_schedule_id"])

    return None

def import_employees_from_csv_rows(conn, rows: list[dict]) -> int:
    imported = 0
    for row in rows:
        employee_code = _employee_csv_cell(row, "employee_code", "社員番号", "code")
        name_kanji = _employee_csv_cell(row, "name_kanji", "氏名", "name")
        name_kana = _employee_csv_cell(row, "name_kana", "フリガナ")
        if not employee_code or not name_kanji:
            continue

        payment_schedule_id = resolve_employee_payment_schedule_id(conn, row)
        if not payment_schedule_id:
            raise ValueError(f"給与支給方式を解決できませんでした: 社員番号 {employee_code}")

        department = _employee_csv_cell(row, "department", "部署")
        std_health = int(_employee_csv_cell(row, "std_monthly_wage", "標準報酬月額（健保）", default="0").replace(",", "") or 0)
        std_pension = int(_employee_csv_cell(row, "std_pension_wage", "標準報酬月額（厚年）", default="0").replace(",", "") or 0)
        social_target_default = "1" if (std_health > 0 or std_pension > 0) else "0"
        social_target = _employee_csv_bool(_employee_csv_cell(row, "is_social_insurance_target", "社会保険加入対象", default=social_target_default))
        employment_target = _employee_csv_bool(_employee_csv_cell(row, "is_employment_insurance_target", "雇用保険加入対象", default="1"))
        tax_type = _employee_csv_cell(row, "tax_type", "源泉区分", "源泉", default="甲") or "甲"
        dependents_count = int(_employee_csv_cell(row, "dependents_count", "扶養人数", "扶養", default="0").replace(",", "") or 0)
        work_prefecture_name = _employee_csv_cell(row, "work_prefecture_name", "勤務地都道府県", "都道府県")
        address_postal_code = _employee_csv_cell(row, "address_postal_code", "郵便番号")
        address_prefecture = _employee_csv_cell(row, "address_prefecture", "住所都道府県")
        address_city = _employee_csv_cell(row, "address_city", "市区町村")
        address_detail = _employee_csv_cell(row, "address_detail", "住所", "それ以降の住所")
        resident_tax_municipality = _employee_csv_cell(row, "resident_tax_municipality", "住民税市区町村")
        phone = _employee_csv_cell(row, "phone", "電話番号")
        email = _employee_csv_cell(row, "email", "メールアドレス")
        bank_name = _employee_csv_cell(row, "bank_name", "銀行名")
        bank_branch_name = _employee_csv_cell(row, "bank_branch_name", "支店名")
        bank_account_type = _employee_csv_cell(row, "bank_account_type", "口座種別")
        bank_account_number = _employee_csv_cell(row, "bank_account_number", "口座番号")
        bank_account_holder = _employee_csv_cell(row, "bank_account_holder", "口座名義")
        birth_date = _normalize_employee_csv_date(_employee_csv_cell(row, "birth_date", "生年月日"))
        hire_date = _normalize_employee_csv_date(_employee_csv_cell(row, "hire_date", "入社日"))
        leave_date = _normalize_employee_csv_date(_employee_csv_cell(row, "leave_date", "退職日"))
        retirement_processed = _employee_csv_bool(_employee_csv_cell(row, "retirement_processed", "退職処理済み"))
        memo = _employee_csv_cell(row, "memo", "メモ", default="") or None

        upsert_employee(
            conn,
            employee_code,
            name_kanji,
            department,
            0,
            std_health,
            std_pension,
            tax_type,
            dependents_count,
            work_prefecture_name=work_prefecture_name,
            address_postal_code=address_postal_code,
            address_prefecture=address_prefecture,
            address_city=address_city,
            address_detail=address_detail,
            resident_tax_municipality=resident_tax_municipality,
            birth_date=birth_date,
            payment_schedule_id=payment_schedule_id,
            hire_date=hire_date,
            leave_date=leave_date,
            retirement_processed=retirement_processed,
            memo=memo,
            name_kana=name_kana,
            phone=phone,
            email=email,
            bank_name=bank_name,
            bank_branch_name=bank_branch_name,
            bank_account_type=bank_account_type,
            bank_account_number=bank_account_number,
            bank_account_holder=bank_account_holder,
            is_social_insurance_target=social_target,
            is_employment_insurance_target=employment_target,
        )
        imported += 1
    return imported

def list_employee_export_rows(conn) -> list[dict]:
    rows = []
    for e in list_employees(conn):
        rows.append(
            {
                "社員番号": row_get(e, "employee_code", ""),
                "氏名": row_get(e, "name_kanji", ""),
                "フリガナ": row_get(e, "name_kana", "") or "",
                "部署": row_get(e, "department", ""),
                "給与支給方式": get_employee_payment_schedule_display(e, conn),
                "給与支給方式ID": row_get(e, "payment_schedule_id", "") or "",
                "支給日": row_get(e, "payday_group", "") or "",
                "標準報酬月額（健保）": row_get(e, "std_monthly_wage", 0) or 0,
                "標準報酬月額（厚年）": row_get(e, "std_pension_wage", 0) or 0,
                "社会保険加入対象": "1" if int(row_get(e, "is_social_insurance_target", 0) or 0) else "0",
                "雇用保険加入対象": "1" if int(row_get(e, "is_employment_insurance_target", 1) or 0) else "0",
                "生年月日": row_get(e, "birth_date", "") or "",
                "入社日": row_get(e, "hire_date", "") or "",
                "退職日": row_get(e, "leave_date", "") or "",
                "退職処理済み": "1" if int(row_get(e, "retirement_processed", 0) or 0) else "0",
                "源泉": row_get(e, "tax_type", "甲") or "甲",
                "扶養人数": row_get(e, "dependents_count", 0) or 0,
                "都道府県": row_get(e, "work_prefecture_name", "") or "",
                "郵便番号": row_get(e, "address_postal_code", "") or "",
                "住所都道府県": row_get(e, "address_prefecture", "") or "",
                "市区町村": row_get(e, "address_city", "") or "",
                "住所": row_get(e, "address_detail", "") or "",
                "住民税市区町村": row_get(e, "resident_tax_municipality", "") or "",
                "電話番号": row_get(e, "phone", "") or "",
                "メールアドレス": row_get(e, "email", "") or "",
                "銀行名": row_get(e, "bank_name", "") or "",
                "支店名": row_get(e, "bank_branch_name", "") or "",
                "口座種別": row_get(e, "bank_account_type", "") or "",
                "口座番号": row_get(e, "bank_account_number", "") or "",
                "口座名義": row_get(e, "bank_account_holder", "") or "",
                "メモ": row_get(e, "memo", "") or "",
            }
        )
    return rows

def ensure_monthly_records(conn, target_month: str, wage_period_start: str, wage_period_end: str, pay_date_by_employee: dict):
    """
    Create payroll_monthly rows for all employees if missing.
    pay_date_by_employee: {employee_id: (pay_date_auto, pay_date_applied)}
    """
    employees = list_employees(conn)
    cur = conn.cursor()
    for e in employees:
        employee_id = e["employee_id"]
        pay_date_auto, pay_date_applied = pay_date_by_employee[employee_id]
        department_id_snapshot, department_name_snapshot = get_employee_department_snapshot(conn, int(employee_id))
        cur.execute(
            """
            INSERT OR IGNORE INTO payroll_monthly(
              target_month, employee_id,
              wage_period_start, wage_period_end,
              pay_date_auto, pay_date_applied,
              department_id_snapshot, department_name_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target_month,
                employee_id,
                wage_period_start,
                wage_period_end,
                pay_date_auto,
                pay_date_applied,
                department_id_snapshot,
                department_name_snapshot,
            ),
        )
    conn.commit()

def refresh_monthly_pay_dates(conn, target_month: str, pay_date_by_employee: dict):
    """
    既存 payroll_monthly の自動支払日を再計算して更新する。
    上書き指定がない行だけ pay_date_applied も自動日に合わせる。
    """
    cur = conn.cursor()
    for employee_id, (pay_date_auto, _) in pay_date_by_employee.items():
        cur.execute(
            """
            UPDATE payroll_monthly
            SET pay_date_auto = ?,
                pay_date_applied = CASE
                    WHEN pay_date_override IS NULL THEN ?
                    ELSE pay_date_applied
                END,
                updated_at = datetime('now')
            WHERE target_month = ? AND employee_id = ?
            """,
            (pay_date_auto, pay_date_auto, target_month, employee_id),
        )
    conn.commit()

def get_payroll_rows(conn, target_month: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          p.*,
          e.employee_code, e.name_kanji, e.department, e.department_id, e.payday_group,
          e.std_monthly_wage, e.std_pension_wage,
          COALESCE(e.is_social_insurance_target, 0) AS is_social_insurance_target,
          COALESCE(e.is_employment_insurance_target, 1) AS is_employment_insurance_target,
          e.tax_type, e.dependents_count, e.work_prefecture_name, e.birth_date,
          e.hire_date, e.leave_date,

          -- 総支給（入力値の合計：税社保計算はまだ含めない）
          (
            p.officer_pay + p.base_salary + p.deemed_ot + p.overtime_pay + p.special_allow + p.commute_nontax
          ) AS total_pay_input,

          -- 控除合計（旧固定控除は廃止済み）
          0 AS total_deduct_input,

          -- 手取り（入力ベース）
          (
            p.officer_pay + p.base_salary + p.deemed_ot + p.overtime_pay + p.special_allow + p.commute_nontax
          ) AS net_pay_input

        FROM payroll_monthly p
        JOIN employees e ON e.employee_id = p.employee_id
        WHERE p.target_month=?
        ORDER BY e.employee_id
        """,
        (target_month,),
    )
    return [_row_with_calculation_basis(conn, r) for r in cur.fetchall()]

def get_payroll_batch_rows(conn, target_month: str):
    """
    給与タブ用:
    対象月の payroll_monthly を、支払日(pay_date_applied)単位で集計して返す。
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          p.target_month,
          p.pay_date_applied,
          COUNT(*) AS employee_count,

          SUM(
            p.officer_pay + p.base_salary + p.deemed_ot + p.overtime_pay + p.special_allow + p.commute_nontax
          ) AS total_pay_input_sum,

          0 AS total_deduct_input_sum,

          SUM(
            COALESCE(p.emp_ins_employee, 0) +
            COALESCE(p.health_ins_employee, 0) +
            COALESCE(p.care_ins_employee, 0) +
            COALESCE(p.childcare_support_employee, 0) +
            COALESCE(p.pension_ins_employee, 0) +
            COALESCE(p.resident_tax_applied, 0) +
            COALESCE(p.withholding_tax_applied, 0)
          ) AS total_deduct_all_sum,

          SUM(
            (
              p.officer_pay + p.base_salary + p.deemed_ot + p.overtime_pay + p.special_allow + p.commute_nontax
            ) -
            (
              COALESCE(p.emp_ins_employee, 0) +
              COALESCE(p.health_ins_employee, 0) +
              COALESCE(p.care_ins_employee, 0) +
              COALESCE(p.childcare_support_employee, 0) +
              COALESCE(p.pension_ins_employee, 0) +
              COALESCE(p.resident_tax_applied, 0) +
              COALESCE(p.withholding_tax_applied, 0)
            )
          ) AS net_pay_sum

        FROM payroll_monthly p
        WHERE p.target_month = ?
        GROUP BY p.target_month, p.pay_date_applied
        ORDER BY p.pay_date_applied
        """,
        (target_month,),
    )
    return cur.fetchall()

# ==============================
# 年別一覧（対象年月基準）
# ==============================
def get_payroll_batch_rows_by_target_year(conn, year: int):
    rows = []
    for r in conn.execute(
        "SELECT DISTINCT target_month FROM payroll_monthly WHERE substr(target_month,1,4)=? ORDER BY target_month",
        (str(year),),
    ).fetchall():
        rows.extend(get_payroll_rows(conn, r["target_month"]))
    return _aggregate_payroll_basis_rows(rows, conn)
def get_payroll_batch_rows_by_paydate_year(conn, year: int):
    rows = []
    target_months = conn.execute(
        "SELECT DISTINCT target_month FROM payroll_monthly WHERE substr(pay_date_applied,1,4)=? ORDER BY target_month",
        (str(year),),
    ).fetchall()
    for r in target_months:
        rows.extend(
            row for row in get_payroll_rows(conn, r["target_month"])
            if str(row_get(row, "pay_date_applied", "") or "").startswith(str(year))
        )
    return _aggregate_payroll_basis_rows(rows, conn)

def get_payroll_rows_by_pay_date(conn, target_month: str, pay_date_applied: str):
    """
    支給日単位の詳細ダイアログ用:
    対象月 + 支払日で絞った社員明細一覧を返す。
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          p.*,
          e.employee_code, e.name_kanji, e.department, e.department_id, e.payday_group,
          e.std_monthly_wage, e.std_pension_wage,
          COALESCE(e.is_social_insurance_target, 0) AS is_social_insurance_target,
          COALESCE(e.is_employment_insurance_target, 1) AS is_employment_insurance_target,
          e.tax_type, e.dependents_count, e.work_prefecture_name, e.birth_date,
          e.hire_date, e.leave_date,

          (
            p.officer_pay + p.base_salary + p.deemed_ot + p.overtime_pay + p.special_allow + p.commute_nontax
          ) AS total_pay_input,

          0 AS total_deduct_input,

          (
            p.officer_pay + p.base_salary + p.deemed_ot + p.overtime_pay + p.special_allow + p.commute_nontax
          ) AS net_pay_input

        FROM payroll_monthly p
        JOIN employees e ON e.employee_id = p.employee_id
        WHERE p.target_month = ? AND p.pay_date_applied = ?
        ORDER BY e.employee_id
        """,
        (target_month, pay_date_applied),
    )
    return [_row_with_calculation_basis(conn, r) for r in cur.fetchall()]

def payroll_month_exists(conn, target_month: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM payroll_monthly WHERE target_month = ? LIMIT 1",
        (target_month,),
    ).fetchone()
    return row is not None

def list_payroll_copy_source_months(conn) -> list[str]:
    return [
        r["target_month"]
        for r in conn.execute(
            """
            SELECT DISTINCT target_month
            FROM payroll_monthly
            ORDER BY target_month DESC
            """
        ).fetchall()
        if r["target_month"]
    ]

def delete_payroll_batch(conn, target_month: str, pay_date_applied: str) -> int:
    payroll_ids = [
        int(r["payroll_id"])
        for r in conn.execute(
            """
            SELECT payroll_id
            FROM payroll_monthly
            WHERE target_month = ? AND pay_date_applied = ?
            """,
            (target_month, pay_date_applied),
        ).fetchall()
    ]
    if not payroll_ids:
        return 0

    placeholders = ",".join("?" for _ in payroll_ids)
    conn.execute(f"DELETE FROM payroll_monthly_item_values WHERE monthly_id IN ({placeholders})", payroll_ids)
    conn.execute(f"DELETE FROM payroll_monthly_social_detail WHERE payroll_id IN ({placeholders})", payroll_ids)
    conn.execute(f"DELETE FROM payroll_monthly_attendance WHERE payroll_id IN ({placeholders})", payroll_ids)
    cur = conn.execute(f"DELETE FROM payroll_monthly WHERE payroll_id IN ({placeholders})", payroll_ids)
    conn.commit()
    return cur.rowcount

def copy_prev_month_inputs(conn, target_month: str, prev_month: str):
    """
    Copy only INPUT FIELDS from prev_month -> target_month.
    Do NOT copy pay_date_override, and do NOT copy any pay_date fields.
    """
    rows = get_payroll_rows(conn, prev_month)
    cur = conn.cursor()
    for r in rows:
        employee_id = r["employee_id"]
        # Update input fields only; leave pay_date_* untouched.
        cur.execute(
            """
            UPDATE payroll_monthly SET
              officer_pay=?, base_salary=?, deemed_ot=?, overtime_pay=?, special_allow=?, commute_nontax=?,
              pay_free1=0, pay_free2=0, pay_free3=0, pay_free4=0, pay_free5=0,
              pay_free1_is_taxable=0, pay_free1_is_social_base=0, pay_free1_is_employment_base=0,
              pay_free2_is_taxable=0, pay_free2_is_social_base=0, pay_free2_is_employment_base=0,
              pay_free3_is_taxable=0, pay_free3_is_social_base=0, pay_free3_is_employment_base=0,
              pay_free4_is_taxable=0, pay_free4_is_social_base=0, pay_free4_is_employment_base=0,
              pay_free5_is_taxable=0, pay_free5_is_social_base=0, pay_free5_is_employment_base=0,
              travel_saving=0, deduct_free1=0, deduct_free2=0, deduct_free3=0, deduct_free4=0, deduct_free5=0,
              updated_at=datetime('now')
            WHERE target_month=? AND employee_id=?
            """,
            (
                r["officer_pay"], r["base_salary"], r["deemed_ot"], r["overtime_pay"], r["special_allow"], r["commute_nontax"],
                target_month, employee_id
            ),
        )
    conn.commit()

def override_pay_date(conn, payroll_id: int, override_date: str | None, reason: str | None, overridden_by: str | None):
    cur = conn.cursor()
    if override_date:
        cur.execute(
            """
            UPDATE payroll_monthly SET
              pay_date_override=?,
              pay_date_applied=?,
              pay_date_override_reason=?,
              pay_date_overridden_at=datetime('now'),
              pay_date_overridden_by=?,
              updated_at=datetime('now')
            WHERE payroll_id=?
            """,
            (override_date, override_date, reason, overridden_by, payroll_id),
        )
    else:
        # Clear override => revert to auto
        cur.execute(
            """
            UPDATE payroll_monthly SET
              pay_date_override=NULL,
              pay_date_applied=pay_date_auto,
              pay_date_override_reason=NULL,
              pay_date_overridden_at=NULL,
              pay_date_overridden_by=NULL,
              updated_at=datetime('now')
            WHERE payroll_id=?
            """,
            (payroll_id,),
        )
    conn.commit()

def update_payroll_inputs(conn, payroll_id: int, data: dict):
    """
    Update input fields for a payroll_monthly row.
    data: dict with keys matching columns.
    """
    cols = [
        "officer_pay", "base_salary", "deemed_ot", "overtime_pay", "special_allow", "commute_nontax",
        "note",
    ]

    sets = ", ".join([f"{c}=?" for c in cols]) + ", updated_at=datetime('now')"
    values = [data.get(c, "" if c == "note" else 0) for c in cols] + [payroll_id]

    cur = conn.cursor()
    cur.execute(f"UPDATE payroll_monthly SET {sets} WHERE payroll_id=?", values)
    conn.commit()

def get_payroll_by_id(conn, payroll_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.*,
               e.employee_code,
               e.name_kanji,
               e.department,
               e.department_id,
               e.payday_group,
               COALESCE(pos.name, '') AS position_name,
               COALESCE(emp_type.name, '') AS employment_type_name
        FROM payroll_monthly p
        JOIN employees e ON e.employee_id = p.employee_id
        LEFT JOIN positions pos ON pos.id = e.position_id
        LEFT JOIN employment_types emp_type ON emp_type.id = e.employment_type_id
        WHERE p.payroll_id=?
        """,
        (payroll_id,),
    )
    row = cur.fetchone()
    return _row_with_current_department_name(conn, row) if row else None

def _column_exists(conn, table: str, column: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]  # r[1] is column name
    return column in cols

def _table_exists(conn, table: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table,),
    )
    return cur.fetchone() is not None

def ensure_schema_migrations(conn):
    """足りない列・テーブルだけ追加する安全なマイグレーション。"""
    cur = conn.cursor()

    # -------------------------------------------------
    # employees
    # -------------------------------------------------
    if not _column_exists(conn, "employees", "std_monthly_wage"):
        conn.execute("ALTER TABLE employees ADD COLUMN std_monthly_wage INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "employees", "std_pension_wage"):
        conn.execute("ALTER TABLE employees ADD COLUMN std_pension_wage INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "employees", "is_social_insurance_target"):
        conn.execute("ALTER TABLE employees ADD COLUMN is_social_insurance_target INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            """
            UPDATE employees
            SET is_social_insurance_target = CASE
                WHEN COALESCE(std_monthly_wage, 0) > 0 OR COALESCE(std_pension_wage, 0) > 0 THEN 1
                ELSE 0
            END
            """
        )
    if not _column_exists(conn, "employees", "is_employment_insurance_target"):
        conn.execute("ALTER TABLE employees ADD COLUMN is_employment_insurance_target INTEGER NOT NULL DEFAULT 1")

    if not _column_exists(conn, "employees", "name_kana"):
        conn.execute("ALTER TABLE employees ADD COLUMN name_kana TEXT NOT NULL DEFAULT ''")

    if not _column_exists(conn, "employees", "tax_type"):
        conn.execute("ALTER TABLE employees ADD COLUMN tax_type TEXT NOT NULL DEFAULT '甲'")
    if not _column_exists(conn, "employees", "dependents_count"):
        conn.execute("ALTER TABLE employees ADD COLUMN dependents_count INTEGER NOT NULL DEFAULT 0")
    
    if not _column_exists(conn, "employees", "work_prefecture_name"):
        conn.execute("ALTER TABLE employees ADD COLUMN work_prefecture_name TEXT NOT NULL DEFAULT ''")
    if not _column_exists(conn, "employees", "address_postal_code"):
        conn.execute("ALTER TABLE employees ADD COLUMN address_postal_code TEXT NOT NULL DEFAULT ''")
    if not _column_exists(conn, "employees", "address_prefecture"):
        conn.execute("ALTER TABLE employees ADD COLUMN address_prefecture TEXT NOT NULL DEFAULT ''")
    if not _column_exists(conn, "employees", "address_city"):
        conn.execute("ALTER TABLE employees ADD COLUMN address_city TEXT NOT NULL DEFAULT ''")
    if not _column_exists(conn, "employees", "address_detail"):
        conn.execute("ALTER TABLE employees ADD COLUMN address_detail TEXT NOT NULL DEFAULT ''")
    if not _column_exists(conn, "employees", "resident_tax_municipality"):
        conn.execute("ALTER TABLE employees ADD COLUMN resident_tax_municipality TEXT NOT NULL DEFAULT ''")
    for col in (
        "phone",
        "email",
        "bank_name",
        "bank_branch_name",
        "bank_account_type",
        "bank_account_number",
        "bank_account_holder",
    ):
        if not _column_exists(conn, "employees", col):
            conn.execute(f"ALTER TABLE employees ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")

    # 生年月日（介護保険判定用）
    if not _column_exists(conn, "employees", "birth_date"):
        conn.execute("ALTER TABLE employees ADD COLUMN birth_date TEXT")

    # 入退社・月末在籍要件
    if not _column_exists(conn, "employees", "hire_date"):
        conn.execute("ALTER TABLE employees ADD COLUMN hire_date TEXT")

    if not _column_exists(conn, "employees", "is_on_leave"):
        conn.execute("ALTER TABLE employees ADD COLUMN is_on_leave INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "employees", "leave_start_date"):
        conn.execute("ALTER TABLE employees ADD COLUMN leave_start_date TEXT")
    if not _column_exists(conn, "employees", "leave_expected_end_date"):
        conn.execute("ALTER TABLE employees ADD COLUMN leave_expected_end_date TEXT")
    if not _column_exists(conn, "employees", "leave_memo"):
        conn.execute("ALTER TABLE employees ADD COLUMN leave_memo TEXT NOT NULL DEFAULT ''")

    if not _column_exists(conn, "employees", "leave_date"):
        conn.execute("ALTER TABLE employees ADD COLUMN leave_date TEXT")

    if not _column_exists(conn, "employees", "retirement_processed"):
        conn.execute("ALTER TABLE employees ADD COLUMN retirement_processed INTEGER NOT NULL DEFAULT 0")

    # 給与支給タイミング
    if not _column_exists(conn, "employees", "payment_schedule_id"):
        conn.execute("ALTER TABLE employees ADD COLUMN payment_schedule_id INTEGER")

    if not _column_exists(conn, "employees", "is_deleted"):
        conn.execute("ALTER TABLE employees ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0")

    if not _column_exists(conn, "employees", "deleted_at"):
        conn.execute("ALTER TABLE employees ADD COLUMN deleted_at TEXT")

    if not _column_exists(conn, "employees", "memo"):
        conn.execute("ALTER TABLE employees ADD COLUMN memo TEXT")

    if not _column_exists(conn, "employees", "department_id"):
        conn.execute("ALTER TABLE employees ADD COLUMN department_id INTEGER")
    if not _column_exists(conn, "employees", "position_id"):
        conn.execute("ALTER TABLE employees ADD COLUMN position_id INTEGER")
    if not _column_exists(conn, "employees", "employment_type_id"):
        conn.execute("ALTER TABLE employees ADD COLUMN employment_type_id INTEGER")

    _normalize_existing_employee_codes(conn)

    if _table_exists(conn, "company_settings"):
        company_columns = {
            "attendance_time_input_mode": "TEXT NOT NULL DEFAULT '60進法'",
            "attendance_time_round_unit": "TEXT NOT NULL DEFAULT '1分'",
            "attendance_time_round_method": "TEXT NOT NULL DEFAULT 'なし'",
        }
        for col, ddl in company_columns.items():
            if not _column_exists(conn, "company_settings", col):
                conn.execute(f"ALTER TABLE company_settings ADD COLUMN {col} {ddl}")

    if _table_exists(conn, "departments"):
        if not _column_exists(conn, "departments", "parent_department_id"):
            conn.execute("ALTER TABLE departments ADD COLUMN parent_department_id INTEGER")
        if not _column_exists(conn, "departments", "department_type"):
            conn.execute("ALTER TABLE departments ADD COLUMN department_type TEXT NOT NULL DEFAULT 'department'")
        remove_departments_name_unique_constraint(conn)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_schedules (
          payment_schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
          schedule_name       TEXT NOT NULL UNIQUE,
          closing_mode        TEXT NOT NULL,
          pay_day             INTEGER NOT NULL,
          is_active           INTEGER NOT NULL DEFAULT 1,
          memo                TEXT,
          created_at          TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    if not _column_exists(conn, "payment_schedules", "memo"):
        conn.execute("ALTER TABLE payment_schedules ADD COLUMN memo TEXT")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payroll_monthly_attendance (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          payroll_id INTEGER NOT NULL UNIQUE,
          employee_id INTEGER NOT NULL,
          target_month TEXT NOT NULL,
          pay_date TEXT NOT NULL,
          scheduled_work_days REAL NOT NULL DEFAULT 0,
          work_days REAL NOT NULL DEFAULT 0,
          weekday_work_days REAL NOT NULL DEFAULT 0,
          holiday_work_days REAL NOT NULL DEFAULT 0,
          paid_leave_days REAL NOT NULL DEFAULT 0,
          special_leave_days REAL NOT NULL DEFAULT 0,
          absence_days REAL NOT NULL DEFAULT 0,
          substitute_leave_taken_days REAL NOT NULL DEFAULT 0,
          substitute_leave_remaining_days REAL NOT NULL DEFAULT 0,
          late_count INTEGER NOT NULL DEFAULT 0,
          early_leave_count INTEGER NOT NULL DEFAULT 0,
          scheduled_work_minutes INTEGER NOT NULL DEFAULT 0,
          work_minutes INTEGER NOT NULL DEFAULT 0,
          non_scheduled_work_minutes INTEGER NOT NULL DEFAULT 0,
          overtime_minutes INTEGER NOT NULL DEFAULT 0,
          holiday_work_minutes INTEGER NOT NULL DEFAULT 0,
          night_work_minutes INTEGER NOT NULL DEFAULT 0,
          holiday_night_work_minutes INTEGER NOT NULL DEFAULT 0,
          late_early_leave_minutes INTEGER NOT NULL DEFAULT 0,
          total_overtime_minutes INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now')),
          FOREIGN KEY(payroll_id) REFERENCES payroll_monthly(payroll_id),
          FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
        )
        """
    )

    # -------------------------------------------------
    # payroll_monthly
    # -------------------------------------------------
    if not _column_exists(conn, "payroll_monthly", "resident_tax_auto"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN resident_tax_auto INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "resident_tax_override"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN resident_tax_override INTEGER")
    if not _column_exists(conn, "payroll_monthly", "resident_tax_applied"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN resident_tax_applied INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "resident_tax_override_reason"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN resident_tax_override_reason TEXT")

    if not _column_exists(conn, "payroll_monthly", "withholding_tax_auto"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN withholding_tax_auto INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "withholding_tax_override"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN withholding_tax_override INTEGER")
    if not _column_exists(conn, "payroll_monthly", "withholding_tax_applied"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN withholding_tax_applied INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "withholding_tax_override_reason"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN withholding_tax_override_reason TEXT")

    if not _column_exists(conn, "payroll_monthly", "health_ins_employee"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN health_ins_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "care_ins_employee"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN care_ins_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "childcare_support_employee"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN childcare_support_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "childcare_support_employer"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN childcare_support_employer INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "pension_ins_employee"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN pension_ins_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "social_ins_total3"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN social_ins_total3 INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "social_ins_total_calc"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN social_ins_total_calc INTEGER NOT NULL DEFAULT 0")

    if not _column_exists(conn, "payroll_monthly", "emp_ins_base"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN emp_ins_base INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "emp_ins_rate_employee"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN emp_ins_rate_employee REAL NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "emp_ins_employee"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN emp_ins_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "emp_ins_rate_employer"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN emp_ins_rate_employer REAL NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "emp_ins_employer"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN emp_ins_employer INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_monthly", "department_id_snapshot"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN department_id_snapshot INTEGER")
    if not _column_exists(conn, "payroll_monthly", "department_name_snapshot"):
        conn.execute("ALTER TABLE payroll_monthly ADD COLUMN department_name_snapshot TEXT NOT NULL DEFAULT ''")
    _backfill_department_snapshots(conn, "payroll_monthly")

    # -------------------------------------------------
    # payroll_bonus
    # -------------------------------------------------
    if not _column_exists(conn, "payroll_bonus", "health_ins_auto"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN health_ins_auto INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "health_ins_override"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN health_ins_override INTEGER")
    if not _column_exists(conn, "payroll_bonus", "health_ins_employee"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN health_ins_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "care_ins_auto"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN care_ins_auto INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "care_ins_override"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN care_ins_override INTEGER")
    if not _column_exists(conn, "payroll_bonus", "care_ins_employee"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN care_ins_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "childcare_support_auto"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN childcare_support_auto INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "childcare_support_override"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN childcare_support_override INTEGER")
    if not _column_exists(conn, "payroll_bonus", "childcare_support_employee"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN childcare_support_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "childcare_support_employer"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN childcare_support_employer INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "pension_ins_auto"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN pension_ins_auto INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "pension_ins_override"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN pension_ins_override INTEGER")
    if not _column_exists(conn, "payroll_bonus", "pension_ins_employee"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN pension_ins_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "emp_ins_auto"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN emp_ins_auto INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "emp_ins_override"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN emp_ins_override INTEGER")
    if not _column_exists(conn, "payroll_bonus", "emp_ins_employee"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN emp_ins_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "social_ins_total_calc"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN social_ins_total_calc INTEGER NOT NULL DEFAULT 0")

    if not _column_exists(conn, "payroll_bonus", "std_bonus_raw"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN std_bonus_raw INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "std_bonus_health"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN std_bonus_health INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "std_bonus_pension"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN std_bonus_pension INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "bonus_fiscal_year"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN bonus_fiscal_year INTEGER NOT NULL DEFAULT 0")

    if not _column_exists(conn, "payroll_bonus", "pay_date"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN pay_date TEXT NOT NULL DEFAULT ''")
 
    # 子ども・子育て拠出金（事業主負担のみ）
    if not _column_exists(conn, "payroll_bonus", "childcare_contribution_employer"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN childcare_contribution_employer INTEGER NOT NULL DEFAULT 0")

    if not _column_exists(conn, "payroll_bonus", "withholding_tax_auto"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN withholding_tax_auto INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "withholding_tax_override"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN withholding_tax_override INTEGER")
    if not _column_exists(conn, "payroll_bonus", "withholding_tax_applied"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN withholding_tax_applied INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "withholding_tax_override_reason"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN withholding_tax_override_reason TEXT")
    if not _column_exists(conn, "payroll_bonus", "department_id_snapshot"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN department_id_snapshot INTEGER")
    if not _column_exists(conn, "payroll_bonus", "department_name_snapshot"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN department_name_snapshot TEXT NOT NULL DEFAULT ''")
    _backfill_department_snapshots(conn, "payroll_bonus")

    # -------------------------------------------------
    # social_insurance_rates
    # -------------------------------------------------
    if not _column_exists(conn, "social_insurance_rates", "care_employee"):
        conn.execute("ALTER TABLE social_insurance_rates ADD COLUMN care_employee REAL NOT NULL DEFAULT 0")
    if not _column_exists(conn, "social_insurance_rates", "childcare_employee"):
        conn.execute("ALTER TABLE social_insurance_rates ADD COLUMN childcare_employee REAL NOT NULL DEFAULT 0")
    if not _column_exists(conn, "social_insurance_rates", "childcare_employer"):
        conn.execute("ALTER TABLE social_insurance_rates ADD COLUMN childcare_employer REAL NOT NULL DEFAULT 0")
    if not _column_exists(conn, "social_insurance_rates", "childcare_contribution_employer"):
        conn.execute("ALTER TABLE social_insurance_rates ADD COLUMN childcare_contribution_employer REAL NOT NULL DEFAULT 0")
    if not _column_exists(conn, "social_insurance_rates_v2", "childcare_contribution_employer"):
        conn.execute(
            "ALTER TABLE social_insurance_rates_v2 "
            "ADD COLUMN childcare_contribution_employer REAL NOT NULL DEFAULT 0"
        )

    # -------------------------------------------------
    # dynamic social insurance tables
    # -------------------------------------------------
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS social_insurance_item_master (
          item_code           TEXT PRIMARY KEY,
          item_name           TEXT NOT NULL,
          applies_to_monthly  INTEGER NOT NULL DEFAULT 1,
          applies_to_bonus    INTEGER NOT NULL DEFAULT 1,
          base_type           TEXT NOT NULL,
          is_tax_deductible   INTEGER NOT NULL DEFAULT 1,
          sort_order          INTEGER NOT NULL DEFAULT 0,
          is_active           INTEGER NOT NULL DEFAULT 1,
          created_at          TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS social_insurance_item_rates (
          rate_id             INTEGER PRIMARY KEY AUTOINCREMENT,
          item_code           TEXT NOT NULL,
          start_month         TEXT NOT NULL,
          employee_rate       REAL NOT NULL DEFAULT 0,
          employer_rate       REAL NOT NULL DEFAULT 0,
          note                TEXT,
          created_at          TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
          UNIQUE(item_code, start_month),
          FOREIGN KEY(item_code) REFERENCES social_insurance_item_master(item_code)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payroll_monthly_social_detail (
          detail_id           INTEGER PRIMARY KEY AUTOINCREMENT,
          payroll_id          INTEGER NOT NULL,
          item_code           TEXT NOT NULL,
          base_amount         INTEGER NOT NULL DEFAULT 0,
          employee_rate       REAL NOT NULL DEFAULT 0,
          employer_rate       REAL NOT NULL DEFAULT 0,
          employee_amount     INTEGER NOT NULL DEFAULT 0,
          employer_amount     INTEGER NOT NULL DEFAULT 0,
          sort_order          INTEGER NOT NULL DEFAULT 0,
          created_at          TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
          UNIQUE(payroll_id, item_code),
          FOREIGN KEY(payroll_id) REFERENCES payroll_monthly(payroll_id),
          FOREIGN KEY(item_code) REFERENCES social_insurance_item_master(item_code)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payroll_bonus_social_detail (
          detail_id           INTEGER PRIMARY KEY AUTOINCREMENT,
          bonus_id            INTEGER NOT NULL,
          item_code           TEXT NOT NULL,
          base_amount         INTEGER NOT NULL DEFAULT 0,
          employee_rate       REAL NOT NULL DEFAULT 0,
          employer_rate       REAL NOT NULL DEFAULT 0,
          employee_amount     INTEGER NOT NULL DEFAULT 0,
          employer_amount     INTEGER NOT NULL DEFAULT 0,
          sort_order          INTEGER NOT NULL DEFAULT 0,
          created_at          TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
          UNIQUE(bonus_id, item_code),
          FOREIGN KEY(bonus_id) REFERENCES payroll_bonus(bonus_id),
          FOREIGN KEY(item_code) REFERENCES social_insurance_item_master(item_code)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS social_insurance_rates_v2 (
        rate_id                         INTEGER PRIMARY KEY AUTOINCREMENT,
        start_month                     TEXT NOT NULL,
        prefecture_name                 TEXT NOT NULL DEFAULT 'DEFAULT',
        health_employee                 REAL NOT NULL DEFAULT 0,
        pension_employee                REAL NOT NULL DEFAULT 0,
        care_employee                   REAL NOT NULL DEFAULT 0,
        childcare_employee              REAL NOT NULL DEFAULT 0,
        childcare_employer              REAL NOT NULL DEFAULT 0,
        childcare_contribution_employer REAL NOT NULL DEFAULT 0,
        note                            TEXT,
        created_at                      TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at                      TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(start_month, prefecture_name)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS company_settings (
          id            INTEGER PRIMARY KEY CHECK (id = 1),
          company_name  TEXT NOT NULL DEFAULT '',
          company_kana  TEXT NOT NULL DEFAULT '',
          postal_code   TEXT NOT NULL DEFAULT '',
          address       TEXT NOT NULL DEFAULT '',
          phone         TEXT NOT NULL DEFAULT '',
          attendance_time_input_mode TEXT NOT NULL DEFAULT '60進法',
          attendance_time_round_unit TEXT NOT NULL DEFAULT '1分',
          attendance_time_round_method TEXT NOT NULL DEFAULT 'なし',
          memo          TEXT,
          created_at    TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )

    for table_sql in [
        """
        CREATE TABLE IF NOT EXISTS departments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          parent_department_id INTEGER,
          department_type TEXT NOT NULL DEFAULT 'department',
          display_order INTEGER NOT NULL DEFAULT 0,
          is_active INTEGER NOT NULL DEFAULT 1,
          memo TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS positions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          display_order INTEGER NOT NULL DEFAULT 0,
          is_active INTEGER NOT NULL DEFAULT 1,
          memo TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS employment_types (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          display_order INTEGER NOT NULL DEFAULT 0,
          is_active INTEGER NOT NULL DEFAULT 1,
          memo TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS payroll_item_categories (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT NOT NULL UNIQUE,
          name TEXT NOT NULL,
          item_kind TEXT NOT NULL,
          display_order INTEGER NOT NULL DEFAULT 0,
          is_active INTEGER NOT NULL DEFAULT 1,
          memo TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS payroll_items (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT NOT NULL UNIQUE,
          name TEXT NOT NULL,
          item_kind TEXT NOT NULL,
          category_id INTEGER,
          is_system INTEGER NOT NULL DEFAULT 0,
          is_active INTEGER NOT NULL DEFAULT 1,
          is_taxable INTEGER NOT NULL DEFAULT 0,
          is_social_insurance_base INTEGER NOT NULL DEFAULT 0,
          is_employment_insurance_base INTEGER NOT NULL DEFAULT 0,
          is_commute INTEGER NOT NULL DEFAULT 0,
          display_order INTEGER NOT NULL DEFAULT 0,
          memo TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now')),
          FOREIGN KEY(category_id) REFERENCES payroll_item_categories(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS payroll_item_assignments (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          item_id INTEGER NOT NULL,
          target_type TEXT NOT NULL DEFAULT 'all',
          department_id INTEGER,
          position_id INTEGER,
          employment_type_id INTEGER,
          employee_id INTEGER,
          action TEXT NOT NULL DEFAULT 'include',
          is_active INTEGER NOT NULL DEFAULT 1,
          display_order INTEGER NOT NULL DEFAULT 0,
          memo TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now')),
          FOREIGN KEY(item_id) REFERENCES payroll_items(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS employee_payroll_item_standard_values (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          employee_id INTEGER NOT NULL,
          item_id INTEGER NOT NULL,
          start_month TEXT NOT NULL,
          amount INTEGER NOT NULL DEFAULT 0,
          is_active INTEGER NOT NULL DEFAULT 1,
          memo TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now')),
          UNIQUE(employee_id, item_id, start_month),
          FOREIGN KEY(employee_id) REFERENCES employees(employee_id),
          FOREIGN KEY(item_id) REFERENCES payroll_items(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS payroll_monthly_item_values (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          monthly_id INTEGER NOT NULL,
          employee_id INTEGER NOT NULL,
          year INTEGER NOT NULL,
          month INTEGER NOT NULL,
          item_id INTEGER NOT NULL,
          item_kind TEXT NOT NULL,
          amount INTEGER NOT NULL DEFAULT 0,
          source TEXT NOT NULL DEFAULT 'manual',
          is_locked INTEGER NOT NULL DEFAULT 0,
          memo TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now')),
          UNIQUE(monthly_id, item_id),
          FOREIGN KEY(monthly_id) REFERENCES payroll_monthly(payroll_id),
          FOREIGN KEY(employee_id) REFERENCES employees(employee_id),
          FOREIGN KEY(item_id) REFERENCES payroll_items(id)
        )
        """,
    ]:
        conn.execute(table_sql)

    conn.commit()

    seed_social_insurance_item_master(conn)
    seed_phase1_masters(conn)
    ensure_payroll_item_codes(conn)


def _get_db_dir(conn) -> Path:
    """SQLite DBファイルが置かれているフォルダ（=データ保存先）を返す。"""
    cur = conn.cursor()
    cur.execute("PRAGMA database_list")
    rows = cur.fetchall()
    for r in rows:
        if r[1] == "main":
            p = r[2]
            if p:
                return Path(p).resolve().parent
    return Path.cwd()


class WithholdingTableError(RuntimeError):
    pass


def _withholding_dir(conn) -> Path:
    """税額表やキャッシュ等のリソース置き場。settings.json で変更可能。"""
    db_dir = _get_db_dir(conn)
    s = app_settings.get_setting("resources_dir", None)
    if isinstance(s, str) and s.strip():
        d = Path(s).expanduser()
        d.mkdir(parents=True, exist_ok=True)
        return d
    # 互換：DB隣の resources
    return app_settings.get_resources_dir_fallback(db_dir)


def _find_withholding_source_file(conn) -> Path | None:
    """resourcesフォルダ内の税額表Excel（.xls/.xlsx）を探す。"""
    d = _withholding_dir(conn)
    cands = list(d.glob("*.xls")) + list(d.glob("*.xlsx"))
    return cands[0] if cands else None


def _cache_path(conn, year: int) -> Path:
    return _withholding_dir(conn) / f"withholding_{year}_monthly.json"


def _load_monthly_table_from_xls(path: Path) -> dict:
    import os

    print("[WITHHOLDING] monthly excel path =", path)
    print("[WITHHOLDING] exists =", os.path.exists(path))
    
    """国税庁 月額表（.xls）を読み取り、内部用テーブル(dict)を返す。"""
    try:
        import xlrd  # type: ignore
    except Exception as e:
        raise WithholdingTableError(
            "税額表Excel（.xls）を読み取るために 'xlrd' が必要です。\n"
            "インストール: pip install xlrd\n"
            "※Officeがある場合は Excel で .xlsx 形式に保存し直す方法もあります。"
        ) from e

    book = xlrd.open_workbook(str(path))
    sh = book.sheet_by_index(0)
    return _parse_monthly_sheet_rows(
        get_cell=lambda r, c: sh.cell_value(r, c),
        nrows=sh.nrows,
        ncols=sh.ncols,
    )


def _load_monthly_table_from_xlsx(path: Path) -> dict:
    """国税庁 月額表（.xlsx）を読み取り、内部用テーブル(dict)を返す。"""
    from openpyxl import load_workbook  # type: ignore

    wb = load_workbook(filename=str(path), data_only=True, read_only=True)

    # できるだけ「月額」シートを選ぶ（active が表紙になる年があるため）
    ws = None
    for name in wb.sheetnames:
        if "月額" in str(name):
            ws = wb[name]
            break
    if ws is None:
        ws = wb.active

    max_row = ws.max_row
    max_col = ws.max_column

    def _cell(r, c):
        v = ws.cell(row=r + 1, column=c + 1).value
        return v if v is not None else ""

    return _parse_monthly_sheet_rows(_cell, max_row, max_col)


def _parse_monthly_sheet_rows(get_cell, nrows: int, ncols: int) -> dict:
    """月額表のシート（行・列アクセス関数）から税額テーブルを抽出する。"""
    OTSU_RATE_UNDER_105K = 0.03063

    brackets: list[dict] = []

    upper_105k = 105000
    found_under = False
    for r in range(min(nrows, 120)):
        v1 = get_cell(r, 1)
        v2 = get_cell(r, 2)
        if isinstance(v1, (int, float)) and int(v1) == upper_105k and "未満" in str(v2):
            found_under = True
            break
    if found_under:
        brackets.append(
            {
                "lower": 0,
                "upper": upper_105k,
                "kou": [0, 0, 0, 0, 0, 0, 0, 0],
                "otsu_mode": "rate",
                "otsu_rate": OTSU_RATE_UNDER_105K,
            }
        )

    for r in range(nrows):
        seq = get_cell(r, 0)
        if not isinstance(seq, (int, float)):
            continue
        if int(seq) != seq:
            continue
        lower = get_cell(r, 1)
        upper = get_cell(r, 2)
        if not isinstance(lower, (int, float)) or not isinstance(upper, (int, float)):
            continue
        kou = []
        ok = True
        for c in range(3, 11):
            v = get_cell(r, c)
            if not isinstance(v, (int, float)):
                ok = False
                break
            kou.append(int(v))
        if not ok:
            continue
        otsu = get_cell(r, 11)
        if not isinstance(otsu, (int, float)):
            continue

        brackets.append(
            {
                "lower": int(lower),
                "upper": int(upper),
                "kou": kou,
                "otsu_mode": "fixed",
                "otsu": int(otsu),
            }
        )

    for r in range(nrows):
        low_txt = str(get_cell(r, 1) or "")
        if "円" in low_txt and "," in low_txt:
            m = re.search(r"([0-9,]+)", low_txt)
            if not m:
                continue
            lower = int(m.group(1).replace(",", ""))
            v3 = get_cell(r, 3)
            v11 = get_cell(r, 11)
            if not isinstance(v3, (int, float)) or not isinstance(v11, (int, float)):
                continue
            kou = []
            ok = True
            for c in range(3, 11):
                v = get_cell(r, c)
                if not isinstance(v, (int, float)):
                    ok = False
                    break
                kou.append(int(v))
            if not ok:
                continue
            brackets.append(
                {
                    "lower": int(lower),
                    "upper": None,
                    "kou": kou,
                    "otsu_mode": "fixed",
                    "otsu": int(v11),
                }
            )
            break

    if not brackets:
        raise WithholdingTableError(
            "税額表Excelから税額データを抽出できませんでした。\n"
            "国税庁の『月額表（令和8年分）』のExcelファイルか確認してください。"
        )

    brackets.sort(key=lambda b: int(b["lower"]))
    return {
        "year": WITHHOLDING_YEAR_DEFAULT,
        "kind": "monthly",
        "brackets": brackets,
    }


def build_withholding_cache_from_excel(conn, year: int = WITHHOLDING_YEAR_DEFAULT) -> Path:
    """withholdingフォルダ内のExcelからJSONキャッシュを生成する。"""
    src = _find_withholding_source_file(conn)
    if not src:
        d = _withholding_dir(conn)
        raise WithholdingTableError(
            "税額表Excelが見つかりません。\n"
            f"次のフォルダに、国税庁の月額表Excel（.xls/.xlsx）を置いてください：\n{d}"
        )

    if src.suffix.lower() == ".xls":
        table = _load_monthly_table_from_xls(src)
    else:
        table = _load_monthly_table_from_xlsx(src)

    out = _cache_path(conn, year)
    out.write_text(json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load_withholding_table(conn, year: int = WITHHOLDING_YEAR_DEFAULT) -> dict:
    """
    月額表（源泉所得税）テーブルを返す。
    - settings.json の withholding_monthly_excel を最優先で使用
    - JSONキャッシュ（withholding_{year}_monthly.json）を使用
    - 税額表が差し替わったら自動でキャッシュ再生成（mtime比較）
    """
    p = _cache_path(conn, year)

    # 1) 月額表Excelのパスを「設定から」確定する（探さない）
    src = None

    # settings.json のフルパス指定を最優先
    s = app_settings.get_setting("withholding_monthly_excel", None)
    if isinstance(s, str) and s.strip():
        cand = Path(s).expanduser()
        if cand.exists():
            src = cand

    # フルパスが無い/存在しない場合は resources_dir + withholding_monthly.xlsx を見る
    if src is None:
        d = _withholding_dir(conn)  # settings.json の resources_dir or DB隣resources
        cand = d / "withholding_monthly.xlsx"
        if cand.exists():
            src = cand

    # それでも無い場合だけ、最後に「月額っぽいファイル」を探す（互換）
    if src is None:
        d = _withholding_dir(conn)
        cands = list(d.glob("*.xls")) + list(d.glob("*.xlsx"))
        # 月額/Monthly っぽいもの優先
        for cand in cands:
            name = cand.name.lower()
            if ("月額" in cand.name) or ("monthly" in name and "bonus" not in name):
                src = cand
                break
        if src is None and cands:
            # 最後の手段：1個だけならそれを使う
            if len(cands) == 1:
                src = cands[0]

    if src is None:
        d = _withholding_dir(conn)
        raise WithholdingTableError(
            "所得税（源泉）の税額表Excelが見つかりません。\n"
            "settings.json の 'withholding_monthly_excel' を確認してください。\n"
            f"探索フォルダ: {d}"
        )

    # 2) キャッシュが新しければキャッシュ利用、古ければ再生成
    def _mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except Exception:
            return 0.0

    need_rebuild = True
    if p.exists():
        # 税額表ファイルがキャッシュより古い/同じならキャッシュOK
        if _mtime(p) >= _mtime(src):
            need_rebuild = False

    if need_rebuild:
        # Excel → 内部テーブル(dict) を生成してキャッシュ
        if src.suffix.lower() == ".xls":
            table = _load_monthly_table_from_xls(src)
        else:
            table = _load_monthly_table_from_xlsx(src)

        p.write_text(json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8")

    return json.loads(p.read_text(encoding="utf-8"))


def _calc_taxable_pay_from_payroll_row(r, conn=None) -> int:
    """課税支給額（簡易）"""
    if conn is not None and USE_DYNAMIC_ITEMS_FOR_TAXABLE_PAY:
        dynamic = get_dynamic_totals_for_payroll_row(conn, r)
        if dynamic["has_dynamic_items"]:
            return max(0, int(dynamic["taxable_pay"] or 0))

    base = 0
    base += int(r["officer_pay"])
    base += int(r["base_salary"])
    base += int(r["deemed_ot"])
    base += int(r["overtime_pay"])
    base += int(r["special_allow"])
    # commute_nontax は除外
    return max(0, base)


def _lookup_withholding(table: dict, taxable_after_social: int, tax_type: str, dependents: int) -> int:
    amt = int(math.floor(max(0, taxable_after_social)))
    tax_type = (tax_type or "甲").strip()
    dependents = int(dependents)
    if dependents < 0:
        dependents = 0
    if dependents > 7:
        dependents = 7

    brackets = table.get("brackets", [])
    if not brackets:
        return 0

    b_hit = None
    for b in brackets:
        low = int(b["lower"])
        up = b.get("upper", None)
        if up is None:
            if amt >= low:
                b_hit = b
                break
        else:
            if low <= amt < int(up):
                b_hit = b
                break
    if b_hit is None:
        b_hit = brackets[-1]

    if tax_type == "乙":
        if b_hit.get("otsu_mode") == "rate":
            rate = float(b_hit.get("otsu_rate", 0.0))
            return int(math.floor(amt * rate))
        return int(b_hit.get("otsu", 0))

    kou = b_hit.get("kou", [])
    if 0 <= dependents < len(kou):
        return int(kou[dependents])
    return int(kou[0]) if kou else 0


def apply_withholding_tax_auto(conn, target_month: str, year: int = WITHHOLDING_YEAR_DEFAULT):
    table = load_withholding_table(conn, year)
    rows = get_payroll_rows(conn, target_month)
    cur = conn.cursor()

    for r in rows:
        taxable_pay = _calc_taxable_pay_from_payroll_row(r, conn)
        social = int(row_get(r, "social_ins_total_calc", 0) or 0)
        taxable_after = taxable_pay - social

        tax_type = row_get(r,"tax_type", "甲")
        deps = int(row_get(r,"dependents_count", 0) or 0)
        auto = _lookup_withholding(table, taxable_after, tax_type, deps)

        override = r["withholding_tax_override"] if "withholding_tax_override" in r.keys() else None
        applied = auto if override is None else int(override)

        cur.execute(
            """
            UPDATE payroll_monthly
            SET withholding_tax_auto=?, withholding_tax_applied=?, updated_at=datetime('now')
            WHERE payroll_id=?
            """,
            (auto, applied, r["payroll_id"]),
        )

    conn.commit()

def recalc_target_month(conn, target_month: str, year: int = WITHHOLDING_YEAR_DEFAULT):
    apply_employment_insurance_auto(conn, target_month)
    apply_social_insurance_auto(conn, target_month)
    apply_resident_tax_auto(conn, target_month)
    apply_withholding_tax_auto(conn, target_month, year=year)

def override_withholding_tax(conn, payroll_id: int, override_amount: int | None, reason: str | None):
    cur = conn.cursor()
    if override_amount is None:
        cur.execute(
            """
            UPDATE payroll_monthly
            SET withholding_tax_override=NULL,
                withholding_tax_override_reason=NULL,
                withholding_tax_applied=withholding_tax_auto,
                updated_at=datetime('now')
            WHERE payroll_id=?
            """,
            (payroll_id,),
        )
    else:
        cur.execute(
            """
            UPDATE payroll_monthly
            SET withholding_tax_override=?,
                withholding_tax_override_reason=?,
                withholding_tax_applied=?,
                updated_at=datetime('now')
            WHERE payroll_id=?
            """,
            (override_amount, reason, override_amount, payroll_id),
        )
    conn.commit()

def upsert_resident_tax(conn, employee_id: int, start_month: str, amount: int, note: str | None = None):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO resident_tax_history(employee_id, start_month, amount, note)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(employee_id, start_month) DO UPDATE SET
          amount=excluded.amount,
          note=excluded.note,
          updated_at=datetime('now')
        """,
        (employee_id, start_month, amount, note),
    )
    conn.commit()

def list_resident_tax(conn, employee_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM resident_tax_history
        WHERE employee_id=?
        ORDER BY start_month DESC
        """,
        (employee_id,),
    )
    return cur.fetchall()

def get_resident_tax_direct_amount(conn, employee_id: int, start_month: str) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT amount FROM resident_tax_history
        WHERE employee_id=? AND start_month=?
        """,
        (employee_id, start_month),
    )
    row = cur.fetchone()
    return int(row["amount"]) if row else 0

def list_resident_tax_for_period(conn, start_month: str, end_month: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM resident_tax_history
        WHERE start_month >= ? AND start_month <= ?
        ORDER BY employee_id, start_month
        """,
        (start_month, end_month),
    )
    return cur.fetchall()

def upsert_resident_tax_annual_values(conn, employee_id: int, month_amount_map: dict, note: str | None = None):
    cur = conn.cursor()
    for start_month, amount in month_amount_map.items():
        cur.execute(
            """
            INSERT INTO resident_tax_history(employee_id, start_month, amount, note)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(employee_id, start_month) DO UPDATE SET
              amount=excluded.amount,
              note=excluded.note,
              updated_at=datetime('now')
            """,
            (employee_id, start_month, int(amount or 0), note),
        )
    conn.commit()

def apply_resident_tax_auto_for_period(conn, start_month: str, end_month: str):
    y, m = (int(x) for x in start_month.split("-", 1))
    ey, em = (int(x) for x in end_month.split("-", 1))
    while (y, m) <= (ey, em):
        apply_resident_tax_auto(conn, f"{y:04d}-{m:02d}")
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1

def get_resident_tax_amount_for_month(conn, employee_id: int, target_month: str) -> int:
    """
    Find the latest resident tax record with start_month <= target_month.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT amount FROM resident_tax_history
        WHERE employee_id=? AND start_month <= ?
        ORDER BY start_month DESC
        LIMIT 1
        """,
        (employee_id, target_month),
    )
    row = cur.fetchone()
    return int(row["amount"]) if row else 0

def apply_resident_tax_auto(conn, target_month: str):
    """
    For each payroll_monthly row of target_month:
    - resident_tax_auto set from history
    - resident_tax_applied set to auto unless override exists
    """
    rows = get_payroll_rows(conn, target_month)
    cur = conn.cursor()
    for r in rows:
        employee_id = r["employee_id"]
        auto = get_resident_tax_amount_for_month(conn, employee_id, target_month)

        # if override exists, keep applied as override; else apply auto
        override = r["resident_tax_override"] if "resident_tax_override" in r.keys() else None
        if override is None:
            applied = auto
        else:
            applied = int(override)

        cur.execute(
            """
            UPDATE payroll_monthly
            SET resident_tax_auto=?, resident_tax_applied=?, updated_at=datetime('now')
            WHERE payroll_id=?
            """,
            (auto, applied, r["payroll_id"]),
        )
    conn.commit()

def override_resident_tax(conn, payroll_id: int, override_amount: int | None, reason: str | None):
    """
    Set or clear override on a payroll row.
    """
    cur = conn.cursor()
    if override_amount is None:
        # clear override -> revert to auto
        cur.execute(
            """
            UPDATE payroll_monthly
            SET resident_tax_override=NULL,
                resident_tax_override_reason=NULL,
                resident_tax_applied=resident_tax_auto,
                updated_at=datetime('now')
            WHERE payroll_id=?
            """,
            (payroll_id,),
        )
    else:
        cur.execute(
            """
            UPDATE payroll_monthly
            SET resident_tax_override=?,
                resident_tax_override_reason=?,
                resident_tax_applied=?,
                updated_at=datetime('now')
            WHERE payroll_id=?
            """,
            (override_amount, reason, override_amount, payroll_id),
        )
    conn.commit()


def upsert_emp_ins_rate(conn, start_month: str, employee_rate: float, employer_rate: float, note: str | None = None):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO employment_insurance_rates(start_month, employee_rate, employer_rate, note)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(start_month) DO UPDATE SET
          employee_rate=excluded.employee_rate,
          employer_rate=excluded.employer_rate,
          note=excluded.note,
          updated_at=datetime('now')
        """,
        (start_month, employee_rate, employer_rate, note),
    )
    conn.commit()

def list_emp_ins_rates(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM employment_insurance_rates ORDER BY start_month DESC")
    return cur.fetchall()

def delete_emp_ins_rate(conn, start_month: str):
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM employment_insurance_rates
        WHERE start_month = ?
        """,
        (start_month,),
    )
    conn.commit()

def get_emp_ins_rate_for_month(conn, target_month: str):
    """
    Find latest rate where start_month <= target_month.
    Returns (employee_rate, employer_rate). If none, (0,0)
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT employee_rate, employer_rate
        FROM employment_insurance_rates
        WHERE start_month <= ?
        ORDER BY start_month DESC
        LIMIT 1
        """,
        (target_month,),
    )
    row = cur.fetchone()
    if not row:
        return (0.0, 0.0)
    return (float(row["employee_rate"]), float(row["employer_rate"]))

def _calc_emp_ins_base_from_payroll_row(r, conn=None) -> int:
    """
    雇用保険の基礎賃金（まずは入力値ベースで簡易に）
    - 非課税交通費は除外
    - 自由支給は is_employment_base=1 のもののみ加算
    """
    if conn is not None and USE_DYNAMIC_ITEMS_FOR_EMPLOYMENT_INSURANCE:
        dynamic = get_dynamic_totals_for_payroll_row(conn, r)
        if dynamic["has_dynamic_items"]:
            return max(0, int(dynamic["employment_insurance_base"] or 0))

    base = 0

    # 固定支給（非課税交通費 제외）
    base += int(r["officer_pay"])
    base += int(r["base_salary"])
    base += int(r["deemed_ot"])
    base += int(r["overtime_pay"])
    base += int(r["special_allow"])
    # commute_nontax は除外

    # 自由支給（雇保対象フラグ）
    # マイナス防止
    if base < 0:
        base = 0

    return base

def apply_employment_insurance_auto(conn, target_month: str):
    """
    target_month の payroll_monthly 全行について雇用保険を自動計算して保存
    端数：切り捨て（floor）
    """
    emp_rate, er_rate = get_emp_ins_rate_for_month(conn, target_month)

    rows = get_payroll_rows(conn, target_month)
    cur = conn.cursor()

    for r in rows:
        hire_date = r["hire_date"] if "hire_date" in r.keys() else None
        leave_date = r["leave_date"] if "leave_date" in r.keys() else None
        wage_period_start = r["wage_period_start"] if "wage_period_start" in r.keys() else None
        wage_period_end = r["wage_period_end"] if "wage_period_end" in r.keys() else None

        applicable = has_employment_insurance_in_wage_period(
            hire_date,
            leave_date,
            wage_period_start,
            wage_period_end,
        )
        employment_target = int(row_get(r, "is_employment_insurance_target", 1) or 0) == 1

        if applicable and employment_target:
            base = _calc_emp_ins_base_from_payroll_row(r, conn)
            emp_amt = int(math.floor(base * emp_rate))
            er_amt = int(math.floor(base * er_rate))
        else:
            base = 0
            emp_amt = 0
            er_amt = 0

        cur.execute(
            """
            UPDATE payroll_monthly
            SET emp_ins_base=?,
                emp_ins_rate_employee=?,
                emp_ins_employee=?,
                emp_ins_rate_employer=?,
                emp_ins_employer=?,
                updated_at=datetime('now')
            WHERE payroll_id=?
            """,
            (base, emp_rate, emp_amt, er_rate, er_amt, r["payroll_id"]),
        )

    conn.commit()

def upsert_social_ins_rate(
    conn,
    start_month: str,
    prefecture_name: str,
    health_employee: float,
    pension_employee: float,
    care_employee: float = 0.0,
    childcare_employee: float = 0.0,
    childcare_employer: float = 0.0,
    childcare_contribution_employer: float = 0.0,
    note: str | None = None,
):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO social_insurance_rates_v2(
            start_month,
            prefecture_name,
            health_employee,
            pension_employee,
            care_employee,
            childcare_employee,
            childcare_employer,
            childcare_contribution_employer,
            note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(start_month, prefecture_name) DO UPDATE SET
          health_employee=excluded.health_employee,
          pension_employee=excluded.pension_employee,
          care_employee=excluded.care_employee,
          childcare_employee=excluded.childcare_employee,
          childcare_employer=excluded.childcare_employer,
          childcare_contribution_employer=excluded.childcare_contribution_employer,
          note=excluded.note,
          updated_at=datetime('now')
        """,
        (
            start_month,
            prefecture_name or "DEFAULT",
            health_employee,
            pension_employee,
            care_employee,
            childcare_employee,
            childcare_employer,
            childcare_contribution_employer,
            note,
        ),
    )
    conn.commit()

def list_social_ins_rates(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM social_insurance_rates_v2
        ORDER BY start_month DESC, prefecture_name ASC
        """
    )
    return cur.fetchall()

def delete_social_ins_rate(conn, start_month: str, prefecture_name: str):
    conn.execute(
        """
        DELETE FROM social_insurance_rates_v2
        WHERE start_month = ?
          AND prefecture_name = ?
        """,
        (start_month, prefecture_name or "DEFAULT"),
    )
    conn.commit()

def get_social_ins_rate_for_month(conn, target_month: str, prefecture_name: str = ""):
    pref = (prefecture_name or "").strip()

    cur = conn.cursor()

    if pref:
        cur.execute(
            """
            SELECT
                health_employee,
                pension_employee,
                care_employee,
                childcare_employee,
                childcare_employer,
                childcare_contribution_employer
            FROM social_insurance_rates_v2
            WHERE start_month <= ?
              AND prefecture_name = ?
            ORDER BY start_month DESC
            LIMIT 1
            """,
            (target_month, pref),
        )
        row = cur.fetchone()
        if row:
            return (
                float(row["health_employee"] or 0),
                float(row["pension_employee"] or 0),
                float(row["care_employee"] or 0),
                float(row["childcare_employee"] or 0),
                float(row["childcare_employer"] or 0),
                float(row["childcare_contribution_employer"] or 0),
            )

    # フォールバック: DEFAULT
    cur.execute(
        """
        SELECT
            health_employee,
            pension_employee,
            care_employee,
            childcare_employee,
            childcare_employer,
            childcare_contribution_employer
        FROM social_insurance_rates_v2
        WHERE start_month <= ?
          AND prefecture_name = 'DEFAULT'
        ORDER BY start_month DESC
        LIMIT 1
        """,
        (target_month,),
    )
    row = cur.fetchone()
    if row:
        return (
            float(row["health_employee"] or 0),
            float(row["pension_employee"] or 0),
            float(row["care_employee"] or 0),
            float(row["childcare_employee"] or 0),
            float(row["childcare_employer"] or 0),
            float(row["childcare_contribution_employer"] or 0),
        )

    return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

def apply_social_insurance_auto(conn, target_month: str):
    rows = get_payroll_rows(conn, target_month)
    cur = conn.cursor()

    for r in rows:
        pref = (r["work_prefecture_name"] or "").strip()
        h_rate, p_rate, c_rate, cc_emp_rate, cc_er_rate, cc_contrib_er_rate = get_social_ins_rate_for_month(
            conn, target_month, pref
        )

        std_health = int(r["std_monthly_wage"] or 0)
        std_pension_raw = int(r["std_pension_wage"] or 0) if r["std_pension_wage"] is not None else std_health
        std_pension = min(std_pension_raw, 650000)

        birth_date = r["birth_date"] if "birth_date" in r.keys() else None
        care_applicable = is_care_insurance_applicable(birth_date, target_month)

        hire_date = r["hire_date"] if "hire_date" in r.keys() else None
        leave_date = r["leave_date"] if "leave_date" in r.keys() else None

        enrolled = is_enrolled_at_month_end(hire_date, leave_date, target_month)

        social_target = int(row_get(r, "is_social_insurance_target", 0) or 0) == 1

        if enrolled and social_target:
            health = round_half_up(std_health * h_rate)
            care = round_half_up(std_health * c_rate) if (care_applicable and c_rate > 0) else 0
            childcare_emp = round_half_up(std_health * cc_emp_rate) if cc_emp_rate > 0 else 0
            childcare_er = round_down(std_health * cc_er_rate) if cc_er_rate > 0 else 0
            pension = round_half_up(std_pension * p_rate)
        else:
            health = 0
            care = 0
            childcare_emp = 0
            childcare_er = 0
            pension = 0

        emp_ins = int(r["emp_ins_employee"] or 0)

        social_total_legacy = health + pension + emp_ins
        social_total_calc = health + care + childcare_emp + pension + emp_ins

        cur.execute(
            """
            UPDATE payroll_monthly
            SET health_ins_employee=?,
                care_ins_employee=?,
                childcare_support_employee=?,
                childcare_support_employer=?,
                pension_ins_employee=?,
                social_ins_total3=?,
                social_ins_total_calc=?,
                updated_at=datetime('now')
            WHERE payroll_id=?
            """,
            (
                health,
                care,
                childcare_emp,
                childcare_er,
                pension,
                social_total_legacy,
                social_total_calc,
                r["payroll_id"],
            ),
        )

    conn.commit()

def _safe_sheet_title(s: str) -> str:
    # Excelシート名制限（31文字・禁止文字）対策
    s = re.sub(r'[\[\]\:\*\?\/\\]', "_", s)
    s = s.strip()
    if not s:
        s = "sheet"
    return s[:31]

def export_payroll_slips_excel(conn, target_month: str, file_path: str) -> None:
    """対象年月の給与明細を、1社員1シートのExcelブックとして出力する。"""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.page import PageMargins

    output_rows = get_payroll_output_data_for_month(conn, target_month)
    company = get_company_settings(conn)
    company_name = row_get(company, "company_name", "") if company else ""

    def fmt_year_month(value: str) -> str:
        text = str(value or "")
        try:
            y, m = text.split("-", 1)
            return f"{int(y):04d}年{int(m):02d}月"
        except Exception:
            return text

    def fmt_date(value: str) -> str:
        text = str(value or "")
        try:
            y, m, d = text.split("-", 2)
            return f"{int(y):04d}年{int(m):02d}月{int(d):02d}日"
        except Exception:
            return text

    def amount(value) -> int:
        return int(value or 0)

    def unique_sheet_title(base: str, used: set[str]) -> str:
        title = _safe_sheet_title(base)
        if title not in used:
            used.add(title)
            return title
        for idx in range(2, 1000):
            suffix = f"_{idx}"
            candidate = _safe_sheet_title(f"{title[:31 - len(suffix)]}{suffix}")
            if candidate not in used:
                used.add(candidate)
                return candidate
        raise ValueError("Excelシート名を一意にできませんでした。")

    def style_range(ws, min_row, max_row, min_col=1, max_col=8, border=None, font_name="Yu Gothic"):
        for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
            for cell in row:
                cell.font = cell.font.copy(name=font_name)
                cell.alignment = cell.alignment.copy(vertical="center")
                if border:
                    cell.border = border

    wb = Workbook()
    wb.remove(wb.active)

    used_titles: set[str] = set()
    thin_gray = Side(style="thin", color="B7C4CF")
    medium_blue = Side(style="medium", color="5E7D9A")
    border = Border(left=thin_gray, right=thin_gray, top=thin_gray, bottom=thin_gray)
    total_border = Border(left=thin_gray, right=thin_gray, top=medium_blue, bottom=thin_gray)
    fill_title = PatternFill("solid", fgColor="1F4E79")
    fill_section = PatternFill("solid", fgColor="D9EAF7")
    fill_header = PatternFill("solid", fgColor="EAF2F8")
    fill_total = PatternFill("solid", fgColor="FFF2CC")
    fill_net = PatternFill("solid", fgColor="D9EAD3")
    font_name = "Yu Gothic"

    if not output_rows:
        ws = wb.create_sheet(title=_safe_sheet_title("給与明細"))
        ws["A1"] = f"{fmt_year_month(target_month)} 給与明細"
        ws["A2"] = "対象データがありません。"
        wb.save(file_path)
        return

    for data in output_rows:
        sheet_title = unique_sheet_title(
            f"{data.get('employee_code', '')}_{data.get('employee_name', '')}",
            used_titles,
        )
        ws = wb.create_sheet(title=sheet_title)
        ws.sheet_view.showGridLines = False

        widths = [15, 13, 15, 13, 15, 13, 15, 13]
        for idx, width in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(idx)].width = width

        ws.merge_cells("A1:H1")
        title = ws["A1"]
        title.value = "給与明細"
        title.font = Font(name=font_name, bold=True, size=22, color="FFFFFF")
        title.fill = fill_title
        title.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 34

        ws.merge_cells("A2:H2")
        company_cell = ws["A2"]
        company_cell.value = company_name
        company_cell.font = Font(name=font_name, bold=True, size=12)
        company_cell.alignment = Alignment(horizontal="left", vertical="center")

        info = [
            ("対象年月", fmt_year_month(data.get("target_month", ""))),
            ("支給日", fmt_date(data.get("pay_date", ""))),
            ("社員番号", data.get("employee_code", "")),
            ("氏名", data.get("employee_name", "")),
            ("部署", data.get("department_name", "")),
            ("役職", data.get("position_name", "")),
            ("雇用区分", data.get("employment_type_name", "")),
        ]
        row_idx = 3
        for idx in range(0, len(info), 2):
            left = info[idx]
            right = info[idx + 1] if idx + 1 < len(info) else ("", "")
            ws.cell(row=row_idx, column=1, value=left[0]).fill = fill_header
            ws.cell(row=row_idx, column=2, value=left[1])
            ws.merge_cells(start_row=row_idx, start_column=2, end_row=row_idx, end_column=4)
            if right[0]:
                ws.cell(row=row_idx, column=5, value=right[0]).fill = fill_header
                ws.cell(row=row_idx, column=6, value=right[1])
                ws.merge_cells(start_row=row_idx, start_column=6, end_row=row_idx, end_column=8)
            row_idx += 1
        style_range(ws, 3, row_idx - 1, border=border, font_name=font_name)

        attendance = get_payroll_attendance(conn, int(data.get("payroll_id") or 0))
        row_idx += 1
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=8)
        section = ws.cell(row=row_idx, column=1, value="勤怠")
        section.font = Font(name=font_name, bold=True)
        section.fill = fill_section
        section.alignment = Alignment(horizontal="center", vertical="center")
        row_idx += 1

        attendance_start = row_idx
        for idx in range(0, len(WAGE_LEDGER_ATTENDANCE_FIELDS), 4):
            fields = WAGE_LEDGER_ATTENDANCE_FIELDS[idx:idx + 4]
            for block, (key, label) in enumerate(fields):
                label_col = block * 2 + 1
                value_col = label_col + 1
                ws.cell(row=row_idx, column=label_col, value=label).fill = fill_header
                value_cell = ws.cell(
                    row=row_idx,
                    column=value_col,
                    value=format_attendance_value_for_output(conn, key, attendance.get(key, 0)),
                )
                value_cell.alignment = Alignment(horizontal="center", vertical="center")
            row_idx += 1
        style_range(ws, attendance_start, row_idx - 1, border=border, font_name=font_name)

        row_idx += 1
        pay_header_row = row_idx
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=4)
        ws.merge_cells(start_row=row_idx, start_column=5, end_row=row_idx, end_column=8)
        ws.cell(row=row_idx, column=1, value="支給")
        ws.cell(row=row_idx, column=5, value="控除")
        for col in (1, 5):
            cell = ws.cell(row=row_idx, column=col)
            cell.font = Font(name=font_name, bold=True)
            cell.fill = fill_section
            cell.alignment = Alignment(horizontal="center", vertical="center")
        row_idx += 1

        ws.cell(row=row_idx, column=1, value="項目").fill = fill_header
        ws.cell(row=row_idx, column=2, value="金額").fill = fill_header
        ws.merge_cells(start_row=row_idx, start_column=2, end_row=row_idx, end_column=4)
        ws.cell(row=row_idx, column=5, value="項目").fill = fill_header
        ws.cell(row=row_idx, column=6, value="金額").fill = fill_header
        ws.merge_cells(start_row=row_idx, start_column=6, end_row=row_idx, end_column=8)
        row_idx += 1

        pay_items = list(data.get("pay_items") or [])
        deduction_items = list(data.get("system_deductions") or []) + list(data.get("deduction_items") or [])
        detail_rows = max(len(pay_items), len(deduction_items), 1)
        detail_start = row_idx
        for idx in range(detail_rows):
            if idx < len(pay_items):
                item = pay_items[idx]
                ws.cell(row=row_idx, column=1, value=item.get("name", ""))
                cell = ws.cell(row=row_idx, column=2, value=amount(item.get("amount")))
                ws.merge_cells(start_row=row_idx, start_column=2, end_row=row_idx, end_column=4)
                cell.number_format = '#,##0'
            if idx < len(deduction_items):
                item = deduction_items[idx]
                ws.cell(row=row_idx, column=5, value=item.get("name", ""))
                cell = ws.cell(row=row_idx, column=6, value=amount(item.get("amount")))
                ws.merge_cells(start_row=row_idx, start_column=6, end_row=row_idx, end_column=8)
                cell.number_format = '#,##0'
            row_idx += 1

        total_row = row_idx
        ws.cell(row=total_row, column=1, value="総支給額").font = Font(name=font_name, bold=True)
        pay_total_cell = ws.cell(row=total_row, column=2, value=amount(data.get("total_pay")))
        ws.merge_cells(start_row=total_row, start_column=2, end_row=total_row, end_column=4)
        pay_total_cell.number_format = '#,##0'
        pay_total_cell.font = Font(name=font_name, bold=True)
        ws.cell(row=total_row, column=5, value="控除合計").font = Font(name=font_name, bold=True)
        deduction_total_cell = ws.cell(row=total_row, column=6, value=amount(data.get("total_deduction")))
        ws.merge_cells(start_row=total_row, start_column=6, end_row=total_row, end_column=8)
        deduction_total_cell.number_format = '#,##0'
        deduction_total_cell.font = Font(name=font_name, bold=True)

        style_range(ws, pay_header_row, total_row, border=border, font_name=font_name)
        for row in ws.iter_rows(min_row=detail_start, max_row=total_row, min_col=2, max_col=8):
            for cell in row:
                if cell.column in {2, 6}:
                    cell.alignment = Alignment(horizontal="right", vertical="center")
        for col in range(1, 9):
            ws.cell(row=total_row, column=col).fill = fill_total
            ws.cell(row=total_row, column=col).border = total_border

        row_idx = total_row + 2
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=4)
        ws.merge_cells(start_row=row_idx, start_column=5, end_row=row_idx, end_column=8)
        ws.cell(row=row_idx, column=1, value="差引支給額").font = Font(name=font_name, bold=True, size=16)
        net_cell = ws.cell(row=row_idx, column=5, value=amount(data.get("net_pay")))
        net_cell.number_format = '#,##0 "円"'
        net_cell.font = Font(name=font_name, bold=True, size=18)
        net_cell.alignment = Alignment(horizontal="right", vertical="center")
        for col in range(1, 9):
            ws.cell(row=row_idx, column=col).fill = fill_net
            ws.cell(row=row_idx, column=col).border = total_border
        ws.row_dimensions[row_idx].height = 30

        note = data.get("note", "")
        if note:
            row_idx += 2
            ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=8)
            ws.cell(row=row_idx, column=1, value=f"備考: {note}")
            ws.cell(row=row_idx, column=1).alignment = Alignment(wrap_text=True, vertical="top")

        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=8):
            for cell in row:
                cell.font = cell.font.copy(name=font_name)
                if cell.value is not None and cell.alignment.horizontal is None:
                    cell.alignment = cell.alignment.copy(horizontal="left")

        ws.print_area = f"A1:H{ws.max_row}"
        ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 1
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_margins = PageMargins(left=0.25, right=0.25, top=0.35, bottom=0.35, header=0.1, footer=0.1)
        ws.print_options.horizontalCentered = True
        ws.print_options.verticalCentered = False

    wb.save(file_path)

def _export_pay_deduct_report_month_transposed(conn, target_month: str, file_path: str) -> None:
    output_rows = get_payroll_output_data_for_month(conn, target_month)

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "支給控除一覧"

    company = get_company_settings(conn)
    company_name = row_get(company, "company_name", "") if company else ""

    def item_key(item):
        return item.get("item_id") or item.get("code") or item.get("name")

    def collect_items(source_key: str):
        found = {}
        for data in output_rows:
            for item in data[source_key]:
                key = item_key(item)
                if key not in found:
                    found[key] = {
                        "key": key,
                        "name": item.get("name") or "",
                        "display_order": int(item.get("display_order") or 0),
                    }
        return sorted(found.values(), key=lambda x: (x["display_order"], x["name"]))

    pay_columns = collect_items("pay_items")
    deduction_columns = collect_items("deduction_items")
    system_columns = [
        {"key": "health_ins_employee", "name": "健康保険料"},
        {"key": "care_ins_employee", "name": "介護保険料"},
        {"key": "childcare_support_employee", "name": "子ども・子育て支援金"},
        {"key": "pension_ins_employee", "name": "厚生年金保険料"},
        {"key": "emp_ins_employee", "name": "雇用保険料"},
        {"key": "withholding_tax_applied", "name": "源泉所得税"},
        {"key": "resident_tax_applied", "name": "住民税"},
    ]

    title = f"{target_month} 支給控除一覧"
    if company_name:
        title = f"{company_name}　{title}"
    ws.cell(row=1, column=1, value=title).font = Font(bold=True, size=13)

    header_fill = PatternFill("solid", fgColor="D9EAF7")
    money_fill = PatternFill("solid", fgColor="F7F7F7")
    header_font = Font(bold=True)
    align_center = Alignment(horizontal="center", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    ws.append([])
    ws.append(["項目"] + [f"{data['employee_code']} {data['employee_name']}".strip() for data in output_rows])
    for cell in ws[3]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    def append_info_row(label: str, values: list):
        ws.append([label] + values)
        row_idx = ws.max_row
        ws.cell(row=row_idx, column=1).font = header_font
        for col_idx in range(1, ws.max_column + 1):
            ws.cell(row=row_idx, column=col_idx).alignment = align_left

    def append_money_row(label: str, values: list, bold: bool = False):
        ws.append([label] + values)
        row_idx = ws.max_row
        ws.cell(row=row_idx, column=1).alignment = align_left
        if bold:
            ws.cell(row=row_idx, column=1).font = header_font
        for col_idx in range(2, ws.max_column + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value is not None:
                cell.number_format = "#,##0"
            cell.alignment = align_right
            cell.fill = money_fill
            if bold:
                cell.font = header_font

    def item_amounts(source_key: str, key):
        values = []
        for data in output_rows:
            item_map = {item_key(item): int(item.get("amount") or 0) for item in data[source_key]}
            values.append(item_map.get(key, 0))
        return values

    append_info_row("社員番号", [data["employee_code"] for data in output_rows])
    append_info_row("氏名", [data["employee_name"] for data in output_rows])
    append_info_row("部署", [data["department_name"] for data in output_rows])
    append_info_row("役職", [data["position_name"] for data in output_rows])
    append_info_row("雇用区分", [data["employment_type_name"] for data in output_rows])

    append_money_row("【支給】", [None] * len(output_rows), bold=True)
    for col in pay_columns:
        append_money_row(col["name"], item_amounts("pay_items", col["key"]))
    append_money_row("総支給額", [data["total_pay"] for data in output_rows], bold=True)
    append_money_row("課税支給額", [data["taxable_pay"] for data in output_rows])
    append_money_row("非課税支給額", [data["non_taxable_pay"] for data in output_rows])
    append_money_row("雇用保険対象額", [data["employment_insurance_base"] for data in output_rows])
    append_money_row("社会保険対象額", [data["social_insurance_base"] for data in output_rows])

    append_money_row("【システム控除】", [None] * len(output_rows), bold=True)
    for col in system_columns:
        values = []
        for data in output_rows:
            system_map = {item.get("code"): int(item.get("amount") or 0) for item in data["system_deductions"]}
            values.append(system_map.get(col["key"], 0))
        append_money_row(col["name"], values)

    append_money_row("【会社独自控除】", [None] * len(output_rows), bold=True)
    for col in deduction_columns:
        append_money_row(col["name"], item_amounts("deduction_items", col["key"]))
    append_money_row("会社独自控除合計", [data["custom_deduction_total"] for data in output_rows], bold=True)
    append_money_row("システム控除合計", [data["system_deduction_total"] for data in output_rows], bold=True)
    append_money_row("控除合計", [data["total_deduction"] for data in output_rows], bold=True)
    append_money_row("差引支給額", [data["net_pay"] for data in output_rows], bold=True)

    ws.freeze_panes = "B4"
    ws.auto_filter.ref = ws.dimensions
    ws.column_dimensions["A"].width = 24
    for col_idx in range(2, ws.max_column + 1):
        header = ws.cell(row=3, column=col_idx).value or ""
        ws.column_dimensions[get_column_letter(col_idx)].width = max(14, min(24, len(str(header)) + 4))

    wb.save(file_path)

def _export_pay_deduct_report_month_by_department(conn, target_month: str, file_path: str) -> None:
    output_rows = get_payroll_output_data_for_month(conn, target_month)

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)

    company = get_company_settings(conn)
    company_name = row_get(company, "company_name", "") if company else ""

    def item_key(item):
        return item.get("item_id") or item.get("code") or item.get("name")

    def collect_items(source_key: str):
        found = {}
        for data in output_rows:
            for item in data[source_key]:
                key = item_key(item)
                if key not in found:
                    found[key] = {
                        "key": key,
                        "name": item.get("name") or "",
                        "display_order": int(item.get("display_order") or 0),
                    }
        return sorted(found.values(), key=lambda x: (x["display_order"], x["name"]))

    pay_columns = collect_items("pay_items")
    deduction_columns = collect_items("deduction_items")
    system_columns = [
        {"key": "health_ins_employee", "name": "健康保険料"},
        {"key": "care_ins_employee", "name": "介護保険料"},
        {"key": "childcare_support_employee", "name": "子ども・子育て支援金"},
        {"key": "pension_ins_employee", "name": "厚生年金保険料"},
        {"key": "emp_ins_employee", "name": "雇用保険料"},
        {"key": "withholding_tax_applied", "name": "源泉所得税"},
        {"key": "resident_tax_applied", "name": "住民税"},
    ]

    header_fill = PatternFill("solid", fgColor="D9EAF7")
    money_fill = PatternFill("solid", fgColor="F7F7F7")
    subtotal_fill = PatternFill("solid", fgColor="FFF2CC")
    header_font = Font(bold=True)
    title_font = Font(bold=True, size=13)
    align_center = Alignment(horizontal="center", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    def item_amounts(rows: list[dict], source_key: str, key):
        values = []
        for data in rows:
            item_map = {item_key(item): int(item.get("amount") or 0) for item in data[source_key]}
            values.append(item_map.get(key, 0))
        return values

    def append_info_row(ws, label: str, values: list):
        ws.append([label] + values + [""])
        row_idx = ws.max_row
        ws.cell(row=row_idx, column=1).font = header_font
        for col_idx in range(1, ws.max_column + 1):
            ws.cell(row=row_idx, column=col_idx).alignment = align_left

    def append_money_row(ws, label: str, values: list, bold: bool = False):
        total = sum(int(v or 0) for v in values)
        ws.append([label] + values + [total])
        row_idx = ws.max_row
        ws.cell(row=row_idx, column=1).alignment = align_left
        if bold:
            ws.cell(row=row_idx, column=1).font = header_font
        for col_idx in range(2, ws.max_column + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value is not None:
                cell.number_format = "#,##0"
            cell.alignment = align_right
            cell.fill = subtotal_fill if bold else money_fill
            if bold:
                cell.font = header_font

    def build_sheet(sheet_title: str, rows: list[dict]):
        ws = wb.create_sheet(title=_safe_sheet_title(sheet_title))
        title = f"{target_month} 支給控除一覧"
        if sheet_title != "\u5168\u793e":
            title = f"{title}（{sheet_title}）"
        if company_name:
            title = f"{company_name}　{title}"
        ws.cell(row=1, column=1, value=title).font = title_font

        ws.append([])
        ws.append(["\u9805\u76ee"] + [f"{data['employee_code']} {data['employee_name']}".strip() for data in rows] + ["\u5408\u8a08"])
        for cell in ws[3]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center

        append_info_row(ws, "社員番号", [data["employee_code"] for data in rows])
        append_info_row(ws, "氏名", [data["employee_name"] for data in rows])
        append_info_row(ws, "部署", [data["department_name"] for data in rows])
        append_info_row(ws, "役職", [data["position_name"] for data in rows])
        append_info_row(ws, "雇用区分", [data["employment_type_name"] for data in rows])

        append_money_row(ws, "【支給】", [0] * len(rows), bold=True)
        for col in pay_columns:
            append_money_row(ws, col["name"], item_amounts(rows, "pay_items", col["key"]))
        append_money_row(ws, "総支給額", [data["total_pay"] for data in rows], bold=True)
        append_money_row(ws, "課税支給額", [data["taxable_pay"] for data in rows])
        append_money_row(ws, "非課税支給額", [data["non_taxable_pay"] for data in rows])
        append_money_row(ws, "雇用保険対象額", [data["employment_insurance_base"] for data in rows])
        append_money_row(ws, "社会保険対象額", [data["social_insurance_base"] for data in rows])

        append_money_row(ws, "【システム控除】", [0] * len(rows), bold=True)
        for col in system_columns:
            values = []
            for data in rows:
                system_map = {item.get("code"): int(item.get("amount") or 0) for item in data["system_deductions"]}
                values.append(system_map.get(col["key"], 0))
            append_money_row(ws, col["name"], values)

        append_money_row(ws, "【会社独自控除】", [0] * len(rows), bold=True)
        for col in deduction_columns:
            append_money_row(ws, col["name"], item_amounts(rows, "deduction_items", col["key"]))
        append_money_row(ws, "会社独自控除合計", [data["custom_deduction_total"] for data in rows], bold=True)
        append_money_row(ws, "システム控除合計", [data["system_deduction_total"] for data in rows], bold=True)
        append_money_row(ws, "控除合計", [data["total_deduction"] for data in rows], bold=True)
        append_money_row(ws, "差引支給額", [data["net_pay"] for data in rows], bold=True)

        ws.freeze_panes = "B4"
        ws.auto_filter.ref = ws.dimensions
        ws.column_dimensions["A"].width = 24
        for col_idx in range(2, ws.max_column + 1):
            header = ws.cell(row=3, column=col_idx).value or ""
            ws.column_dimensions[get_column_letter(col_idx)].width = max(14, min(24, len(str(header)) + 4))

    build_sheet("\u5168\u793e", output_rows)

    departments = {}
    for data in output_rows:
        key = (data.get("department_name") or "\u90e8\u7f72\u672a\u8a2d\u5b9a").strip() or "\u90e8\u7f72\u672a\u8a2d\u5b9a"
        departments.setdefault(key, []).append(data)
    for dept_name in sorted(departments):
        build_sheet(dept_name, departments[dept_name])

    wb.save(file_path)


def export_pay_deduct_report_month(conn, target_month: str, file_path: str) -> None:
    """
    支給控除一覧表（対象月・全社員）を縦並びでExcel出力。
    見せ方B:
      健康保険料（介護保険料）→ 子ども・子育て支援金 → 厚生年金保険料 → 雇用保険料
    """
    return _export_pay_deduct_report_month_by_department(conn, target_month, file_path)

    output_rows = get_payroll_output_data_for_month(conn, target_month)

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "動的支給控除一覧"

    company = get_company_settings(conn)
    company_name = row_get(company, "company_name", "") if company else ""

    def item_key(item):
        return item.get("item_id") or item.get("code") or item.get("name")

    def collect_items(source_key: str):
        found = {}
        for data in output_rows:
            for item in data[source_key]:
                key = item_key(item)
                if key not in found:
                    found[key] = {
                        "key": key,
                        "name": item.get("name") or "",
                        "display_order": int(item.get("display_order") or 0),
                    }
        return sorted(found.values(), key=lambda x: (x["display_order"], x["name"]))

    pay_columns = collect_items("pay_items")
    deduction_columns = collect_items("deduction_items")
    system_columns = [
        {"key": "health_ins_employee", "name": "健康保険料"},
        {"key": "care_ins_employee", "name": "介護保険料"},
        {"key": "childcare_support_employee", "name": "子ども・子育て支援金"},
        {"key": "pension_ins_employee", "name": "厚生年金保険料"},
        {"key": "emp_ins_employee", "name": "雇用保険料"},
        {"key": "withholding_tax_applied", "name": "源泉所得税"},
        {"key": "resident_tax_applied", "name": "住民税"},
    ]

    title = f"{target_month} 支給控除一覧"
    if company_name:
        title = f"{company_name}　{title}"
    ws.cell(row=1, column=1, value=title).font = Font(bold=True, size=13)

    headers = ["社員番号", "氏名", "部署", "役職", "雇用区分"]
    headers += [c["name"] for c in pay_columns]
    headers += ["総支給額", "課税支給額", "非課税支給額", "雇用保険対象額", "社会保険対象額"]
    headers += [c["name"] for c in system_columns]
    headers += [c["name"] for c in deduction_columns]
    headers += ["会社独自控除合計", "システム控除合計", "控除合計", "差引支給額"]
    ws.append([])
    ws.append(headers)

    header_fill = PatternFill("solid", fgColor="D9EAF7")
    money_fill = PatternFill("solid", fgColor="F7F7F7")
    header_font = Font(bold=True)
    align_center = Alignment(horizontal="center", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    for cell in ws[3]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    for data in output_rows:
        pay_map = {item_key(item): int(item.get("amount") or 0) for item in data["pay_items"]}
        deduction_map = {item_key(item): int(item.get("amount") or 0) for item in data["deduction_items"]}
        system_map = {item.get("code"): int(item.get("amount") or 0) for item in data["system_deductions"]}
        row = [
            data["employee_code"],
            data["employee_name"],
            data["department_name"],
            data["position_name"],
            data["employment_type_name"],
        ]
        row += [pay_map.get(c["key"], 0) for c in pay_columns]
        row += [
            data["total_pay"],
            data["taxable_pay"],
            data["non_taxable_pay"],
            data["employment_insurance_base"],
            data["social_insurance_base"],
        ]
        row += [system_map.get(c["key"], 0) for c in system_columns]
        row += [deduction_map.get(c["key"], 0) for c in deduction_columns]
        row += [
            data["custom_deduction_total"],
            data["system_deduction_total"],
            data["total_deduction"],
            data["net_pay"],
        ]
        ws.append(row)

    for row in ws.iter_rows(min_row=4, max_row=ws.max_row):
        for idx, cell in enumerate(row, start=1):
            if idx >= 6:
                cell.number_format = "#,##0"
                cell.alignment = align_right
                cell.fill = money_fill
            else:
                cell.alignment = align_left

    ws.freeze_panes = "F4"
    ws.auto_filter.ref = ws.dimensions
    for col_idx in range(1, ws.max_column + 1):
        header = ws.cell(row=3, column=col_idx).value or ""
        width = max(10, min(24, len(str(header)) + 4))
        if col_idx <= 5:
            width = max(width, 14)
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    slip_ws = wb.create_sheet("給与明細")
    current_row = 1
    for data in output_rows:
        slip_title = f"{data['target_month']} 給与明細　{data['employee_code']}　{data['employee_name']}"
        if company_name:
            slip_title = f"{company_name}　{slip_title}"
        slip_ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=4)
        slip_ws.cell(row=current_row, column=1, value=slip_title).font = Font(bold=True, size=12)
        current_row += 1
        slip_ws.cell(row=current_row, column=1, value="部署")
        slip_ws.cell(row=current_row, column=2, value=data["department_name"])
        slip_ws.cell(row=current_row, column=3, value="支給日")
        slip_ws.cell(row=current_row, column=4, value=data["pay_date"])
        current_row += 2
        for col, label in enumerate(["支給", "金額", "控除", "金額"], start=1):
            cell = slip_ws.cell(row=current_row, column=col, value=label)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = align_center
        current_row += 1

        pay_items = data["pay_items"] + [{"name": "総支給額", "amount": data["total_pay"]}]
        deduct_items = data["system_deductions"] + data["deduction_items"] + [{"name": "控除合計", "amount": data["total_deduction"]}]
        for i in range(max(len(pay_items), len(deduct_items))):
            if i < len(pay_items):
                slip_ws.cell(row=current_row, column=1, value=pay_items[i]["name"])
                cell = slip_ws.cell(row=current_row, column=2, value=int(pay_items[i]["amount"] or 0))
                cell.number_format = "#,##0"
                cell.alignment = align_right
            if i < len(deduct_items):
                slip_ws.cell(row=current_row, column=3, value=deduct_items[i]["name"])
                cell = slip_ws.cell(row=current_row, column=4, value=int(deduct_items[i]["amount"] or 0))
                cell.number_format = "#,##0"
                cell.alignment = align_right
            current_row += 1
        slip_ws.cell(row=current_row, column=3, value="差引支給額").font = header_font
        cell = slip_ws.cell(row=current_row, column=4, value=data["net_pay"])
        cell.font = header_font
        cell.number_format = "#,##0"
        cell.alignment = align_right
        current_row += 3

    for col_idx, width in enumerate([24, 14, 24, 14], start=1):
        slip_ws.column_dimensions[get_column_letter(col_idx)].width = width

    wb.save(file_path)
    return

    rows = get_payroll_rows(conn, target_month)

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment

    wb = Workbook()
    ws = wb.active
    ws.title = f"支給控除一覧_{target_month}"

    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 18

    font_h1 = Font(bold=True, size=12)
    font_h2 = Font(bold=True)
    align_l = Alignment(horizontal="left", vertical="center")
    align_r = Alignment(horizontal="right", vertical="center")
    align_c = Alignment(horizontal="center", vertical="center")

    r0 = 1

    def write_money(row, col, val):
        cell = ws.cell(row=row, column=col, value=int(val or 0))
        cell.number_format = "#,##0"
        cell.alignment = align_r

    def write_text(row, col, val, bold=False, center=False):
        cell = ws.cell(row=row, column=col, value=val)
        cell.alignment = align_c if center else align_l
        if bold:
            cell.font = font_h2

    for r in rows:
        emp_code = row_get(r, "employee_code", "")
        name = row_get(r, "name_kanji", "")
        dept = row_get(r, "department", "")
        payday_group = row_get(r, "payday_group", "")

        title = f"{target_month}　{emp_code}　{name}（{dept}） 支払日区分:{payday_group}"
        ws.merge_cells(start_row=r0, start_column=1, end_row=r0, end_column=4)
        c = ws.cell(row=r0, column=1, value=title)
        c.font = font_h1
        c.alignment = align_l
        r0 += 1

        # 支給部
        write_text(r0, 1, "【支給】", bold=True)
        write_text(r0, 2, "項目", bold=True, center=True)
        write_text(r0, 3, "金額", bold=True, center=True)
        r0 += 1

        pay_items = [
            ("基本給", row_get(r, "base_salary", 0)),
            ("役員報酬", row_get(r, "officer_pay", 0)),
            ("手当", row_get(r, "special_allow", 0)),
            ("残業(みなし)", row_get(r, "deemed_ot", 0)),
            ("残業", row_get(r, "overtime_pay", 0)),
            ("非課税通勤", row_get(r, "commute_nontax", 0)),
        ]
        for label, val in pay_items:
            write_text(r0, 2, label)
            write_money(r0, 3, val)
            r0 += 1

        gross = _calc_gross_pay_from_payroll_row(r)
        write_text(r0, 2, "総支給", bold=True)
        write_money(r0, 3, gross)
        r0 += 2

        # 控除部
        write_text(r0, 1, "【控除】", bold=True)
        write_text(r0, 2, "項目", bold=True, center=True)
        write_text(r0, 3, "金額", bold=True, center=True)
        r0 += 1

        deduct_items = [
            ("健康保険料（介護保険料）", _health_care_display_amount(r)),
            ("子ども・子育て支援金", row_get(r, "childcare_support_employee", 0)),
            ("厚生年金保険料", row_get(r, "pension_ins_employee", 0)),
            ("雇用保険料", row_get(r, "emp_ins_employee", 0)),
            ("所得税", row_get(r, "withholding_tax_applied", 0)),
            ("住民税", row_get(r, "resident_tax_applied", 0)),
        ]
        for label, val in deduct_items:
            write_text(r0, 2, label)
            write_money(r0, 3, val)
            r0 += 1

        deduct_total = (
            _health_care_display_amount(r)
            + int(row_get(r, "childcare_support_employee", 0) or 0)
            + int(row_get(r, "pension_ins_employee", 0) or 0)
            + int(row_get(r, "emp_ins_employee", 0) or 0)
            + int(row_get(r, "withholding_tax_applied", 0) or 0)
            + int(row_get(r, "resident_tax_applied", 0) or 0)
            + _other_deductions_total(r)
        )
        write_text(r0, 2, "控除合計", bold=True)
        write_money(r0, 3, deduct_total)
        r0 += 1

        write_text(r0, 2, "差引支給額", bold=True)
        write_money(r0, 3, gross - deduct_total)
        r0 += 3

    wb.save(file_path)

def _health_care_display_amount(row) -> int:
    """見せ方B用: 健康保険料（介護保険料）を合算表示する。"""
    health = int(row_get(row, "health_ins_employee", 0) or 0)
    care = int(row_get(row, "care_ins_employee", 0) or 0)
    return health + care

def _calc_gross_pay_from_payroll_row(row) -> int:
    """給与1行から総支給額を計算する。"""
    return (
        int(row_get(row, "base_salary", 0) or 0)
        + int(row_get(row, "officer_pay", 0) or 0)
        + int(row_get(row, "special_allow", 0) or 0)
        + int(row_get(row, "deemed_ot", 0) or 0)
        + int(row_get(row, "overtime_pay", 0) or 0)
        + int(row_get(row, "commute_nontax", 0) or 0)
    )

def _other_deductions_total(row) -> int:
    """法定控除以外の控除合計。"""
    return 0

def export_wage_ledger_excel(conn, target_month: str, file_path: str) -> None:
    """賃金台帳（月単位）をExcel出力する。旧固定自由項目は出力しない。"""
    rows = get_payroll_rows(conn, target_month)

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = f"賃金台帳_{target_month}"

    headers = [
        "対象年月", "支払日",
        "社員番号", "氏名", "部署",
        "基本給", "役員報酬", "手当", "残業(みなし)", "残業", "非課税通勤",
        "総支給",
        "健康保険料(介護保険料含む)", "子ども・子育て支援金", "厚生年金保険料", "雇用保険料",
        "所得税", "住民税",
        "控除合計", "差引支給額",
        "備考",
    ]

    attendance_headers = [label for _key, label in WAGE_LEDGER_ATTENDANCE_FIELDS]
    headers = headers[:5] + attendance_headers + headers[5:]

    ws.append(headers)

    header_font = Font(bold=True)
    align_center = Alignment(horizontal="center", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = header_font
        cell.alignment = align_center

    for r in rows:
        gross = _calc_gross_pay_from_payroll_row(r)

        health_care = _health_care_display_amount(r)
        childcare = int(row_get(r, "childcare_support_employee", 0) or 0)
        pension = int(row_get(r, "pension_ins_employee", 0) or 0)
        emp_ins = int(row_get(r, "emp_ins_employee", 0) or 0)
        withholding_tax = int(row_get(r, "withholding_tax_applied", 0) or 0)
        resident_tax = int(row_get(r, "resident_tax_applied", 0) or 0)

        deduct_total = health_care + childcare + pension + emp_ins + withholding_tax + resident_tax
        net = gross - deduct_total
        attendance = get_payroll_attendance(conn, int(row_get(r, "payroll_id", 0) or 0))
        attendance_values = [
            format_attendance_value_for_output(conn, key, attendance.get(key, 0))
            for key, _label in WAGE_LEDGER_ATTENDANCE_FIELDS
        ]

        data = [
            row_get(r, "target_month", ""),
            row_get(r, "pay_date_applied", ""),
            row_get(r, "employee_code", ""),
            row_get(r, "name_kanji", ""),
            row_get(r, "department", ""),
            int(row_get(r, "base_salary", 0) or 0),
            int(row_get(r, "officer_pay", 0) or 0),
            int(row_get(r, "special_allow", 0) or 0),
            int(row_get(r, "deemed_ot", 0) or 0),
            int(row_get(r, "overtime_pay", 0) or 0),
            int(row_get(r, "commute_nontax", 0) or 0),
            gross,
            health_care,
            childcare,
            pension,
            emp_ins,
            withholding_tax,
            resident_tax,
            deduct_total,
            net,
            row_get(r, "note", ""),
        ]
        data = data[:5] + attendance_values + data[5:]
        ws.append(data)

    money_headers = {
        "基本給", "役員報酬", "手当", "残業(みなし)", "残業", "非課税通勤",
        "総支給",
        "健康保険料(介護保険料含む)", "子ども・子育て支援金", "厚生年金保険料", "雇用保険料",
        "所得税", "住民税",
        "控除合計", "差引支給額",
    }
    money_cols_idx = [i for i, h in enumerate(headers, start=1) if h in money_headers]

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for ci in money_cols_idx:
            cell = row[ci - 1]
            cell.number_format = "#,##0"
            cell.alignment = align_right

    text_cols_idx = [1, 2, 3, 4, 5, len(headers)]
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for ci in text_cols_idx:
            row[ci - 1].alignment = align_left

    widths = {
        1: 10, 2: 12, 3: 12, 4: 14, 5: 14,
        6: 12, 7: 12, 8: 12, 9: 12, 10: 12, 11: 12,
        12: 12,
        13: 20, 14: 16, 15: 16, 16: 12,
        17: 12, 18: 12,
        19: 12, 20: 12, 21: 24,
    }
    for ci, w in widths.items():
        ws.column_dimensions[get_column_letter(ci)].width = w

    wb.save(file_path)
def _export_wage_ledger_year_with_totals(conn, year: int, file_path: str, basis: str = "target") -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    cur = conn.cursor()
    cur.execute(
        """
        SELECT employee_id, employee_code, name_kanji, department
        FROM employees
        ORDER BY employee_id
        """
    )
    emps = cur.fetchall()

    monthly_rows = []
    if basis == "paydate":
        cur.execute(
            """
            SELECT p.*,
                   e.employee_code,
                   e.name_kanji,
                   e.department,
                   e.department_id,
                   e.payment_schedule_id,
                   e.std_monthly_wage,
                   e.std_pension_wage,
                   e.birth_date
            FROM payroll_monthly p
            JOIN employees e ON e.employee_id = p.employee_id
            WHERE substr(p.pay_date_applied, 1, 4) = ?
            ORDER BY p.pay_date_applied, p.target_month
            """,
            (str(year),),
        )
        monthly_rows = [_row_with_current_department_name(conn, r) for r in cur.fetchall()]
    else:
        for month in range(1, 13):
            monthly_rows.extend(get_payroll_rows(conn, f"{year:04d}-{month:02d}"))

    by_emp_month = {}
    for r in monthly_rows:
        month_source = row_get(r, "pay_date_applied", "") if basis == "paydate" else row_get(r, "target_month", "")
        try:
            mm = int(str(month_source).split("-")[1])
        except Exception:
            continue
        by_emp_month.setdefault((int(row_get(r, "employee_id", 0) or 0), mm), []).append(r)

    bonus_year_column = "pay_date" if basis == "paydate" else "target_month"
    cur.execute(
        f"""
        SELECT *
        FROM payroll_bonus
        WHERE substr({bonus_year_column}, 1, 4) = ?
        ORDER BY {bonus_year_column}, pay_date
        """,
        (str(year),),
    )
    by_emp_bonus = {}
    for r in cur.fetchall():
        bonus_month_source = row_get(r, "pay_date", "") if basis == "paydate" else row_get(r, "target_month", "")
        try:
            mm = int(str(bonus_month_source).split("-")[1])
        except Exception:
            mm = 0
        by_emp_bonus.setdefault(int(row_get(r, "employee_id", 0) or 0), []).append((mm, r))

    wb = Workbook()
    wb.remove(wb.active)

    font_h1 = Font(bold=True, size=12)
    font_head = Font(bold=True)
    fill_subtotal = PatternFill("solid", fgColor="FFF2CC")
    fill_total = PatternFill("solid", fgColor="D9EAD3")
    align_l = Alignment(horizontal="left", vertical="center")
    align_c = Alignment(horizontal="center", vertical="center")
    align_r = Alignment(horizontal="right", vertical="center")

    headers = [
        "月", "基本給", "役員報酬", "特別手当", "みなし残業", "残業", "非課税通勤",
        "自由支給合計", "総支給", "健康・介護", "子ども・子育て", "厚生年金", "雇用保険",
        "源泉所得税", "住民税", "その他控除", "控除合計", "差引支給額",
    ]
    attendance_fields = WAGE_LEDGER_ATTENDANCE_FIELDS
    attendance_headers = [label for _key, label in attendance_fields]
    headers = headers[:1] + attendance_headers + headers[1:]
    attendance_len = len(attendance_fields)
    fixed_codes = {"base_salary", "officer_pay", "special_allow", "deemed_ot", "overtime_pay", "commute_nontax"}

    def pay_amount(data, code):
        for item in data["pay_items"]:
            if item.get("code") == code:
                return int(item.get("amount") or 0)
        return 0

    def monthly_values(r):
        if r is None:
            return [0] * (len(headers) - 1)
        data = build_payroll_output_data(conn, r)
        free_pay_total = sum(int(item.get("amount") or 0) for item in data["pay_items"] if item.get("code") not in fixed_codes)
        attendance = get_payroll_attendance(conn, int(row_get(r, "payroll_id", 0) or 0))
        attendance_values = [attendance.get(key, 0) or 0 for key, _label in attendance_fields]
        return attendance_values + [
            pay_amount(data, "base_salary"),
            pay_amount(data, "officer_pay"),
            pay_amount(data, "special_allow"),
            pay_amount(data, "deemed_ot"),
            pay_amount(data, "overtime_pay"),
            pay_amount(data, "commute_nontax"),
            free_pay_total,
            data["total_pay"],
            data["health_insurance"] + data["nursing_care_insurance"],
            data["child_care_contribution"],
            data["pension_insurance"],
            data["employment_insurance"],
            data["income_tax"],
            data["resident_tax"],
            data["custom_deduction_total"],
            data["total_deduction"],
            data["net_pay"],
        ]

    def monthly_values_for_rows(rows):
        if not rows:
            return [0] * (len(headers) - 1)
        return sum_rows([monthly_values(r) for r in rows])

    def bonus_values(r):
        bonus_amount = int(row_get(r, "bonus_amount", 0) or 0)
        health_care = int(row_get(r, "health_ins_employee", 0) or 0) + int(row_get(r, "care_ins_employee", 0) or 0)
        childcare = int(row_get(r, "childcare_support_employee", 0) or 0)
        pension = int(row_get(r, "pension_ins_employee", 0) or 0)
        emp_ins = int(row_get(r, "emp_ins_employee", 0) or 0)
        withholding = int(row_get(r, "withholding_tax_applied", 0) or 0)
        deduct_total = health_care + childcare + pension + emp_ins + withholding
        net = bonus_amount - deduct_total
        return [0] * attendance_len + [0, 0, 0, 0, 0, 0, 0, bonus_amount, health_care, childcare, pension, emp_ins, withholding, 0, 0, deduct_total, net]

    def sum_rows(rows):
        if not rows:
            return [0] * (len(headers) - 1)
        return [sum(row[i] for row in rows) for i in range(len(headers) - 1)]

    def employee_department_for_ledger(employee_id, employee_row):
        for mm in range(1, 13):
            for payroll_row in by_emp_month.get((employee_id, mm), []) or []:
                department = row_get(payroll_row, "department", "")
                if department:
                    return department
        return row_get(employee_row, "department", "")

    def write_row(ws, row_idx, label, values, fill=None, bold=False):
        cell = ws.cell(row=row_idx, column=1, value=label)
        cell.alignment = align_c
        if bold:
            cell.font = font_head
        if fill:
            cell.fill = fill
        for ci, val in enumerate(values, start=2):
            if ci <= 1 + attendance_len:
                key = attendance_fields[ci - 2][0]
                cell = ws.cell(row=row_idx, column=ci, value=format_attendance_value_for_output(conn, key, val))
                cell.alignment = align_r
            else:
                cell = ws.cell(row=row_idx, column=ci, value=val)
                cell.number_format = "#,##0"
                cell.alignment = align_r
            if bold:
                cell.font = font_head
            if fill:
                cell.fill = fill

    for e in emps:
        emp_id = int(row_get(e, "employee_id", 0) or 0)
        emp_code = row_get(e, "employee_code", "")
        name = row_get(e, "name_kanji", "")
        dept = employee_department_for_ledger(emp_id, e)
        ws = wb.create_sheet(title=_safe_sheet_title(f"{emp_code}_{name}"))

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        title_cell = ws.cell(row=1, column=1, value=f"賃金台帳（年次） {year}年　{emp_code}　{name}（{dept}）")
        title_cell.font = font_h1
        title_cell.alignment = align_l

        for i, h in enumerate(headers, start=1):
            cell = ws.cell(row=3, column=i, value=h)
            cell.font = font_head
            cell.alignment = align_c

        out_row = 4
        monthly_value_rows = []
        for mm in range(1, 13):
            values = monthly_values_for_rows(by_emp_month.get((emp_id, mm)))
            monthly_value_rows.append(values)
            write_row(ws, out_row, mm, values)
            out_row += 1

        monthly_subtotal = sum_rows(monthly_value_rows)
        write_row(ws, out_row, "給与小計", monthly_subtotal, fill=fill_subtotal, bold=True)
        out_row += 2

        bonus_value_rows = []
        for idx, (mm, bonus_row) in enumerate(by_emp_bonus.get(emp_id, []), start=1):
            values = bonus_values(bonus_row)
            bonus_value_rows.append(values)
            write_row(ws, out_row, f"賞与{idx}({mm}月)", values)
            out_row += 1

        bonus_subtotal = sum_rows(bonus_value_rows)
        write_row(ws, out_row, "賞与小計", bonus_subtotal, fill=fill_subtotal, bold=True)
        out_row += 1

        grand_total = [monthly_subtotal[i] + bonus_subtotal[i] for i in range(len(monthly_subtotal))]
        write_row(ws, out_row, "合計", grand_total, fill=fill_total, bold=True)

        ws.column_dimensions["A"].width = 12
        for i in range(2, len(headers) + 1):
            ws.column_dimensions[get_column_letter(i)].width = 14
        ws.freeze_panes = "B4"

    wb.save(file_path)


def export_wage_ledger_year(conn, year: int, file_path: str, basis: str = "target") -> None:
    return _export_wage_ledger_year_with_totals(conn, year, file_path, basis=basis)
    """
    賃金台帳（年次）を社員ごとにシート分けしてExcel出力する。
    見せ方B:
      健康保険料（介護保険料）→ 子ども・子育て支援金 → 厚生年金保険料 → 雇用保険料
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    from openpyxl.utils import get_column_letter

    cur = conn.cursor()

    cur.execute(
        """
        SELECT employee_id, employee_code, name_kanji, department
        FROM employees
        ORDER BY employee_id
        """
    )
    emps = cur.fetchall()

    y_prefix = f"{year:04d}-"
    cur.execute(
        """
        SELECT p.*,
               e.employee_code, e.name_kanji, e.department
        FROM payroll_monthly p
        JOIN employees e ON e.employee_id = p.employee_id
        WHERE p.target_month LIKE ?
        """,
        (y_prefix + "%",),
    )
    rows = cur.fetchall()

    by_emp_month = {}
    for r in rows:
        tm = row_get(r, "target_month", "")
        try:
            mm = int(tm.split("-")[1])
        except Exception:
            continue
        by_emp_month[(int(row_get(r, "employee_id", 0)), mm)] = r

    wb = Workbook()
    wb.remove(wb.active)

    font_h1 = Font(bold=True, size=12)
    font_head = Font(bold=True)
    align_l = Alignment(horizontal="left", vertical="center")
    align_c = Alignment(horizontal="center", vertical="center")
    align_r = Alignment(horizontal="right", vertical="center")

    headers = [
        "月",
        "基本給", "役員報酬", "手当", "残業(みなし)", "残業", "非課税通勤",
        "総支給",
        "健康保険料（介護保険料）", "子ども・子育て支援金", "厚生年金保険料", "雇用保険料",
        "所得税", "住民税",
        "その他控除",
        "控除合計",
        "差引支給額",
    ]

    money_cols = set(range(2, len(headers) + 1))

    for e in emps:
        emp_id = int(row_get(e, "employee_id", 0))
        emp_code = row_get(e, "employee_code", "")
        name = row_get(e, "name_kanji", "")
        dept = row_get(e, "department", "")

        title = _safe_sheet_title(f"{emp_code}_{name}")
        ws = wb.create_sheet(title=title)

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        c = ws.cell(row=1, column=1, value=f"賃金台帳（年次） {year}年　{emp_code}　{name}（{dept}）")
        c.font = font_h1
        c.alignment = align_l

        for i, h in enumerate(headers, start=1):
            cell = ws.cell(row=3, column=i, value=h)
            cell.font = font_head
            cell.alignment = align_c

        ws.column_dimensions["A"].width = 5
        for i in range(2, len(headers) + 1):
            ws.column_dimensions[get_column_letter(i)].width = 14

        out_row = 4
        for mm in range(1, 13):
            r = by_emp_month.get((emp_id, mm))

            if r is None:
                values = [mm] + [0] * (len(headers) - 1)
            else:
                gross = _calc_gross_pay_from_payroll_row(r)

                health_care = _health_care_display_amount(r)
                childcare = int(row_get(r, "childcare_support_employee", 0) or 0)
                pension = int(row_get(r, "pension_ins_employee", 0) or 0)
                emp_ins = int(row_get(r, "emp_ins_employee", 0) or 0)
                withholding_tax = int(row_get(r, "withholding_tax_applied", 0) or 0)
                resident_tax = int(row_get(r, "resident_tax_applied", 0) or 0)
                other_deduct = _other_deductions_total(r)

                deduct_total = (
                    health_care
                    + childcare
                    + pension
                    + emp_ins
                    + withholding_tax
                    + resident_tax
                    + other_deduct
                )

                net = gross - deduct_total

                values = [
                    mm,
                    int(row_get(r, "base_salary", 0) or 0),
                    int(row_get(r, "officer_pay", 0) or 0),
                    int(row_get(r, "special_allow", 0) or 0),
                    int(row_get(r, "deemed_ot", 0) or 0),
                    int(row_get(r, "overtime_pay", 0) or 0),
                    int(row_get(r, "commute_nontax", 0) or 0),
                    gross,
                    health_care,
                    childcare,
                    pension,
                    emp_ins,
                    withholding_tax,
                    resident_tax,
                    other_deduct,
                    deduct_total,
                    net,
                ]

            for ci, val in enumerate(values, start=1):
                cell = ws.cell(row=out_row, column=ci, value=val)
                if ci in money_cols:
                    cell.number_format = "#,##0"
                    cell.alignment = align_r
                else:
                    cell.alignment = align_c
            out_row += 1

    wb.save(file_path)

# =========================
# Bonus payroll (payroll_bonus)
# =========================

def list_bonus_rows(conn, target_month: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT b.*,
               e.employee_code, e.name_kanji, e.department, e.department_id,
               e.tax_type, e.dependents_count, e.work_prefecture_name
        FROM payroll_bonus b
        JOIN employees e ON e.employee_id = b.employee_id
        WHERE b.target_month=?
        ORDER BY e.employee_code
        """,
        (target_month,),
    )
    return [_row_with_current_department_name(conn, r) for r in cur.fetchall()]


def get_bonus_by_id(conn, bonus_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT b.*,
               e.employee_code, e.name_kanji, e.department, e.department_id,
               e.tax_type, e.dependents_count, e.work_prefecture_name
        FROM payroll_bonus b
        JOIN employees e ON e.employee_id = b.employee_id
        WHERE b.bonus_id=?
        """,
        (bonus_id,),
    )
    row = cur.fetchone()
    return _row_with_current_department_name(conn, row) if row else None

def upsert_bonus(conn, target_month: str, pay_date: str, employee_id: int, bonus_amount: int, note: str | None = None):
    department_id_snapshot, department_name_snapshot = get_employee_department_snapshot(conn, int(employee_id))
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO payroll_bonus (
          target_month, pay_date, employee_id, bonus_amount, note,
          department_id_snapshot, department_name_snapshot
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(target_month, employee_id) DO UPDATE SET
          pay_date=excluded.pay_date,
          bonus_amount=excluded.bonus_amount,
          note=excluded.note,
          department_id_snapshot=COALESCE(payroll_bonus.department_id_snapshot, excluded.department_id_snapshot),
          department_name_snapshot=CASE
            WHEN COALESCE(payroll_bonus.department_name_snapshot, '') = '' THEN excluded.department_name_snapshot
            ELSE payroll_bonus.department_name_snapshot
          END,
          updated_at=datetime('now')
        """,
        (
            target_month,
            pay_date,
            employee_id,
            bonus_amount,
            note,
            department_id_snapshot,
            department_name_snapshot,
        ),
    )
    conn.commit()

def get_bonus_by_employee_month(conn, target_month: str, employee_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT b.*,
               e.employee_code, e.name_kanji, e.department, e.department_id,
               e.tax_type, e.dependents_count, e.work_prefecture_name
        FROM payroll_bonus b
        JOIN employees e ON e.employee_id = b.employee_id
        WHERE b.target_month=? AND b.employee_id=?
        """,
        (target_month, employee_id),
    )
    row = cur.fetchone()
    return _row_with_current_department_name(conn, row) if row else None

def update_bonus_overrides(conn, bonus_id: int, overrides: dict):
    allowed = {
        "health_ins_override",
        "care_ins_override",
        "childcare_support_override",
        "pension_ins_override",
        "emp_ins_override",
        "withholding_tax_override",
    }
    updates = []
    params = []
    for key, value in overrides.items():
        if key not in allowed:
            continue
        updates.append(f"{key}=?")
        params.append(value)
    if not updates:
        return
    updates.append("updated_at=datetime('now')")
    params.append(bonus_id)
    conn.execute(
        f"UPDATE payroll_bonus SET {', '.join(updates)} WHERE bonus_id=?",
        params,
    )
    conn.commit()

def list_bonus_batch_rows(conn, target_month: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          b.target_month,
          b.pay_date,
          COUNT(*) AS employee_count,
          SUM(COALESCE(b.bonus_amount, 0)) AS total_bonus_amount,
          SUM(
            COALESCE(b.health_ins_employee, 0)
            + COALESCE(b.care_ins_employee, 0)
            + COALESCE(b.childcare_support_employee, 0)
            + COALESCE(b.pension_ins_employee, 0)
          ) AS total_social_ins,
          SUM(COALESCE(b.emp_ins_employee, 0)) AS total_emp_ins,
          SUM(COALESCE(b.withholding_tax_applied, 0)) AS total_withholding_tax,
          SUM(
            COALESCE(b.bonus_amount, 0)
            - COALESCE(b.health_ins_employee, 0)
            - COALESCE(b.care_ins_employee, 0)
            - COALESCE(b.childcare_support_employee, 0)
            - COALESCE(b.pension_ins_employee, 0)
            - COALESCE(b.emp_ins_employee, 0)
            - COALESCE(b.withholding_tax_applied, 0)
          ) AS total_net_amount
        FROM payroll_bonus b
        WHERE b.target_month = ?
        GROUP BY b.target_month, b.pay_date
        ORDER BY b.pay_date
        """,
        (target_month,),
    )
    return cur.fetchall()

def list_bonus_batch_rows_by_target_year(conn, year: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          b.target_month,
          b.pay_date,
          COUNT(*) AS employee_count,
          SUM(COALESCE(b.bonus_amount, 0)) AS total_bonus_amount,
          SUM(
            COALESCE(b.health_ins_employee, 0)
            + COALESCE(b.care_ins_employee, 0)
            + COALESCE(b.childcare_support_employee, 0)
            + COALESCE(b.pension_ins_employee, 0)
          ) AS total_social_ins,
          SUM(COALESCE(b.emp_ins_employee, 0)) AS total_emp_ins,
          SUM(COALESCE(b.withholding_tax_applied, 0)) AS total_withholding_tax,
          SUM(
            COALESCE(b.bonus_amount, 0)
            - COALESCE(b.health_ins_employee, 0)
            - COALESCE(b.care_ins_employee, 0)
            - COALESCE(b.childcare_support_employee, 0)
            - COALESCE(b.pension_ins_employee, 0)
            - COALESCE(b.emp_ins_employee, 0)
            - COALESCE(b.withholding_tax_applied, 0)
          ) AS total_net_amount
        FROM payroll_bonus b
        WHERE substr(b.target_month, 1, 4) = ?
        GROUP BY b.target_month, b.pay_date
        ORDER BY b.pay_date
        """,
        (str(year),),
    )
    return cur.fetchall()

def list_bonus_batch_rows_by_paydate_year(conn, year: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          b.target_month,
          b.pay_date,
          COUNT(*) AS employee_count,
          SUM(COALESCE(b.bonus_amount, 0)) AS total_bonus_amount,
          SUM(
            COALESCE(b.health_ins_employee, 0)
            + COALESCE(b.care_ins_employee, 0)
            + COALESCE(b.childcare_support_employee, 0)
            + COALESCE(b.pension_ins_employee, 0)
          ) AS total_social_ins,
          SUM(COALESCE(b.emp_ins_employee, 0)) AS total_emp_ins,
          SUM(COALESCE(b.withholding_tax_applied, 0)) AS total_withholding_tax,
          SUM(
            COALESCE(b.bonus_amount, 0)
            - COALESCE(b.health_ins_employee, 0)
            - COALESCE(b.care_ins_employee, 0)
            - COALESCE(b.childcare_support_employee, 0)
            - COALESCE(b.pension_ins_employee, 0)
            - COALESCE(b.emp_ins_employee, 0)
            - COALESCE(b.withholding_tax_applied, 0)
          ) AS total_net_amount
        FROM payroll_bonus b
        WHERE substr(b.pay_date, 1, 4) = ?
        GROUP BY b.target_month, b.pay_date
        ORDER BY b.pay_date
        """,
        (str(year),),
    )
    return cur.fetchall()

def bonus_month_exists(conn, target_month: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM payroll_bonus WHERE target_month = ? LIMIT 1",
        (target_month,),
    ).fetchone()
    return row is not None

def list_bonus_copy_source_months(conn) -> list[str]:
    return [
        r["target_month"]
        for r in conn.execute(
            """
            SELECT DISTINCT target_month
            FROM payroll_bonus
            ORDER BY target_month DESC
            """
        ).fetchall()
        if r["target_month"]
    ]

def list_bonus_rows_by_pay_date(conn, target_month: str, pay_date: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT b.*,
               e.employee_code, e.name_kanji, e.department, e.department_id,
               e.tax_type, e.dependents_count, e.work_prefecture_name
        FROM payroll_bonus b
        JOIN employees e ON e.employee_id = b.employee_id
        WHERE b.target_month = ? AND b.pay_date = ?
        ORDER BY e.employee_id
        """,
        (target_month, pay_date),
    )
    return [_row_with_current_department_name(conn, r) for r in cur.fetchall()]

def delete_bonus(conn, bonus_id: int):
    conn.execute("DELETE FROM payroll_bonus WHERE bonus_id=?", (bonus_id,))
    conn.commit()

def delete_bonus_batch(conn, target_month: str, pay_date: str) -> int:
    bonus_ids = [
        int(r["bonus_id"])
        for r in conn.execute(
            """
            SELECT bonus_id
            FROM payroll_bonus
            WHERE target_month = ? AND pay_date = ?
            """,
            (target_month, pay_date),
        ).fetchall()
    ]
    if not bonus_ids:
        return 0

    placeholders = ",".join("?" for _ in bonus_ids)
    conn.execute(f"DELETE FROM payroll_bonus_social_detail WHERE bonus_id IN ({placeholders})", bonus_ids)
    cur = conn.execute(f"DELETE FROM payroll_bonus WHERE bonus_id IN ({placeholders})", bonus_ids)
    conn.commit()
    return cur.rowcount

def copy_prev_bonus_inputs(conn, target_month: str, pay_date: str, prev_month: str) -> int:
    rows = conn.execute(
        """
        SELECT employee_id, bonus_amount, note
        FROM payroll_bonus
        WHERE target_month = ?
        """,
        (prev_month,),
    ).fetchall()
    if not rows:
        return 0

    for r in rows:
        upsert_bonus(
            conn,
            target_month,
            pay_date,
            int(r["employee_id"]),
            int(r["bonus_amount"] or 0),
            r["note"],
        )
    return len(rows)

def _prev_month(ym: str) -> str:
    # ym: yyyy-mm
    y, m = ym.split("-")
    y = int(y)
    m = int(m)
    if m == 1:
        return f"{y-1}-12"
    return f"{y}-{m-1:02d}"

def get_bonus_fiscal_year(target_month: str) -> int:
    y, m = map(int, target_month.split("-"))
    return y if m >= 4 else y - 1

def get_prior_bonus_std_health_total(conn, employee_id: int, target_month: str) -> int:
    fy = get_bonus_fiscal_year(target_month)
    start_ym = f"{fy}-04"
    end_ym = f"{fy+1}-03"

    cur = conn.cursor()
    cur.execute(
        """
        SELECT bonus_amount
        FROM payroll_bonus
        WHERE employee_id = ?
          AND target_month >= ?
          AND target_month <= ?
          AND target_month < ?
        ORDER BY target_month
        """,
        (employee_id, start_ym, end_ym, target_month),
    )
    rows = cur.fetchall()

    total = 0
    for r in rows:
        amt = int(r["bonus_amount"] or 0)
        std_raw = (amt // 1000) * 1000
        total += std_raw

    return total

def apply_bonus_insurance_auto(conn, target_month: str):
    """賞与の社保・雇保を自動計算"""
    emp_rate, _ = get_emp_ins_rate_for_month(conn, target_month)

    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            b.bonus_id,
            b.employee_id,
            b.bonus_amount,
            b.health_ins_override,
            b.care_ins_override,
            b.childcare_support_override,
            b.pension_ins_override,
            b.emp_ins_override,
            e.work_prefecture_name,
            COALESCE(e.is_social_insurance_target, 0) AS is_social_insurance_target,
            COALESCE(e.is_employment_insurance_target, 1) AS is_employment_insurance_target
        FROM payroll_bonus b
        JOIN employees e ON e.employee_id = b.employee_id
        WHERE b.target_month=?
        """,
        (target_month,),
    )
    rows = cur.fetchall()

    for r in rows:
        pref = (r["work_prefecture_name"] or "").strip()
        h_rate, p_rate, c_rate, cc_emp_rate, cc_er_rate, contribution_rate = \
            get_social_ins_rate_for_month(conn, target_month, pref)
       
        employee_id = int(r["employee_id"])
        amt = int(r["bonus_amount"] or 0)

        # 1) 標準賞与額（1,000円未満切捨て）
        std_raw = (amt // 1000) * 1000

        # 2) 健保・介護・支援金の年度上限 573万円
        prior_total = get_prior_bonus_std_health_total(conn, employee_id, target_month)
        remaining_health_cap = max(0, 5_730_000 - min(prior_total, 5_730_000))
        std_health = min(std_raw, remaining_health_cap)

        # 3) 厚年・拠出金の月上限 150万円
        std_pension = min(std_raw, 1_500_000)

        if int(r["is_social_insurance_target"] or 0):
            # 4) 本人負担
            health = round_half_up(std_health * h_rate)
            care = round_half_up(std_health * c_rate) if c_rate > 0 else 0
            childcare_support_emp = round_half_up(std_health * cc_emp_rate) if cc_emp_rate > 0 else 0
            pension = round_half_up(std_pension * p_rate)

            # 5) 事業主負担
            childcare_support_er = round_down(std_health * cc_er_rate) if cc_er_rate > 0 else 0

            # 6) 拠出金（事業主のみ）
            childcare_contribution_er = round_down(std_pension * contribution_rate)
        else:
            health = 0
            care = 0
            childcare_support_emp = 0
            pension = 0
            childcare_support_er = 0
            childcare_contribution_er = 0

        # 7) 雇用保険は従来どおり賞与支給額ベース
        empins = int(math.floor(amt * emp_rate)) if int(r["is_employment_insurance_target"] or 0) else 0

        applied_health = health if r["health_ins_override"] is None else int(r["health_ins_override"])
        applied_care = care if r["care_ins_override"] is None else int(r["care_ins_override"])
        applied_childcare = childcare_support_emp if r["childcare_support_override"] is None else int(r["childcare_support_override"])
        applied_pension = pension if r["pension_ins_override"] is None else int(r["pension_ins_override"])
        applied_empins = empins if r["emp_ins_override"] is None else int(r["emp_ins_override"])

        social_total_calc = applied_health + applied_care + applied_childcare + applied_pension

        cur.execute(
            """
            UPDATE payroll_bonus
            SET std_bonus_raw=?,
                std_bonus_health=?,
                std_bonus_pension=?,
                bonus_fiscal_year=?,
                health_ins_auto=?,
                care_ins_auto=?,
                childcare_support_auto=?,
                pension_ins_auto=?,
                emp_ins_auto=?,
                health_ins_employee=?,
                care_ins_employee=?,
                childcare_support_employee=?,
                childcare_support_employer=?,
                childcare_contribution_employer=?,
                pension_ins_employee=?,
                emp_ins_employee=?,
                social_ins_total_calc=?,
                updated_at=datetime('now')
            WHERE bonus_id=?
            """,
            (
                std_raw,
                std_health,
                std_pension,
                get_bonus_fiscal_year(target_month),
                health,
                care,
                childcare_support_emp,
                pension,
                empins,
                applied_health,
                applied_care,
                applied_childcare,
                childcare_support_er,
                childcare_contribution_er,
                applied_pension,
                applied_empins,
                social_total_calc,
                r["bonus_id"],
            ),
        )

    conn.commit()


class BonusWithholdingTableError(RuntimeError):
    pass


def _find_bonus_withholding_source_file(conn) -> Path | None:
    """
    賞与税額表（算出率表）xlsx を探す。
    優先順位:
      1) settings.json の 'withholding_bonus_excel'（ファイルパス）
      2) resources_dir 配下の *.xlsx から、ファイル名に 'bonus' または '賞与' を含むもの
    """
    s = app_settings.get_setting("withholding_bonus_excel", None)
    if isinstance(s, str) and s.strip():
        p = Path(s).expanduser()
        if p.exists():
            return p

    d = _withholding_dir(conn)
    cands = list(d.glob("*.xlsx"))
    for p in cands:
        name = p.name.lower()
        if "bonus" in name or "賞与" in p.name:
            return p
    return cands[0] if cands else None


def _bonus_cache_path(conn, year: int) -> Path:
    return _withholding_dir(conn) / f"withholding_{year}_bonus.json"


def _load_bonus_rate_table_from_xlsx(path: Path) -> dict:
    """国税庁 賞与に対する源泉徴収税額の算出率表（.xlsx）を読み取り、内部用テーブル(dict)を返す。"""
    wb = load_workbook(filename=str(path), data_only=True, read_only=True)
    # 国税庁フォーマットは「賞与」シートが多い。無ければ先頭。
    ws = wb["賞与"] if "賞与" in wb.sheetnames else wb.active

    max_row = ws.max_row

    def cell(r, c):
        v = ws.cell(row=r, column=c).value
        return v

    rows = []
    # データ開始はだいたい9行目（A1=タイトル）
    for r in range(9, max_row + 1):
        rate = cell(r, 2)
        if not isinstance(rate, (int, float)):
            continue

        def parse_pair(start_col, end_col):
            low = cell(r, start_col)
            up = cell(r, end_col)

            # 空は無効
            if low is None and up is None:
                return None

            # "xxx 千円未満" の場合（上限だけ）
            if isinstance(up, str) and "未満" in up:
                if isinstance(low, (int, float)):
                    return {"lower": None, "upper": int(low)}
                return None

            # 数値-数値
            if isinstance(low, (int, float)) and isinstance(up, (int, float)):
                return {"lower": int(low), "upper": int(up)}

            # 数値-空（以上）
            if isinstance(low, (int, float)) and (up is None or str(up).strip() == ""):
                return {"lower": int(low), "upper": None}

            return None

        kou = []
        for dep in range(0, 8):
            sc = 4 + dep * 2
            ec = sc + 1
            kou.append(parse_pair(sc, ec))

        otsu = parse_pair(20, 21)

        rows.append({"rate_percent": float(rate), "kou": kou, "otsu": otsu})

    return {"year": WITHHOLDING_YEAR_DEFAULT, "kind": "bonus", "rows": rows}


def build_bonus_withholding_cache_from_excel(conn, year: int = WITHHOLDING_YEAR_DEFAULT) -> Path:
    src = _find_bonus_withholding_source_file(conn)
    if not src:
        d = _withholding_dir(conn)
        raise BonusWithholdingTableError(
            "賞与の税額表Excel（算出率表）が見つかりません。\n"
            f"次のフォルダに、国税庁の『賞与に対する源泉徴収税額の算出率の表』（.xlsx）を置くか、\n"
            "settings.json の 'withholding_bonus_excel' を設定してください。\n\n"
            f"フォルダ: {d}"
        )
    table = _load_bonus_rate_table_from_xlsx(src)
    out = _bonus_cache_path(conn, year)
    out.write_text(json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load_bonus_withholding_table(conn, year: int = WITHHOLDING_YEAR_DEFAULT) -> dict:
    p = _bonus_cache_path(conn, year)
    if not p.exists():
        build_bonus_withholding_cache_from_excel(conn, year)
    return json.loads(p.read_text(encoding="utf-8"))


def _lookup_bonus_rate_percent(table: dict, prev_after_social_yen: int, tax_type: str, dependents: int) -> float:
    """前月の社保控除後給与（千円単位）から、算出率（%）を引く。"""
    amt_k = int(math.floor(max(0, prev_after_social_yen) / 1000))
    tax_type = (tax_type or "甲").strip()
    dependents = int(dependents)
    if dependents < 0:
        dependents = 0
    if dependents > 7:
        dependents = 7

    rows = table.get("rows", [])
    if not rows:
        return 0.0

    def hit(pair):
        if not pair:
            return False
        low = pair.get("lower", None)
        up = pair.get("upper", None)
        if low is None and up is not None:
            return amt_k < int(up)
        if up is None:
            return amt_k >= int(low)
        return int(low) <= amt_k < int(up)

    for rr in rows:
        if tax_type == "乙":
            if hit(rr.get("otsu")):
                return float(rr.get("rate_percent", 0.0))
        else:
            kou = rr.get("kou", [])
            pair = kou[dependents] if 0 <= dependents < len(kou) else None
            if hit(pair):
                return float(rr.get("rate_percent", 0.0))

    # 最後まで当たらない場合（表外）は最後の行を使う
    return float(rows[-1].get("rate_percent", 0.0))


def apply_bonus_withholding_tax_auto(conn, target_month: str, year: int = WITHHOLDING_YEAR_DEFAULT):
    """
    賞与の源泉：算出率表（%）を用いて自動計算。
    ざっくり:
      前月の(社保等控除後)給与 → 算出率(%)
      源泉税 = floor( (賞与額 - 社保等) * rate/100 )
    """
    table = load_bonus_withholding_table(conn, year)
    prev_m = _prev_month(target_month)

    cur = conn.cursor()

    prev_rows = get_payroll_rows(conn, prev_m)
    prev_map = {r["employee_id"]: r for r in prev_rows}

    rows = list_bonus_rows(conn, target_month)

    for r in rows:
        emp_id = r["employee_id"]

        prev = prev_map.get(emp_id)
        if prev is None:
            prev_after_social = 0
        else:
            prev_taxable = _calc_taxable_pay_from_payroll_row(prev, conn)
            prev_social = int(row_get(prev, "social_ins_total_calc", 0) or 0)
            prev_after_social = max(0, prev_taxable - prev_social)

        tax_type = row_get(r, "tax_type", "甲")
        deps = int(row_get(r, "dependents_count", 0) or 0)
        rate_percent = _lookup_bonus_rate_percent(table, prev_after_social, tax_type, deps)

        bonus_amt = int(r["bonus_amount"] or 0)
        social = int(row_get(r, "social_ins_total_calc", 0) or 0)
        emp_ins = int(row_get(r, "emp_ins_employee", 0) or 0)
        bonus_after_social = max(0, bonus_amt - social - emp_ins)

        auto = int(math.floor(bonus_after_social * rate_percent / 100.0))

        override = r["withholding_tax_override"]
        applied = auto if override is None else int(override)

        cur.execute(
            """
            UPDATE payroll_bonus
            SET withholding_tax_auto=?, withholding_tax_applied=?, updated_at=datetime('now')
            WHERE bonus_id=?
            """,
            (auto, applied, r["bonus_id"]),
        )

    conn.commit()


def recalc_bonus_month(conn, target_month: str):
    """
    賞与月の再計算
    - 保険（社保＋雇保）
    - 源泉所得税
    """
    apply_bonus_insurance_auto(conn, target_month)
    apply_bonus_withholding_tax_auto(conn, target_month)


def seed_social_insurance_item_master(conn):
    rows = [
        ("health", "健康保険料", 1, 1, "std_health", 1, 10, 1),
        ("care", "介護保険料", 1, 1, "std_health", 1, 15, 1),
        ("childcare", "子ども・子育て支援金", 1, 1, "std_health", 1, 20, 1),
        ("pension", "厚生年金保険料", 1, 1, "std_pension", 1, 30, 1),
        ("childcare_contribution", "子ども・子育て拠出金", 0, 1, "std_pension", 0, 40, 1),
    ]

    cur = conn.cursor()
    for row in rows:
        cur.execute(
            """
            INSERT OR IGNORE INTO social_insurance_item_master(
                item_code, item_name, applies_to_monthly, applies_to_bonus,
                base_type, is_tax_deductible, sort_order, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
    conn.commit()

def is_enrolled_at_month_end(hire_date, leave_date, target_month: str) -> bool:
    """
    月末在籍判定（社保用）
    """
    import calendar
    from datetime import datetime

    y, m = map(int, target_month.split("-"))
    last_day = calendar.monthrange(y, m)[1]
    month_end = datetime.strptime(f"{y}-{m:02d}-{last_day:02d}", "%Y-%m-%d").date()

    if hire_date:
        hd = datetime.strptime(hire_date, "%Y-%m-%d").date()
        if hd > month_end:
            return False

    if leave_date:
        ld = datetime.strptime(leave_date, "%Y-%m-%d").date()
        if ld <= month_end:
            return False

    return True

def has_employment_insurance_in_wage_period(hire_date, leave_date, wage_period_start: str | None, wage_period_end: str | None) -> bool:
    """
    雇用保険の給与控除判定（賃金対象期間基準）
    賃金期間と在職期間が1日でも重なれば、その給与では雇用保険料を控除する。
    """
    if not wage_period_start or not wage_period_end:
        return False

    from datetime import datetime

    try:
        ws = datetime.strptime(wage_period_start, "%Y-%m-%d").date()
        we = datetime.strptime(wage_period_end, "%Y-%m-%d").date()
    except Exception:
        return False

    if hire_date:
        hd = datetime.strptime(hire_date, "%Y-%m-%d").date()
        if hd > we:
            return False

    if leave_date:
        ld = datetime.strptime(leave_date, "%Y-%m-%d").date()
        if ld < ws:
            return False

    return True

