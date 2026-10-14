# ReportForge v2.0.0 — بستهٔ کامل (فازهای ۱ و ۲)

همهٔ فایل‌ها **کامل و اعمال‌شده** هستند و ساختار پوشه‌ها با ریپازیتوری یکی است.
کافی است محتویات این پوشه را روی ریپازیتوری (شاخهٔ `arena/01a10d0f-reporting-software`) کپی کنید
(ترجیحاً در شاخهٔ جدید `feature/studies-workspace-v2`). هیچ patch دستی لازم نیست.

## فایل‌های موجود که **جایگزین** می‌شوند (نسخهٔ کامل)
| فایل | تغییر |
|---|---|
| app/core/models.py | تنظیمات حفاظتی کامل روی RecloserInfo/SectionalizerInfo، title_text، ثبت Nested (فیلدهای قدیمی حفظ شد) |
| app/core/report_types.py | نوع‌های `recloser` فعال و `combined_protection` |
| app/core/project_manager.py | بارگذاری/مهاجرت/ذخیرهٔ `workspace.json` |
| app/core/validation.py | `validate_protection` برای ریکلوزر و ترکیبی (کمبود داده = هشدار) |
| app/report/pipeline.py | مسیر ریکلوزر/ترکیبی به `ProtectionReportGenerator` |
| app/main.py | پنجرهٔ Engineering پیش‌فرض؛ `--classic` رابط قبلی |
| app/ui/protection_page.py | حذف پیام «ریکلوزر هنوز فعال نشده» |
| tests/test_v130_sectionalizer.py | تست «ریکلوزر مسدود» به تست «ریکلوزر گزارش می‌سازد» تبدیل شد |

## فایل‌های جدید
app/core: protection_models, studies, workspace, forecast_engine, project_tree
app/rules: reference_profile, protection_labels, protection_context, domains, common/, recloser/, sectionalizer/, heavy_applicant/
app/report: composer
app/ui/shell: design, inspector_model, dashboard_model, explorer, inspector, dashboard_page,
settings_editor, protection_settings_page, report_center_page, engineering_window
tests: test_v200_{workspace,protection_rules,composer,forecast_engine,backward_compat,ui_models,ui_shell}

## اجرا
```
QT_QPA_PLATFORM=offscreen pytest tests/
python -m app.main            # Engineering Desktop
python -m app.main --classic  # رابط قبلی
```
