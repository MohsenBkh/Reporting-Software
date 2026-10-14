# -*- coding: utf-8 -*-
"""ساخت Context ارزیابی Ruleهای حفاظتی از «مطالعه + شبکه مشترک».

تمام محاسبات (نسبت‌ها، مقایسه با بالادست، ...) اینجا انجام می‌شود تا شرط Ruleها
فقط ساده (مقایسه و منطق) بماند. اصل ثابت: نبود داده = ``None`` و هیچ مقداری
حدس زده نمی‌شود.
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.protection_models import ProtectionSettings
from app.core.studies import StudyKind
from app.core.tcc import CURVE_LABELS_FA, coordination_ok, delayed_curve
from app.core.workspace import Workspace, resolve_study_inputs
from app.rules.protection_labels import FUNCTION_SUFFIXES, LABELS, key_of
from app.rules.reference_profile import (PROFILE_KEYS, REFERENCE_PROFILE,
                                         UNDEFINED_THRESHOLDS)


def _has(ctx: dict, key: str) -> None:
    ctx[f"has_{key}"] = ctx.get(key) is not None


def _g(v: Optional[float]) -> str:
    return "ناموجود" if v is None else f"{v:g}"


def build_context(project: Any, workspace: Workspace, kind: StudyKind,
                  thresholds: Optional[dict] = None) -> dict[str, Any]:
    kind = StudyKind(kind)
    info = getattr(project, kind.value)
    settings: ProtectionSettings = getattr(info, "settings", None) or ProtectionSettings()
    inputs = resolve_study_inputs(project, workspace, kind)
    cfg = dict(REFERENCE_PROFILE)
    cfg.update(thresholds or {})

    ctx: dict[str, Any] = {
        "feeder_name": inputs["feeder_name"].value,
        "has_common_feeder": inputs["common_feeder"] is not None,
        "fault_current_ka": inputs["fault_current_ka"].value,
        "min_fault_current_ka": inputs["min_fault_current_ka"].value,
        "load_current_a": inputs["load_current_a"].value,
        "installation_location": getattr(info, "installation_location", "") or None,
        "placement_basis": getattr(info, "placement_basis", "") or None,
        "protection_functions": (sum(f.is_set() for f in settings.functions().values())
                                 if settings.any_function_set() else None),
        "shots": settings.shots,
        "reclaim_time_s": settings.reclaim_time_s,
        "counter": settings.counter,
        "dead_line_current_pct": settings.dead_line_current_pct,
        "dead_line_voltage_pct": settings.dead_line_voltage_pct,
        "dead_times_text": ("، ".join(f"{t:g} s" for t in settings.dead_times_s)
                            if settings.dead_times_s else "ناموجود"),
    }
    common = inputs["common_feeder"]
    ctx["dg_status"] = (None if common is None or common.has_dg is None
                        else ("دارد" if common.has_dg else "ندارد"))
    ctx["dg_present"] = bool(common.has_dg) if common is not None else False
    ctx["dg_note"] = (common.dg_note if common is not None else "") or "—"
    scen = bool(common and (common.normal_scenario.strip() or common.emergency_scenario.strip()))
    ctx["operating_scenarios"] = "ثبت شده" if scen else None
    ctx["sc_1ph_ka"] = common.sc_1ph_ka if common is not None else None
    for key in ("feeder_name", "fault_current_ka", "min_fault_current_ka", "load_current_a",
                "installation_location", "placement_basis", "shots", "reclaim_time_s"):
        _has(ctx, key)
    ctx["has_any_function"] = ctx["protection_functions"] is not None
    for suf in FUNCTION_SUFFIXES:
        f = settings.function(key_of(suf))
        ctx[f"pickup_{suf}"] = f.pickup_a
    # آستانه‌های تعریف‌نشده فقط با ورودی صریح کاربر مقدار می‌گیرند
    for key in UNDEFINED_THRESHOLDS:
        ctx[key] = (thresholds or {}).get(key)
        _has(ctx, key)

    up: Optional[ProtectionSettings] = inputs["upstream_settings"]
    if kind is StudyKind.RECLOSER:
        _recloser(ctx, settings, up, inputs["upstream_ref"])
    else:
        _sectionalizer(ctx, settings, up, inputs["upstream_ref"], cfg)
    return ctx


def _recloser(ctx: dict, s: ProtectionSettings, up: Optional[ProtectionSettings],
              up_ref: Optional[str]) -> None:
    ctx["upstream_settings_ref"] = up_ref
    ctx["has_upstream_settings"] = up is not None
    mt = ctx.get("min_reclaim_time_s")
    ctx["reclaim_ok"] = (None if mt is None or s.reclaim_time_s is None
                         else s.reclaim_time_s >= mt)
    # هماهنگی با بالادست — برای هر تابع
    for suf in FUNCTION_SUFFIXES:
        key = key_of(suf)
        ctx[f"coord_known_{suf}"] = False
        ctx[f"coord_ok_{suf}"] = None
        ctx[f"coord_detail_{suf}"] = ""
        if up is None:
            continue
        r, u = s.function(key), up.function(key)
        if r.pickup_a is None or u.pickup_a is None:
            continue
        pickup_ok = r.pickup_a < u.pickup_a
        time_ok: Optional[bool] = None
        if (r.time_value is not None and u.time_value is not None
                and r.time_unit and r.time_unit == u.time_unit):
            time_ok = r.time_value < u.time_value
        ctx[f"coord_known_{suf}"] = True
        ctx[f"coord_ok_{suf}"] = pickup_ok and time_ok is not False
        t_txt = ("مقایسهٔ زمان ممکن نیست (واحد یا مقدار ناموجود)" if time_ok is None else
                 f"زمان {r.time_text()} در برابر {u.time_text()}")
        ctx[f"coord_detail_{suf}"] = (
            f"{LABELS[suf]}: Pickup ریکلوزر {_g(r.pickup_a)} A در برابر بالادست "
            f"{_g(u.pickup_a)} A ({'مناسب' if pickup_ok else 'نامناسب'})؛ {t_txt}"
            + ("" if time_ok is None else f" ({'مناسب' if time_ok else 'نامناسب'})") + ".")
    # هماهنگی منحنی جریان–زمان (TCC) با بالادست — توابع تأخیری ۵۱ و ۵۱N
    # مبنا: دفترچه نمونه فیدر ۴ خلخال (شکل‌های ۳ و ۴) — منحنی ریکلوزر باید در
    # تمام محدودهٔ جریان‌های خطا زیر منحنی رله بالادست قرار گیرد.
    _curve_coordination(ctx, s, up)
    # حساسیت و حاشیه نسبت به بار (بر اساس تابع ۵۱)
    p51 = s.f51.pickup_a
    min_a = (ctx["min_fault_current_ka"] * 1000.0
             if ctx["min_fault_current_ka"] is not None else None)
    ctx["sensitivity_ratio"] = (min_a / p51) if (min_a is not None and p51) else None
    ctx["has_sensitivity_ratio"] = ctx["sensitivity_ratio"] is not None
    t = ctx.get("min_sensitivity_ratio")
    ctx["sensitivity_ok"] = (None if t is None or ctx["sensitivity_ratio"] is None
                             else ctx["sensitivity_ratio"] >= t)
    load = ctx["load_current_a"]
    ctx["min_fault_a"] = min_a
    max_a = ctx["fault_current_ka"] * 1000.0 if ctx["fault_current_ka"] is not None else None
    ctx["max_fault_a"] = max_a
    p50 = s.f50.pickup_a
    ctx["pickup_below_load"] = bool(p51 is not None and load is not None and p51 < load)
    ctx["pickup_above_minfault"] = bool(p51 is not None and min_a is not None and p51 >= min_a)
    ctx["inst_above_maxfault"] = bool(p50 is not None and max_a is not None and p50 >= max_a)
    ctx["pickup_load_ratio"] = (p51 / load) if (p51 is not None and load) else None
    ctx["has_load_ratio"] = ctx["pickup_load_ratio"] is not None
    t = ctx.get("min_pickup_to_load_ratio")
    ctx["load_ratio_ok"] = (None if t is None or ctx["pickup_load_ratio"] is None
                            else ctx["pickup_load_ratio"] >= t)


def _curve_coordination(ctx: dict, s: ProtectionSettings,
                        up: Optional[ProtectionSettings]) -> None:
    """مقایسهٔ منحنی‌های معکوس IEC (NI/VI/EI) ریکلوزر و بالادست در محدودهٔ خطا.

    زمان عملکرد از رابطهٔ استاندارد t = TMS·k/((I/Ip)^α − 1) با TMS درصدی محاسبه
    می‌شود؛ اگر منحنی/TMS/Pickup هر طرف ثبت نشده باشد، مقایسه «ناشناخته» می‌ماند.
    """
    max_a = ctx.get("fault_current_ka") * 1000.0 \
        if ctx.get("fault_current_ka") is not None else None
    min_a = ctx.get("min_fault_current_ka") * 1000.0 \
        if ctx.get("min_fault_current_ka") is not None else None
    for suf in ("51", "51n"):
        key = key_of(suf)
        ctx[f"curve_known_{suf}"] = False
        ctx[f"curve_ok_{suf}"] = None
        ctx[f"curve_detail_{suf}"] = ""
        if up is None:
            continue
        down_c = delayed_curve("ریکلوزر", LABELS[suf], s.function(key))
        up_c = delayed_curve("بالادست", LABELS[suf], up.function(key))
        if down_c is None or up_c is None or not down_c.is_inverse or not up_c.is_inverse:
            continue
        lo = max(down_c.pickup_a, up_c.pickup_a) * 1.05
        hi = max_a if (max_a is not None and max_a > lo) else lo * 20.0
        n = 25
        currents = [lo * (hi / lo) ** (i / (n - 1)) for i in range(n)]
        if min_a is not None and min_a > lo:
            currents.append(min_a)
        ok = coordination_ok(down_c, up_c, currents)
        if ok is None:
            continue
        ctx[f"curve_known_{suf}"] = True
        ctx[f"curve_ok_{suf}"] = ok
        probe = max_a if (max_a is not None and max_a > lo) else hi
        td, tu = down_c.time_at(probe), up_c.time_at(probe)
        t_txt = ("" if td is None or tu is None else
                 f"؛ زمان عملکرد در {probe:.0f} A: ریکلوزر {td:.2f} s در برابر "
                 f"بالادست {tu:.2f} s")
        state = ("در تمام محدودهٔ جریان‌های خطا زیر منحنی بالادست قرار دارد" if ok else
                 "در بخشی از محدودهٔ جریان‌های خطا زیر منحنی بالادست قرار ندارد")
        ctx[f"curve_detail_{suf}"] = (
            f"{LABELS[suf]}: منحنی ریکلوزر ({CURVE_LABELS_FA.get(down_c.curve, down_c.curve)}، "
            f"TMS {down_c.tms * 100:g}%) {state} "
            f"(بالادست: {CURVE_LABELS_FA.get(up_c.curve, up_c.curve)}، "
            f"TMS {up_c.tms * 100:g}%){t_txt}.")


def _sectionalizer(ctx: dict, s: ProtectionSettings, ref: Optional[ProtectionSettings],
                   ref_name: Optional[str], cfg: dict) -> None:
    ctx["reference_ref"] = ref_name
    ctx["has_reference"] = ref is not None
    ctx["has_reference_profile"] = all(k in cfg for k in PROFILE_KEYS)
    for k in PROFILE_KEYS:
        ctx[k] = cfg.get(k)
    for suf in FUNCTION_SUFFIXES:
        key = key_of(suf)
        ratio = cfg.get(f"secz_pickup_ratio_{suf}")
        actual = s.function(key).pickup_a
        base = ref.function(key).pickup_a if ref else None
        known = ratio is not None and actual is not None and base is not None
        ctx.update({f"pk_known_{suf}": known, f"pk_match_{suf}": None,
                    f"pk_actual_{suf}": actual, f"pk_ref_{suf}": base,
                    f"pk_expected_{suf}": None})
        if known:
            expected = ratio * base
            ctx[f"pk_expected_{suf}"] = round(expected, 2)
            ctx[f"pk_match_{suf}"] = round(actual, 1) == round(expected, 1)
    for suf in ("51", "51n"):
        key = key_of(suf)
        off = cfg.get(f"secz_tms_offset_{suf}")
        a, r = s.function(key), (ref.function(key) if ref else None)
        known = (off is not None and r is not None and a.time_value is not None
                 and r.time_value is not None and a.time_unit == r.time_unit == "percent")
        ctx.update({f"tms_known_{suf}": known, f"tms_match_{suf}": None,
                    f"tms_actual_{suf}": a.time_value, f"tms_expected_{suf}": None})
        if known:
            expected = round(r.time_value - off, 2)
            ctx[f"tms_expected_{suf}"] = expected
            ctx[f"tms_match_{suf}"] = round(a.time_value, 2) == expected
    ref_shots = ref.shots if ref else None
    ctx["ref_shots"] = ref_shots
    ctx["counter_known"] = s.counter is not None and ref_shots is not None
    ctx["counter_match"] = (s.counter == ref_shots) if ctx["counter_known"] else None
    cur, vol = cfg.get("secz_dead_line_current_pct"), cfg.get("secz_dead_line_voltage_pct")
    ctx["deadline_known"] = (s.dead_line_current_pct is not None
                             and s.dead_line_voltage_pct is not None
                             and cur is not None and vol is not None)
    ctx["deadline_match"] = ((s.dead_line_current_pct == cur and s.dead_line_voltage_pct == vol)
                             if ctx["deadline_known"] else None)
