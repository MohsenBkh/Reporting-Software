# -*- coding: utf-8 -*-
"""v2.0.0 — قواعد حفاظتی ریکلوزر/سکشنالایزر (بر پایهٔ دفترچه‌های نمونه خلخال و سلوط)."""
from __future__ import annotations

from app.core.models import Feeder, Project, RecloserInfo, SectionalizerInfo
from app.core.protection_models import FunctionSetting as F, ProtectionSettings
from app.core.studies import StudyKind
from app.core.workspace import (DEVICE_FEEDER_RELAY, ExistingProtectionDevice,
                                workspace_from_project)
from app.rules.domains import build_protection_engine, evaluate_study
from app.rules.rule_engine import safe_eval_bool


def _salut():
    """دفترچه سلوط: ریکلوزر (جدول ۱) و تنظیمات پیشنهادی سکشنالایزر (جدول ۲)."""
    rec = ProtectionSettings(
        f51=F("NI", 400, 7.5, "percent"), f50=F("NI", 2400, 120, "ms"),
        f51n=F("NI", 80, 7.5, "percent"), f50n=F("NI", 480, 120, "ms"),
        shots=1, dead_times_s=[1], reclaim_time_s=5)
    sec = ProtectionSettings(
        f51=F("NI", 380, 4.5, "percent"), f50=F("NI", 2160, 0, "ms"),
        f51n=F("NI", 72, 4.5, "percent"), f50n=F("NI", 432, 0, "ms"),
        counter=1, dead_line_current_pct=10, dead_line_voltage_pct=20)
    p = Project(name="سلوط", feeders=[Feeder(name="F8 سلوط", substation="پست", peak_current_a=None)])
    p.recloser = RecloserInfo(feeder_name="F8 سلوط", installation_location="پست", settings=rec)
    p.sectionalizer = SectionalizerInfo(feeder_name="F8 سلوط", installation_location="x", settings=sec)
    return p, workspace_from_project(p)


def _khalkhal():
    """دفترچه خلخال: ریکلوزر پیشنهادی (جدول ۳) و رله سر فیدر (جدول ۲)."""
    rec = ProtectionSettings(
        f51=F("NI", 250, 5, "percent"), f50=F("NI", 600, 50, "ms"),
        f51n=F("NI", 30, 5, "percent"), f50n=F("NI", 280, 50, "ms"),
        shots=2, dead_times_s=[2, 30], reclaim_time_s=300)
    relay = ProtectionSettings(
        f51=F("NI", 300, 9, "percent"), f50=F("NI", 2400, 100, "ms"),
        f51n=F("NI", 45, 8, "percent"), f50n=F("NI", 675, 100, "ms"))
    p = Project(name="خلخال", feeders=[Feeder(name="F4 خلخال", substation="پست", peak_current_a=None)])
    p.recloser = RecloserInfo(feeder_name="F4 خلخال", installation_location="قبل از انشعاب",
                              placement_basis="تمرکز خاموشی‌ها", settings=rec)
    ws = workspace_from_project(p)
    ws.common_network.feeders[0].existing_protection.append(ExistingProtectionDevice(
        name="رله سر فیدر", device_type=DEVICE_FEEDER_RELAY, settings=relay))
    return p, ws


def _by_key(results):
    return {r.rule_key: r for r in results}


def test_all_rule_conditions_use_only_safe_constructs():
    eng = build_protection_engine()
    assert len(eng.analysis_rules) > 30
    for rule in eng.analysis_rules.values():
        # شرط باید بدون خطا ارزیابی شود (روی Context خالی False/True است، نه Exception)
        assert safe_eval_bool(rule.condition, {}) in (True, False)


def test_domains_are_separated():
    eng = build_protection_engine()
    domains = {r.domain for r in eng.analysis_rules.values()}
    assert domains == {"protection_common", "recloser", "sectionalizer"}


def test_salut_sample_sectionalizer_matches_reference_profile():
    p, ws = _salut()
    res = _by_key(evaluate_study(p, ws, StudyKind.SECTIONALIZER))
    for key in ("SECZ-PK-51-OK", "SECZ-PK-50-OK", "SECZ-PK-51N-OK", "SECZ-PK-50N-OK",
                "SECZ-TMS-51-OK", "SECZ-TMS-51N-OK", "SECZ-COUNTER-OK", "SECZ-DEADLINE-OK"):
        assert res[key].status == "PASS", key
    assert not any(k.endswith("-DEV") for k in res)


def test_sectionalizer_deviation_is_warning_with_engineer_review():
    p, ws = _salut()
    p.sectionalizer.settings.f51 = F("NI", 390, 4.5, "percent")
    p.sectionalizer.settings.counter = 2
    res = _by_key(evaluate_study(p, ws, StudyKind.SECTIONALIZER))
    assert res["SECZ-PK-51-DEV"].status == "WARNING"
    assert res["SECZ-PK-51-DEV"].engineer_review_required
    assert res["SECZ-COUNTER-DEV"].status == "WARNING"


def test_sectionalizer_without_reference_recloser_reports_missing_data():
    p, ws = _salut()
    p.recloser.settings = ProtectionSettings()
    res = _by_key(evaluate_study(p, ws, StudyKind.SECTIONALIZER))
    assert res["SECZ-REF-MISSING"].status == "MISSING_DATA"
    assert not any(k.startswith("SECZ-PK") for k in res)       # بدون مرجع، مقایسه‌ای ساخته نمی‌شود


def test_khalkhal_sample_recloser_is_coordinated_with_feeder_relay():
    p, ws = _khalkhal()
    res = _by_key(evaluate_study(p, ws, StudyKind.RECLOSER))
    for suf in ("51", "50", "51N", "50N"):
        assert res[f"REC-COORD-{suf}-OK"].status == "PASS"
    assert res["REC-SHOTS-INFO"].engineer_review_required


def test_recloser_slower_than_upstream_fails():
    p, ws = _khalkhal()
    p.recloser.settings.f51 = F("NI", 320, 5, "percent")        # Pickup بالاتر از رله (300 A)
    res = _by_key(evaluate_study(p, ws, StudyKind.RECLOSER))
    assert res["REC-COORD-51-BAD"].status == "FAIL"
    assert "REC-COORD-51-OK" not in res


def test_time_not_compared_when_units_differ():
    p, ws = _khalkhal()
    p.recloser.settings.f50 = F("NI", 600, 0.05, "s")           # واحد متفاوت با رله (ms)
    res = _by_key(evaluate_study(p, ws, StudyKind.RECLOSER))
    assert "مقایسهٔ زمان ممکن نیست" in res["REC-COORD-50-OK"].finding


def test_undefined_thresholds_yield_missing_rule_not_invented_values():
    p, ws = _khalkhal()
    p.recloser.min_fault_current_ka = 1.2
    p.recloser.load_current_a = 150
    res = _by_key(evaluate_study(p, ws, StudyKind.RECLOSER))
    for key in ("REC-RECLAIM-NOTHRESH", "REC-SENS-NOTHRESH", "REC-LOADMARGIN-NOTHRESH"):
        assert res[key].status == "MISSING_RULE", key
        assert res[key].engineer_review_required
    assert not any(k.endswith(("-OK", "-BAD")) and k.startswith(("REC-RECLAIM", "REC-SENS",
                                                                  "REC-LOADMARGIN")) for k in res)


def test_user_supplied_thresholds_enable_pass_fail():
    p, ws = _khalkhal()
    p.recloser.min_fault_current_ka = 1.2
    p.recloser.load_current_a = 150
    th = {"min_reclaim_time_s": 300, "min_sensitivity_ratio": 1.5, "min_pickup_to_load_ratio": 1.5}
    res = _by_key(evaluate_study(p, ws, StudyKind.RECLOSER, thresholds=th))
    assert res["REC-RECLAIM-OK"].status == "PASS"
    assert res["REC-SENS-OK"].status == "PASS"          # 1200/250 = 4.8
    assert res["REC-LOADMARGIN-OK"].status == "PASS"    # 250/150 = 1.67
    th["min_reclaim_time_s"] = 600
    res = _by_key(evaluate_study(p, ws, StudyKind.RECLOSER, thresholds=th))
    assert res["REC-RECLAIM-BAD"].status == "FAIL"


def test_empty_study_reports_missing_data_only():
    p = Project(name="x", feeders=[Feeder(name="F1", substation="S", peak_current_a=None)])
    ws = workspace_from_project(p)
    res = evaluate_study(p, ws, StudyKind.RECLOSER)
    assert res and all(r.status in ("MISSING_DATA", "INFO") for r in res)
    assert {"REC-LOC-MISSING", "REC-SET-MISSING"} <= {r.rule_key for r in res}


def test_every_result_carries_traceability_fields():
    p, ws = _khalkhal()
    for r in evaluate_study(p, ws, StudyKind.RECLOSER):
        assert r.rule_key and r.status and r.category and r.owner
        if r.rule_key.startswith("REC-"):
            assert r.source and r.source_page


def test_heavy_kind_is_rejected_by_protection_evaluation():
    p, ws = _khalkhal()
    try:
        evaluate_study(p, ws, StudyKind.HEAVY)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


# ---------------------------------------------------------------------------
# داده‌های شبکهٔ مشترک: منابع تولید پراکنده و سناریوهای بهره‌برداری (فایل اصلاحات)
# ---------------------------------------------------------------------------
def test_dg_and_scenarios_missing_are_reported_not_assumed():
    p, ws = _khalkhal()
    res = _by_key(evaluate_study(p, ws, StudyKind.RECLOSER))
    assert res["PCM-DG-UNKNOWN"].status == "MISSING_DATA"
    assert res["PCM-SCENARIO-MISSING"].status == "MISSING_DATA"
    assert "PCM-DG-PRESENT" not in res


def test_dg_present_requires_engineer_review_and_scenarios_clear_the_gap():
    p, ws = _khalkhal()
    f = ws.common_network.feeders[0]
    f.has_dg, f.dg_note = True, "۵۰۰ کیلووات"
    f.normal_scenario = "تغذیه از پست اصلی"
    res = _by_key(evaluate_study(p, ws, StudyKind.RECLOSER))
    assert "PCM-DG-UNKNOWN" not in res and "PCM-SCENARIO-MISSING" not in res
    dg = res["PCM-DG-PRESENT"]
    assert dg.status == "INFO" and dg.engineer_review_required and "۵۰۰ کیلووات" in dg.finding


def test_no_dg_is_a_valid_answer():
    p, ws = _khalkhal()
    ws.common_network.feeders[0].has_dg = False
    res = _by_key(evaluate_study(p, ws, StudyKind.RECLOSER))
    assert "PCM-DG-UNKNOWN" not in res and "PCM-DG-PRESENT" not in res
