# -*- coding: utf-8 -*-
"""v2.0.0 — Workspace، انتخاب مطالعات، Common Network و مهاجرت پروژه‌های قدیمی."""
from __future__ import annotations

from app.core.models import Feeder, Project, RecloserInfo, SectionalizerInfo
from app.core.project_tree import (ST_COMPLETE, ST_EMPTY, ST_INCOMPLETE, ST_NOT_SELECTED,
                                   build_dashboard, build_project_tree, study_status)
from app.core.protection_models import FunctionSetting, ProtectionSettings
from app.core.studies import StudyKind, StudySelection, selection_from_legacy
from app.core.workspace import (DEVICE_FEEDER_RELAY, ExistingProtectionDevice,
                                FeederNetworkData, Workspace, load_workspace,
                                resolve_study_inputs, workspace_from_project)


def _project(report_type="heavy"):
    p = Project(name="پروژه", report_type=report_type,
                feeders=[Feeder(name="F4 خلخال", substation="پست", peak_current_a=210.0)])
    p.network_voltage_kv = 20.0
    return p


def test_legacy_report_type_maps_to_selection():
    assert selection_from_legacy("sectionalizer") == StudySelection(sectionalizer=True)
    assert selection_from_legacy("recloser") == StudySelection(recloser=True)
    assert selection_from_legacy("heavy") == StudySelection(heavy=True)
    assert selection_from_legacy(None) == StudySelection(heavy=True)
    assert selection_from_legacy("???") == StudySelection(heavy=True)


def test_migration_seeds_common_network_without_inventing_values():
    ws = workspace_from_project(_project("recloser"))
    f = ws.common_network.feeder("F4 خلخال")
    assert f.load_current_a == 210.0 and f.voltage_kv == 20.0
    assert f.max_fault_current_ka is None and f.min_fault_current_ka is None
    assert ws.selection.recloser and not ws.selection.heavy


def test_workspace_roundtrip_and_missing_file(tmp_path):
    ws = workspace_from_project(_project())
    ws.common_network.feeders[0].existing_protection.append(ExistingProtectionDevice(
        name="رله سر فیدر", device_type=DEVICE_FEEDER_RELAY,
        settings=ProtectionSettings(f51=FunctionSetting("NI", 300.0, 9.0, "percent"))))
    ws.save(tmp_path)
    loaded = load_workspace(tmp_path, _project())
    assert loaded == ws
    # نبود فایل → مهاجرت از پروژه
    empty = load_workspace(tmp_path / "none", _project("sectionalizer"))
    assert empty.selection.sectionalizer


def test_corrupt_workspace_falls_back_to_migration(tmp_path):
    (tmp_path / "workspace.json").write_text("{bad json", encoding="utf-8")
    ws = load_workspace(tmp_path, _project("recloser"))
    assert ws.selection.recloser


def test_study_value_overrides_common_and_common_fills_gaps():
    p = _project("recloser")
    ws = workspace_from_project(p)
    ws.common_network.feeders[0].max_fault_current_ka = 6.0
    p.recloser = RecloserInfo(feeder_name="F4 خلخال", fault_current_ka=5.0)
    r = resolve_study_inputs(p, ws, StudyKind.RECLOSER)
    assert (r["fault_current_ka"].value, r["fault_current_ka"].source) == (5.0, "study")
    assert (r["load_current_a"].value, r["load_current_a"].source) == (210.0, "common")
    assert r["min_fault_current_ka"].source == "missing"


def test_upstream_for_recloser_comes_from_common_feeder_relay():
    p = _project("recloser")
    ws = workspace_from_project(p)
    relay = ProtectionSettings(f51=FunctionSetting("NI", 300.0, 9.0, "percent"))
    ws.common_network.feeders[0].existing_protection.append(
        ExistingProtectionDevice(name="رله", device_type=DEVICE_FEEDER_RELAY, settings=relay))
    p.recloser = RecloserInfo(feeder_name="F4 خلخال")
    r = resolve_study_inputs(p, ws, StudyKind.RECLOSER)
    assert r["upstream_settings"] is relay


def test_sectionalizer_reference_is_linked_recloser():
    p = _project("sectionalizer")
    ws = workspace_from_project(p)
    p.recloser = RecloserInfo(settings=ProtectionSettings(f51=FunctionSetting("NI", 400.0, 7.5, "percent")))
    p.sectionalizer = SectionalizerInfo(feeder_name="F4 خلخال")
    assert resolve_study_inputs(p, ws, StudyKind.SECTIONALIZER)["upstream_settings"] is p.recloser.settings
    p.sectionalizer.link_to_project_recloser = False
    assert resolve_study_inputs(p, ws, StudyKind.SECTIONALIZER)["upstream_settings"] is None


def test_tree_and_dashboard_never_claim_complete_without_evaluation():
    p = _project("recloser")
    ws = workspace_from_project(p)
    tree = build_project_tree(p, ws)
    keys = set(tree.keys())
    assert {"dashboard", "step.project", "step.input", "step.validation", "step.analysis",
            "step.review", "step.preview", "step.generate", "images", "settings"} <= keys
    assert "input.recloser" in keys and "input.heavy" not in keys and "input.sectionalizer" not in keys
    assert study_status(p, ws, StudyKind.SECTIONALIZER) == ST_NOT_SELECTED
    assert study_status(p, ws, StudyKind.RECLOSER) == ST_EMPTY
    p.recloser = RecloserInfo(feeder_name="F4 خلخال")
    assert study_status(p, ws, StudyKind.RECLOSER) == "not_evaluated"
    class R:  # نتیجهٔ ساختگی
        status, engineer_review_required = "MISSING_DATA", True
    assert study_status(p, ws, StudyKind.RECLOSER, [R()]) == ST_INCOMPLETE
    class Ok:
        status, engineer_review_required = "PASS", False
    assert study_status(p, ws, StudyKind.RECLOSER, [Ok()]) == ST_COMPLETE
    assert build_dashboard(p, ws)["heavy"]["status"] == ST_NOT_SELECTED


def test_new_tree_numbers_steps_one_to_seven_and_shows_states():
    p = _project("recloser")
    ws = workspace_from_project(p)
    tree = build_project_tree(p, ws, {"project": "done", "input": "warning"})
    labels = {n: tree.find(n).label for n in ("step.project", "step.input", "step.validation",
                                              "step.analysis", "step.review", "step.preview",
                                              "step.generate")}
    assert labels["step.project"].startswith("✓ 1.") and labels["step.input"].startswith("! 2.")
    assert [labels[k].split(".")[0].lstrip("✓!✕● ") for k in labels] == ["1", "2", "3", "4", "5", "6", "7"]
    assert tree.find("report.select") and tree.find("report.generate")


def test_tree_has_per_study_input_pages_and_feeder_scope():
    p = _project("recloser")
    ws = workspace_from_project(p)
    ws.selection = StudySelection(heavy=True, recloser=True, sectionalizer=True)
    ws.add_to_scope("recloser", "F4 خلخال")
    tree = build_project_tree(p, ws)
    for key in ("heavy.applicant", "heavy.feeders", "heavy.study", "recloser.network",
                "recloser.device", "recloser.settings", "sectionalizer.network",
                "sectionalizer.device", "sectionalizer.settings"):
        assert tree.find(key), key
    assert tree.find("feeder:recloser:F4 خلخال")
    keys = tree.keys()
    assert len(keys) == len(set(keys))                      # کلید گره‌ها یکتا است


def test_study_scope_is_independent_and_persisted(tmp_path):
    ws = workspace_from_project(_project())
    ws.add_to_scope("recloser", "F4 خلخال")
    ws.add_to_scope("recloser", "f4 خلخال")                 # تکراری (بدون حساسیت به حروف)
    ws.add_to_scope("sectionalizer", "F8 سلوط")
    ws.remove_from_scope("recloser", "F4 خلخال")
    assert ws.scope("recloser") == [] and ws.scope("sectionalizer") == ["F8 سلوط"]
    assert ws.common_network.feeder("F4 خلخال") is not None  # حذف از محدوده، داده را پاک نمی‌کند
    ws.save(tmp_path)
    assert load_workspace(tmp_path, _project()).study_scopes == ws.study_scopes


def test_new_network_fields_roundtrip():
    from app.core.workspace import FeederNetworkData
    ws = workspace_from_project(_project())
    f = ws.common_network.feeders[0]
    f.sc_1ph_ka, f.has_dg, f.dg_note = 2.1, True, "۵۰۰ کیلووات"
    f.normal_scenario, f.emergency_scenario = "عادی", "اضطراری"
    back = Workspace.from_dict(ws.to_dict())
    g = back.common_network.feeders[0]
    assert (g.sc_1ph_ka, g.has_dg, g.dg_note, g.normal_scenario, g.emergency_scenario) == (
        2.1, True, "۵۰۰ کیلووات", "عادی", "اضطراری")
    assert FeederNetworkData().has_dg is None                # نامشخص، نه «ندارد»


def test_legacy_workspace_json_without_scopes_loads(tmp_path):
    import json
    legacy = {"schema_version": 1, "selection": {"recloser": True},
              "common_network": {"feeders": [{"name": "F1"}]}}
    (tmp_path / "workspace.json").write_text(json.dumps(legacy), encoding="utf-8")
    ws = load_workspace(tmp_path, _project())
    assert ws.selection.recloser and ws.study_scopes == {}


def test_migration_seeds_scope_from_study_feeder():
    p = _project("recloser")
    p.recloser = RecloserInfo(feeder_name="F4 خلخال")
    assert workspace_from_project(p).scope("recloser") == ["F4 خلخال"]


def test_report_type_for_selection():
    from app.core.studies import report_type_for_selection as rt
    assert rt(StudySelection(heavy=True, recloser=True)) == "heavy"
    assert rt(StudySelection(recloser=True, sectionalizer=True)) == "combined_protection"
    assert rt(StudySelection(recloser=True)) == "recloser"
    assert rt(StudySelection(sectionalizer=True)) == "sectionalizer"
    assert rt(StudySelection()) == "heavy"
