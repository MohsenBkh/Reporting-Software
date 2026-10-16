# -*- coding: utf-8 -*-
"""v2.1.1/v2.2.0 — منحنی جریان–زمان (TCC): محاسبات IEC و Rule هماهنگی منحنی.

از v2.2.0 تولید نمودار TCC حذف شد (نمودارها از نرم‌افزار IDMT وارد می‌شوند)؛
محاسبات IEC برای قواعد REC-CURVE همچنان اینجاست.

مقادیر مرجع از دفترچه نمونه «احداث ریکلوزر — فیدر ۴ خلخال»:
    رله سر فیدر: 51 → 300 A / NI / TMS 9٪ — ریکلوزر R2: 51 → 250 A / NI / TMS 5٪
"""
from __future__ import annotations

from app.core.protection_models import FunctionSetting, ProtectionSettings
from app.core.studies import StudyKind
from app.core.tcc import (DEFAULT_CURVE, IEC_CURVES, RelayCurve, coordination_ok,
                          delayed_curve, device_curves, instant_curve,
                          normalize_curve, tms_factor, trip_time)
from app.report.composer import ReportComposer
from app.report.sections import FigureBlock
from test_v200_protection_rules import _khalkhal, _salut


# ---------------------------------------------------------------------------
# محاسبات پایه
# ---------------------------------------------------------------------------
def test_default_curve_is_ni_and_all_three_iec_curves_supported():
    assert DEFAULT_CURVE == "NI"
    assert set(IEC_CURVES) == {"NI", "VI", "EI"}
    assert IEC_CURVES["NI"] == (0.14, 0.02)
    assert IEC_CURVES["VI"] == (13.5, 1.0)
    assert IEC_CURVES["EI"] == (80.0, 2.0)


def test_normalize_curve_maps_aliases_and_blank_to_default():
    assert normalize_curve("") == "NI"              # خالی = پیش‌فرض NI
    assert normalize_curve(None) == "NI"
    assert normalize_curve("ni") == "NI"
    assert normalize_curve("Very Inverse") == "VI"
    assert normalize_curve("E.I") == "EI"
    assert normalize_curve("نامعتبر") is None


def test_tms_percent_is_default_unit():
    assert tms_factor(5, "percent") == 0.05
    assert tms_factor(9, "") == 0.09                # بدون واحد = درصد (پیش‌فرض)
    assert tms_factor(None, "percent") is None
    assert tms_factor(100, "ms") is None            # زمان ثابت TMS نیست


def test_trip_time_matches_iec_formula():
    # NI: t = 0.09 × 0.14 / ((1000/300)^0.02 − 1) ≈ 0.517 s
    t = trip_time(1000, 300, 0.09, "NI")
    assert abs(t - 0.517) < 0.01
    assert trip_time(200, 300, 0.09, "NI") is None      # زیر Pickup عمل نمی‌کند
    assert trip_time(1000, 300, 0.09, "XX") is None     # منحنی ناشناخته
    # VI و EI در جریان یکسان سریع‌تر از NI در جریان‌های بالا
    assert trip_time(3000, 300, 0.05, "EI") < trip_time(3000, 300, 0.05, "VI")


def test_delayed_and_instant_curves_from_function_settings():
    d = delayed_curve("ریکلوزر", "۵۱", FunctionSetting("NI", 250, 5, "percent"))
    assert d is not None and d.is_inverse and d.tms == 0.05 and d.curve == "NI"
    # منحنی خالی = پیش‌فرض NI
    d2 = delayed_curve("ریکلوزر", "۵۱", FunctionSetting("", 250, 5, "percent"))
    assert d2 is not None and d2.curve == "NI"
    i = instant_curve("ریکلوزر", "۵۰", FunctionSetting("", 600, 50, "ms"))
    assert i is not None and not i.is_inverse and i.fixed_time_s == 0.05
    assert delayed_curve("x", "۵۱", FunctionSetting("NI", None, 5, "percent")) is None


def test_coordination_ok_recloser_below_upstream():
    up = delayed_curve("رله", "۵۱", FunctionSetting("NI", 300, 9, "percent"))
    rec = delayed_curve("ریکلوزر", "۵۱", FunctionSetting("NI", 250, 5, "percent"))
    assert coordination_ok(rec, up, [400, 1000, 3000, 6600]) is True
    # ریکلوزر کندتر از بالادست → عدم هماهنگی
    slow = delayed_curve("ریکلوزر", "۵۱", FunctionSetting("NI", 250, 20, "percent"))
    assert coordination_ok(slow, up, [400, 1000, 3000, 6600]) is False
    assert coordination_ok(rec, up, [100]) is None      # نقطهٔ مشترک ندارد


def test_device_curves_phase_and_ground_groups():
    s = ProtectionSettings(f51=FunctionSetting("NI", 250, 5, "percent"),
                           f50=FunctionSetting("", 600, 50, "ms"),
                           f51n=FunctionSetting("NI", 30, 5, "percent"))
    phase = device_curves("R2", s, "phase")
    assert [c.function for c in phase] == ["۵۱", "۵۰"]
    ground = device_curves("R2", s, "ground")
    assert [c.function for c in ground] == ["۵۱N"]      # ۵۰N ثبت نشده است


# ---------------------------------------------------------------------------
# v2.2.0 — تولید نمودار TCC حذف شد: نمودارها از نرم‌افزار IDMT وارد می‌شوند
# ---------------------------------------------------------------------------
def _figures(report, key):
    sec = next((s for s in report.sections if s.key == key), None)
    return [] if sec is None else [b for b in sec.blocks if isinstance(b, FigureBlock)]


def test_tcc_chart_generation_removed_from_chart_generator():
    import app.report.chart_generator as cg
    assert not hasattr(cg, "tcc_chart")


def test_reports_have_no_builtin_tcc_figures(tmp_path):
    """گزارش‌ساز دیگر نمودار TCC نمی‌سازد؛ منحنی‌ها با «ورود از IDMT» می‌آیند."""
    p, ws = _khalkhal()
    report = ReportComposer().compose(p, ws, [StudyKind.RECLOSER], charts_dir=tmp_path)
    assert not _figures(report, "prot_coordination")
    p2, ws2 = _salut()
    report2 = ReportComposer().compose(p2, ws2, [StudyKind.SECTIONALIZER], charts_dir=tmp_path)
    assert not _figures(report2, "prot_coordination")


# ---------------------------------------------------------------------------
# Rule هماهنگی منحنی (REC-CURVE-*)
# ---------------------------------------------------------------------------
def test_curve_coordination_rules_pass_for_khalkhal_sample():
    from app.rules.domains import build_protection_engine, evaluate_study
    p, ws = _khalkhal()
    results = evaluate_study(p, ws, StudyKind.RECLOSER, build_protection_engine())
    by_key = {r.rule_key: r for r in results}
    assert by_key["REC-CURVE-51-OK"].status == "PASS"
    assert by_key["REC-CURVE-51N-OK"].status == "PASS"
    assert "REC-CURVE-51-BAD" not in by_key


def test_curve_coordination_rule_fails_for_slow_recloser():
    from app.rules.domains import build_protection_engine, evaluate_study
    p, ws = _khalkhal()
    p.recloser.settings.f51.time_value = 30             # TMS 30٪ ≫ بالادست (۹٪)
    results = evaluate_study(p, ws, StudyKind.RECLOSER, build_protection_engine())
    by_key = {r.rule_key: r for r in results}
    assert by_key["REC-CURVE-51-BAD"].status == "FAIL"
    assert "بالادست" in (by_key["REC-CURVE-51-BAD"].finding or "")
