# -*- coding: utf-8 -*-
"""v1.0.3 — بازبینی مهندس، اعتبارسنجی، ردیابی، خطاها، ذخیره/بازیابی."""
import json
from pathlib import Path

import pytest
from sample_projects import make_feeder, make_project

from app.core import findings as fnd
from app.core import traceability as trace
from app.core import validation as val
from app.core.models import (REVIEW_ACCEPTED, REVIEW_EDITED, REVIEW_OVERRIDDEN,
                             REVIEW_REJECTED, project_from_dict, to_dict)
from app.core.project_manager import ProjectManager
from app.core.settings import AppSettings
from app.report.analysis import AnalysisService
from app.utils import errors

S = AppSettings()


def _svc(tmp_path):
    mgr = ProjectManager(S)
    p = make_project()
    p.feeders = [make_feeder()]
    mgr.new_project(tmp_path / "proj", p)
    return mgr, AnalysisService(mgr, S)


def _find(svc, domain):
    return next(f for f in svc.get(force=True).findings if f.domain == domain)


# ---------------- review ----------------
def test_edit_replaces_text_in_report_and_survives_regenerate(tmp_path):
    mgr, svc = _svc(tmp_path)
    f = _find(svc, "loading")
    fnd.set_decision(mgr.project, f, REVIEW_EDITED, "اصلاح عبارت", "متن مهندس: بارگذاری مناسب است.")
    svc.invalidate()
    rep = svc.get()
    text = "\n".join(p.text for s in rep.sections for p in s.paragraphs())
    assert "متن مهندس: بارگذاری مناسب است." in text
    assert _find(svc, "loading").status == REVIEW_EDITED


def test_reject_removes_paragraph_but_keeps_comment_in_appendix(tmp_path):
    mgr, svc = _svc(tmp_path)
    f = _find(svc, "loading")
    fnd.set_decision(mgr.project, f, REVIEW_REJECTED, "مبنای معیار نامعتبر")
    svc.invalidate()
    rep = svc.get()
    assert f.auto_text not in "\n".join(p.text for s in rep.sections for p in s.paragraphs())
    appx = next(s for s in rep.sections if s.key == "appendix_review")
    assert any("مبنای معیار نامعتبر" in c for t in appx.blocks if hasattr(t, "body_rows") for r in t.body_rows for c in r)


def test_edit_without_text_is_rejected():
    p = make_project()
    f = fnd.Finding("loading:x", "loading", "f", "L", "n", "normal", "auto")
    with pytest.raises(ValueError):
        fnd.set_decision(p, f, REVIEW_OVERRIDDEN, "c", "  ")


def test_decision_marked_stale_when_inputs_change(tmp_path):
    mgr, svc = _svc(tmp_path)
    f = _find(svc, "loading")
    fnd.set_decision(mgr.project, f, REVIEW_ACCEPTED)
    mgr.project.feeders[0].peak_load_mw = 6.9     # تغییر فنی ورودی
    svc.invalidate()
    f2 = _find(svc, "loading")
    assert f2.stale and f2.needs_attention
    assert f2.status == REVIEW_ACCEPTED           # تصمیم از بین نمی‌رود


def test_adding_figure_does_not_make_decision_stale():
    a = "همانطور که در شکل 1 نشان داده شده"
    b = "همانطور که در شکل 2 نشان داده شده"
    assert fnd.text_hash(a) == fnd.text_hash(b)


def test_reviews_persist_in_project_json(tmp_path):
    mgr, svc = _svc(tmp_path)
    fnd.set_decision(mgr.project, _find(svc, "conclusion"), REVIEW_OVERRIDDEN, "دلیل", "نتیجه مهندس")
    mgr.save()
    mgr2 = ProjectManager(S)
    mgr2.open_project(tmp_path / "proj" / "project.json")
    d = mgr2.project.reviews["conclusion"]
    assert d.status == REVIEW_OVERRIDDEN and d.replacement_text == "نتیجه مهندس" and d.comment == "دلیل"


def test_old_project_json_without_new_fields_loads():
    p = project_from_dict({"name": "x", "feeders": [{"name": "a", "forecast": {"method": "regression"}}]})
    assert p.reviews == {} and p.feeders[0].data_sources == {} and p.feeders[0].forecast.review_status == "OK"


def test_invalid_review_status_falls_back_to_pending():
    p = project_from_dict({"reviews": {"k": {"status": "hacked"}}})
    assert p.reviews["k"].status == "pending"


def test_analysis_cache_invalidates_on_data_change(tmp_path):
    mgr, svc = _svc(tmp_path)
    r1 = svc.get()
    assert svc.get() is r1
    mgr.project.feeders[0].peak_load_mw = 6.5
    assert svc.get() is not r1


# ---------------- validation ----------------
def _items(p):
    return val.validate_project(p, S)


def _errs(p):
    return [i.message for i in _items(p) if i.status == val.ERROR]


def test_valid_project_has_no_errors():
    p = make_project(); p.feeders = [make_feeder()]
    assert not val.has_errors(_items(p))


def test_voltage_in_kv_is_error_with_hint():
    p = make_project(); p.feeders = [make_feeder(after=(205, 420, 20.1, 20.2))]
    it = [i for i in _items(p) if i.status == val.ERROR and "کیلوولت" in i.message]
    assert it and "p.u." in it[0].hint and it[0].step == val.STEP_LOADFLOW


def test_peak_in_kw_instead_of_mw_warns():
    p = make_project(); p.feeders = [make_feeder(peak=5000)]
    assert any("kW" in i.message for i in _items(p) if i.status == val.WARNING)


def test_duplicate_feeder_names_error():
    p = make_project(); p.feeders = [make_feeder("A"), make_feeder("A")]
    assert any("تکراری" in m for m in _errs(p))


def test_incomplete_powerflow_is_error():
    p = make_project(); f = make_feeder(); f.after.loss_kw = None; p.feeders = [f]
    assert any("ناقص" in m for m in _errs(p))


def test_equal_powers_error_and_bad_date_warning():
    p = make_project(requested_power_kw=1000, date_jalali="2026-01-01"); p.feeders = [make_feeder()]
    assert any("برابر" in m for m in _errs(p))
    assert any("تاریخ" in i.message for i in _items(p) if i.status == val.WARNING)


def test_persian_digits_in_date_accepted():
    p = make_project(date_jalali="۱۴۰۵/۰۶/۱۵"); p.feeders = [make_feeder()]
    assert not any("تاریخ" in i.message for i in _items(p))


def test_current_decrease_after_adding_load_warns():
    p = make_project(); p.feeders = [make_feeder(before=(300, 400, .97, .98), after=(250, 420, .96, .97))]
    assert any("کاهش" in i.message for i in _items(p) if i.status == val.WARNING)


def test_empty_project_reports_missing_pieces():
    from app.core.models import Project
    errs = _errs(Project())
    assert any("اطلاعات پروژه" in m for m in errs) and any("فیدر" in m for m in errs)


# ---------------- traceability ----------------
def test_trace_sources_manual_calc_pf():
    p = make_project(); f = make_feeder(); p.feeders = [f]
    trace.mark_all(f, trace.SRC_EXCEL, "in.xlsx")
    old = trace.snapshot(f)
    f.peak_load_mw = 5.5
    trace.mark_manual_changes(f, old)
    rows = {r.item: r for r in trace.build_trace(p, S)}
    assert rows["پیک بار"].source_type == trace.SRC_MANUAL
    assert rows["ضریب توان"].source_type == trace.SRC_EXCEL and "in.xlsx" in rows["ضریب توان"].source_label
    assert rows["جریان بعد"].source_type == trace.SRC_PF
    assert rows["درصد بارگذاری فیدر"].source_type == trace.SRC_CALC


# ---------------- errors ----------------
def test_friendly_errors_are_persian_without_traceback():
    for exc in (KeyError("feeder_name"), PermissionError(), FileNotFoundError(), ZeroDivisionError(),
                ValueError("x"), RuntimeError("boom")):
        ue = errors.friendly_error(exc, "تست")
        assert ue.message and "Traceback" not in ue.text() and "boom" not in ue.text()
    assert "فیدر مورد مطالعه" in errors.friendly_error(KeyError("feeder_name")).solution


def test_logging_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTFORGE_HOME", str(tmp_path))
    import logging
    for h in list(logging.getLogger(errors.LOGGER_NAME).handlers):
        logging.getLogger(errors.LOGGER_NAME).removeHandler(h)
    errors.setup_logging()
    errors.log_exception(ValueError("log-me"), "ctx")
    for h in logging.getLogger(errors.LOGGER_NAME).handlers:
        h.flush()
    assert "log-me" in (tmp_path / "logs" / "reportforge.log").read_text(encoding="utf-8")
