# -*- coding: utf-8 -*-
"""فهرست بخش‌های گزارش و نگاشت شکل‌ها به بخش‌ها — نسخه ۱.۲.۰.

هر شکل (تصویر) می‌تواند به یک «بخش گزارش» نسبت داده شود و در آن بخش با
ترتیب (اولویت) مشخص قرار گیرد. اگر شکلی بخش مشخصی نداشته باشد، بر پایهٔ
«نوع» آن به بخش پیش‌فرض راهنما می‌رود (سازگاری کامل با پروژه‌های قدیمی).
"""
from __future__ import annotations

from typing import Optional

# کلید بخش → عنوان فارسی (ترتیب = ترتیب ظهور در گزارش)
REPORT_SECTIONS: list[tuple[str, str]] = [
    ("intro", "مقدمه"),
    ("loading", "تحلیل وضعیت بارگذاری"),
    ("forecast", "پیش‌بینی بار"),
    ("before", "نتایج پخش بار — قبل"),
    ("after", "نتایج پخش بار — بعد"),
    ("study_demand", "مطالعه: اطلاعات تقاضا"),
    ("study_substations", "مطالعه: ایستگاه‌های نزدیک"),
    ("study_lines", "مطالعه: خطوط نزدیک"),
    ("study_coincident", "مطالعه: متقاضیان همزمان"),
    ("study_loading", "مطالعه: بارگذاری فیدر و راهکارهای تعدیل بار"),
    ("study_analysis", "مطالعه: نکات تحلیلی"),
    ("study_scenarios", "مطالعه: سناریوهای تأمین"),
    ("study_economics", "مطالعه: بررسی اقتصادی"),
    ("study_conclusion", "مطالعه: نتیجه‌گیری و پیشنهادات"),
    ("conclusion", "جمع‌بندی"),
    ("appendix", "پیوست‌ها"),
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
