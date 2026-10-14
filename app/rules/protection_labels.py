# -*- coding: utf-8 -*-
"""برچسب‌های توابع حفاظتی با پسوند کوتاه (51, 50, 51n, 50n)."""
FUNCTION_SUFFIXES = ("51", "50", "51n", "50n")
LABELS = {
    "51": "تابع ۵۱",
    "50": "تابع ۵۰",
    "51n": "تابع ۵۱N",
    "50n": "تابع ۵۰N",
}
def key_of(suffix: str) -> str:
    return "f" + suffix
