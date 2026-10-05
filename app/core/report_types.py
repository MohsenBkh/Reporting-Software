# -*- coding: utf-8 -*-
"""انواع گزارش‌های گزارش‌یار (v1.1.0).

گزارش‌یار سه نوع مطالعه را پشتیبانی می‌کند:

- ``heavy``         مطالعات اتصال متقاضیان سنگین (یک مگاوات و بالاتر) — دستورالعمل TAV111-10/00
- ``sectionalizer`` مطالعات نصب سکشنالایزر — ساختار گزارش فعال است (جزئیات تکمیلی متعاقباً)
- ``recloser``      مطالعات نصب ریکلوزر — در برنامه (به‌زودی)

تعریف متمرکز در همین ماژول تا هیچ برچسب/عنوانی در کد پراکنده نشود.
"""
from __future__ import annotations

REPORT_HEAVY = "heavy"
REPORT_SECTIONALIZER = "sectionalizer"
REPORT_RECLOSER = "recloser"

# برچسب کامل (برای کمبو و عناوین)
REPORT_TYPE_LABELS = {
    REPORT_HEAVY: "متقاضیان سنگین (یک مگاوات و بالاتر)",
    REPORT_SECTIONALIZER: "مطالعه سکشنالایزر",
    REPORT_RECLOSER: "مطالعه ریکلوزر",
}

# برچسب کوتاه (برای داشبورد و هدر)
REPORT_TYPE_SHORT = {
    REPORT_HEAVY: "متقاضیان سنگین",
    REPORT_SECTIONALIZER: "سکشنالایزر",
    REPORT_RECLOSER: "ریکلوزر",
}

# عنوان دفترچه روی جلد و سربرگ — مطابق نمونه‌های مرجع هر نوع مطالعه
BOOKLET_TITLES = {
    REPORT_HEAVY: "دفترچه مطالعات تأمین برق به متقاضیان یک مگاوات و بالاتر",
    REPORT_SECTIONALIZER: "گزارش مطالعات نصب سکشنالایزر",
    REPORT_RECLOSER: "گزارش مطالعات نصب ریکلوزر",
}

# انواع فعال (قابل انتخاب برای پروژه جدید)
AVAILABLE_TYPES = (REPORT_HEAVY, REPORT_SECTIONALIZER)
# انواع در دست توسعه — در رابط کاربری نمایش داده می‌شوند ولی هنوز فعال نیستند
PLANNED_TYPES = (REPORT_RECLOSER,)


def booklet_title(report_type: str) -> str:
    """عنوان دفترچه گزارش برای جلد/سربرگ؛ برای نوع ناشناخته، عنوان مصارف سنگین."""
    return BOOKLET_TITLES.get(report_type, BOOKLET_TITLES[REPORT_HEAVY])


def type_label(report_type: str) -> str:
    return REPORT_TYPE_LABELS.get(report_type, REPORT_TYPE_LABELS[REPORT_HEAVY])


def type_short(report_type: str) -> str:
    return REPORT_TYPE_SHORT.get(report_type, REPORT_TYPE_SHORT[REPORT_HEAVY])


def is_heavy(report_type: str) -> bool:
    """آیا پروژه از نوع مطالعات متقاضیان سنگین است؟ (نوع‌های قدیمی نیز سنگین فرض می‌شوند)"""
    return report_type in (REPORT_HEAVY, "", None)


def is_available(report_type: str) -> bool:
    return report_type in AVAILABLE_TYPES
