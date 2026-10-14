# -*- coding: utf-8 -*-
"""قواعد متقاضی سنگین — فایل‌های JSON موجود در ``app/rules/data/study_rules`` بدون
جابه‌جایی حفظ شده‌اند؛ این بسته فقط نقطهٔ دسترسی دامنه‌ای است."""
from app.rules.rule_engine import RuleEngine


def build_engine() -> RuleEngine:
    """موتور پیش‌فرض (قواعد کلاسیک + تحلیلی + سناریو) بدون هیچ تغییر."""
    return RuleEngine()
