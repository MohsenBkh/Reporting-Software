# TEST REPORT — ReportForge 1.0.3

اجرا: `python -m pytest tests -q` (Python 3.12، PySide6 در حالت `offscreen`)
نتیجه: **87 تست — همه موفق** (قبل از ارتقا: 28 تست؛ 3 تست قدیمی مطابق منطق مهندسی جدید به‌روز شد).

| فایل | تعداد | محدوده |
|---|---|---|
| test_core.py, test_fixes.py, test_scenario_* | 27 | رگرسیون نسخه 1.0.2 (محاسبات، Rule Engine، سناریوهای نیرورسانی/افزایش قدرت/ولتاژ) |
| test_v103_forecast_quality.py | 10 | R²، Outlier، جهش/مانور، فاصله سال، داده ثابت/ناکافی، آستانه‌های قابل تنظیم، پیش‌بینی دستی |
| test_v103_engineering_rules.py | 7 | ولتاژ مطلق در برابر اثر متقاضی، تلفات تنها، severity همه Ruleها، FC-REVIEW، نبود Placeholder |
| test_v103_review_validation.py | 21 | Accept/Edit/Reject/Override، حفظ تصمیم، کهنگی، ذخیره/بازیابی، سازگاری پروژه قدیمی، Validation، Traceability، پیام خطا، Log |
| test_v103_word_output.py | 11 | ساختار DOCX، RTL، TOC، «صفحه X از Y»، Caption و شماره‌گذاری، سرستون جدول، ویژگی‌های سند، ساختار طلایی، پیوست‌ها، Deterministic |
| test_v103_ui.py | 11 | ناوبری همه صفحات در دو Theme، قفل بدون پروژه، Workflow، بازبینی، تولید Background، ویرایش دستی، منبع MANUAL |

## بررسی بصری (دستی)
- DOCX نمونه با LibreOffice به PDF تبدیل و بازبینی شد: جلد بدون شماره، فهرست مطالب، «صفحه X از Y»، جداول RTL، کپشن‌ها، پیوست الف.
- اسکرین‌شات صفحات برنامه در Theme روشن و تاریک بررسی شد.

## محدودیت‌ها و موارد باز
- **Golden Report واقعی**: دو گزارش مرجع (فایل‌های Word نمونه) همراه ورودی نبودند؛ تست `test_golden_structure_regression` فقط ساختار بخش‌ها را قفل می‌کند. با اضافه کردن دو گزارش مرجع می‌توان مقایسه متنی/جدولی دقیق افزود.
- فونت‌های B Nazanin / B Titr و رندر نهایی Word فقط در Windows+Word قابل تأیید کامل است (در Linux با LibreOffice جایگزین می‌شوند).
- تست UI در `offscreen` است؛ تعامل ماوس/صفحه‌کلید واقعی و DPI بالا در دستگاه هدف باید یک‌بار دستی دیده شود.
- فونت UI: Vazirmatn در صورت نصب، وگرنه Segoe UI/Tahoma.
