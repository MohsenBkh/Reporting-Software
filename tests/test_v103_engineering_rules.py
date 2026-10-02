# -*- coding: utf-8 -*-
"""v1.0.3 — تفکیک ولتاژ مطلق از اثر متقاضی، تلفات، شدت Ruleها، متن‌ها."""
from sample_projects import make_feeder, make_project

from app.core import calculations as calc
from app.core.settings import AppSettings
from app.report.template_manager import TemplateManager
from app.report.text_generator import TextGenerator
from app.rules.rule_engine import RuleEngine

S = AppSettings()


def _ctx(before_v, after_v):
    p = make_project()
    f = make_feeder(before=(180, 400, before_v, before_v + .01), after=(205, 420, after_v, after_v + .01))
    p.feeders = [f]
    return p, calc.build_feeder_context(f, p, S), calc.build_project_context(p, S)


def test_preexisting_low_voltage_is_not_caused_by_applicant():
    p, fc, pc = _ctx(0.930, 0.928)
    assert fc["v_preexisting"] and not fc["v_caused_bad"]
    assert RuleEngine().first_match("conclusion", pc).id == "C-PREEXISTING"


def test_new_violation_caused_by_applicant():
    p, fc, pc = _ctx(0.960, 0.915)
    assert fc["v_caused_bad"] and not fc["v_preexisting"]
    assert RuleEngine().first_match("conclusion", pc).id in ("C-BAD", "C-CONDITIONAL")


def test_healthy_case_is_ok():
    _p, _fc, pc = _ctx(0.975, 0.970)
    assert RuleEngine().first_match("conclusion", pc).id == "C-OK"


def test_loss_increase_alone_never_triggers_corrective_conclusion():
    p = make_project()
    f = make_feeder(before=(180, 100, 0.97, 0.98), after=(205, 300, 0.965, 0.975))
    p.feeders = [f]
    pc = calc.build_project_context(p, S)
    assert pc["any_loss_up"] and RuleEngine().first_match("conclusion", pc).id == "C-OK"


def test_every_rule_has_valid_severity():
    eng = RuleEngine()
    for domain in ("loading", "after_voltage", "current", "loss", "forecast", "conclusion"):
        rules = eng.by_domain(domain)
        assert rules, domain
        for r in rules:
            assert r.severity in ("normal", "warning", "error", "review"), (domain, r.id)


def test_forecast_review_rule_selected_for_poor_quality():
    p = make_project()
    f = make_feeder(years=[1399 + i for i in range(6)], values=[10, 14, 9, 13, 10, 12])
    p.feeders = [f]
    ctx = calc.build_feeder_context(f, p, S)
    rule = RuleEngine().first_match("forecast", ctx)
    assert rule.id == "FC-REVIEW" and rule.severity == "review"


def test_no_unfilled_placeholders_in_any_generated_text():
    p = make_project()
    p.feeders = [make_feeder(years=[1399 + i for i in range(6)], values=[10, 14, 9, 13, 10, 12])]
    from pathlib import Path
    import tempfile
    gen = TextGenerator(p, S, TemplateManager(), RuleEngine(), Path(tempfile.mkdtemp()))
    secs = gen.build_all()
    text = "\n".join(x.text for s in secs for x in s.paragraphs())
    assert "{" not in text and "}" not in text
    assert any(f.rule_id == "FC-REVIEW" for f in gen.findings)
