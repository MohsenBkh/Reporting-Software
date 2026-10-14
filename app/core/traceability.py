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
SRC_GIS = "GIS"
SOURCE_LABELS_FA = {SRC_EXCEL: "Excel", SRC_CSV: "CSV", SRC_MANUAL: "ورود دستی",
                    SRC_CALC: "محاسبه", SRC_PF: "نتیجه PowerFactory",
                    SRC_GIS: "داده شبکه (GIS)؛ ورود دستی"}

STUDY_DETAIL = "جدول‌های مطالعه مصارف سنگین"

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
    for f in project.active_feeders:         # v1.2.0: فیدر خاموش در ردیابی نمی‌آید
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
    rows.extend(_study_rows(project, settings))
    return rows


def _study_rows(project: Project, settings=None) -> list[TraceRow]:
    """ردیابی منبع داده‌های مطالعه مصارف سنگین (تقاضا، ایستگاه‌ها، خطوط، سناریوها).

    مقادیر این جدول‌ها (فاصله/ظرفیت/بارگیری/افت ولتاژ/اتصال کوتاه/هزینه) ورودی
    کارشناس‌اند یا از سیستم‌های اطلاعات مکانی/مطالعات شبکه استخراج می‌شوند؛
    هر ردیف منبع خود را نشان می‌دهد و هیچ مقداری ساختگی نیست.
    """
    rows: list[TraceRow] = []
    d = project.demand
    for key, title, value, unit in (
            ("demand.with_coincidence", "تقاضا با ضریب همزمانی", d.with_coincidence_kw, "kW"),
            ("demand.without_coincidence", "تقاضا بدون ضریب همزمانی", d.without_coincidence_kw, "kW"),
            ("demand.existing", "دیماند موجود", d.existing_demand_kw, "kW")):
        if value is None:
            continue
        rows.append(TraceRow("اطلاعات تقاضا", title, fmt_local(value, 0), unit,
                             SRC_MANUAL, STUDY_DETAIL))
    for ss in project.active_substations:      # v1.2.0: ورودی خاموش ردیابی نمی‌شود
        name = ss.display_name
        for title, value, unit in (("فاصله ایستگاه (km)", ss.distance_km, "km"),
                                   ("ظرفیت ایستگاه (MVA)", ss.transformer_capacity_mva, "MVA"),
                                   ("بارگیری T1 (٪)", ss.t1_loading_percent, "٪"),
                                   ("بارگیری T2 (٪)", ss.t2_loading_percent, "٪"),
                                   ("تعداد فیدر", ss.feeder_count, "")):
            if value is None:
                continue
            rows.append(TraceRow(name, title, fmt_local(value, 2), unit, SRC_GIS, STUDY_DETAIL))
    for ln in project.active_lines:
        name = ln.display_name
        for title, value, unit in (("فاصله خط (m)", ln.distance_m, "m"),
                                   ("پیک بار خط (MVA)", ln.peak_mva, "MVA"),
                                   ("افت ولتاژ قبل (٪)", ln.vdrop_before_percent, "٪"),
                                   ("افت ولتاژ بعد (٪)", ln.vdrop_after_percent, "٪"),
                                   ("حداکثر اتصال کوتاه (kA)", ln.sc_max_ka, "kA"),
                                   ("حداقل اتصال کوتاه (kA)", ln.sc_min_ka, "kA")):
            if value is None:
                continue
            rows.append(TraceRow(name, title, fmt_local(value, 3), unit, SRC_GIS, STUDY_DETAIL))
        delta = None
        if ln.vdrop_before_percent is not None and ln.vdrop_after_percent is not None:
            delta = ln.vdrop_after_percent - ln.vdrop_before_percent
        if delta is not None:
            rows.append(TraceRow(name, "تغییر افت ولتاژ ناشی از بار جدید (واحد درصد)",
                                 fmt_local(delta, 2), "pp", SRC_CALC, "After − Before"))
    for c in project.active_coincident_demands:
        if c.computed_delta_kw() is None:
            continue
        rows.append(TraceRow(c.name or "متقاضی همزمان", "افزایش بار (kW)",
                             fmt_local(c.computed_delta_kw(), 0), "kW",
                             SRC_MANUAL, STUDY_DETAIL))
    for sc in project.scenarios:
        for title, value, unit in (("هزینه ثبت‌شده (میلیون تومان)", sc.estimated_cost_million, "M"),
                                   ("طول شبکه موردنیاز (km)", sc.required_line_length_km, "km"),
                                   ("درصد خط هوایی", sc.overhead_percent, "٪"),
                                   ("درصد خط زمینی", sc.underground_percent, "٪")):
            if value is None:
                continue
            rows.append(TraceRow(sc.display_title, title, fmt_local(value, 2), unit,
                                 SRC_MANUAL, "بررسی اقتصادی سناریوها"))
    for key, title, value, unit in (
            ("reported_total_additional_load_kw", "کل بار اضافه‌شده گزارش‌شده",
             project.reported_total_additional_load_kw, "kW"),
            ("demand_used_in_analysis_kw", "تقاضای مبنای تحلیل",
             project.demand_used_in_analysis_kw, "kW")):
        if value is None:
            continue
        rows.append(TraceRow("کنترل ناسازگاری", title, fmt_local(value, 0), unit,
                             SRC_MANUAL, STUDY_DETAIL))
    return rows


def fmt_local(value, digits: int = 2) -> str:
    from app.utils.formatting import fmt
    return fmt(value, digits)


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
