# -*- coding: utf-8 -*-
"""ابزارهای قالب‌بندی اعداد و متن برای استفاده در همه‌جای برنامه."""
from __future__ import annotations

from typing import Optional


def fmt(value: Optional[float], digits: int = 2, dash: str = "—") -> str:
    """عدد را با تعداد رقم اعشار مشخص قالب‌بندی می‌کند؛ صفرهای انتهاییِ اعشار حذف می‌شوند."""
    if value is None:
        return dash
    try:
        text = f"{float(value):.{digits}f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text if text not in ("", "-") else "0"
    except (TypeError, ValueError):
        return dash


def fmt_pct(value: Optional[float], digits: int = 1, dash: str = "—") -> str:
    if value is None:
        return dash
    return fmt(value, digits)


def signed(value: Optional[float], digits: int = 2) -> str:
    """عدد با علامم برای نمایش تغییرات (مثلاً +۱۲.۵ یا -۳)."""
    if value is None:
        return "—"
    s = fmt(abs(value), digits)
    if value > 0:
        return f"+{s}"
    if value < 0:
        return f"−{s}"  # علامم منفی فارسی
    return "0"


def fmt_int(value: Optional[int | float], dash: str = "—") -> str:
    if value is None:
        return dash
    try:
        return str(int(round(float(value))))
    except (TypeError, ValueError):
        return dash
