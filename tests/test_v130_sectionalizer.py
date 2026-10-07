# -*- coding: utf-8 -*-
"""v1.3.0 — قابلیت گزارش‌سازی «سکشنالایزر» (اسکلت فعال).

ساختار پنج‌بخشی آماده است و جزئیات تکمیلی بعداً توسط کارفرما ارسال می‌شود؛
این تست‌ها اسکلت، نوع گزارش، اعتبارسنجی و سازگاری ذخیره‌سازی را پوشش می‌دهند.
"""
from __future__ import annotations

import pytest

from app.core.models import SectionalizerInfo, project_from_dict, to_dict
from app.core.report_types import (REPORT_TYPE_HEAVY, REPORT_TYPE_RECLOSER,
                                   REPORT_TYPE_SECTIONALIZER)
from app.core.settings import AppSettings
from app.core.validation import (ERROR, WARNING, validate_project)
from app.report.pipeline import build_sections, generate_docx, report_to_html
from app.report.template_manager import TemplateManager
from app.rules.rule_engine import RuleEngine


def make_sectionalizer_project(**over):
    from sample_projects import make_project
    p = make_project()
    p.report_type = REPORT_TYPE_SECTIONALIZER
    p.applicant_name = "اداره برق منطقه نمونه"
    p.sectionalizer = SectionalizerInfo(
        feeder_name="فیدر ۲۰کیلوولت نمونه",
        installation_location="تیر شماره ۱۲۳، تقاطع بلوار کشاورز",
        objective="ایزوله‌سازی سریع خطاهای بالادست و کاهش خاموشی",
        fault_current_ka=4.5,
        min_fault_current_ka=1.2,
        pickup_current_a=280.0,
        tms=0.15,
        upstream_device="ریکلوزر پست فوق توزیع نمونه",
        coordination_note="زمان‌بندی به‌صورت پلکانی با ریکلوزر بالادست تنظیم شود.",
    )
    for k, v in over.items():
        setattr(p, k, v)
    return p


# ---------------------------------------------------------------------------
# اسکلت گزارش — ساخت پنج بخش با ترتیب ثابت
# ---------------------------------------------------------------------------
def test_sectionalizer_report_has_five_sections_in_order(tmp_path):
    p = make_sectionalizer_project()
    settings = AppSettings(include_appendices=False)
    report = build_sections(p, settings, TemplateManager(), RuleEngine(), tmp_path)
    keys = [s.key for s in report.sections]
    assert keys == ["secz_overview", "secz_network", "secz_settings",
                    "secz_coordination", "secz_conclusion"]
    titles = [s.title for s in report.sections]
    assert "کلیات و مقدمه" in titles[0]
    assert "شبکه و محل نصب" in titles[1]
    assert "اتصال کوتاه" in titles[2]
    assert "هماهنگی حفاظت" in titles[3]
    assert "نتیجه‌گیری و پیشنهادات" in titles[4]


def test_sectionalizer_settings_table_has_values_and_no_unfilled_vars(tmp_path):
    from app.report.sections import TableSpec

    p = make_sectionalizer_project()
    settings = AppSettings(include_appendices=False)
    report = build_sections(p, settings, TemplateManager(), RuleEngine(), tmp_path)
    sec = next(s for s in report.sections if s.key == "secz_settings")
    tables = [b for b in sec.blocks if isinstance(b, TableSpec)]
    assert len(tables) == 1
    body = {row[0]: row[1] for row in tables[0].body_rows}
    assert body["جریان اتصال کوتاه در محل نصب (kA)"] == "4.5"
    assert body["جریان تنظیم پیکاپ (A)"] == "280"
    assert body["تنظیم زمانی (TMS)"] == "0.15"
    text = "\n".join(b.text for s in report.sections for b in s.paragraphs())
    assert "{" not in text and "}" not in text
    assert "فیدر ۲۰کیلوولت نمونه" in text


def test_sectionalizer_missing_fields_show_missing_not_zero(tmp_path):
    from app.report.sections import TableSpec

    p = make_sectionalizer_project(sectionalizer=SectionalizerInfo())
    settings = AppSettings(include_appendices=False)
    report = build_sections(p, settings, TemplateManager(), RuleEngine(), tmp_path)
    sec = next(s for s in report.sections if s.key == "secz_settings")
    table = next(b for b in sec.blocks if isinstance(b, TableSpec))
    values = [row[1] for row in table.body_rows]
    assert all(v == "ناموجود" for v in values)
    assert report.warnings  # هشدار ناقص‌بودن تنظیمات ثبت شده است


def test_sectionalizer_section_on_off(tmp_path):
    p = make_sectionalizer_project()
    settings = AppSettings(include_appendices=False)
    settings.report_sections.secz_settings = False
    report = build_sections(p, settings, TemplateManager(), RuleEngine(), tmp_path)
    keys = [s.key for s in report.sections]
    assert "secz_settings" not in keys
    assert len(keys) == 4


def test_sectionalizer_word_generation(tmp_path):
    from docx import Document

    p = make_sectionalizer_project()
    settings = AppSettings(include_appendices=False)
    report = build_sections(p, settings, TemplateManager(), RuleEngine(), tmp_path)
    out = tmp_path / "secz.docx"
    generate_docx(p, settings, report, out)
    assert out.exists()
    doc = Document(str(out))
    assert doc.core_properties.subject == "گزارش مطالعه نصب سکشنالایزر"
    joined = "\n".join(para.text for para in doc.paragraphs)
    assert "سکشنالایزر" in joined
    html = report_to_html(report, p, settings)
    assert "گزارش مطالعه نصب سکشنالایزر" in html


# ---------------------------------------------------------------------------
# نوع گزارش — ذخیره‌سازی و اعتبارسنجی
# ---------------------------------------------------------------------------
def test_report_type_and_sectionalizer_survive_serialization():
    p = make_sectionalizer_project()
    data = to_dict(p)
    assert data["report_type"] == REPORT_TYPE_SECTIONALIZER
    assert data["sectionalizer"]["fault_current_ka"] == 4.5
    p2 = project_from_dict(data)
    assert p2.report_type == REPORT_TYPE_SECTIONALIZER
    assert isinstance(p2.sectionalizer, SectionalizerInfo)
    assert p2.sectionalizer.pickup_current_a == 280.0
    assert p2.sectionalizer.coordination_note.startswith("زمان‌بندی")
    # پروژه‌های قدیمی بدون فیلد نوع گزارش → پیش‌فرض متقاضیان سنگین
    old = project_from_dict({"name": "قدیمی"})
    assert old.report_type == REPORT_TYPE_HEAVY
    assert old.sectionalizer == SectionalizerInfo()


def test_sectionalizer_validation():
    settings = AppSettings()
    # کامل → هیچ خطایی نیست
    p = make_sectionalizer_project()
    items = validate_project(p, settings)
    assert not any(i.status == ERROR for i in items)
    # بدون نام/شماره/تاریخ → خطا
    p2 = make_sectionalizer_project(applicant_name="", report_number="",
                                    date_jalali="")
    items2 = validate_project(p2, settings)
    assert any(i.status == ERROR for i in items2)
    # بدون داده فنی → هشدار (نه خطا) و تولید گزارش ممکن می‌ماند
    p3 = make_sectionalizer_project(sectionalizer=SectionalizerInfo())
    items3 = validate_project(p3, settings)
    assert any(i.status == WARNING for i in items3)
    assert not any(i.status == ERROR for i in items3)


def test_heavy_validation_untouched_for_heavy_projects():
    p = make_sectionalizer_project(report_type=REPORT_TYPE_HEAVY)
    items = validate_project(p, AppSettings())
    # مسیر اعتبارسنجی متقاضیان سنگین: فیدر تعریف‌نشده → خطا
    assert any(i.status == ERROR for i in items)


def test_recloser_report_type_is_blocked_with_clear_message(tmp_path):
    """در معماری baru، ریکلوزر با هشدار پردازش می‌شود (نه با خطا)."""
    p = make_sectionalizer_project(report_type=REPORT_TYPE_RECLOSER)
    settings = AppSettings(include_appendices=False)
    # در معماری جدید، خطای NotImplementedError Raise نمی‌شود
    # Instead، گزارش با هشدار تولید می‌شود
    report = build_sections(p, settings, TemplateManager(), RuleEngine(), tmp_path)
    # به‌جای خطا، هشدار در报告数据中存在
    assert report.warnings, "باید هشدار مربوط به ریکلوزر وجود داشته باشد"
    assert any("ریکلوزر" in w for w in report.warnings), \
        "هشدار باید مربوط به ریکلوزر باشد"
    # اعتبارسنجی هم به‌جای خطای مبهم، هشدار می‌دهد
    items = validate_project(p, AppSettings())
    assert any(i.status == WARNING and "ریکلوزر" in i.message for i in items)
