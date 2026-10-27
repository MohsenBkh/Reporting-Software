# -*- coding: utf-8 -*-
"""کدگذاری مدارک مطالعات — v2.5.0، مطابق فایل «کدگذاری مطالعات.xlsx».

ساختار کد: ``**-##-###`` = «کد نوع مطالعات» - «کد امور» - «شماره گزارش (از 001)»
مثال: ``PD-13-001`` = گزارش شماره یک - امور مشگین‌شهر - جایابی تجهیزات حفاظتی.
"""
from __future__ import annotations

import re
from typing import Optional

# --- کد نوع مطالعات (ستون «نوع مطالعات/کد» فایل کدگذاری) --------------------
STUDY_CODES: dict[str, str] = {
    "heavy_applicant": "DM",      # متقاضیان بالای یک مگاوات
    "protective_device": "PD",    # جایابی تجهیزات حفاظتی (ریکلوزر/سکشنالایزر)
    "feeder_dev": "FD",           # توسعه و اصلاح فیدر
    "autobooster": "AP",          # جایابی اتوبوستر
    "capacitor": "CP",            # خازن‌گذاری
}

STUDY_CODE_LABELS: dict[str, str] = {
    "DM": "متقاضیان بالای یک مگاوات",
    "PD": "جایابی تجهیزات حفاظتی",
    "FD": "توسعه و اصلاح فیدر",
    "AP": "جایابی اتوبوستر",
    "CP": "خازن‌گذاری",
}

#: نگاشت report_type برنامه ← کد نوع مطالعه
REPORT_TYPE_TO_CODE: dict[str, str] = {
    "heavy": "DM",
    "recloser": "PD",
    "sectionalizer": "PD",
    "combined_protection": "PD",
    "feeder_dev": "FD",
}

# --- کد امور (ستون «امور/کد» فایل کدگذاری) ----------------------------------
OFFICE_CODES: dict[str, str] = {
    "برق اردبیل": "18",
    "پارس‌آباد": "15",
    "بیله‌سوار": "17",
    "گرمی": "14",
    "مشگین‌شهر": "13",
    "نمین": "21",
    "نیر": "22",
    "سرعین": "23",
    "خلخال": "16",
    "کوثر": "24",
    "اصلاندوز": "25",
    "انگوت": "26",
}

#: کد امور ← نام امور
OFFICE_BY_CODE: dict[str, str] = {v: k for k, v in OFFICE_CODES.items()}

#: الگوی کد معتبر: دو حرف لاتین - دو رقم - سه رقم
REPORT_NUMBER_RE = re.compile(r"^(DM|PD|FD|AP|CP)-(\d{2})-(\d{3})$")


def make_report_number(study_code: str, office_code: str, serial: int) -> str:
    """ساخت کد مدرک: ``FD-26-001``. شماره گزارش از 001 شروع می‌شود."""
    return f"{study_code}-{office_code}-{max(1, int(serial)):03d}"


def study_code_for_report_type(report_type: str) -> str:
    """کد نوع مطالعه برای report_type برنامه («» اگر ناشناخته)."""
    return REPORT_TYPE_TO_CODE.get((report_type or "").strip(), "")


def office_code_for_name(office_name: str) -> str:
    """کد امور از روی نام (با تحمل فاصله/نیم‌فاصله/پیشوند «امور»)؛ «» اگر پیدا نشد."""
    name = _normalize(office_name)
    if not name:
        return ""
    for known, code in OFFICE_CODES.items():
        k = _normalize(known)
        if name == k or name.endswith(k) or k.endswith(name):
            return code
    return ""


def parse_report_number(text: str) -> Optional[tuple[str, str, int]]:
    """تجزیه کد مدرک به (کد مطالعه، کد امور، شماره)؛ None اگر قالب نامعتبر باشد."""
    m = REPORT_NUMBER_RE.match((text or "").strip())
    if not m:
        return None
    return m.group(1), m.group(2), int(m.group(3))


def is_valid_report_number(text: str) -> bool:
    return parse_report_number(text) is not None


def describe_report_number(text: str) -> str:
    """توضیح فارسی یک کد معتبر؛ «» اگر نامعتبر باشد."""
    parsed = parse_report_number(text)
    if parsed is None:
        return ""
    sc, oc, serial = parsed
    office = OFFICE_BY_CODE.get(oc, f"امور با کد {oc}")
    return f"گزارش شماره {serial} — امور {office} — {STUDY_CODE_LABELS.get(sc, sc)}"


def _normalize(s: str) -> str:
    s = (s or "").strip()
    for ch in ("\u200c", " ", "‌", "-", "ـ"):
        s = s.replace(ch, "")
    s = s.replace("آ", "ا")
    for prefix in ("امور", "برق"):
        if s.startswith(prefix) and len(s) > len(prefix) and s != "برقاردبیل":
            s = s[len(prefix):]
    return s
