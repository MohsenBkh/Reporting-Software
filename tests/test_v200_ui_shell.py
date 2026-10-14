# -*- coding: utf-8 -*-
"""v2.0.0 (فاز ۲) — ویجت‌های Shell. با PySide6 واقعی در حالت offscreen اجرا می‌شود:
    QT_QPA_PLATFORM=offscreen pytest tests/test_v200_ui_shell.py
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core.models import Feeder, Project, RecloserInfo  # noqa: E402
from app.core.project_tree import build_project_tree  # noqa: E402
from app.core.protection_models import FunctionSetting as F, ProtectionSettings  # noqa: E402
from app.core.studies import StudySelection  # noqa: E402
from app.core.workspace import workspace_from_project  # noqa: E402
from app.ui.shell.explorer import ProjectExplorer  # noqa: E402
from app.ui.shell.report_center_page import ReportCenterPage  # noqa: E402
from app.ui.shell.settings_editor import (OptionalNumberEdit, ProtectionSettingsEditor,  # noqa: E402
                                          parse_optional_float)

_APP = QApplication.instance() or QApplication([])


def test_parse_optional_float_handles_persian_digits_and_empty():
    assert parse_optional_float("۳۲۰") == 320.0
    assert parse_optional_float("0٫18") == 0.18
    assert parse_optional_float("") is None and parse_optional_float("abc") is None
    assert parse_optional_float("0") == 0.0                      # صفر واقعی ≠ ناموجود


def test_optional_edit_roundtrip_none_and_value():
    e = OptionalNumberEdit()
    e.set_value(None)
    assert e.value() is None
    e.set_value(2.5)
    assert e.value() == 2.5


def _settings():
    return ProtectionSettings(
        f51=F("NI", 250, 5, "percent"), f50=F("NI", 600, 50, "ms"),
        f51n=F("NI", 30, 5, "percent"), f50n=F("NI", 280, 50, "ms"),
        shots=2, dead_times_s=[2.0, 30.0], reclaim_time_s=300.0)


def test_editor_roundtrip_matches_model_exactly():
    ed = ProtectionSettingsEditor(reclosing=True, counter=False)
    ed.load(_settings())
    out = ProtectionSettings()
    ed.store(out)
    assert out == _settings()


def test_editor_empty_fields_store_none_not_zero():
    ed = ProtectionSettingsEditor(reclosing=True, counter=True)
    ed.load(ProtectionSettings())
    out = ProtectionSettings()
    ed.store(out)
    assert out.f51.pickup_a is None and out.shots is None and out.counter is None
    assert out.dead_times_s == [] and out.reclaim_time_s is None


def test_editor_sectionalizer_counter_and_dead_line():
    ed = ProtectionSettingsEditor(reclosing=False, counter=True)
    ed.load(ProtectionSettings(counter=2, dead_line_current_pct=10.0, dead_line_voltage_pct=20.0))
    out = ProtectionSettings()
    ed.store(out)
    assert (out.counter, out.dead_line_current_pct, out.dead_line_voltage_pct) == (2, 10.0, 20.0)


def test_editor_emits_changed_only_on_user_edit():
    ed = ProtectionSettingsEditor(reclosing=True, counter=False)
    hits = []
    ed.changed.connect(lambda: hits.append(1))
    ed.load(_settings())
    assert hits == []                                            # بارگذاری Signal نمی‌دهد
    ed.shots.setText("3")
    assert hits


def _project():
    p = Project(name="x", feeders=[Feeder(name="F4", substation="پست", peak_current_a=200.0)])
    p.recloser = RecloserInfo(feeder_name="F4", settings=_settings())
    return p, workspace_from_project(p)


def test_explorer_builds_tree_and_emits_selection():
    p, ws = _project()
    ex = ProjectExplorer()
    got = []
    ex.node_selected.connect(got.append)
    ws.selection = StudySelection(heavy=True, recloser=True)
    ex.set_tree(build_project_tree(p, ws))
    assert {"input.recloser", "step.generate", "images", "settings"} <= set(ex._items)
    ex.select_key("input.recloser")
    assert got[-1] == "input.recloser" and ex.current_key() == "input.recloser"


class _Mgr:
    def __init__(self, p):
        self.project = p


def test_report_center_plans_follow_selection_and_output_mode():
    p, ws = _project()
    ws.selection = StudySelection(recloser=True, sectionalizer=True)
    page = ReportCenterPage(_Mgr(p), lambda: ws)
    page.refresh()
    assert [pl.key for pl in page.plans()] == ["combined_protection"]
    ws.report_prefs.output_mode = "separate"
    assert [pl.key for pl in page.plans()] == ["recloser", "sectionalizer"]


def test_report_center_section_prefs_persist_to_workspace():
    p, ws = _project()
    ws.selection = StudySelection(recloser=True)
    page = ReportCenterPage(_Mgr(p), lambda: ws)
    page.refresh()
    first = page.sections.item(0)
    key = first.data(Qt.UserRole)
    first.setCheckState(Qt.Unchecked)
    page._on_sections()
    assert key in ws.report_prefs.disabled_sections
    assert ws.report_prefs.section_order[0] == key


def test_new_project_dialog_requires_at_least_one_study():
    from app.core.studies import StudyKind
    from app.ui.shell.new_project_dialog import NewProjectDialog
    dlg = NewProjectDialog()
    assert dlg.selection().heavy and not dlg.selection().is_empty()
    for c in dlg.checks.values():
        c.setChecked(False)
    assert dlg.selection().is_empty()
    dlg.checks[StudyKind.RECLOSER].setChecked(True)
    dlg.checks[StudyKind.SECTIONALIZER].setChecked(True)
    sel = dlg.selection()
    assert sel.recloser and sel.sectionalizer and not sel.heavy


def test_network_editor_roundtrip_and_scope():
    from app.core.studies import StudyKind
    from app.ui.shell.network_editor import NetworkEditor
    p, ws = _project()
    ed = NetworkEditor(_Mgr(p), lambda: ws, StudyKind.RECLOSER)
    ed._add_to_scope("F4")
    assert ws.scope("recloser") == ["F4"] and ed._feeder is ws.common_network.feeder("F4")
    ed.ed_sc3.set_value(6.5)
    ed.ed_sc1.set_value(2.0)
    ed.cb_dg.setCurrentIndex(2)                                   # «دارد»
    ed.txt_normal.setPlainText("عادی")
    ed.relay_editor._rows["f51"][3].setText("300")
    ed._on_edit()
    f = ws.common_network.feeder("F4")
    assert (f.max_fault_current_ka, f.sc_1ph_ka, f.has_dg, f.normal_scenario) == (6.5, 2.0, True, "عادی")
    relay = f.device("feeder_relay")
    assert relay is not None and relay.settings.f51.pickup_a == 300.0


def test_network_editor_empty_relay_is_not_created():
    from app.core.studies import StudyKind
    from app.ui.shell.network_editor import NetworkEditor
    p, ws = _project()
    ed = NetworkEditor(_Mgr(p), lambda: ws, StudyKind.RECLOSER)
    ed._add_to_scope("F9")
    ed._on_edit()
    assert ws.common_network.feeder("F9").device("feeder_relay") is None
    assert ws.common_network.feeder("F9").has_dg is None           # نامشخص می‌ماند


def test_project_page_has_only_the_six_general_fields_and_no_report_type():
    from app.ui.project_page import ProjectPage
    pg = ProjectPage(None)
    assert "cb_report_type" not in vars(pg) and "ed_applicant" not in vars(pg)
    p = Project(name="x")
    pg.ed_name.setText("پروژه")
    pg.ed_expert.setText("کارشناس")
    pg.save_to(p)
    assert (p.name, p.expert_name) == ("پروژه", "کارشناس")
    pg.load_from(Project(name="دیگر", office="امور"))
    assert pg.ed_name.text() == "دیگر" and pg.ed_office.text() == "امور"


def test_applicant_page_roundtrip_and_auto_increase():
    from app.ui.applicant_page import ApplicantPage
    pg = ApplicantPage()
    p = Project(name="x", applicant_name="شرکت", existing_power_kw=1000.0, requested_power_kw=2500.0)
    pg.load_from(p)
    assert pg.ed_applicant.text() == "شرکت" and "1,500" in pg.lbl_added.text()
    pg.ed_applicant.setText("شرکت جدید")
    pg.sp_requested.setValue(3000.0)
    out = Project(name="y")
    pg.save_to(out)
    assert out.applicant_name == "شرکت جدید" and out.requested_power_kw == 3000.0
    assert out.existing_power_kw == 1000.0


def test_guide_bar_shows_links_and_emits_goto_override():
    from app.core.guided_flow import compute_flow, guide_model
    from app.core.settings import AppSettings
    from app.ui.shell.guide_bar import GuideBar
    p = Project(name="x")
    ws = workspace_from_project(p)
    ws.selection = StudySelection(recloser=True)
    bar = GuideBar()
    got, over = [], []
    bar.goto_requested.connect(lambda r, f: got.append((r, f)))
    bar.override_requested.connect(over.append)
    bar.set_model(guide_model(compute_flow(p, ws, AppSettings()), ws.selection))
    assert "گام 1 از 7" in bar.lbl_title.text()
    bar._on_go()
    assert got[-1] == ("project", "ed_number")
    bar._on_override()
    assert over == ["project"]
    bar.set_model(guide_model([], None))                 # بدون پروژه: نوار پنهان می‌شود
    assert bar.lbl_title.text() == ""
