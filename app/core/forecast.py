# -*- coding: utf-8 -*-
"""پیش‌بینی بار ۵ ساله — رگرسیون خطی روی پیک‌های سالانه + کنترل کیفیت داده.

اصول:
* اگر داده کافی نباشد هیچ عدد ساختگی تولید نمی‌شود (method = none).
* Forecast بدون کنترل کیفیت داده مبنای نتیجه‌گیری قطعی نیست؛ هر مشکل کیفیت
  (R² پایین، Outlier، داده ناقص/فاصله، جهش ساختاری ناشی از مانور فیدر) باعث
  review_status = REQUIRES_ENGINEER_REVIEW می‌شود. تصمیم نهایی با مهندس است.
* همه آستانه‌ها از ThresholdSettings خوانده می‌شوند (Hard-Code نیست).
"""
from __future__ import annotations

import math
from typing import Optional

from app.core.models import ForecastPoint, ForecastResult
from app.core.settings import ThresholdSettings

REQUIRES_REVIEW = "REQUIRES_ENGINEER_REVIEW"
STATUS_OK = "OK"

# کدهای کیفیت
FLAG_INSUFFICIENT = "INSUFFICIENT_DATA"
FLAG_LOW_R2 = "LOW_R2"
FLAG_OUTLIER = "OUTLIER"
FLAG_STRUCTURAL = "STRUCTURAL_CHANGE"
FLAG_GAPS = "DATA_GAPS"
FLAG_FLAT = "NO_VARIATION"

FLAG_LABELS_FA = {
    FLAG_INSUFFICIENT: "داده تاریخی کافی نیست",
    FLAG_LOW_R2: "ضریب تعیین (R²) پایین است",
    FLAG_OUTLIER: "داده پرت (Outlier) شناسایی شد",
    FLAG_STRUCTURAL: "تغییر ساختاری ناگهانی (احتمال مانور/بازآرایی فیدر)",
    FLAG_GAPS: "داده سال‌های میانی ناقص است",
    FLAG_FLAT: "داده فاقد تغییر است (R² قابل محاسبه نیست)",
}


def _unique_sorted(years: list[int], values: list[float]) -> tuple[list[int], list[float]]:
    uniq: dict[int, float] = {}
    for y, v in zip(years, values):
        if y is None or v is None:
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if math.isnan(fv):
            continue
        uniq[int(y)] = fv
    ys = sorted(uniq)
    return ys, [uniq[y] for y in ys]


def _fit(years: list[int], values: list[float]):
    n = len(years)
    mx = sum(years) / n
    my = sum(values) / n
    sxx = sum((x - mx) ** 2 for x in years)
    sxy = sum((x - mx) * (y - my) for x, y in zip(years, values))
    slope = sxy / sxx if sxx else 0.0
    intercept = my - slope * mx
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(years, values))
    ss_tot = sum((y - my) ** 2 for y in values)
    r2 = 1.0 - ss_res / ss_tot if ss_tot else None
    return slope, intercept, r2, ss_res


def assess_quality(years: list[int], values: list[float],
                   th: Optional[ThresholdSettings] = None,
                   maneuver_years: Optional[list[int]] = None) -> dict:
    """کنترل کیفیت داده تاریخی؛ خروجی: flags / outlier_years / jump_years.

    maneuver_years: سال‌هایی که مهندس مانور فیدر را ثبت کرده است (اختیاری) —
    جهش در آن سال‌ها همچنان «نیازمند بررسی» است اما پیام علت را دقیق‌تر می‌کند.
    """
    th = th or ThresholdSettings()
    flags: list[str] = []
    outliers: list[int] = []
    jumps: list[int] = []
    years, values = _unique_sorted(years, values)
    n = len(years)

    if n < th.forecast_min_history:
        flags.append(FLAG_INSUFFICIENT)
        return {"flags": flags, "outlier_years": outliers, "jump_years": jumps,
                "r2": None, "slope": None}

    # --- فاصله بین سال‌ها ---
    if any(b - a > th.forecast_max_gap_years for a, b in zip(years, years[1:])):
        flags.append(FLAG_GAPS)

    # --- جهش ساختاری (مانور فیدر) ---
    for (y0, v0), (y1, v1) in zip(zip(years, values), zip(years[1:], values[1:])):
        if v0 > 0 and abs(v1 - v0) / v0 * 100.0 > th.forecast_jump_pct * max(1, y1 - y0):
            jumps.append(y1)
    if jumps:
        flags.append(FLAG_STRUCTURAL)

    slope, _icpt, r2, ss_res = _fit(years, values)

    # --- Outlier: باقیمانده پیش‌بینی Leave-One-Out (studentized) ---
    if n >= 5:
        for i in range(n):
            ys = years[:i] + years[i + 1:]
            vs = values[:i] + values[i + 1:]
            m = len(ys)
            sl, ic, _r2, ssr = _fit(ys, vs)
            mxs = sum(ys) / m
            sxx = sum((x - mxs) ** 2 for x in ys)
            if sxx == 0:
                continue
            d = values[i] - (sl * years[i] + ic)
            s_loo = math.sqrt(ssr / (m - 2)) if m > 2 else 0.0
            se = math.sqrt(1.0 + 1.0 / m + (years[i] - mxs) ** 2 / sxx)
            scale = max(s_loo * se, 1e-3 * max(abs(v) for v in values))
            if abs(d) / scale > th.forecast_outlier_sigma:
                outliers.append(years[i])
    if outliers:
        flags.append(FLAG_OUTLIER)

    # --- R² ---
    if r2 is None:
        flags.append(FLAG_FLAT)
    elif r2 < th.forecast_r2_min:
        flags.append(FLAG_LOW_R2)

    return {"flags": flags, "outlier_years": outliers, "jump_years": jumps,
            "r2": r2, "slope": slope}


def linear_forecast(history_years: list[int], history_values: list[float],
                    horizon: int = 5, min_points: int = 3,
                    th: Optional[ThresholdSettings] = None,
                    maneuver_years: Optional[list[int]] = None) -> ForecastResult:
    """رگرسیون خطی کمینه مربعات + کنترل کیفیت.

    سازگار با امضای قبلی؛ با ارسال th کنترل کیفیت کامل اعمال می‌شود، در غیر این
    صورت آستانه‌های پیش‌فرض ThresholdSettings استفاده می‌گردد.
    """
    th = th or ThresholdSettings()
    if th.forecast_min_history != min_points:
        th = ThresholdSettings(**{**th.__dict__, "forecast_min_history": min_points})
    years, values = _unique_sorted(history_years, history_values)

    if len(years) < min_points:
        return ForecastResult(
            method="none", history_years=years, history_values=values,
            note=f"داده تاریخی کافی نیست ({len(years)} نقطه؛ حداقل {min_points}).",
            review_status=REQUIRES_REVIEW, quality_flags=[FLAG_INSUFFICIENT])

    q = assess_quality(years, values, th, maneuver_years)
    slope, intercept, r2, _ = _fit(years, values)
    last = years[-1]
    preds = [ForecastPoint(year=last + k,
                           value_mw=round(max(slope * (last + k) + intercept, 0.0), 2))
             for k in range(1, horizon + 1)]
    flags = q["flags"]
    return ForecastResult(
        method="regression", points=preds,
        history_years=years, history_values=values,
        r2=round(r2, 3) if r2 is not None else None,
        slope_mw_per_year=round(slope, 4),
        review_status=REQUIRES_REVIEW if flags else STATUS_OK,
        quality_flags=flags, outlier_years=q["outlier_years"],
        jump_years=q["jump_years"],
        note="؛ ".join(FLAG_LABELS_FA[f] for f in flags))


def manual_forecast(points: list[tuple[int, float]]) -> ForecastResult:
    """پیش‌بینی دستی کارشناس — ذخیره بدون هیچ تغییری (تصمیم مهندس است)."""
    pts = sorted((ForecastPoint(year=int(y), value_mw=float(v)) for y, v in points),
                 key=lambda p: p.year)
    return ForecastResult(method="manual", points=pts)


def growth_pct_per_year(fc: ForecastResult) -> Optional[float]:
    """میانگین رشد سالانه (٪) نسبت به میانگین داده تاریخی."""
    if fc.method != "regression" or fc.slope_mw_per_year is None:
        return None
    if not fc.history_values:
        return None
    mean_v = sum(fc.history_values) / len(fc.history_values)
    if mean_v == 0:
        return None
    return abs(fc.slope_mw_per_year) / mean_v * 100.0
