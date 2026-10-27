# -*- coding: utf-8 -*-
"""v2.0.0 — سازگاری با پروژه‌های ذخیره‌شدهٔ قبلی (report_type / sectionalizer / recloser)."""
from __future__ import annotations

import json

from app.core.models import (Feeder, Project, RecloserInfo, SectionalizerInfo,
                             project_from_dict, to_dict)
from app.core.project_manager import PROJECT_FILE, ProjectManager
from app.core.protection_models import FunctionSetting as F, ProtectionSettings
from app.core.report_types import (REPORT_TYPE_COMBINED_PROTECTION, REPORT_TYPE_RECLOSER,
                                   REPORT_TYPE_SECTIONALIZER, is_implemented, normalize)
from app.core.workspace import WORKSPACE_FILE, Workspace


class _Settings:
    """فقط همان بخشی از AppSettings که ProjectManager استفاده می‌کند (بدون نوشتن روی دیسک)."""

    def add_recent(self, _path: str) -> None:
        pass


# نمونهٔ project.json در قالب v1.3/v1.4 (بدون هیچ فیلد v2)
LEGACY = {
    "name": "پروژه قدیمی", "report_number": "PD-21-001", "date_jalali": "1404/10/01",
    "report_type": "sectionalizer", "applicant_name": "اداره برق",
    "sectionalizer": {"installation_location": "تیر ۱۲۳", "feeder_name": "F8 سلوط",
                      "fault_current_ka": 4.5, "pickup_current_a": 380.0, "tms": 4.5},
    "recloser": {"installation_location": "پست", "feeder_name": "F8 سلوط",
                 "pickup_current_a": 400.0, "tms": 7.5},
    "feeders": [{"name": "F8 سلوط", "substation": "پست ۶۳/۲۰", "peak_current_a": 210.0}],
}


def test_legacy_json_loads_without_losing_any_field():
    p = project_from_dict(LEGACY)
    assert p.report_type == "sectionalizer"
    assert p.sectionalizer.pickup_current_a == 380.0 and p.sectionalizer.tms == 4.5
    assert p.recloser.pickup_current_a == 400.0 and p.recloser.feeder_name == "F8 سلوط"
    assert p.feeders[0].peak_current_a == 210.0
    # فیلدهای جدید با پیش‌فرض امن (ناموجود، نه صفر)
    assert p.recloser.settings.is_empty() and p.sectionalizer.settings.is_empty()
    assert p.recloser.rated_current_a is None and p.recloser.include_in_report is True
    assert p.recloser.name == "R1" and p.sectionalizer.name == "S1"


def test_legacy_fields_survive_a_full_roundtrip():
    out = to_dict(project_from_dict(LEGACY))
    for key, value in LEGACY["sectionalizer"].items():
        assert out["sectionalizer"][key] == value
    for key, value in LEGACY["recloser"].items():
        assert out["recloser"][key] == value
    assert out["report_type"] == "sectionalizer"


def test_new_protection_settings_roundtrip_through_json_text():
    p = Project(name="x")
    p.recloser = RecloserInfo(
        feeder_name="F4", rated_current_a=630.0, placement_basis="تمرکز خاموشی",
        settings=ProtectionSettings(f51=F("NI", 250.0, 5.0, "percent"), shots=2,
                                    dead_times_s=[2.0, 30.0], reclaim_time_s=300.0),
        upstream_settings=ProtectionSettings(f51=F("NI", 300.0, 9.0, "percent")))
    p.sectionalizer = SectionalizerInfo(
        link_to_project_recloser=False,
        settings=ProtectionSettings(counter=2, dead_line_current_pct=10.0,
                                    dead_line_voltage_pct=20.0))
    back = project_from_dict(json.loads(json.dumps(to_dict(p), ensure_ascii=False)))
    assert back.recloser.settings == p.recloser.settings
    assert isinstance(back.recloser.settings.f51, F)            # شیء، نه dict خام
    assert back.recloser.upstream_settings.f51.pickup_a == 300.0
    assert back.sectionalizer.settings.counter == 2
    assert back.sectionalizer.link_to_project_recloser is False


def test_unknown_future_keys_are_ignored_not_fatal():
    data = dict(LEGACY, recloser=dict(LEGACY["recloser"], future_field="x",
                                       settings={"f51": {"pickup_a": 250, "future": 1},
                                                 "future_top": 1}))
    p = project_from_dict(data)
    assert p.recloser.settings.f51.pickup_a == 250


def test_report_types_registry_v2():
    assert is_implemented(REPORT_TYPE_RECLOSER)
    assert is_implemented(REPORT_TYPE_COMBINED_PROTECTION)
    assert normalize(REPORT_TYPE_COMBINED_PROTECTION) == REPORT_TYPE_COMBINED_PROTECTION
    assert normalize("???") == "heavy"


def test_title_text_for_new_report_types():
    p = project_from_dict(LEGACY)
    # v2.5.0 — «عنوان پروژه» (در صورت وجود) بر متن خودکار مقدم است
    p.report_type = REPORT_TYPE_RECLOSER
    assert p.title_text() == p.name
    p.name = ""                      # بدون عنوان: متن خودکار قبلی
    assert "ریکلوزر" in p.title_text()
    p.report_type = REPORT_TYPE_COMBINED_PROTECTION
    assert "ریکلوزر و سکشنالایزر" in p.title_text()
    p.report_type = REPORT_TYPE_SECTIONALIZER
    assert "سکشنالایزر" in p.title_text()


def _write_legacy_dir(tmp_path):
    (tmp_path / PROJECT_FILE).write_text(json.dumps(LEGACY, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_project_manager_migrates_legacy_project_and_persists_workspace(tmp_path):
    d = _write_legacy_dir(tmp_path)
    assert not (d / WORKSPACE_FILE).exists()
    pm = ProjectManager(_Settings())
    pm.open_project(d / PROJECT_FILE)
    ws = pm.workspace
    assert ws.selection.sectionalizer and not ws.selection.heavy      # از report_type مهاجرت شد
    assert ws.common_network.feeder("F8 سلوط").load_current_a == 210.0
    assert pm.project._workspace is ws                                # noqa: SLF001
    pm.save()
    assert (d / WORKSPACE_FILE).exists()
    saved = json.loads((d / PROJECT_FILE).read_text(encoding="utf-8"))
    assert "_workspace" not in saved                                  # ویژگی گذرا ذخیره نمی‌شود
    assert saved["sectionalizer"]["pickup_current_a"] == 380.0        # داده قدیمی دست‌نخورده
    # بازکردن دوباره: Workspace از فایل خوانده می‌شود
    pm2 = ProjectManager(_Settings())
    pm2.open_project(d)
    assert pm2.workspace == ws


def test_edited_selection_is_preserved_on_reopen(tmp_path):
    d = _write_legacy_dir(tmp_path)
    pm = ProjectManager(_Settings())
    pm.open_project(d)
    pm.workspace.selection.recloser = True
    pm.workspace.report_prefs.output_mode = "separate"
    pm.save()
    pm2 = ProjectManager(_Settings())
    pm2.open_project(d)
    assert pm2.workspace.selection.recloser and pm2.workspace.selection.sectionalizer
    assert pm2.workspace.report_prefs.output_mode == "separate"


def test_new_project_creates_workspace_json(tmp_path):
    pm = ProjectManager(_Settings())
    pm.new_project(tmp_path / "proj", Project(name="n", feeders=[Feeder(name="F1")]))
    assert (tmp_path / "proj" / WORKSPACE_FILE).exists()
    assert isinstance(pm.workspace, Workspace)
    assert pm.workspace.common_network.feeder("F1") is not None
