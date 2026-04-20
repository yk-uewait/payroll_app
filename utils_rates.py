# utils_rates.py
import re

def parse_percent_to_rate(s: str) -> float:
    """
    画面入力（%単位）→ DB保存用（比率）に変換する。
    例) '0.55' -> 0.0055, '0.55%' -> 0.0055, '55' -> 0.55
    仕様：常に「%として」解釈する（=必ず /100）
    """
    if s is None:
        return 0.0

    t = str(s).strip()
    if t == "":
        return 0.0

    # 全角/記号ゆれ吸収
    t = t.replace("％", "%")
    # 数字/小数点/マイナス/% 以外を除去（念のため）
    t = re.sub(r"[^0-9\.\-%]", "", t)

    if t.endswith("%"):
        t = t[:-1].strip()

    val = float(t)
    return val / 100.0


def format_rate_to_percent_text(rate: float, decimals: int = 2) -> str:
    """
    DB保存用（比率）→ 画面表示（%単位文字列）
    例) 0.0055 -> '0.55'
    """
    if rate is None:
        rate = 0.0
    return f"{rate * 100:.{decimals}f}"