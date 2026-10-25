# -*- coding: utf-8 -*-
"""مدل Property Inspector — Context Sensitive و مستقل از Qt.

با انتخاب هر گره Explorer، عنوان و ردیف‌های «کلید/مقدار» همان شیء ساخته می‌شود.
هیچ مقدار پیش‌فرض ساخته نمی‌شود: نبود داده = «—».
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.protection_models import FUNCTION_LABELS_FA
from app.core.studies import STUDY_LABELS_FA, StudyKind
from app.core.workspace import Workspace
from app.ui.shell.design import MISSING_TEXT, format_quantity

CURVE_NAMES = {"NI": "Normal Inverse", "VI": "Very Inverse", "EI": "Extremely Inverse",
               "LTI": "Long Time Inverse"}


@dataclass
class InspectorModel:
    title: str = "—"
    subtitle: str = ""
    rows: list[tuple[str, str]] = field(default_factory=list)
    include_key: Optional[str] = None        # کلید شیء برای چک‌باکس «Include in Report»
    include_value: Optional[bool] = None


def _txt(v: Any) -> str:
    return MISSING_TEXT if v in (None, "") else str(v)


def _device_model(project: Any, kind: StudyKind) -> InspectorModel:
    info = getattr(project, kind.value)
    s = getattr(info, "settings", None)
    f51 = getattr(s, "f51", None)
    curve = getattr(f51, "curve", "") if f51 else ""
    rows = [
        ("فیدر", _txt(getattr(info, "feeder_name", ""))),
        ("محل نصب", _txt(getattr(info, "installation_location", ""))),
        ("جریان نامی", format_quantity(getattr(info, "rated_current_a", None), "A", 0)),
        ("Pickup (۵۱)", format_quantity(getattr(f51, "pickup_a", None), "A", 1)),
        ("TMS (۵۱)", f51.time_text() if f51 and f51.time_value is not None else MISSING_TEXT),
        ("منحنی", (f"{curve} — {CURVE_NAMES[curve]}" if curve in CURVE_NAMES else _txt(curve))),
    ]
    if kind is StudyKind.RECLOSER and s is not None:
        rows += [("تعداد Shot", _txt(s.shots)),
                 ("Reclaim time", format_quantity(s.reclaim_time_s, "s", 0)),
                 ("فیوز سیوینگ", MISSING_TEXT if s.fuse_saving is None
                  else ("فعال" if s.fuse_saving else "غیرفعال"))]
    if kind is StudyKind.SECTIONALIZER and s is not None:
        rows += [("Counter", _txt(s.counter)),
                 ("Dead line", (f"{s.dead_line_current_pct:g}% I / {s.dead_line_voltage_pct:g}% V"
                                if s.dead_line_current_pct is not None
                                and s.dead_line_voltage_pct is not None else MISSING_TEXT))]
    name = getattr(info, "name", "") or ("R1" if kind is StudyKind.RECLOSER else "S1")
    model = InspectorModel(title=f"{STUDY_LABELS_FA[kind]} {name}", rows=rows)
    if hasattr(info, "include_in_report"):
        model.include_key, model.include_value = kind.value, bool(info.include_in_report)
    return model


def _feeder_model(workspace: Workspace, name: str) -> InspectorModel:
    f = workspace.common_network.feeder(name)
    if f is None:
        return InspectorModel(title=name, subtitle="داده‌ای در شبکه مشترک ثبت نشده است.")
    return InspectorModel(
        title=f"فیدر {f.name}", subtitle=f.source,
        rows=[("پست", _txt(f.substation)), ("ولتاژ", format_quantity(f.voltage_kv, "kV", 1)),
              ("جریان بار", format_quantity(f.load_current_a, "A", 1)),
              ("Isc حداکثر", format_quantity(f.max_fault_current_ka, "kA", 2)),
              ("Isc حداقل", format_quantity(f.min_fault_current_ka, "kA", 2)),
              ("تجهیزات حفاظتی موجود", str(len(f.existing_protection)))])


def inspector_model(project: Any, workspace: Workspace, key: str) -> InspectorModel:
    """مدل Inspector برای کلید گرهٔ Explorer."""
    if project is None:
        return InspectorModel(title="پروژه‌ای باز نیست")
    base = key
    if key.startswith("input."):
        base = key.split(".", 1)[1]
    elif "." in key and not key.startswith(("step.", "report.", "network.", "project.")):
        base = key.split(".")[0]                      # recloser.network → recloser
    if base in (StudyKind.RECLOSER.value, StudyKind.SECTIONALIZER.value):
        return _device_model(project, StudyKind(base))
    if base == StudyKind.FEEDER_DEV.value:               # v2.4.0
        fd = getattr(project, "feeder_dev", None)
        if fd is None:
            return InspectorModel(title="توسعه و اصلاح فیدر")
        return InspectorModel(
            title="توسعه و اصلاح فیدر",
            rows=[("نوع طرح", _txt(fd.plan_kind)),
                  ("پست محدوده", _txt(fd.substation)),
                  ("تعداد فیدر", str(len(fd.feeders or []))),
                  ("طول خط جدید", format_quantity(fd.new_line_length_km, "km", 2)),
                  ("نوع هادی", _txt(fd.conductor_type)),
                  ("نتایج قبل/بعد", "ثبت شده" if fd.has_results() else MISSING_TEXT)])
    if key.startswith("feeder:"):
        return _feeder_model(workspace, key.split(":")[-1])
    if key in ("project", "project.info", "step.project", "dashboard"):
        return InspectorModel(
            title=getattr(project, "name", "") or "پروژه",
            rows=[("شماره گزارش", _txt(getattr(project, "report_number", ""))),
                  ("تاریخ", _txt(getattr(project, "date_jalali", ""))),
                  ("متقاضی", _txt(getattr(project, "applicant_name", ""))),
                  ("تعداد فیدر", str(len(getattr(project, "feeders", []) or []))),
                  ("مطالعات انتخاب‌شده",
                   "، ".join(STUDY_LABELS_FA[k] for k in workspace.selection.kinds()) or MISSING_TEXT)])
    if key.startswith("report.") or key.startswith("step."):
        return InspectorModel(title="گزارش", subtitle="برای ساخت گزارش به Report Center بروید.")
    return InspectorModel(title="—", subtitle="شیئی انتخاب نشده است.")


def apply_include_flag(project: Any, key: str, value: bool) -> bool:
    """تغییر «Include in Report»؛ اگر فیلد در مدل نبود False برمی‌گرداند."""
    info = getattr(project, key, None)
    if info is None or not hasattr(info, "include_in_report"):
        return False
    info.include_in_report = bool(value)
    return True
