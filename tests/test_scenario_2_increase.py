# -*- coding: utf-8 -*-
"""تست سناریوی ۲ — افزایش قدرت 1000→1100 kW با 2 فیدر + مانور (بخش ۴۸ سند)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.models import (Feeder, Maneuver, PowerFlowResult, Project,
                             REQUEST_INCREASE)
from app.core.settings import AppSettings
from app.report import pipeline
from app.report.template_manager import TemplateManager
from app.rules.rule_engine import RuleEngine


def test_increase_2feeders_maneuver(tmp_path):
    settings = AppSettings()
    project = Project(
        name="افزایش قدرت ناب پروتئین مهر",
        report_number="DM-18-001", date_jalali="1405/06/15",
        applicant_name="شرکت تأمین تولید و توزیع ناب پروتئین مهر",
        request_type=REQUEST_INCREASE,
        existing_power_kw=1000, requested_power_kw=1100,
        substation="کمی‌آباد", office="اردبیل",
    )
    project.maneuver = Maneuver(enabled=True, source_feeder="فیدر 2 اردبیل",
                                target_feeder="فیدر 1 اردبیل",
                                transferred_mw=2.5)
    f1 = Feeder(name="فیدر 1 اردبیل", peak_load_mw=6.3, peak_year=1404,
                power_factor=0.89, peak_current_a=204, capacity_mw=7,
                before=PowerFlowResult(201, 452, 0.835, 0.956),
                after=PowerFlowResult(204, 459, 0.835, 0.954))
    f2 = Feeder(name="فیدر 2 اردبیل", peak_load_mw=6.1, peak_year=1404,
                power_factor=0.89, peak_current_a=200, capacity_mw=7,
                before=PowerFlowResult(205, 687, 0.847),
                after=PowerFlowResult(205, 687, 0.847))
    project.feeders = [f1, f2]

    report, docx, items = pipeline.generate_report_full(
        project, settings, tmp_path / "charts", tmp_path,
        TemplateManager(), RuleEngine())

    assert docx.exists()
    text = "\n".join(p.text for s in report.sections for p in s.paragraphs())

    # عنوان با ساختار نمونه
    assert "افزایش قدرت" in text and "1000" in text and "1100" in text
    # مانور با مقدار منتقل‌شده
    assert "2.5" in text and "فیدر 2 اردبیل" in text
    # عنوان چندفیدری
    titles = [s.title for s in report.sections]
    assert any("فیدرهای" in t for t in titles)
    # منطق افت ولتاژ موجود فیدر 1 — ناشی از بار جدید نیست (Test 3 نیز پوشش داده می‌شود)
    assert "ناشی از افزایش قدرت جدید نیست" in text
    # جدول ۲ با دو ستون فیدر
    tbl2 = next(t for s in report.sections for t in s.blocks
                if hasattr(t, "caption") and "جدول 2" in t.caption)
    assert len(tbl2.merges) == 2  # دو گروه ستون فیدر
    # عدم باقی ماندن placeholder
    assert "{" not in text and "}" not in text
