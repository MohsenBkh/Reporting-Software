# -*- coding: utf-8 -*-
"""موتور قواعد مهندسی مستقل از مولد گزارش (بخش ۱۵ سند).

سه خانواده قاعده پشتیبانی می‌شود:

1. **Ruleهای کلاسیک تعیین متن** (`data/rules/*.json`) — رفتار پیشین v1.0.3 بدون
   تغییر؛ انتخاب متن گزارش بر اساس وضعیت داده‌ها.
2. **Ruleهای تحلیلی با خروجی استاندارد** (`data/study_rules/*.json`, kind=analysis)
   — هر Rule یک :class:`~app.rules.outcome.RuleResult` کامل با ساختار
   Input → Calculation → Rule → Finding → Evidence → Report Text تولید می‌کند.
3. **Ruleهای تولید سناریوی تأمین** (kind=scenario) — سناریوها را *تولید* می‌کنند و
   هیچ‌گاه خودسرانه یکی را انتخاب/توصیه نمی‌کنند.

قواعد در JSON ذخیره می‌شوند و با ارزیاب عبارت امن (بدون eval آزاد) ارزیابی می‌گردند.
هیچ آستانه‌ای در کد یا در Rule هارد‌کد نمی‌شود: هر Rule آستانه‌های موردنیازش را
اعلام می‌کند و در نبود آن‌ها وضعیت MISSING_RULE ثبت می‌شود (نه مقدار حدسی).
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.rules.outcome import (BASIS_CONFIG, BASIS_DOCUMENT, BASIS_NONE,
                               RuleResult, render_template)
from app.utils.formatting import fmt

RULES_DIR = Path(__file__).resolve().parent / "data" / "rules"
STUDY_RULES_DIR = Path(__file__).resolve().parent / "data" / "study_rules"

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or,
    ast.UnaryOp, ast.Not, ast.USub,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
    ast.Name, ast.Load, ast.Constant,
)

# «true/false/null» سبک JSON/JS به لیترال‌های پایتون تبدیل می‌شود
# (در غیر این صورت NameError می‌گیرد و قاعده هرگز منطبق نمی‌شود)
# با NodeTransformer انجام می‌شود تا مقادیر رشته‌ای مثل 'none' دست‌نخورده بمانند.
_LITERAL_VALUES = {"true": True, "false": False, "null": None, "none": None}


class _LiteralTransformer(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name):
        value = _LITERAL_VALUES.get(node.id.lower())
        if value is None and node.id.lower() not in _LITERAL_VALUES:
            return node
        return ast.copy_location(ast.Constant(value=value), node)


def safe_eval_bool(expression: str, context: dict[str, Any]) -> bool:
    """ارزیابی امن عبارت منطقی روی context؛ خطا یا مقدار نامعتبر = False."""
    try:
        if not isinstance(expression, str) or not expression.strip():
            return False
        tree = ast.parse(expression, mode="eval")
        tree = _LiteralTransformer().visit(tree)
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED_NODES):
                raise ValueError(f"node not allowed: {type(node).__name__}")
        result = eval(  # noqa: S307 — درخت AST از قبل محدود شده است
            compile(tree, "<rule>", "eval"), {"__builtins__": {}}, dict(context))
        return bool(result)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Rule کلاسیک (تعیین متن گزارش) — بدون تغییر نسبت به v1.0.3
# ---------------------------------------------------------------------------
@dataclass
class Rule:
    id: str
    name: str
    domain: str          # loading | after_voltage | current | loss | forecast | conclusion
    condition: str
    text_id: str         # شناسه متن در کتابخانه متن
    priority: int = 10
    enabled: bool = True
    severity: str = "normal"   # normal | warning | error | review

    def matches(self, context: dict[str, Any]) -> bool:
        return safe_eval_bool(self.condition, context)


@dataclass
class RuleOutcome:
    rule: Rule
    text_id: str


# ---------------------------------------------------------------------------
# Rule تحلیلی با خروجی استاندارد (kind = analysis)
# ---------------------------------------------------------------------------
@dataclass
class ThresholdRef:
    """آستانه موردنیاز یک Rule — با مبنای صریح (سند مرجع / پیکربندی)."""

    key: str
    label: str = ""
    basis: str = BASIS_CONFIG
    note: str = ""
    required: bool = True

    @classmethod
    def from_json(cls, item: Any) -> "ThresholdRef":
        if isinstance(item, str):
            return cls(key=item, label=item, basis=BASIS_CONFIG)
        if isinstance(item, dict):
            return cls(
                key=str(item.get("key", "")),
                label=str(item.get("label") or item.get("key", "")),
                basis=str(item.get("basis", BASIS_CONFIG)),
                note=str(item.get("note", "")),
                required=bool(item.get("required", True)),
            )
        return cls(key=str(item))


@dataclass
class AnalysisRule:
    """Rule تحلیلی — خروجی آن یک RuleResult با ساختار استاندارد است."""

    id: str
    name: str
    domain: str
    condition: str
    status: str                                   # PASS | WARNING | FAIL | INFO | ...
    rule_id: str = ""                             # شناسه گزارش‌شده (پیش‌فرض: id) — مثلاً DATA_INCONSISTENCY
    priority: int = 10
    enabled: bool = True
    severity: str = ""                            # در صورت خالی بودن از status مشتق می‌شود
    requires: list[str] = field(default_factory=list)          # داده‌های الزامی
    thresholds: list[ThresholdRef] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)            # در input_values ثبت می‌شود
    calculated: list[str] = field(default_factory=list)        # در calculated_values ثبت می‌شود
    finding: str = ""
    evidence: str = ""
    recommended_text: str = ""
    source: str = "TAV111-10/00"
    source_page: str = ""
    engineer_review_required: bool = False
    tags: list[str] = field(default_factory=list)

    def matches(self, context: dict[str, Any]) -> bool:
        return safe_eval_bool(self.condition, context)


@dataclass
class ScenarioRule:
    """Rule تولید سناریوی تأمین (kind = scenario)."""

    id: str
    name: str
    kind: str                     # new_feeder | existing_feeder | alternative_feeder
    condition: str
    title: str = ""
    technical_basis: str = ""
    required_network_changes: str = ""
    candidate_feeder: str = ""
    required_equipment: list[str] = field(default_factory=list)
    evidence: str = ""
    review_status: str = "REQUIRES_ENGINEER_REVIEW"
    priority: int = 10
    enabled: bool = True
    source: str = "TAV111-10/00"
    source_page: str = ""

    def matches(self, context: dict[str, Any]) -> bool:
        return safe_eval_bool(self.condition, context)


@dataclass
class ScenarioSpec:
    """سناریوی تولیدشده توسط Rule Engine (پیش از ذخیره در مدل داده)."""

    rule_id: str
    kind: str
    title: str
    technical_basis: str
    required_network_changes: str
    candidate_feeder: str
    required_equipment: list[str]
    evidence: str
    review_status: str
    priority: int
    source: str
    source_page: str

    @property
    def key(self) -> str:
        """کلید پایدار برای بازبینی مهندس (مستقل از ترتیب تولید)."""
        return f"scenario:{self.kind}"


# ---------------------------------------------------------------------------
class RuleEngine:
    """بارگذاری و ارزیابی قواعد از پوشه‌های data/rules و data/study_rules."""

    def __init__(self, rules_dir: Path | str = RULES_DIR,
                 study_rules_dir: Path | str = STUDY_RULES_DIR) -> None:
        self.rules_dir = Path(rules_dir)
        self.study_rules_dir = Path(study_rules_dir)
        self.rules: list[Rule] = []
        # Ruleهای تحلیلی و سناریویی — Map از rule_id به گونه
        self.analysis_rules: dict[str, AnalysisRule] = {}
        self.scenario_rules: dict[str, ScenarioRule] = {}
        self._last_skipped: list[str] = []      # Ruleهای نامعتبر (برای عیب‌یابی در تست‌ها)
        self.load()

    # ------------------------------------------------------------------
    def load(self) -> None:
        self.rules = []
        self.analysis_rules = {}
        self.scenario_rules = {}
        self._last_skipped = []
        self._load_classic()
        self._load_study()
        self.rules.sort(key=lambda r: -r.priority)

    def reload(self) -> None:
        """بارگذاری مجدد قواعد از دیسک (پس از ویرایش JSON توسط کاربر)."""
        self.load()

    # ------------------------------------------------------------------
    def _load_classic(self) -> None:
        if not self.rules_dir.exists():
            return
        for path in sorted(self.rules_dir.glob("*.json")):
            data = self._read_json(path)
            if data is None:
                continue
            domain = data.get("domain", "")
            for item in data.get("rules", []):
                try:
                    self.rules.append(Rule(
                        id=item["id"], name=item.get("name", item["id"]),
                        domain=item.get("domain", domain),
                        condition=item["condition"],
                        text_id=item["text_id"],
                        priority=int(item.get("priority", 10)),
                        enabled=bool(item.get("enabled", True)),
                        severity=str(item.get("severity", "normal"))))
                except (KeyError, TypeError, ValueError):
                    self._last_skipped.append(f"{path.name}:{item.get('id', '?')}")

    def _load_study(self) -> None:
        if not self.study_rules_dir.exists():
            return
        for path in sorted(self.study_rules_dir.glob("*.json")):
            data = self._read_json(path)
            if data is None:
                continue
            domain = data.get("domain", "")
            kind = str(data.get("kind", "analysis")).lower()
            for item in data.get("rules", []):
                try:
                    if kind == "scenario":
                        rule = ScenarioRule(
                            id=item["id"],
                            name=item.get("name", item["id"]),
                            kind=str(item.get("scenario_kind", item.get("kind", "new_feeder"))),
                            condition=item["condition"],
                            title=str(item.get("title", "")),
                            technical_basis=str(item.get("technical_basis", "")),
                            required_network_changes=str(item.get("required_network_changes", "")),
                            candidate_feeder=str(item.get("candidate_feeder", "")),
                            required_equipment=[str(x) for x in item.get("required_equipment", [])],
                            evidence=str(item.get("evidence", "")),
                            review_status=str(item.get("review_status", "REQUIRES_ENGINEER_REVIEW")),
                            priority=int(item.get("priority", 10)),
                            enabled=bool(item.get("enabled", True)),
                            source=str(item.get("source", "TAV111-10/00")),
                            source_page=str(item.get("source_page", "")))
                        self.scenario_rules[rule.id] = rule
                    else:
                        rule = AnalysisRule(
                            id=item["id"],
                            name=item.get("name", item["id"]),
                            domain=str(item.get("domain", domain)),
                            condition=item.get("condition", "True"),
                            status=str(item.get("status", "INFO")).upper(),
                            rule_id=str(item.get("rule_id", "")),
                            priority=int(item.get("priority", 10)),
                            enabled=bool(item.get("enabled", True)),
                            severity=str(item.get("severity", "")),
                            requires=[str(x) for x in item.get("requires", [])],
                            thresholds=[ThresholdRef.from_json(x)
                                        for x in item.get("thresholds", [])],
                            inputs=[str(x) for x in item.get("inputs", [])],
                            calculated=[str(x) for x in item.get("calculated", [])],
                            finding=str(item.get("finding", "")),
                            evidence=str(item.get("evidence", "")),
                            recommended_text=str(item.get("recommended_text", "")),
                            source=str(item.get("source", "TAV111-10/00")),
                            source_page=str(item.get("source_page", "")),
                            engineer_review_required=bool(item.get("engineer_review_required", False)),
                            tags=[str(x) for x in item.get("tags", [])])
                        self.analysis_rules[rule.id] = rule
                except (KeyError, TypeError, ValueError):
                    self._last_skipped.append(f"{path.name}:{item.get('id', '?')}")

    @staticmethod
    def _read_json(path: Path) -> Optional[dict]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Ruleهای کلاسیک (سازگار با v1.0.3)
    # ------------------------------------------------------------------
    def first_match(self, domain: str, context: dict[str, Any]) -> Optional[Rule]:
        """اولین قاعده منطبق از بالاترین اولویت."""
        for rule in self.rules:
            if rule.domain == domain and rule.enabled and rule.matches(context):
                return rule
        return None

    def all_matches(self, domain: str, context: dict[str, Any]) -> list[Rule]:
        return [r for r in self.rules
                if r.domain == domain and r.enabled and r.matches(context)]

    def by_domain(self, domain: str) -> list[Rule]:
        return [r for r in self.rules if r.domain == domain]

    # ------------------------------------------------------------------
    # Ruleهای تحلیلی (خروجی استاندارد)
    # ------------------------------------------------------------------
    def analysis_by_domain(self, domain: str) -> list[AnalysisRule]:
        return sorted([r for r in self.analysis_rules.values() if r.domain == domain],
                      key=lambda r: -r.priority)

    def domains(self) -> list[str]:
        """حوزه‌های Ruleهای تحلیلی به ترتیب اولویت."""
        domains: list[str] = []
        for rule in sorted(self.analysis_rules.values(), key=lambda r: -r.priority):
            if rule.domain not in domains:
                domains.append(rule.domain)
        return domains

    def evaluate(self, domain: str, context: dict[str, Any]) -> list[RuleResult]:
        """ارزیابی همه Ruleهای منطبق یک حوزه → فهرست RuleResult استاندارد.

        اگر Rule به آستانه تعریف‌نشده نیاز داشته باشد، وضعیت MISSING_RULE ثبت
        می‌شود؛ اگر داده الزامی موجود نباشد، MISSING_DATA ثبت می‌شود. در هیچ
        حالتی مقدار یا نتیجه حدسی تولید نمی‌گردد.
        """
        out: list[RuleResult] = []
        for rule in self.analysis_by_domain(domain):
            if rule.enabled and rule.matches(context):
                out.append(self._build_result(rule, context))
        return out

    def evaluate_many(self, context: dict[str, Any],
                      domains: Optional[list[str]] = None) -> list[RuleResult]:
        """ارزیابی همه حوزه‌ها (یا حوزه‌های داده‌شده) روی یک Context."""
        out: list[RuleResult] = []
        for domain in (domains or self.domains()):
            out.extend(self.evaluate(domain, context))
        return out

    def _build_result(self, rule: AnalysisRule, ctx: dict[str, Any]) -> RuleResult:
        inputs = {k: ctx.get(k) for k in rule.inputs}
        calculated = {k: ctx.get(k) for k in rule.calculated}
        thresholds: dict[str, Any] = {}
        missing: list[str] = []

        # ۱) داده‌های الزامی
        missing_data = [k for k in rule.requires if ctx.get(k) is None]

        # ۲) آستانه‌های موردنیاز — هیچ‌گاه مقدار پیش‌فرض اختراع نمی‌شود
        missing_thresholds: list[ThresholdRef] = []
        for ref in rule.thresholds:
            value = ctx.get(ref.key)
            basis = ref.basis if value is not None else BASIS_NONE
            thresholds[ref.key] = {
                "value": value,
                "basis": basis,
                "label": ref.label or ref.key,
                "note": ref.note,
            }
            if value is None and ref.required:
                missing_thresholds.append(ref)
        calculated["_thresholds"] = {k: v["value"] for k, v in thresholds.items()}

        status = rule.status
        engineer_review = rule.engineer_review_required

        if missing_data:
            status = "MISSING_DATA"
            engineer_review = True
            missing = list(missing_data)
            finding = ("داده لازم برای اجرای این Rule ثبت نشده است: "
                       + "، ".join(missing_data)
                       + "؛ تا تکمیل داده‌ها هیچ نتیجه‌ای تولید نمی‌شود.")
            evidence = rule.evidence
            text = ""
        elif missing_thresholds:
            status = "MISSING_RULE"
            engineer_review = True
            missing = [ref.key for ref in missing_thresholds]
            labels = "، ".join(f"{ref.label or ref.key}" for ref in missing_thresholds)
            finding = ("برای تصمیم‌گیری این Rule حد آستانه لازم است و این آستانه نه در "
                       f"سند مرجع تعریف شده و نه در پیکربندی: {labels}. "
                       "مقدار جایگزین به‌صورت خودکار فرض نمی‌شود.")
            evidence = "؛ ".join(ref.note for ref in missing_thresholds if ref.note) or rule.evidence
            text = ""
        else:
            values = dict(ctx)
            values.update({k: v["value"] for k, v in thresholds.items()})
            finding = render_template(rule.finding, values)
            evidence = render_template(rule.evidence, values)
            text = render_template(rule.recommended_text, values)

        return RuleResult(
            rule_id=(rule.rule_id or rule.id),
            category=rule.domain,
            status=status,
            input_values=inputs,
            calculated_values=calculated,
            finding=finding,
            evidence=evidence,
            source=rule.source,
            source_page=rule.source_page,
            recommended_text=text,
            engineer_review_required=engineer_review,
            rule_key=rule.id,
            rule_name=rule.name,
            priority=rule.priority,
            thresholds=thresholds,
            missing=missing,
        )

    # ------------------------------------------------------------------
    # Ruleهای سناریو — تولید سناریو (بدون انتخاب/توصیه خودسرانه)
    # ------------------------------------------------------------------
    def generate_scenarios(self, context: dict[str, Any]) -> list[ScenarioSpec]:
        """تولید همه سناریوهای ممکن برای تأمین تقاضا بر اساس Rule Set.

        هیچ سناریویی «انتخاب» یا «توصیه» نمی‌شود؛ انتخاب نهایی فقط با مهندس است
        مگر معیار انتخاب صریحاً در Rule Set تعریف شده باشد (در نسخه فعلی چنین
        معیاری تعریف نشده و therefore وضعیت همه سناریوها REQUIRES_ENGINEER_REVIEW است).
        """
        specs: list[ScenarioSpec] = []
        for rule in sorted(self.scenario_rules.values(), key=lambda r: -r.priority):
            if not rule.enabled or not rule.matches(context):
                continue
            values = dict(context)
            specs.append(ScenarioSpec(
                rule_id=rule.id,
                kind=rule.kind,
                title=render_template(rule.title, values) or rule.name,
                technical_basis=render_template(rule.technical_basis, values),
                required_network_changes=render_template(rule.required_network_changes, values),
                candidate_feeder=render_template(rule.candidate_feeder, values),
                required_equipment=[render_template(x, values) for x in rule.required_equipment],
                evidence=render_template(rule.evidence, values),
                review_status=rule.review_status,
                priority=rule.priority,
                source=rule.source,
                source_page=rule.source_page,
            ))
        return specs

    def scenario_rule(self, rule_id: str) -> Optional[ScenarioRule]:
        return self.scenario_rules.get(rule_id)


# ---------------------------------------------------------------------------
def describe_missing_threshold_rules(engine: RuleEngine) -> list[dict[str, str]]:
    """فهرست Ruleهایی که به آستانه‌های غیرمستند/تعریف‌نشده وابسته‌اند.

    برای مستندسازی «Ruleهای فاقد Threshold» و شفافیت مبنای تصمیم‌گیری.
    """
    rows: list[dict[str, str]] = []
    for rule in sorted(engine.analysis_rules.values(), key=lambda r: (-r.priority, r.id)):
        for ref in rule.thresholds:
            rows.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "domain": rule.domain,
                "threshold_key": ref.key,
                "threshold_label": ref.label or ref.key,
                "basis": ref.basis,
                "source_page": rule.source_page,
            })
    return rows
