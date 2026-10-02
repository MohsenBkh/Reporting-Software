# -*- coding: utf-8 -*-
"""موتور قواعد مهندسی مستقل از مولد گزارش (بخش ۱۵ سند).

قواعد در فایل‌های JSON ذخیره می‌شوند و با یک ارزیاب عبارت امن (بدون eval آزاد)
در برابر Context محاسبه‌شده هر فیدر/پروژه ارزیابی می‌گردند.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

RULES_DIR = Path(__file__).resolve().parent / "data" / "rules"

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


class RuleEngine:
    """بارگذاری و ارزیابی قواعد از پوشه data/rules."""

    def __init__(self, rules_dir: Path | str = RULES_DIR) -> None:
        self.rules_dir = Path(rules_dir)
        self.rules: list[Rule] = []
        self.load()

    def load(self) -> None:
        self.rules = []
        if not self.rules_dir.exists():
            return
        for path in sorted(self.rules_dir.glob("*.json")):
            try:
                data = __import__("json").loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
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
                    continue
        self.rules.sort(key=lambda r: -r.priority)

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
