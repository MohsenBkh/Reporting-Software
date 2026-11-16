# -*- coding: utf-8 -*-
"""ورود خروجی نرم‌افزار SwitchLoc (eens_report.json) — v2.6.0.

مطالعه «جایابی سکسیونر» بخش جایابی (روش EENS — انرژی توزیع‌نشده) را همیشه از
فایل ``eens_report.json`` می‌گیرد تا نتایج گزارش عیناً با خروجی نرم‌افزار
جایابی منطبق باشد. این ماژول فایل را می‌خواند، اعتبارسنجی سبک می‌کند و
فیلدهای :class:`app.core.models.DisconnectorInfo` را پر می‌کند.

نگاشت فیلدها (قالب ← فایل):

====================  =====================================================
متغیر قالب             مسیر در eens_report.json
====================  =====================================================
{شناسه فیدر}           study.feeders[i].feeder_key
{نرخ خرابی}            study.feeders[i].failure_rate_per_year
{زمان تعمیر}           study.feeders[i].repair_time_min
{نرخ خرابی گذرا}        study.feeders[i].transient_rate_per_year
{طول خط}              study.feeders[i].line_length_km
{بار تحت پوشش}         study.feeders[i].total_load_kw
{EENS پایه}            study.summary_rows[i].baseline_eens_mwh
{EENS پس از نصب}       study.summary_rows[i].best_eens_mwh
{درصد بهبود}           study.summary_rows[i].improvement_percent
{تعداد کلید}            study.summary_rows[i].selected_count
{نوع خط/تجهیز}{مختصات}  study.summary_rows[i].selected_labels
====================  =====================================================
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


class EENSImportError(Exception):
    """خطای خواندن/اعتبارسنجی فایل eens_report.json."""


@dataclass
class EENSFeederResult:
    """نتیجه EENS یک فیدر از فایل SwitchLoc."""

    feeder_key: str = ""
    line_length_km: Optional[float] = None
    total_load_kw: Optional[float] = None
    failure_rate_per_year: Optional[float] = None
    repair_time_min: Optional[float] = None
    transient_rate_per_year: Optional[float] = None
    switch_type_fa: str = ""
    baseline_eens_mwh: Optional[float] = None   # MWh/سال
    best_eens_mwh: Optional[float] = None       # MWh/سال
    improvement_percent: Optional[float] = None
    selected_count: Optional[int] = None
    selected_labels: list[str] = field(default_factory=list)


@dataclass
class EENSReport:
    """محتوای مفید eens_report.json برای گزارش جایابی سکسیونر."""

    algo_version: str = ""
    method_fa: str = ""
    switch_type: str = ""
    assumptions: list[str] = field(default_factory=list)
    total_baseline_eens_kwh: Optional[float] = None
    total_best_eens_kwh: Optional[float] = None
    total_improvement_percent: Optional[float] = None
    total_selected_switches: Optional[int] = None
    feeders: list[EENSFeederResult] = field(default_factory=list)

    def feeder(self, key: str = "") -> Optional[EENSFeederResult]:
        """فیدر با شناسه داده‌شده (خالی = اولین فیدر)."""
        if not self.feeders:
            return None
        if not (key or "").strip():
            return self.feeders[0]
        for f in self.feeders:
            if f.feeder_key == key:
                return f
        return None


def _num(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _mwh(value_kwh: Any) -> Optional[float]:
    v = _num(value_kwh)
    return None if v is None else v / 1000.0


def load_eens_report(path: str | Path) -> EENSReport:
    """خواندن و اعتبارسنجی فایل eens_report.json (خروجی SwitchLoc)."""
    p = Path(path)
    if not p.exists():
        raise EENSImportError(f"فایل یافت نشد: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise EENSImportError(f"فایل قابل خواندن نیست: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EENSImportError(f"فایل JSON معتبر نیست: {exc}") from exc
    if not isinstance(data, dict):
        raise EENSImportError("ساختار فایل نامعتبر است (انتظار: شیء JSON).")
    study = data.get("study")
    if not isinstance(study, dict):
        raise EENSImportError(
            "فایل انتخاب‌شده خروجی جایابی SwitchLoc نیست (بخش «study» یافت نشد).")
    feeders_raw = study.get("feeders") or []
    if not feeders_raw:
        raise EENSImportError("هیچ فیدری در فایل جایابی یافت نشد (study.feeders خالی است).")

    settings = data.get("settings") or {}
    engine = settings.get("engine") or {}
    report = EENSReport(
        algo_version=str(data.get("algo_version") or data.get("app_version") or ""),
        method_fa=str(settings.get("method_fa") or settings.get("method") or ""),
        switch_type=str(engine.get("switch_type") or ""),
        assumptions=[str(a) for a in (study.get("assumptions") or [])],
        total_baseline_eens_kwh=_num(study.get("total_baseline_eens_kwh_per_year")),
        total_best_eens_kwh=_num(study.get("total_best_eens_kwh_per_year")),
        total_improvement_percent=_num(study.get("total_improvement_percent")),
        total_selected_switches=(int(study["total_selected_switches"])
                                 if study.get("total_selected_switches") is not None else None),
    )

    # summary_rows با feeders هم‌ترتیب است؛ با شناسه فیدر هم تطبیق می‌دهیم.
    summaries: dict[str, dict] = {}
    rows = study.get("summary_rows") or []
    for i, row in enumerate(rows):
        if isinstance(row, dict):
            key = str(row.get("feeder_key") or row.get("feeder") or f"#{i}")
            summaries[key] = row
            summaries.setdefault(f"#{i}", row)

    for i, raw in enumerate(feeders_raw):
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("feeder_key") or "")
        row = summaries.get(key) or summaries.get(f"#{i}") or {}
        labels = row.get("selected_labels") or []
        if isinstance(labels, str):
            labels = [labels]
        selected_count = row.get("selected_count")
        if selected_count is None:
            steps = raw.get("steps") or []
            selected_count = len([s for s in steps
                                  if isinstance(s, dict) and s.get("selected")]) or None
        fr = EENSFeederResult(
            feeder_key=key,
            line_length_km=_num(raw.get("line_length_km")),
            total_load_kw=_num(raw.get("total_load_kw")),
            failure_rate_per_year=_num(raw.get("failure_rate_per_year")),
            repair_time_min=_num(raw.get("repair_time_min")),
            transient_rate_per_year=_num(raw.get("transient_rate_per_year")),
            switch_type_fa=str(raw.get("switch_type_fa") or ""),
            baseline_eens_mwh=(_num(row.get("baseline_eens_mwh"))
                               if row.get("baseline_eens_mwh") is not None
                               else _mwh(raw.get("baseline_eens_kwh_per_year"))),
            best_eens_mwh=(_num(row.get("best_eens_mwh"))
                           if row.get("best_eens_mwh") is not None
                           else _mwh(raw.get("best_eens_kwh_per_year"))),
            improvement_percent=(_num(row.get("improvement_percent"))
                                 if row.get("improvement_percent") is not None
                                 else _num(raw.get("improvement_percent"))),
            selected_count=(int(selected_count) if selected_count is not None else None),
            selected_labels=[str(x) for x in labels],
        )
        report.feeders.append(fr)
    if not report.feeders:
        raise EENSImportError("هیچ فیدر معتبری در فایل جایابی یافت نشد.")
    return report


def apply_eens_to_disconnector(dx, report: EENSReport, feeder_key: str = "") -> str:
    """پرکردن فیلدهای جایابی ``DisconnectorInfo`` از نتایج فایل SwitchLoc.

    برمی‌گرداند: شناسه فیدری که اعمال شد (برای پیام UI).
    """
    f = report.feeder(feeder_key)
    if f is None:
        raise EENSImportError(f"فیدر «{feeder_key}» در فایل جایابی یافت نشد.")
    dx.feeder_key = f.feeder_key
    dx.failure_rate_per_year = f.failure_rate_per_year
    dx.repair_time_min = f.repair_time_min
    dx.transient_rate_per_year = f.transient_rate_per_year
    dx.line_length_km = f.line_length_km
    dx.covered_load_kw = f.total_load_kw
    dx.eens_base_mwh = f.baseline_eens_mwh
    dx.eens_after_mwh = f.best_eens_mwh
    dx.improvement_pct = f.improvement_percent
    dx.switch_count = f.selected_count
    if f.selected_labels:
        # برچسب نمونه: «F10 - RADIO · خط هوایی · @ 750552, 4379268 m»
        kinds, coords = [], []
        for lbl in f.selected_labels:
            for seg in [x.strip() for x in str(lbl).split("·")][1:]:
                if seg.startswith("@"):
                    coords.append(seg.lstrip("@ ").strip())
                elif seg and seg not in kinds:
                    kinds.append(seg)
        if kinds and not (dx.device_note or "").strip():
            dx.device_note = " — ".join(kinds)
        if coords:
            dx.device_coords = "؛ ".join(coords)
    # «نوع سکسیونر» قالب (مثل موتوردار/گازی) با نوع کلید فایل (سکسیونر) یکی نیست؛
    # خودکار پر نمی‌شود تا در عنوان «جایابی سکسیونر {نوع}» تکرار نشود.
    if not (dx.optimal_location or "").strip() and dx.device_coords:
        dx.optimal_location = dx.device_coords
    dx.eens_imported = True
    dx.eens_algo_version = report.algo_version
    dx.eens_assumptions = list(report.assumptions)
    return f.feeder_key
