# -*- coding: utf-8 -*-
"""تعریف «مطالعه» (Study) و انتخاب مطالعات پروژه.

پروژه دیگر فقط یک ``report_type`` ندارد؛ هر پروژه می‌تواند چند مطالعهٔ مستقل
داشته باشد: متقاضی سنگین، ریکلوزر، سکشنالایزر. ``report_type`` قدیمی همچنان
خوانده می‌شود و فقط برای مهاجرت (Migration) به انتخاب مطالعات به کار می‌رود.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class StudyKind(str, Enum):
    HEAVY = "heavy"
    RECLOSER = "recloser"
    SECTIONALIZER = "sectionalizer"
    FEEDER_DEV = "feeder_dev"            # v2.4.0 — توسعه و اصلاح فیدر


STUDY_LABELS_FA = {
    StudyKind.HEAVY: "متقاضی سنگین",
    StudyKind.RECLOSER: "ریکلوزر",
    StudyKind.SECTIONALIZER: "سکشنالایزر",
    StudyKind.FEEDER_DEV: "توسعه و اصلاح فیدر",
}
PROTECTION_KINDS = (StudyKind.RECLOSER, StudyKind.SECTIONALIZER)
PROTECTION_WORKSPACE_TITLE_FA = "مطالعات حفاظت و اتوماسیون شبکه"


@dataclass
class StudySelection:
    """مطالعاتی که کاربر برای تحلیل/گزارش انتخاب کرده است."""

    heavy: bool = False
    recloser: bool = False
    sectionalizer: bool = False
    feeder_dev: bool = False             # v2.4.0 — توسعه و اصلاح فیدر

    def kinds(self) -> list[StudyKind]:
        return [k for k in StudyKind if getattr(self, k.value)]

    def protection_kinds(self) -> list[StudyKind]:
        return [k for k in self.kinds() if k in PROTECTION_KINDS]

    def is_selected(self, kind: StudyKind) -> bool:
        return bool(getattr(self, StudyKind(kind).value))

    def is_empty(self) -> bool:
        return not self.kinds()

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "StudySelection":
        data = data or {}
        return cls(**{k.value: bool(data.get(k.value, False)) for k in StudyKind})


def selection_from_legacy(report_type: Optional[str]) -> StudySelection:
    """مهاجرت از ``Project.report_type`` قدیمی؛ ناشناخته/خالی = متقاضی سنگین."""
    if report_type == StudyKind.SECTIONALIZER.value:
        return StudySelection(sectionalizer=True)
    if report_type == StudyKind.RECLOSER.value:
        return StudySelection(recloser=True)
    if report_type == StudyKind.FEEDER_DEV.value:
        return StudySelection(feeder_dev=True)
    return StudySelection(heavy=True)


def has_study_data(project: Any, kind: StudyKind) -> bool:
    """آیا کاربر برای این مطالعه داده‌ای وارد کرده است؟ (بدون حدس)"""
    kind = StudyKind(kind)
    if kind is StudyKind.HEAVY:
        return bool(getattr(project, "feeders", None) or getattr(project, "applicant_name", ""))
    info = getattr(project, kind.value, None)
    if info is None:
        return False
    return dataclasses.asdict(info) != dataclasses.asdict(type(info)())


def report_type_for_selection(selection: "StudySelection") -> str:
    """نوع گزارش اولیهٔ پروژه از روی مطالعات انتخاب‌شده (برای سازگاری با ``report_type``).

    اولویت: متقاضی سنگین، سپس ترکیبی (هر دو مطالعهٔ حفاظتی)، سپس ریکلوزر، سپس سکشنالایزر.
    Report Center بعداً نوع گزارشِ در حال تولید را برای هر خروجی تنظیم می‌کند.
    """
    if selection.heavy:
        return StudyKind.HEAVY.value
    if selection.recloser and selection.sectionalizer:
        return "combined_protection"
    if selection.recloser:
        return StudyKind.RECLOSER.value
    if selection.sectionalizer:
        return StudyKind.SECTIONALIZER.value
    if selection.feeder_dev:
        return StudyKind.FEEDER_DEV.value
    return StudyKind.HEAVY.value
