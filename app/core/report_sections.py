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
    # مطالعات حفاظتی (v2.0.0) — گزارش ریکلوزر / سکشنالایزر / ترکیبی (app/report/composer.py)
    # ترتیب فصل‌ها مطابق دفترچه نمونه «احداث ریکلوزر — فیدر ۴ خلخال»:
    # مقدمه ← مشخصات شبکه ← وضعیت حفاظتی موجود ← جانمایی تجهیزات ← مطالعه ←
    # هماهنگی حفاظتی ← سناریوی عملکرد
    ("prot_intro", "حفاظت — مقدمه"),
    ("prot_network", "حفاظت — مشخصات شبکه"),
    ("prot_existing", "حفاظت — وضعیت حفاظتی موجود"),
    ("prot_placement", "حفاظت — جانمایی تجهیزات"),
    ("prot_recloser", "حفاظت — مطالعه ریکلوزر"),
    ("prot_sectionalizer", "حفاظت — مطالعه سکشنالایزر"),
    ("prot_coordination", "حفاظت — هماهنگی حفاظتی"),
    ("prot_scenario", "حفاظت — سناریوی عملکرد"),
    ("prot_conclusion", "حفاظت — جمع‌بندی"),
    ("prot_recommendation", "حفاظت — پیشنهاد نهایی"),
    ("prot_trace", "حفاظت — پیوست ردیابی یافته‌ها"),
    # v2.2.0 — پیوست برگه تنظیمات نهایی (خروجی نرم‌افزار IDMT)
    ("prot_settings_sheet", "حفاظت — پیوست برگه تنظیمات"),
    # v2.4.0 — مطالعه «توسعه و اصلاح فیدر» (دفترچه مطالعات توسعه و اصلاح شبکه)
    # ترتیب فصل‌ها مطابق دفترچه‌های نمونه (اصلاح خط اوچ‌بلاغ / فیدر جدید آغدام):
    # مقدمه ← مشخصات شبکه و وضعیت موجود ← پخش بار قبل ← راه‌حل پیشنهادی ← پخش بار بعد ← نتیجه‌گیری
    ("fd_intro", "توسعه فیدر — مقدمه"),
    ("fd_network", "توسعه فیدر — مشخصات شبکه و وضعیت موجود"),
    ("fd_before", "توسعه فیدر — پخش بار قبل از اصلاح"),
    ("fd_plan", "توسعه فیدر — راه‌حل پیشنهادی (شرح طرح)"),
    ("fd_after", "توسعه فیدر — پخش بار بعد از اصلاح"),
    ("fd_conclusion", "توسعه فیدر — نتیجه‌گیری"),
]

# شکل بدون محل صریح در گزارش‌های حفاظتی: نوع شکل ← بخش پیش‌فرض
PROTECTION_DEFAULT_SECTION_BY_KIND: dict[str, str] = {
    "location": "prot_placement", "network": "prot_network", "other": "prot_coordination",
    "single_line": "prot_network", "tcc": "prot_coordination", "placement": "prot_placement",
    "sequence": "prot_scenario", "settings_sheet": "prot_settings_sheet",
}

# v2.4.0 — شکل بدون محل صریح در گزارش «توسعه و اصلاح فیدر»: نوع شکل ← بخش پیش‌فرض
FEEDER_DEV_DEFAULT_SECTION_BY_KIND: dict[str, str] = {
    "network": "fd_network", "single_line": "fd_network", "location": "fd_network",
    "profile": "fd_network", "before": "fd_before", "after": "fd_after",
    "other": "fd_after",
}

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


# ---------------------------------------------------------------------------
# v2.0.0 — بخش‌ها و انواع شکل متناسب با مطالعات انتخاب‌شده
# ---------------------------------------------------------------------------
def _is_heavy_key(key: str) -> bool:
    return not key.startswith(("secz_", "prot_", "fd_"))


def sections_for_selection(selection) -> list[tuple[str, str]]:
    """بخش‌های قابل‌انتخاب برای درج شکل بر اساس مطالعات پروژه.

    * متقاضی سنگین → بخش‌های گزارش متقاضی سنگین.
    * ریکلوزر / سکشنالایزر → بخش‌های ``prot_*`` (بخش مطالعهٔ هر تجهیز فقط وقتی مطالعه‌اش
      انتخاب شده باشد؛ پیوست ردیابی شکل نمی‌پذیرد). بخش‌های قدیمی ``secz_*`` دیگر نمایش داده نمی‌شوند.
    ``selection=None`` یعنی همه (سازگاری با رفتار قدیمی).
    """
    if selection is None:
        return list(REPORT_SECTIONS)
    out: list[tuple[str, str]] = []
    prot = selection.recloser or selection.sectionalizer
    fd = bool(getattr(selection, "feeder_dev", False))
    for key, label in REPORT_SECTIONS:
        if key.startswith("secz_") or key == "prot_trace":
            continue
        if key.startswith("prot_"):
            if not prot:
                continue
            if key == "prot_recloser" and not selection.recloser:
                continue
            if key == "prot_sectionalizer" and not selection.sectionalizer:
                continue
            out.append((key, label))
        elif key.startswith("fd_"):
            if fd:                                  # v2.4.0 — توسعه و اصلاح فیدر
                out.append((key, label))
        elif selection.heavy:
            out.append((key, label))
    return out


HEAVY_ONLY_IMAGE_KINDS = ("profile", "forecast", "before", "after")


def image_kinds_for_selection(selection, all_kinds: dict[str, str]) -> dict[str, str]:
    """انواع شکل: «پروفیل/پیش‌بینی/پخش بار» فقط برای متقاضی سنگین؛ «تک‌خطی/TCC/جانمایی» فقط حفاظتی.

    v2.4.0 — مطالعه «توسعه و اصلاح فیدر» هم شکل‌های پخش بار (قبل/بعد) و پروفیل دارد.
    """
    if selection is None:
        return dict(all_kinds)
    prot = selection.recloser or selection.sectionalizer
    heavy_like = selection.heavy or bool(getattr(selection, "feeder_dev", False))
    out = {}
    for k, label in all_kinds.items():
        if k in HEAVY_ONLY_IMAGE_KINDS and not heavy_like:
            continue
        if k in PROTECTION_IMAGE_KINDS and not prot:
            continue
        out[k] = label
    return out


PROTECTION_IMAGE_KINDS = ("single_line", "tcc", "placement", "sequence", "settings_sheet")
