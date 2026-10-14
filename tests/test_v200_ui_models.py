# -*- coding: utf-8 -*-
"""v2.0.0 (فاز ۲) — مدل‌های بدون Qt: Design Tokens، Inspector، Dashboard."""
from __future__ import annotations

import re

from app.core.models import Feeder, Project, RecloserInfo, SectionalizerInfo
from app.core.protection_models import FunctionSetting as F, ProtectionSettings
from app.core.studies import StudyKind, StudySelection
from app.core.workspace import workspace_from_project
from app.rules.domains import evaluate_study
from app.ui import theme as theme_mod
from app.ui.shell.dashboard_model import (dashboard_cards, result_view, validation_checklist)
from app.ui.shell.design import (GLYPH, MISSING_TEXT, RESULT_STATE_TO_BADGE, format_quantity,
                                 shell_qss)
from app.ui.shell.inspector_model import apply_include_flag, inspector_model


def _project():
    p = Project(name="خلخال", feeders=[Feeder(name="F4", substation="پست", peak_current_a=200.0)])
    p.recloser = RecloserInfo(
        feeder_name="F4", installation_location="تیر ۱۵۴", rated_current_a=630.0,
        settings=ProtectionSettings(f51=F("NI", 320.0, 0.18, ""), shots=2, reclaim_time_s=300))
    return p, workspace_from_project(p)


def test_format_quantity_standard_units_and_missing():
    assert format_quantity(630, "A", 0) == "630\u00a0A"
    assert format_quantity(0.18, "", 2) == "0.18"
    assert format_quantity(None, "A") == MISSING_TEXT          # نبود داده ≠ صفر
    assert format_quantity(0.0, "A", 1) == "0\u00a0A"          # صفر واقعی نمایش داده می‌شود


def test_shell_qss_uses_only_theme_token_colors():
    tokens = theme_mod.tokens("light")
    qss = shell_qss("light", tokens)
    allowed = {v.lower() for v in tokens.values() if isinstance(v, str) and v.startswith("#")}
    used = {c.lower() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", qss)}
    assert used and used <= allowed, used - allowed          # هیچ رنگ Hard-code نیست


def test_every_rule_status_has_a_visual_state():
    for status in ("PASS", "WARNING", "FAIL", "INFO", "MISSING_DATA", "MISSING_RULE"):
        assert RESULT_STATE_TO_BADGE[status] in GLYPH


def test_inspector_for_recloser_matches_expected_context_rows():
    p, ws = _project()
    m = inspector_model(p, ws, "recloser")
    rows = dict(m.rows)
    assert m.title.startswith("ریکلوزر") and rows["فیدر"] == "F4"
    assert rows["محل نصب"] == "تیر ۱۵۴" and rows["جریان نامی"] == "630\u00a0A"
    assert rows["Pickup (۵۱)"] == "320\u00a0A" and rows["TMS (۵۱)"] == "0.18"
    assert rows["منحنی"] == "NI — Normal Inverse"
    assert m.include_key == "recloser" and m.include_value is True


def test_inspector_missing_values_are_dash_not_zero():
    p = Project(name="x")
    ws = workspace_from_project(p)
    rows = dict(inspector_model(p, ws, "sectionalizer").rows)
    assert rows["Pickup (۵۱)"] == MISSING_TEXT and rows["Counter"] == MISSING_TEXT


def test_inspector_feeder_and_project_and_none():
    p, ws = _project()
    assert dict(inspector_model(p, ws, "feeder:F4").rows)["جریان بار"] == "200\u00a0A"
    assert inspector_model(p, ws, "feeder:Nope").subtitle
    assert "مطالعات انتخاب‌شده" in dict(inspector_model(p, ws, "project").rows)
    assert inspector_model(None, ws, "recloser").title == "پروژه‌ای باز نیست"


def test_include_flag_roundtrip():
    p, ws = _project()
    assert apply_include_flag(p, "recloser", False) is True
    assert inspector_model(p, ws, "recloser").include_value is False
    assert apply_include_flag(p, "nonexistent", True) is False


def test_result_view_carries_review_marker_and_provenance():
    p, ws = _project()
    res = evaluate_study(p, ws, StudyKind.RECLOSER)
    shots = next(r for r in res if r.rule_key == "REC-SHOTS-INFO")
    state, text, tip = result_view(shots)
    assert state == "info" and "نیازمند بازبینی مهندس" in text and "REC-SHOTS-INFO" in tip
    missing = next(r for r in res if r.status == "MISSING_DATA")
    assert result_view(missing)[0] == "warning"


def test_checklist_reflects_inputs_network_and_review():
    p, ws = _project()
    ws.selection = StudySelection(recloser=True)
    items = validation_checklist(p, ws, input_errors=0, input_warnings=2, results_by_kind=None,
                                 report_generated=False)
    by = {i.label: i for i in items}
    assert by["اعتبارسنجی ورودی‌ها"].state == "warning"
    assert by["اعتبارسنجی شبکه"].state == "warning" and "Isc" in by["اعتبارسنجی شبکه"].detail
    assert by["بازبینی مهندس"].state == "pending" and by["تولید گزارش"].state == "pending"
    results = {StudyKind.RECLOSER: evaluate_study(p, ws, StudyKind.RECLOSER)}
    items = validation_checklist(p, ws, input_errors=1, input_warnings=0,
                                 results_by_kind=results, report_generated=True)
    by = {i.label: i for i in items}
    assert by["اعتبارسنجی ورودی‌ها"].state == "error" and by["بازبینی مهندس"].state == "review"
    assert by["تولید گزارش"].state == "completed"


def test_dashboard_cards_badge_mapping():
    p, ws = _project()
    ws.selection = StudySelection(recloser=True)
    cards = {c["key"]: c for c in dashboard_cards(p, ws)}
    assert cards["recloser"]["badge"] == "info"            # انتخاب شده، ارزیابی نشده
    assert cards["heavy"]["badge"] == "pending"            # انتخاب نشده
