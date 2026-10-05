# -*- coding: utf-8 -*-
"""ثبت «نوع گزارش» — نسخه ۱.۳.۰.

گزارش‌یار سه قالب گزارش را پشتیبانی می‌کند:

* ``متقاضیان سنگین`` (پیش‌فرض) — دفترچه مطالعات تأمین برق به متقاضیان
  یک مگاوات و بالاتر (کاملاً پیاده‌سازی شده).
* ``سکشنالایزر`` — قالب گزارش مطالعه نصب سکشنالایزر (اسکلت فعال؛ جزئیات
  تکمیلی توسط کارفرما ارسال می‌شود و ساختار آمادهٔ گسترش است).
* ``ریکلوزر`` — قالب گزارش مطالعه ریکلوزر (در برنامه؛ هنوز پیاده‌سازی نشده).

هیچ منطق گزارش‌سازی‌ای در این فایل نیست؛ فقط ثبت، برچسب‌ها و وضعیت
دسترس‌پذیری هر قالب. اسکلت تولید گزارش سکشنالایزر در
``app/report/sectionalizer.py`` قرار دارد.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# کلید انواع گزارش
# ---------------------------------------------------------------------------
REPORT_TYPE_HEAVY = "heavy"                # متقاضیان سنگین (پیش‌فرض)
REPORT_TYPE_SECTIONALIZER = "sectionalizer"  # مطالعه نصب سکشنالایزر
REPORT_TYPE_RECLOSER = "recloser"          # مطالعه ریکلوزر (در برنامه)

REPORT_TYPE_LABELS: dict[str, str] = {
    REPORT_TYPE_HEAVY: "متقاضیان سنگین (یک مگاوات و بالاتر)",
    REPORT_TYPE_SECTIONALIZER: "مطالعه سکشنالایزر",
    REPORT_TYPE_RECLOSER: "مطالعه ریکلوزر",
}

# عنوان دفترچهٔ مندرج در جلد، سربرگ و مشخصات سند — برای هر قالب
REPORT_TYPE_BOOKLETS: dict[str, str] = {
    REPORT_TYPE_HEAVY: "دفترچه مطالعات تأمین برق به متقاضیان یک مگاوات و بالاتر",
    REPORT_TYPE_SECTIONALIZER: "گزارش مطالعه نصب سکشنالایزر",
    REPORT_TYPE_RECLOSER: "گزارش مطالعه نصب ریکلوزر",
}

# قالب‌هایی که پیاده‌سازی آن‌ها تکمیل شده است.
_IMPLEMENTED = {REPORT_TYPE_HEAVY, REPORT_TYPE_SECTIONALIZER}


# ---------------------------------------------------------------------------
def report_type_label(report_type: str) -> str:
    """برچسب فارسی نوع گزارش (کلید ناشناخته = متن کلید)."""
    return REPORT_TYPE_LABELS.get(report_type or "", report_type or "")


def booklet_title(report_type: str) -> str:
    """عنوان دفترچهٔ گزارش برای درج در جلد/سربرگ/مشخصات سند."""
    return REPORT_TYPE_BOOKLETS.get(report_type or "",
                                    REPORT_TYPE_BOOKLETS[REPORT_TYPE_HEAVY])


def is_implemented(report_type: str) -> bool:
    """آیا قالب گزارش پیاده‌سازی شده است؟ (ریکلوزر هنوز خیر)"""
    return (report_type or REPORT_TYPE_HEAVY) in _IMPLEMENTED


def pending_message(report_type: str) -> str:
    """پیام استاندارد برای قالب‌های هنوز پیاده‌سازی‌نشده."""
    return (f"قالب گزارش «{report_type_label(report_type)}» هنوز پیاده‌سازی "
            "نشده است و در نسخه‌های بعدی اضافه می‌شود.")


def normalize(report_type) -> str:
    """نوع گزارش معتبر؛ مقدار خالی/ناشناخته به پیش‌فرض (متقاضیان سنگین) برمی‌گردد."""
    if report_type in REPORT_TYPE_LABELS:
        return report_type
    return REPORT_TYPE_HEAVY
