# -*- coding: utf-8 -*-
"""قواعد مشترک مطالعات حفاظتی (داده‌های شبکهٔ مشترک)."""
from app.rules.common.builder import DOMAIN_COMMON, make_rule

SRC = "ساختار Rule Engine — داده مشترک شبکه"


def build_rules() -> list:
    D = DOMAIN_COMMON
    missing = [
        ("PCM-FEEDER-MISSING", "نام فیدر هدف ثبت نشده", "not has_feeder_name", "feeder_name"),
        ("PCM-FAULT-MISSING", "جریان اتصال کوتاه در محل نصب ثبت نشده",
         "not has_fault_current_ka", "fault_current_ka"),
        ("PCM-MINFAULT-MISSING", "حداقل جریان اتصال کوتاه ثبت نشده",
         "not has_min_fault_current_ka", "min_fault_current_ka"),
        ("PCM-LOAD-MISSING", "جریان بار فیدر/محل نصب ثبت نشده",
         "not has_load_current_a", "load_current_a"),
    ]
    rules = [make_rule(rid, name, D, cond, "MISSING_DATA", requires=[key],
                       source=SRC, priority=80, review=True)
             for rid, name, cond, key in missing]
    rules.append(make_rule(
        "PCM-NO-COMMON-FEEDER", "فیدر در شبکه مشترک پروژه تعریف نشده", D,
        "has_feeder_name and not has_common_feeder", "INFO",
        finding="برای فیدر «{feeder_name}» داده‌ای در شبکه مشترک ثبت نشده است؛ "
                "فقط مقادیر واردشده در خود مطالعه استفاده می‌شود.",
        source=SRC, priority=60, review=True))
    rules += [
        make_rule("PCM-DG-UNKNOWN", "وضعیت منابع تولید پراکنده مشخص نشده", D,
                  "has_common_feeder and dg_status == None", "MISSING_DATA",
                  requires=["dg_status"], source=SRC, priority=65, review=True),
        make_rule("PCM-DG-PRESENT", "وجود منابع تولید پراکنده در فیدر", D, "dg_present", "INFO",
                  finding="منبع تولید پراکنده روی فیدر «{feeder_name}» گزارش شده است ({dg_note}). "
                          "اثر آن بر جریان خطا و هماهنگی حفاظتی باید توسط مهندس بررسی شود.",
                  source=SRC, priority=62, review=True),
        make_rule("PCM-SCENARIO-MISSING", "سناریوهای بهره‌برداری عادی/اضطراری ثبت نشده", D,
                  "has_common_feeder and operating_scenarios == None", "MISSING_DATA",
                  requires=["operating_scenarios"], source=SRC, priority=64, review=True),
    ]
    return rules
