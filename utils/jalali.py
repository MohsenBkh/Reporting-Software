# -*- coding: utf-8 -*-
"""ابزار کار با تاریخ شمسی (جلالی)."""
from __future__ import annotations

from typing import Optional

try:
    import jdatetime
    JALALI_AVAILABLE = True
except Exception:  # pragma: no cover
    JALALI_AVAILABLE = False


def today_jalali() -> str:
    """تاریخ امروز به صورت رشته 1405/06/15"""
    if JALALI_AVAILABLE:
        return jdatetime.date.fromgregorian(date=__import__("datetime").date.today()).strftime("%Y/%m/%d")
    return ""


def jalali_month_year(date_str: str = "") -> str:
    """از رشته تاریخ 1405/06/15 عبارت «شهریور 1405» را می‌سازد."""
    months = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
              "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    if not date_str and JALALI_AVAILABLE:
        d = jdatetime.date.fromgregorian(date=__import__("datetime").date.today())
        return f"{months[d.month - 1]} {d.year}"
    parts = str(date_str).replace("-", "/").split("/")
    if len(parts) >= 2:
        try:
            y, m = int(parts[0]), int(parts[1])
            if 1 <= m <= 12:
                return f"{months[m - 1]} {y}"
            return str(y)
        except ValueError:
            return str(date_str)
    return str(date_str)


def jalali_year(date_str: str) -> Optional[int]:
    """سال شمسی از رشته تاریخ؛ None اگر قابل استخراج نباشد."""
    try:
        return int(str(date_str).replace("-", "/").split("/")[0])
    except (ValueError, IndexError):
        return None
