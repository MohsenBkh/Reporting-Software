# -*- coding: utf-8 -*-
"""پروفایل مرجع قواعد حفاظتی — برگرفته از دفترچه‌های نمونه (نه استاندارد الزام‌آور).

هر مقدار فقط در صورتی اینجا هست که صراحتاً در یکی از دفترچه‌های نمونه آمده باشد.
مقادیری که در دو نمونه متفاوت بودند (تعداد Shot، Dead time، Reclaim time) عمداً
**تعریف نشده‌اند**؛ Rule Engine برای آن‌ها ``MISSING_RULE`` تولید می‌کند تا مهندس
یا دستورالعمل واقعی آستانه را تعیین کند. کاربر می‌تواند با ``thresholds`` در
``build_context`` هر مقدار را بازنویسی کند.

تفسیر «۳ درصد کمتر از TMS ریکلوزر»: TMS در جدول‌ها بر حسب درصد است (مثلاً 7.5%
برای ریکلوزر و ظاهراً 4.5% برای سکشنالایزر)؛ این‌جا «۳ واحد درصد» فرض شده و
در خروجی Rule با ``engineer_review_required`` علامت‌گذاری می‌شود.
"""
from __future__ import annotations

SRC_SECZ = ("دفترچه مطالعات هماهنگی و تنظیمات حفاظتی سکشنالایزر فیدر ۸ سلوط "
            "(PD-21-001، دی ۱۴۰۴)")
PAGE_SECZ = "جدول ۲ و بند ۳ — صفحه ۲"
SRC_REC = ("دفترچه مطالعات جایابی و هماهنگی حفاظتی ریکلوزر فیدر ۴ خلخال "
           "(DM-1301، خرداد ۱۴۰۴)")
PAGE_REC = "بند ۴ و جدول‌های ۲ و ۳ و شکل‌های ۳ و ۴ — صفحات ۴ تا ۶"

REFERENCE_PROFILE: dict[str, float] = {
    # نسبت Pickup سکشنالایزر به Pickup ریکلوزر (جدول ۲ دفترچه سلوط)
    "secz_pickup_ratio_51": 0.95,
    "secz_pickup_ratio_50": 0.90,
    "secz_pickup_ratio_51n": 0.90,
    "secz_pickup_ratio_50n": 0.90,
    # اختلاف TMS (واحد درصد) نسبت به ریکلوزر برای توابع تأخیری
    "secz_tms_offset_51": 3.0,
    "secz_tms_offset_51n": 3.0,
    # Dead line سکشنالایزر (جدول ۲)
    "secz_dead_line_current_pct": 10.0,
    "secz_dead_line_voltage_pct": 20.0,
}
PROFILE_KEYS = tuple(REFERENCE_PROFILE)

# آستانه‌هایی که در دفترچه‌های نمونه حد واحد ندارند — عمداً تعریف نشده‌اند
UNDEFINED_THRESHOLDS = ("min_reclaim_time_s", "min_sensitivity_ratio",
                        "min_pickup_to_load_ratio")
