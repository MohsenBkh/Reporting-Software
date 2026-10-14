# -*- coding: utf-8 -*-
"""ثبت «نوع گزارش» — نسخه ۲.۰.۰.

گزارش‌یار این قالب‌های گزارش را پشتیبانی می‌کند:

* ``متقاضیان سنگین`` (پیش‌فرض) — دفترچه مطالعات تأمین برق به متقاضیان
  یک مگاوات و بالاتر (کاملاً پیاده‌سازی شده).
* ``سکشنالایزر`` — گزارش مطالعه نصب سکشنالایزر.
* ``ریکلوزر`` — گزارش مطالعه ریکلوزر (از نسخه ۲.۰.۰ فعال است).
* ``ترکیبی ریکلوزر و سکشنالایزر`` — یک گزارش واحد برای دو مطالعهٔ حفاظتی
  (از نسخه ۲.۰.۰؛ مولد: ``app/report/composer.py``).

هیچ منطق گزارش‌سازی‌ای در این فایل نیست؛ فقط ثبت، برچسب‌ها و وضعیت
دسترس‌پذیری هر قالب. اسکلت تولید گزارش سکشنالایزر در
``app/report/sectionalizer.py`` و مولد مطالعات حفاظتی در
``app/report/composer.py`` قرار دارد.

توجه: انتخاب هم‌زمان چند مطالعه در ``Workspace`` (workspace.json) نگهداری می‌شود؛
``report_type`` فقط قالب گزارشِ در حال تولید را مشخص می‌کند و برای سازگاری با
پروژه‌های قبلی حفظ شده است.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# کلید انواع گزارش
# ---------------------------------------------------------------------------
REPORT_TYPE_HEAVY = "heavy"                # متقاضیان سنگین (پیش‌فرض)
REPORT_TYPE_SECTIONALIZER = "sectionalizer"  # مطالعه نصب سکشنالایزر
REPORT_TYPE_RECLOSER = "recloser"          # مطالعه ریکلوزر
REPORT_TYPE_COMBINED_PROTECTION = "combined_protection"  # گزارش ترکیبی ریکلوزر + سکشنالایزر

REPORT_TYPE_LABELS: dict[str, str] = {
    REPORT_TYPE_HEAVY: "متقاضیان سنگین (یک مگاوات و بالاتر)",
    REPORT_TYPE_SECTIONALIZER: "مطالعه سکشنالایزر",
    REPORT_TYPE_RECLOSER: "مطالعه ریکلوزر",
    REPORT_TYPE_COMBINED_PROTECTION: "گزارش ترکیبی ریکلوزر و سکشنالایزر",
}

# عنوان دفترچهٔ مندرج در جلد، سربرگ و مشخصات سند — برای هر قالب
REPORT_TYPE_BOOKLETS: dict[str, str] = {
    REPORT_TYPE_HEAVY: "دفترچه مطالعات تأمین برق به متقاضیان یک مگاوات و بالاتر",
    REPORT_TYPE_SECTIONALIZER: "گزارش مطالعه نصب سکشنالایزر",
    REPORT_TYPE_RECLOSER: "گزارش مطالعه نصب ریکلوزر",
    REPORT_TYPE_COMBINED_PROTECTION: "دفترچه مطالعات ریکلوزر و سکشنالایزر",
}

# قالب‌هایی که پیاده‌سازی آن‌ها تکمیل شده است.
_IMPLEMENTED = {REPORT_TYPE_HEAVY, REPORT_TYPE_SECTIONALIZER,
                REPORT_TYPE_RECLOSER, REPORT_TYPE_COMBINED_PROTECTION}

# قالب‌هایی که با مولد مطالعات حفاظتی (ReportComposer) تولید می‌شوند
PROTECTION_COMPOSER_TYPES = {REPORT_TYPE_RECLOSER, REPORT_TYPE_COMBINED_PROTECTION}


# ---------------------------------------------------------------------------
def report_type_label(report_type: str) -> str:
    """برچسب فارسی نوع گزارش (کلید ناشناخته = متن کلید)."""
    return REPORT_TYPE_LABELS.get(report_type or "", report_type or "")


def booklet_title(report_type: str) -> str:
    """عنوان دفترچهٔ گزارش برای درج در جلد/سربرگ/مشخصات سند."""
    return REPORT_TYPE_BOOKLETS.get(report_type or "",
                                    REPORT_TYPE_BOOKLETS[REPORT_TYPE_HEAVY])


def is_implemented(report_type: str) -> bool:
    """آیا قالب گزارش پیاده‌سازی شده است؟"""
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
