# -*- coding: utf-8 -*-
"""ثبت دامنه‌های Rule و ارزیابی مطالعات.

``rules/``
    ├── common/              قواعد داده مشترک شبکه (protection_common)
    ├── heavy_applicant/     قواعد JSON موجود (بدون جابه‌جایی)
    ├── recloser/            قواعد ریکلوزر
    └── sectionalizer/       قواعد سکشنالایزر

قواعد حفاظتی در موتور مستقلی ثبت می‌شوند تا با قواعد متقاضی سنگین مخلوط نشوند.
در صورت وجود پوشهٔ ``data/protection_rules/*.json`` (قالب study_rules) قواعد آن
با شناسهٔ یکسان بر پیش‌فرض‌های پایتون اولویت دارند.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from app.core.studies import StudyKind
from app.core.workspace import Workspace
from app.rules import common as common_rules
from app.rules import recloser as recloser_rules
from app.rules import sectionalizer as sectionalizer_rules
from app.rules.common.builder import (DOMAIN_COMMON, DOMAIN_RECLOSER,
                                      DOMAIN_SECTIONALIZER)
from app.rules.protection_context import build_context
from app.rules.rule_engine import RuleEngine

OVERRIDE_DIR = Path(__file__).resolve().parent / "data" / "protection_rules"
_NO_DIR = Path(__file__).resolve().parent / "data" / "_no_such_dir"

STUDY_DOMAIN = {StudyKind.RECLOSER: DOMAIN_RECLOSER,
                StudyKind.SECTIONALIZER: DOMAIN_SECTIONALIZER}


def build_protection_engine(override_dir: Optional[Path] = None) -> RuleEngine:
    engine = RuleEngine(rules_dir=_NO_DIR, study_rules_dir=override_dir or OVERRIDE_DIR)
    for rule in (common_rules.build_rules() + recloser_rules.build_rules()
                 + sectionalizer_rules.build_rules()):
        engine.analysis_rules.setdefault(rule.id, rule)   # JSON با همان id برنده است
    return engine


def evaluate_study(project: Any, workspace: Workspace, kind: StudyKind,
                   engine: Optional[RuleEngine] = None,
                   thresholds: Optional[dict] = None) -> list:
    """نتایج Rule یک مطالعهٔ حفاظتی (قواعد مشترک + قواعد اختصاصی)."""
    kind = StudyKind(kind)
    if kind not in STUDY_DOMAIN:
        raise ValueError("ارزیابی حفاظتی فقط برای ریکلوزر و سکشنالایزر تعریف شده است.")
    engine = engine or build_protection_engine()
    ctx = build_context(project, workspace, kind, thresholds)
    results = engine.evaluate(DOMAIN_COMMON, ctx) + engine.evaluate(STUDY_DOMAIN[kind], ctx)
    owner = getattr(getattr(project, kind.value), "name", "") or kind.value
    for r in results:
        r.owner = owner
    return results
