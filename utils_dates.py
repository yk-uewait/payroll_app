from __future__ import annotations
import calendar
from dataclasses import dataclass
from datetime import date, timedelta

import jpholiday

@dataclass(frozen=True)
class MonthInfo:
    target_month: str         # YYYY-MM
    start: date               # 1st
    end: date                 # last day

def parse_month(yyyy_mm: str) -> MonthInfo:
    y, m = map(int, yyyy_mm.split("-"))
    last = calendar.monthrange(y, m)[1]
    return MonthInfo(target_month=yyyy_mm, start=date(y, m, 1), end=date(y, m, last))

def is_business_day(d: date) -> bool:
    if d.weekday() >= 5:  # Sat/Sun
        return False
    if jpholiday.is_holiday(d):
        return False
    return True

def adjust_to_prev_business_day(d: date) -> date:
    cur = d
    while not is_business_day(cur):
        cur -= timedelta(days=1)
    return cur

def compute_pay_date(target_month: str, payday_day: int) -> date:
    mi = parse_month(target_month)
    d = date(mi.start.year, mi.start.month, payday_day)
    return adjust_to_prev_business_day(d)
