# -*- coding: utf-8 -*-
"""v2.0.0 — Guided Flow، ردیابی خطا، موتور متن و حذف نیاز «نام متقاضی» در مطالعات حفاظتی."""
from __future__ import annotations

from app.core.guided_flow import compute_flow, next_step, STEP_KEYS
from app.core.models import Feeder, Project, RecloserInfo, SectionalizerInfo
from app.core.protection_models import FunctionSetting as F, ProtectionSettings
from app.core.settings import AppSettings
from app.core.studies import StudyKind, StudySelection
from app.core.validation import ERROR, WARNING, validate_project
from app.core.workspace import workspace_from_project
from app.report.composer import ReportComposer
from app.report.protection_narrative import NarrativeEngine, RefParagraph
from app.report.sections import Paragraph, TableSpec
from app.rules.domains import evaluate_study
from app.rules.trace import trace_link
from test_v200_protection_rules import _khalkhal, _salut


# ---------------------------------------------------------------------------
# اعتبارسنجی: نام متقاضی برای مطالعات حفاظتی لازم نیست
# ---------------------------------------------------------------------------
def _prot_project(rtype):
    p = Project(name="پ", report_number="R-1", date_jalali="1405/01/01", report_type=rtype)
    return p


def test_protection_validation_does_not_require_applicant_name():
    for rtype in ("recloser", "sectionalizer", "combined_protection"):
        p = _prot_project(rtype)
        assert p.applicant_name == ""
        items = validate_project(p, AppSettings())
        assert not any(i.status == ERROR for i in items), rtype
        assert not any("متقاضی" in i.message for i in items)


def test_protection_validation_errors_link_to_exact_field():
    p = Project(name="پ", report_type="recloser")
    items = [i for i in validate_project(p, AppSettings()) if i.status == ERROR]
    assert {(i.target, i.field) for i in items} == {("project", "ed_number"), ("project", "ed_date")}


def test_protection_warning_links_to_settings_field():
    p = _prot_project("recloser")
    w = [i for i in validate_project(p, AppSettings()) if i.status == WARNING and i.field == "f51.pickup_a"]
    assert w and w[0].target == "recloser.settings"


# ---------------------------------------------------------------------------
# ردیابی دقیق: Rule ← محل اصلاح + منبع
# ---------------------------------------------------------------------------
def test_missing_data_result_links_to_input_field():
    p = Project(name="x", feeders=[Feeder(name="F1")])
    ws = workspace_from_project(p)
    res = {r.rule_key: r for r in evaluate_study(p, ws, StudyKind.RECLOSER)}
    link = trace_link(res["REC-LOC-MISSING"], StudyKind.RECLOSER)
    assert (link.route, link.field) == ("recloser.device", "installation_location")
    assert trace_link(res["PCM-FAULT-MISSING"], StudyKind.SECTIONALIZER).route == "sectionalizer.network"
    assert "recloser.device" in link.to_text() and "REC-LOC-MISSING" in link.to_text()


def test_computed_result_links_to_function_and_carries_source_and_values():
    p, ws = _khalkhal()
    p.recloser.settings.f51 = F("NI", 320, 5, "percent")
    res = {r.rule_key: r for r in evaluate_study(p, ws, StudyKind.RECLOSER)}
    link = trace_link(res["REC-COORD-51-BAD"], StudyKind.RECLOSER)
    assert (link.route, link.field) == ("recloser.settings", "f51.pickup_a")
    assert "دفترچه" in link.source and link.source_page
    link50n = trace_link(next(r for r in evaluate_study(p, ws, StudyKind.RECLOSER)
                              if r.rule_key.startswith("REC-COORD-50N")), StudyKind.RECLOSER)
    assert link50n.field == "f50n.pickup_a"                      # 50N قبل از 50 تطبیق می‌خورد


# ---------------------------------------------------------------------------
# قواعد فیزیکی تازه (بدون آستانهٔ ساختگی)
# ---------------------------------------------------------------------------
def test_physical_checks_pickup_vs_load_and_fault_currents():
    p, ws = _khalkhal()
    p.recloser.load_current_a = 300.0                            # Pickup 250 < بار
    p.recloser.min_fault_current_ka = 0.2                        # Pickup 250 ≥ حداقل خطا 200 A
    ws.common_network.feeders[0].max_fault_current_ka = 0.5      # Pickup آنی 600 ≥ 500 A
    res = {r.rule_key: r for r in evaluate_study(p, ws, StudyKind.RECLOSER)}
    assert res["REC-PICKUP-BELOW-LOAD"].status == "FAIL"
    assert res["REC-PICKUP-ABOVE-MINFAULT"].status == "FAIL"
    assert res["REC-INST-ABOVE-MAXFAULT"].status == "WARNING"


def test_physical_checks_silent_when_data_is_fine_or_missing():
    p, ws = _khalkhal()
    res = {r.rule_key for r in evaluate_study(p, ws, StudyKind.RECLOSER)}
    assert not {"REC-PICKUP-BELOW-LOAD", "REC-PICKUP-ABOVE-MINFAULT", "REC-INST-ABOVE-MAXFAULT"} & res
    p.recloser.load_current_a, p.recloser.min_fault_current_ka = 100.0, 1.2
    ws.common_network.feeders[0].max_fault_current_ka = 6.0
    res = {r.rule_key for r in evaluate_study(p, ws, StudyKind.RECLOSER)}
    assert not {"REC-PICKUP-BELOW-LOAD", "REC-PICKUP-ABOVE-MINFAULT", "REC-INST-ABOVE-MAXFAULT"} & res


# ---------------------------------------------------------------------------
# موتور متن (Narrative)
# ---------------------------------------------------------------------------
def _compose(p, ws, kinds, **kw):
    return ReportComposer().compose(p, ws, kinds, **kw)


def _texts(report, key):
    sec = next(s for s in report.sections if s.key == key)
    return [b for b in sec.blocks if isinstance(b, Paragraph)]


def test_narrative_uses_data_and_states_missing_explicitly():
    p, ws = _khalkhal()
    f = ws.common_network.feeders[0]
    f.max_fault_current_ka, f.sc_1ph_ka, f.has_dg = 6.0, 2.0, False
    net = " ".join(b.text for b in _texts(_compose(p, ws, [StudyKind.RECLOSER]), "prot_network"))
    assert "6 کیلوآمپر" in net and "تکفاز 2" in net and "منبع تولید پراکنده وجود ندارد" in net
    p2, ws2 = _khalkhal()
    net2 = " ".join(b.text for b in _texts(_compose(p2, ws2, [StudyKind.RECLOSER]), "prot_network"))
    assert "ثبت نشده" in net2 and "مشخص نشده" in net2            # SC پست و DG در دسترس نیست


def test_narrative_coordination_summary_and_references():
    p, ws = _khalkhal()
    rep = _compose(p, ws, [StudyKind.RECLOSER])
    paras = _texts(rep, "prot_coordination")
    summary = next(b for b in paras if getattr(b, "template_id", "") == "coordination.all_ok_rec")
    assert "4 تابع" in summary.text and any(r.startswith("REC-COORD") for r in summary.refs)
    p.recloser.settings.f51 = F("NI", 320, 5, "percent")
    bad = next(b for b in _texts(_compose(p, ws, [StudyKind.RECLOSER]), "prot_coordination")
               if getattr(b, "template_id", "") == "coordination.bad_rec")
    assert "1 تابع از 4" in bad.text


def test_narrative_sectionalizer_reference_and_counter():
    p, ws = _salut()
    rep = _compose(p, ws, [StudyKind.RECLOSER, StudyKind.SECTIONALIZER])
    secz = " ".join(b.text for b in _texts(rep, "prot_sectionalizer"))
    assert "ریکلوزر مرجع" in secz and "شمارندهٔ سکشنالایزر 1" in secz and "برابر است" in secz
    coord = " ".join(b.text for b in _texts(rep, "prot_coordination"))
    assert "8 مورد بررسی‌شده، 8 مورد با نمونهٔ مرجع مطابقت" in coord


def test_narrative_conclusion_lists_failures_missing_data_and_thresholds():
    p, ws = _khalkhal()
    p.recloser.settings.f51 = F("NI", 320, 5, "percent")
    text = " ".join(b.text for b in _texts(_compose(p, ws, [StudyKind.RECLOSER]), "prot_conclusion"))
    assert "عدم انطباق" in text and "حداقل زمان Reclaim" in text
    assert "داده‌های زیر ثبت شود" in text                         # SC/بار/DG ... ناموجود


def test_narrative_never_invents_numbers_without_data():
    p = Project(name="x", feeders=[Feeder(name="F1")])
    ws = workspace_from_project(p)
    rep = _compose(p, ws, [StudyKind.RECLOSER])
    scen = " ".join(b.text for b in _texts(rep, "prot_scenario"))
    assert "ثبت نشده" in scen and "شات" not in scen.replace("(Shot/Counter)", "")


def test_templates_are_editable_without_code_changes(tmp_path):
    import json
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"prot_intro": [{"id": "intro.x", "when": "rec_selected",
                                                "text": "متن سفارشی برای {feeders_text}"}]}),
                    encoding="utf-8")
    p, ws = _khalkhal()
    rep = ReportComposer(narrative=NarrativeEngine(path)).compose(p, ws, [StudyKind.RECLOSER])
    assert [b.text for b in _texts(rep, "prot_intro")] == ["متن سفارشی برای F4 خلخال"]


def test_missing_template_file_degrades_to_findings_only(tmp_path):
    p, ws = _khalkhal()
    rep = ReportComposer(narrative=NarrativeEngine(tmp_path / "none.json")).compose(
        p, ws, [StudyKind.RECLOSER])
    assert any(s.key == "prot_coordination" for s in rep.sections)   # گزارش ساخته می‌شود


# ---------------------------------------------------------------------------
# پیوست ردیابی، هشدار نقص‌ها و متن دستی
# ---------------------------------------------------------------------------
def test_trace_appendix_is_off_by_default_and_lists_sources_when_enabled():
    p, ws = _khalkhal()
    keys = [s.key for s in _compose(p, ws, [StudyKind.RECLOSER]).sections]
    assert "prot_trace" not in keys
    ws.report_prefs.disabled_sections = []
    rep = _compose(p, ws, [StudyKind.RECLOSER])
    sec = next(s for s in rep.sections if s.key == "prot_trace")
    table = next(b for b in sec.blocks if isinstance(b, TableSpec))
    assert table.header_rows[0][0] == "Rule" and any(row[0].startswith("PCM-") for row in table.body_rows)
    assert all(row[5] for row in table.body_rows)                  # محل اصلاح


def test_report_is_generated_with_unresolved_errors_and_flags_them():
    p, ws = _khalkhal()
    rep = _compose(p, ws, [StudyKind.RECLOSER], notices=["شماره گزارش ثبت نشده است."])
    assert rep.sections[0].key == "prot_notice"
    assert any("شماره گزارش" in b.text for b in rep.sections[0].blocks if isinstance(b, Paragraph))


def test_manual_text_replaces_paragraphs_but_keeps_tables():
    p, ws = _khalkhal()
    p.manual_texts = {"prot_recloser": "متن اصلاح‌شدهٔ مهندس.\nخط دوم."}
    sec = next(s for s in _compose(p, ws, [StudyKind.RECLOSER]).sections if s.key == "prot_recloser")
    texts = [b.text for b in sec.blocks if isinstance(b, Paragraph)]
    assert texts == ["متن اصلاح‌شدهٔ مهندس.", "خط دوم."]
    assert any(isinstance(b, TableSpec) for b in sec.blocks) and sec.manual is True


# ---------------------------------------------------------------------------
# Guided Flow
# ---------------------------------------------------------------------------
def _flow(p, ws, **kw):
    return compute_flow(p, ws, AppSettings(), **kw)


def test_flow_has_seven_steps_and_locks_following_steps():
    p = Project(name="x")
    ws = workspace_from_project(p)
    ws.selection = StudySelection(recloser=True)
    steps = _flow(p, ws)
    assert [s.key for s in steps] == list(STEP_KEYS) and [s.number for s in steps] == list(range(1, 8))
    assert steps[0].unlocked and not steps[0].complete and not steps[1].unlocked
    assert all(not s.unlocked for s in steps[1:])
    assert next_step(steps).key == "project"
    assert {(r.target, r.field) for r in steps[0].missing} == {("project", "ed_number"), ("project", "ed_date")}


def test_flow_unlocks_next_step_when_requirements_met():
    p = Project(name="x", report_number="R1", date_jalali="1405/01/01")
    ws = workspace_from_project(p)
    ws.selection = StudySelection(recloser=True)
    steps = _flow(p, ws)
    assert steps[0].complete and steps[1].unlocked and not steps[1].complete and not steps[2].unlocked
    labels = [r.label for r in steps[1].missing]
    assert any("فیدر" in l for l in labels) and any("اتصال کوتاه" in l for l in labels)
    assert any("Pickup" in l for l in labels) and all(r.study == "recloser" for r in steps[1].missing)


def test_flow_requirements_follow_selected_studies():
    p, ws = _khalkhal()
    p.report_number, p.date_jalali = "R1", "1405/01/01"
    ws.selection = StudySelection(sectionalizer=True)
    ws.add_to_scope("sectionalizer", "F4 خلخال")
    reqs = _flow(p, ws)[1].requirements
    assert reqs and all(r.study == "sectionalizer" for r in reqs)
    ws.selection = StudySelection(heavy=True)
    heavy = _flow(p, ws)[1].requirements
    assert all(r.study == "heavy" for r in heavy)


def test_flow_override_unlocks_next_step_without_completing():
    p = Project(name="x")
    ws = workspace_from_project(p)
    ws.selection = StudySelection(recloser=True)
    ws.override("project")
    steps = _flow(p, ws)
    assert not steps[0].complete and steps[0].overridden and steps[0].passed
    assert steps[1].unlocked and steps[0].state == "warning"
    ws.override("project", False)
    assert not _flow(p, ws)[1].unlocked


def test_flow_full_completion_and_manual_steps():
    p, ws = _khalkhal()
    p.report_number, p.date_jalali = "R1", "1405/01/01"
    p.recloser.min_fault_current_ka = 1.2
    ws.selection = StudySelection(recloser=True)
    ws.add_to_scope("recloser", "F4 خلخال")
    ws.common_network.feeders[0].max_fault_current_ka = 6.0
    steps = _flow(p, ws, validation_errors=0)
    assert steps[1].complete and steps[2].complete and steps[3].unlocked and not steps[3].complete
    for k in ("analysis", "review", "preview"):
        ws.mark_done(k)
    steps = _flow(p, ws, validation_errors=0)
    assert all(s.complete for s in steps[:6]) and steps[6].unlocked and not steps[6].complete
    assert next_step(steps).key == "generate"
    assert _flow(p, ws, validation_errors=0, report_generated=True)[6].complete


def test_flow_state_roundtrips_in_workspace(tmp_path):
    from app.core.workspace import Workspace, load_workspace
    ws = workspace_from_project(Project(name="x"))
    ws.mark_done("analysis")
    ws.mark_done("analysis")
    ws.override("review")
    ws.clear_done("preview")
    ws.save(tmp_path)
    back = load_workspace(tmp_path, Project(name="x"))
    assert back.flow_done == ["analysis"] and back.flow_overrides == ["review"]
    assert Workspace.from_dict({}).flow_done == []                # پروژهٔ قدیمی


# ---------------------------------------------------------------------------
# نوار راهنما، قفل Explorer، تصاویر وابسته به مطالعه، گزارش با خطا
# ---------------------------------------------------------------------------
def test_guide_model_points_to_first_missing_requirement():
    from app.core.guided_flow import guide_model
    p = Project(name="x")
    ws = workspace_from_project(p)
    ws.selection = StudySelection(recloser=True)
    gm = guide_model(_flow(p, ws), ws.selection)
    assert gm.step.key == "project" and gm.goto == "project" and gm.goto_field == "ed_number"
    assert gm.can_override and len(gm.links) == 2 and "گام 1 از 7" in gm.title


def test_guide_model_empty_and_finished():
    from app.core.guided_flow import guide_model
    assert guide_model([], None).title == ""                      # بدون پروژه: نوار پنهان
    p, ws = _khalkhal()
    p.report_number, p.date_jalali = "R1", "1405/01/01"
    p.recloser.min_fault_current_ka = 1.2
    ws.selection = StudySelection(recloser=True)
    ws.add_to_scope("recloser", "F4 خلخال")
    ws.common_network.feeders[0].max_fault_current_ka = 6.0
    for k in ("analysis", "review", "preview"):
        ws.mark_done(k)
    steps = _flow(p, ws, validation_errors=0, report_generated=True)
    assert guide_model(steps, ws.selection).finished


def test_guide_offers_protection_ack_at_review_step():
    from app.core.guided_flow import guide_model
    p, ws = _khalkhal()
    p.report_number, p.date_jalali = "R1", "1405/01/01"
    p.recloser.min_fault_current_ka = 1.2
    ws.selection = StudySelection(recloser=True)
    ws.add_to_scope("recloser", "F4 خلخال")
    ws.common_network.feeders[0].max_fault_current_ka = 6.0
    ws.mark_done("analysis")
    gm = guide_model(_flow(p, ws, validation_errors=0), ws.selection)
    assert gm.step.key == "review" and gm.needs_protection_ack and gm.goto in ("recloser.settings",)


def test_tree_locks_steps_that_are_not_open_yet():
    from app.core.project_tree import build_project_tree
    p = Project(name="x")
    ws = workspace_from_project(p)
    ws.selection = StudySelection(recloser=True)
    tree = build_project_tree(p, ws, {"project": "current", "input": "locked"},
                              {"input": "ابتدا گام «اطلاعات پروژه» را کامل کنید.",
                               "analysis": "x"})
    assert not tree.find("step.project").locked
    n = tree.find("step.input")
    assert n.locked and "اطلاعات پروژه" in n.tooltip and n.label.startswith("🔒 2.")
    assert tree.find("recloser.network").locked and tree.find("images").locked   # فرزندان هم
    assert tree.find("step.analysis").locked and not tree.find("settings").locked


def test_image_sections_and_kinds_follow_selected_studies():
    from app.core.models import IMAGE_KINDS
    from app.core.report_sections import image_kinds_for_selection, sections_for_selection
    rec = StudySelection(recloser=True)
    keys = [k for k, _ in sections_for_selection(rec)]
    assert "prot_recloser" in keys and "prot_sectionalizer" not in keys and "prot_trace" not in keys
    assert not any(k.startswith("secz_") for k in keys) and "loadflow_before" not in keys
    kinds = image_kinds_for_selection(rec, IMAGE_KINDS)
    assert "tcc" in kinds and "single_line" in kinds and "profile" not in kinds and "before" not in kinds
    heavy_keys = [k for k, _ in sections_for_selection(StudySelection(heavy=True))]
    assert heavy_keys and not any(k.startswith("prot_") for k in heavy_keys)
    heavy_kinds = image_kinds_for_selection(StudySelection(heavy=True), IMAGE_KINDS)
    assert "profile" in heavy_kinds and "tcc" not in heavy_kinds
    both = [k for k, _ in sections_for_selection(StudySelection(heavy=True, recloser=True, sectionalizer=True))]
    assert "prot_recloser" in both and "prot_sectionalizer" in both and len(both) > len(heavy_keys)
    assert [k for k, _ in sections_for_selection(None)] == [k for k, _ in __import__(
        "app.core.report_sections", fromlist=["x"]).REPORT_SECTIONS]


def test_unresolved_errors_section_is_added_for_any_report_type():
    from app.report.pipeline import unresolved_errors_section
    p = Project(name="x", report_type="recloser")
    sec = unresolved_errors_section(p, AppSettings())
    assert sec is not None and sec.key == "notice_unresolved"
    texts = " ".join(b.text for b in sec.blocks)
    assert "شماره گزارش" in texts and "تاریخ گزارش" in texts
    p.report_number, p.date_jalali = "R1", "1405/01/01"
    assert unresolved_errors_section(p, AppSettings()) is None


def test_sectionalizer_only_report_goes_through_composer_with_narrative(tmp_path):
    from app.report.pipeline import build_sections
    from app.report.template_manager import TemplateManager
    from app.rules.rule_engine import RuleEngine
    p, ws = _salut()
    p.report_type, p.report_number, p.date_jalali = "sectionalizer", "R1", "1405/01/01"
    p._workspace = ws
    rep = build_sections(p, AppSettings(include_appendices=False), TemplateManager(), RuleEngine(), tmp_path)
    assert rep.sections[0].key == "prot_intro" and "prot_sectionalizer" in [s.key for s in rep.sections]
    text = " ".join(b.text for s in rep.sections for b in s.paragraphs())
    assert "ریکلوزر مرجع" in text


def test_heavy_flow_requires_applicant_and_power_on_the_applicant_page():
    p = Project(name="x", report_number="R1", date_jalali="1405/01/01")
    ws = workspace_from_project(p)
    ws.selection = StudySelection(heavy=True)
    reqs = {r.label: r for r in _flow(p, ws)[1].requirements}
    assert reqs["متقاضی سنگین: نام متقاضی"].target == "applicant" and not reqs["متقاضی سنگین: نام متقاضی"].done
    assert reqs["متقاضی سنگین: نام متقاضی"].field == "ed_applicant"
    assert any("توان فعلی" in l for l in reqs)                    # نوع پیش‌فرض: افزایش قدرت
    p.applicant_name, p.requested_power_kw, p.existing_power_kw = "شرکت", 2000.0, 1000.0
    done = {r.label: r.done for r in _flow(p, ws)[1].requirements}
    assert done["متقاضی سنگین: نام متقاضی"] and done["متقاضی سنگین: توان درخواستی/جدید (kW)"]
