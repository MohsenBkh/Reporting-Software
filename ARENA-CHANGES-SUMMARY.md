# دقیقاً چه چیزی تغییر کرد؟ — «تغییرات آرنا» (نسخهٔ جاری: ۱.۴.۰)

> **آخرین به‌روزرسانی (۱.۴.۰ — تب مجزا «سکشنالایزر و ریکلوزر»):** به پیشنهاد کارفرما
> بخش سکشنالایزر و ریکلوزر از مطالعه مصارف سنگین جدا و در یک **تب مجزا** تجمیع شد؛
> طراحی رابط از الگوهای **گالری طراحی ویندوز (WinUI Gallery)** پیروی می‌کند.
>
> ۱) صفحه جدید `app/ui/protection_page.py` با آیتم ناوبری «سکشنالایزر و ریکلوزر»:
> دو تب (سکشنالایزر فعال / ریکلوزر در برنامه) با فرم یکسان، ذخیره جداگانه در
> `Project.sectionalizer` و `Project.recloser` (اسکلت جدید `RecloserInfo`)، و نوار
> اطلاع‌رسانی تنظیم «نوع گزارش» با یک کلیک.
> ۲) فرم سکشنالایزر از صفحه «پروژه» به این تب منتقل شد؛ صفحه پروژه فقط قالب گزارش
> را تعیین می‌کند.
> ۳) استایل کارت‌ها و نوارهای اطلاع‌رسانی (`theme.py`) + آیکن `protection` در هر دو
> تم روشن/تاریک.
>
> آزمون‌ها: **۹ تست رابط جدید** (`test_v131_protection_page.py`)؛ مجموعه غیررابط:
> **۱۷۰ تست موفق**. مستند: `docs/REPORT_LAYOUT_v1.3.0.md` (بخش تب حفاظتی).

> **به‌روزرسانی (۱.۳.۰ — چیدمان مرجع + انواع گزارش):** دو دستور کارفرما اعمال و آزمون شد.
>
> ۱) **چیدمان گزارش دقیقاً مطابق گزارش مرجع مهر ۱۴۰۵** — ۹ بخش به همین ترتیب:
> مقدمه ← تحلیل بارگذاری ← پیش‌بینی ← **ایستگاه‌های نزدیک** ← **خطوط نزدیک** ←
> پخش بار قبل ← پخش بار بعد ← کنترل بارگذاری ← نتیجه‌گیری و پیشنهادات.
> ایستگاه‌ها/خطوط به قبل از پخش بار منتقل شدند؛ «جمع‌بندی» تکراری وقتی نتیجه‌گیری
> مطالعه هست حذف شد؛ بخش‌های تکمیلی موتور مطالعه پیش‌فرض خاموش شدند (از تنظیمات
> قابل فعال‌سازی‌اند). بند الف مقدمه (مشخصات تقاضا) مطابق مرجع اضافه شد.
> ۲) **انواع گزارش** (`app/core/report_types.py`): «متقاضیان سنگین» (کامل)،
> «سکشنالایزر» (اسکلت فعال — `app/report/sectionalizer.py`) و «ریکلوزر» (در برنامه).
> عنوان دفترچه در جلد/سربرگ/مشخصات سند بر اساس نوع گزارش است؛ انتخاب نوع در صفحه
> «پروژه»؛ ریکلوزر پیام «در نسخه‌های بعدی» می‌دهد. اسکلت سکشنالایزر پنج‌بخشی آمادهٔ
> گسترش با جزئیات ارسالی کارفرماست (فیلدهای `SectionalizerInfo`، متن‌های
> `sectionalizer.json`). اعتبارسنجی برای هر نوع مسیر جداگانه دارد.
>
> آزمون‌ها: **۲۰ تست جدید** (`test_v130_report_layout.py` + `test_v130_sectionalizer.py`)؛
> مجموعهٔ غیررابط گرافیکی: **۱۷۰ تست موفق**. راستی‌آزمایی خروجی واقعی با
> `python tools/build_demo.py` → بخش‌ها دقیقاً به ترتیب ۹گانهٔ مرجع تولید شدند.
> مستند فنی: `docs/REPORT_LAYOUT_v1.3.0.md`.

> **به‌روزرسانی (۱.۲.۰ — «اصلاحات نسخهٔ بعدی»):** پنج بند دستور کارفرما اعمال و آزمون شد.
>
> ۱) **جدول‌های ورود داده شبیه Excel** (`app/ui/excel_table.py`): پاک‌کردن با `Delete` (بدون
> گذاشتن صفر)، کپی/برش/چسباندن با `Ctrl+C/X/V` (بلوک چندخانه‌ای از Excel + ساخت خودکار ردیف)،
> `Enter` = ردیف پایین، منوی راست‌کلیک (کپی، چسباندن، پاک‌کردن، درج/حذف ردیف، انتخاب همه).
> در جدول‌های گزارش فقط کپی فعال است.
> ۲) **بارگذاری کل فیدر** = پیک فیدر + بار اضافه‌شدهٔ جدید؛ `≥ ۷ MW` ⇒ «بارگذاری بحرانی»
> (`LD-CRITICAL`، WARNING) و `≥ ۸ MW` ⇒ «بارگذاری شدیداً بحرانی» (`LD-SEVERE`، FAIL). «توضیحات
> فنی» دو راهکار می‌دهد: **بازآرایی فیدر** با انتقال بار به **فیدر همجوار نزد ثبت‌شده در ورودی‌ها**
> و **احداث فیدر جدید** — همیشه «نیازمند تأیید مهندس». آستانه‌ها در تنظیمات قابل ویرایش‌اند
> (۷.۰/۸.۰) و آستانه‌های سند (۱۰/۳۰) دست‌نخورده باقی مانده‌اند.
> ۳) **کلید «در گزارش (On/Off)»** برای همهٔ ورودی‌ها: فیدر، تقاضا، ایستگاه، خط، متقاضی همزمان،
> سناریو، فیدر همجوار، شکل، سال‌های پیک واقعی و سطرهای پیش‌بینی. ردیف خاموش از گزارش،
> اعتبارسنجی، محاسبات و سناریوها حذف می‌شود اما **مقدارش پاک نمی‌شود**.
> ۴) **بخش تصاویر**: تعیین **بخش گزارش**، **اولویت/ترتیب** و **کپشن مستقل** برای هر شکل +
> چند شکل برای یک بخش (به‌همراه «تکثیر شکل»).
> ۵) **نگاشت ستون‌ها با نام ستون (نه شماره ستون)** در همهٔ جدول‌های برنامه؛ حذف/جابه‌جایی ستون
> هیچ فیلدی را جابه‌جا نمی‌کند.
> ۶) بخش «کنترل بارگذاری کل فیدر» در گزارش + نمایش آستانه‌های ۷/۸ مگاوات در جدول مهندسی فیدر.
>
> آزمون‌ها: **۱۸۵ تست موفق** (بدون `test_v103_ui.py`)، **۱۲ تست** رابط گرافیکی، و اجرای کامل
> `tools/ui_check_study.py` («هیچ متغیر پرنشده‌ای وجود ندارد»). مستند فنی: `docs/INCREMENTAL_FIXES_v1.2.0.md`
> و `docs/STUDY_RULE_SET_v1.2.0.md`. ساخت نمونهٔ تکرارپذیر: `python tools/build_demo.py`.

> **به‌روزرسانی (۱.۱.۲):** کرش فایل اجرایی (`ReportForge.exe`) در شروع برنامه رفع شد.
> علت: باگ CPython 3.12.0–3.12.3 در `repr` ماژول‌های مجازی `six.moves` که در exe از مسیر
> `shiboken → inspect.getsource → pyi_rth_inspect → inspect.getfile` فعال می‌شد.
> اصلاح: Runtime Hook (`app/pyi_rth_reportforge.py`) + محافظ مشترک (`app/utils/import_guard.py`)
> + `runtime_hooks` در `ReportForge.spec` + دستور `--smoke-test` و اجرای خودکار آن در `build_exe.bat`.
> جزئیات و شواهد: `docs/EXE_BUILD_FIX_v1.1.2.md` و `screenshots/exe-fix-v1.1.2.html`.
> آزمون‌ها: **۱۵۲ تست موفق** + اجرای کامل `tools/ui_check_study.py`.

## ۰. خلاصهٔ نسخهٔ ۱.۱.۲ (رفع کرش exe)

| موضوع | قبل | بعد |
|---|---|---|
| اجرای `dist\ReportForge.exe` | بسته‌شدن فوری با `AttributeError: '_SixMetaPathImporter' object has no attribute '_path'` | بالا آمدن سالم (تأیید با `--smoke-test` ⇒ `RESULT: OK`) |
| ریشهٔ خطا | `importlib._module_repr_from_spec` نسخهٔ 3.12.0–3.12.3 روی ماژول مجازی `six.moves` | همان مسیر با سه لایه محافظ بسته شد (مستقل از نسخهٔ Python) |
| فایل‌های جدید | — | `app/pyi_rth_reportforge.py`، `app/utils/import_guard.py`، `app/utils/selfcheck.py`، `tests/test_v112_exe_guard.py`، `docs/EXE_BUILD_FIX_v1.1.2.md` |
| ابزار تشخیص | — | `ReportForge.exe --smoke-test` + گزارش `ReportForge-smoke.txt` کنار exe |
| ساخت exe | `build_exe.bat` | همان دستور؛ در پایان خودآزمون اجرا و نتیجه نمایش داده می‌شود |
| اجرای سورسی | `python -m app.main` | بدون تغییر (آزمون شد) |


> **به‌روزرسانی:** صفحهٔ ورود داده و بخش تنظیمات هم اضافه شد. اکنون در برنامه می‌بینید:
> Sidebar → **«مطالعه مصارف سنگین»** (۵ جدول ورود داده) و **تنظیمات** → دو گروه «حدآستانه‌های مطالعه
> مصارف سنگین» و «پارامترهای هزینه بررسی اقتصادی». در گزارش هم جدول‌های «ایستگاه‌های نزدیک به محل تقاضا»،
> «خطوط نزدیک به محل تقاضا» و بخش **«نتیجه‌گیری و پیشنهادات»** اضافه شده است.
> تصاویر واقعی از اجرای برنامه: `screenshots/preview.html` (و پوشهٔ `screenshots/`).

## ۱. حجم تغییرات (قابل راستی‌آزمایی با `git diff --stat main arena-changes`)

| شاخص | مقدار |
|---|---|
| فایل‌های تغییر یافته | **۴۳ فایل** |
| خطوط افزوده / حذف‌شده | **+۷٬۷۷۸ / −۹۸** |
| کامیت‌ها روی برنچ `arena-changes` | **۳ کامیت** (۱.۱.۰ موتور، ۱.۱.۰ UI، ۱.۱.۱ اصلاحات) |
| نسخه | `1.0.3` → `1.1.0` (`app/__init__.py`) |
| Rule تحلیلی جدید | **۵۶** |
| Rule تولید سناریو | **۳** |
| متن فارسی جدید | **۷۹** (`app/report/data/texts/study.json`) |
| تست جدید | **۶۲** (جمع: **۱۳۸ تست موفق**؛ شامل ۱۴ تست UI مطالعه و ۷ تست جداسازی پروفیل/پیش‌بینی) |
| فایل‌های JSON قواعد | **۹ فایل** در `app/rules/data/study_rules/` |

## ۲. نگاشت «بندهای پرامپت شما» → «آنچه ساخته شد»

| بند پرامپت | آنچه پیاده شد | فایل‌ها | چطور راستی‌آزمایی کنید |
|---|---|---|---|
| ۱. ساختار داده‌های موردنیاز (A تا E) | `DemandInfo` (بدون/با ضریب همزمانی، دیماند موجود)، `SubstationCandidate` (فاصله، ظرفیت، T1/T2 Loading و Peak، تعداد فیدر)، `LineCandidate` (فاصله، MVA/MW/A، افت ولتاژ قبل/بعد، SC max/min)، `CoincidentDemand` (توان موجود/جدید/دلتا/محل/امکان‌تأمین)، `SupplyScenario` (نوع، طول خط، ٪هوایی/زمینی، تجهیزات، هزینه) | `app/core/models.py` | `python -c "from app.core.models import *; print(DemandInfo(), LineCandidate())"` |
| ۲. Ruleهای تحلیلی (۱ تا ۶) | ۵۶ Rule در ۸ حوزه؛ محاسبهٔ صریح `Delta = After − Before`؛ مقایسهٔ پیک/جریان/افت ولتاژ/اتصال کوتاه؛ تفکیک «مقدار مطلق» از «تغییر ناشی از متقاضی»؛ محاسبهٔ افزایش بار متقاضیان همزمان و مجموع؛ بررسی توپولوژیکی تأمین مشترک | `app/rules/data/study_rules/*.json` (۹ فایل)، `app/core/study.py` | `python tools/export_rule_set.py` سپس مشاهدهٔ `docs/STUDY_RULE_SET_v1.1.0.md` |
| ۳. Ruleهای سناریو تأمین | Scenario 1 (فیدر جدید) و Scenario 2 (فیدر موجود/جایگزین) **تولید** می‌شوند با Technical Basis / Required Network Changes / Candidate Feeder / Estimated Cost / Required Equipment / Supporting Evidence / Review Status؛ **هیچ توصیه‌ای انجام نمی‌شود** + Rule `SC-NO-SELECTION-CRITERION` | `app/core/scenarios.py`، `scenario_rules.json`، `scenario_check_rules.json` | `python make_demo_report.py` → جدول «سناریوهای تأمین برق» |
| ۴. بررسی اقتصادی پارامتریک | پارامترهای هزینه در `settings.json` (خارج از کد، پیش‌فرض `None`)؛ اقلام جداگانه (هوایی/زمینی/پست زمینی/کلیدزنی/حفاظتی)؛ **نبود هزینه = `MISSING_DATA` (نه صفر)**؛ Rule `EC-COST-ZERO-NO-BASIS` برای «صفر بدون مبنا» | `app/core/settings.py` (`CostSettings`)، `economics_rules.json`، `app/core/study.py` (`cost_estimate`) | تست `test_cost_parameters_are_parametric_and_not_hardcoded` |
| ۵. کنترل ناسازگاری (Cross Validation) | Rule با **`Rule ID = DATA_INCONSISTENCY`** و وضعیت `REQUIRES_ENGINEER_REVIEW`: مغایرت مجموع افزایش بار با کل بار گزارش‌شده و مغایرت تقاضای درخواستی با تقاضای مبنای تحلیل؛ بدون حدس یا جایگزینی خودکار | `crosscheck_rules.json`، `app/core/validation.py` | تست `test_load_sum_mismatch_is_data_inconsistency_without_guessing` |
| ۶. وضعیت خروجی استاندارد | خروجی دقیقاً با کلیدهای خواسته‌شده: `rule_id, category, status, input_values, calculated_values, finding, evidence, source, source_page, recommended_text, engineer_review_required` + وضعیت‌های `PASS/WARNING/FAIL/INFO/DATA_ERROR/REQUIRES_ENGINEER_REVIEW` (+ `MISSING_RULE/MISSING_DATA`) | `app/rules/outcome.py` | تست `test_every_rule_result_follows_standard_schema` |
| ۷. ممنوعیت اختراع آستانه | هر Rule آستانه‌هایش را **اعلام** می‌کند (`thresholds` با `basis` = سند مرجع/پیکربندی)؛ نبود آستانه → `MISSING_RULE` و **هیچ متنی تولید نمی‌شود** | `rule_engine.py` (`ThresholdRef`, `_build_result`)، همهٔ JSONها | تست `test_missing_threshold_produces_missing_rule_and_no_text` |
| ۸. ارتباط با Report Generator | ۷ بخش جدید Word/پیش‌نمایش + جدول کنترل کیفیت Ruleها + پیوست ردیابی؛ تولید متن فقط با دادهٔ معتبر؛ Findings قابل Accept/Edit/Reject/Override | `app/report/study_sections.py`، `study.json`، `text_generator.py` | `python tools/ui_check_study.py` |
| ۹. اصل «تحلیل‌گر قابل‌ردیابی» | زنجیرهٔ `Input → Calculation → Rule → Finding → Evidence → Report Text` با متد `trace_lines()` و خروجی `to_dict()/to_json()` | `app/rules/outcome.py` | تست `test_rule_result_trace_chain_is_complete` |

## ۳. فهرست کامل Ruleها (۵۹ مورد)

| حوزه | تعداد | شناسه‌ها |
|---|---|---|
| اطلاعات تقاضا | ۷ | `D-DEMAND-COMPLETE`، `D-COINCIDENCE-NOT-APPLIED`، `D-COINCIDENCE-OVER-ONE`، `D-DELTA-POWER`، `D-DEMAND-FALLBACK`، `D-DEMAND-HEAVY-LIMIT`، `D-DEMAND-HEAVY-NO-THRESHOLD` |
| ایستگاه‌های نزدیک | ۷ | `SS-DESCRIBE`، `SS-DATA-INCOMPLETE`، `SS-LOADING-CHECK-NO-THRESHOLD`، `SS-LOADING-MISMATCH`، `SS-LOADING-LEVEL`، `SS-LOADING-LEVEL-NO-THRESHOLD`، `SS-NO-DATA` |
| خطوط نزدیک | ۱۷ | `LN-PEAK-DESCRIBE`، `LN-DELTA-CALC`، `LN-ABSOLUTE-VS-DELTA`، `LN-DELTA-EXCEEDS-LIMIT`، `LN-PREEXISTING-DROP`، `LN-VDROP-ORDER-ERROR`، `LN-CURRENT-LIMIT-MISSING`، `LN-CURRENT-OVER`، `LN-CURRENT-OK`، `LN-CURRENT-CHECK-NO-THRESHOLD`، `LN-CURRENT-MISMATCH`، `LN-SC-INCONSISTENT`، `LN-SC-LIMIT-MISSING`، `LN-SC-OVER`، `LN-DATA-INCOMPLETE`، `LN-DELTA-LIMIT-NO-THRESHOLD`، `LN-NO-DATA` |
| متقاضیان همزمان | ۴ | `CD-LIST`، `CD-TOTAL-LOAD`، `CD-DATA-INCOMPLETE`، `CD-NONE` |
| توپولوژی تأمین مشترک | ۴ | `TP-SHARED-SUPPLY-REVIEW`، `TP-SHARED-SUPPLY-EVIDENCED`، `TP-SHARED-SUPPLY-NO-EVIDENCE`، `TP-SINGLE-POINT` |
| سناریو | ۷ | تحلیل: `SC-GENERATED`، `SC-NO-SELECTION-CRITERION`، `SC-INFO-INCOMPLETE`، `SC-NONE` + تولید: `SC-GEN-NEW-FEEDER`، `SC-GEN-EXISTING-FEEDER`، `SC-GEN-ALTERNATIVE-FEEDER` |
| بررسی اقتصادی | ۷ | `EC-COST-VALUE`، `EC-COST-ZERO-NO-BASIS`، `EC-COST-MISSING`، `EC-PARAMETRIC-NO-PARAMS`، `EC-PARAMETRIC-ESTIMATE`، `EC-EXCLUDED-ITEMS`، `EC-ROUTE-LENGTH-VS-DISTANCE` |
| کنترل ناسازگاری | ۶ | `DATA_INCONSISTENCY` (×۲: مجموع بار و مبنای تقاضا)، `XC-LOAD-SUM-OK`، `XC-DEMAND-BASE-OK`، `XC-NO-BASELINE-SUM`، `XC-NO-BASELINE-DEMAND` |

## ۴. چرا در برنامه «چیزی نمی‌بینید» و چطور ببینید

**دلیل:** Rule Engine پشت صحنه است. نتیجهٔ آن در سه جای برنامه دیده می‌شود، ولی تنها **وقتی دادهٔ مطالعه در پروژه باشد**:

1. **مطالعه مصارف سنگین (Sidebar)** → ۵ جدول ورود داده (تقاضا / ایستگاه‌های نزدیک / خطوط نزدیک / متقاضیان همزمان و کنترل داده / مسیر و هزینهٔ سناریوها).
2. **تنظیمات** → «حدآستانه‌های مطالعه مصارف سنگین» + «پارامترهای هزینه بررسی اقتصادی» (تعریف‌نشده = `None`).
3. **پیش‌نمایش گزارش / خروجی Word** → ۷ بخش مطالعه + جدول‌های مرجع «ایستگاه‌های نزدیک به محل تقاضا»، «خطوط نزدیک به محل تقاضا» و بخش «نتیجه‌گیری و پیشنهادات».
4. **صفحهٔ تحلیل مهندسی** → جدول Findings (یک ردیف به‌ازای هر Rule اجراشده) و جدول اعتبارسنجی.
5. **صفحهٔ بازبینی مهندس** → همان Findings با Accept/Edit/Reject/Override.

**سه راه دیدن همین حالا:**

| راه | دستور / کار |
|---|---|
| پروژهٔ نمونه را در برنامه باز کنید | برنامه → **بازکردن پروژه** → فایل `پروژه_نمونه_مطالعه/project.json` → برو به «پیش‌نمایش گزارش» (خروجی آزمایش‌شده: ۱۴ بخش، ۴۲ Finding) |
| آزمون خودکار اجرای برنامه | `python tools/ui_check_study.py` |
| گزارش Word آماده | فایل `demo/مطالعه تأمین برق متقاضی نمونه.docx` (۸ جدول، شامل جدول سناریوها و بررسی اقتصادی) |

## ۵. وضعیت فعلی و نکات باقی‌مانده (شفاف باشم)

**انجام شد (در سه کامیت):**

- صفحهٔ **«مطالعه مصارف سنگین»** در Sidebar با ۵ تب ورود داده؛ ذخیرهٔ خودکار در `project.json`
  هنگام خروج از صفحه (نیازی به ویرایش دستی فایل نیست). الگوی صفحه: `app/ui/study_page.py`.
- تب تنظیمات: گروه **«حدآستانه‌های مطالعه مصارف سنگین»** (تلورانس بارگیری ایستگاه، تلورانس جریان خط،
  حد هشدار بارگیری، حد اتصال کوتاه، تلورانس مجموع بار، حد مصرف سنگین) و گروه **«پارامترهای هزینهٔ
  بررسی اقتصادی»** (هوایی/زمینی هر کیلومتر، پست زمینی، کلیدزنی، حفاظتی، سایر). هر مقدار تعریف‌نشده
  `None` می‌ماند ⇒ Rule مربوطه `MISSING_RULE` / هزینهٔ نبوده `MISSING_DATA` (هرگز صفر).
- دکمه‌های «تولید/بازتولید سناریوها از Rule Engine» و «محاسبهٔ برآورد پارامتریک هزینه» در تب سناریوها.
- جدول‌های مرجع گزارش + بخش «نتیجه‌گیری و پیشنهادات» (یک جدول با سرستون ادغام‌شده و سه ردیف
  نکات تحلیلی / سناریوهای پیشنهادی / بررسی اقتصادی سناریوها) و پشتیبانی سلول چندخطی در Word/HTML.

**اصلاحات v1.1.1 (خواستهٔ شما):**

| خواسته | پیاده‌سازی | آزمون |
|---|---|---|
| جدول تب «متقاضیان و کنترل داده» دیده نمی‌شد؛ ردیف‌ها با افزودن متقاضی نمایش داده نمی‌شدند | ارتفاع کمینهٔ جدول‌ها (۲۲۰–۲۴۰px) + ناحیهٔ اسکرول برای هر تب + `fit_columns` پس از هر تغییر ردیف | `test_coincident_table_is_visible_and_keeps_rows`، `test_study_tabs_are_scrollable` |
| حذف ستون‌ها هم ممکن باشد | دکمهٔ «حذف ستون انتخاب‌شده»، کلیک راست روی سرستون، «بازگرداندن ستون‌ها»؛ نگاشت داده بر مبنای عنوان ستون | `test_delete_and_restore_columns_roundtrip`، `test_column_menu_offers_delete_and_restore` |
| پس از پیام موفقیت تولید، بخش‌های «آمادگی»/«تنظیمات خروجی» روی هم می‌افتادند | کل صفحه در `QScrollArea` + حداقل ارتفاع بخش‌ها (آمادگی ۱۵۰px، کارت نتیجه ۹۶px) | `test_generate_page_scrolls_after_success` |
| پروفیل بار و پیش‌بینی جدا شوند؛ ورود «پیک سال‌های قبل» و پیش‌بینی سال‌های بعد؛ در حالت دستی دو بخش جدا | بخش ۱ «داده واقعی: پیک سال‌های گذشته» (با منبع MANUAL/PROFILE/EXCEL) ⟂ بخش ۲ «پیش‌بینی»؛ دکمهٔ رگرسیون فقط از دادهٔ واردشده محاسبه می‌کند؛ حالت دستی جدول بخش ۲ را ویرایش‌پذیر می‌کند | `tests/test_v111_forecast_split.py` (۷ تست) |

**عمداً انجام نشد (طبق پرامپت، نه فراموشی):**

- **هیچ آستانه‌ای پیش‌فرض گذاشته نشد**: نه تلورانس بارگیری، نه حد اتصال کوتاه، نه پارامتر هزینه —
  چون سند TAV111-10/00 عددی برای آن‌ها تعیین نکرده است. تا وقتی شما در «تنظیمات» تعریف نکنید،
  همان Ruleها `MISSING_RULE` می‌مانند (این خودِ خواستهٔ پرامپت است).
- **معیار انتخاب سناریو تعریف نشده**: موتور سناریوها را تولید می‌کند ولی توصیه/انتخاب نمی‌کند؛
  تا وقتی «معیار صریح انتخاب سناریو» (تب ۴) پر نشود، Rule `SC-NO-SELECTION-CRITERION` فعال است.
- **صفحهٔ «تحلیل مهندسی»** همان ۴ کارت قبلی را دارد؛ Findingهای مطالعه در همان کارت‌ها شمارش می‌شوند
  (جدول کامل Findings و فهرست بازبینی مهندس همهٔ آن‌ها را نشان می‌دهد).

## ۶. دستیابی به کار (بدون دسترسی نوشتن به GitHub از این محیط)

خروجی‌ها در Workspace آماده است؛ یکی را انتخاب کنید:

| فایل | کاربرد |
|---|---|
| `arena-changes-v1.1.2.patch` | `git am < arena-changes-v1.1.2.patch` (۴ کامیت) — روش اصلی |
| `arena-changes-v1.1.2.bundle` | `git fetch arena-changes-v1.1.2.bundle arena-changes:arena-changes` |
| `arena-changes-v1.1.2.zip` | ۵۴ فایل تغییر‌یافته + راهنما + `verify_package.py` + patch + bundle |
| `ReportForge-v1.1.2-full.zip` | کل پروژهٔ آمادهٔ اجرا + پروژهٔ نمونه + گزارش نمونه + تصاویر و شواهد |
