# -*- coding: utf-8 -*-
"""v1.1.1 «تغییرات آرنا» — جداسازی «پروفیل بار» از «پیش‌بینی بار».

قواعد آزمون‌شده:
* پیش‌بینی بر پایه **پیک سال‌های گذشته** که کاربر وارد می‌کند محاسبه می‌شود،
  نه از پروفیل بار یک سال.
* «داده واقعی» و «پیش‌بینی» دو بخش مستقل‌اند: ثبت پیش‌بینی دستی، داده واقعی را تغییر نمی‌دهد
  و بالعکس.
* در نبود داده کافی هیچ مقدار جانشینی (مثلاً از پروفیل) ساخته نمی‌شود.
* دادهٔ پیک سالانه در `project.json` ذخیره و بازخوانی می‌شود.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6", reason="PySide6 برای تست‌های UI لازم است")

from PySide6.QtCore import Qt                                        # noqa: E402
from PySide6.QtWidgets import (QApplication, QMessageBox,            # noqa: E402
                               QTableWidget, QTableWidgetItem)

from app.core import forecast as fc_mod                              # noqa: E402
from app.core.models import Feeder, ForecastPoint, PowerFlowResult, Project  # noqa: E402
from app.core.settings import AppSettings                            # noqa: E402


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
        name="پروژه پیش‌بینی", applicant_name="متقاضی", report_number="DM-18-777",
        date_jalali="1405/06/15", requested_power_kw=1500, existing_power_kw=900))
    f = Feeder(name="فیدر ۱", substation="پست ۱", peak_load_mw=2.75, peak_year=1403,
               power_factor=0.93, peak_current_a=85, max_current_a=400, capacity_mw=7.0,
               before=PowerFlowResult(180, 400, 0.97, 0.98),
               after=PowerFlowResult(205, 420, 0.96, 0.97))
    m.project.feeders = [f]
    return m


@pytest.fixture()
def page(app, manager):
    from app.ui.feeder_page import FeederPage

    p = FeederPage(manager, AppSettings())
    p.show()
    p.refresh()
    p.show_section("profile")
    p.list.setCurrentRow(0)
    app.processEvents()
    return p


def _fill_peaks(page, rows, source="MANUAL", enabled=None):
    """پرکردن جدول «داده واقعی» — ستون ۰ = کلید On/Off، ۱ = سال، ۲ = پیک، ۳ = منبع."""
    t = page.tbl_peaks
    t.setRowCount(0)
    for i, (y, v) in enumerate(rows):
        r = t.rowCount()
        t.insertRow(r)
        t.setItem(r, 0, QTableWidgetItem(""))
        state = True if enabled is None else (i < len(enabled) and enabled[i])
        page._set_onoff(t, r, state)
        t.setItem(r, 1, QTableWidgetItem(str(y)))
        t.setItem(r, 2, QTableWidgetItem(str(v)))
        t.setItem(r, 3, QTableWidgetItem(source))
    page._peaks_changed()


# ---------------------------------------------------------------------------
# پیش‌بینی از دادهٔ واردشده (نه از پروفیل)
# ---------------------------------------------------------------------------
def test_forecast_uses_entered_peaks_not_load_profile(app, manager, page, monkeypatch):
    calls = []
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: calls.append(a)))
    # پروفیلی وارد نشده است
    assert manager.get_profile(page.current) is None

    _fill_peaks(page, [(1400, 2.0), (1401, 2.2), (1402, 2.4), (1403, 2.6)])
    page._auto_forecast()

    f = manager.project.feeders[0]
    assert [p.year for p in f.annual_peaks] == [1400, 1401, 1402, 1403]
    assert f.forecast.method == "regression"
    assert f.forecast.history_years == [1400, 1401, 1402, 1403]
    assert f.forecast.history_values == [2.0, 2.2, 2.4, 2.6]
    assert f.forecast.slope_mw_per_year == pytest.approx(0.2, abs=1e-6)
    assert [p.year for p in f.forecast.points][:2] == [1404, 1405]
    assert f.forecast.points[0].value_mw == pytest.approx(2.8, abs=0.01)
    # بخش ۲ جدول پیش‌بینی هم پر شده است
    assert page.tbl_fc_points.rowCount() == len(f.forecast.points)


def test_forecast_refuses_to_guess_without_enough_peaks(app, manager, page, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: warnings.append(a) or QMessageBox.Ok))
    _fill_peaks(page, [(1403, 2.6)])          # فقط یک سال — کمتر از حداقل داده لازم
    page._auto_forecast()

    f = manager.project.feeders[0]
    assert f.forecast.method == "none"        # هیچ پیش‌بینی ساخته نشد
    assert warnings, "پیام هشدار برای داده ناکافی نمایش داده نشد"
    assert "داده واقعی کافی نیست" in warnings[0][2]
    # هیچ استخراج خودکاری از پروفیل انجام نشده است
    assert f.annual_peaks == [ForecastPoint(year=1403, value_mw=2.6, source="MANUAL")]


# ---------------------------------------------------------------------------
# دو بخش مستقل: داده واقعی و پیش‌بینی
# ---------------------------------------------------------------------------
def test_manual_forecast_is_separate_from_actual_data(app, manager, page, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    _fill_peaks(page, [(1400, 2.0), (1401, 2.2), (1402, 2.4), (1403, 2.6)])

    page.cb_fc_method.setCurrentIndex(1)      # حالت دستی
    app.processEvents()
    assert page.btn_manual_fc.isVisibleTo(page)
    assert not page.btn_auto_forecast.isVisibleTo(page)
    assert page.tbl_fc_points.editTriggers() != QTableWidget.NoEditTriggers

    # کاربر بخش ۲ را پر می‌کند
    page.tbl_fc_points.setRowCount(0)
    # ستون ۰ = کلید «در گزارش» (On/Off) — سال/مقدار از ستون‌های ۱ و ۲
    for y, v in ((1404, 3.1), (1405, 3.4)):
        r = page.tbl_fc_points.rowCount()
        page.tbl_fc_points.insertRow(r)
        page.tbl_fc_points.setItem(r, 1, QTableWidgetItem(str(y)))
        page.tbl_fc_points.setItem(r, 2, QTableWidgetItem(str(v)))
    page._manual_forecast()

    f = manager.project.feeders[0]
    assert f.forecast.method == "manual"
    assert [(p.year, p.value_mw) for p in f.forecast.points] == [(1404, 3.1), (1405, 3.4)]
    assert [(p.year, p.value_mw) for p in f.manual_forecast] == [(1404, 3.1), (1405, 3.4)]
    # دادهٔ واقعی دست‌نخورده مانده است
    assert [(p.year, p.value_mw) for p in f.annual_peaks] == \
        [(1400, 2.0), (1401, 2.2), (1402, 2.4), (1403, 2.6)]


def test_switching_back_to_regression_keeps_manual_data(app, manager, page, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    _fill_peaks(page, [(1400, 2.0), (1401, 2.2), (1402, 2.4), (1403, 2.6)])
    page.cb_fc_method.setCurrentIndex(1)
    page.tbl_fc_points.setRowCount(0)
    r = page.tbl_fc_points.rowCount()
    page.tbl_fc_points.insertRow(r)
    page.tbl_fc_points.setItem(r, 1, QTableWidgetItem("1404"))
    page.tbl_fc_points.setItem(r, 2, QTableWidgetItem("9.9"))
    page._manual_forecast()
    assert manager.project.feeders[0].forecast.method == "manual"

    page.cb_fc_method.setCurrentIndex(0)
    page._auto_forecast()
    f = manager.project.feeders[0]
    assert f.forecast.method == "regression"
    # پیش‌بینی دستی قبلی حفظ می‌شود (دو بخش مستقل)
    assert [(p.year, p.value_mw) for p in f.manual_forecast] == [(1404, 9.9)]


# ---------------------------------------------------------------------------
# ماندگاری داده و مسیر گزارش
# ---------------------------------------------------------------------------
def test_annual_peaks_persist_in_project_json(app, manager, tmp_path):
    f = manager.project.feeders[0]
    f.annual_peaks = [ForecastPoint(year=1401, value_mw=2.2, source="MANUAL"),
                      ForecastPoint(year=1402, value_mw=2.4, source="PROFILE")]
    f.manual_forecast = [ForecastPoint(year=1404, value_mw=3.1, source="MANUAL")]
    manager.save()
    from app.core.models import project_from_dict
    import json

    data = json.loads((manager.project_dir / "project.json").read_text(encoding="utf-8"))
    assert data["feeders"][0]["annual_peaks"][0]["year"] == 1401
    again = project_from_dict(data)
    assert [(p.year, p.value_mw, p.source) for p in again.feeders[0].annual_peaks] == \
        [(1401, 2.2, "MANUAL"), (1402, 2.4, "PROFILE")]
    assert [p.year for p in again.feeders[0].manual_forecast] == [1404]


def test_report_chart_uses_annual_peaks_for_manual_forecast(app, manager, tmp_path):
    """نمودار «داده واقعی در برابر پیش‌بینی» باید از پیک‌های واردشده ساخته شود."""
    from app.report.pipeline import build_sections
    from app.report.template_manager import TemplateManager
    from app.report.sections import FigureBlock
    from app.rules.rule_engine import RuleEngine

    f = manager.project.feeders[0]
    f.annual_peaks = [ForecastPoint(year=y, value_mw=v)
                      for y, v in ((1400, 2.0), (1401, 2.2), (1402, 2.4), (1403, 2.6))]
    f.forecast = fc_mod.manual_forecast([(1404, 2.8), (1405, 3.0)])
    settings = AppSettings(include_appendices=False)
    report = build_sections(manager.project, settings, TemplateManager(), RuleEngine(),
                            tmp_path / "charts")
    sec = next(s for s in report.sections if s.key == "forecast")
    assert any(isinstance(b, FigureBlock) for b in sec.blocks), \
        "نمودار پیش‌بینی از داده واقعی واردشده ساخته نشد"
    assert any((tmp_path / "charts").glob("forecast_*.png"))


def test_old_projects_migrate_history_into_actual_data_table(app, manager, page, monkeypatch):
    """پروژه‌های قدیمی که تاریخچه پیش‌بینی داشتند، به جدول «داده واقعی» منتقل می‌شوند."""
    f = manager.project.feeders[0]
    f.annual_peaks = []
    f.forecast = fc_mod.linear_forecast([1400, 1401, 1402, 1403],
                                        [2.0, 2.2, 2.4, 2.6], 5, 3)
    page._load_current()
    app.processEvents()
    assert page.tbl_peaks.rowCount() == 4
    assert page.tbl_peaks.item(0, 1).text() == "1400"        # ستون ۰ = کلید «در گزارش»
    assert page.tbl_peaks.item(0, 3).text() == "PROFILE"
    assert page.tbl_fc_points.rowCount() == 5
