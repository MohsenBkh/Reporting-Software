# -*- coding: utf-8 -*-
"""v2.1.2 — چیدمان خروجی Word مطابق «نمونه دفترچه مطالعه ریکلوزر و سکشنالایزر».

لوگوی توانیر، عناوین جلد، سربرگ سه‌ستونه، راست‌چینی تیترها و ۷ فصل پیش‌فرض.
"""
from __future__ import annotations

import re
import zipfile

from test_v130_sectionalizer import make_sectionalizer_project

from app.core.report_types import (PROTECTION_BOOKLET_TITLE,
                                   PROTECTION_HEADER_TITLE,
                                   REPORT_TYPE_COMBINED_PROTECTION,
                                   REPORT_TYPE_HEAVY, REPORT_TYPE_RECLOSER,
                                   REPORT_TYPE_SECTIONALIZER, booklet_title,
                                   header_title, is_protection_report)
from app.core.settings import AppSettings
from app.core.workspace import ReportPreferences
from app.report.pipeline import build_sections, generate_docx
from app.report.template_manager import TemplateManager
from app.report.word_generator import default_logo_path, header_logo_path
from app.rules.rule_engine import RuleEngine

# ۷ فصل دفترچه نمونه (مطالعه تک‌دستگاهی؛ در گزارش ترکیبی فصل دستگاه دوم افزوده می‌شود)
SAMPLE_CHAPTERS = ["مقدمه", "مشخصات شبکه", "وضعیت حفاظتی موجود", "جانمایی تجهیزات",
                   "هماهنگی حفاظتی", "سناریوی عملکرد"]


def _docx(tmp_path, **over):
    p = make_sectionalizer_project(**over)
    settings = AppSettings(include_appendices=False)
    report = build_sections(p, settings, TemplateManager(), RuleEngine(), tmp_path)
    out = generate_docx(p, settings, report, tmp_path / "out.docx")
    return p, report, zipfile.ZipFile(out)


def _texts(xml: str) -> list[str]:
    return re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml)


def test_protection_titles_match_sample_booklet():
    for rt in (REPORT_TYPE_RECLOSER, REPORT_TYPE_SECTIONALIZER,
               REPORT_TYPE_COMBINED_PROTECTION):
        assert is_protection_report(rt)
        assert booklet_title(rt) == PROTECTION_BOOKLET_TITLE
        assert header_title(rt) == PROTECTION_HEADER_TITLE
    assert not is_protection_report(REPORT_TYPE_HEAVY)
    assert header_title(REPORT_TYPE_HEAVY) == booklet_title(REPORT_TYPE_HEAVY)
    assert PROTECTION_BOOKLET_TITLE == "دفترچه مطالعات جایابی تجهیزات و هماهنگی حفاظتی"


def test_tavanir_logos_ship_with_app():
    cover, header = default_logo_path(), header_logo_path()
    assert cover is not None and cover.name == "tavanir_logo.png"
    assert header is not None and header.name == "tavanir_logo_header.png"


def test_default_protection_report_has_seven_chapters(tmp_path):
    _, report, _ = _docx(tmp_path)
    keys = [s.key for s in report.sections]
    assert len(keys) == 7
    assert keys == ["prot_intro", "prot_network", "prot_existing", "prot_placement",
                    "prot_sectionalizer", "prot_coordination", "prot_scenario"]
    titles = [s.title for s in report.sections]
    for ch in SAMPLE_CHAPTERS:
        assert any(ch in t for t in titles), ch


def test_report_preferences_default_disables_extras():
    prefs = ReportPreferences()
    assert set(prefs.disabled_sections) == {"prot_trace", "prot_conclusion",
                                            "prot_recommendation"}


def test_header_is_three_column_table_with_logo_and_sample_texts(tmp_path):
    p, _, z = _docx(tmp_path)
    headers = [n for n in z.namelist() if n.startswith("word/header")]
    assert headers
    xml = max((z.read(h).decode("utf-8") for h in headers), key=len)
    assert "<w:tbl>" in xml and "bidiVisual" in xml
    assert len(re.findall("<w:gridCol", xml)) == 3          # سه‌ستونه مطابق نمونه
    assert "<w:drawing>" in xml                              # آرم توانیر در سربرگ
    txts = _texts(xml)
    assert any(PROTECTION_HEADER_TITLE in t for t in txts)
    assert any("شماره گزارش:" in t for t in txts)
    assert any(t.startswith("تاریخ:") for t in txts)
    assert any("شرکت توزیع" in t for t in txts)
    # خط ممتد زیر سربرگ
    assert "w:pBdr" in xml


def test_cover_matches_sample_layout(tmp_path):
    p, _, z = _docx(tmp_path)
    doc = z.read("word/document.xml").decode("utf-8")
    txts = _texts(doc)
    i_series = next(i for i, t in enumerate(txts) if t == PROTECTION_BOOKLET_TITLE)
    # ترتیب جلد: شرکت → معاونت → دفتر/گروه → عنوان سری → عنوان پروژه → ماه/سال → شماره
    assert "شرکت توزیع" in txts[i_series - 3]
    assert "معاونت" in txts[i_series - 2]
    txt_after = txts[i_series + 1: i_series + 4]
    assert p.title_text() == txt_after[0]
    assert re.fullmatch(r"\S+ \d{4}", txt_after[1])          # «ماه ۱۴۰۵»
    assert txt_after[2].startswith("شماره گزارش:")
    # مطابق نمونه: سطر جداگانه «تاریخ: YYYY/MM/DD» روی جلد نیست
    cover_txts = txts[: i_series + 6]
    assert not any(t.startswith("تاریخ:") for t in cover_txts)
    # لوگوی جلد درج شده است
    assert "word/media/image1.png" in z.namelist()


def test_headings_are_right_aligned_rtl(tmp_path):
    _, _, z = _docx(tmp_path)
    doc = z.read("word/document.xml").decode("utf-8")
    heads = [p for p in re.findall(r"<w:pPr>.*?</w:pPr>", doc)
             if 'w:val="Heading1"' in p]
    assert heads                                              # تیتر فصل وجود دارد
    for pPr in heads:                                         # راست‌چین + دوجهتی
        assert "<w:bidi/>" in pPr and 'w:jc w:val="right"' in pPr


def test_captions_are_eleven_point_in_protection_reports(tmp_path):
    from app.core.models import Project
    from app.report.word_generator import WordGenerator
    settings = AppSettings()
    gen = WordGenerator(make_sectionalizer_project(), settings)
    assert gen.protection and gen._caption_size == 11
    heavy = Project(); heavy.report_type = REPORT_TYPE_HEAVY
    gen2 = WordGenerator(heavy, settings)
    assert not gen2.protection
    assert gen2._caption_size == settings.fonts.body_size - 1
