# -*- coding: utf-8 -*-
"""v2.0.0 — Report Center / Composer: برنامه گزارش‌ها و ساختار بخش‌ها."""
from __future__ import annotations

from app.core.studies import StudyKind, StudySelection
from app.core.workspace import OUTPUT_COMBINED, OUTPUT_SEPARATE
from app.report.composer import (ProtectionReportGenerator, ReportComponent,
                                 ReportComposer, plan_reports)
from app.report.sections import Paragraph, ReportSection
from test_v200_protection_rules import _khalkhal, _salut

# ترتیب فصل‌ها مطابق «نمونه دفترچه مطالعه ریکلوزر و سکشنالایزر»:
# پیش‌فرض ۷ فصل (برای گزارش ترکیبی، فصل سکشنالایزر هم افزوده می‌شود)؛
# جمع‌بندی/پیشنهادها به‌صورت پیش‌فرض خاموش‌اند و از Report Center فعال می‌شوند
COMBINED_KEYS = ["prot_intro", "prot_network", "prot_existing", "prot_placement",
                 "prot_recloser", "prot_sectionalizer", "prot_coordination",
                 "prot_scenario"]
# حالت کامل با جمع‌بندی و پیشنهادها (وقتی در Report Center فعال شوند)
FULL_KEYS = COMBINED_KEYS + ["prot_conclusion", "prot_recommendation"]


def _enable_all_sections(ws):
    ws.report_prefs.disabled_sections = ["prot_trace"]


def test_plan_single_studies():
    assert [p.key for p in plan_reports(StudySelection(recloser=True))] == ["recloser"]
    assert [p.key for p in plan_reports(StudySelection(sectionalizer=True))] == ["sectionalizer"]
    assert [p.key for p in plan_reports(StudySelection(heavy=True))] == ["heavy"]


def test_plan_both_protection_studies_combined_or_separate():
    sel = StudySelection(recloser=True, sectionalizer=True)
    assert [p.key for p in plan_reports(sel, OUTPUT_COMBINED)] == ["combined_protection"]
    assert [p.key for p in plan_reports(sel, OUTPUT_SEPARATE)] == ["recloser", "sectionalizer"]


def test_plan_heavy_is_always_separate_from_protection():
    sel = StudySelection(heavy=True, recloser=True, sectionalizer=True)
    assert [p.key for p in plan_reports(sel, OUTPUT_COMBINED)] == ["heavy", "combined_protection"]


def test_combined_report_has_the_specified_sections_in_order():
    p, ws = _salut()
    plan = plan_reports(StudySelection(recloser=True, sectionalizer=True))[0]
    report = ReportComposer().build(plan, p, ws)
    assert [s.key for s in report.sections] == COMBINED_KEYS


def test_conclusion_and_recommendation_can_be_enabled_from_report_center():
    p, ws = _salut()
    _enable_all_sections(ws)
    plan = plan_reports(StudySelection(recloser=True, sectionalizer=True))[0]
    report = ReportComposer().build(plan, p, ws)
    assert [s.key for s in report.sections] == FULL_KEYS


def test_single_study_reports_skip_the_other_study_section():
    p, ws = _salut()
    keys = [s.key for s in ReportComposer().compose(p, ws, [StudyKind.RECLOSER]).sections]
    assert "prot_recloser" in keys and "prot_sectionalizer" not in keys
    keys = [s.key for s in ReportComposer().compose(p, ws, [StudyKind.SECTIONALIZER]).sections]
    assert "prot_sectionalizer" in keys and "prot_recloser" not in keys


def test_section_order_and_disable_are_extensible_via_prefs():
    p, ws = _salut()
    ws.report_prefs.section_order = ["prot_conclusion"]
    ws.report_prefs.disabled_sections = ["prot_scenario"]
    keys = [s.key for s in ReportComposer().compose(p, ws, [StudyKind.RECLOSER, StudyKind.SECTIONALIZER]).sections]
    assert keys[0] == "prot_conclusion" and "prot_scenario" not in keys


def test_register_custom_component():
    p, ws = _salut()
    _enable_all_sections(ws)
    comp = ReportComposer()
    comp.register(ReportComponent("prot_custom", "بخش سفارشی",
                                  lambda ctx: ReportSection("prot_custom", "بخش سفارشی",
                                                            [Paragraph("x")])),
                  before="prot_conclusion")
    keys = [s.key for s in comp.compose(p, ws, [StudyKind.RECLOSER]).sections]
    assert keys.index("prot_custom") == keys.index("prot_conclusion") - 1


def test_missing_data_is_reported_not_invented():
    p, ws = _khalkhal()                      # Counter/Shot سکشنالایزر ثبت نشده است
    _enable_all_sections(ws)
    report = ReportComposer().compose(p, ws, [StudyKind.RECLOSER, StudyKind.SECTIONALIZER])
    scenario = next(s for s in report.sections if s.key == "prot_scenario")
    text = " ".join(b.text for b in scenario.blocks if isinstance(b, Paragraph))
    assert "شمارندهٔ" not in text            # سکشنالایزر بدون Counter → ادعایی دربارهٔ آن نیست
    final = next(s for s in report.sections if s.key == "prot_recommendation")
    assert "منوط به تأیید مهندس" in " ".join(b.text for b in final.blocks)


def test_heavy_plan_requires_builder_and_delegates():
    p, ws = _salut()
    plan = plan_reports(StudySelection(heavy=True))[0]
    try:
        ReportComposer().build(plan, p, ws)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
    sentinel = object()
    assert ReportComposer().build(plan, p, ws, heavy_builder=lambda: sentinel) is sentinel


def test_pipeline_adapter_interface():
    p, ws = _salut()
    gen = ProtectionReportGenerator(p, None, None, kinds=[StudyKind.RECLOSER], workspace=ws)
    assert [s.key for s in gen.build_all()][0] == "prot_intro"
    assert isinstance(gen.report_warnings, list) and gen.findings == []


# ---------------------------------------------------------------------------
# تصاویر در گزارش‌های حفاظتی (بخش «تصاویر» دوباره فعال شد)
# ---------------------------------------------------------------------------
class _Img:
    def __init__(self, section_key="", kind="other", order=0, caption="", title="شکل", enabled=True):
        self.section_key, self.kind, self.order = section_key, kind, order
        self.caption, self.title, self.enabled = caption, title, enabled
        self.kind_label = "سایر"


def _with_images(p, images):
    p.__class__ = type("P", (p.__class__,), {"active_images": property(
        lambda self: [i for i in images if i.enabled])})
    return p


def test_images_are_placed_by_explicit_section_with_order_and_caption():
    from app.report.sections import FigureBlock
    p, ws = _salut()
    _enable_all_sections(ws)
    imgs = [_Img("prot_coordination", order=2, caption="دوم"),
            _Img("prot_coordination", order=1, caption="اول"),
            _Img("prot_conclusion", order=0, caption="جمع‌بندی")]
    p = _with_images(p, imgs)
    report = ReportComposer().compose(p, ws, [StudyKind.RECLOSER, StudyKind.SECTIONALIZER],
                                      image_resolver=lambda img: f"/x/{img.caption}.png")
    coord = next(s for s in report.sections if s.key == "prot_coordination")
    caps = [b.caption for b in coord.blocks if isinstance(b, FigureBlock)]
    # نمودارهای پیش‌فرض جریان–زمان (TCC) جدا از شکل‌های کاربر شمرده می‌شوند
    assert [c for c in caps if "جریان–زمان" not in c] == ["اول", "دوم"]
    concl = next(s for s in report.sections if s.key == "prot_conclusion")
    assert [b.caption for b in concl.blocks if isinstance(b, FigureBlock)] == ["جمع‌بندی"]


def test_images_default_section_by_kind_and_off_images_skipped():
    from app.report.sections import FigureBlock
    p, ws = _salut()
    p = _with_images(p, [_Img(kind="location", caption="محل"), _Img(kind="profile", caption="پروفیل"),
                         _Img(kind="network", caption="خاموش", enabled=False)])
    report = ReportComposer().compose(p, ws, [StudyKind.RECLOSER], image_resolver=lambda i: "/x.png")
    placement = next(s for s in report.sections if s.key == "prot_placement")
    assert [b.caption for b in placement.blocks if isinstance(b, FigureBlock)] == ["محل"]
    all_caps = [b.caption for s in report.sections for b in s.blocks if isinstance(b, FigureBlock)]
    assert "پروفیل" not in all_caps and "خاموش" not in all_caps   # نوع غیرمرتبط / خاموش درج نمی‌شود


def test_missing_image_file_is_skipped_not_fatal():
    from app.report.sections import FigureBlock
    p, ws = _salut()
    p = _with_images(p, [_Img("prot_intro", caption="x")])
    report = ReportComposer().compose(p, ws, [StudyKind.RECLOSER], image_resolver=lambda i: None)
    caps = [b.caption for s in report.sections for b in s.blocks if isinstance(b, FigureBlock)]
    assert "x" not in caps                       # شکل کاربر بدون فایل درج نمی‌شود
    assert all("جریان–زمان" in c for c in caps)   # فقط نمودارهای پیش‌فرض TCC


def test_protection_sections_are_available_for_image_placement():
    from app.core.report_sections import REPORT_SECTIONS
    keys = [k for k, _t in REPORT_SECTIONS]
    for k in COMBINED_KEYS:
        assert k in keys
