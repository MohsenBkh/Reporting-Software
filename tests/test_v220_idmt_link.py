# -*- coding: utf-8 -*-
"""v2.2.0 — پیوند با نرم‌افزار «هماهنگی حفاظت فیدر (IDMT Coordination)».

داده‌ها یک‌بار در ابزار IDMT وارد می‌شوند؛ بسته «خروجی گزارش‌ساز» شامل تنظیمات
نهایی + نمودارهای TCC/توالی/برگه A4 است و این‌جا وارد مدل ReportForge می‌شود.
"""
from __future__ import annotations

import base64
import json

import pytest

from app.core.idmt_bundle import (BUNDLE_KIND, IDMT_TITLE_PREFIX,
                                  IdmtBundleError, apply_bundle_to_project,
                                  import_idmt_file, load_bundle)
from app.core.models import IMAGE_KINDS, Project
from app.core.report_types import REPORT_TYPE_RECLOSER
from app.core.report_sections import (PROTECTION_DEFAULT_SECTION_BY_KIND,
                                      PROTECTION_IMAGE_KINDS, SECTION_LABELS)
from app.core.settings import AppSettings
from app.core.project_manager import ProjectManager
from app.utils.resources import resource_path

# PNG معتبر ۱×۱ (برای آزمون ورود تصاویر بسته)
PNG_1PX = base64.b64encode(base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")).decode()


def _settings(pickup, tms, inst_pickup=None, curve="VI", inst_time=0.05):
    return {"pickup": pickup, "curve": curve, "tms": tms, "delayMode": "IDMT",
            "dt": 0.5, "instEnabled": inst_pickup is not None,
            "instPickup": inst_pickup, "instTime": inst_time}


def make_bundle(**over):
    """بسته نمونه مطابق خروجی واقعی دکمه «خروجی گزارش‌ساز» ابزار IDMT ۰۸."""
    b = {
        "kind": BUNDLE_KIND,
        "app": "IDMT Coordination",
        "version": "08",
        "schema": 8,
        "exportedAt": "2026-10-16T08:00:00.000Z",
        "project": {
            "schema": 8,
            "meta": {"title": "مطالعه فیدر ۴ خلخال", "feeder": "فیدر ۴ خلخال",
                     "date": "2026-10-16"},
            "system": {"voltage": 20, "topology": "parallel"},
            "inputs": {
                "phase": {"load": 150, "ct": 300, "thermal": 160, "faultMin": 250,
                          "faultMax": 1000, "fuseFault": 403, "mct": 0.04,
                          "mctCurrent": 403, "ctiDown": 0.15, "ctiUp": 0.15},
                "earth": {"load": 150, "ct": 300, "method": "math", "kCLPU": 2,
                          "faultMin": 100, "faultMax": 530, "fuseFault": 360,
                          "mct": 0.04, "mctCurrent": 360, "ctiDown": 0.3, "ctiUp": 0.3},
            },
        },
        "resolved": {
            "phase": {
                "rec": _settings(190, 0.19, inst_pickup=490),
                "head": _settings(200, 0.5, inst_pickup=2500),
                "sections": [{"id": "S1", "name": "سکشنالایزر 1", "ct": 200,
                              "load": 100, "settings": _settings(180, 0.16, 440,
                                                                 inst_time=0.04)}],
            },
            "earth": {
                "rec": _settings(60, 0.3, inst_pickup=440),
                "head": _settings(80, 0.6, inst_pickup=1200),
                "sections": [{"id": "S1", "name": "سکشنالایزر 1", "ct": 200,
                              "settings": _settings(55, 0.27, 390, inst_time=0.04)}],
            },
            "cycle": {"shots": 2, "reclaim": 300, "deadTimes": [2, 30], "maxDead": 30,
                      "sections": [{"id": "S1", "settings": {
                          "counter": 2, "resetSingle": 301, "deadLogic": "both",
                          "deadI": 20, "deadU": 4}}]},
            "counts": {"pass": 40, "fail": 1, "warn": 2, "unknown": 0},
            "failures": [{"id": "phase:R:50-range", "title": "قیود Pickup آنی",
                          "target": "≤ 500", "actual": "510"}],
        },
        "charts": {"tcc_phase": PNG_1PX, "tcc_earth": PNG_1PX,
                   "sequence_phase": PNG_1PX, "sequence_earth": PNG_1PX,
                   "sheet": PNG_1PX},
    }
    b.update(over)
    return b


# ---------------------------------------------------------------------------
# خواندن بسته
# ---------------------------------------------------------------------------
def test_load_bundle_accepts_bundle_and_raw_project(tmp_path):
    f = tmp_path / "IDMT08-ReportForge.json"
    f.write_text(json.dumps(make_bundle(), ensure_ascii=False), encoding="utf-8")
    assert load_bundle(f)["kind"] == BUNDLE_KIND
    # فایل «خروجی JSON» خام ابزار نیز پذیرفته می‌شود (بدون resolved/نمودار)
    raw = tmp_path / "IDMT08-Project.json"
    raw.write_text(json.dumps(make_bundle()["project"], ensure_ascii=False),
                   encoding="utf-8")
    loaded = load_bundle(raw)
    assert loaded["resolved"] is None and loaded["charts"] == {}


def test_load_bundle_rejects_foreign_files(tmp_path):
    bad = tmp_path / "x.json"
    bad.write_text('{"hello": 1}', encoding="utf-8")
    with pytest.raises(IdmtBundleError):
        load_bundle(bad)
    notjson = tmp_path / "y.json"
    notjson.write_text("<html>", encoding="utf-8")
    with pytest.raises(IdmtBundleError):
        load_bundle(notjson)


# ---------------------------------------------------------------------------
# نگاشت تنظیمات نهایی → مدل ReportForge
# ---------------------------------------------------------------------------
def test_apply_bundle_maps_recloser_settings():
    p = Project(report_type=REPORT_TYPE_RECLOSER)
    res = apply_bundle_to_project(p, make_bundle())
    s = p.recloser.settings
    # ۵۱ فاز: TMS ضریبی ۰٫۱۹ → ۱۹٪ (قرارداد درصدی گزارش‌ساز)
    assert s.f51.pickup_a == 190 and s.f51.curve == "VI"
    assert s.f51.time_value == 19 and s.f51.time_unit == "percent"
    # ۵۰ فاز: زمان ثانیه → میلی‌ثانیه
    assert s.f50.pickup_a == 490 and s.f50.time_value == 50 and s.f50.time_unit == "ms"
    # زمین
    assert s.f51n.pickup_a == 60 and s.f51n.time_value == 30
    assert s.f50n.pickup_a == 440
    # چرخه وصل مجدد
    assert s.shots == 2 and s.reclaim_time_s == 300 and s.dead_times_s == [2, 30]
    # مشخصات مطالعه
    assert p.recloser.feeder_name == "فیدر ۴ خلخال"
    assert p.recloser.fault_current_ka == 1.0 and p.recloser.min_fault_current_ka == 0.25
    assert p.recloser.load_current_a == 150 and p.recloser.nominal_voltage_kv == 20
    assert p.recloser.pickup_current_a == 190
    assert "IDMT" in s.note
    assert any("ریکلوزر" in a for a in res.applied)


def test_apply_bundle_maps_upstream_and_sectionalizer():
    p = Project(report_type=REPORT_TYPE_RECLOSER)
    apply_bundle_to_project(p, make_bundle())
    up = p.recloser.upstream_settings
    assert up.f51.pickup_a == 200 and up.f51.time_value == 50     # TMS 0.5 → 50%
    assert up.f51n.pickup_a == 80
    sz = p.sectionalizer
    assert sz.settings.f51.pickup_a == 180 and sz.settings.f51.time_value == 16
    assert sz.settings.f50.time_value == 40                       # 0.04 s → 40 ms
    assert sz.settings.counter == 2
    # Dead line: deadI=20A با CT=200 → ۱۰٪ ، deadU=4kV با 20kV → ۲۰٪
    assert sz.settings.dead_line_current_pct == 10
    assert sz.settings.dead_line_voltage_pct == 20
    assert sz.name == "سکشنالایزر 1" and sz.feeder_name == "فیدر ۴ خلخال"


def test_apply_bundle_reports_idmt_failures_as_warnings():
    p = Project(report_type=REPORT_TYPE_RECLOSER)
    res = apply_bundle_to_project(p, make_bundle())
    assert res.failures and any("قیود" in f for f in res.failures)
    assert any("ناموفق" in w for w in res.warnings)


def test_raw_project_json_imports_inputs_only_with_warning():
    p = Project(report_type=REPORT_TYPE_RECLOSER)
    res = apply_bundle_to_project(p, {"kind": BUNDLE_KIND,
                                      "project": make_bundle()["project"],
                                      "resolved": None, "charts": {}})
    assert p.recloser.fault_current_ka == 1.0          # ورودی‌های خام منتقل شد
    assert not p.recloser.settings.any_function_set()  # تنظیم نهایی ساخته نشد
    assert any("خروجی گزارش‌ساز" in w for w in res.warnings)


# ---------------------------------------------------------------------------
# ورود کامل با ProjectManager: تصاویر + جایگزینی در ورود مجدد
# ---------------------------------------------------------------------------
def _manager(tmp_path):
    m = ProjectManager(AppSettings())
    m.new_project(tmp_path / "prj", Project(name="تست",
                                            report_type=REPORT_TYPE_RECLOSER))
    return m


def test_import_idmt_file_places_charts_in_report_sections(tmp_path):
    m = _manager(tmp_path)
    f = tmp_path / "bundle.json"
    f.write_text(json.dumps(make_bundle(), ensure_ascii=False), encoding="utf-8")
    res = import_idmt_file(m, f)
    assert len(res.images) == 5
    by_section = {}
    for img in m.project.images:
        by_section.setdefault(img.section_key, []).append(img)
        assert img.title.startswith(IDMT_TITLE_PREFIX)
        assert (m.project_dir / "images" / img.file_name).exists()
    assert len(by_section["prot_coordination"]) == 2      # TCC فاز + زمین
    assert len(by_section["prot_scenario"]) == 2          # توالی فاز + زمین
    assert len(by_section["prot_settings_sheet"]) == 1    # برگه A4
    kinds = {img.kind for img in m.project.images}
    assert kinds == {"tcc", "sequence", "settings_sheet"}


def test_reimport_replaces_previous_idmt_images(tmp_path):
    m = _manager(tmp_path)
    f = tmp_path / "bundle.json"
    f.write_text(json.dumps(make_bundle(), ensure_ascii=False), encoding="utf-8")
    import_idmt_file(m, f)
    import_idmt_file(m, f)                                 # ورود دوباره
    assert len(m.project.images) == 5                      # تکراری نشد


# ---------------------------------------------------------------------------
# ثبت بخش/نوع شکل جدید + حذف تولید TCC داخلی
# ---------------------------------------------------------------------------
def test_new_image_kinds_and_appendix_section_registered():
    assert "sequence" in IMAGE_KINDS and "settings_sheet" in IMAGE_KINDS
    assert "sequence" in PROTECTION_IMAGE_KINDS
    assert PROTECTION_DEFAULT_SECTION_BY_KIND["sequence"] == "prot_scenario"
    assert PROTECTION_DEFAULT_SECTION_BY_KIND["settings_sheet"] == "prot_settings_sheet"
    assert "prot_settings_sheet" in SECTION_LABELS


def test_settings_sheet_appendix_only_when_image_exists(tmp_path):
    import sys
    sys.path.insert(0, "tests")
    from test_v200_protection_rules import _khalkhal
    from app.core.studies import StudyKind
    from app.report.composer import ReportComposer
    p, ws = _khalkhal()
    report = ReportComposer().compose(p, ws, [StudyKind.RECLOSER])
    assert all(s.key != "prot_settings_sheet" for s in report.sections)  # بدون شکل → حذف

    class _Img:
        uid = "x1"
        file_name = "sheet.png"
        title = IDMT_TITLE_PREFIX + "برگه"
        kind = "settings_sheet"
        section_key = "prot_settings_sheet"
        order = 0
        caption = "برگه تنظیمات"
        enabled = True
        kind_label = "برگه"
    png = tmp_path / "sheet.png"
    png.write_bytes(base64.b64decode(PNG_1PX))
    p.__class__ = type("P", (p.__class__,), {
        "active_images": property(lambda self: [_Img()])})
    report = ReportComposer().compose(p, ws, [StudyKind.RECLOSER],
                                      image_resolver=lambda i: str(png))
    sheet = next(s for s in report.sections if s.key == "prot_settings_sheet")
    assert sheet.title.startswith("پیوست")
    from app.report.sections import FigureBlock
    assert any(isinstance(b, FigureBlock) for b in sheet.blocks)


def test_idmt_tool_ships_with_app_and_has_export_button():
    html = resource_path("idmt_coordination.html")
    assert html.exists() and html.stat().st_size > 500_000
    text = html.read_text(encoding="utf-8")
    assert "exportBundle" in text
    assert "idmt-reportforge-bundle" in text
    assert "tcc_" in text and "sequence_" in text and '"sheet"' in text.replace("charts.sheet", '"sheet"')
