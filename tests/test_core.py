# -*- coding: utf-8 -*-
"""تست‌های واحد — مدل داده، محاسبات، پیش‌بینی، قالب Excel و قواعد."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import pytest

from app.core import loading_profile as lp
from app.core import forecast as fc_mod
from app.core.models import (Feeder, PowerFlowResult, Project,
                             REQUEST_INCREASE, REQUEST_NEW, project_from_dict,
                             to_dict)
from app.core.settings import AppSettings
from app.core.validation import has_errors, validate_project
from app.excel.importer import build_project_from_excel
from app.excel.template import create_template
from app.rules.rule_engine import safe_eval_bool
from app.core.project_manager import ProjectManager


# ---------------------------------------------------------------------------
# مدل داده
# ---------------------------------------------------------------------------
def test_project_power_delta_auto():
    p = Project(request_type=REQUEST_INCREASE,
                existing_power_kw=1000, requested_power_kw=1100)
    assert p.power_delta_kw() == 100
    assert p.added_power_mw() == 0.1
    assert "1100" in p.title_text() and "1000" in p.title_text()


def test_project_new_supply_title():
    p = Project(request_type=REQUEST_NEW, requested_power_kw=1500,
                applicant_name="ایستگاه پمپاژ")
    assert "1500" in p.title_text()


def test_project_roundtrip_serialization(tmp_path):
    p = Project(name="تست", report_number="DM-1", date_jalali="1405/01/01",
                applicant_name="م", request_type=REQUEST_INCREASE,
                existing_power_kw=1000, requested_power_kw=1100)
    f = Feeder(name="ف1", peak_load_mw=1.5,
               before=PowerFlowResult(10, 20, 0.95),
               after=PowerFlowResult(11, 22, 0.94))
    p.feeders = [f]
    data = to_dict(p)
    p2 = project_from_dict(data)
    assert p2.feeders[0].before.min_voltage_pu == 0.95
    assert p2.feeders[0].after.current_a == 11
    assert p2.request_type == REQUEST_INCREASE


# ---------------------------------------------------------------------------
# محاسبات
# ---------------------------------------------------------------------------
def test_metrics_delta_percentages():
    settings = AppSettings()
    project = Project(request_type=REQUEST_INCREASE,
                      existing_power_kw=1000, requested_power_kw=1100)
    f = Feeder(name="ف",
               before=PowerFlowResult(current_a=200, loss_kw=400,
                                      min_voltage_pu=0.950),
               after=PowerFlowResult(current_a=210, loss_kw=440,
                                     min_voltage_pu=0.945))
    ctx = calc_ctx(f, project, settings)
    assert ctx["d_i_pct"] == pytest.approx(5.0)
    assert ctx["d_loss_pct"] == pytest.approx(10.0)
    assert ctx["d_v_pct"] == pytest.approx(-0.526, abs=0.01)
    assert ctx["v_before_ok"] is True
    assert ctx["v_after_ok"] is False  # 0.945 < 0.95


def calc_ctx(f, project, settings):
    from app.core import calculations as calc
    return calc.build_feeder_context(f, project, settings)


def test_loading_classification():
    settings = AppSettings()
    project = Project(request_type=REQUEST_NEW, requested_power_kw=1500)
    f = Feeder(name="ف", peak_load_mw=2.75, capacity_mw=7)
    ctx = calc_ctx(f, project, settings)
    # 2.75/7 = 39.3% → مطابق گزارش نمونه: عادی و نسبتاً کم‌بار
    assert ctx["loading_pct"] == pytest.approx(39.29, abs=0.05)
    assert ctx["loading_class"] == "عادی و نسبتاً کم‌بار"
    # با بار جدید 1.5 → 4.25/7 = 60.7% → همچنان عادی و نسبتاً کم‌بار
    assert ctx["loading_after_class"] == "عادی و نسبتاً کم‌بار"


# ---------------------------------------------------------------------------
# پروفیل بار و پیش‌بینی
# ---------------------------------------------------------------------------
def test_profile_parse_and_stats():
    raw = "Date\tFeeder\tP_MW\tQ_MVAR\n1404/05/02\tفیدر1\t2.5\t0.9\n1404/06/10\tفیدر1\t2.75\t1.0\n"
    df, errors = lp.parse_profile(raw)
    assert not errors
    assert len(df) == 2
    st = lp.compute_stats(df)
    assert st.peak_p_mw == 2.75
    assert st.peak_date == "1404/06/10"
    assert st.n_points == 2
    years, values = lp.annual_peaks(df)
    assert years == [1404] and values == [2.75]


def test_profile_missing_columns():
    df, errors = lp.parse_profile("A\tB\n1\t2\n")
    assert errors  # ستون‌های ضروری پیدا نشد
    assert df.empty


def test_forecast_regression_and_insufficient():
    fc = fc_mod.linear_forecast([1400, 1401, 1402, 1403], [2.0, 2.2, 2.4, 2.6],
                                horizon=5, min_points=3)
    assert fc.method == "regression"
    assert fc.slope_mw_per_year == pytest.approx(0.2, abs=0.01)
    assert fc.end_year() == 1408
    assert fc.end_value() == pytest.approx(3.6, abs=0.05)  # 2.6 + 0.2×5
    assert len(fc.points) == 5

    fc2 = fc_mod.linear_forecast([1403], [2.0], horizon=5, min_points=3)
    assert fc2.method == "none"  # بدون جعل داده
    assert not fc2.available


# ---------------------------------------------------------------------------
# قواعد
# ---------------------------------------------------------------------------
def test_safe_eval():
    assert safe_eval_bool("a > 1", {"a": 2}) is True
    assert safe_eval_bool("a > 1", {"a": 0}) is False
    assert safe_eval_bool("has_capacity and f_loading_pct > 100",
                          {"has_capacity": True, "f_loading_pct": 120}) is True
    # تلاش برای اجرای کد باید False بدهد
    assert safe_eval_bool("__import__('os').system('dir')", {}) is False
    assert safe_eval_bool("open('x')", {"open": 1}) is False


# ---------------------------------------------------------------------------
# اعتبارسنجی
# ---------------------------------------------------------------------------
def test_validation_blocks_missing_required():
    settings = AppSettings()
    p = Project()  # خالی
    items = validate_project(p, settings)
    assert has_errors(items)


def test_validation_complete_project():
    settings = AppSettings()
    p = Project(name="پ", report_number="DM-1", date_jalali="1405/01/01",
                applicant_name="م", request_type=REQUEST_INCREASE,
                existing_power_kw=1000, requested_power_kw=1100)
    p.feeders = [Feeder(name="ف", peak_load_mw=1.0,
                        before=PowerFlowResult(10, 20, 0.95),
                        after=PowerFlowResult(11, 22, 0.95))]
    items = validate_project(p, settings)
    assert not has_errors(items)


# ---------------------------------------------------------------------------
# قالب Excel و Importer
# ---------------------------------------------------------------------------
def test_excel_template_roundtrip(tmp_path):
    settings = AppSettings()
    tpl = create_template(tmp_path / "tpl.xlsx")
    assert tpl.exists()
    project, errors, warnings = build_project_from_excel(tpl, settings)
    assert not errors, errors
    assert project is not None
    assert len(project.feeders) == 1
    f = project.feeders[0]
    assert f.name == "فیدر 1 اردبیل"
    assert f.before.min_voltage_pu == 0.835
    assert f.after.current_a == 204
    assert project.request_type == REQUEST_INCREASE


def test_excel_bad_file_rejected(tmp_path):
    settings = AppSettings()
    bad = tmp_path / "bad.xlsx"
    bad.write_bytes(b"not excel")
    project, errors, _ = build_project_from_excel(bad, settings)
    assert project is None
    assert errors


# ---------------------------------------------------------------------------
# مدیریت پروژه
# ---------------------------------------------------------------------------
def test_project_save_open_roundtrip(tmp_path):
    settings = AppSettings()
    pm = ProjectManager(settings)
    p = Project(name="پروژه ذخیره", report_number="DM-9",
                date_jalali="1405/02/03", applicant_name="الف",
                request_type=REQUEST_NEW, requested_power_kw=1200)
    p.feeders = [Feeder(name="فیدر", peak_load_mw=2.0,
                        before=PowerFlowResult(50, 30, 0.97),
                        after=PowerFlowResult(100, 60, 0.96))]
    pm.new_project(tmp_path / "proj", p)
    assert (tmp_path / "proj" / "project.json").exists()

    pm2 = ProjectManager(settings)
    p2 = pm2.open_project(tmp_path / "proj" / "project.json")
    assert p2.feeders[0].after.current_a == 100
    assert p2.report_number == "DM-9"
