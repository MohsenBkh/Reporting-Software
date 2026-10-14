# -*- coding: utf-8 -*-
"""قواعد مطالعه سکشنالایزر — مبتنی بر دفترچه نمونه فیدر ۸ سلوط.

مقایسه با «پروفایل مرجع نمونه» انجام می‌شود (نه استاندارد الزام‌آور)؛ انحراف از
نمونه WARNING با نیاز به بازبینی مهندس است و هیچ مقداری خودکار اصلاح نمی‌شود.
"""
from app.rules.common.builder import DOMAIN_SECTIONALIZER as D, make_rule, th
from app.rules.outcome import BASIS_DOCUMENT
from app.rules.protection_labels import FUNCTION_SUFFIXES, LABELS
from app.rules.reference_profile import PAGE_SECZ, PROFILE_KEYS, SRC_SECZ

KW = dict(source=SRC_SECZ, page=PAGE_SECZ, review=True)


def _pair(rid, name, known, match, thresholds, ok_text, dev_text, priority=55):
    return [
        make_rule(f"{rid}-OK", name, D, f"{known} and {match}", "PASS",
                  finding=ok_text, thresholds=thresholds, priority=priority, **KW),
        make_rule(f"{rid}-DEV", name, D, f"{known} and not {match}", "WARNING",
                  finding=dev_text, thresholds=thresholds, priority=priority + 20,
                  evidence="مقایسه با نسبت‌های جدول تنظیمات پیشنهادی دفترچه نمونه سلوط.", **KW),
    ]


def build_rules() -> list:
    rules = [
        make_rule("SECZ-SET-MISSING", "تنظیمات توابع حفاظتی سکشنالایزر ثبت نشده", D,
                  "not has_any_function", "MISSING_DATA", requires=["protection_functions"],
                  priority=80, **KW),
        make_rule("SECZ-REF-MISSING", "تنظیمات ریکلوزر مرجع برای تنظیم سکشنالایزر ثبت نشده", D,
                  "has_any_function and not has_reference", "MISSING_DATA",
                  requires=["reference_ref"], priority=78, **KW),
        make_rule("SECZ-PROFILE-MISSING", "پروفایل مرجع نسبت‌های تنظیم تعریف نشده", D,
                  "not has_reference_profile", "MISSING_RULE",
                  thresholds=[th(k, k, BASIS_DOCUMENT) for k in PROFILE_KEYS],
                  priority=79, **KW),
    ]
    for s in FUNCTION_SUFFIXES:
        key = f"secz_pickup_ratio_{s}"
        rules += _pair(
            f"SECZ-PK-{s.upper()}", f"Pickup {LABELS[s]} نسبت به ریکلوزر", f"pk_known_{s}",
            f"pk_match_{s}", [th(key, f"نسبت Pickup {LABELS[s]}", BASIS_DOCUMENT,
                                 "جدول ۲ دفترچه سلوط")],
            "Pickup سکشنالایزر ({pk_actual_" + s + "} A) با نسبت مرجع از Pickup ریکلوزر "
            "({pk_ref_" + s + "} A) برابر ({pk_expected_" + s + "} A) مطابقت دارد.",
            "Pickup سکشنالایزر ({pk_actual_" + s + "} A) با مقدار مرجع محاسبه‌شده "
            "({pk_expected_" + s + "} A از Pickup ریکلوزر {pk_ref_" + s + "} A) تفاوت دارد.")
    for s in ("51", "51n"):
        key = f"secz_tms_offset_{s}"
        rules += _pair(
            f"SECZ-TMS-{s.upper()}", f"TMS {LABELS[s]} نسبت به ریکلوزر", f"tms_known_{s}",
            f"tms_match_{s}", [th(key, f"اختلاف TMS {LABELS[s]}", BASIS_DOCUMENT,
                                 "جدول ۲ دفترچه سلوط — تفسیر: واحد درصد")],
            "TMS سکشنالایزر ({tms_actual_" + s + "}) با مقدار مرجع ({tms_expected_" + s + "}) "
            "مطابقت دارد.",
            "TMS سکشنالایزر ({tms_actual_" + s + "}) با مقدار مرجع ({tms_expected_" + s + "}) "
            "تفاوت دارد.")
    rules += _pair(
        "SECZ-COUNTER", "شمارندهٔ سکشنالایزر نسبت به شات ریکلوزر", "counter_known", "counter_match",
        [], "شمارنده ({counter}) با تعداد شات ریکلوزر ({ref_shots}) برابر است.",
        "شمارنده ({counter}) با تعداد شات ریکلوزر ({ref_shots}) برابر نیست.")
    rules += _pair(
        "SECZ-DEADLINE", "پارامترهای Dead line سکشنالایزر", "deadline_known", "deadline_match",
        [th("secz_dead_line_current_pct", "درصد جریان Dead line", BASIS_DOCUMENT),
         th("secz_dead_line_voltage_pct", "درصد ولتاژ Dead line", BASIS_DOCUMENT)],
        "Dead line برابر {dead_line_current_pct}% جریان و {dead_line_voltage_pct}% ولتاژ نامی "
        "است و با نمونه مرجع مطابقت دارد.",
        "Dead line ({dead_line_current_pct}% جریان، {dead_line_voltage_pct}% ولتاژ) با نمونه "
        "مرجع ({secz_dead_line_current_pct}% و {secz_dead_line_voltage_pct}%) تفاوت دارد.")
    return rules
