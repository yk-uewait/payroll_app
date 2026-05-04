-- Employees
CREATE TABLE IF NOT EXISTS employees (
  employee_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_code    TEXT UNIQUE,
  name_kanji       TEXT NOT NULL,
  department       TEXT,
  department_id    INTEGER,
  position_id      INTEGER,
  employment_type_id INTEGER,
  payday_group     INTEGER NOT NULL DEFAULT 25,  -- 15 or 25
  payment_schedule_id INTEGER,
  is_deleted       INTEGER NOT NULL DEFAULT 0,
  deleted_at       TEXT,
  tax_type         TEXT NOT NULL DEFAULT '甲',
  dependents_count INTEGER NOT NULL DEFAULT 0,
  birth_date       TEXT,  -- YYYY-MM-DD
  hire_date        TEXT,
  leave_date       TEXT,
  retirement_processed INTEGER NOT NULL DEFAULT 0,
  memo             TEXT,
  std_monthly_wage INTEGER NOT NULL DEFAULT 0,
  std_pension_wage INTEGER NOT NULL DEFAULT 0,
  created_at       TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
  work_prefecture_name TEXT NOT NULL DEFAULT '',
  address_city     TEXT NOT NULL DEFAULT '',
  address_detail   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS payment_schedules (
  payment_schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
  schedule_name       TEXT NOT NULL UNIQUE,
  closing_mode        TEXT NOT NULL,      -- 'same_month' or 'next_month'
  pay_day             INTEGER NOT NULL,   -- 1..28 推奨
  is_active           INTEGER NOT NULL DEFAULT 1,
  memo                TEXT,
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Monthly payroll input (minimal)
CREATE TABLE IF NOT EXISTS payroll_monthly (
  payroll_id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  target_month                 TEXT NOT NULL,            -- YYYY-MM
  employee_id                  INTEGER NOT NULL,
  wage_period_start            TEXT NOT NULL,            -- YYYY-MM-01
  wage_period_end              TEXT NOT NULL,            -- YYYY-MM-lastday
  pay_date_auto                TEXT NOT NULL,            -- computed (YYYY-MM-DD)
  pay_date_override            TEXT,                     -- optional
  pay_date_applied             TEXT NOT NULL,            -- auto or override
  pay_date_override_reason     TEXT,
  pay_date_overridden_at       TEXT,
  pay_date_overridden_by       TEXT,

  -- Pay items (minimal: fixed + 5 free)
  officer_pay                  INTEGER NOT NULL DEFAULT 0,
  base_salary                  INTEGER NOT NULL DEFAULT 0,
  deemed_ot                    INTEGER NOT NULL DEFAULT 0,
  overtime_pay                 INTEGER NOT NULL DEFAULT 0,
  special_allow                INTEGER NOT NULL DEFAULT 0,
  commute_nontax               INTEGER NOT NULL DEFAULT 0,

  pay_free1                    INTEGER NOT NULL DEFAULT 0,
  pay_free2                    INTEGER NOT NULL DEFAULT 0,
  pay_free3                    INTEGER NOT NULL DEFAULT 0,
  pay_free4                    INTEGER NOT NULL DEFAULT 0,
  pay_free5                    INTEGER NOT NULL DEFAULT 0,

  -- Free pay attributes (tax/social/employment insurance base)
  pay_free1_is_taxable         INTEGER NOT NULL DEFAULT 1,
  pay_free1_is_social_base     INTEGER NOT NULL DEFAULT 1,
  pay_free1_is_employment_base INTEGER NOT NULL DEFAULT 1,

  pay_free2_is_taxable         INTEGER NOT NULL DEFAULT 1,
  pay_free2_is_social_base     INTEGER NOT NULL DEFAULT 1,
  pay_free2_is_employment_base INTEGER NOT NULL DEFAULT 1,

  pay_free3_is_taxable         INTEGER NOT NULL DEFAULT 1,
  pay_free3_is_social_base     INTEGER NOT NULL DEFAULT 1,
  pay_free3_is_employment_base INTEGER NOT NULL DEFAULT 1,

  pay_free4_is_taxable         INTEGER NOT NULL DEFAULT 1,
  pay_free4_is_social_base     INTEGER NOT NULL DEFAULT 1,
  pay_free4_is_employment_base INTEGER NOT NULL DEFAULT 1,

  pay_free5_is_taxable         INTEGER NOT NULL DEFAULT 1,
  pay_free5_is_social_base     INTEGER NOT NULL DEFAULT 1,
  pay_free5_is_employment_base INTEGER NOT NULL DEFAULT 1,

  -- Deductions: travel saving + 5 free
  travel_saving                INTEGER NOT NULL DEFAULT 0,
  deduct_free1                 INTEGER NOT NULL DEFAULT 0,
  deduct_free2                 INTEGER NOT NULL DEFAULT 0,
  deduct_free3                 INTEGER NOT NULL DEFAULT 0,
  deduct_free4                 INTEGER NOT NULL DEFAULT 0,
  deduct_free5                 INTEGER NOT NULL DEFAULT 0,

  -- Employment insurance
  emp_ins_base                 INTEGER NOT NULL DEFAULT 0,
  emp_ins_rate_employee        REAL NOT NULL DEFAULT 0,
  emp_ins_employee             INTEGER NOT NULL DEFAULT 0,
  emp_ins_rate_employer        REAL NOT NULL DEFAULT 0,
  emp_ins_employer             INTEGER NOT NULL DEFAULT 0,

  -- Social insurance (compatibility columns)
  health_ins_employee          INTEGER NOT NULL DEFAULT 0,
  care_ins_employee            INTEGER NOT NULL DEFAULT 0,
  childcare_support_employee   INTEGER NOT NULL DEFAULT 0,
  childcare_support_employer   INTEGER NOT NULL DEFAULT 0,
  pension_ins_employee         INTEGER NOT NULL DEFAULT 0,

  -- Legacy / compatibility totals
  social_ins_total3            INTEGER NOT NULL DEFAULT 0,
  social_ins_total_calc        INTEGER NOT NULL DEFAULT 0,

  -- Resident tax
  resident_tax_auto            INTEGER NOT NULL DEFAULT 0,
  resident_tax_override        INTEGER,
  resident_tax_applied         INTEGER NOT NULL DEFAULT 0,
  resident_tax_override_reason TEXT,

  -- Withholding tax
  withholding_tax_auto         INTEGER NOT NULL DEFAULT 0,
  withholding_tax_override     INTEGER,
  withholding_tax_applied      INTEGER NOT NULL DEFAULT 0,
  withholding_tax_override_reason TEXT,

  note                         TEXT,

  created_at                   TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at                   TEXT NOT NULL DEFAULT (datetime('now')),

  UNIQUE(target_month, employee_id),
  FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
);

-- Resident tax history per employee (start month based)
CREATE TABLE IF NOT EXISTS resident_tax_history (
  resident_tax_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id       INTEGER NOT NULL,
  start_month       TEXT NOT NULL,   -- YYYY-MM
  amount            INTEGER NOT NULL,
  note              TEXT,
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(employee_id, start_month),
  FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
);

-- Employment insurance rate master (effective from start_month)
CREATE TABLE IF NOT EXISTS employment_insurance_rates (
  rate_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  start_month    TEXT NOT NULL UNIQUE,  -- YYYY-MM
  employee_rate  REAL NOT NULL,         -- 例: 0.006 (0.6%)
  employer_rate  REAL NOT NULL,         -- 将来用（まずは保存だけ）
  note           TEXT,
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Social insurance rates master (effective from start_month)
CREATE TABLE IF NOT EXISTS social_insurance_rates (
  rate_id              INTEGER PRIMARY KEY AUTOINCREMENT,
  start_month          TEXT NOT NULL UNIQUE,   -- YYYY-MM
  health_employee      REAL NOT NULL,          -- 例: 0.04995（本人負担）
  pension_employee     REAL NOT NULL,          -- 例: 0.0915（本人負担）
  care_employee        REAL NOT NULL DEFAULT 0,
  childcare_employee   REAL NOT NULL DEFAULT 0,
  childcare_employer   REAL NOT NULL DEFAULT 0,
  note                 TEXT,
  created_at           TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Bonus payroll (pro way: separate table)
CREATE TABLE IF NOT EXISTS payroll_bonus (
  bonus_id                    INTEGER PRIMARY KEY AUTOINCREMENT,
  target_month                TEXT NOT NULL,            -- YYYY-MM
  pay_date                    TEXT NOT NULL DEFAULT '', -- YYYY-MM-DD
  employee_id                 INTEGER NOT NULL,

  bonus_amount                INTEGER NOT NULL DEFAULT 0,
  note                        TEXT,

  -- Insurance (employee share) - compatibility columns
  health_ins_employee         INTEGER NOT NULL DEFAULT 0,
  care_ins_employee           INTEGER NOT NULL DEFAULT 0,
  childcare_support_employee  INTEGER NOT NULL DEFAULT 0,
  childcare_support_employer  INTEGER NOT NULL DEFAULT 0,
  pension_ins_employee        INTEGER NOT NULL DEFAULT 0,
  emp_ins_employee            INTEGER NOT NULL DEFAULT 0,

  -- Calculated totals
  social_ins_total_calc       INTEGER NOT NULL DEFAULT 0,

  -- Withholding tax
  withholding_tax_auto        INTEGER NOT NULL DEFAULT 0,
  withholding_tax_override    INTEGER,
  withholding_tax_applied     INTEGER NOT NULL DEFAULT 0,
  withholding_tax_override_reason TEXT,

  created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at                  TEXT NOT NULL DEFAULT (datetime('now')),

  UNIQUE(target_month, employee_id),
  FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
);

-- =========================================================
-- Social insurance item master / dynamic detail
-- =========================================================

CREATE TABLE IF NOT EXISTS social_insurance_item_master (
  item_code           TEXT PRIMARY KEY,             -- health / care / childcare / pension
  item_name           TEXT NOT NULL,
  applies_to_monthly  INTEGER NOT NULL DEFAULT 1,
  applies_to_bonus    INTEGER NOT NULL DEFAULT 1,
  base_type           TEXT NOT NULL,                -- std_health / std_pension
  is_tax_deductible   INTEGER NOT NULL DEFAULT 1,   -- 源泉税控除対象か
  sort_order          INTEGER NOT NULL DEFAULT 0,   -- 表示順
  is_active           INTEGER NOT NULL DEFAULT 1,
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS social_insurance_item_rates (
  rate_id             INTEGER PRIMARY KEY AUTOINCREMENT,
  item_code           TEXT NOT NULL,
  start_month         TEXT NOT NULL,                -- YYYY-MM
  employee_rate       REAL NOT NULL DEFAULT 0,
  employer_rate       REAL NOT NULL DEFAULT 0,
  note                TEXT,
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(item_code, start_month),
  FOREIGN KEY(item_code) REFERENCES social_insurance_item_master(item_code)
);

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
);

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
);

CREATE TABLE IF NOT EXISTS social_insurance_rates_v2 (
  rate_id              INTEGER PRIMARY KEY AUTOINCREMENT,
  start_month          TEXT NOT NULL,              -- YYYY-MM
  prefecture_name      TEXT NOT NULL DEFAULT 'DEFAULT',
  health_employee      REAL NOT NULL DEFAULT 0,
  pension_employee     REAL NOT NULL DEFAULT 0,
  care_employee        REAL NOT NULL DEFAULT 0,
  childcare_employee   REAL NOT NULL DEFAULT 0,
  childcare_employer   REAL NOT NULL DEFAULT 0,
  note                 TEXT,
  created_at           TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at           TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(start_month, prefecture_name)
);

CREATE TABLE IF NOT EXISTS company_settings (
  id            INTEGER PRIMARY KEY CHECK (id = 1),
  company_name  TEXT NOT NULL DEFAULT '',
  company_kana  TEXT NOT NULL DEFAULT '',
  postal_code   TEXT NOT NULL DEFAULT '',
  address       TEXT NOT NULL DEFAULT '',
  phone         TEXT NOT NULL DEFAULT '',
  memo          TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS departments (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE,
  display_order INTEGER NOT NULL DEFAULT 0,
  is_active     INTEGER NOT NULL DEFAULT 1,
  memo          TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS positions (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE,
  display_order INTEGER NOT NULL DEFAULT 0,
  is_active     INTEGER NOT NULL DEFAULT 1,
  memo          TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS employment_types (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE,
  display_order INTEGER NOT NULL DEFAULT 0,
  is_active     INTEGER NOT NULL DEFAULT 1,
  memo          TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payroll_item_categories (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  code          TEXT NOT NULL UNIQUE,
  name          TEXT NOT NULL,
  item_kind     TEXT NOT NULL,
  display_order INTEGER NOT NULL DEFAULT 0,
  is_active     INTEGER NOT NULL DEFAULT 1,
  memo          TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payroll_items (
  id                            INTEGER PRIMARY KEY AUTOINCREMENT,
  code                          TEXT NOT NULL UNIQUE,
  name                          TEXT NOT NULL,
  item_kind                     TEXT NOT NULL,
  category_id                   INTEGER,
  is_system                     INTEGER NOT NULL DEFAULT 0,
  is_active                     INTEGER NOT NULL DEFAULT 1,
  is_taxable                    INTEGER NOT NULL DEFAULT 0,
  is_social_insurance_base      INTEGER NOT NULL DEFAULT 0,
  is_employment_insurance_base  INTEGER NOT NULL DEFAULT 0,
  is_commute                    INTEGER NOT NULL DEFAULT 0,
  display_order                 INTEGER NOT NULL DEFAULT 0,
  memo                          TEXT,
  created_at                    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at                    TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(category_id) REFERENCES payroll_item_categories(id)
);

CREATE TABLE IF NOT EXISTS payroll_item_assignments (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id             INTEGER NOT NULL,
  target_type         TEXT NOT NULL DEFAULT 'all',
  department_id       INTEGER,
  position_id         INTEGER,
  employment_type_id  INTEGER,
  employee_id         INTEGER,
  action              TEXT NOT NULL DEFAULT 'include',
  is_active           INTEGER NOT NULL DEFAULT 1,
  display_order       INTEGER NOT NULL DEFAULT 0,
  memo                TEXT,
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(item_id) REFERENCES payroll_items(id),
  FOREIGN KEY(department_id) REFERENCES departments(id),
  FOREIGN KEY(position_id) REFERENCES positions(id),
  FOREIGN KEY(employment_type_id) REFERENCES employment_types(id),
  FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
);

CREATE TABLE IF NOT EXISTS employee_payroll_item_standard_values (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  employee_id   INTEGER NOT NULL,
  item_id       INTEGER NOT NULL,
  start_month   TEXT NOT NULL,
  amount        INTEGER NOT NULL DEFAULT 0,
  is_active     INTEGER NOT NULL DEFAULT 1,
  memo          TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(employee_id, item_id, start_month),
  FOREIGN KEY(employee_id) REFERENCES employees(employee_id),
  FOREIGN KEY(item_id) REFERENCES payroll_items(id)
);

CREATE TABLE IF NOT EXISTS payroll_monthly_item_values (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  monthly_id    INTEGER NOT NULL,
  employee_id   INTEGER NOT NULL,
  year          INTEGER NOT NULL,
  month         INTEGER NOT NULL,
  item_id       INTEGER NOT NULL,
  item_kind     TEXT NOT NULL,
  amount        INTEGER NOT NULL DEFAULT 0,
  source        TEXT NOT NULL DEFAULT 'manual',
  is_locked     INTEGER NOT NULL DEFAULT 0,
  memo          TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(monthly_id, item_id),
  FOREIGN KEY(monthly_id) REFERENCES payroll_monthly(payroll_id),
  FOREIGN KEY(employee_id) REFERENCES employees(employee_id),
  FOREIGN KEY(item_id) REFERENCES payroll_items(id)
);
