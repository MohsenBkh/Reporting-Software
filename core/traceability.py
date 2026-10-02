# -*- coding: utf-8 -*-
"""ردیابی منبع اعداد مهم گزارش (Traceability) — v1.0.3.

انواع منبع: EXCEL | CSV | MANUAL | CALC | POWERFACTORY
مقدار ثبت‌شده در Feeder.data_sources به شکل «TYPE» یا «TYPE|جزئیات (نام فایل)».
نتایج پخش بار (before/after) همیشه «نتیجه PowerFactory» هستند؛ جزئیات، روش ورود
(Excel/دستی) را نشان می‌دهد.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.models import Feeder, Project

SRC_EXCEL, SRC_CSV, SRC_MANUAL = "EXCEL", "CSV", "MANUAL"
SRC_CALC, SRC_PF = "CALC", "POWERFACTORY"
SOURCE_LABELS_FA = {SRC_EXCEL: "Excel", SRC_CSV: "CSV", SRC_MANUAL: "ورود دستی",
                    SRC_CALC: "محاسبه", SRC_PF: "نتیجه PowerFactory"}

# (کلید منبع، عنوان فارسی، تابع استخراج مقدار، واحد)
_INPUT_FIELDS = [
    ("peak_load_mw", "پیک بار", lambda f: f.peak_load_mw, "MW"),
    ("power_factor", "ضریب توان", lambda f: f.power_factor, ""),
    ("capacity_mw", "معیار بارگذاری", lambda f: f.capacity_mw, "MW"),
    ("max_current_a", "حداکثر جریان مجاز", lambda f: f.max_current_a, "A"),
]
_PF_FIELDS = [
    ("before.current_a", "جریان قبل", lambda f: f.before.current_a, "A"),
    ("before.loss_kw", "تلفات قبل", lambda f: f.before.loss_kw, "kW"),
    ("before.min_voltage_pu", "حداقل ولتاژ قبل", lambda f: f.before.min_voltage_pu, "pu"),
    ("after.current_a", "جریان بعد", lambda f: f.after.current_a, "A"),
    ("after.loss_kw", "تلفات بعد", lambda f: f.after.loss_kw, "kW"),
    ("after.min_voltage_pu", "حداقل ولتاژ بعد", lambda f: f.after.min_voltage_pu, "pu"),
]
_CALC_FIELDS = [
    ("loading_pct", "درصد بارگذاری فیدر", "٪"),
    ("d_v_pct", "تغییر ولتاژ ناشی از متقاضی", "٪"),
    ("d_i_pct", "تغییر جریان", "٪"),
    ("d_loss_pct", "تغییر تلفات", "٪"),
]


@dataclass
class TraceRow:
    feeder: str
    item: str
    value: str
    unit: str
    source_type: str
    detail: str

    @property
    def source_label(self) -> str:
        base = SOURCE_LABELS_FA.get(self.source_type, self.source_type)
        return f"{base} ({self.detail})" if self.detail else base


def split_source(raw: Optional[str], default: str = SRC_MANUAL) -> tuple[str, str]:
    if not raw:
        return default, ""
    t, _, d = raw.partition("|")
    return t or default, d


def build_trace(project: Project, settings=None) -> list[TraceRow]:
    from app.core import calculations as calc
    from app.core.settings import AppSettings
    from app.utils.formatting import fmt
    settings = settings or AppSettings()
    rows: list[TraceRow] = []
    for f in project.feeders:
        name = f.display_name
        for key, title, getter, unit in _INPUT_FIELDS:
            v = getter(f)
            if v is None:
                continue
            t, d = split_source(f.data_sources.get(key))
            rows.append(TraceRow(name, title, fmt(v, 3), unit, t, d))
        for key, title, getter, unit in _PF_FIELDS:
            v = getter(f)
            if v is None:
                continue
            raw = f.data_sources.get(key) or f.data_sources.get(key.split(".")[0])
            _t, d = split_source(raw, SRC_MANUAL)
            rows.append(TraceRow(name, title, fmt(v, 3), unit, SRC_PF,
                                 SOURCE_LABELS_FA.get(d, d) if d else SOURCE_LABELS_FA[SRC_MANUAL]))
        if f.profile_stats.n_points:
            t, d = split_source(f.data_sources.get("profile"), SRC_CSV)
            rows.append(TraceRow(name, "پیک پروفیل بار", fmt(f.profile_stats.peak_p_mw, 3), "MW", t, d or f.profile_file))
        if f.forecast.available:
            t, d = (SRC_MANUAL, "") if f.forecast.method == "manual" else (SRC_CALC, "رگرسیون خطی")
            rows.append(TraceRow(name, f"پیک پیش‌بینی سال {f.forecast.end_year()}",
                                 fmt(f.forecast.end_value(), 2), "MW", t, d))
        m = calc.feeder_metrics(f, project, settings)
        for key, title, unit in _CALC_FIELDS:
            if m.get(key) is not None:
                rows.append(TraceRow(name, title, fmt(m[key], 2), unit, SRC_CALC, "از ورودی‌های بالا"))
    return rows


def snapshot(f: Feeder) -> dict[str, Optional[float]]:
    """مقادیر قابل ردیابی یک فیدر برای تشخیص ویرایش دستی."""
    snap = {key: getter(f) for key, _t, getter, _u in _INPUT_FIELDS}
    snap.update({key: getter(f) for key, _t, getter, _u in _PF_FIELDS})
    return snap


def mark_manual_changes(f: Feeder, old: dict[str, Optional[float]]) -> None:
    """هر مقداری که کاربر دستی تغییر داده باشد منبع MANUAL می‌گیرد."""
    new = snapshot(f)
    for key, v in new.items():
        if v != old.get(key):
            f.data_sources[key] = SRC_MANUAL
            if "." in key:   # نتایج پخش بار: ورود دستی نتیجه PowerFactory
                f.data_sources[key.split(".")[0]] = SRC_MANUAL


def mark_all(f: Feeder, source_type: str, detail: str = "") -> None:
    """ثبت منبع برای همه مقادیر موجود فیدر (مثلاً Import از Excel)."""
    tag = f"{source_type}|{detail}" if detail else source_type
    for key, v in snapshot(f).items():
        if v is not None:
            f.data_sources[key] = tag
