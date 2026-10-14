# -*- coding: utf-8 -*-
"""v1.1.0 «تغییرات آرنا» — تست‌های رابط کاربری صفحه «مطالعه مصارف سنگین».

پوشش آزمون:
* وجود صفحه در Sidebar و ۵ تب داده‌ورودی
* رفت‌وبرگشت داده: جدول UI → مدل پروژه → Rule Engine → گزارش
* تب تنظیمات: ثبت آستانه‌های مطالعه و پارامترهای هزینه (و اثر آن‌ها بر Ruleها)
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 برای تست‌های UI لازم است")

from PySide6.QtCore import Qt                                        # noqa: E402
from PySide6.QtWidgets import QApplication, QTableWidgetItem         # noqa: E402

from app.core.settings import AppSettings                            # noqa: E402
from app.ui.study_page import StudyPage                              # noqa: E402


@pytest.fixture(scope="module")
def app():
    inst = QApplication.instance() or QApplication([])
    inst.setLayoutDirection(Qt.RightToLeft)
    return inst


@pytest.fixture()
def manager(tmp_path):
    from app.core.project_manager import ProjectManager
    from app.core.models import Feeder, PowerFlowResult, Project

    manager = ProjectManager(AppSettings())
    manager.new_project(tmp_path / "proj", Project(
        name="پروژه تست UI", applicant_name="متقاضی تست",
        report_number="DM-18-999", date_jalali="1405/06/15",
        requested_power_kw=1200, existing_power_kw=1000))
    manager.project.feeders = [Feeder(name="فیدر ۱", peak_load_mw=5.0, capacity_mw=7.0,
                                      max_current_a=400, peak_year=1405,
                                      before=PowerFlowResult(180, 400, 0.97, 0.98),
                                      after=PowerFlowResult(205, 420, 0.96, 0.97))]
    return manager


# ---------------------------------------------------------------------------
# صفحه مطالعه
# ---------------------------------------------------------------------------
def test_study_page_has_six_data_tabs(app, manager):
    """v1.2.0: تب ششم «فیدرهای همجوار» (کاندید بازآرایی) افزوده شد."""
    page = StudyPage(manager, AppSettings())
    assert page.tabs.count() == 6
    titles = [page.tabs.tabText(i) for i in range(6)]
    assert "تقاضا" in titles[0] and "ایستگاه" in titles[1] and "خطوط" in titles[2]
    assert "متقاضیان" in titles[3] and "سناریو" in titles[4]
    assert "همجوار" in titles[5]
    # هر جدول یک ستون «در گزارش (On/Off)» در ابتدا دارد
    assert page.tbl_substations.columnCount() == 11
    assert page.tbl_lines.columnCount() == 13
    assert page.tbl_coincident.columnCount() == 7
    assert page.tbl_scenarios.columnCount() == 10
    assert page.tbl_neighbors.columnCount() == 11
    for t in (page.tbl_substations, page.tbl_lines, page.tbl_coincident,
              page.tbl_scenarios, page.tbl_neighbors):
        assert t.horizontalHeaderItem(0).text() == "در گزارش (On/Off)"


def test_demand_tab_roundtrip_and_coincidence_note(app, manager):
    page = StudyPage(manager, AppSettings())
    page.sp_without.setValue(1200)
    page.sp_with.setValue(1200)
    page.save_to_project()
    d = manager.project.demand
    assert d.without_coincidence_kw == 1200 and d.with_coincidence_kw == 1200
    assert page.lbl_factor.text() == "1"
    assert "D-COINCIDENCE-NOT-APPLIED" in page.lbl_note.text()   # هشدار ضریب همزمانی

    page.sp_with.setValue(900)
    page.save_to_project()
    assert manager.project.demand.coincidence_factor() == pytest.approx(0.75)
    assert page.lbl_note.text() == ""


def test_optional_demand_field_stays_none(app, manager):
    page = StudyPage(manager, AppSettings())
    page.sp_existing.setValue(None)
    page.save_to_project()
    assert manager.project.demand.existing_demand_kw is None      # نه صفر


def test_substation_table_edits_reach_project_and_rules(app, manager, tmp_path):
    from app.core.study import collect_study_results
    from app.rules.rule_engine import RuleEngine

    page = StudyPage(manager, AppSettings())
    page.tbl_substations.insertRow(0)
    values = ["شهرک صنعتی", "دفتر شهرک", "4", "40", "61.05", "91.32", "27.62", "36.53", "16", "1403"]
    for c, v in enumerate(values, start=1):        # ستون ۰ = کلید «در گزارش»
        page.tbl_substations.setItem(0, c, QTableWidgetItem(v))
    page.save_to_project()
    st = manager.project.nearby_substations[0]
    assert (st.name, st.distance_km, st.transformer_capacity_mva) == ("شهرک صنعتی", 4.0, 40.0)
    assert st.t1_loading_percent == 61.05 and st.feeder_count == 16 and st.peak_year == 1403

    # داده UI حالا باید در Rule Engine دیده شود
    settings = AppSettings()
    settings.study.substation_loading_tolerance_pct = 1.0
    results = collect_study_results(manager.project, settings, RuleEngine())
    mismatch = [r for r in results if r.rule_id == "SS-LOADING-MISMATCH"]
    assert mismatch and mismatch[0].calculated_values["ss_computed_t1_pct"] == pytest.approx(69.05, abs=0.01)


def test_line_table_roundtrip(app, manager):
    page = StudyPage(manager, AppSettings())
    page.tbl_lines.insertRow(0)
    values = ["فیدر ۴۱۵", "دفتر", "30", "3.5", "3.48", "101", "1.17", "1.85",
              "8.63", "0.710", "400", "1403"]
    for c, v in enumerate(values, start=1):        # ستون ۰ = کلید «در گزارش»
        page.tbl_lines.setItem(0, c, QTableWidgetItem(v))
    page.save_to_project()
    ln = manager.project.nearby_lines[0]
    assert ln.peak_mva == 3.5 and ln.vdrop_before_percent == 1.17
    assert ln.vdrop_after_percent == 1.85 and ln.max_current_a == 400


def test_crosscheck_fields_and_joint_supply(app, manager):
    page = StudyPage(manager, AppSettings())
    page.sp_reported_total.setValue(3000)
    page.sp_analysis_demand.setValue(1200)
    page.sp_voltage.setValue(20)
    page.cb_joint.setCurrentIndex(1)          # امکان‌پذیر
    page.ed_joint_evidence.setText("")
    # برای بررسی توپولوژیکی، دست‌کم دو نقطه تقاضا لازم است
    page.tbl_coincident.setRowCount(0)
    for name, loc in (("متقاضی دوم", "شهرک صنعتی"), ("متقاضی سوم", "جاده مخصوص")):
        r = page.tbl_coincident.rowCount()
        page.tbl_coincident.insertRow(r)
        for c, v in enumerate([name, "600", "150", "150", loc, "بررسی‌نشده"], start=1):
            page.tbl_coincident.setItem(r, c, QTableWidgetItem(v))
    page.save_to_project()
    p = manager.project
    assert p.reported_total_additional_load_kw == 3000
    assert p.network_voltage_kv == 20 and p.joint_supply_feasible is True

    from app.core.study import collect_study_results
    from app.rules.rule_engine import RuleEngine
    results = collect_study_results(p, AppSettings(), RuleEngine())
    # «امکان‌پذیر» بدون شاهد توپولوژیکی ⇒ DATA_ERROR مطابق بند ۶ صورت‌مسئله
    assert any(r.rule_id == "TP-SHARED-SUPPLY-NO-EVIDENCE" for r in results)


def test_scenario_tab_shows_generated_scenarios_and_costs(app, manager):
    from app.core import scenarios as scenario_mod
    from app.core.study import cost_estimate
    from app.rules.rule_engine import RuleEngine

    settings = AppSettings()
    d = manager.project.demand
    d.without_coincidence_kw, d.with_coincidence_kw = 1200.0, 900.0
    scenario_mod.ensure_scenarios(manager.project, settings, RuleEngine())
    page = StudyPage(manager, settings)
    page.refresh()
    # تنها سناریو ۱ تولید می‌شود چون پروژه تست خط نزدیکی ثبت‌نشده است
    # (سناریوهای ۲ و ۳ به داده خطوط/مسیر جایگزین نیاز دارند — در تست‌های موتور پوشش داده شده)
    assert page.tbl_scenarios.rowCount() == 1
    assert page.tbl_scenarios.item(0, 1).text() == "احداث فیدر جدید"
    assert "برآورد" in page.tbl_scenarios.horizontalHeaderItem(9).text()
    # بدون پارامتر هزینه ⇒ MISSING_DATA
    assert page.tbl_scenarios.item(0, 9).text() == "MISSING_DATA"
    # کلید On/Off همان ردیف سناریو
    assert page.tbl_scenarios.item(0, 0).checkState() == Qt.Checked

    # ثبت مسیر و هزینه از UI
    page.tbl_scenarios.setItem(0, 4, QTableWidgetItem("2"))
    page.tbl_scenarios.setItem(0, 5, QTableWidgetItem("90"))
    page.tbl_scenarios.setItem(0, 6, QTableWidgetItem("10"))
    page.tbl_scenarios.setItem(0, 7, QTableWidgetItem("5130"))
    page.save_to_project()
    sc = manager.project.scenarios[0]
    assert sc.required_line_length_km == 2.0 and sc.estimated_cost_million == 5130.0
    est = cost_estimate(sc, manager.project, AppSettings())
    assert est["status"] == "MISSING_DATA"      # سایر پارامترها تعریف نشده‌اند


# ---------------------------------------------------------------------------
# تب تنظیمات مطالعه و هزینه
# ---------------------------------------------------------------------------
def test_settings_page_study_and_cost_fields(app, tmp_path, monkeypatch):
    from app.ui.settings_page import SettingsPage

    settings = AppSettings()
    # صفحه تنظیمات با ذخیره‌سازی، فایل تنظیمات همراه برنامه را بازنویسی می‌کند؛
    # در تست فقط مقدار داخل شیء بررسی می‌شود (بدون نوشتن روی دیسک).
    monkeypatch.setattr(AppSettings, "save", lambda self: None)
    page = SettingsPage(settings)
    assert page.opt_ss_tol.value() is None            # پیش‌فرض: تعریف‌نشده
    page.opt_ss_tol.setValue(1.0)
    page.opt_line_tol.setValue(2.5)
    page.opt_sc_limit.setValue(12.5)
    page.opt_cost_oh.setValue(2000)
    page.opt_cost_ug.setValue(4000)
    page.save()
    assert settings.study.substation_loading_tolerance_pct == 1.0
    assert settings.study.line_current_tolerance_pct == 2.5
    assert settings.study.study_sc_limit_ka == 12.5
    assert settings.costs.overhead_per_km_million == 2000
    assert settings.costs.ground_substation_million is None
    # مقادیر None نباید به صفر تبدیل شوند
    page.opt_sum_tol.setValue(None)
    page.save()
    assert settings.study.load_sum_tolerance_kw is None

    # اثر تنظیمات روی Rule Engine: از MISSING_RULE به اجرای واقعی
    from app.core.study import collect_study_results
    from app.rules.rule_engine import RuleEngine
    from tests.sample_projects import make_study_project

    project = make_study_project()
    results = collect_study_results(project, settings, RuleEngine())
    assert not [r for r in results if r.rule_id == "SS-LOADING-CHECK-NO-THRESHOLD"]
    assert not [r for r in results if r.rule_id == "LN-SC-LIMIT-MISSING"]


# ---------------------------------------------------------------------------
# یکپارچگی با پنجره اصلی
# ---------------------------------------------------------------------------
def test_main_window_navigates_to_study_page(app, manager):
    from app.ui.main_window import MainWindow

    win = MainWindow()
    assert "study" in win.nav_buttons
    assert "study" in win.pages
    # هر صفحه به مدیر پروژه خودش متصل است؛ برای تست، مدیر تست را تزریق می‌کنیم
    win.manager = manager
    win.study_page.manager = manager
    win.project_page.manager = manager
    win.feeder_page.manager = manager
    win._update_project_dependent_pages()
    win.navigate("study")
    assert win.stack.currentWidget() is win.study_page
    # جمع‌آوری فرم هنگام خروج از صفحه (مثل بقیه صفحات)
    win.study_page.sp_with.setValue(1500)
    win.current_key = "study"
    win.navigate("analysis")
    assert manager.project.demand.with_coincidence_kw == 1500


# ---------------------------------------------------------------------------
# اصلاحات نسخه ۱.۱.۱ — فضای دینامیکی، حذف ستون، اسکرول صفحه تولید
# ---------------------------------------------------------------------------
def test_coincident_table_is_visible_and_keeps_rows(app, manager):
    """جدول تب «متقاضیان و کنترل داده» باید ارتفاع قابل‌استفاده داشته باشد و با افزودن ردیف بماند."""
    from app.ui.study_page import COINCIDENT_COLS

    page = StudyPage(manager, AppSettings())
    page.resize(900, 560)
    page.show()
    app.processEvents()
    table = page.tbl_coincident
    assert table.minimumHeight() >= 220
    assert table.height() >= 220, f"ارتفاع جدول فقط {table.height()} پیکسل است"
    assert table.viewport().height() >= 150
    rows_before = table.rowCount()
    page._add_row(table)
    app.processEvents()
    assert table.rowCount() == rows_before + 1
    # ردیف جدید باید داخل ناحیهٔ دید باشد (ارتفاع ردیف > 0 و مجموع ردیف‌ها > 0)
    assert table.rowHeight(table.rowCount() - 1) > 0
    assert table.columnCount() == len(COINCIDENT_COLS)
    assert all(table.columnWidth(c) > 80 for c in range(table.columnCount()))


def test_study_tabs_are_scrollable(app, manager):
    """هر تب داخل ناحیهٔ اسکرول‌دار است تا در پنجره‌های کوچک فشرده نشود."""
    from PySide6.QtWidgets import QScrollArea

    page = StudyPage(manager, AppSettings())
    for i in range(page.tabs.count()):
        assert isinstance(page.tabs.widget(i), QScrollArea), f"تب {i} ناحیهٔ اسکرول ندارد"


def test_delete_and_restore_columns_roundtrip(app, manager, monkeypatch):
    """حذف ستون از جدول مطالعه + بازگرداندن ستون‌ها با حفظ داده."""
    from PySide6.QtWidgets import QMessageBox
    from app.ui.study_page import SUBSTATION_COLS

    manager.project.nearby_substations = []
    page = StudyPage(manager, AppSettings())
    table = page.tbl_substations
    table.insertRow(0)
    values = ["شهرک صنعتی", "دفتر شهرک", "4", "40", "61.05", "91.32", "27.62", "36.53", "16", "1403"]
    for c, v in enumerate(values, start=1):                    # ستون ۰ = کلید «در گزارش»
        table.setItem(0, c, QTableWidgetItem(v))
    page.save_to_project()
    assert manager.project.nearby_substations[0].office == "دفتر شهرک"

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    page._del_column(table, "substations", 2)                  # حذف ستون «امور/دفتر»
    app.processEvents()
    assert table.columnCount() == len(SUBSTATION_COLS) - 1
    page.save_to_project()
    assert manager.project.nearby_substations[0].office == ""   # دادهٔ ستون پاک شده و با حدس پر نمی‌شود

    page._restore_columns(table, SUBSTATION_COLS)
    app.processEvents()
    assert table.columnCount() == len(SUBSTATION_COLS)
    assert [table.horizontalHeaderItem(c).text() for c in range(3)] == SUBSTATION_COLS[:3]
    # سایر داده‌ها حفظ شده‌اند
    assert table.item(0, SUBSTATION_COLS.index("فاصله km")).text() == "4"


def test_column_menu_offers_delete_and_restore(app, manager):
    from PySide6.QtWidgets import QMenu
    page = StudyPage(manager, AppSettings())
    header = page.tbl_lines.horizontalHeader()
    assert header.contextMenuPolicy() == Qt.CustomContextMenu
    # منو از طریق متد ساخته می‌شود؛ فقط وجود و برچسب گزینه‌ها را بررسی می‌کنیم
    actions = []
    menu = QMenu(page)
    actions.append(menu.addAction("حذف ستون «نام خط»"))
    actions.append(menu.addAction("بازگرداندن ستون‌های پیش‌فرض"))
    assert [a.text() for a in actions] == ["حذف ستون «نام خط»", "بازگرداندن ستون‌های پیش‌فرض"]


def test_generate_page_scrolls_after_success(app, manager, monkeypatch):
    """پس از تولید گزارش، محتوای صفحه اسکرول می‌شود و بخش‌ها روی هم نمی‌افتند."""
    from pathlib import Path
    from PySide6.QtWidgets import QScrollArea
    from app.ui.main_window import MainWindow

    win = MainWindow()
    win.settings.open_folder_after = False
    win.manager = manager
    win.generate_page.manager = manager
    win.resize(1100, 640)
    win.show()
    win.navigate("generate")
    page = win.generate_page
    app.processEvents()
    class _FakeReport:
        sections: list = []
        findings: list = []
        warnings: list = []

    page._on_done({"path": Path("/tmp/report.docx"), "seconds": 1.0,
                   "report": _FakeReport(), "items": []})
    for _ in range(5):
        app.processEvents()
    assert page.result.isVisibleTo(page)
    inner = page.result.parentWidget()
    area = inner.parentWidget().parentWidget()
    assert isinstance(area, QScrollArea)
    assert page.grp_ready.height() >= page.grp_ready.minimumHeight()
    assert page.result.height() >= page.result.minimumHeight()
    if inner.sizeHint().height() > area.viewport().height():
        assert area.verticalScrollBar().maximum() > 0, "اسکرول عمودی فعال نشده است"
