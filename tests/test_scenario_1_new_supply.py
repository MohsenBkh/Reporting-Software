# -*- coding: utf-8 -*-
"""تست سناریوی ۱ — تأمین برق جدید 1500 kW با 1 فیدر (بخش ۴۸ سند)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.models import (Feeder, PowerFlowResult, Project, REQUEST_NEW)
from app.core.settings import AppSettings
from app.report import pipeline
from app.report.template_manager import TemplateManager
from app.rules.rule_engine import RuleEngine


def test_new_supply_1500kw_single_feeder(tmp_path):
    settings = AppSettings()
    project = Project(
        name="نیرورسانی ایستگاه پمپاژ سلیمانی",
        report_number="DM-18-003", date_jalali="1405/06/21",
        applicant_name="ایستگاه پمپاژ آب شهرک شهید سلیمانی",
        request_type=REQUEST_NEW, requested_power_kw=1500,
        substation="اردبیل غربی", office="اردبیل",
        location_distance_m=50, cable_suggestion="آلومینیومی سایز 70",
    )
    f1 = Feeder(name="فیدر 2 اردبیل غربی", peak_load_mw=2.75, peak_year=1404,
                power_factor=0.93, peak_current_a=85, max_current_a=490,
                capacity_mw=7,
                before=PowerFlowResult(79, 64, 0.972, 0.992),
                after=PowerFlowResult(122, 93, 0.967, 0.986))
    project.feeders = [f1]

    report, docx, items = pipeline.generate_report_full(
        project, settings, tmp_path / "charts", tmp_path,
        TemplateManager(), RuleEngine())

    assert docx.exists()
    text = "\n".join(p.text for s in report.sections for p in s.paragraphs())

    # ساختار مطابق گزارش مرجع (مقدمه ... نتیجه‌گیری و پیشنهادات)
    titles = [s.title for s in report.sections]
    assert any("مقدمه" in t for t in titles)
    assert any("تحلیل وضعیت بارگذاری" in t for t in titles)
    assert any("قبل از" in t for t in titles)
    assert any("پس از" in t for t in titles)
    assert any("نتیجه‌گیری و پیشنهادات" in t for t in titles)

    # عدد افزایش: 1.5 مگاوات خودکار محاسبه شود
    assert "1.5" in text
    # متن ولتاژ عادی: قبل/بعد در محدوده و تغییر کم
    assert "در محدوده مجاز" in text
    # عنوان جدول نتایج
    caps = [t.caption for s in report.sections for t in s.blocks if hasattr(t, "caption")]
    assert any("جدول 2" in c for c in caps)
    # جریان/تلفات بعد در جدول
    tbl2 = next(t for s in report.sections for t in s.blocks if hasattr(t, "caption") and "جدول 2" in t.caption)
    flat = [cell for row in tbl2.body_rows for cell in row]
    assert "122" in flat and "93" in flat
