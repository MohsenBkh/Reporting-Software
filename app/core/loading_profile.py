# -*- coding: utf-8 -*-
"""تحلیل پروفیل بار — روش‌های Excel / Paste / دستی (بخش ۹ سند)."""
from __future__ import annotations

import io
from typing import Optional

import pandas as pd

from app.core.models import ProfileStats
from app.utils.jalali import jalali_year

# نام‌های قابل قبول ستون‌ها (فارسی و انگلیسی)
COL_ALIASES = {
    "date": ["date", "تاریخ", "tarikh", "زمان"],
    "feeder": ["feeder", "fider", "فیدر", "فیدرها", "نام فیدر"],
    "p_mw": ["p_mw", "p", "p (mw)", "p(mw)", "توان اکتیو", "توان اکتیو (mw)", "mw"],
    "q_mvar": ["q_mvar", "q", "q (mvar)", "q(mvar)", "توان راکتیو", "توان راکتیو (mvar)"],
}


def _norm(s: str) -> str:
    return (str(s).strip().lower()
            .replace("ي", "ی").replace("ك", "ک")
            .replace("‌", " ").replace("_", " ")
            .replace("(", " ").replace(")", " ")
            .replace("  ", " ").strip())


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """ستون‌ها را به نام استاندارد date/feeder/p_mw/q_mvar تبدیل می‌کند."""
    rename = {}
    for col in df.columns:
        n = _norm(col)
        for std, aliases in COL_ALIASES.items():
            if n in [_norm(a) for a in aliases]:
                rename[col] = std
                break
    return df.rename(columns=rename)


def _to_jalali_str(value) -> str:
    """تاریخ ورودی (شمسی رشته‌ای یا میلادی) را به رشته شمسی یکدست می‌کند."""
    import datetime as _dt
    try:
        if isinstance(value, (_dt.datetime, _dt.date, pd.Timestamp)):
            import jdatetime
            jd = jdatetime.date.fromgregorian(date=value)
            return jd.strftime("%Y/%m/%d")
    except Exception:
        pass
    s = str(value).strip().replace("-", "/")
    parts = s.split("/")
    if len(parts) == 3:
        try:
            y, m, d = int(float(parts[0])), int(float(parts[1])), int(float(parts[2]))
            return f"{y:04d}/{m:02d}/{d:02d}"
        except ValueError:
            return s
    return s


def parse_profile(raw: str | pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """ورودی متن چسبانده‌شده یا DataFrame را به پروفیل استاندارد تبدیل می‌کند.

    خروجی: (DataFrame با ستون‌های date/feeder/p_mw/q_mvar ، لیست خطاها)
    """
    errors: list[str] = []
    try:
        if isinstance(raw, str):
            sep = "\t" if "\t" in raw.splitlines()[0] else (
                ";" if raw.splitlines()[0].count(";") > raw.splitlines()[0].count(",") else ",")
            df = pd.read_csv(io.StringIO(raw), sep=sep, engine="python")
        else:
            df = raw.copy()
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame(), [f"خواندن داده ناموفق بود: {exc}"]

    df = normalize_columns(df)
    for col in ("date", "p_mw"):
        if col not in df.columns:
            errors.append(f"ستون {col} پیدا نشد.")
    if errors:
        return pd.DataFrame(), errors

    for col in ("feeder", "q_mvar"):
        if col not in df.columns:
            df[col] = None

    df = df.dropna(subset=["p_mw"])
    df["p_mw"] = pd.to_numeric(df["p_mw"], errors="coerce")
    df["q_mvar"] = pd.to_numeric(df.get("q_mvar"), errors="coerce")
    df["feeder"] = df["feeder"].fillna("").astype(str).str.strip()
    df = df.dropna(subset=["p_mw"]).sort_values("date").reset_index(drop=True)
    if df.empty:
        errors.append("داده معتبری در ستون توان اکتیو یافت نشد.")
    return df, errors


def compute_stats(df: pd.DataFrame) -> ProfileStats:
    """آمار پروفیل: پیک، تاریخ پیک، ضریب توان در پیک، بازه (بخش ۹ سند)."""
    if df is None or df.empty or "p_mw" not in df.columns:
        return ProfileStats()
    dates = df["date"].astype(str)
    idx = df["p_mw"].idxmax()
    peak = df.loc[idx]
    q_at_peak = peak.get("q_mvar")
    pf = None
    try:
        if pd.notna(q_at_peak) and float(q_at_peak) is not None:
            p, q = float(peak["p_mw"]), float(q_at_peak)
            pf = round(p / (p * p + q * q) ** 0.5, 2)
    except (TypeError, ValueError):
        pf = None
    return ProfileStats(
        peak_p_mw=round(float(peak["p_mw"]), 2),
        peak_date=_to_jalali_str(peak.get("date", "")),
        peak_q_mvar=round(float(q_at_peak), 2) if pd.notna(q_at_peak) else None,
        power_factor_at_peak=pf,
        min_p_mw=round(float(df["p_mw"].min()), 2),
        max_p_mw=round(float(df["p_mw"].max()), 2),
        avg_p_mw=round(float(df["p_mw"].mean()), 2),
        period_start=_to_jalali_str(dates.iloc[0]),
        period_end=_to_jalali_str(dates.iloc[-1]),
        n_points=int(len(df)),
    )


def annual_peaks(df: pd.DataFrame) -> tuple[list[int], list[float]]:
    """پیک سالانه (به تفکیک سال شمسی) — ورودی پیش‌بینی."""
    if df is None or df.empty:
        return [], []
    d = df.copy()
    d["year"] = d["date"].astype(str).map(lambda s: jalali_year(_to_jalali_str(s)))
    d = d.dropna(subset=["year"])
    if d.empty:
        return [], []
    grouped = d.groupby("year")["p_mw"].max()
    years = [int(y) for y in grouped.index]
    values = [round(float(v), 3) for v in grouped.values]
    return years, values


def filter_feeder(df: pd.DataFrame, feeder_name: str) -> pd.DataFrame:
    if df is None or df.empty or "feeder" not in df.columns or not feeder_name:
        return df
    return df[df["feeder"].str.strip() == feeder_name.strip()].reset_index(drop=True)
