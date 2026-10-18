# -*- coding: utf-8 -*-
"""فهرست بخش‌های گزارش و نگاشت شکل‌ها به بخش‌ها — نسخه ۱.۲.۰.

هر شکل (تصویر) می‌تواند به یک «بخش گزارش» نسبت داده شود و در آن بخش با
ترتیب (اولویت) مشخص قرار گیرد. اگر شکلی بخش مشخصی نداشته باشد، بر پایهٔ
«نوع» آن به بخش پیش‌فرض راهنما می‌رود (سازگاری کامل با پروژه‌های قدیمی).
"""
from __future__ import annotations

from typing import Optional

# کلید بخش → عنوان فارسی (ترتیب = ترتیب ظهور در گزارش)
#
# ترتیب بخش‌های «متقاضیان سنگین» دقیقاً مطابق گزارش مرجع مهر ۱۴۰۵
# (دفترچه مطالعات تأمین برق به متقاضیان یک مگاوات و بالاتر) تنظیم شده است:
#   ۱ مقدمه — ۲ تحلیل وضعیت بارگذاری — ۳ پیش‌بینی پیک بار —
#   ۴ ایستگاه‌های نزدیک به محل تقاضا — ۵ خطوط نزدیک به محل تقاضا —
#   ۶ نتایج پخش بار قبل — ۷ نتایج پخش بار بعد —
#   ۸ کنترل بارگذاری فیدر و راهکارهای تعدیل بار — ۹ نتیجه‌گیری و پیشنهادات
# بخش‌های تکمیلی موتور مطالعه (اطلاعات تقاضا، همزمانی، نکات تحلیلی،
# سناریوها و اقتصاد) پس از اسکلت اصلی می‌آیند و به‌طور پیش‌فرض خاموش‌اند
# (فعال‌سازی از «تنظیمات → بخش‌های گزارش»).
REPORT_SECTIONS: list[tuple[str, str]] = [
    ("intro", "مقدمه"),
    ("loading", "تحلیل وضعیت بارگذاری"),
    ("forecast", "پیش‌بینی بار"),
    ("study_substations", "ایستگاه‌های نزدیک به محل تقاضا"),
    ("study_lines", "خطوط نزدیک به محل تقاضا"),
    ("before", "نتایج پخش بار — قبل"),
    ("after", "نتایج پخش بار — بعد"),
    ("study_loading", "کنترل بارگذاری فیدر و راهکارهای تعدیل بار"),
    ("study_demand", "اطلاعات تقاضا"),
    ("study_coincident", "متقاضیان همزمان"),
    ("study_analysis", "نکات تحلیلی"),
    ("study_scenarios", "سناریوهای تأمین"),
    ("study_economics", "بررسی اقتصادی"),
    ("study_conclusion", "نتیجه‌گیری و پیشنهادات"),
    ("conclusion", "جمع‌بندی"),
    ("appendix", "پیوست‌ها"),
    # قالب سکشنالایزر (v1.3.0) — فقط در گزارش‌های نوع «سکشنالایزر» ظاهر می‌شود
    ("secz_overview", "کلیات و مقدمه"),
    ("secz_network", "شبکه و محل نصب"),
    ("secz_settings", "سطح اتصال کوتاه و تنظیمات حفاظتی"),
    ("secz_coordination", "هماهنگی حفاظت"),
    ("secz_conclusion", "نتیجه‌گیری و پیشنهادات"),
]

SECTION_LABELS: dict[str, str] = dict(REPORT_SECTIONS)
SECTION_ORDER: list[str] = [key for key, _label in REPORT_SECTIONS]

# شکل بدون «محل قرارگیری» صریح: به کدام بخش‌ها می‌تواند برود؟
# ترتیب مهم است: بخشی که اول ساخته شود، شکل را برمی‌دارد (سازگاری با نسخه‌های قبل).
DEFAULT_SECTIONS_BY_KIND: dict[str, list[str]] = {
    "location": ["intro"],
    "network": ["intro", "loading"],
    "profile": ["loading"],
    "forecast": ["forecast"],
    "before": ["before"],
    "after": ["after"],
    "other": ["after"],
}


def section_label(key: str) -> str:
    if not key:
        return "— (خودکار بر اساس نوع)"
    return SECTION_LABELS.get(key, key)


def section_of_image(image) -> Optional[str]:
    """بخش صریح شکل (None اگر تعیین نشده باشد)."""
    key = (getattr(image, "section_key", "") or "").strip()
    return key or None


def default_sections_of_kind(kind: str) -> list[str]:
    return DEFAULT_SECTIONS_BY_KIND.get(kind or "other", DEFAULT_SECTIONS_BY_KIND["other"])


def kind_options() -> list[tuple[str, str]]:
    """گزینه‌های «نوع شکل» — از مدل داده خوانده می‌شود (جلوگیری از تکرار)."""
    from app.core.models import IMAGE_KINDS
    return list(IMAGE_KINDS.items())
