# -*- coding: utf-8 -*-
"""خروجی استاندارد Rule Engine — «تغییرات آرنا» v1.1.0.

هر Rule نتیجه‌ای با ساختار یکتا و قابل‌ردیابی تولید می‌کند:

    Input → Calculation → Rule → Finding → Evidence → Report Text

* خروجی Machine-readable (dict/JSON) برای مصرف ماشینی و پیوست ردیابی.
* خروجی Persian Engineering Text فقط زمانی ساخته می‌شود که داده‌های لازم معتبر
  باشند؛ در غیر این صورت جای متن، وضعیت MISSING_DATA / MISSING_RULE /
  DATA_ERROR / REQUIRES_ENGINEER_REVIEW ثبت می‌گردد و هیچ عدد یا نتیجه‌ای
  ساخته یا حدس زده نمی‌شود.

هیچ آستانه‌ای در این ماژول تعریف نمی‌شود؛ آستانه‌ها فقط از زمینه (Context)
خوانده می‌شوند و مبنای هر آستانه (سند مرجع / پیکربندی) در خروجی ثبت می‌شود.
"""
from __future__ import annotations

import json
import string
from dataclasses import dataclass, field
from typing import Any, Optional

from app.utils.formatting import fmt

# ---------------------------------------------------------------------------
# وضعیت‌های استاندارد خروجی Rule (بخش ۶ صورت‌مسئله)
# ---------------------------------------------------------------------------
STATUS_PASS = "PASS"
STATUS_WARNING = "WARNING"
STATUS_FAIL = "FAIL"
STATUS_INFO = "INFO"
STATUS_DATA_ERROR = "DATA_ERROR"
STATUS_REQUIRES_REVIEW = "REQUIRES_ENGINEER_REVIEW"
STATUS_MISSING_RULE = "MISSING_RULE"
STATUS_MISSING_DATA = "MISSING_DATA"

STATUS_VALUES = (
    STATUS_PASS, STATUS_WARNING, STATUS_FAIL, STATUS_INFO,
    STATUS_DATA_ERROR, STATUS_REQUIRES_REVIEW,
    STATUS_MISSING_RULE, STATUS_MISSING_DATA,
)

STATUS_LABELS_FA = {
    STATUS_PASS: "منطبق",
    STATUS_WARNING: "هشدار",
    STATUS_FAIL: "عدم انطباق",
    STATUS_INFO: "اطلاع‌رسانی",
    STATUS_DATA_ERROR: "خطای داده",
    STATUS_REQUIRES_REVIEW: "نیازمند بررسی مهندس",
    STATUS_MISSING_RULE: "قاعده/آستانه تعریف‌نشده",
    STATUS_MISSING_DATA: "داده ناموجود",
}

# نگاشت وضعیت Rule به شدت Finding موجود نرم‌افزار (normal|warning|error|review)
# — هیچ شدت جدیدی اضافه نمی‌شود تا صفحات تحلیل/بازبینی بدون تغییر کار کنند.
SEVERITY_BY_STATUS = {
    STATUS_PASS: "normal",
    STATUS_INFO: "normal",
    STATUS_WARNING: "warning",
    STATUS_FAIL: "error",
    STATUS_DATA_ERROR: "review",
    STATUS_REQUIRES_REVIEW: "review",
    STATUS_MISSING_RULE: "review",
    STATUS_MISSING_DATA: "review",
}

# وضعیت‌هایی که متن گزارش برای آن‌ها تولید نمی‌شود (فقط ثبت/بازبینی)
NO_TEXT_STATUSES = (STATUS_MISSING_RULE, STATUS_DATA_ERROR)

# مبنای آستانه‌ها
BASIS_DOCUMENT = "document"      # صریحاً در سند مرجع
BASIS_CONFIG = "config"          # پیکربندی نرم‌افزار (کاربر قابل ویرایش)
BASIS_NONE = "undefined"         # تعریف‌نشده → MISSING_RULE


# ---------------------------------------------------------------------------
# قالب‌بندی امن متن Finding / Evidence / متن گزارش
# ---------------------------------------------------------------------------
class _SafeFormatter(string.Formatter):
    """قالب‌بندی مقاوم: کلید ناموجود → «—» و مقدار None → «—».

    برخلاف str.format، اینجا نبودِ یک کلید باعث خطا نمی‌شود؛ زیرا در Rule Engine
    هرگز نباید متن ناقص/حدسی تولید شود و نبود داده باید در وضعیت Rule دیده شود،
    نه به‌صورت متن نیمه‌ساخته.
    """

    def get_value(self, key, args, kwargs):  # noqa: D102
        if isinstance(key, str):
            return kwargs.get(key)
        try:
            return args[key]
        except (IndexError, TypeError):
            return None

    def format_field(self, value, format_spec):  # noqa: D102
        if value is None:
            return "—"
        if isinstance(value, str):
            return value
        if isinstance(value, float) and not format_spec:
            return fmt(value, 3)
        if isinstance(value, (int, float)) and format_spec:
            try:
                return format(value, format_spec)
            except (TypeError, ValueError):
                return fmt(value, 3)
        return str(value)


_FORMATTER = _SafeFormatter()


def render_template(template: str, values: dict[str, Any]) -> str:
    """رندر قالب متنی Rule با مقادیر Context؛ بدون تولید متن نیمه‌کاره."""
    if not template:
        return ""
    try:
        return _FORMATTER.vformat(template, (), dict(values or {}))
    except Exception:
        return str(template)


# ---------------------------------------------------------------------------
# خروجی استاندارد یک Rule
# ---------------------------------------------------------------------------
@dataclass
class RuleResult:
    """نتیجه یک Rule — Machine-readable + Persian Engineering Text."""

    rule_id: str
    category: str
    status: str
    input_values: dict[str, Any] = field(default_factory=dict)
    calculated_values: dict[str, Any] = field(default_factory=dict)
    finding: str = ""
    evidence: str = ""
    source: str = ""
    source_page: str = ""
    recommended_text: str = ""
    engineer_review_required: bool = False
    # --- متادیتا (خارج از قاعده استاندارد، برای ردیابی و UI) ---
    rule_key: str = ""                  # شناسه داخلی Rule در Rule Set (مثلاً XC-LOAD-SUM-MISMATCH)
    rule_name: str = ""
    priority: int = 10
    owner: str = ""                     # فیدر/خط/پست/سناریو/متقاضی مرتبط
    thresholds: dict[str, Any] = field(default_factory=dict)   # {key: {"value":…,"basis":…}}
    missing: list[str] = field(default_factory=list)           # داده/آستانه‌های ناموجود

    # ------------------------------------------------------------------
    @property
    def severity(self) -> str:
        """شدت سازگار با Finding نرم‌افزار — برای صفحه تحلیل/بازبینی."""
        return SEVERITY_BY_STATUS.get(self.status, "review")

    @property
    def needs_review(self) -> bool:
        return (self.engineer_review_required
                or self.status in (STATUS_DATA_ERROR, STATUS_REQUIRES_REVIEW,
                                   STATUS_MISSING_RULE, STATUS_MISSING_DATA))

    @property
    def text_available(self) -> bool:
        """آیا متن مهندسی فارسی قابل استفاده در گزارش تولید شده است؟"""
        return bool(self.recommended_text) and self.status not in NO_TEXT_STATUSES

    @property
    def status_label(self) -> str:
        return STATUS_LABELS_FA.get(self.status, self.status)

    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """خروجی استاندارد (بخش ۶): کلیدها مطابق قرارداد Rule Engine."""
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "status": self.status,
            "input_values": self.input_values,
            "calculated_values": self.calculated_values,
            "finding": self.finding,
            "evidence": self.evidence,
            "source": self.source,
            "source_page": self.source_page,
            "recommended_text": self.recommended_text,
            "engineer_review_required": bool(self.engineer_review_required),
            "meta": {
                "rule_key": self.rule_key or self.rule_id,
                "rule_name": self.rule_name,
                "owner": self.owner,
                "priority": self.priority,
                "thresholds": self.thresholds,
                "missing": list(self.missing),
                "severity": self.severity,
                "text_available": self.text_available,
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=str)

    # ------------------------------------------------------------------
    def trace_lines(self) -> list[tuple[str, str]]:
        """زنجیره ردیابی: Input → Calculation → Rule → Finding → Evidence → Text."""
        def _show(d: dict[str, Any]) -> str:
            if not d:
                return "—"
            return "، ".join(f"{k}={fmt(v, 3) if isinstance(v, float) else v}"
                             for k, v in d.items() if v is not None) or "—"

        return [
            ("ورودی (Input)", _show(self.input_values)),
            ("محاسبه (Calculation)", _show(self.calculated_values)),
            ("قاعده (Rule)", f"{self.rule_key or self.rule_id} — {self.rule_name} "
                             f"[{self.category}] | Rule ID گزارش‌شده: {self.rule_id}"),
            ("یافته (Finding)", self.finding or "—"),
            ("شاهد (Evidence)", self.evidence or "—"),
            ("متن گزارش (Report Text)", self.recommended_text or "— (تولید نشد)"),
            ("منبع", f"{self.source} — {self.source_page}"),
        ]


def result_from_rule_result(rr: RuleResult) -> dict[str, Any]:
    """اختصار: خروجی dict استاندارد (برای تست‌ها و گزارش ماشینی)."""
    return rr.to_dict()


def summarize_results(results: list[RuleResult]) -> dict[str, Any]:
    """خلاصه شمارشی نتایج Rule — برای داشبورد/جدول ردیابی."""
    counts: dict[str, int] = {s: 0 for s in STATUS_VALUES}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return {
        "total": len(results),
        "by_status": counts,
        "needs_review": sum(1 for r in results if r.needs_review),
        "missing_rule": [r.rule_id for r in results if r.status == STATUS_MISSING_RULE],
        "missing_data": [r.rule_id for r in results if r.status == STATUS_MISSING_DATA],
        "data_errors": [r.rule_id for r in results if r.status == STATUS_DATA_ERROR],
    }


def find_by_id(results: list[RuleResult], rule_id: str) -> Optional[RuleResult]:
    for r in results:
        if r.rule_id == rule_id:
            return r
    return None


def has_blocking_review(results: list[RuleResult]) -> bool:
    """آیا نتیجه‌ای وجود دارد که پیش از نتیجه‌گیری مهندسی باید بازبینی شود؟"""
    return any(r.needs_review for r in results)
