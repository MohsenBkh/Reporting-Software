# -*- coding: utf-8 -*-
"""محاسبات مهندسی: تغییرات Before/After، درصد تغییرات و طبقه‌بندی (بخش ۱۴ و ۳۸ سند).

اصل مهم: هیچ عدد یا نتیجه‌ای ساخته نمی‌شود — فقط از داده‌های واردشده محاسبه می‌شود.
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.models import Feeder, Project, REQUEST_INCREASE, REQUEST_NEW
from app.core.settings import AppSettings


def _pct_change(before: Optional[float], after: Optional[float]) -> Optional[float]:
    """درصد تغییر نسبت به مقدار قبل؛ None اگر داده نباشد یا قبل صفر باشد."""
    if before is None or after is None or before == 0:
        return None
    return (after - before) / abs(before) * 100.0


def _delta(before: Optional[float], after: Optional[float]) -> Optional[float]:
    if before is None or after is None:
        return None
    return after - before


def loading_class(loading_pct: Optional[float], th: Any) -> str:
    """نام طبقه بارگذاری — هم‌ساز با قواعد loading_rules.json و حدآستانه‌های تنظیمات."""
    if loading_pct is None:
        return "نامشخص"
    if loading_pct > th.loading_heavy_pct:
        return "بحرانی"
    if loading_pct > th.loading_semi_pct:
        return "پربار"
    if loading_pct > th.loading_normal_pct:
        return "نسبتاً پربار"
    if loading_pct > th.loading_light_pct:
        return "عادی و نسبتاً کم‌بار"
    return "کم‌بار"


def feeder_metrics(feeder: Feeder, project: Project, settings: AppSettings) -> dict[str, Any]:
    """تمام کمیت‌های محاسبه‌شده یک فیدر — ورودی Rule Engine و جدول‌ها."""
    th = settings.thresholds
    b, a = feeder.before, feeder.after

    d_i = _delta(b.current_a, a.current_a)
    d_i_pct = _pct_change(b.current_a, a.current_a)
    d_loss = _delta(b.loss_kw, a.loss_kw)
    d_loss_pct = _pct_change(b.loss_kw, a.loss_kw)
    d_v = _delta(b.min_voltage_pu, a.min_voltage_pu)
    d_v_pct = _pct_change(b.min_voltage_pu, a.min_voltage_pu)

    loading_pct = None
    if feeder.capacity_mw and feeder.peak_load_mw is not None:
        loading_pct = feeder.peak_load_mw / feeder.capacity_mw * 100.0

    added = project.added_power_mw()
    loading_after_pct = None
    if feeder.capacity_mw and feeder.peak_load_mw is not None and added is not None:
        loading_after_pct = (feeder.peak_load_mw + added) / feeder.capacity_mw * 100.0

    i_loading_pct = None
    if feeder.max_current_a and a.current_a is not None:
        i_loading_pct = a.current_a / feeder.max_current_a * 100.0

    return {
        "loading_pct": loading_pct,
        "loading_class": loading_class(loading_pct, th),
        "loading_after_pct": loading_after_pct,
        "loading_after_class": loading_class(loading_after_pct, th),
        "i_loading_pct": i_loading_pct,
        "d_i": d_i, "d_i_pct": d_i_pct,
        "d_loss": d_loss, "d_loss_pct": d_loss_pct,
        "d_v": d_v, "d_v_pct": d_v_pct,
    }


def build_feeder_context(feeder: Feeder, project: Project,
                         settings: AppSettings) -> dict[str, Any]:
    """Context تخت برای ارزیابی قواعدِ یک فیدر."""
    th = settings.thresholds
    m = feeder_metrics(feeder, project, settings)
    b, a = feeder.before, feeder.after

    v_before_ok = (b.min_voltage_pu is not None
                   and th.voltage_min_pu <= b.min_voltage_pu <= th.voltage_max_pu)
    v_after_ok = (a.min_voltage_pu is not None
                  and th.voltage_min_pu <= a.min_voltage_pu <= th.voltage_max_pu)
    d_v_pct = m["d_v_pct"]
    v_change_ok = d_v_pct is not None and abs(d_v_pct) <= th.voltage_change_max_pct

    fc = feeder.forecast
    growth_pct = None
    if fc.slope_mw_per_year is not None and fc.history_values:
        mean_v = sum(fc.history_values) / len(fc.history_values)
        if mean_v:
            growth_pct = abs(fc.slope_mw_per_year) / mean_v * 100.0

    ctx: dict[str, Any] = dict(m)
    # نام مستعار مورد استفاده در فایل‌های قواعد JSON
    ctx["f_loading_pct"] = m["loading_pct"]
    ctx.update({
        "req_type": project.request_type,
        "f_name": feeder.name,
        "f_capacity": feeder.capacity_mw,
        "f_peak": feeder.peak_load_mw,
        "f_imax": feeder.max_current_a,
        "has_capacity": feeder.capacity_mw is not None and feeder.capacity_mw > 0,
        "has_imax": feeder.max_current_a is not None and feeder.max_current_a > 0,
        "has_before": b.is_complete(),
        "has_after": a.is_complete(),
        "b_i": b.current_a, "b_loss": b.loss_kw, "b_v": b.min_voltage_pu,
        "b_vbus": b.applicant_bus_voltage_pu,
        "a_i": a.current_a, "a_loss": a.loss_kw, "a_v": a.min_voltage_pu,
        "a_vbus": a.applicant_bus_voltage_pu,
        "v_before_ok": v_before_ok, "v_after_ok": v_after_ok,
        "v_change_ok": v_change_ok,
        "has_profile": bool(feeder.profile_stats.n_points),
        "has_forecast": fc.available,
        "fc_method": fc.method,
        "fc_growth_pct": growth_pct,
        "fc_review": fc.needs_review,
        # تفکیک ولتاژ مطلق از تغییر ناشی از متقاضی (v1.0.3)
        "v_caused_bad": bool(b.is_complete() and a.is_complete()
                             and ((v_before_ok and not v_after_ok) or not v_change_ok)),
        "v_preexisting": bool(b.is_complete() and a.is_complete()
                              and not v_before_ok and not v_after_ok and v_change_ok),
        "i_over": bool(feeder.max_current_a and a.current_a is not None
                       and a.current_a > feeder.max_current_a),
        # حدآستانه‌ها — بدون Hard-Code
        "voltage_min_pu": th.voltage_min_pu,
        "voltage_max_pu": th.voltage_max_pu,
        "voltage_change_max_pct": th.voltage_change_max_pct,
        "loading_light_pct": th.loading_light_pct,
        "loading_normal_pct": th.loading_normal_pct,
        "loading_semi_pct": th.loading_semi_pct,
        "loading_heavy_pct": th.loading_heavy_pct,
        "loss_change_warn_pct": th.loss_change_warn_pct,
        "growth_low_pct": th.growth_low_pct,
        "growth_high_pct": th.growth_high_pct,
    })
    return ctx


def build_project_context(project: Project, settings: AppSettings) -> dict[str, Any]:
    """Context جمع‌بندی برای کل پروژه.

    اصل v1.0.3: ولتاژ مطلق (خارج از محدوده بودن) با تغییر ناشی از متقاضی تفکیک می‌شود؛
    افت ولتاژ موجود که بار متقاضی آن را ایجاد نکرده باعث «امکان‌پذیر نیست» نمی‌شود.
    افزایش تلفات به‌تنهایی نیز هیچ‌گاه منجر به نتیجه «مشروط به اقدام اصلاحی» نمی‌شود.
    """
    th = settings.thresholds
    active = project.active_feeders        # v1.2.0: فقط فیدرهای روشن (On/Off)
    feeder_ctxs = [build_feeder_context(f, project, settings) for f in active]
    with_after = [c for c in feeder_ctxs if c["has_after"] and c["has_before"]]
    has_after = len(with_after) == len(active) and bool(active)

    any_i_over = any(c["i_over"] for c in with_after)
    caused_v = [c["v_caused_bad"] for c in with_after]
    any_caused_v = any(caused_v)
    all_v_caused_bad = bool(with_after) and all(caused_v)
    any_preexisting_v = any(c["v_preexisting"] for c in with_after)
    any_loss_up = any(c["d_loss_pct"] is not None and c["d_loss_pct"] > th.loss_change_warn_pct
                      for c in with_after)
    any_caused_issue = any_i_over or any_caused_v
    all_ok = bool(with_after) and not any_caused_issue and not any_preexisting_v

    return {
        "has_after": has_after,
        "all_ok": all_ok,
        "any_issue": any_caused_issue or any_preexisting_v,
        "any_caused_issue": any_caused_issue,
        "any_preexisting_v": any_preexisting_v,
        "all_v_caused_bad": all_v_caused_bad,
        "any_i_over": any_i_over,
        "any_loss_up": any_loss_up,      # صرفاً اطلاع‌رسانی؛ مبنای اقدام اصلاحی نیست
        "n_feeders": len(active),
        "n_with_after": len(with_after),
        "voltage_change_max_pct": th.voltage_change_max_pct,
    }


def issue_summary(project: Project, settings: AppSettings) -> str:
    """خلاصه متنی مشکلات برای متن جمع‌بندی مشروط — فقط از داده‌ها.

    هر مشکل فقط وقتی گزارش می‌شود که واقعاً رخ داده باشد؛ فیدر سالم
    هرگز «افزایش قابل توجه تلفات» یا مشکل ساختگی نمی‌گیرد.
    """
    th = settings.thresholds
    issues: list[str] = []
    for f in project.active_feeders:
        ctx = build_feeder_context(f, project, settings)
        if not (ctx["has_before"] and ctx["has_after"]):
            continue
        if ctx["has_imax"] and ctx["a_i"] is not None and ctx["a_i"] > ctx["f_imax"]:
            issues.append(f"جریان بیش از ظرفیت هدایتی فیدر {f.name}")
        if ctx["v_caused_bad"]:
            if ctx["v_before_ok"] and not ctx["v_after_ok"]:
                issues.append(f"خروج حداقل ولتاژ فیدر {f.name} از محدوده مجاز به‌دلیل بار جدید")
            else:
                issues.append(f"تغییر ولتاژ فیدر {f.name} بیش از حد مجاز دستورالعمل")
    if not issues:
        return "بدون مشکل خاصی"
    return " و ".join(issues[:3]) + " داشته است"
