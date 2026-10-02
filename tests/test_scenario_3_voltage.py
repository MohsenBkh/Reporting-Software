# -*- coding: utf-8 -*-
"""تست سناریوی ۳ — تشخیص مشکل ولتاژ موجود (قبل: خارج از محدوده، بعد: بدون تغییر).

نرم‌افزار باید تشخیص دهد که مشکل ولتاژ موجود الزاماً ناشی از افزایش قدرت نیست.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import calculations as calc
from app.core.models import (Feeder, PowerFlowResult, Project,
                             REQUEST_INCREASE)
from app.core.settings import AppSettings
from app.report.text_generator import TextGenerator
from app.report.template_manager import TemplateManager
from app.rules.rule_engine import RuleEngine


def test_preexisting_voltage_problem_detected(tmp_path):
    settings = AppSettings()
    project = Project(
        name="افزایش قدرت تست ولتاژ", report_number="DM-18-010",
        date_jalali="1405/06/15", applicant_name="متقاضی تست",
        request_type=REQUEST_INCREASE,
        existing_power_kw=1000, requested_power_kw=1100)
    f1 = Feeder(name="فیدر تست", peak_load_mw=5.0, capacity_mw=7,
                before=PowerFlowResult(current_a=180, loss_kw=400,
                                       min_voltage_pu=0.910,   # خارج از محدوده
                                       applicant_bus_voltage_pu=0.95),
                after=PowerFlowResult(current_a=182, loss_kw=406,
                                      min_voltage_pu=0.910,   # تقریباً بدون تغییر
                                      applicant_bus_voltage_pu=0.949))
    project.feeders = [f1]

    engine = RuleEngine()
    texts = TemplateManager()
    ctx = calc.build_feeder_context(f1, project, settings)
    rule = engine.first_match("after_voltage", ctx)
    assert rule is not None
    assert rule.id == "V-PREEXISTING", f"قاعده منتخب: {rule.id}"

    gen = TextGenerator(project, settings, texts, engine, tmp_path)
    sec = gen.build_after()
    text = "\n".join(p.text for p in sec.paragraphs())
    assert "ناشی از افزایش قدرت جدید نیست" in text
    assert "اقدامات اصلاحی" in text


def test_new_violation_detected(tmp_path):
    """سناریوی مخالف: بار جدید باعث خروج ولتاژ از محدوده می‌شود."""
    settings = AppSettings()
    project = Project(
        name="افزایش قدرت تست ۲", report_number="DM-18-011",
        date_jalali="1405/06/15", applicant_name="متقاضی تست",
        request_type=REQUEST_INCREASE,
        existing_power_kw=1000, requested_power_kw=1100)
    f1 = Feeder(name="فیدر تست", peak_load_mw=5.0, capacity_mw=7,
                before=PowerFlowResult(current_a=180, loss_kw=400,
                                       min_voltage_pu=0.960),
                after=PowerFlowResult(current_a=240, loss_kw=510,
                                      min_voltage_pu=0.915))
    project.feeders = [f1]

    engine = RuleEngine()
    ctx = calc.build_feeder_context(f1, project, settings)
    rule = engine.first_match("after_voltage", ctx)
    assert rule is not None
    assert rule.id in ("V-NEWVIOLATION", "V-CHANGEBIG")

    texts = TemplateManager()
    gen = TextGenerator(project, settings, texts, engine, tmp_path)
    sec = gen.build_after()
    text = "\n".join(p.text for p in sec.paragraphs())
    assert ("امکان‌پذیر نمی‌باشد" in text) or ("حد مجاز" in text)


def test_conclusion_conditional(tmp_path):
    """جمع‌بندی مشروط هنگام وجود مشکل — بدون اختراع نتیجه فنی جدید."""
    settings = AppSettings()
    project = Project(
        name="جمع‌بندی تست", report_number="DM-18-012",
        date_jalali="1405/06/15", applicant_name="متقاضی",
        request_type=REQUEST_INCREASE,
        existing_power_kw=1000, requested_power_kw=1100)
    f1 = Feeder(name="فیدر تست", peak_load_mw=5.0, capacity_mw=7,
                before=PowerFlowResult(180, 400, 0.910, None),
                after=PowerFlowResult(182, 406, 0.910, None))
    project.feeders = [f1]
    engine = RuleEngine()
    ctx = calc.build_project_context(project, settings)
    rule = engine.first_match("conclusion", ctx)
    assert rule is not None
    # ولتاژ موجود ناشی از متقاضی نیست → نه «بد» و نه «مشروط به اقدام»؛ نه C-OK
    assert rule.id == "C-PREEXISTING"
    assert rule.id != "C-OK"
