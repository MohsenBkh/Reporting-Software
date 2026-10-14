# -*- coding: utf-8 -*-
"""سازندهٔ کوتاه Ruleهای تحلیلی (AnalysisRule) برای دامنه‌های حفاظتی."""
from __future__ import annotations

from app.rules.rule_engine import AnalysisRule, ThresholdRef

DOMAIN_COMMON = "protection_common"
DOMAIN_RECLOSER = "recloser"
DOMAIN_SECTIONALIZER = "sectionalizer"


def make_rule(rule_id: str, name: str, domain: str, condition: str, status: str, *,
              finding: str = "", evidence: str = "", text: str = "",
              requires=(), thresholds=(), inputs=(), calculated=(),
              source: str = "", page: str = "", review: bool = False,
              priority: int = 50, report_id: str = "") -> AnalysisRule:
    return AnalysisRule(
        id=rule_id, name=name, domain=domain, condition=condition, status=status,
        rule_id=report_id, priority=priority, requires=list(requires),
        thresholds=list(thresholds), inputs=list(inputs), calculated=list(calculated),
        finding=finding, evidence=evidence, recommended_text=text,
        source=source, source_page=page, engineer_review_required=review)


def th(key: str, label: str, basis: str, note: str = "") -> ThresholdRef:
    return ThresholdRef(key=key, label=label, basis=basis, note=note)
