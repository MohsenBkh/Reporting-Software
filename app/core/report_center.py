# -*- coding: utf-8 -*-
"""Report Center — مدیریت انتخاب مطالعات و ترکیب گزارش‌ها.

این ماژول به‌جای reliance بر `report_type` واحد، به کاربر اجازه می‌دهد:
- مطالعات مختلف را فعال/غیرفعال کند
- برای Protection Studies گزارش مستقل یا ترکیبی انتخاب کند
- ترتیب بخش‌ها در گزارش را تنظیم کند
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# کلیدهای مطالعات
STUDY_HEAVY = "heavy"
STUDY_RECLOSER = "recloser"
STUDY_SECTIONALIZER = "sectionalizer"

ALL_STUDY_KEYS = (STUDY_HEAVY, STUDY_RECLOSER, STUDY_SECTIONALIZER)

# وضعیت مطالعه
STUDY_STATE_NOT_STARTED = "not_started"
STUDY_STATE_IN_PROGRESS = "in_progress"
STUDY_STATE_COMPLETE = "complete"
STUDY_STATE_REVIEW_REQUIRED = "review_required"
STUDY_STATE_ERROR = "error"


@dataclass
class StudySelection:
    """انتخاب یک مطالعه برای گزارش‌گیری."""

    key: str = STUDY_HEAVY
    enabled: bool = True
    include_in_report: bool = True


@dataclass
class ProtectionReportConfig:
    """تنظیمات گزارش ترکیبی ریکلوزر + سکشنالایزر."""

    # آیا گزارش ترکیبی تولید شود یا جداگانه
    combined: bool = True

    # ترتیب بخش‌های گزارش ترکیبی (قابل توسعه)
    section_order: list[str] = field(default_factory=lambda: [
        "network_info",        # ۱. مشخصات شبکه
        "existing_protection",  # ۲. وضعیت حفاظتی موجود
        "recloser_study",      # ۳. مطالعه ریکلوزر
        "sectionalizer_study",  # ۴. مطالعه سکشنالایزر
        "coordination",        # ۵. هماهنگی حفاظتی
        "equipment_inventory", # ۶. جانمایی تجهیزات
        "performance_scenario", # ۷. سناریوی عملکرد
        "conclusion",          # ۸. جمع‌بندی
        "final_recommendation", # ۹. پیشنهاد نهایی
    ])


@dataclass
class ReportCenter:
    """مرکز مدیریت گزارش — جایگزین report_type واحد.

    می‌تواند:
    - مطالعات مختلف را فعال کند
    - برای Protection Studies گزارش مستقل یا ترکیبی انتخاب کند
    - ترتیب بخش‌های گزارش ترکیبی را تعریف کند
    - وضعیت هر مطالعه را ردیابی کند
    """

    # انتخاب مطالعات
    studies: dict[str, StudySelection] = field(default_factory=lambda: {
        STUDY_HEAVY: StudySelection(STUDY_HEAVY, True, True),
        STUDY_RECLOSER: StudySelection(STUDY_RECLOSER, False, False),
        STUDY_SECTIONALIZER: StudySelection(STUDY_SECTIONALIZER, False, False),
    })

    # تنظیمات گزارش حفاظت (ریکلوزر + سکشنالایزر)
    protection_report: ProtectionReportConfig = field(default_factory=ProtectionReportConfig)

    # ترتیب بخش‌های کلی گزارش (قابل توسعه)
    global_section_order: list[str] = field(default_factory=list)

    # وضعیت مطالعات (برای داشبورد)
    study_states: dict[str, str] = field(default_factory=dict)

    def enable_study(self, key: str, enabled: bool = True) -> None:
        """فعال/غیرفعال کردن یک مطالعه."""
        if key in self.studies:
            self.studies[key].enabled = enabled

    def include_in_report(self, key: str, include: bool = True) -> None:
        """신청 یک مطالعه در گزارش."""
        if key in self.studies:
            self.studies[key].include_in_report = include

    def set_study_state(self, key: str, state: str) -> None:
        """تنظیم وضعیت یک مطالعه."""
        self.study_states[key] = state

    def get_study_state(self, key: str) -> str:
        """ دریافت وضعیت یک مطالعه."""
        return self.study_states.get(key, STUDY_STATE_NOT_STARTED)

    def active_studies(self) -> list[str]:
        """لیست مطالعات فعال."""
        return [k for k, s in self.studies.items() if s.enabled]

    def report_studies(self) -> list[str]:
        """لیست مطالعات که در گزارشincluded هستند."""
        return [k for k, s in self.studies.items() if s.include_in_report]

    def has_protection_study(self, key: str) -> bool:
        """آیا یک مطالعه حفاظت انتخاب شده؟"""
        return key in self.studies and self.studies[key].enabled

    def both_protection_enabled(self) -> bool:
        """آیا هم ریکلوزر و هم سکشنالایزر فعال هستند؟"""
        return (self.studies.get(STUDY_RECLOSER, StudySelection()).enabled and
                self.studies.get(STUDY_SECTIONALIZER, StudySelection()).enabled)

    def protection_report_mode(self) -> str:
        """حالت گزارش حفاظت: 'combined' یا 'separate'."""
        if not self.both_protection_enabled():
            return "separate"
        return "combined" if self.protection_report.combined else "separate"
