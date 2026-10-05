# -*- coding: utf-8 -*-
"""تحلیل مطالعه مصارف سنگین — «تغییرات آرنا» v1.1.0.

این ماژول پل میان *مدل داده* و *Rule Engine* است:

1. برای هر دسته داده (تقاضا، پست‌های نزدیک، خطوط نزدیک، متقاضیان همزمان، توپولوژی،
   سناریوها، بررسی اقتصادی، کنترل ناسازگاری) یک Context می‌سازد که فقط شامل
   **مقادیر ورودی و محاسبات صریح** است.
2. Ruleهای تحلیلی (JSON) را روی این Contextها اجرا می‌کند و
   :class:`~app.rules.outcome.RuleResult` استاندارد تولید می‌کند.
3. هیچ عددی حدس نمی‌زند، هیچ آستانه‌ای نمی‌سازد و هیچ نتیجه‌ای خارج از داده ورودی
   تولید نمی‌کند. نبود آستانه → MISSING_RULE و نبود داده → MISSING_DATA.

زنجیره ردیابی هر نتیجه: Input → Calculation → Rule → Finding → Evidence → Report Text
"""
from __future__ import annotations

import math
from typing import Any, Optional

from app.core.models import (CoincidentDemand, DemandInfo, Feeder, LineCandidate,
                             NeighborFeeder, Project, SubstationCandidate,
                             SupplyScenario)
from app.core.settings import AppSettings
from app.rules.outcome import (STATUS_DATA_ERROR, STATUS_MISSING_DATA,
                               STATUS_REQUIRES_REVIEW, RuleResult)
from app.rules.rule_engine import RuleEngine
from app.utils.formatting import fmt

# ---------------------------------------------------------------------------
# ثابت‌های داخلی (نه آستانه مهندسی — صرفاً تلورانس عددی مقایسه)
# ---------------------------------------------------------------------------
_EPS = 1e-9                     # تلورانس مقایسه برابری دقیق اعداد
_LIST_SEP = "؛ "

STUDY_DOMAINS = ("study_demand", "study_substation", "study_line", "study_coincidence",
                 "study_topology", "study_scenario", "study_economics", "study_crosscheck",
                 "study_loading", "study_rearrange")

# مبنای آستانه‌های بارگذاری فیدر (۷/۸ مگاوات) — دستور کارفرما/سیاست بهره‌برداری
SOURCE_LOADING_POLICY = "سیاست بهره‌برداری (دستور کارفرما)"
PAGE_LOADING_POLICY = ("تنظیمات → مطالعه و هزینه — آستانه‌های بارگذاری فیدر "
                       "(پیش‌فرض ۷ و ۸ مگاوات)")


# ---------------------------------------------------------------------------
# ابزارهای کمکی
# ---------------------------------------------------------------------------
def _sorted_context(ctx: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in ctx.items() if v is not None}


def _join(items: list[str]) -> str:
    return _LIST_SEP.join(x for x in items if x)


def _threshold_flags(settings: AppSettings) -> dict[str, Any]:
    """همه آستانه‌ها + پرچم has_<key> برای تشخیص MISSING_RULE در Rule Engine."""
    flat = settings.thresholds_flat()
    out: dict[str, Any] = {}
    for key, value in flat.items():
        out[key] = value
        out[f"has_{key}"] = value is not None
    return out


def _loading_pct(peak: Optional[float], capacity: Optional[float]) -> Optional[float]:
    """درصد بارگیری از نسبت پیک به ظرفیت — فقط با داده موجود."""
    if peak is None or not capacity:
        return None
    return peak / capacity * 100.0


def _delta(after: Optional[float], before: Optional[float]) -> Optional[float]:
    """Delta = After − Before (فقط با داده کامل)."""
    if after is None or before is None:
        return None
    return after - before


def _rel_pct(after: Optional[float], before: Optional[float]) -> Optional[float]:
    if after is None or before is None or before == 0:
        return None
    return (after - before) / abs(before) * 100.0


# ---------------------------------------------------------------------------
# A) اطلاعات تقاضا
# ---------------------------------------------------------------------------
def demand_context(project: Project, settings: AppSettings) -> dict[str, Any]:
    d: DemandInfo = project.demand
    factor = d.coincidence_factor()
    ctx: dict[str, Any] = {
        "req_type": project.request_type,
        "demand_without_coincidence_kw": d.without_coincidence_kw,
        "demand_with_coincidence_kw": d.with_coincidence_kw,
        "existing_demand_kw": d.existing_demand_kw,
        "requested_power_kw": project.requested_power_kw,
        "existing_power_kw": project.existing_power_kw,
        "coincidence_factor": factor,
        "coincidence_factor_eq_one": factor is not None and abs(factor - 1.0) <= _EPS,
        "coincidence_factor_gt_one": factor is not None and factor > 1.0 + _EPS,
        "demand_for_analysis_kw": d.analysis_demand_kw(),
        "has_demand_with": d.with_coincidence_kw is not None,
        "has_demand_without": d.without_coincidence_kw is not None,
        "has_existing_demand": d.existing_demand_kw is not None,
        "has_demand_for_analysis": d.analysis_demand_kw() is not None,
        "delta_power_kw": None,
    }
    if project.request_type == "increase":
        ctx["delta_power_kw"] = _delta(project.requested_power_kw, project.existing_power_kw)
    ctx.update(_threshold_flags(settings))
    return ctx


# ---------------------------------------------------------------------------
# B) ایستگاه‌های نزدیک
# ---------------------------------------------------------------------------
def substation_context(project: Project, settings: AppSettings,
                       ss: SubstationCandidate) -> dict[str, Any]:
    comp_t1 = _loading_pct(ss.t1_peak_mva, ss.transformer_capacity_mva)
    comp_t2 = _loading_pct(ss.t2_peak_mva, ss.transformer_capacity_mva)
    loadings = [v for v in (ss.t1_loading_percent, ss.t2_loading_percent) if v is not None]
    computed = [v for v in (comp_t1, comp_t2) if v is not None]
    diff_t1 = (ss.t1_loading_percent - comp_t1
               if ss.t1_loading_percent is not None and comp_t1 is not None else None)
    tolerance = settings.study.substation_loading_tolerance_pct
    mismatch = (diff_t1 is not None and tolerance is not None
                and abs(diff_t1) > tolerance + _EPS)
    ctx: dict[str, Any] = {
        "ss_name": ss.display_name,
        "ss_uid": ss.uid,
        "ss_distance_km": ss.distance_km,
        "ss_transformer_capacity_mva": ss.transformer_capacity_mva,
        "ss_t1_loading_pct": ss.t1_loading_percent,
        "ss_t2_loading_pct": ss.t2_loading_percent,
        "ss_t1_peak_mva": ss.t1_peak_mva,
        "ss_t2_peak_mva": ss.t2_peak_mva,
        "ss_feeder_count": ss.feeder_count,
        "ss_peak_year": ss.peak_year,
        "ss_office": ss.office,
        "ss_computed_t1_pct": comp_t1,
        "ss_computed_t2_pct": comp_t2,
        "ss_loading_diff_t1_pct": diff_t1,
        "ss_max_loading_pct": max(loadings) if loadings else (max(computed) if computed else None),
        "ss_loading_check_data_ok": (ss.t1_loading_percent is not None
                                     and ss.t1_peak_mva is not None
                                     and bool(ss.transformer_capacity_mva)),
        "ss_loading_mismatch": mismatch,
        "ss_complete": not ss.missing_fields(),
        "ss_missing_fields": "، ".join(ss.missing_fields()) or "—",
        "has_substations": bool(project.active_substations),
    }
    ctx.update(_threshold_flags(settings))
    return ctx


def substation_contexts(project: Project, settings: AppSettings) -> list[dict[str, Any]]:
    """Context ایستگاه‌های «فعال» (کلید On/Off در جدول ورودی)."""
    return [substation_context(project, settings, ss) for ss in project.active_substations]


# ---------------------------------------------------------------------------
# C) خطوط نزدیک
# ---------------------------------------------------------------------------
def line_context(project: Project, settings: AppSettings,
                 ln: LineCandidate) -> dict[str, Any]:
    d_v = _delta(ln.vdrop_after_percent, ln.vdrop_before_percent)
    computed_i = None
    if ln.peak_mva is not None and project.network_voltage_kv:
        computed_i = ln.peak_mva * 1e6 / (math.sqrt(3) * project.network_voltage_kv * 1e3)
    diff_i_pct = _rel_pct(ln.peak_current_a, computed_i)
    tolerance = settings.study.line_current_tolerance_pct
    mismatch_i = (diff_i_pct is not None and tolerance is not None
                  and abs(diff_i_pct) > tolerance + _EPS)
    ctx: dict[str, Any] = {
        "line_name": ln.display_name,
        "line_uid": ln.uid,
        "line_office": ln.office,
        "line_distance_m": ln.distance_m,
        "line_peak_mva": ln.peak_mva,
        "line_peak_mw": ln.peak_mw,
        "line_peak_current_a": ln.peak_current_a,
        "line_peak_year": ln.peak_year,
        "line_v_before_pct": ln.vdrop_before_percent,
        "line_v_after_pct": ln.vdrop_after_percent,
        "line_delta_v_pp": d_v,
        "line_delta_v_rel_pct": _rel_pct(ln.vdrop_after_percent, ln.vdrop_before_percent),
        "line_sc_max_ka": ln.sc_max_ka,
        "line_sc_min_ka": ln.sc_min_ka,
        "line_max_current_a": ln.max_current_a,
        "line_computed_current_a": computed_i,
        "line_current_diff_pct": diff_i_pct,
        "line_current_mismatch": mismatch_i,
        "line_current_loading_pct": (ln.peak_current_a / ln.max_current_a * 100.0
                                     if ln.max_current_a and ln.peak_current_a is not None else None),
        "has_line_peak": ln.peak_mva is not None or ln.peak_current_a is not None,
        "has_line_peak_mva": ln.peak_mva is not None,
        "has_line_before_after": (ln.vdrop_before_percent is not None
                                  and ln.vdrop_after_percent is not None),
        "has_line_current_limit": bool(ln.max_current_a),
        "has_line_sc": ln.sc_max_ka is not None,
        "has_network_voltage_kv": bool(project.network_voltage_kv),
        "network_voltage_kv": project.network_voltage_kv,
        "line_missing_fields": "، ".join(ln.missing_fields()) or "—",
        "has_lines": bool(project.nearby_lines),
    }
    ctx.update(_threshold_flags(settings))
    return ctx


def line_contexts(project: Project, settings: AppSettings) -> list[dict[str, Any]]:
    """Context خطوط «فعال» (کلید On/Off در جدول ورودی)."""
    return [line_context(project, settings, ln) for ln in project.active_lines]


# ---------------------------------------------------------------------------
# D) متقاضیان/تقاضاهای همزمان
# ---------------------------------------------------------------------------
def coincidence_context(project: Project, settings: AppSettings) -> dict[str, Any]:
    rows: list[CoincidentDemand] = project.active_coincident_demands
    deltas = [r.computed_delta_kw() for r in rows]
    known_deltas = [d for d in deltas if d is not None]
    new_powers = [r.new_requested_power_kw for r in rows
                  if r.new_requested_power_kw is not None]
    incomplete = [r.name or f"ردیف {i + 1}"
                  for i, r in enumerate(rows) if r.missing_fields()]
    locations = [r.location for r in rows if r.location]
    demand_ctx = demand_context(project, settings)
    applicant_kw = demand_ctx.get("demand_for_analysis_kw")
    total = (applicant_kw or 0.0) + sum(known_deltas) if known_deltas else None
    if applicant_kw is None and not known_deltas:
        total = None

    # داده مبنا برای کنترل SUM (بند ۵ صورت‌مسئله)
    if not rows and applicant_kw is not None:
        itemized = [applicant_kw]
    elif rows:
        itemized = ([applicant_kw] if applicant_kw is not None else []) + known_deltas
    else:
        itemized = []
    sum_changes = sum(itemized) if itemized else None
    reported = project.reported_total_additional_load_kw
    tolerance = settings.study.load_sum_tolerance_kw
    if sum_changes is not None and reported is not None:
        diff = sum_changes - reported
        consistent = abs(diff) <= (_EPS if tolerance is None else tolerance + _EPS)
        has_sum_check = True
    else:
        diff = None
        consistent = False
        has_sum_check = False

    ctx: dict[str, Any] = {
        "cd_count": len(rows),
        "cd_list": _join([f"{r.name or 'بدون نام'} ({fmt(r.computed_delta_kw(), 0)} کیلووات)"
                          for r in rows]) or "—",
        "cd_locations": _join(locations) or "—",
        "cd_sum_delta_kw": sum(known_deltas) if known_deltas else None,
        "cd_sum_new_power_kw": sum(new_powers) if new_powers else None,
        "cd_total_new_load_kw": total,
        "cd_incomplete_rows": _join(incomplete) or "—",
        "cd_complete": not incomplete,
        "has_coincident_demands": bool(rows),
        # کنترل SUM (Cross Validation)
        "sum_new_demand_changes_kw": sum_changes,
        "reported_total_additional_load_kw": reported,
        "load_sum_diff_kw": diff,
        "load_sum_consistent": consistent,
        "has_load_sum_check": has_sum_check,
        "has_reported_total_additional_load_kw": reported is not None,
        "load_sum_tolerance_kw": tolerance,
        "has_load_sum_tolerance_kw": tolerance is not None,
        # کنترل مبنای تقاضا
        "requested_power_kw": project.requested_power_kw,
        "demand_used_in_analysis_kw": project.demand_used_in_analysis_kw,
        "has_demand_used_in_analysis_kw": project.demand_used_in_analysis_kw is not None,
        "demand_base_check_enabled": (project.requested_power_kw is not None
                                      and project.demand_used_in_analysis_kw is not None),
        "cd_reported_diff_kw": (total - reported
                                if total is not None and reported is not None else None),
    }
    # داده‌های تقاضا (مبنای تحلیل، دامنه شمول) نیز در همین Context لازم است
    ctx.update(demand_context(project, settings))
    base_tolerance = settings.study.load_sum_tolerance_kw
    if ctx["demand_base_check_enabled"]:
        base_diff = project.requested_power_kw - project.demand_used_in_analysis_kw
        ctx["demand_base_diff_kw"] = base_diff
        ctx["demand_base_consistent"] = abs(base_diff) <= (_EPS if base_tolerance is None
                                                           else base_tolerance + _EPS)
        ctx["has_demand_base_check"] = True
    else:
        ctx["demand_base_diff_kw"] = None
        ctx["demand_base_consistent"] = False
        ctx["has_demand_base_check"] = False
    ctx.update(_threshold_flags(settings))
    return ctx


# ---------------------------------------------------------------------------
# توپولوژی تأمین مشترک چند نقطه تقاضا
# ---------------------------------------------------------------------------
def topology_context(project: Project, settings: AppSettings) -> dict[str, Any]:
    n_points = 1 + len(project.active_coincident_demands)
    coh = coincidence_context(project, settings)
    distances = [ss.distance_km for ss in project.active_substations
                 if ss.distance_km is not None]
    ctx: dict[str, Any] = {
        "n_demand_points": n_points,
        "n_demand_points_ge_2": n_points >= 2,
        "n_demand_points_lt_2": n_points < 2,
        "cd_locations": coh.get("cd_locations"),
        "min_distance_km": min(distances) if distances else None,
        "min_substation_distance_km": min(distances) if distances else None,
        "nearest_substation_names": _join(
            [ss.display_name for ss in project.active_substations
             if ss.distance_km == min(distances)]) if distances else None,
        "has_joint_supply_study": project.joint_supply_feasible is not None,
        "has_joint_supply_evidence": bool((project.joint_supply_evidence or "").strip()),
        "joint_supply_feasibility": ("امکان‌پذیر" if project.joint_supply_feasible
                                     else "امکان‌پذیر نیست")
        if project.joint_supply_feasible is not None else None,
        "joint_supply_note": project.joint_supply_note or "—",
    }
    ctx.update(_threshold_flags(settings))
    return ctx


# ---------------------------------------------------------------------------
# E) سناریوها و بررسی اقتصادی
# ---------------------------------------------------------------------------
def scenario_context(project: Project, settings: AppSettings,
                     scenarios: list[SupplyScenario]) -> dict[str, Any]:
    ln_ctxs = line_contexts(project, settings)
    names = [c["line_name"] for c in ln_ctxs]
    distances = [ss.distance_km for ss in project.active_substations
                 if ss.distance_km is not None]
    missing_rows = [f"{s.display_title}: " + "، ".join(s.missing_fields())
                    for s in scenarios if s.missing_fields()]
    ctx: dict[str, Any] = {
        "scenario_count": len(scenarios),
        "has_scenarios": bool(scenarios),
        "scenario_titles": "، ".join(f"{s.display_title} ({s.kind})" for s in scenarios) or "—",
        "scenarios_complete": not missing_rows,
        "scenarios_missing_fields": _join(missing_rows) or "—",
        "has_selection_criterion": bool((project.scenario_selection_criterion or "").strip()),
        "line_candidates_count": len(names),
        "line_candidates_ge_2": len(names) >= 2,
        "has_nearby_lines": bool(names),
        "ln_names": "، ".join(names) or "—",
        "ln_summary": _join([f"{c['line_name']}: پیک {fmt(c['line_peak_mva'], 2)} MVA / افت ولتاژ بعد "
                             f"{fmt(c['line_v_after_pct'], 2)}٪" for c in ln_ctxs]) or "—",
        "ln_loading_summary": _join([f"{c['line_name']}: {fmt(c['line_peak_mva'], 2)} MVA"
                                     for c in ln_ctxs]) or "—",
        "min_substation_distance_km": min(distances) if distances else None,
        "nearest_substation_names": _join([ss.display_name for ss in project.active_substations
                                           if ss.distance_km == min(distances)]) if distances else None,
    }
    # v1.2.0 — وضعیت بارگذاری فیدرها (پیک + بار جدید) و کاندید بازآرایی
    # مبنای سناریوی «بازآرایی فیدر و انتقال بار» (SC-GEN-REARRANGE)
    lds = feeder_loading_contexts(project, settings)
    ctx["ld_count"] = len(lds)
    ctx["has_feeder_loading_context"] = bool(lds)
    ctx["feeder_total_ge_critical"] = any(c.get("feeder_total_ge_critical") for c in lds)
    ctx["feeder_total_ge_severe"] = any(c.get("feeder_total_ge_severe") for c in lds)
    ctx["has_rearrange_candidate"] = any(c.get("has_rearrange_candidate") for c in lds)
    worst = None
    for c in lds:
        value = c.get("feeder_total_load_mw")
        if value is None:
            continue
        if worst is None or value > (worst.get("feeder_total_load_mw") or -1):
            worst = c
    if worst is not None:
        prefixes = ("feeder_", "added_", "over_", "rearrange_", "transfer_", "nf_",
                    "has_feeder", "has_added", "has_rearrange", "has_neighbor",
                    "threshold_order_error")
        ctx.update({k: v for k, v in worst.items() if k.startswith(prefixes)})

    ctx.update(demand_context(project, settings))
    topo = topology_context(project, settings)
    for key in ("n_demand_points", "n_demand_points_ge_2", "n_demand_points_lt_2",
                "cd_locations", "min_distance_km", "has_joint_supply_study",
                "has_joint_supply_evidence", "joint_supply_feasibility"):
        ctx[key] = topo.get(key)
    ctx.update(_threshold_flags(settings))
    return ctx


def cost_estimate(scenario: SupplyScenario, project: Project,
                  settings: AppSettings) -> dict[str, Any]:
    """برآورد پارامتریک هزینه یک سناریو (بدون Hard-Code و بدون فرض مقدار).

    خروجی:
        breakdown: {نام قلم: مقدار یا None}
        estimated_total: جمع اقلام موجود یا None
        missing_items: اقلام ناموجود (شامل پارامترهای هزینه تعریف‌نشده)
        status: OK | MISSING_DATA
    """
    costs = settings.costs
    breakdown: dict[str, Optional[float]] = {}
    missing: list[str] = []

    def _add(label: str, value: Optional[float], unit_note: str = "") -> None:
        if value is None:
            missing.append(f"{label}{(' — ' + unit_note) if unit_note else ''}")
        breakdown[label] = value

    if scenario.required_line_length_km is None or scenario.overhead_percent is None \
            or scenario.underground_percent is None:
        missing.append("طول شبکه / درصد خط هوایی و زمینی")
    else:
        oh_km, ug_km = scenario.overhead_km(), scenario.underground_km()
        _add("شبکه هوایی", (oh_km * costs.overhead_per_km_million
                            if oh_km is not None and costs.overhead_per_km_million is not None
                            else None), "پارامتر هزینه هوایی تعریف نشده")
        _add("شبکه زمینی", (ug_km * costs.underground_per_km_million
                            if ug_km is not None and costs.underground_per_km_million is not None
                            else None), "پارامتر هزینه زمینی تعریف نشده")

    _add("پست زمینی", costs.ground_substation_million, "پارامتر تعریف نشده")
    _add("تجهیزات کلیدزنی", costs.switchgear_million, "پارامتر تعریف نشده")
    _add("تجهیزات حفاظتی", costs.protection_million, "پارامتر تعریف نشده")
    _add("سایر تجهیزات", costs.other_equipment_million, "پارامتر تعریف نشده")

    values = [v for v in breakdown.values() if v is not None]
    total = sum(values) if values else None
    if total is None:
        status = "MISSING_DATA"          # هیچ قلمی قابل محاسبه نیست
    elif missing:
        status = "PARTIAL"               # جمع اقلام شناخته‌شده + فهرست اقلام ناموجود
    else:
        status = "OK"
    return {
        "breakdown": breakdown,
        "estimated_total": total,
        "missing_items": missing,
        "status": status,
    }


def economics_context(project: Project, settings: AppSettings,
                      scenario: SupplyScenario) -> dict[str, Any]:
    est = cost_estimate(scenario, project, settings)
    breakdown_txt = _join([f"{k}: {fmt(v, 0)}" for k, v in est["breakdown"].items()
                           if v is not None]) or "—"
    missing_txt = _join(est["missing_items"]) or "—"
    distances = [ss.distance_km for ss in project.active_substations
                 if ss.distance_km is not None]
    min_dist = min(distances) if distances else None
    length = scenario.required_line_length_km
    ctx: dict[str, Any] = {
        "scenario_kind": scenario.kind,
        "scenario_key": scenario.key,
        "scenario_title": scenario.display_title,
        "scenario_rule_id": scenario.rule_id,
        "scenario_cost_million": scenario.estimated_cost_million,
        "scenario_cost_available": scenario.estimated_cost_million is not None,
        "scenario_cost_is_zero": (scenario.estimated_cost_million is not None
                                  and abs(scenario.estimated_cost_million) <= _EPS),
        "scenario_cost_items": _join([f"{k}: {fmt(v, 0)}" for k, v in (scenario.cost_items or {}).items()
                                      if v is not None]) or "—",
        "scenario_cost_note": ("، " + scenario.cost_note) if scenario.cost_note else "",
        "scenario_excluded_items_present": bool(scenario.cost_excluded_items),
        "scenario_excluded_items": _join(list(scenario.cost_excluded_items)) or "—",
        "scenario_length_km": length,
        "scenario_overhead_pct": scenario.overhead_percent,
        "scenario_underground_pct": scenario.underground_percent,
        "scenario_overhead_km": scenario.overhead_km(),
        "scenario_underground_km": scenario.underground_km(),
        "scenario_required_switchgear": scenario.required_switchgear or "—",
        "scenario_estimated_cost_million": est["estimated_total"],
        "scenario_cost_breakdown": breakdown_txt,
        "scenario_cost_missing_items": missing_txt,
        "has_scenario": True,
        "has_scenario_route": (length is not None and scenario.overhead_percent is not None
                               and scenario.underground_percent is not None),
        "has_cost_parameters": settings.costs.has_any(),
        "scenario_estimate_partial": (est["estimated_total"] is not None
                                      and bool(est["missing_items"])),
        "min_substation_distance_km": min_dist,
        "nearest_substation_names": _join([ss.display_name for ss in project.active_substations
                                           if ss.distance_km == min_dist]) if min_dist else None,
        "scenario_length_lt_min_distance": (length is not None and min_dist is not None
                                            and length < min_dist - _EPS),
        "has_substations": bool(project.active_substations),
    }
    ctx.update(_threshold_flags(settings))
    return ctx


def economics_contexts(project: Project, settings: AppSettings,
                       scenarios: list[SupplyScenario]) -> list[dict[str, Any]]:
    return [economics_context(project, settings, s) for s in scenarios]


# ---------------------------------------------------------------------------
# v1.2.0 — بارگذاری کل فیدر (پیک فیدر + بار اضافه‌شدهٔ متقاضی) و بازآرایی
# ---------------------------------------------------------------------------
def _added_load_mw(project: Project, settings: AppSettings) -> Optional[float]:
    """بار اضافه‌شدهٔ جدید متقاضی (MW) — مبنا: تقاضای تحلیل، سپس افزایش قدرت.

    هیچ مقداری ساخته نمی‌شود؛ اگر هیچ داده‌ای نباشد None برمی‌گردد.
    """
    d = project.demand
    kw = d.analysis_demand_kw()
    if kw is None:
        kw = project.power_delta_kw()
    if kw is None and project.requested_power_kw is not None \
            and project.request_type == "new":
        kw = project.requested_power_kw
    return None if kw is None else kw / 1000.0


def _nearest_neighbor(project: Project, settings: AppSettings) -> Optional[NeighborFeeder]:
    """فیدر همجوار کاندید بازآرایی.

    معیار: کمترین «فاصله» ثبت‌شده (در صورت نبود فاصله، ترتیب ورودی جدول) —
    مطابق دستور کارفرما: «از فیدر نزدیک بعدی که در ورودی‌ها تعریف می‌شود».
    """
    neighbors = [n for n in project.active_neighbor_feeders if (n.name or "").strip()]
    if not neighbors:
        return None
    if not settings.study.rearrange_use_nearest_feeder:
        return neighbors[0]
    with_distance = [n for n in neighbors if n.distance_km is not None]
    if with_distance:
        return min(with_distance, key=lambda n: (n.distance_km, n.name))
    return neighbors[0]


def neighbor_feeder_context(project: Project, settings: AppSettings,
                            neighbor: NeighborFeeder) -> dict[str, Any]:
    """Context یک فیدر همجوار (ورودی بازآرایی)."""
    free = neighbor.free_capacity_mw()
    peak_pct = (neighbor.peak_load_mw / neighbor.capacity_mw * 100.0
                if neighbor.capacity_mw and neighbor.peak_load_mw is not None else None)
    current_pct = (neighbor.peak_current_a / neighbor.max_current_a * 100.0
                   if neighbor.max_current_a and neighbor.peak_current_a is not None else None)
    ctx: dict[str, Any] = {
        "nf_name": neighbor.display_name,
        "nf_uid": neighbor.uid,
        "nf_office": neighbor.office,
        "nf_substation": neighbor.substation,
        "nf_peak_mw": neighbor.peak_load_mw,
        "nf_capacity_mw": neighbor.capacity_mw,
        "nf_free_mw": free,
        "nf_peak_pct": peak_pct,
        "nf_peak_current_a": neighbor.peak_current_a,
        "nf_max_current_a": neighbor.max_current_a,
        "nf_current_pct": current_pct,
        "nf_distance_km": neighbor.distance_km,
        "nf_transferable_mw": neighbor.transferable_mw,
        "nf_note": neighbor.note,
        "has_neighbor_feeders": bool(project.active_neighbor_feeders),
        "has_neighbor_free_capacity": free is not None,
        "has_neighbor_transferable": neighbor.transferable_mw is not None,
        "nf_missing_fields": "، ".join(neighbor.missing_fields()) or "—",
    }
    ctx.update(_threshold_flags(settings))
    return ctx


def neighbor_feeder_contexts(project: Project, settings: AppSettings) -> list[dict[str, Any]]:
    return [neighbor_feeder_context(project, settings, n)
            for n in project.active_neighbor_feeders]


def feeder_loading_context(project: Project, settings: AppSettings,
                           feeder: Feeder) -> dict[str, Any]:
    """Context «بارگذاری کل فیدر» برای یک فیدر.

    محاسبهٔ صریح: ``Total = Peak_Feeder + Added_Load`` (هیچ مقدار دیگری اضافه نمی‌شود)
    و مقایسه با آستانه‌های پیکربندی‌شدهٔ کاربر (پیش‌فرض ۷ و ۸ مگاوات).

    در صورت وجود فیدر همجوار فعال، پیشنهاد بازآرایی نیز **محاسبه** می‌شود:
    مقدار بار پیشنهادی برای انتقال = مازاد بر آستانهٔ بحرانی
    (``Total − Critical``) که با «بار قابل انتقال ثبت‌شده» و «ظرفیت آزاد فیدر
    همجوار» (در صورت وجود) محدود می‌گردد. هیچ آستانه/حاشیه‌ای اختراع نمی‌شود.
    """
    peak = feeder.peak_load_mw
    added = _added_load_mw(project, settings)
    total = peak + added if (peak is not None and added is not None) else None

    critical = settings.study.feeder_loading_critical_mw
    severe = settings.study.feeder_loading_severe_mw

    ge_critical = (total is not None and critical is not None and total >= critical - _EPS)
    ge_severe = (total is not None and severe is not None and total >= severe - _EPS)
    order_error = (critical is not None and severe is not None and critical >= severe)

    over_critical = (total - critical if (total is not None and critical is not None
                                          and total > critical + _EPS) else None)
    over_severe = (total - severe if (total is not None and severe is not None
                                      and total > severe + _EPS) else None)

    neighbor = _nearest_neighbor(project, settings)
    nf_ctx = neighbor_feeder_context(project, settings, neighbor) if neighbor else {}

    transfer_needed = over_critical
    transfer_proposed: Optional[float] = None
    limiting: list[str] = []
    if transfer_needed is not None and neighbor is not None:
        transfer_proposed = transfer_needed
        if neighbor.transferable_mw is not None and neighbor.transferable_mw < transfer_proposed - _EPS:
            transfer_proposed = neighbor.transferable_mw
            limiting.append("بار قابل انتقال ثبت‌شدهٔ فیدر همجوار")
        free = neighbor.free_capacity_mw()
        if free is not None and free < transfer_proposed - _EPS:
            transfer_proposed = free
            limiting.append("ظرفیت آزاد فیدر همجوار")
        if transfer_proposed < 0:
            transfer_proposed = 0.0

    nf_after = None
    nf_after_pct = None
    if neighbor is not None and transfer_proposed is not None and neighbor.peak_load_mw is not None:
        nf_after = neighbor.peak_load_mw + transfer_proposed
        if neighbor.capacity_mw:
            nf_after_pct = nf_after / neighbor.capacity_mw * 100.0

    feeder_after_rearrange = (total - transfer_proposed
                              if (total is not None and transfer_proposed is not None) else None)

    ctx: dict[str, Any] = {
        # داده ورودی فیدر
        "feeder_uid": feeder.uid,
        "feeder_name": feeder.display_name,
        "feeder_substation": feeder.substation,
        "feeder_peak_load_mw": peak,
        "feeder_peak_year": feeder.peak_year,
        "feeder_capacity_mw": feeder.capacity_mw,
        "feeder_peak_current_a": feeder.peak_current_a,
        "feeder_max_current_a": feeder.max_current_a,
        "feeder_power_factor": feeder.power_factor,
        "feeder_note": feeder.notes,
        # بار اضافه‌شده و کل بار
        "added_load_mw": added,
        "feeder_total_load_mw": total,
        "feeder_total_load_pct": (total / feeder.capacity_mw * 100.0
                                  if (total is not None and feeder.capacity_mw) else None),
        # پرچم‌های داده
        "has_feeder_peak": peak is not None,
        "has_added_load": added is not None,
        "has_feeder_total_load": total is not None,
        "has_feeder_capacity": bool(feeder.capacity_mw),
        # آستانه‌ها
        "feeder_loading_critical_mw": critical,
        "feeder_loading_severe_mw": severe,
        "has_feeder_loading_critical_mw": critical is not None,
        "has_feeder_loading_severe_mw": severe is not None,
        "threshold_order_error": order_error,
        "feeder_total_ge_critical": ge_critical,
        "feeder_total_ge_severe": ge_severe,
        "feeder_total_lt_critical": (total is not None and critical is not None
                                     and not ge_critical),
        "over_critical_mw": over_critical,
        "over_severe_mw": over_severe,
        # بازآرایی
        "has_rearrange_candidate": neighbor is not None,
        "rearrange_feeder_name": nf_ctx.get("nf_name"),
        "rearrange_distance_km": nf_ctx.get("nf_distance_km"),
        "rearrange_peak_mw": nf_ctx.get("nf_peak_mw"),
        "rearrange_capacity_mw": nf_ctx.get("nf_capacity_mw"),
        "rearrange_free_mw": nf_ctx.get("nf_free_mw"),
        "rearrange_transferable_mw": nf_ctx.get("nf_transferable_mw"),
        "transfer_needed_mw": transfer_needed,
        "transfer_proposed_mw": transfer_proposed,
        "transfer_limiting_factor": _join(limiting) or "—",
        "transfer_limited": bool(limiting),
        "rearrange_feeder_after_mw": nf_after,
        "rearrange_feeder_after_pct": nf_after_pct,
        "rearrange_feeder_total_pct": nf_ctx.get("nf_peak_pct"),
        "rearrange_current_pct": nf_ctx.get("nf_current_pct"),
        "feeder_after_rearrange_mw": feeder_after_rearrange,
        "nf_count": len(project.active_neighbor_feeders),
        "nf_list": _join([f"{n.display_name}"
                          + (f" (فاصله {fmt(n.distance_km, 2)} km)" if n.distance_km is not None else "")
                          for n in project.active_neighbor_feeders]) or "—",
        "has_neighbor_feeders": bool(project.active_neighbor_feeders),
    }
    ctx.update(demand_context(project, settings))
    ctx.update(_threshold_flags(settings))
    # آستانه‌ها پس از update باید دوباره از پیکربندی خوانده شوند (نام‌های یکسان‌اند)
    ctx["feeder_loading_critical_mw"] = critical
    ctx["feeder_loading_severe_mw"] = severe
    ctx["has_feeder_loading_critical_mw"] = critical is not None
    ctx["has_feeder_loading_severe_mw"] = severe is not None
    return ctx


def feeder_loading_contexts(project: Project, settings: AppSettings) -> list[dict[str, Any]]:
    """Context بارگذاری همهٔ فیدرهای فعال."""
    return [feeder_loading_context(project, settings, f) for f in project.active_feeders]


# ---------------------------------------------------------------------------
# اجرای Ruleهای تحلیلی مطالعه
# ---------------------------------------------------------------------------
def collect_study_results(project: Project, settings: AppSettings,
                          engine: RuleEngine,
                          scenarios: Optional[list[SupplyScenario]] = None) -> list[RuleResult]:
    """اجرای همه Ruleهای تحلیلی مطالعه روی داده‌های پروژه → فهرست RuleResult.

    مقادیر بازگشتی شامل نتایج PASS/WARNING/FAIL/INFO و نیز وضعیت‌های
    MISSING_DATA / MISSING_RULE / DATA_ERROR / REQUIRES_ENGINEER_REVIEW هستند.
    """
    scenarios = list(scenarios if scenarios is not None
                     else project.active_scenarios)          # v1.2.0: فقط سناریوهای روشن
    results: list[RuleResult] = []

    # A) تقاضا
    results.extend(engine.evaluate("study_demand", demand_context(project, settings)))
    # B) ایستگاه‌های نزدیک (برای هر ایستگاه)
    for ctx in substation_contexts(project, settings):
        for res in engine.evaluate("study_substation", ctx):
            res.owner = ctx.get("ss_name", "")
            results.append(res)
    if not project.active_substations:
        results.extend(engine.evaluate("study_substation", _with_flags(project, settings, {})))
    # C) خطوط نزدیک (برای هر خط)
    for ctx in line_contexts(project, settings):
        for res in engine.evaluate("study_line", ctx):
            res.owner = ctx.get("line_name", "")
            results.append(res)
    if not project.active_lines:
        results.extend(engine.evaluate("study_line", _with_flags(project, settings, {})))
    # D) متقاضیان همزمان + کنترل ناسازگاری
    results.extend(engine.evaluate("study_coincidence", coincidence_context(project, settings)))
    results.extend(engine.evaluate("study_crosscheck", coincidence_context(project, settings)))
    # توپولوژی
    results.extend(engine.evaluate("study_topology", topology_context(project, settings)))
    # E1) بارگذاری کل فیدر + بازآرایی (v1.2.0)
    for ctx in feeder_loading_contexts(project, settings):
        for res in engine.evaluate("study_loading", ctx):
            res.owner = ctx.get("feeder_name", "")
            results.append(res)
        for res in engine.evaluate("study_rearrange", ctx):
            res.owner = ctx.get("feeder_name", "")
            results.append(res)
    if not project.active_feeders:
        results.extend(engine.evaluate("study_loading",
                                       _with_flags(project, settings, {})))

    # E) سناریو و اقتصاد
    results.extend(engine.evaluate("study_scenario", scenario_context(project, settings, scenarios)))
    for ctx in economics_contexts(project, settings, scenarios):
        for res in engine.evaluate("study_economics", ctx):
            res.owner = ctx.get("scenario_title", "")
            results.append(res)

    results.sort(key=lambda r: (-r.priority, r.rule_id, r.owner))
    return results


def _with_flags(project: Project, settings: AppSettings,
                base: dict[str, Any]) -> dict[str, Any]:
    """Context پایه + آستانه‌ها (برای Ruleهایی که داده‌ای برای بررسی ندارند)."""
    ctx = dict(base)
    ctx.update(_threshold_flags(settings))
    ctx.setdefault("has_substations", bool(project.active_substations))
    ctx.setdefault("has_lines", bool(project.active_lines))
    return ctx


# ---------------------------------------------------------------------------
# جمع‌بندی خروجی برای گزارش/بازبینی
# ---------------------------------------------------------------------------
def has_study_data(project: Project) -> bool:
    """آیا داده‌های مطالعه مصارف سنگین در پروژه ثبت شده است؟

    تا زمانی که هیچ داده‌ای از این مطالعه وارد نشده باشد، بخش‌های مطالعه در گزارش
    و هشدارهای آن در اعتبارسنجی ظاهر نمی‌شوند (سازگاری کامل با پروژه‌های v1.0.3).
    """
    d = project.demand or DemandInfo()
    demand_rows = bool(getattr(d, "enabled", True)) and (
        d.without_coincidence_kw is not None
        or d.with_coincidence_kw is not None
        or d.existing_demand_kw is not None)
    return bool(demand_rows
                or project.active_substations                 # v1.2.0: فقط ورودی‌های روشن
                or project.active_lines
                or project.active_coincident_demands
                or project.active_scenarios
                or project.reported_total_additional_load_kw is not None
                or project.demand_used_in_analysis_kw is not None
                or project.joint_supply_feasible is not None)


def inconsistencies(results: list[RuleResult]) -> list[RuleResult]:
    """نتایجی که مغایرت داده یا نیاز به بازبینی را نشان می‌دهند."""
    return [r for r in results
            if r.status in (STATUS_DATA_ERROR, STATUS_REQUIRES_REVIEW, STATUS_MISSING_DATA)]


def missing_rule_results(results: list[RuleResult]) -> list[RuleResult]:
    """Ruleهایی که به آستانه تعریف‌نشده وابسته‌اند (MISSING_RULE)."""
    return [r for r in results if r.status == "MISSING_RULE"]
