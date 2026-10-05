# -*- coding: utf-8 -*-
"""تست‌های نسخه ۱.۲.۰ — «اصلاحات نسخه بعدی» (پنج بند کارفرما).

1. جدول‌های شبیه‌اکسل: Delete پاک می‌کند، Enter ردیف بعد، چسباندن بلوکی از Excel.
2. بارگذاری فیدر: پیک فیدر **+ بار جدید** با آستانه‌های ۷ و ۸ مگاوات
   («بحرانی» / «شدیداً بحرانی») و پیشنهاد راهکار (بازآرایی فیدر همجوار / احداث فیدر جدید).
3. کلید On/Off هر ورودی: خاموش‌ها از تحلیل و گزارش حذف می‌شوند و داده‌شان پاک نمی‌شود.
4. بخش تصاویر: محل قرارگیری (بخش)، اولویت/ترتیب، کپشن مستقل و چند شکل برای یک بخش.
5. ماندگاری کامل تنظیمات/فراداده در project.json و سازگاری با پروژه‌های قدیمی.

هیچ عدد یا معیار جدیدی در این تست‌ها اختراع نشده است؛ آستانه‌های ۷/۸ از تنظیمات
(سیاست بهره‌برداری اعلامی کارفرما) خوانده می‌شوند.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 برای تست‌های UI لازم است")

from PySide6.QtCore import QMimeData, QPoint, Qt                       # noqa: E402
from PySide6.QtGui import QKeyEvent                                    # noqa: E402
from PySide6.QtWidgets import (QApplication, QListWidgetItem,          # noqa: E402
                               QTableWidget, QTableWidgetItem)

from app.core.models import (Feeder, ForecastPoint, NeighborFeeder,     # noqa: E402
                             PowerFlowResult, Project)
from app.core.settings import AppSettings                               # noqa: E402


@pytest.fixture(scope="module")
def app():
    inst = QApplication.instance() or QApplication([])
    inst.setLayoutDirection(Qt.RightToLeft)
    return inst


@pytest.fixture()
def manager(tmp_path):
    from app.core.project_manager import ProjectManager

    m = ProjectManager(AppSettings())
    m.new_project(tmp_path / "proj", Project(
        name="پروژه ۱.۲.۰", applicant_name="متقاضی", report_number="DM-12-000",
        date_jalali="1405/07/01", requested_power_kw=6000, existing_power_kw=1000))
    m.project.feeders = [Feeder(name="فیدر ۱۰۱", substation="پست ۱", peak_load_mw=6.5,
                                peak_year=1403, power_factor=0.93, peak_current_a=90,
                                max_current_a=400, capacity_mw=10.0,
                                before=PowerFlowResult(90, 300, 0.97, 0.98),
                                after=PowerFlowResult(120, 330, 0.96, 0.97))]
    return m


# ===========================================================================
# ۱) جدول شبیه‌اکسل
# ===========================================================================
def _key(table, key, modifiers=Qt.NoModifier):
    ev = QKeyEvent(QKeyEvent.KeyPress, key, modifiers)
    QApplication.sendEvent(table, ev)


def test_excel_table_delete_enter_and_paste(app):
    from app.ui.excel_table import enable_excel_table

    t = QTableWidget(3, 3)
    t.setHorizontalHeaderLabels(["الف", "ب", "ج"])
    for r in range(3):
        for c in range(3):
            t.setItem(r, c, QTableWidgetItem(f"{r}{c}"))
    enable_excel_table(t, editable=True, auto_add_row=True)
    t.show()
    app.processEvents()

    # Delete فقط خانه‌های انتخاب‌شده را پاک می‌کند
    t.setCurrentCell(1, 1)
    _key(t, Qt.Key_Delete)
    assert t.item(1, 1).text() == ""
    assert t.item(1, 0).text() == "10" and t.item(0, 1).text() == "01"

    # Enter به ردیف بعد می‌رود و در آخرین ردیف، ردیف جدید می‌سازد
    t.setCurrentCell(2, 0)
    _key(t, Qt.Key_Return)
    assert t.rowCount() == 4

    # چسباندن بلوکی از Excel (Tab بین ستون‌ها، \r\n بین ردیف‌ها)
    data = QMimeData()
    data.setText("۱\t۲\r\n۳\t۴")
    QApplication.clipboard().setMimeData(data)
    t.setCurrentCell(0, 0)
    t.excel.paste()
    assert (t.item(0, 0).text(), t.item(0, 1).text()) == ("۱", "۲")
    assert (t.item(1, 0).text(), t.item(1, 1).text()) == ("۳", "۴")


def test_excel_table_paste_grows_rows_and_copies_tsv(app):
    from app.ui.excel_table import enable_excel_table

    t = QTableWidget(1, 2)
    enable_excel_table(t, editable=True, auto_add_row=True)
    data = QMimeData()
    data.setText("a\tb\nc\td\ne\tf")
    QApplication.clipboard().setMimeData(data)
    t.setCurrentCell(0, 0)
    t.excel.paste()
    assert t.rowCount() == 3 and t.item(2, 1).text() == "f"
    t.selectAll()
    t.excel.copy()
    assert QApplication.clipboard().text().splitlines()[0] == "a\tb"
    assert QApplication.clipboard().text().splitlines()[2] == "e\tf"


def test_readonly_table_blocks_editing_but_allows_copy(app):
    from app.ui.excel_table import enable_excel_table

    t = QTableWidget(1, 1)
    t.setItem(0, 0, QTableWidgetItem("نتیجه"))
    enable_excel_table(t, editable=False, auto_add_row=False)
    t.setCurrentCell(0, 0)
    data = QMimeData(); data.setText("تغییر")
    QApplication.clipboard().setMimeData(data)
    t.excel.paste()
    assert t.item(0, 0).text() == "نتیجه"       # جدول فقط‌خواندنی تغییر نکرد
    t.excel.copy()
    assert QApplication.clipboard().text() == "نتیجه"


# ===========================================================================
# ۲) بارگذاری فیدر: پیک + بار جدید، آستانه‌های ۷ و ۸ مگاوات
# ===========================================================================
def _study_project(manager, added_kw=6000, peak_mw=6.5, neighbor_mw=1.5):
    p = manager.project
    p.feeders[0].peak_load_mw = peak_mw
    p.feeders[0].capacity_mw = 10.0
    p.demand.without_coincidence_kw = float(added_kw)
    p.demand.with_coincidence_kw = float(added_kw)
    if neighbor_mw is not None:
        p.neighbor_feeders = [NeighborFeeder(name="فیدر همجوار ۱۰۲", office="امور ۱",
                                             substation="پست ۱", peak_load_mw=3.0,
                                             capacity_mw=8.0, distance_km=1.2,
                                             transferable_mw=neighbor_mw)]
    return p


def test_feeder_total_load_uses_peak_plus_added_load(manager):
    from app.core.study import feeder_loading_context

    p = _study_project(manager, added_kw=6000)          # ۶.۵ + ۶.۰ = ۱۲.۵ MW
    ctx = feeder_loading_context(p, manager.settings, p.feeders[0])
    assert ctx["feeder_total_load_mw"] == pytest.approx(12.5)
    assert ctx["feeder_total_ge_critical"] is True      # ≥ ۷
    assert ctx["feeder_total_ge_severe"] is True        # ≥ ۸
    assert ctx["over_severe_mw"] == pytest.approx(4.5)


def test_loading_rule_flags_critical_and_severe_with_remedy(manager):
    from app.core.study import collect_study_results
    from app.rules.rule_engine import RuleEngine

    p = _study_project(manager, added_kw=6000)
    results = collect_study_results(p, manager.settings, RuleEngine())
    by_id = {r.rule_id: r for r in results}
    assert by_id["LD-SEVERE"].status == "FAIL"           # ۱۲.۵ ≥ ۸ ⇒ شدیداً بحرانی
    assert "LD-CRITICAL" not in by_id                    # باند ۷–۸ با باند شدید جمع نمی‌شود
    assert "بازآرایی" in by_id["LD-SEVERE"].recommended_text
    assert "فیدر همجوار ۱۰۲" in by_id["LD-SEVERE"].recommended_text
    prop = by_id["LD-REARRANGE-PROPOSAL"]
    assert prop.calculated_values["transfer_proposed_mw"] == pytest.approx(1.5)
    assert prop.calculated_values["transfer_limited"] is True


def test_loading_bands_are_separated_by_threshold(manager):
    """زیر ۷: عادی — بین ۷ و ۸: بحرانی (WARNING) — ۸ و بالاتر: شدیداً بحرانی (FAIL)."""
    from app.core.study import collect_study_results
    from app.rules.rule_engine import RuleEngine

    p = _study_project(manager, added_kw=1000, peak_mw=5.0, neighbor_mw=None)  # ۶.۰ MW
    below = {r.rule_id: r for r in collect_study_results(p, manager.settings, RuleEngine())}
    assert "LD-FEEDER-LOADING-OK" in below
    assert below.get("LD-CRITICAL", None) is None and below.get("LD-SEVERE", None) is None

    p2 = _study_project(manager, added_kw=750, peak_mw=6.5, neighbor_mw=None)  # ۷.۲۵ MW
    band = {r.rule_id: r for r in collect_study_results(p2, manager.settings, RuleEngine())}
    assert band["LD-CRITICAL"].status == "WARNING"
    assert "LD-SEVERE" not in band


def test_missing_loading_thresholds_reports_missing_rule(manager):
    from app.core.study import collect_study_results
    from app.rules.rule_engine import RuleEngine

    settings = manager.settings
    settings.study.feeder_loading_critical_mw = None
    settings.study.feeder_loading_severe_mw = None
    p = _study_project(manager, added_kw=6000)
    results = collect_study_results(p, settings, RuleEngine())
    # بی‌آنکه آستانه‌ای اختراع شود: هیچ داوری بارگذاری انجام نمی‌شود
    assert any(r.rule_id == "LD-THRESHOLD-UNDEFINED" and r.status == "MISSING_RULE"
               for r in results)
    assert not any(r.rule_id in ("LD-CRITICAL", "LD-SEVERE") for r in results)


def test_rearrange_scenario_generated_with_neighbor_feeder(manager):
    from app.core import scenarios as scenario_mod
    from app.rules.rule_engine import RuleEngine

    p = _study_project(manager, added_kw=6000)
    scenario_mod.ensure_scenarios(p, manager.settings, RuleEngine())
    kinds = [s.kind for s in p.scenarios]
    assert "rearrangement" in kinds
    sc = next(s for s in p.scenarios if s.kind == "rearrangement")
    assert "فیدر همجوار ۱۰۲" in sc.title
    assert sc.review_status == "REQUIRES_ENGINEER_REVIEW"


def test_thresholds_are_configurable_not_hardcoded(manager):
    """با تغییر آستانه‌ها، داوری Ruleها هم تغییر می‌کند (هیچ عددی هارد‌کد نیست)."""
    from app.core.study import feeder_loading_context

    settings = manager.settings
    settings.study.feeder_loading_critical_mw = 12.0
    settings.study.feeder_loading_severe_mw = 15.0
    p = _study_project(manager, added_kw=6000)          # ۱۲.۵ MW
    ctx = feeder_loading_context(p, settings, p.feeders[0])
    assert ctx["feeder_total_load_mw"] == pytest.approx(12.5)
    assert ctx["feeder_total_ge_critical"] is True       # ۱۲.۵ ≥ ۱۲
    assert ctx["feeder_total_ge_severe"] is False        # ۱۲.۵ < ۱۵


# ===========================================================================
# ۳) کلید On/Off ورودی‌ها
# ===========================================================================
def test_disabled_feeder_is_excluded_from_report(manager, tmp_path):
    from app.report.pipeline import build_sections
    from app.report.template_manager import TemplateManager
    from app.rules.rule_engine import RuleEngine

    p = manager.project
    p.feeders.append(Feeder(name="فیدر ۲۰۲", peak_load_mw=4.0, capacity_mw=8.0,
                            max_current_a=400, peak_year=1403))
    p.feeders[1].enabled = False
    report = build_sections(p, manager.settings, TemplateManager(), RuleEngine(),
                            Path(tmp_path) / "charts",
                            image_resolver=manager.image_path)
    text = "\n".join(block.text for sec in report.sections for block in sec.blocks
                     if getattr(block, "text", ""))
    assert "فیدر ۱۰۱" in text
    assert "فیدر ۲۰۲" not in text


def test_disabled_rows_are_skipped_in_validation_and_calculations(manager):
    from app.core.calculations import build_project_context
    from app.core.validation import validate_project

    p = manager.project
    p.feeders.append(Feeder(name="فیدر خاموش", peak_load_mw=None, capacity_mw=None))
    p.feeders[1].enabled = False
    ctx = build_project_context(p, manager.settings)
    assert ctx["n_feeders"] == 1                      # فیدر خاموش شمرده نمی‌شود
    items = validate_project(p, manager.settings)
    assert not any("فیدر خاموش" in i.message for i in items)


def test_disabled_image_is_not_emitted(app, manager, tmp_path):
    from pathlib import Path as _P
    src = _P(tmp_path) / "fig.png"
    src.write_bytes(_fig_png_bytes())
    assert manager.import_image(str(src), "شکل خاموش", "other") is True
    manager.project.images[0].enabled = False
    from app.report.pipeline import build_sections
    from app.report.template_manager import TemplateManager
    from app.rules.rule_engine import RuleEngine
    report = build_sections(manager.project, manager.settings, TemplateManager(),
                            RuleEngine(), _P(tmp_path) / "charts",
                            image_resolver=manager.image_path)
    kinds = [type(b).__name__ for sec in report.sections for b in sec.blocks]
    assert "FigureBlock" not in kinds


def _fig_png_bytes() -> bytes:
    """یک PNG کوچک معتبر (۲×۲ پیکسل) برای تست‌های شکل‌ها."""
    import base64
    return base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGP8z8Dwn4GBgYGJAQ"
        b"oAABsCAQDJQ3ApAAAAAElFTkSuQmCC")


# ===========================================================================
# ۴) تصاویر: بخش، اولویت، کپشن مستقل، چند شکل برای یک بخش
# ===========================================================================
def test_image_metadata_roundtrip_and_report_order(app, manager, tmp_path):
    from app.core.report_sections import REPORT_SECTIONS
    from app.report.pipeline import build_sections
    from app.report.template_manager import TemplateManager

    src = Path(tmp_path) / "fig.png"
    src.write_bytes(_fig_png_bytes())
    assert manager.import_image(str(src), "شکل دوم", "other",
                                section_key="study_loading", order=20) is True
    assert manager.import_image(str(src), "شکل اول", "other",
                                section_key="study_loading", order=10,
                                caption="کپشن دستی من") is True

    p = manager.project
    assert [i.title for i in p.active_images] == ["شکل دوم", "شکل اول"]   # ترتیب ورود
    assert p.images[0].section_key == "study_loading"

    # ماندگاری
    manager.save()
    from app.core.project_manager import ProjectManager
    again = ProjectManager(AppSettings()).open_project(manager.project_dir)
    assert [(i.title, i.section_key, i.order, i.caption) for i in again.images] == [
        ("شکل دوم", "study_loading", 20, ""),
        ("شکل اول", "study_loading", 10, "کپشن دستی من")]

    # ترتیب درج: اولویت کمتر جلوتر + کپشن دستی
    from app.rules.rule_engine import RuleEngine as _RE
    report = build_sections(again, manager.settings, TemplateManager(),
                            _RE(), Path(tmp_path) / "charts2",
                            image_resolver=manager.image_path)
    sec = next(s for s in report.sections if s.key == "study_loading")
    caps = [b.caption for b in sec.blocks if type(b).__name__ == "FigureBlock"]
    assert caps and caps[0].endswith("کپشن دستی من")
    assert REPORT_SECTIONS[0][0] == "intro"        # فهرست بخش‌ها پایدار مانده است


def test_images_page_offers_section_order_caption(app, manager):
    from app.ui.images_page import ImagesPage

    page = ImagesPage(manager)
    assert page.cb_section.count() == 1 + 16       # «خودکار» + ۱۶ بخش گزارش
    assert page.sp_order.minimum() < 0 < page.sp_order.maximum()
    page.ed_caption.setPlainText("کپشن")
    assert page.ed_caption.toPlainText() == "کپشن"


def test_images_page_list_has_onoff_and_order_buttons(app, manager, tmp_path):
    from app.ui.images_page import ImagesPage

    src = Path(tmp_path) / "fig.png"
    src.write_bytes(_fig_png_bytes())
    manager.import_image(str(src), "شکل الف", "other", section_key="appendix")
    manager.import_image(str(src), "شکل ب", "other", section_key="appendix")
    page = ImagesPage(manager)
    page.refresh()
    assert page.list.count() == 2
    assert page.list.item(0).flags() & Qt.ItemIsUserCheckable
    page.list.setCurrentRow(1)
    page._move(-1)
    orders = sorted(i.order for i in manager.project.images)
    assert orders[0] < orders[1]


# ===========================================================================
# ۵) تنظیمات و سازگاری
# ===========================================================================
def test_settings_persist_loading_thresholds_and_sections(tmp_path, monkeypatch):
    import app.core.settings as settings_mod

    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", tmp_path / "settings.json")
    settings = AppSettings()
    settings.study.feeder_loading_critical_mw = 7.5
    settings.study.feeder_loading_severe_mw = 9.5
    settings.report_sections.study_loading = False
    assert settings.section_enabled("study_loading") is False
    settings.save()
    again = AppSettings.load()
    assert again.study.feeder_loading_critical_mw == pytest.approx(7.5)
    assert again.study.feeder_loading_severe_mw == pytest.approx(9.5)
    assert again.section_enabled("study_loading") is False


def test_old_project_json_still_loads(tmp_path):
    """پروژه‌های ۱.۱.x باید بدون خطا و با پیش‌فرض‌های روشن بارگذاری شوند."""
    import json

    from app.core.models import project_from_dict

    old = {
        "uid": "old1", "name": "پروژه قدیمی",
        "feeders": [{"uid": "f1", "name": "فیدر قدیمی", "peak_load_mw": 5.0,
                     "capacity_mw": 8.0}],
        "images": [{"uid": "i1", "file_name": "a.png", "title": "شکل قدیمی",
                    "kind": "other"}],
        "demand": {"without_coincidence_kw": 1000, "with_coincidence_kw": 1000},
    }
    p = project_from_dict(json.loads(json.dumps(old)))
    assert p.feeders[0].enabled is True and len(p.active_feeders) == 1
    assert p.images[0].section_key == "" and p.images[0].order == 0
    assert p.images[0].enabled is True and p.demand.enabled is True
    assert p.neighbor_feeders == []


def test_demo_project_still_opens():
    from app.core.project_manager import ProjectManager

    demo = Path(__file__).resolve().parents[2] / "demo-project" / "پروژه_نمونه_مطالعه"
    if not demo.exists():
        pytest.skip("پروژه نمونه در این محیط موجود نیست")
    project = ProjectManager(AppSettings()).open_project(demo)
    assert project.feeders and project.active_feeders


# ===========================================================================
# ۶) جدول شبیه‌اکسل در صفحه‌های واقعی برنامه
# ===========================================================================
def _study_page(manager):
    from app.ui.study_page import StudyPage

    page = StudyPage(manager, manager.settings)
    page.show()
    page.refresh()
    QApplication.processEvents()
    return page


def _key(table, key, modifiers=Qt.NoModifier):
    ev = QKeyEvent(QKeyEvent.KeyPress, key, modifiers)
    QApplication.sendEvent(table, ev)


def test_study_table_delete_clears_cell_and_model(app, manager):
    """Delete محتوای خانه‌های انتخاب‌شده را پاک می‌کند و مدل هم به‌روز می‌شود."""
    from app.core.models import SubstationCandidate

    manager.project.nearby_substations = [
        SubstationCandidate(name="شهرک", distance_km=4.0, transformer_capacity_mva=40.0)]
    page = _study_page(manager)
    t = page.tbl_substations
    assert t.rowCount() == 1
    assert t.item(0, 3).text() == "4"            # ستون ۰ = کلید On/Off
    t.setCurrentCell(0, 3)                       # انتخاب خانهٔ «فاصله km»
    _key(t, Qt.Key_Delete)
    QApplication.processEvents()
    assert t.item(0, 3).text() == ""
    manager.project.nearby_substations = [page._row_to_substation(0)]
    assert manager.project.nearby_substations[0].distance_km is None    # پاک شد، صفر نشد


def test_study_table_paste_from_excel_block(app, manager):
    """چسباندن بلوک کپی‌شده از Excel در جدول ایستگاه‌ها."""
    from PySide6.QtCore import QMimeData
    manager.project.nearby_substations = []
    page = _study_page(manager)
    t = page.tbl_substations
    t.insertRow(0)
    t.insertRow(1)
    data = QMimeData()
    data.setText("پست الف\tدفتر ۱\t1.5\t40\r\nپست ب\tدفتر ۲\t2.5\t30")
    QApplication.clipboard().setMimeData(data)
    t.setCurrentCell(0, 1)                       # ستون «نام ایستگاه»
    _key(t, Qt.Key_V, Qt.ControlModifier)
    QApplication.processEvents()
    assert t.item(0, 1).text() == "پست الف" and t.item(1, 4).text() == "30"
    page.save_to_project()
    assert [(s.name, s.transformer_capacity_mva)
            for s in manager.project.nearby_substations] == [("پست الف", 40.0), ("پست ب", 30.0)]


def test_study_table_enter_adds_row_and_saves(app, manager):
    """Enter در آخرین ردیف یک ردیف تازه می‌سازد (رفتار اکسل)."""
    manager.project.coincident_demands = []
    page = _study_page(manager)
    t = page.tbl_coincident
    t.insertRow(0)
    t.setCurrentCell(0, 1)
    _key(t, Qt.Key_Return)
    QApplication.processEvents()
    assert t.rowCount() == 2
    assert t.item(1, 0) is not None              # ردیف تازه ستون «در گزارش» دارد


def test_study_page_onoff_column_is_round_tripped(app, manager):
    """ستون «در گزارش (On/Off)» در پروژه ذخیره و بازخوانی می‌شود."""
    from app.core.models import LineCandidate
    manager.project.nearby_lines = [LineCandidate(name="خط ۱", peak_mva=3.5)]
    page = _study_page(manager)
    t = page.tbl_lines
    t.item(0, 0).setCheckState(Qt.Unchecked)
    page.save_to_project()
    assert manager.project.nearby_lines[0].enabled is False
    assert manager.project.active_lines == []
    # بازخوانی صفحه: کلید خاموش همان‌طور می‌ماند
    page.refresh()
    assert page._enabled(page.tbl_lines, 0) is False


def test_study_page_neighbor_tab_roundtrip(app, manager):
    """تب ۶ — فیدرهای همجوار (کاندید بازآرایی) در مدل پروژه ذخیره می‌شود."""
    page = _study_page(manager)
    t = page.tbl_neighbors
    t.insertRow(0)
    t.setItem(0, 0, page._onoff_item(True))
    t.setItem(0, 1, QTableWidgetItem("فیدر همجوار ۹"))
    t.setItem(0, 4, QTableWidgetItem("3.0"))     # پیک بار MW
    t.setItem(0, 8, QTableWidgetItem("1.2"))     # فاصله km
    t.setItem(0, 9, QTableWidgetItem("1.5"))     # بار قابل انتقال
    page.save_to_project()
    nf = manager.project.neighbor_feeders[0]
    assert (nf.name, nf.peak_load_mw, nf.distance_km, nf.transferable_mw) == \
        ("فیدر همجوار ۹", 3.0, 1.2, 1.5)
    assert nf.free_capacity_mw() is None         # ظرفیت ثبت نشده → None (نه صفر)


def test_demand_onoff_toggle_removes_study_demand_section(app, manager):
    from app.report.pipeline import build_sections
    from app.report.template_manager import TemplateManager
    from app.rules.rule_engine import RuleEngine

    p = manager.project
    p.demand.without_coincidence_kw = 1000.0
    p.demand.with_coincidence_kw = 900.0
    p.demand.enabled = False
    from pathlib import Path as _P
    import tempfile
    charts = _P(tempfile.mkdtemp(dir=str(tmp_path := __import__("tempfile").mkdtemp())))
    report = build_sections(p, manager.settings, TemplateManager(), RuleEngine(), charts)
    assert "study_demand" not in [s.key for s in report.sections]
    p.demand.enabled = True
    report = build_sections(p, manager.settings, TemplateManager(), RuleEngine(), charts)
    assert "study_demand" in [s.key for s in report.sections]


def test_disabled_study_row_is_excluded_from_report(app, manager, tmp_path):
    from app.core.models import SubstationCandidate
    from app.report.pipeline import build_sections
    from app.report.template_manager import TemplateManager
    from app.report.sections import TableSpec
    from app.rules.rule_engine import RuleEngine

    p = manager.project
    p.demand.with_coincidence_kw = 1200.0
    p.nearby_substations = [
        SubstationCandidate(name="پست فعال", distance_km=3.0),
        SubstationCandidate(name="پست خاموش", distance_km=5.0, enabled=False)]
    report = build_sections(p, manager.settings, TemplateManager(), RuleEngine(),
                            tmp_path / "charts")
    rows = "\n".join(cell for s in report.sections for b in s.blocks
                     if isinstance(b, TableSpec) for r in b.body_rows for cell in r)
    assert "پست فعال" in rows and "پست خاموش" not in rows


def test_disabled_report_section_is_not_generated(app, manager, tmp_path):
    from app.report.pipeline import build_sections
    from app.report.template_manager import TemplateManager
    from app.rules.rule_engine import RuleEngine

    settings = manager.settings
    settings.report_sections.study_economics = False
    manager.project.demand.with_coincidence_kw = 1200.0
    report = build_sections(manager.project, settings, TemplateManager(), RuleEngine(),
                            tmp_path / "charts")
    keys = [s.key for s in report.sections]
    assert "study_economics" not in keys
    settings.report_sections.study_economics = True


# ===========================================================================
# ۷) صفحه تصاویر و صفحه تنظیمات
# ===========================================================================
def test_images_page_orders_figures_per_section(app, manager, tmp_path):
    from app.ui.images_page import ImagesPage, AUTO_SECTION

    src = Path(tmp_path) / "fig.png"
    src.write_bytes(_fig_png_bytes())
    manager.import_image(str(src), "شکل مقدمه", "location")
    manager.import_image(str(src), "شکل دوم مقدمه", "location")
    manager.import_image(str(src), "شکل پیش‌بینی", "forecast")
    page = ImagesPage(manager)
    page.refresh()
    assert page.cb_section.count() == len([AUTO_SECTION]) + 16
    # شکل‌های خودکار بر پایهٔ «نوع» مرتب می‌شوند: location→intro، forecast→forecast
    assert "مقدمه" in page.list.item(0).text()
    # انتخاب شکل دوم همان بخش و بردن آن به بالا (ترتیب/اولویت)
    page.list.setCurrentRow(1)
    page._move(-1)
    images = manager.project.images
    assert images[1].order < images[0].order
    page.list.setCurrentRow(0)
    current = page.current_item
    page.cb_section.setCurrentIndex(page.cb_section.findData("study_scenarios"))
    page.ed_caption.setPlainText("کپشن مستقل شکل")
    page.sp_order.setValue(5)
    assert current.section_key == "study_scenarios"
    assert current.caption == "کپشن مستقل شکل" and current.order == 5


def test_images_page_can_define_multiple_figures_for_one_section(app, manager, tmp_path):
    from app.core.report_sections import REPORT_SECTIONS  # noqa: F401  (فهرست بخش‌ها)
    from app.ui.images_page import ImagesPage

    src = Path(tmp_path) / "fig.png"
    src.write_bytes(_fig_png_bytes())
    manager.import_image(str(src), "شکل ۱", "other", section_key="appendix", order=10)
    manager.import_image(str(src), "شکل ۲", "other", section_key="appendix", order=20)
    manager.import_image(str(src), "شکل ۳", "other", section_key="appendix", order=30)
    page = ImagesPage(manager)
    page.refresh()
    same_section = [i for i in manager.project.images if i.section_key == "appendix"]
    assert len(same_section) == 3               # چند شکل برای یک آیتم/بخش
    assert [i.order for i in same_section] == [10, 20, 30]
    assert page.list.count() == 3
    assert "پیوست" in page.list.item(0).text()


def test_settings_page_saves_loading_thresholds_and_sections(app, manager, monkeypatch):
    from app.ui.settings_page import SettingsPage

    settings = AppSettings()
    monkeypatch.setattr(settings.__class__, "save", lambda self: None)
    page = SettingsPage(settings)
    assert page.opt_ld_crit.value() == 7.0
    assert page.opt_ld_sev.value() == 8.0
    page.opt_ld_crit.setValue(7.5)
    page.opt_ld_sev.setValue(9.0)
    assert "study_loading" in page.chk_sections
    page.chk_sections["study_loading"].setChecked(False)
    page.chk_sections["study_economics"].setChecked(False)
    page.save()
    assert settings.study.feeder_loading_critical_mw == 7.5
    assert settings.study.feeder_loading_severe_mw == 9.0
    assert settings.report_sections.study_loading is False
    assert settings.report_sections.study_economics is False
    assert settings.section_enabled("study_loading") is False
    # بازنشانی: همهٔ بخش‌ها روشن و آستانه‌ها به پیش‌فرض برمی‌گردند
    page._reset()
    assert all(chk.isChecked() for chk in page.chk_sections.values())


# ===========================================================================
# ۸) جدول پیش‌بینی (بخش ۲) — کلید «در گزارش» و اثر آن بر محاسبه/گزارش
# ===========================================================================
def _feeder_page(manager):
    from app.ui.feeder_page import FeederPage

    page = FeederPage(manager, manager.settings)
    page.resize(1200, 900)
    page.show()
    page.refresh()
    page.list.setCurrentRow(0)              # انتخاب فیدر ⇒ current پر می‌شود
    QApplication.processEvents()
    return page


def _fill_fc(page, rows):
    """ردیف‌های پیش‌بینی: ستون ۰ = On/Off، ستون ۱ = سال، ستون ۲ = پیک (MW)."""
    t = page.tbl_fc_points
    t.setRowCount(0)
    for y, v in rows:
        r = t.rowCount()
        t.insertRow(r)
        t.setItem(r, 1, QTableWidgetItem(str(y)))
        t.setItem(r, 2, QTableWidgetItem(str(v)))


def test_forecast_table_has_onoff_column(app, manager, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    page = _feeder_page(manager)
    head = [page.tbl_fc_points.horizontalHeaderItem(c).text()
            for c in range(page.tbl_fc_points.columnCount())]
    assert head[0] == "در گزارش (On/Off)"
    assert head[1:] == ["سال", "پیک پیش‌بینی (MW)"]
    # نگاشت بر مبنای نام ستون: جابه‌جایی ستون‌ها داده را عوض نمی‌کند
    page.tbl_fc_points.horizontalHeader().moveSection(1, 2)
    _fill_fc(page, [(1404, 3.1), (1405, 3.4)])
    assert page._fc_rows() == [(1404, 3.1), (1405, 3.4)]


def test_disabled_forecast_row_excluded_from_manual_forecast(app, manager, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    page = _feeder_page(manager)
    _fill_fc(page, [(1404, 3.1), (1405, 3.4), (1406, 3.7)])
    page._set_onoff(page.tbl_fc_points, 1, False)      # سال ۱۴۰۵ خاموش
    page._manual_forecast()

    f = manager.project.feeders[0]
    assert f.forecast.method == "manual"
    # محاسبه فقط روی سطرهای روشن انجام می‌شود…
    assert [(p.year, p.value_mw) for p in f.forecast.points] == [(1404, 3.1), (1406, 3.7)]
    # …اما مقدار سطر خاموش در مدل حفظ می‌شود (حذف نمی‌شود)
    assert [(p.year, p.value_mw, p.enabled) for p in f.manual_forecast] == [
        (1404, 3.1, True), (1405, 3.4, False), (1406, 3.7, True)]
    assert [p.year for p in f.active_forecast_points] == [1404, 1406]


def test_all_forecast_rows_off_blocks_manual_registration(app, manager, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warnings = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warnings.append(a) or QMessageBox.Ok))
    page = _feeder_page(manager)
    _fill_fc(page, [(1404, 3.1), (1405, 3.4)])
    for r in range(page.tbl_fc_points.rowCount()):
        page._set_onoff(page.tbl_fc_points, r, False)
    page._manual_forecast()

    f = manager.project.feeders[0]
    assert f.forecast.method != "manual"        # هیچ پیش‌بینی‌ای ساخته نشد
    assert warnings and "غیرفعال" in warnings[0][2]
    assert [(p.year, p.enabled) for p in f.manual_forecast] == [(1404, False), (1405, False)]


def test_forecast_flag_survives_reload_and_report_note(app, manager, tmp_path):
    from app.core import forecast as fc_mod
    from app.report.pipeline import build_sections
    from app.report.template_manager import TemplateManager
    from app.rules.rule_engine import RuleEngine

    f = manager.project.feeders[0]
    f.forecast = fc_mod.linear_forecast([1400, 1401, 1402, 1403],
                                        [2.0, 2.2, 2.4, 2.6], 5, 3)
    f.forecast.points[1].enabled = False        # یک سال پیش‌بینی خاموش
    page = _feeder_page(manager)
    assert page.tbl_fc_points.rowCount() == len(f.forecast.points)
    assert page._onoff_state(page.tbl_fc_points, 1) is False   # وضعیت در جدول بازتاب می‌یابد
    # نگاشت با عنوان ستون: مقدار ستون‌ها جابه‌جا نشده است
    assert int(page._cell_num(page.tbl_fc_points, 0, 1)) == f.forecast.points[0].year

    report = build_sections(manager.project, manager.settings, TemplateManager(),
                            RuleEngine(), Path(tmp_path) / "charts",
                            image_resolver=manager.image_path)
    text = "\n".join(block.text for sec in report.sections for block in sec.blocks
                     if getattr(block, "text", ""))
    assert "غیرفعال (Off)" in text               # یادداشت شفاف در گزارش
    assert len(manager.project.feeders[0].active_forecast_points) == \
        len(f.forecast.points) - 1
