# -*- coding: utf-8 -*-
"""قواعد مطالعه ریکلوزر — مبتنی بر دفترچه نمونه فیدر ۴ خلخال.

* هماهنگی با رله بالادست: Pickup و زمان ریکلوزر باید کمتر از بالادست باشد
  (جدول‌های ۲ و ۳ و شکل‌های ۳ و ۴ دفترچه نمونه).
* تعداد Shot، Dead time و Reclaim time: در دو نمونه مقادیر متفاوت آمده؛ حد قطعی
  تعریف نشده و Rule فقط ثبت می‌کند (یا MISSING_RULE می‌دهد).
"""
from app.rules.common.builder import DOMAIN_RECLOSER as D, make_rule, th
from app.rules.outcome import BASIS_CONFIG
from app.rules.protection_labels import FUNCTION_SUFFIXES, LABELS
from app.rules.reference_profile import PAGE_REC, SRC_REC


def _triple(prefix, name, known, ok, status_bad, finding_ok, finding_bad,
            threshold_key, threshold_label, note, priority=50):
    """سه Rule یک آزمون آستانه‌ای: منطبق / نامنطبق / آستانهٔ تعریف‌نشده."""
    t = [th(threshold_key, threshold_label, BASIS_CONFIG, note)]
    kw = dict(source=SRC_REC, page=PAGE_REC, thresholds=t, priority=priority)
    return [
        make_rule(f"{prefix}-OK", name, D, f"{known} and has_{threshold_key} and {ok}", "PASS",
                  finding=finding_ok, review=True, **kw),
        make_rule(f"{prefix}-BAD", name, D, f"{known} and has_{threshold_key} and not {ok}",
                  status_bad, finding=finding_bad, review=True, **kw),
        make_rule(f"{prefix}-NOTHRESH", name, D, f"{known} and not has_{threshold_key}", "INFO",
                  review=True, **kw),
    ]


def build_rules() -> list:
    rules = [
        make_rule("REC-LOC-MISSING", "محل نصب ریکلوزر ثبت نشده", D,
                  "not has_installation_location", "MISSING_DATA",
                  requires=["installation_location"], priority=80, review=True,
                  source=SRC_REC, page=PAGE_REC),
        make_rule("REC-SET-MISSING", "تنظیمات توابع حفاظتی ریکلوزر ثبت نشده", D,
                  "not has_any_function", "MISSING_DATA",
                  requires=["protection_functions"], priority=80, review=True,
                  source=SRC_REC, page=PAGE_REC),
        make_rule("REC-UP-MISSING", "تنظیمات تجهیز بالادست برای بررسی هماهنگی ثبت نشده", D,
                  "has_any_function and not has_upstream_settings", "MISSING_DATA",
                  requires=["upstream_settings_ref"], priority=78, review=True,
                  source=SRC_REC, page=PAGE_REC),
        make_rule("REC-SHOTS-INFO", "ثبت چرخهٔ وصل مجدد ریکلوزر", D, "has_shots", "INFO",
                  finding="ریکلوزر با {shots} شات، زمان‌های مرده {dead_times_text} و "
                          "زمان Reclaim برابر {reclaim_time_s} ثانیه ثبت شده است. حد مجاز "
                          "واحدی برای این پارامترها در دفترچه‌های مرجع تعریف نشده و "
                          "تأیید مهندس لازم است.",
                  source=SRC_REC, page=PAGE_REC, priority=40, review=True),
        make_rule("REC-PLACEMENT-MISSING", "مبنای جانمایی ریکلوزر ثبت نشده", D,
                  "not has_placement_basis", "MISSING_DATA",
                  requires=["placement_basis"], priority=70, review=True,
                  source=SRC_REC, page="بند ۲ و ۳ — صفحات ۲ و ۳"),
        make_rule("REC-PLACEMENT-INFO", "مبنای جانمایی ریکلوزر", D, "has_placement_basis", "INFO",
                  finding="مبنای جانمایی ثبت‌شده: {placement_basis}",
                  source=SRC_REC, page="بند ۲ و ۳ — صفحات ۲ و ۳", priority=40, review=True),
    ]
    # Reclaim time
    rules += _triple(
        "REC-RECLAIM", "کنترل زمان Reclaim ریکلوزر", "has_reclaim_time_s", "reclaim_ok", "FAIL",
        "زمان Reclaim ({reclaim_time_s} s) از حد تعیین‌شده ({min_reclaim_time_s} s) کمتر نیست.",
        "زمان Reclaim ({reclaim_time_s} s) از حد تعیین‌شده ({min_reclaim_time_s} s) کمتر است.",
        "min_reclaim_time_s", "حداقل زمان Reclaim (s)",
        "در دفترچه‌های نمونه مقادیر ۵ s و ۳۰۰ s آمده است؛ حد واحد تعریف نشده.")
    # حساسیت و حاشیه نسبت به بار
    rules += _triple(
        "REC-SENS", "حساسیت Pickup فاز نسبت به حداقل جریان خطا", "has_sensitivity_ratio",
        "sensitivity_ok", "WARNING",
        "نسبت حداقل جریان خطا به Pickup برابر {sensitivity_ratio:.2f} است.",
        "نسبت حداقل جریان خطا به Pickup برابر {sensitivity_ratio:.2f} و کمتر از حد تعیین‌شده است.",
        "min_sensitivity_ratio", "حداقل نسبت حساسیت (Imin/Pickup)",
        "در دفترچه‌های نمونه حد حساسیت تعریف نشده است.")
    rules += _triple(
        "REC-LOADMARGIN", "حاشیه Pickup فاز نسبت به جریان بار", "has_load_ratio", "load_ratio_ok",
        "WARNING",
        "نسبت Pickup به جریان بار برابر {pickup_load_ratio:.2f} است.",
        "نسبت Pickup به جریان بار برابر {pickup_load_ratio:.2f} و کمتر از حد تعیین‌شده است.",
        "min_pickup_to_load_ratio", "حداقل نسبت Pickup به جریان بار",
        "در دفترچه‌های نمونه حاشیه Pickup نسبت به بار تعریف نشده است.")
    # بررسی‌های فیزیکی (بدون آستانهٔ ساختگی): Pickup نباید زیر جریان بار یا بالای جریان خطای
    # در دسترس باشد؛ در غیر این صورت رله یا بی‌جا تریپ می‌کند یا خطا را هرگز نمی‌بیند.
    rules += [
        make_rule("REC-PICKUP-BELOW-LOAD", "Pickup فاز کمتر از جریان بار", D,
                  "has_load_ratio and pickup_below_load", "FAIL",
                  finding="Pickup تابع ۵۱ ({pickup_51} A) کمتر از جریان بار ({load_current_a} A) است؛ "
                          "ریکلوزر در بار عادی تحریک می‌شود.",
                  evidence="مقایسهٔ مستقیم Pickup و جریان بار (بدون آستانه).",
                  source=SRC_REC, page=PAGE_REC, priority=78, review=True),
        make_rule("REC-PICKUP-ABOVE-MINFAULT", "Pickup فاز بالاتر از حداقل جریان خطا", D,
                  "pickup_above_minfault", "FAIL",
                  finding="Pickup تابع ۵۱ ({pickup_51} A) از حداقل جریان اتصال کوتاه ({min_fault_a:.0f} A) "
                          "بیشتر است؛ خطای حداقل توسط ریکلوزر دیده نمی‌شود.",
                  evidence="مقایسهٔ مستقیم Pickup و حداقل جریان خطا (بدون آستانه).",
                  source=SRC_REC, page=PAGE_REC, priority=79, review=True),
        make_rule("REC-INST-ABOVE-MAXFAULT", "Pickup آنی بالاتر از حداکثر جریان خطا", D,
                  "inst_above_maxfault", "WARNING",
                  finding="Pickup تابع ۵۰ ({pickup_50} A) از جریان اتصال کوتاه حداکثر ({max_fault_a:.0f} A) "
                          "بیشتر است؛ المان لحظه‌ای در این محل هرگز عمل نمی‌کند.",
                  evidence="مقایسهٔ مستقیم Pickup آنی و حداکثر جریان خطا (بدون آستانه).",
                  source=SRC_REC, page=PAGE_REC, priority=70, review=True),
    ]
    # هماهنگی منحنی جریان–زمان (TCC) با بالادست — توابع تأخیری ۵۱ و ۵۱N
    # (شکل‌های ۳ و ۴ دفترچه نمونه: منحنی ریکلوزر باید در تمام محدودهٔ جریان‌های
    # خطا زیر منحنی رله سر فیدر قرار گیرد؛ محاسبه با منحنی‌های IEC NI/VI/EI و TMS درصدی)
    for suf in ("51", "51n"):
        rules += [
            make_rule(f"REC-CURVE-{suf.upper()}-OK",
                      f"هماهنگی منحنی جریان–زمان {LABELS[suf]} با بالادست", D,
                      f"curve_known_{suf} and curve_ok_{suf}", "PASS",
                      finding="{curve_detail_" + suf + "}", source=SRC_REC,
                      page="شکل‌های ۳ و ۴ — صفحات ۶ و ۷", priority=56, review=True,
                      evidence="محاسبهٔ زمان عملکرد از رابطهٔ IEC 60255 "
                               "t = TMS·k/((I/Ip)^α − 1) در محدودهٔ جریان‌های خطا."),
            make_rule(f"REC-CURVE-{suf.upper()}-BAD",
                      f"عدم هماهنگی منحنی جریان–زمان {LABELS[suf]} با بالادست", D,
                      f"curve_known_{suf} and not curve_ok_{suf}", "FAIL",
                      finding="{curve_detail_" + suf + "}", source=SRC_REC,
                      page="شکل‌های ۳ و ۴ — صفحات ۶ و ۷", priority=76, review=True,
                      evidence="منحنی ریکلوزر در بخشی از محدودهٔ خطا بالاتر از "
                               "منحنی بالادست است (محاسبهٔ IEC 60255)."),
        ]
    # هماهنگی با بالادست — هر تابع
    for suf in FUNCTION_SUFFIXES:
        rules += [
            make_rule(f"REC-COORD-{suf.upper()}-OK",
                      f"هماهنگی {LABELS[suf]} با بالادست", D,
                      f"coord_known_{suf} and coord_ok_{suf}", "PASS",
                      finding="{coord_detail_" + suf + "}", source=SRC_REC, page=PAGE_REC,
                      priority=55, review=True,
                      evidence="مقایسهٔ Pickup و زمان ریکلوزر با رله بالادست؛ منحنی‌ها باید "
                               "در نرم‌افزار شبیه‌ساز نیز تأیید شود."),
            make_rule(f"REC-COORD-{suf.upper()}-BAD",
                      f"عدم هماهنگی {LABELS[suf]} با بالادست", D,
                      f"coord_known_{suf} and not coord_ok_{suf}", "FAIL",
                      finding="{coord_detail_" + suf + "}", source=SRC_REC, page=PAGE_REC,
                      priority=75, review=True,
                      evidence="Pickup یا زمان ریکلوزر از بالادست کمتر نیست."),
        ]
    return rules
