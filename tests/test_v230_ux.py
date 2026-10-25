# -*- coding: utf-8 -*-
"""آزمون‌های v2.3.0 — بهبودهای UX و گزارش:

۱) ماندگاری تنظیمات دستیار AI (مدل/آدرس پایه) + ارتقای دستورالعمل پیش‌فرض
۲) دستورالعمل AI شامل تحلیل تصاویر و جدول‌ها
۳) صفحهٔ افقی (Landscape) برای پیوست برگه تنظیمات در Word
۴) اندازهٔ شکل‌ها تا لبهٔ حاشیه‌ها
۵) مختصات محل نصب ریکلوزر/سکشنالایزر
۶) شماره‌گذاری سراسری شکل‌ها مانند جدول‌ها
۷) صفحهٔ مشترک «فیدرهای محدودهٔ مطالعه» (حذف تب از صفحه‌های مطالعه)
۸) حذف ورود دستی رلهٔ ابتدای فیدر — ورود از IDMT جایگزین است
۹) سه تب «بخش‌های گزارش» بر اساس نوع مطالعه در تنظیمات
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).parent))

_APP = QApplication.instance() or QApplication([])

from app.core.models import Project, RecloserInfo, SectionalizerInfo
from app.core.settings import AppSettings
from app.report.sections import FigureBlock, Paragraph, ReportSection, number_figures


# ---------------------------------------------------------------------------
# ۶) شماره‌گذاری شکل‌ها
# ---------------------------------------------------------------------------
def test_number_figures_sequential_across_sections():
    secs = [ReportSection("a", "الف", [FigureBlock("/x.png", "تک‌خطی"), Paragraph("متن")]),
            ReportSection("b", "ب", [FigureBlock("/y.png", "TCC فاز"),
                                     FigureBlock("/z.png", "")])]
    n = number_figures(secs)
    assert n == 3
    assert secs[0].blocks[0].caption == "شکل 1: تک‌خطی"
    assert secs[1].blocks[0].caption == "شکل 2: TCC فاز"
    assert secs[1].blocks[1].caption == "شکل 3"        # بدون عنوان → فقط شماره


def test_number_figures_strips_old_prefix_on_regenerate():
    secs = [ReportSection("a", "الف", [FigureBlock("/x.png", "شکل 7: تک‌خطی")])]
    number_figures(secs)
    assert secs[0].blocks[0].caption == "شکل 1: تک‌خطی"
    number_figures(secs)                                # تولید دوباره = بدون انباشت پیشوند
    assert secs[0].blocks[0].caption == "شکل 1: تک‌خطی"


def test_composer_numbers_user_figures():
    from app.core.studies import StudyKind
    from app.core.workspace import workspace_from_project
    from app.report.composer import ReportComposer

    p = Project(name="x")
    p.recloser = RecloserInfo(feeder_name="F4")

    class _Img:
        section_key, kind, order, caption, title, enabled = "prot_intro", "other", 0, "محل", "ش", True

    p.__class__ = type("P", (p.__class__,), {"active_images": property(lambda self: [_Img()])})
    ws = workspace_from_project(p)
    report = ReportComposer().compose(p, ws, [StudyKind.RECLOSER],
                                      image_resolver=lambda i: "/x.png")
    caps = [b.caption for s in report.sections for b in s.blocks if isinstance(b, FigureBlock)]
    assert caps and all(c.startswith("شکل ") for c in caps)


# ---------------------------------------------------------------------------
# ۳ و ۴) Word: پیوست افقی + شکل‌ها تا لبه حاشیه
# ---------------------------------------------------------------------------
def _mini_png(path: Path) -> Path:
    import base64
    png = base64.b64decode(
        b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQAB"
        b"h6FO1AAAAABJRU5ErkJggg==")
    path.write_bytes(png)
    return path


def test_word_settings_sheet_section_is_landscape_and_figures_full_width(tmp_path):
    from app.report.word_generator import WordGenerator

    img = _mini_png(tmp_path / "sheet.png")
    p = Project(name="پروژه", report_type="recloser")
    settings = AppSettings()
    gen = WordGenerator(p, settings)
    assert "prot_settings_sheet" in gen.LANDSCAPE_SECTIONS

    from app.report.sections import GeneratedReport
    report = GeneratedReport(sections=[
        ReportSection("prot_intro", "مقدمه", [Paragraph("متن"),
                                              FigureBlock(str(img), "شکل 1: تک‌خطی")]),
        ReportSection("prot_settings_sheet", "پیوست — برگه تنظیمات",
                      [FigureBlock(str(img), "شکل 2: برگه تنظیمات")])])
    out = gen.generate(report, tmp_path / "r.docx")
    xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8")
    assert 'w:orient="landscape"' in xml                 # Section افقی ساخته شده است
    # صفحه افقی A4: عرض 29.7cm (~16838 twips) و ارتفاع 21cm (~11906 twips)
    assert 'w:w="16838" w:h="11906"' in xml


def test_word_figure_width_fills_portrait_margins(tmp_path):
    from docx import Document
    from docx.shared import Cm
    from app.report.sections import GeneratedReport
    from app.report.word_generator import WordGenerator

    img = _mini_png(tmp_path / "sq.png")
    p = Project(name="پروژه", report_type="recloser")
    gen = WordGenerator(p, AppSettings())
    report = GeneratedReport(sections=[
        ReportSection("prot_intro", "مقدمه", [FigureBlock(str(img), "شکل 1: مربع")]),
        ReportSection("prot_settings_sheet", "پیوست",
                      [FigureBlock(str(img), "شکل 2: برگه")])])
    out = gen.generate(report, tmp_path / "r.docx")
    doc = Document(out)
    widths = [sh.width for sh in doc.inline_shapes]
    # شکل عمودی: تصویر مربع تا عرض کامل حاشیه‌ها (17cm) بزرگ می‌شود (قبلاً 15cm)
    assert any(abs(w - Cm(17.0)) < Cm(0.05) for w in widths)
    # شکل افقی (پیوست): تصویر مربع با سقف ارتفاع صفحه افقی (16.2cm) محدود می‌شود
    assert any(abs(w - Cm(16.2)) < Cm(0.05) for w in widths)


# ---------------------------------------------------------------------------
# ۵) مختصات محل نصب
# ---------------------------------------------------------------------------
def test_coordinates_roundtrip_and_in_placement_chapter():
    from app.core.models import project_from_dict, to_dict
    from app.core.studies import StudyKind
    from app.core.workspace import workspace_from_project
    from app.report.composer import ReportComposer

    p = Project(name="x")
    p.recloser = RecloserInfo(feeder_name="F4", installation_location="تیر ۱۲",
                              coordinates="48.283541, 38.561204")
    p.sectionalizer = SectionalizerInfo(coordinates="UTM 39S 612345 4268900")
    d = to_dict(p)
    p2 = project_from_dict(d)
    assert p2.recloser.coordinates == "48.283541, 38.561204"
    assert p2.sectionalizer.coordinates == "UTM 39S 612345 4268900"

    ws = workspace_from_project(p)
    report = ReportComposer().compose(p, ws, [StudyKind.RECLOSER])
    placement = next(s for s in report.sections if s.key == "prot_placement")
    text = "\n".join(b.text for b in placement.blocks if isinstance(b, Paragraph))
    assert "مختصات محل نصب: 48.283541, 38.561204" in text


def test_protection_page_has_coordinates_field(qtbot=None):
    from app.ui.protection_page import ProtectionPage

    class _Mgr:
        project = None
        dirty = False

    pg = ProtectionPage(_Mgr(), AppSettings())
    for prefix in ("secz", "rcls"):
        assert "coordinates" in getattr(pg, f"{prefix}_fields")


# ---------------------------------------------------------------------------
# ۱ و ۲) دستیار AI
# ---------------------------------------------------------------------------
def test_ai_settings_are_serialized_and_legacy_instructions_upgraded(tmp_path, monkeypatch):
    from app.ai.settings import DEFAULT_INSTRUCTIONS, LEGACY_INSTRUCTIONS

    assert "تحلیل" in DEFAULT_INSTRUCTIONS and "جدول" in DEFAULT_INSTRUCTIONS
    assert "تفسیر مهندسی" in DEFAULT_INSTRUCTIONS

    s = AppSettings()
    s.ai.provider = "openai"
    s.ai.models["openai"] = "gpt-4o-mini"
    s.ai.custom_base_url = "https://example.com/v1"
    s.ai.instructions = LEGACY_INSTRUCTIONS            # کاربر نسخهٔ قدیم را ذخیره کرده بود
    import app.core.settings as settings_mod
    monkeypatch.setattr(settings_mod, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings_mod, "SETTINGS_FILE", tmp_path / "settings.json")
    s.save()
    s2 = AppSettings.load()
    assert s2.ai.provider == "openai"
    assert s2.ai.models["openai"] == "gpt-4o-mini"
    assert s2.ai.custom_base_url == "https://example.com/v1"
    assert s2.ai.instructions == DEFAULT_INSTRUCTIONS   # ارتقای خودکار متن قدیمی


def test_ai_page_persists_on_edit(tmp_path, monkeypatch):
    from app.ui.shell.ai_page import AIPage

    saved = []

    class _Mgr:
        project = None
        image_path = staticmethod(lambda i: None)

    s = AppSettings()
    monkeypatch.setattr(s, "save", lambda: saved.append(True))
    page = AIPage(_Mgr(), s, lambda: None, lambda: None, lambda: {})
    page.refresh()
    page.ed_model.setText("my-model")                  # تایپ کاربر
    assert page._persist_timer.isActive()              # ذخیرهٔ تأخیری فعال شد
    page._persist_timer.stop()
    page._persist()
    assert saved and s.ai.model() == "my-model"


# ---------------------------------------------------------------------------
# ۷ و ۸) صفحهٔ مشترک فیدرها + حذف ورود دستی رله
# ---------------------------------------------------------------------------
def test_protection_study_page_has_no_network_tab():
    from app.ui.shell.study_pages import ProtectionStudyPage

    assert ProtectionStudyPage.TAB_KEYS == ("device", "settings")


def test_engineering_window_routes_network_to_shared_page():
    from app.ui.shell.engineering_window import ROUTES, TITLES

    assert ROUTES["recloser.network"] == ("protnet", None)
    assert ROUTES["sectionalizer.network"] == ("protnet", None)
    assert ROUTES["protnet"] == ("protnet", None)
    assert ROUTES["recloser"] == ("recloser", "device")
    assert "protnet" in TITLES


def test_idmt_import_fills_shared_network_and_head_relay(tmp_path):
    from app.core.idmt_bundle import apply_bundle_to_project
    from app.core.workspace import DEVICE_FEEDER_RELAY, workspace_from_project
    from test_v220_idmt_link import make_bundle

    p = Project(name="", report_type="recloser")
    p.recloser = RecloserInfo()
    ws = workspace_from_project(p)
    p._workspace = ws
    res = apply_bundle_to_project(p, make_bundle())
    feeder_name = p.recloser.feeder_name
    assert feeder_name
    fd = ws.common_network.feeder(feeder_name)
    assert fd is not None
    assert feeder_name in ws.scope("recloser") and feeder_name in ws.scope("sectionalizer")
    relay = fd.device(DEVICE_FEEDER_RELAY)
    assert relay is not None and relay.settings.any_function_set()
    assert any("شبکه مشترک" in a for a in res.applied)


# ---------------------------------------------------------------------------
# ۹) سه تب بخش‌های گزارش در تنظیمات
# ---------------------------------------------------------------------------
def test_settings_page_sections_split_into_three_tabs():
    from PySide6.QtWidgets import QTabWidget
    from app.core.report_sections import REPORT_SECTIONS
    from app.ui.settings_page import SettingsPage

    pg = SettingsPage(AppSettings())
    # همه بخش‌ها همچنان چک‌باکس دارند (ذخیره/بازیابی بدون تغییر)
    assert set(pg.chk_sections) == {k for k, _ in REPORT_SECTIONS}
    tabs = [w for w in pg.findChildren(QTabWidget)]
    # v2.4.0: تب چهارم «توسعه و اصلاح فیدر» اضافه شد (۳ تب قبلی + ۱)
    assert any(t.count() == 4 for t in tabs)
