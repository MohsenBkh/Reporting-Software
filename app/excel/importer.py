# -*- coding: utf-8 -*-
"""Importer — ساخت مدل Project کامل از Excel استاندارد (بخش ۲۸: تولید سریع)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from app.core import loading_profile as lp
from app.core import forecast as fc_mod
from app.core.models import (Feeder, ForecastPoint, Maneuver, NearbyLine,
                             NearbyStation, PowerFlowResult, Project,
                             REQUEST_INCREASE, REQUEST_NEW)
from app.core.settings import AppSettings
from app.excel.template import ExcelData, read_workbook
from app.excel.template import _norm_header as _norm


def _fnum(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        v = float(str(value).replace(",", "").strip())
        return v
    except ValueError:
        return None


def _inum(value) -> Optional[int]:
    v = _fnum(value)
    return int(round(v)) if v is not None else None


def _map_feeder_row(rec: dict) -> Feeder:
    return Feeder(
        name=str(rec.get("نام فیدر", "")).strip(),
        substation=str(rec.get("نام پست", "") or "").strip(),
        peak_load_mw=_fnum(rec.get("پیک بار mw")),
        peak_year=_inum(rec.get("سال پیک")),
        power_factor=_fnum(rec.get("ضریب توان")),
        peak_current_a=_fnum(rec.get("پیک جریان a")),
        max_current_a=_fnum(rec.get("حداکثر جریان مجاز a")),
        capacity_mw=_fnum(rec.get("معیار بارگذاری mw")),
        notes=str(rec.get("توضیحات", "") or "").strip(),
    )


def _apply_powerflow(project: Project, rows: list[dict]) -> list[str]:
    warnings: list[str] = []
    for rec in rows:
        name = str(rec.get("نام فیدر", "")).strip()
        state = str(rec.get("وضعیت", "")).strip()
        feeder = next((f for f in project.feeders if f.name == name), None)
        if feeder is None:
            warnings.append(f"در شیت پخش بار، فیدر «{name}» بین فیدرهای تعریف‌شده نیست.")
            continue
        target = PowerFlowResult(
            current_a=_fnum(rec.get("جریان ابتدای فیدر a")),
            loss_kw=_fnum(rec.get("تلفات kw")),
            min_voltage_pu=_fnum(rec.get("حداقل ولتاژ فیدر pu")),
            applicant_bus_voltage_pu=_fnum(rec.get("ولتاژ باس متقاضی pu")),
        )
        if state in ("بعد", "پس از", "after"):
            feeder.after = target
        elif state in ("قبل", "موجود", "فعلی", "before"):
            feeder.before = target
        else:
            warnings.append(f"وضعیت «{state}» برای فیدر {name} نامعتبر است (قبل/بعد).")
    return warnings


def build_project_from_excel(path: str | Path, settings: AppSettings) -> tuple[Optional[Project], list[str], list[str]]:
    """از فایل Excel قالب استاندارد، پروژه کامل می‌سازد.

    خروجی: (project یا None، خطاها، هشدارها)
    """
    data, errors = read_workbook(path)
    if errors:
        return None, errors, []

    f = data.project_fields
    rt_raw = f.get("request_type", "")
    request_type = REQUEST_INCREASE if "افزایش" in rt_raw else (
        REQUEST_NEW if ("جدید" in rt_raw or "تامین" in rt_raw or "تأمین" in rt_raw) else REQUEST_INCREASE)

    project = Project(
        name=f.get("name", ""),
        report_number=f.get("report_number", ""),
        date_jalali=f.get("date_jalali", ""),
        applicant_name=f.get("applicant_name", ""),
        request_type=request_type,
        existing_power_kw=_fnum(f.get("existing_power_kw")),
        requested_power_kw=_fnum(f.get("requested_power_kw")),
        substation=f.get("substation", ""),
        office=f.get("office", ""),
        expert_name=f.get("expert_name", ""),
        location_note=f.get("location_note", ""),
        location_distance_m=_fnum(f.get("location_distance_m")),
        cable_suggestion=f.get("cable_suggestion", ""),
        conductor_type=f.get("conductor_type", ""),
        conclusion_scenarios=f.get("conclusion_scenarios", ""),
    )
    if not project.name:
        project.name = project.title_text()

    man = f.get("maneuver_enabled", "")
    if man and "بله" in man:
        project.maneuver = Maneuver(
            enabled=True,
            source_feeder=f.get("maneuver_source", ""),
            target_feeder=f.get("maneuver_target", ""),
            transferred_mw=_fnum(f.get("maneuver_mw")),
            date_jalali=f.get("maneuver_date", ""),
            note=f.get("maneuver_note", ""),
        )

    # --- فیدرها ---
    project.feeders = [_map_feeder_row(r) for r in data.feeders]
    if not project.feeders:
        return None, errors + ["هیچ فیدری در شیت «فیدرها» وارد نشده است."], []

    warnings = _apply_powerflow(project, data.powerflow)

    # --- ایستگاه‌ها و خطوط نزدیک به محل تقاضا (اختیاری) ---
    for rec in data.stations:
        project.nearby_stations.append(NearbyStation(
            name=str(rec.get("نام ایستگاه", "")).strip(),
            distance_km=_fnum(rec.get(_norm("فاصله تا محل تقاضا km"))),
            capacity_mva=_fnum(rec.get(_norm("ظرفیت ایستگاه mva"))),
            t1_loading_pct=_fnum(rec.get(_norm("درصد بارگیری ترانس t1 در پیک"))),
            t2_loading_pct=_fnum(rec.get(_norm("درصد بارگیری ترانس t2 در پیک"))),
            t1_loading_mva=_fnum(rec.get(_norm("میزان بارگیری ترانس t1 در پیک mva"))),
            t2_loading_mva=_fnum(rec.get(_norm("میزان بارگیری ترانس t2 در پیک mva"))),
            feeder_count=_inum(rec.get(_norm("تعداد کل فیدر برقرار")))))
    for rec in data.lines:
        project.nearby_lines.append(NearbyLine(
            name=str(rec.get("نام خط", "")).strip(),
            distance_m=_fnum(rec.get(_norm("فاصله تا محل تقاضا m"))),
            peak_mva=_fnum(rec.get(_norm("پیک بار خط mva"))),
            peak_mw=_fnum(rec.get(_norm("پیک بار خط mw"))),
            peak_a=_fnum(rec.get(_norm("پیک بار خط a"))),
            vdrop_before_pct=_fnum(rec.get(_norm("افت ولتاژ انتهای خط قبل از بار جدید درصد"))),
            vdrop_after_pct=_fnum(rec.get(_norm("افت ولتاژ انتهای خط بعد از بار جدید درصد")))))

    from app.core import traceability as _trace
    for _f in project.feeders:
        _trace.mark_all(_f, _trace.SRC_EXCEL, Path(path).name)

    # --- پروفیل بار ---
    if data.profile_rows:
        pdf = pd.DataFrame(data.profile_rows)
        pdf = pdf.rename(columns={"feeder": "feeder", "p_mw": "p_mw", "q_mvar": "q_mvar", "date": "date"})
        for col in ("date", "feeder", "p_mw", "q_mvar"):
            if col not in pdf.columns:
                pdf[col] = None
        pdf["p_mw"] = pd.to_numeric(pdf["p_mw"], errors="coerce")
        pdf = pdf.dropna(subset=["p_mw"]).sort_values("date").reset_index(drop=True)
        for feeder in project.feeders:
            sub = lp.filter_feeder(pdf, feeder.name) if "feeder" in pdf.columns else pdf
            if sub is not None and not sub.empty:
                feeder._profile_df = sub  # noqa: SLF001
                feeder.data_sources["profile"] = f"EXCEL|{Path(path).name}"
                feeder.profile_stats = lp.compute_stats(sub)

                # اگر پیک/ضریب توان از فرم خالی باشد، از پروفیل تکمیل می‌شود
                if feeder.peak_load_mw is None:
                    feeder.peak_load_mw = feeder.profile_stats.peak_p_mw
                if feeder.power_factor is None and feeder.profile_stats.power_factor_at_peak:
                    feeder.power_factor = feeder.profile_stats.power_factor_at_peak

    # --- پیش‌بینی دستی یا رگرسیون ---
    th = settings.thresholds
    for feeder in project.feeders:
        manual_rows = [r for r in data.forecast_rows if r["feeder"] == feeder.name]
        if manual_rows:
            pts = [(int(r["year"]), float(r["value"])) for r in manual_rows]
            feeder.forecast = fc_mod.manual_forecast(pts)
        else:
            df = getattr(feeder, "_profile_df", None)
            if df is not None and not df.empty:
                years, values = lp.annual_peaks(df)
                feeder.forecast = fc_mod.linear_forecast(
                    years, values, horizon=th.forecast_years,
                    min_points=th.forecast_min_history, th=th)

    # --- شماره گزارش پیش‌فرض از پیشوند تنظیمات ---
    if not project.report_number and settings.report_prefix:
        pass  # شماره گزارش را کاربر/زمان تولید تکمیل می‌کند

    return project, errors, warnings
