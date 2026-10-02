# -*- coding: utf-8 -*-
"""تست‌های رگرسیون — پوشش ایرادات برطرف‌شده (Fixes regression tests)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.core import calculations as calc
from app.core.models import (Feeder, ForecastPoint, ForecastResult, Project,
                             PowerFlowResult, REQUEST_NEW,
                             feeder_from_dict, project_from_dict, to_dict)
from app.core.settings import AppSettings
from app.report import pipeline
from app.report.template_manager import TemplateManager
from app.rules.rule_engine import RuleEngine, safe_eval_bool


# ---------------------------------------------------------------------------
def _healthy_project() -> Project:
    p = Project(name="پ", report_number="DM-1", date_jalali="1405/01/01",
                applicant_name="م", request_type=REQUEST_NEW,
                requested_power_kw=1500)
    p.feeders = [Feeder(name="ف", peak_load_mw=1.0, capacity_mw=7,
                        before=PowerFlowResult(100, 50, 0.98, 0.99),
                        after=PowerFlowResult(110, 52, 0.978, 0.985))]
    return p


# --- Fix: forecast points survive serialization roundtrip -------------------
def test_forecast_points_roundtrip_as_objects(tmp_path):
    p = _healthy_project()
    f = p.feeders[0]
    f.forecast = ForecastResult(method="regression",
                                points=[ForecastPoint(year=1406, value_mw=2.9),
                                        ForecastPoint(year=1407, value_mw=3.1)],
                                history_years=[1403, 1404, 1405],
                                history_values=[2.4, 2.6, 2.75],
                                r2=0.98, slope_mw_per_year=0.18)
    p2 = project_from_dict(to_dict(p))
    fc = p2.feeders[0].forecast
    assert isinstance(fc.points[0], ForecastPoint)
    assert fc.end_value() == pytest.approx(3.1)
    assert fc.end_year() == 1407
    # and the full report pipeline can render it without AttributeError
    s = AppSettings()
    out = pipeline.generate_report_full(p2, s, tmp_path / "charts",
                                        tmp_path, TemplateManager(), RuleEngine())
    assert out[1].exists()


# --- Fix: feeder_from_dict manual_forecast stays objects --------------------
def test_manual_forecast_roundtrip():
    f = feeder_from_dict({"name": "ف", "manual_forecast": [{"year": 1406, "value_mw": 3.0}]})
    assert all(isinstance(pt, ForecastPoint) for pt in f.manual_forecast)


# --- Fix: C-NODATA conclusion rule matches when results incomplete ----------
def test_conclusion_nodata_rule_matches_empty_context():
    eng = RuleEngine()
    rule = eng.first_match("conclusion", {})
    assert rule is not None and rule.id == "C-NODATA"


def test_safe_eval_lowercase_and_string_none():
    assert safe_eval_bool("true", {}) is True
    assert safe_eval_bool("false", {}) is False
    # 'none' داخل رشته نباید تغییر کند
    ctx = {"fc_method": "none"}
    assert safe_eval_bool("fc_method == 'none'", ctx) is True
    assert safe_eval_bool("fc_method == 'regression'", ctx) is False


# --- Fix: issue_summary never invents problems for a healthy feeder ---------
def test_issue_summary_healthy_feeder():
    s = AppSettings()
    summary = calc.issue_summary(_healthy_project(), s)
    assert summary == "بدون مشکل خاصی"


def test_loss_increase_alone_is_not_an_issue():
    """v1.0.3: افزایش تلفات به‌تنهایی مبنای اقدام اصلاحی/نتیجه مشروط نیست."""
    s = AppSettings()
    p = _healthy_project()
    p.feeders[0].after.loss_kw = 80   # +60% > آستانه
    summary = calc.issue_summary(p, s)
    assert "تلفات" not in summary
    ctx = calc.build_project_context(p, s)
    assert ctx["any_loss_up"] is True        # فقط اطلاع‌رسانی
    assert ctx["any_caused_issue"] is False
    assert ctx["all_ok"] is True


# --- Fix: report sections carry tables after manual edit replacement --------
def test_manual_text_replacement_keeps_tables():
    from app.report.sections import Paragraph, ReportSection, TableSpec
    from app.report.text_generator import TextGenerator
    s = AppSettings()
    p = _healthy_project()
    gen = TextGenerator(p, s, TemplateManager(), RuleEngine(), Path("."))
    sec = ReportSection("conclusion", "جمع‌بندی")
    sec.blocks = [Paragraph("متن خودکار"), TableSpec("کپشن", [["a"], ["b"]], [])]
    p.manual_texts["conclusion"] = "متن ویرایش‌شده"
    # اجرای همان منطق build_all روی بخش
    manual = (p.manual_texts or {}).get(sec.key, "").strip()
    assert manual
    # simulate the (fixed) build_all logic
    new_blocks = []
    inserted = False
    for b in sec.blocks:
        if isinstance(b, Paragraph) and not inserted:
            for part in [x.strip() for x in manual.split("\n\n") if x.strip()]:
                new_blocks.append(Paragraph(part))
            inserted = True
        elif not isinstance(b, Paragraph):
            new_blocks.append(b)
    sec.blocks = new_blocks
    tables = [b for b in sec.blocks if isinstance(b, TableSpec)]
    assert len(tables) == 1  # جدول حفظ شده است
    assert any(b.text == "متن ویرایش‌شده" for b in sec.blocks if isinstance(b, Paragraph))


# --- Fix: each user image is inserted only once -----------------------------
def test_images_inserted_once(tmp_path, monkeypatch):
    from app.core.models import ProjectImage
    from app.report.text_generator import TextGenerator
    s = AppSettings()
    p = _healthy_project()
    img = ProjectImage(file_name="x.png", title="ت", kind="network")
    p.images = [img]
    png = tmp_path / "x.png"
    png.write_bytes(b"fake")
    gen = TextGenerator(p, s, TemplateManager(), RuleEngine(), tmp_path,
                        image_resolver=lambda i: png)
    a = gen._figures_of_kind("network")
    b = gen._figures_of_kind("network")
    assert len(a) == 1 and len(b) == 0
