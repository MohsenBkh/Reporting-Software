# -*- coding: utf-8 -*-
"""تست‌های v2.6.0 — مطالعه «جایابی سکسیونر» + ورود eens_report.json.

۱) مدل DisconnectorInfo و ذخیره/بازخوانی پروژه.
۲) ماژول ورود eens_report.json (SwitchLoc) و نگاشت فیلدها.
۳) بخش‌های dx_* گزارش‌ساز: متن‌های ثابت قالب Disconnector Format.json عیناً،
   متغیرهای آکولادی از ورودی کاربر/فایل، خالی = «ناموجود».
۴) صفحه UI، اعتبارسنجی، Guided Flow، درخت پروژه و خروجی Word.
"""
from __future__ import annotations

import dataclasses
import json
import re
import zipfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

QApplication.instance() or QApplication([])

REPO = Path(__file__).resolve().parents[1]
EENS_FILE = REPO / "eens_report.json"

from app.core.eens_import import (EENSImportError, apply_eens_to_disconnector,  # noqa: E402
                                  load_eens_report)
from app.core.models import DisconnectorInfo, Project, project_from_dict  # noqa: E402
from app.core.settings import AppSettings  # noqa: E402
from app.core.studies import STUDY_LABELS_FA, StudyKind, StudySelection  # noqa: E402
from app.core.workspace import workspace_from_project  # noqa: E402
from app.report.composer import ReportComposer, plan_reports  # noqa: E402


def _dx_project(**dx_fields) -> Project:
    p = Project(name="تست سکسیونر", report_type="disconnector", office="خلخال")
    for k, v in dx_fields.items():
        setattr(p.disconnector, k, v)
    return p


def _compose(p: Project):
    return ReportComposer().compose(p, workspace_from_project(p),
                                    [StudyKind.DISCONNECTOR])


def _sec(report, key):
    return next((s for s in report.sections if s.key == key), None)


def _texts(sec) -> str:
    from app.report.sections import Paragraph
    return "\n".join(b.text for b in sec.blocks if isinstance(b, Paragraph))


# ---------------------------------------------------------------------------
# ۱) مدل و ذخیره/بازخوانی
# ---------------------------------------------------------------------------
class TestModel:
    def test_study_kind_registered(self):
        assert StudyKind.DISCONNECTOR.value == "disconnector"
        assert STUDY_LABELS_FA[StudyKind.DISCONNECTOR] == "جایابی سکسیونر"
        sel = StudySelection(disconnector=True)
        assert sel.kinds() == [StudyKind.DISCONNECTOR]

    def test_project_roundtrip(self):
        p = _dx_project(dx_kind="موتوردار", eens_base_mwh=562.1667,
                        eens_assumptions=["فرض ۱"], eens_imported=True)
        q = project_from_dict(dataclasses.asdict(p))
        assert isinstance(q.disconnector, DisconnectorInfo)
        assert q.disconnector.dx_kind == "موتوردار"
        assert q.disconnector.eens_base_mwh == 562.1667
        assert q.disconnector.eens_assumptions == ["فرض ۱"]
        assert q.disconnector.eens_imported is True

    def test_report_coding_pd(self):
        from app.core.report_coding import REPORT_TYPE_TO_CODE
        assert REPORT_TYPE_TO_CODE["disconnector"] == "PD"

    def test_report_types(self):
        from app.core.report_types import (booklet_title, header_title,
                                           is_implemented)
        assert is_implemented("disconnector")
        assert booklet_title("disconnector") == "دفترچه مطالعات جایابی تجهیزات و هماهنگی حفاظتی"
        assert header_title("disconnector") == "دفترچه مطالعه جایابی سکسیونر"


# ---------------------------------------------------------------------------
# ۲) ورود eens_report.json
# ---------------------------------------------------------------------------
class TestEENSImport:
    def test_load_real_file(self):
        r = load_eens_report(EENS_FILE)
        assert r.algo_version.startswith("SwitchLoc")
        assert len(r.feeders) == 1
        f = r.feeders[0]
        assert f.feeder_key == "F10 - RADIO"
        assert f.failure_rate_per_year == 146.0
        assert f.repair_time_min == 43.54
        assert f.baseline_eens_mwh == 562.1667
        assert f.best_eens_mwh == 367.8555
        assert f.improvement_percent == 34.565
        assert f.selected_count == 1
        assert len(r.assumptions) == 7

    def test_apply_matches_file(self):
        dx = DisconnectorInfo()
        key = apply_eens_to_disconnector(dx, load_eens_report(EENS_FILE))
        assert key == "F10 - RADIO"
        assert dx.feeder_key == "F10 - RADIO"
        assert dx.eens_base_mwh == 562.1667
        assert dx.eens_after_mwh == 367.8555
        assert dx.improvement_pct == 34.565
        assert dx.switch_count == 1
        assert dx.line_length_km == pytest.approx(37.919576)
        assert dx.covered_load_kw == pytest.approx(7094.756901)
        assert dx.transient_rate_per_year is not None
        assert dx.eens_imported is True
        # برچسب «F10 - RADIO · خط هوایی · @ 750552, 4379268 m» تجزیه می‌شود
        assert dx.device_note == "خط هوایی"
        assert "750552" in dx.device_coords
        # نوع سکسیونر خودکار پر نمی‌شود (با عنوان بخش ۴ تکرار می‌شد)
        assert dx.dx_kind == ""

    def test_user_inputs_not_overwritten(self):
        dx = DisconnectorInfo(device_note="کابل زمینی", dx_kind="گازی",
                              optimal_location="ابتدای روستا")
        apply_eens_to_disconnector(dx, load_eens_report(EENS_FILE))
        assert dx.device_note == "کابل زمینی"
        assert dx.dx_kind == "گازی"
        assert dx.optimal_location == "ابتدای روستا"

    def test_invalid_files(self, tmp_path):
        with pytest.raises(EENSImportError):
            load_eens_report(tmp_path / "missing.json")
        bad = tmp_path / "bad.json"
        bad.write_text("{ broken", encoding="utf-8")
        with pytest.raises(EENSImportError):
            load_eens_report(bad)
        nostudy = tmp_path / "nostudy.json"
        nostudy.write_text(json.dumps({"x": 1}), encoding="utf-8")
        with pytest.raises(EENSImportError, match="study"):
            load_eens_report(nostudy)

    def test_feeder_lookup(self):
        r = load_eens_report(EENS_FILE)
        assert r.feeder("").feeder_key == "F10 - RADIO"
        assert r.feeder("F10 - RADIO") is not None
        assert r.feeder("ناشناخته") is None
        with pytest.raises(EENSImportError):
            apply_eens_to_disconnector(DisconnectorInfo(), r, "ناشناخته")


# ---------------------------------------------------------------------------
# ۳) بخش‌های گزارش
# ---------------------------------------------------------------------------
class TestComposer:
    def test_plan_reports(self):
        plans = plan_reports(StudySelection(disconnector=True))
        assert [p.key for p in plans] == ["disconnector"]
        assert plans[0].kinds == [StudyKind.DISCONNECTOR]

    def test_section_order_matches_format(self):
        rep = _compose(_dx_project())
        assert [s.key for s in rep.sections] == [
            "dx_intro", "dx_network", "dx_switching", "dx_placement", "dx_coverage"]

    def test_fixed_texts_verbatim(self):
        """متن‌های ثابت قالب عیناً درج می‌شوند (TAV111-03/00 و TAV122-02/00 و ۷ قاعده)."""
        fmt = json.loads((REPO / "Disconnector Format.json").read_text(encoding="utf-8"))
        rep = _compose(_dx_project())
        intro = _texts(_sec(rep, "dx_intro"))
        assert fmt["sections"]["introduction"]["content"][0] in intro
        sw = _texts(_sec(rep, "dx_switching"))
        assert fmt["sections"]["switching_requirements"]["intro"] in sw
        for rule in fmt["sections"]["switching_requirements"]["rules"]:
            assert rule in sw
        assert fmt["sections"]["switching_requirements"]["influencing_parameters"] in sw
        pl = _texts(_sec(rep, "dx_placement"))
        assert fmt["sections"]["sectioner_placement"]["methodology"] in pl

    def test_placeholders_filled_from_user(self):
        p = _dx_project(dx_kind="موتوردار", location="روستای رادیو", county="خلخال",
                        feeder_name="F10 - RADIO", post_name="پست خلخال",
                        voltage_kv=20.0, load_current_a=205.0,
                        dg_status="منبع تولید پراکنده وجود ندارد")
        rep = _compose(p)
        intro = _texts(_sec(rep, "dx_intro"))
        assert "سکسیونر موتوردار" in intro
        assert "روستای رادیو" in intro and "خلخال" in intro
        net = _sec(rep, "dx_network")
        txt = _texts(net)
        assert "سطح ولتاژ 20 کیلوولت" in txt and "205 آمپر" in txt
        from app.report.sections import TableSpec
        tables = [b for b in net.blocks if isinstance(b, TableSpec)]
        assert tables and tables[0].body_rows[0][0] == "F10 - RADIO"

    def test_missing_values_as_namojood(self):
        rep = _compose(_dx_project())
        assert "ناموجود" in _texts(_sec(rep, "dx_network"))
        assert "ناموجود" in _texts(_sec(rep, "dx_placement"))

    def test_placement_matches_eens_file(self):
        p = _dx_project()
        apply_eens_to_disconnector(p.disconnector, load_eens_report(EENS_FILE))
        rep = _compose(p)
        pl = _texts(_sec(rep, "dx_placement"))
        for v in ("562.1667", "367.8555", "34.565", "146", "43.54",
                  "37.9196", "7094.7569", "F10 - RADIO"):
            assert v in pl, v
        assert "eens_report.json" in pl          # ردپای ورود فایل
        from app.report.sections import TableSpec
        t2 = [b for b in _sec(rep, "dx_placement").blocks if isinstance(b, TableSpec)][0]
        assert t2.body_rows[0][3] == "562.1667"
        assert t2.body_rows[0][4] == "367.8555"
        assert t2.body_rows[0][5] == "34.565"

    def test_coverage_section(self):
        p = _dx_project(province="اردبیل", coverage_areas="روستای رادیو و جاده",
                        coverage_status="مطلوب", dx_kind="موتوردار",
                        location="روستای رادیو")
        rep = _compose(p)
        cov = _sec(rep, "dx_coverage")
        txt = _texts(cov)
        assert "ایرانسل" in txt and "همراه اول" in txt and "مطلوب" in txt
        from app.report.sections import TableSpec
        t3 = [b for b in cov.blocks if isinstance(b, TableSpec)][0]
        assert t3.body_rows[0] == ["اردبیل", "روستای رادیو و جاده", "مطلوب"]

    def test_manual_intro_overrides(self):
        rep = _compose(_dx_project(intro="متن سفارشی مقدمه"))
        assert _texts(_sec(rep, "dx_intro")).strip() == "متن سفارشی مقدمه"

    def test_word_output(self, tmp_path):
        from app.report.word_generator import WordGenerator
        p = _dx_project(dx_kind="موتوردار", location="روستای رادیو",
                        county="خلخال", feeder_name="F10 - RADIO")
        apply_eens_to_disconnector(p.disconnector, load_eens_report(EENS_FILE))
        rep = _compose(p)
        out = tmp_path / "dx.docx"
        WordGenerator(p, AppSettings()).generate(rep, out)
        xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8")
        paras = ["".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", px))
                 for px in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)]
        joined = "\n".join(paras)
        for t in ("TAV122-02/00", "562.1667", "367.8555", "F10 - RADIO",
                  "دفترچه مطالعات جایابی تجهیزات و هماهنگی حفاظتی"):
            assert t in joined, t


# ---------------------------------------------------------------------------
# ۴) اعتبارسنجی، Guided Flow، درخت، بخش‌ها و UI
# ---------------------------------------------------------------------------
class TestIntegration:
    def test_validation_warns_without_import(self):
        from app.core.validation import WARNING, validate_project
        items = validate_project(_dx_project(), AppSettings())
        msgs = [i.message for i in items if i.status == WARNING]
        assert any("eens_report.json" in m for m in msgs)

    def test_validation_ok_after_import(self):
        from app.core.validation import OK, validate_project
        p = _dx_project(feeder_name="F10", location="روستا",
                        voltage_kv=20.0, load_current_a=205.0, coverage_status="مطلوب")
        apply_eens_to_disconnector(p.disconnector, load_eens_report(EENS_FILE))
        items = validate_project(p, AppSettings())
        ok = [i.message for i in items if i.status == OK]
        assert any("eens_report.json" in m for m in ok)

    def test_guided_flow_requirement(self):
        from app.core.guided_flow import input_requirements
        p = _dx_project(feeder_name="F10", location="روستا")
        ws = workspace_from_project(p)
        ws.selection = StudySelection(disconnector=True)
        reqs = [r for r in input_requirements(p, ws, AppSettings())
                if r.study == "disconnector"]
        assert len(reqs) == 2
        assert reqs[0].done and not reqs[1].done            # EENS هنوز وارد نشده
        apply_eens_to_disconnector(p.disconnector, load_eens_report(EENS_FILE))
        reqs = [r for r in input_requirements(p, ws, AppSettings())
                if r.study == "disconnector"]
        assert all(r.done for r in reqs)

    def test_project_tree_and_status(self):
        from app.core.project_tree import ST_COMPLETE, ST_INCOMPLETE, build_project_tree, study_status
        p = _dx_project(feeder_name="F10")
        ws = workspace_from_project(p)
        ws.selection = StudySelection(disconnector=True)
        tree = build_project_tree(p, ws)
        keys = []
        def walk(n):
            keys.append(n.key)
            for c in n.children:
                walk(c)
        walk(tree)
        assert "input.disconnector" in keys
        assert study_status(p, ws, StudyKind.DISCONNECTOR) == ST_INCOMPLETE
        apply_eens_to_disconnector(p.disconnector, load_eens_report(EENS_FILE))
        assert study_status(p, ws, StudyKind.DISCONNECTOR) == ST_COMPLETE

    def test_report_sections_for_selection(self):
        from app.core.report_sections import sections_for_selection
        keys = [k for k, _l in sections_for_selection(StudySelection(disconnector=True))]
        assert keys == ["dx_intro", "dx_network", "dx_switching",
                        "dx_placement", "dx_coverage"]

    def test_default_image_sections(self):
        from app.core.report_sections import DISCONNECTOR_DEFAULT_SECTION_BY_KIND
        assert DISCONNECTOR_DEFAULT_SECTION_BY_KIND["location"] == "dx_intro"
        assert DISCONNECTOR_DEFAULT_SECTION_BY_KIND["placement"] == "dx_placement"
        assert DISCONNECTOR_DEFAULT_SECTION_BY_KIND["other"] == "dx_coverage"

    def test_inspector_model(self):
        from app.core.workspace import workspace_from_project as _wfp
        from app.ui.shell.inspector_model import inspector_model
        p = _dx_project(dx_kind="موتوردار", feeder_name="F10 - RADIO")
        apply_eens_to_disconnector(p.disconnector, load_eens_report(EENS_FILE))
        model = inspector_model(p, _wfp(p), "input.disconnector")
        assert model.title == "جایابی سکسیونر"
        rows = dict(model.rows)
        assert rows["EENS پایه (MWh/سال)"] == "562.1667"
        assert "eens_report.json" in rows["نتایج جایابی"]

    def test_page_import_and_roundtrip(self):
        from app.ui.shell.disconnector_page import DisconnectorPage

        class M:
            project = Project(name="تست")
        mgr = M()
        pg = DisconnectorPage(mgr)
        pg.refresh()
        assert pg.import_eens_file(str(EENS_FILE)) == "F10 - RADIO"
        assert pg.eens_base.value() == 562.1667
        assert "eens_report.json" in pg.lbl_import.text()
        pg.location.setText("روستای رادیو")
        pg.dx_kind.setCurrentText("موتوردار")
        pg.save_to_project()
        dx = mgr.project.disconnector
        assert dx.location == "روستای رادیو" and dx.dx_kind == "موتوردار"
        assert dx.eens_base_mwh == 562.1667 and dx.eens_imported
        # بازخوانی فرم مقادیر را حفظ می‌کند
        pg.load_from(mgr.project)
        pg.save_to_project()
        assert mgr.project.disconnector.eens_base_mwh == 562.1667

    def test_pipeline_generator(self):
        from app.report.pipeline import make_generator
        from app.report.template_manager import TemplateManager
        from app.rules.rule_engine import RuleEngine
        import tempfile
        p = _dx_project()
        gen = make_generator(p, AppSettings(), TemplateManager(), RuleEngine(),
                             Path(tempfile.mkdtemp()))
        assert type(gen).__name__ == "ProtectionReportGenerator"
