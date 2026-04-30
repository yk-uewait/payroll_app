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

EMPLOYEE_CSV_COLUMNS = [
    "社員番号",
    "氏名",
    "部署",
    "給与支給方式",
    "給与支給方式ID",
    "支給日",
    "標準報酬月額（健保）",
    "標準報酬月額（厚年）",
    "生年月日",
    "入社日",
    "退職日",
    "退職処理済み",
    "源泉",
    "扶養人数",
    "都道府県",
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

    if closing_mode == "next_month":
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

def upsert_payment_schedule(conn, schedule_name: str, closing_mode: str, pay_day: int, is_active: int = 1, payment_schedule_id: int | None = None):
    cur = conn.cursor()
    if payment_schedule_id is None:
        cur.execute(
            """
            INSERT INTO payment_schedules(
                schedule_name, closing_mode, pay_day, is_active
            )
            VALUES (?, ?, ?, ?)
            """,
            (schedule_name, closing_mode, pay_day, is_active),
        )
    else:
        cur.execute(
            """
            UPDATE payment_schedules
            SET schedule_name=?,
                closing_mode=?,
                pay_day=?,
                is_active=?,
                updated_at=datetime('now')
            WHERE payment_schedule_id=?
            """,
            (schedule_name, closing_mode, pay_day, is_active, payment_schedule_id),
        )
    conn.commit()

def list_payment_schedules_all(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM payment_schedules
        ORDER BY is_active DESC, pay_day ASC, payment_schedule_id ASC
        """
    )
    return cur.fetchall()

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


def round_half_up(value: float) -> int:
    """0.5以上切り上げ、0.5未満切り捨て"""
    return int(math.floor(value + 0.5))

def round_down(value: float) -> int:
    """小数点以下切り捨て"""
    return int(math.floor(value))

def get_age_on_date(birth_date_str: str | None, target_date_str: str) -> int | None:
    """
    birth_date_str: 'YYYY-MM-DD'
    target_date_str: 'YYYY-MM' または 'YYYY-MM-DD'
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
    birth_date=None,
    payment_schedule_id=None,
    hire_date=None,
    leave_date=None,
    retirement_processed=0,
    memo=None,
):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO employees(
          employee_code, name_kanji, department, payday_group,
          std_monthly_wage, std_pension_wage,
          tax_type, dependents_count, work_prefecture_name, birth_date,
          payment_schedule_id, hire_date, leave_date, retirement_processed, memo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(employee_code) DO UPDATE SET
          name_kanji=excluded.name_kanji,
          department=excluded.department,
          payday_group=excluded.payday_group,
          is_deleted=0,
          deleted_at=NULL,
          std_monthly_wage=excluded.std_monthly_wage,
          std_pension_wage=excluded.std_pension_wage,
          tax_type=excluded.tax_type,
          dependents_count=excluded.dependents_count,
          work_prefecture_name=excluded.work_prefecture_name,
          birth_date=excluded.birth_date,
          payment_schedule_id=excluded.payment_schedule_id,
          hire_date=excluded.hire_date,
          leave_date=excluded.leave_date,
          retirement_processed=excluded.retirement_processed,
          memo=excluded.memo,
          updated_at=datetime('now')
        """,
        (
            employee_code,
            name_kanji,
            department,
            payday_group,
            std_health,
            std_pension,
            tax_type,
            dependents_count,
            work_prefecture_name,
            birth_date,
            payment_schedule_id,
            hire_date,
            leave_date,
            int(retirement_processed or 0),
            memo,
        ),
    )
    conn.commit()

def list_employees(conn, include_deleted: bool = False):
    cur = conn.cursor()
    if include_deleted:
        cur.execute("SELECT * FROM employees ORDER BY employee_id DESC")
    else:
        cur.execute("SELECT * FROM employees WHERE COALESCE(is_deleted, 0) = 0 ORDER BY employee_id DESC")
    return cur.fetchall()

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
        if not employee_code or not name_kanji:
            continue

        payment_schedule_id = resolve_employee_payment_schedule_id(conn, row)
        if not payment_schedule_id:
            raise ValueError(f"給与支給方式を解決できませんでした: 社員番号 {employee_code}")

        department = _employee_csv_cell(row, "department", "部署")
        std_health = int(_employee_csv_cell(row, "std_monthly_wage", "標準報酬月額（健保）", default="0").replace(",", "") or 0)
        std_pension = int(_employee_csv_cell(row, "std_pension_wage", "標準報酬月額（厚年）", default="0").replace(",", "") or 0)
        tax_type = _employee_csv_cell(row, "tax_type", "源泉区分", "源泉", default="甲") or "甲"
        dependents_count = int(_employee_csv_cell(row, "dependents_count", "扶養人数", "扶養", default="0").replace(",", "") or 0)
        work_prefecture_name = _employee_csv_cell(row, "work_prefecture_name", "勤務地都道府県", "都道府県")
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
            work_prefecture_name,
            birth_date,
            payment_schedule_id,
            hire_date,
            leave_date,
            retirement_processed,
            memo,
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
                "部署": row_get(e, "department", ""),
                "給与支給方式": get_employee_payment_schedule_display(e, conn),
                "給与支給方式ID": row_get(e, "payment_schedule_id", "") or "",
                "支給日": row_get(e, "payday_group", "") or "",
                "標準報酬月額（健保）": row_get(e, "std_monthly_wage", 0) or 0,
                "標準報酬月額（厚年）": row_get(e, "std_pension_wage", 0) or 0,
                "生年月日": row_get(e, "birth_date", "") or "",
                "入社日": row_get(e, "hire_date", "") or "",
                "退職日": row_get(e, "leave_date", "") or "",
                "退職処理済み": "1" if int(row_get(e, "retirement_processed", 0) or 0) else "0",
                "源泉": row_get(e, "tax_type", "甲") or "甲",
                "扶養人数": row_get(e, "dependents_count", 0) or 0,
                "都道府県": row_get(e, "work_prefecture_name", "") or "",
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
        cur.execute(
            """
            INSERT OR IGNORE INTO payroll_monthly(
              target_month, employee_id,
              wage_period_start, wage_period_end,
              pay_date_auto, pay_date_applied
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (target_month, employee_id, wage_period_start, wage_period_end, pay_date_auto, pay_date_applied),
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
          e.employee_code, e.name_kanji, e.department, e.payday_group,
          e.std_monthly_wage, e.std_pension_wage,
          e.tax_type, e.dependents_count, e.work_prefecture_name, e.birth_date,
          e.hire_date, e.leave_date,

          -- 総支給（入力値の合計：税社保計算はまだ含めない）
          (
            p.officer_pay + p.base_salary + p.deemed_ot + p.overtime_pay + p.special_allow + p.commute_nontax +
            p.pay_free1 + p.pay_free2 + p.pay_free3 + p.pay_free4 + p.pay_free5
          ) AS total_pay_input,

          -- 控除合計（旅行積立＋その他控除：税社保住民税等はまだ）
          (
            p.travel_saving +
            p.deduct_free1 + p.deduct_free2 + p.deduct_free3 + p.deduct_free4 + p.deduct_free5
          ) AS total_deduct_input,

          -- 手取り（入力ベース）
          (
            (
              p.officer_pay + p.base_salary + p.deemed_ot + p.overtime_pay + p.special_allow + p.commute_nontax +
              p.pay_free1 + p.pay_free2 + p.pay_free3 + p.pay_free4 + p.pay_free5
            ) -
            (
              p.travel_saving +
              p.deduct_free1 + p.deduct_free2 + p.deduct_free3 + p.deduct_free4 + p.deduct_free5
            )
          ) AS net_pay_input

        FROM payroll_monthly p
        JOIN employees e ON e.employee_id = p.employee_id
        WHERE p.target_month=?
        ORDER BY e.employee_id
        """,
        (target_month,),
    )
    return cur.fetchall()

def get_payroll_batch_rows(conn, target_month: str):
    """
    月次給与タブ用:
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
            p.officer_pay + p.base_salary + p.deemed_ot + p.overtime_pay + p.special_allow + p.commute_nontax +
            p.pay_free1 + p.pay_free2 + p.pay_free3 + p.pay_free4 + p.pay_free5
          ) AS total_pay_input_sum,

          SUM(
            p.travel_saving +
            p.deduct_free1 + p.deduct_free2 + p.deduct_free3 + p.deduct_free4 + p.deduct_free5
          ) AS total_deduct_input_sum,

          SUM(
            COALESCE(p.emp_ins_employee, 0) +
            COALESCE(p.health_ins_employee, 0) +
            COALESCE(p.care_ins_employee, 0) +
            COALESCE(p.childcare_support_employee, 0) +
            COALESCE(p.pension_ins_employee, 0) +
            COALESCE(p.resident_tax_applied, 0) +
            COALESCE(p.withholding_tax_applied, 0) +
            COALESCE(p.travel_saving, 0) +
            COALESCE(p.deduct_free1, 0) + COALESCE(p.deduct_free2, 0) + COALESCE(p.deduct_free3, 0) +
            COALESCE(p.deduct_free4, 0) + COALESCE(p.deduct_free5, 0)
          ) AS total_deduct_all_sum,

          SUM(
            (
              p.officer_pay + p.base_salary + p.deemed_ot + p.overtime_pay + p.special_allow + p.commute_nontax +
              p.pay_free1 + p.pay_free2 + p.pay_free3 + p.pay_free4 + p.pay_free5
            ) -
            (
              COALESCE(p.emp_ins_employee, 0) +
              COALESCE(p.health_ins_employee, 0) +
              COALESCE(p.care_ins_employee, 0) +
              COALESCE(p.childcare_support_employee, 0) +
              COALESCE(p.pension_ins_employee, 0) +
              COALESCE(p.resident_tax_applied, 0) +
              COALESCE(p.withholding_tax_applied, 0) +
              COALESCE(p.travel_saving, 0) +
              COALESCE(p.deduct_free1, 0) + COALESCE(p.deduct_free2, 0) + COALESCE(p.deduct_free3, 0) +
              COALESCE(p.deduct_free4, 0) + COALESCE(p.deduct_free5, 0)
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
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          p.target_month,
          p.pay_date_applied,
          COUNT(*) AS employee_count,
          SUM(
            COALESCE(p.officer_pay, 0) +
            COALESCE(p.base_salary, 0) +
            COALESCE(p.deemed_ot, 0) +
            COALESCE(p.overtime_pay, 0) +
            COALESCE(p.special_allow, 0) +
            CASE WHEN COALESCE(p.pay_free1_is_taxable, 0) = 1 THEN COALESCE(p.pay_free1, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free2_is_taxable, 0) = 1 THEN COALESCE(p.pay_free2, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free3_is_taxable, 0) = 1 THEN COALESCE(p.pay_free3, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free4_is_taxable, 0) = 1 THEN COALESCE(p.pay_free4, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free5_is_taxable, 0) = 1 THEN COALESCE(p.pay_free5, 0) ELSE 0 END
          ) AS taxable_pay_sum,
          SUM(
            COALESCE(p.commute_nontax, 0) +
            CASE WHEN COALESCE(p.pay_free1_is_taxable, 0) = 0 THEN COALESCE(p.pay_free1, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free2_is_taxable, 0) = 0 THEN COALESCE(p.pay_free2, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free3_is_taxable, 0) = 0 THEN COALESCE(p.pay_free3, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free4_is_taxable, 0) = 0 THEN COALESCE(p.pay_free4, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free5_is_taxable, 0) = 0 THEN COALESCE(p.pay_free5, 0) ELSE 0 END
          ) AS non_taxable_pay_sum,
          SUM(
            COALESCE(p.officer_pay, 0) +
            COALESCE(p.base_salary, 0) +
            COALESCE(p.deemed_ot, 0) +
            COALESCE(p.overtime_pay, 0) +
            COALESCE(p.special_allow, 0) +
            COALESCE(p.commute_nontax, 0) +
            COALESCE(p.pay_free1, 0) +
            COALESCE(p.pay_free2, 0) +
            COALESCE(p.pay_free3, 0) +
            COALESCE(p.pay_free4, 0) +
            COALESCE(p.pay_free5, 0)
          ) AS gross_pay_sum,
          SUM(COALESCE(p.social_ins_total_calc, 0)) AS social_ins_sum,
          SUM(COALESCE(p.withholding_tax_applied, 0)) AS withholding_tax_sum,
          SUM(COALESCE(p.resident_tax_applied, 0)) AS resident_tax_sum,
          SUM(
            COALESCE(p.travel_saving, 0) +
            COALESCE(p.deduct_free1, 0) +
            COALESCE(p.deduct_free2, 0) +
            COALESCE(p.deduct_free3, 0) +
            COALESCE(p.deduct_free4, 0) +
            COALESCE(p.deduct_free5, 0)
          ) AS other_deduct_sum,
          SUM(
            COALESCE(p.social_ins_total_calc, 0) +
            COALESCE(p.withholding_tax_applied, 0) +
            COALESCE(p.resident_tax_applied, 0) +
            COALESCE(p.travel_saving, 0) +
            COALESCE(p.deduct_free1, 0) +
            COALESCE(p.deduct_free2, 0) +
            COALESCE(p.deduct_free3, 0) +
           COALESCE(p.deduct_free4, 0) +
            COALESCE(p.deduct_free5, 0)
          ) AS total_deduct_sum,
          SUM(
            (
              COALESCE(p.officer_pay, 0) +
              COALESCE(p.base_salary, 0) +
             COALESCE(p.deemed_ot, 0) +
              COALESCE(p.overtime_pay, 0) +
              COALESCE(p.special_allow, 0) +
             COALESCE(p.commute_nontax, 0) +
              COALESCE(p.pay_free1, 0) +
              COALESCE(p.pay_free2, 0) +
              COALESCE(p.pay_free3, 0) +
              COALESCE(p.pay_free4, 0) +
              COALESCE(p.pay_free5, 0)
            ) -
            (
              COALESCE(p.social_ins_total_calc, 0) +
             COALESCE(p.withholding_tax_applied, 0) +
             COALESCE(p.resident_tax_applied, 0) +
              COALESCE(p.travel_saving, 0) +
              COALESCE(p.deduct_free1, 0) +
              COALESCE(p.deduct_free2, 0) +
              COALESCE(p.deduct_free3, 0) +
              COALESCE(p.deduct_free4, 0) +
              COALESCE(p.deduct_free5, 0)
            )
          ) AS net_pay_sum
        FROM payroll_monthly p
        WHERE substr(p.target_month,1,4)=?
        GROUP BY p.target_month, p.pay_date_applied
        ORDER BY p.pay_date_applied
        """,
        (str(year),),
    )
    return cur.fetchall()

# ==============================
# 年別一覧（支給日基準）
# ==============================
def get_payroll_batch_rows_by_paydate_year(conn, year: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          p.target_month,
          p.pay_date_applied,
          COUNT(*) AS employee_count,
          SUM(
            COALESCE(p.officer_pay, 0) +
            COALESCE(p.base_salary, 0) +
            COALESCE(p.deemed_ot, 0) +
            COALESCE(p.overtime_pay, 0) +
            COALESCE(p.special_allow, 0) +
           CASE WHEN COALESCE(p.pay_free1_is_taxable, 0) = 1 THEN COALESCE(p.pay_free1, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free2_is_taxable, 0) = 1 THEN COALESCE(p.pay_free2, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free3_is_taxable, 0) = 1 THEN COALESCE(p.pay_free3, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free4_is_taxable, 0) = 1 THEN COALESCE(p.pay_free4, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free5_is_taxable, 0) = 1 THEN COALESCE(p.pay_free5, 0) ELSE 0 END
          ) AS taxable_pay_sum,
          SUM(
            COALESCE(p.commute_nontax, 0) +
            CASE WHEN COALESCE(p.pay_free1_is_taxable, 0) = 0 THEN COALESCE(p.pay_free1, 0) ELSE 0 END +
           CASE WHEN COALESCE(p.pay_free2_is_taxable, 0) = 0 THEN COALESCE(p.pay_free2, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free3_is_taxable, 0) = 0 THEN COALESCE(p.pay_free3, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free4_is_taxable, 0) = 0 THEN COALESCE(p.pay_free4, 0) ELSE 0 END +
            CASE WHEN COALESCE(p.pay_free5_is_taxable, 0) = 0 THEN COALESCE(p.pay_free5, 0) ELSE 0 END
          ) AS non_taxable_pay_sum,
          SUM(
            COALESCE(p.officer_pay, 0) +
            COALESCE(p.base_salary, 0) +
            COALESCE(p.deemed_ot, 0) +
            COALESCE(p.overtime_pay, 0) +
            COALESCE(p.special_allow, 0) +
            COALESCE(p.commute_nontax, 0) +
           COALESCE(p.pay_free1, 0) +
            COALESCE(p.pay_free2, 0) +
           COALESCE(p.pay_free3, 0) +
            COALESCE(p.pay_free4, 0) +
            COALESCE(p.pay_free5, 0)
          ) AS gross_pay_sum,
          SUM(COALESCE(p.social_ins_total_calc, 0)) AS social_ins_sum,
         SUM(COALESCE(p.withholding_tax_applied, 0)) AS withholding_tax_sum,
          SUM(COALESCE(p.resident_tax_applied, 0)) AS resident_tax_sum,
          SUM(
            COALESCE(p.travel_saving, 0) +
            COALESCE(p.deduct_free1, 0) +
            COALESCE(p.deduct_free2, 0) +
           COALESCE(p.deduct_free3, 0) +
            COALESCE(p.deduct_free4, 0) +
            COALESCE(p.deduct_free5, 0)
          ) AS other_deduct_sum,
          SUM(
            COALESCE(p.social_ins_total_calc, 0) +
            COALESCE(p.withholding_tax_applied, 0) +
            COALESCE(p.resident_tax_applied, 0) +
            COALESCE(p.travel_saving, 0) +
            COALESCE(p.deduct_free1, 0) +
            COALESCE(p.deduct_free2, 0) +
            COALESCE(p.deduct_free3, 0) +
            COALESCE(p.deduct_free4, 0) +
            COALESCE(p.deduct_free5, 0)
          ) AS total_deduct_sum,
          SUM(
            (
              COALESCE(p.officer_pay, 0) +
              COALESCE(p.base_salary, 0) +
              COALESCE(p.deemed_ot, 0) +
              COALESCE(p.overtime_pay, 0) +
              COALESCE(p.special_allow, 0) +
              COALESCE(p.commute_nontax, 0) +
              COALESCE(p.pay_free1, 0) +
              COALESCE(p.pay_free2, 0) +
              COALESCE(p.pay_free3, 0) +
              COALESCE(p.pay_free4, 0) +
              COALESCE(p.pay_free5, 0)
            ) -
            (
              COALESCE(p.social_ins_total_calc, 0) +
              COALESCE(p.withholding_tax_applied, 0) +
              COALESCE(p.resident_tax_applied, 0) +
              COALESCE(p.travel_saving, 0) +
              COALESCE(p.deduct_free1, 0) +
             COALESCE(p.deduct_free2, 0) +
              COALESCE(p.deduct_free3, 0) +
              COALESCE(p.deduct_free4, 0) +
              COALESCE(p.deduct_free5, 0)
           )
          ) AS net_pay_sum
        FROM payroll_monthly p
        WHERE substr(p.pay_date_applied,1,4)=?
        GROUP BY p.target_month, p.pay_date_applied
        ORDER BY p.pay_date_applied
        """,
        (str(year),),
    )
    return cur.fetchall()

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
          e.employee_code, e.name_kanji, e.department, e.payday_group,
          e.std_monthly_wage, e.std_pension_wage,
          e.tax_type, e.dependents_count, e.work_prefecture_name, e.birth_date,
          e.hire_date, e.leave_date,

          (
            p.officer_pay + p.base_salary + p.deemed_ot + p.overtime_pay + p.special_allow + p.commute_nontax +
            p.pay_free1 + p.pay_free2 + p.pay_free3 + p.pay_free4 + p.pay_free5
          ) AS total_pay_input,

          (
            p.travel_saving +
            p.deduct_free1 + p.deduct_free2 + p.deduct_free3 + p.deduct_free4 + p.deduct_free5
          ) AS total_deduct_input,

          (
            (
              p.officer_pay + p.base_salary + p.deemed_ot + p.overtime_pay + p.special_allow + p.commute_nontax +
              p.pay_free1 + p.pay_free2 + p.pay_free3 + p.pay_free4 + p.pay_free5
            ) -
            (
              p.travel_saving +
              p.deduct_free1 + p.deduct_free2 + p.deduct_free3 + p.deduct_free4 + p.deduct_free5
            )
          ) AS net_pay_input

        FROM payroll_monthly p
        JOIN employees e ON e.employee_id = p.employee_id
        WHERE p.target_month = ? AND p.pay_date_applied = ?
        ORDER BY e.employee_id
        """,
        (target_month, pay_date_applied),
    )
    return cur.fetchall()

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
              pay_free1=?, pay_free2=?, pay_free3=?, pay_free4=?, pay_free5=?,
              pay_free1_is_taxable=?, pay_free1_is_social_base=?, pay_free1_is_employment_base=?,
              pay_free2_is_taxable=?, pay_free2_is_social_base=?, pay_free2_is_employment_base=?,
              pay_free3_is_taxable=?, pay_free3_is_social_base=?, pay_free3_is_employment_base=?,
              pay_free4_is_taxable=?, pay_free4_is_social_base=?, pay_free4_is_employment_base=?,
              pay_free5_is_taxable=?, pay_free5_is_social_base=?, pay_free5_is_employment_base=?,
              travel_saving=?, deduct_free1=?, deduct_free2=?, deduct_free3=?, deduct_free4=?, deduct_free5=?,
              updated_at=datetime('now')
            WHERE target_month=? AND employee_id=?
            """,
            (
                r["officer_pay"], r["base_salary"], r["deemed_ot"], r["overtime_pay"], r["special_allow"], r["commute_nontax"],
                r["pay_free1"], r["pay_free2"], r["pay_free3"], r["pay_free4"], r["pay_free5"],
                r["pay_free1_is_taxable"], r["pay_free1_is_social_base"], r["pay_free1_is_employment_base"],
                r["pay_free2_is_taxable"], r["pay_free2_is_social_base"], r["pay_free2_is_employment_base"],
                r["pay_free3_is_taxable"], r["pay_free3_is_social_base"], r["pay_free3_is_employment_base"],
                r["pay_free4_is_taxable"], r["pay_free4_is_social_base"], r["pay_free4_is_employment_base"],
                r["pay_free5_is_taxable"], r["pay_free5_is_social_base"], r["pay_free5_is_employment_base"],
                r["travel_saving"], r["deduct_free1"], r["deduct_free2"], r["deduct_free3"], r["deduct_free4"], r["deduct_free5"],
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
        "pay_free1", "pay_free2", "pay_free3", "pay_free4", "pay_free5",
        "pay_free1_is_taxable", "pay_free1_is_social_base", "pay_free1_is_employment_base",
        "pay_free2_is_taxable", "pay_free2_is_social_base", "pay_free2_is_employment_base",
        "pay_free3_is_taxable", "pay_free3_is_social_base", "pay_free3_is_employment_base",
        "pay_free4_is_taxable", "pay_free4_is_social_base", "pay_free4_is_employment_base",
        "pay_free5_is_taxable", "pay_free5_is_social_base", "pay_free5_is_employment_base",
        "travel_saving", "deduct_free1", "deduct_free2", "deduct_free3", "deduct_free4", "deduct_free5",
        "note",
    ]

    sets = ", ".join([f"{c}=?" for c in cols]) + ", updated_at=datetime('now')"
    values = [data.get(c) for c in cols] + [payroll_id]

    cur = conn.cursor()
    cur.execute(f"UPDATE payroll_monthly SET {sets} WHERE payroll_id=?", values)
    conn.commit()

def get_payroll_by_id(conn, payroll_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.*, e.employee_code, e.name_kanji, e.department, e.payday_group
        FROM payroll_monthly p
        JOIN employees e ON e.employee_id = p.employee_id
        WHERE p.payroll_id=?
        """,
        (payroll_id,),
    )
    return cur.fetchone()

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

    if not _column_exists(conn, "employees", "tax_type"):
        conn.execute("ALTER TABLE employees ADD COLUMN tax_type TEXT NOT NULL DEFAULT '甲'")
    if not _column_exists(conn, "employees", "dependents_count"):
        conn.execute("ALTER TABLE employees ADD COLUMN dependents_count INTEGER NOT NULL DEFAULT 0")
    
    if not _column_exists(conn, "employees", "work_prefecture_name"):
        conn.execute("ALTER TABLE employees ADD COLUMN work_prefecture_name TEXT NOT NULL DEFAULT ''")

    # 生年月日（介護保険判定用）
    if not _column_exists(conn, "employees", "birth_date"):
        conn.execute("ALTER TABLE employees ADD COLUMN birth_date TEXT")

    # 入退社・月末在籍要件
    if not _column_exists(conn, "employees", "hire_date"):
        conn.execute("ALTER TABLE employees ADD COLUMN hire_date TEXT")

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

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_schedules (
          payment_schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
          schedule_name       TEXT NOT NULL UNIQUE,
          closing_mode        TEXT NOT NULL,
          pay_day             INTEGER NOT NULL,
          is_active           INTEGER NOT NULL DEFAULT 1,
          created_at          TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
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

    # -------------------------------------------------
    # payroll_bonus
    # -------------------------------------------------
    if not _column_exists(conn, "payroll_bonus", "health_ins_employee"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN health_ins_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "care_ins_employee"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN care_ins_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "childcare_support_employee"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN childcare_support_employee INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "childcare_support_employer"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN childcare_support_employer INTEGER NOT NULL DEFAULT 0")
    if not _column_exists(conn, "payroll_bonus", "pension_ins_employee"):
        conn.execute("ALTER TABLE payroll_bonus ADD COLUMN pension_ins_employee INTEGER NOT NULL DEFAULT 0")
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

    conn.commit()

    seed_social_insurance_item_master(conn)


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


def _calc_taxable_pay_from_payroll_row(r) -> int:
    """課税支給額（簡易）"""
    base = 0
    base += int(r["officer_pay"])
    base += int(r["base_salary"])
    base += int(r["deemed_ot"])
    base += int(r["overtime_pay"])
    base += int(r["special_allow"])
    # commute_nontax は除外
    for i in range(1, 6):
        amt = int(r[f"pay_free{i}"])
        flag = int((row_get(r,f"pay_free{i}_is_taxable", 1) or 1))
        if flag == 1:
            base += amt
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
        taxable_pay = _calc_taxable_pay_from_payroll_row(r)
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

def _calc_emp_ins_base_from_payroll_row(r) -> int:
    """
    雇用保険の基礎賃金（まずは入力値ベースで簡易に）
    - 非課税交通費は除外
    - 自由支給は is_employment_base=1 のもののみ加算
    """
    base = 0

    # 固定支給（非課税交通費 제외）
    base += int(r["officer_pay"])
    base += int(r["base_salary"])
    base += int(r["deemed_ot"])
    base += int(r["overtime_pay"])
    base += int(r["special_allow"])
    # commute_nontax は除外

    # 自由支給（雇保対象フラグ）
    for i in range(1, 6):
        amt = int(r[f"pay_free{i}"])
        flag = int(r[f"pay_free{i}_is_employment_base"])
        if flag == 1:
            base += amt

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

        if applicable:
            base = _calc_emp_ins_base_from_payroll_row(r)
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

        if enrolled:
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


def export_pay_deduct_report_month(conn, target_month: str, file_path: str) -> None:
    """
    支給控除一覧表（対象月・全社員）を縦並びでExcel出力。
    見せ方B:
      健康保険料（介護保険料）→ 子ども・子育て支援金 → 厚生年金保険料 → 雇用保険料
    """
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
            ("自由支給1", row_get(r, "pay_free1", 0)),
            ("自由支給2", row_get(r, "pay_free2", 0)),
            ("自由支給3", row_get(r, "pay_free3", 0)),
            ("自由支給4", row_get(r, "pay_free4", 0)),
            ("自由支給5", row_get(r, "pay_free5", 0)),
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
            ("旅行積立", row_get(r, "travel_saving", 0)),
            ("自由控除1", row_get(r, "deduct_free1", 0)),
            ("自由控除2", row_get(r, "deduct_free2", 0)),
            ("自由控除3", row_get(r, "deduct_free3", 0)),
            ("自由控除4", row_get(r, "deduct_free4", 0)),
            ("自由控除5", row_get(r, "deduct_free5", 0)),
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
    """月次給与1行から総支給額を計算する。"""
    return (
        int(row_get(row, "base_salary", 0) or 0)
        + int(row_get(row, "officer_pay", 0) or 0)
        + int(row_get(row, "special_allow", 0) or 0)
        + int(row_get(row, "deemed_ot", 0) or 0)
        + int(row_get(row, "overtime_pay", 0) or 0)
        + int(row_get(row, "commute_nontax", 0) or 0)
        + int(row_get(row, "pay_free1", 0) or 0)
        + int(row_get(row, "pay_free2", 0) or 0)
        + int(row_get(row, "pay_free3", 0) or 0)
        + int(row_get(row, "pay_free4", 0) or 0)
        + int(row_get(row, "pay_free5", 0) or 0)
    )

def _other_deductions_total(row) -> int:
    """法定控除以外の控除合計。"""
    return (
        int(row_get(row, "travel_saving", 0) or 0)
        + int(row_get(row, "deduct_free1", 0) or 0)
        + int(row_get(row, "deduct_free2", 0) or 0)
        + int(row_get(row, "deduct_free3", 0) or 0)
        + int(row_get(row, "deduct_free4", 0) or 0)
        + int(row_get(row, "deduct_free5", 0) or 0)
    )

def export_wage_ledger_excel(conn, target_month: str, file_path: str) -> None:
    """
    賃金台帳（1ヶ月分）をExcel出力する。
    見せ方B:
      健康保険料（介護保険料）→ 子ども・子育て支援金 → 厚生年金保険料 → 雇用保険料
    """
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
        "自由支給1", "自由支給2", "自由支給3", "自由支給4", "自由支給5",
        "総支給",
        "健康保険料（介護保険料）", "子ども・子育て支援金", "厚生年金保険料", "雇用保険料",
        "所得税", "住民税",
        "旅行積立",
        "自由控除1", "自由控除2", "自由控除3", "自由控除4", "自由控除5",
        "控除合計", "差引支給額",
        "備考"
    ]

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

        deduct_total = (
            health_care
            + childcare
            + pension
            + emp_ins
            + withholding_tax
            + resident_tax
            + _other_deductions_total(r)
        )

        net = gross - deduct_total

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
            int(row_get(r, "pay_free1", 0) or 0),
            int(row_get(r, "pay_free2", 0) or 0),
            int(row_get(r, "pay_free3", 0) or 0),
            int(row_get(r, "pay_free4", 0) or 0),
            int(row_get(r, "pay_free5", 0) or 0),
            gross,
            health_care,
            childcare,
            pension,
            emp_ins,
            withholding_tax,
            resident_tax,
            int(row_get(r, "travel_saving", 0) or 0),
            int(row_get(r, "deduct_free1", 0) or 0),
            int(row_get(r, "deduct_free2", 0) or 0),
            int(row_get(r, "deduct_free3", 0) or 0),
            int(row_get(r, "deduct_free4", 0) or 0),
            int(row_get(r, "deduct_free5", 0) or 0),
            deduct_total,
            net,
            row_get(r, "note", ""),
        ]
        ws.append(data)

    # 数値列
    money_headers = {
        "基本給", "役員報酬", "手当", "残業(みなし)", "残業", "非課税通勤",
        "自由支給1", "自由支給2", "自由支給3", "自由支給4", "自由支給5",
        "総支給",
        "健康保険料（介護保険料）", "子ども・子育て支援金", "厚生年金保険料", "雇用保険料",
        "所得税", "住民税",
        "旅行積立",
        "自由控除1", "自由控除2", "自由控除3", "自由控除4", "自由控除5",
        "控除合計", "差引支給額",
    }
    money_cols_idx = [i for i, h in enumerate(headers, start=1) if h in money_headers]

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for ci in money_cols_idx:
            cell = row[ci - 1]
            cell.number_format = "#,##0"
            cell.alignment = align_right

    # 文字列列
    text_cols_idx = [1, 2, 3, 4, 5, len(headers)]
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for ci in text_cols_idx:
            row[ci - 1].alignment = align_left

    # 列幅
    widths = {
        1: 10, 2: 12, 3: 12, 4: 14, 5: 14,
        6: 12, 7: 12, 8: 12, 9: 12, 10: 12, 11: 12,
        12: 12, 13: 12, 14: 12, 15: 12, 16: 12,
        17: 12,
        18: 18, 19: 14, 20: 14, 21: 12,
        22: 12, 23: 12,
        24: 12, 25: 12, 26: 12, 27: 12, 28: 12, 29: 12,
        30: 12, 31: 12, 32: 24,
    }
    for ci, w in widths.items():
        ws.column_dimensions[get_column_letter(ci)].width = w

    wb.save(file_path)


def export_wage_ledger_year(conn, year: int, file_path: str) -> None:
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
        "自由支給合計",
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
                free_pay_total = (
                    int(row_get(r, "pay_free1", 0) or 0)
                    + int(row_get(r, "pay_free2", 0) or 0)
                    + int(row_get(r, "pay_free3", 0) or 0)
                    + int(row_get(r, "pay_free4", 0) or 0)
                    + int(row_get(r, "pay_free5", 0) or 0)
                )

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
                    free_pay_total,
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
               e.employee_code, e.name_kanji, e.department,
               e.tax_type, e.dependents_count, e.work_prefecture_name
        FROM payroll_bonus b
        JOIN employees e ON e.employee_id = b.employee_id
        WHERE b.target_month=?
        ORDER BY e.employee_code
        """,
        (target_month,),
    )
    return cur.fetchall()


def get_bonus_by_id(conn, bonus_id: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT b.*,
               e.employee_code, e.name_kanji, e.department,
               e.tax_type, e.dependents_count, e.work_prefecture_name
        FROM payroll_bonus b
        JOIN employees e ON e.employee_id = b.employee_id
        WHERE b.bonus_id=?
        """,
        (bonus_id,),
    )
    return cur.fetchone()

def upsert_bonus(conn, target_month: str, pay_date: str, employee_id: int, bonus_amount: int, note: str | None = None):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO payroll_bonus (target_month, pay_date, employee_id, bonus_amount, note)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(target_month, employee_id) DO UPDATE SET
          pay_date=excluded.pay_date,
          bonus_amount=excluded.bonus_amount,
          note=excluded.note,
          updated_at=datetime('now')
        """,
        (target_month, pay_date, employee_id, bonus_amount, note),
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
          SUM(COALESCE(b.social_ins_total_calc, 0)) AS total_social_ins,
          SUM(COALESCE(b.withholding_tax_applied, 0)) AS total_withholding_tax,
          SUM(
            COALESCE(b.bonus_amount, 0)
            - COALESCE(b.social_ins_total_calc, 0)
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
          SUM(COALESCE(b.social_ins_total_calc, 0)) AS total_social_ins,
          SUM(COALESCE(b.withholding_tax_applied, 0)) AS total_withholding_tax,
          SUM(
            COALESCE(b.bonus_amount, 0)
            - COALESCE(b.social_ins_total_calc, 0)
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
          SUM(COALESCE(b.social_ins_total_calc, 0)) AS total_social_ins,
          SUM(COALESCE(b.withholding_tax_applied, 0)) AS total_withholding_tax,
          SUM(
            COALESCE(b.bonus_amount, 0)
            - COALESCE(b.social_ins_total_calc, 0)
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

def list_bonus_rows_by_pay_date(conn, target_month: str, pay_date: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT b.*,
               e.employee_code, e.name_kanji, e.department,
               e.tax_type, e.dependents_count, e.work_prefecture_name
        FROM payroll_bonus b
        JOIN employees e ON e.employee_id = b.employee_id
        WHERE b.target_month = ? AND b.pay_date = ?
        ORDER BY e.employee_id
        """,
        (target_month, pay_date),
    )
    return cur.fetchall()

def delete_bonus(conn, bonus_id: int):
    conn.execute("DELETE FROM payroll_bonus WHERE bonus_id=?", (bonus_id,))
    conn.commit()


def _prev_month(ym: str) -> str:
    # ym: YYYY-MM
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
            e.work_prefecture_name
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

        # 4) 本人負担
        health = round_half_up(std_health * h_rate)
        care = round_half_up(std_health * c_rate) if c_rate > 0 else 0
        childcare_support_emp = round_half_up(std_health * cc_emp_rate) if cc_emp_rate > 0 else 0
        pension = round_half_up(std_pension * p_rate)

        # 5) 事業主負担
        childcare_support_er = round_down(std_health * cc_er_rate) if cc_er_rate > 0 else 0

        # 6) 拠出金（事業主のみ）
        childcare_contribution_er = round_down(std_pension * contribution_rate)

        # 7) 雇用保険は従来どおり賞与支給額ベース
        empins = int(math.floor(amt * emp_rate))

        social_total_calc = health + care + childcare_support_emp + pension + empins

        cur.execute(
            """
            UPDATE payroll_bonus
            SET std_bonus_raw=?,
                std_bonus_health=?,
                std_bonus_pension=?,
                bonus_fiscal_year=?,
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
                childcare_support_er,
                childcare_contribution_er,
                pension,
                empins,
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
            prev_taxable = _calc_taxable_pay_from_payroll_row(prev)
            prev_social = int(row_get(prev, "social_ins_total_calc", 0) or 0)
            prev_after_social = max(0, prev_taxable - prev_social)

        tax_type = row_get(r, "tax_type", "甲")
        deps = int(row_get(r, "dependents_count", 0) or 0)
        rate_percent = _lookup_bonus_rate_percent(table, prev_after_social, tax_type, deps)

        bonus_amt = int(r["bonus_amount"] or 0)
        social = int(row_get(r, "social_ins_total_calc", 0) or 0)
        bonus_after_social = max(0, bonus_amt - social)

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
    雇用保険の月次給与控除判定（賃金対象期間基準）
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
