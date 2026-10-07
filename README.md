# ReportForge — گزارش‌یار مطالعات فنی شبکه توزیع

تولید خودکار گزارش مطالعات فنی اتصال مصارف سنگین (۱ مگاوات و بالاتر) به شبکه توزیع —

مطابق دستورالعمل **TAV111-10/00** شرکت توانیر و ساختار دفترچه‌های مطالعات شرکت توزیع نیروی برق استان اردبیل.

---

## 📋 نسخه-Jones**

| نسخه | تاریخ | دسته | توضیحات کلیدی |
|------|-------|------|----------------|
| **1.4.0** | ۱۴۰۳/۱۰/۱۲ | سکشنالایزر+ریکلوزر | تب مجزا «حفاظت‌های شبکه»، `SectionalizerInfo`، `RecloserInfo`، ۹۴ تست |
| **1.3.0** | ۱۴۰۳/۰۹ | چیدمان+انواع گزارش | چیدمان ۹بخشی مطابق مرجع ۱۴۰۵، انواع گزارش (Heavy/Sectionalizer/Recloser)، ۲۰ تست |
| **1.2.0** | ۱۴۰۳/۰۷ | اصلاحات فنی | جدول‌های Excel-گونه،obarگذاری بحرانی ۷/۸MW، کلید On/Off، بخش تصاویر، ۱۸۵ تست |
| **1.1.2** | ۱۴۰۳/۰۵ | رفع کرش exe | رفع مشکل `_SixMetaPathImporter` در Python 3.12.0-3.12.3، ۱۵۲ تست |
| **1.1.1** | ۱۴۰۳/۰۴ | اصلاحات UI | ارشد جدول‌ها، حذف/بازگرد ستون‌ها، فراخوان پیش‌بینی |
| **1.1.0** | ۱۴۰۳/۰۳ | Rule Engine+UI | ۵６ Rule تحلیلی + ۳ Rule سناریو، ۵ جدول ورود داده، ۱۳۸ تست |
| **1.0.3** | ۱۴۰۳/۰۱ | اولین نسخه | رابط کاربری حرفه‌ای، اعتبارسنجی، Word خروجی |
| **1.0.2** | ۱۴۰۲/۱۱ | اصلاحات | رفع ۹ ایراد خروجی + ۳ ایراد جزئی |
| **1.0.1** | ۱۴۰۲/۱۰ | اصلاحات | رفع ۱۲ ایراد، ۲۸ تست |

---

## 🚀 ویژگی‌های کلیدی نسخه ۱.۴.۰

### ۱. موتور قواعد مهندسی (Rule Engine) — مطالعه مصارف سنگین

- **۵۹ Rule** در ۸ حوزه تحلیل (طلب‌ها، ایستگاه‌ها، خطوط، متقاضیان همزمان، تأمین مشترک، سناریو، اقتصاد، کنترل ناسازگاری)
- **خروجی استاندارد**: هر Rule نتیجه با ساختار `rule_id / category / status / input_values / calculated_values / finding / evidence / source / source_page / recommended_text / engineer_review_required` تولید می‌کند
- **۵۶ Rule تحلیلی + ۳ Rule تولید سناریو** استخراج‌شده از دفترچه TAV111-10/00
- **محاسبه صریح Delta = After − Before** و تفکیک «افت ولتاژ مطلق» از «تغییر ناشی از متقاضی»
- **تولید سناریو بدون توصیه**: Scenario ۱ (فیدر جدید) و Scenario ۲ (فیدر موجود/جایگزین) با ثبت Technical Basis / Required Network Changes / Candidate Feeder / Estimated Cost / Required Equipment / Supporting Evidence / Review Status
- **بررسی اقتصادی پارامتریک**: پارامترهای هزینه در تنظیمات (خارج از کد)؛ نبود هزینه = `MISSING_DATA` (نه صفر)
- **کنترل ناسازگاری داده (DATA_INCONSISTENCY)**: مغایرت مجموع افزایش بار با کل بار گزارش‌شده و مغایرت تقاضای درخواستی با تقاضای مبنای تحلیل → `REQUIRES_ENGINEER_REVIEW` بدون حدس یا جایگزینی

### ۲. رابط کاربری حرفه‌ای (Engineering Desktop)

- **Sidebar N-Reftel**: پروژه / مطالعه مصارف سنگین / حفاظت‌های شبکه (سکشنالایزر / ریکلوزر)
- **نوار راهنما و ویرایش**: نوار ابروپ Toolbar + Property Inspector + StatusBar
- **د 여러**: QTabWidget با داشبورد + صفحات مطالعه + صفحات حفاظت
- **Theme روشن/تاریک** + آیکون‌های یکپارچه + پشتیبانی RTL (فارسی)
- **صفحه «مطالعه مصارف سنگین»**: ۵ جدول ورود داده (تقاضا / ایستگاه‌های نزدیک / خطوط نزدیک / متقاضیان همزمان / مسیر و هزینهٔ سناریوها)
- **تنظیمات**: «حدآستانه‌های مطالعه مصارف سنگین» + «پارامترهای هزینه بررسی اقتصادی»
- **جدول‌های Excel-گونه**: Delete/کپی/چسباندن/Enter، منوی راست‌کلیک، حذف/بازگرد ستون‌ها با نگاشت نام ستون

### ۳. انواع گزارش (Report Types) — v1.3.0+

| نوع | وضعیت | توضیح |
|-----|--------|--------|
| متقاضیان سنگین (Heavy) | ✅ کامل | ۹ بخش مطابق چیدمان مرجع ۱۴۰۵ |
| سکشنالایزر (Sectionalizer) | ✅اسکلت فعال | ۵ بخش: کliest، شبکه، تنظیمات، هماهنگی، نتیجه‌گیری |
| ریکلوزر (Recloser) | 📋 در برنامه | پیام واضح «در نسخه‌های بعدی» |

### ۴. outputs

- **Word فارسی RTL**: سربرگ، پاورقی «صفحه X از Y»، TOC (فیلد)، جداول راست‌به‌چپ، کپشن شکل/جدول، استایل Heading
- **پیش‌نمایش HTML**: همان ساختار بخش‌ها
- **۷ بخش مطالعه** در گزارش فقط وقتی داده مطالعه وجود داشته باشد؛ پروژه‌های بدون داده دقیقاً مثل v1.0.3 تولید می‌شوند
- **نتیجه‌گیری و پیشنهادات**: یک جدول با سرستون ادغام‌شده و سه ردیف (نکات تحلیلی / سناریوهای پیشنهادی / بررسی اقتصادی)

---

## 🏗️ معماری نرم‌افزار

### لایه مدل (Model Layer) — Phase 1

```
app/core/
├── models.py              مدل داده اصلی (Project، DemandInfo، Substation، Line، ...)
├── heavy_applicant.py     HeavyApplicantStudy — مستقل از Protection Studies
├── report_center.py       ReportCenter — مدیریت انتخاب مطالعات و ترکیب گزارش‌ها
├── report_types.py        ثبت انواع گزارش (Heavy/Sectionalizer/Recloser)
├── settings.py            تنظیمات (AppSettings، CostSettings، آستانه‌ها)
├── validation.py          اعتبارسنجی (واحد، محدوده، داده ناقص)
├── calculations.py        محاسبات (پیش‌بینی، پخش بار، تلفات، ولتاژ)
├── study.py               مطالعه مصارف سنگین (تحلیل‌ها، محاسبات)
├── scenarios.py           سناریوهای تأمین (تولید + بررسی)
├── forecast.py            پیش‌بینی (رگرسیون، کیفیت، تولید نانو)
└── profile.py             پروفیل بار (ورود، تحلیل، پیک‌ها)
```

**اهمیت معماری جداسازی:**
- `HeavyApplicantStudy` به‌طور کامل از `Project` جدا شده — احتمال مدیریت مستقل هر مطالعه
- `p.demand is p.heavy_applicant.demand` → `True` (مربع داده واحد)
- `ReportCenter` با قابلیت `combined=True/False` و `section_order` تنظیم‌پذیر
- `to_dict()`/`from_dict()` با سازگاری پشتیبان برای `project.json` قدیمی

### لایه قواعد (Rule Engine) — v1.1.0+

```
app/rules/
├── rule_engine.py         CategoricalRuleRunner، مدیریت_runnerها، найдone
├── outcome.py             ساخت نتیجه استاندارد، Trace Chain
├── data/study_rules/      ۹ فایل JSON قواعد (حوزه‌ها)
├── data/study.json        ۷۹ متن فارسی برای تنظیمات گزارش
└── __init__.py
```

**قابلیت‌های خاص:**
- هر Rule آستانه‌های موردنیازش را اعلام می‌کند → `MISSING_RULE` اگر آستانه نبود
- وضعیت‌های: `PASS/WARNING/FAIL/INFO/DATA_ERROR/REQUIRES_ENGINEER_REVIEW` (+ `MISSING_RULE/MISSING_DATA`)
- «اصل NEVER INVENT ENGINEERING DATA»: داده نبود = پیام شفاف، نه عدد ساختگی

### لایه گزارش (Report Generation)

```
app/report/
├── pipeline.py            오케ست 보인 کننده اصلی (build_sections، generate_docx)
├── composer.py            ReportComposer — ترکیب بخش‌ها بر اساس ReportCenter
├── study_sections.py      ۷ بخش مطالعه مصارف سنگین
├── sectionalizer.py       ۵ بخش گزارش سکشنالایزر
├── word_generator.py      تولید فایل DOCX با تمامی ویژگی‌های بالا
├── template_manager.py    مدیریت قالب‌ها و ترتیب بخش‌ها
└── data/texts/            کتابخانه متن‌های فارسی (قابل ویرایش)
```

### لایه رابط کاربری (UI)

```
app/ui/
├── main.py                نقطه ورود برنامه
├── engineering_desktop.py  EngineeringDesktop — QMainWindow اصلی
├── theme.py               مدیریت تم روشن/تاریک + QSS
├── study_page.py          صفحه مطالعه مصارف سنگین (۵ جدول)
├── protection_page.py     صفحه حفاظت‌های شبکه (سکشنالایزر/ریکلوزر)
├── excel_table.py         جدول‌های شبیه Excel با قابلیت‌های کامل
├── generate_page.py       صفحه تولید و بازبینی گزارش
├── images_page.py         مدیریت تصاویر پروژه
└── ...
```

---

## 📁 ساختار پروژه

```
Reporting-Software/
├── app/
│   ├── main.py              نقطه ورود
│   ├── __init__.py          نسخه + محافظ import
│   ├── core/                مدل داده، محاسبات، اعتبارسنجی، مطالعه، سناریو
│   ├── rules/               موتور قواعد + data/rules/*.json
│   ├── report/              متن، جدول، Word، Pipeline + data/texts/*.json
│   ├── excel/               قالب استاندارد Excel + Importer
│   ├── ui/                  صفحات PySide6 (فارسی RTL)
│   ├── utils/               کمک‌کننده‌ها (import_guard، selfcheck)
│   └── data/                تنظیمات پیش‌فرض، قالب‌ها
├── tests/
│   ├── test_core.py         ۱۴ تست (مدل، serialization، اعتبارسنجی)
│   ├── test_fixes.py        ۸ تست (رفع ایرادات v1.0.2)
│   ├── test_scenario_*.py   ۳ سناریوی الزامی (نیرورسانی/افزایش/ولتاژ)
│   ├── test_v103_*.py       تست‌های پیش‌بینی، Rules، Review، Word
│   ├── test_v110_study_engine.py  ۲۰ تست (موتور مطالعه)
│   ├── test_v111_*.py       UI مطالعه، تفکیک پیش‌بینی
│   ├── test_v112_exe_guard.py  ۱۴ تست (محافظ exe)
│   ├── test_v120_incremental.py  ۳۳ تست (اصلاحات v1.2.0 رابط)
│   ├── test_v130_*.py       ۱۱+۸ تست (چیدمان، سکشنالایزر)
│   ├── test_v131_protection_page.py  ۹ تست (صفحه حفاظت)
│   └── conftest.py          تنظیمات تست
├── docs/
│   ├── STUDY_RULE_SET_v1.1.0.md   مستند Rules
│   ├── REPORT_LAYOUT_v1.3.0.md    مستند چیدمان
│   ├── INCREMENTAL_FIXES_v1.2.0.md
│   └── EXE_BUILD_FIX_v1.1.2.md
├── screens/
│   └── ...                  تصاویر، نمودارهای نمونه
├── demo/
│   └── ...                  پروژه نمونه، Word نمونه
├── tools/
│   ├── build_demo.py        ساخت پروژه+nمونه+گزارش
│   ├── export_rule_set.py   خروجی مستند Rules
│   └── ui_check_study.py    آزمون خودکار رابط
├── requirements.txt         PySide6, python-docx, openpyxl, pandas, matplotlib, numpy, jdatetime, arabic-reshaper, python-bidi
├── pytest.ini
└── README.md                این فایل
```

---

## 🗄️ پوشه پروژه مطالعه

```
ProjectDir/
    project.json       مدل کامل پروژه (قابل بازگشتی با نسخه‌های قدیمی)
    profiles/          پروفیل بار فیدرها (CSV یا Excel)
    images/            تصاویر کاربر (JPG/PNG)
    charts/            نمودارهای تولیدی (PNG)
    output/            گزارش‌های Word (DOCX)
```

**قالب Excel استاندارد** (از صفحه اصلی → «قالب Excel ورودی»):

| شیت | محتوا |
|-----|-------|
| پروژه | اطلاعات پایه (نام متقاضی، نوع درخواست، توان‌ها، پست، امور، مانور، ...) |
| فیدرها | نام فیدر، پست، پیک MW، سال، ضریب توان، جریان‌ها، معیار بارگذاری |
| پخش بار | نتایج قبل/بعد هر فیدر (جریان، تلفات، ولتاژها) |
| پروفیل بار | Date / Feeder / P_MW / Q_MVAR |
| پیش‌بینی | پیش‌بینی دستی (اختیاری): فیدر، سال، پیک |

سپس صفحه اصلی → «تولید سریع از Excel».

---

## 🛠️ راهنمای استفاده

### اجرا

```bat
# ویندوز
run.bat

# مستقیم
set PYTHONIOENCODING=utf-8
python -m app.main
```

### ساخت فایل اجرایی (exe) — ویندوز

```bat
build_exe.bat
```

خروجی: `dist\ReportForge.exe` (onefile، بدون کنسول). پس از ساخت، خودآزمون به‌صورت خودکار اجرا می‌شود و گزارش `dist\ReportForge-smoke.txt` در کنسول نمایش داده می‌شود.

بررسی دستی سلامت exe:

```bat
dist\ReportForge.exe --smoke-test
type dist\ReportForge-smoke.txt
```

ساخت نسخهٔ اشکال‌زدایی (با کنسول، برای دیدن متن خطاها):

```bat
set REPORTFORGE_SPEC_CONSOLE=1
build_exe.bat
```

> **توصیه:** برای ساخت exe از Python 3.12.4+ یا 3.13 استفاده کنید. در 3.12.0–3.12.3 یک باگ در `importlib` وجود دارد که باید در سطح بسته‌بندی جبران شود؛ این جبران در `app/pyi_rth_reportforge.py` + `app/utils/import_guard.py` پیاده شده است.

### تست

```bash
python -m pytest tests/ -q
```

با خطای `libGL.so.1` (环境中没有 GUI) فقط تست‌های غیررابط اجرا می‌شوند:
- **۹۴ تست** در محیط لینوکس/offscreen (همه موفق)
- تست‌های رابط گرافیکی (PySide6) روی ویندوز کامل سبز هستند

سه سناریوی الزامی سند طراحی:
1. تأمین برق جدید ۱۵۰۰ کیلووات، ۱ فیدر
2. افزایش قدرت ۱۰۰۰→۱۱۰۰ کیلووات، ۲ فیدر + مانور
3. مشکل ولتاژ موجود (قبل خارج از محدوده، بعد بدون تغییر) → تشخیص «ناشی از افزایش قدرت نیست»

### کش(build_demo.py)

```bash
python tools/build_demo.py
```

→ پروژهٔ نمونه + Word نمونهٔ ۱.۴.۰ با بخش‌های مطابق چیدمان مرجع.

---

## ✅ وضعیت فعلی و تست‌ها

### شاخص پیشرفت

| شاخص | مقدار |
|-------|--------|
| فایل‌های تغییر یافته (Arena) | ۴۳ فایل |
| خطوط افزوده / حذف‌شده | +۷٬۷۷۸ / −۹۸ |
| کامیت‌ها روی برنچ | ۷ کامیت |
| نسخه | `1.0.3` → `1.4.0` |

### شمارش تست‌ها (نسخه ۱.۴.۰)

| گروه تست | تعداد | 토픽 |
|-----------|--------|------|
| core + fixes + scenarios | ۲7 | رگرسیون ۱.۰.۲ |
| forecast quality (v103) | ۱۰ | R²، Outlier، جهش، داده |
| engineering rules (v103) | ۷ | ولتاژ، تلفات، severity |
| review validation (v103) | ۲۱ | Accept/Edit/Reject/Override |
| word output (v103) | ۱۱ | DOCX، RTL، TOC، ساختار |
| study engine (v110) | ۲۰ | موتور مطالعه، چیدمان |
| protection page (v131) | ۹ | UI حفاظت‌های شبکه |
| report layout (v130) | ۱۱ | ۹ بخش مرجع |
| sectionalizer (v130) | ۸ | ۵ بخش سکشنالایزر |
| exe guard (v112) | چند | --smoke-test |
| **کل (غیررابط)** | **۹۴+** | todas motschim |

تست‌های رابط گرافیکی (PySide6) در محیط tanpa libGL اجرا نمی‌شوند اما روی ویندوز کامل سبز هستند.

### بررسی بصری

```bash
python tools/build_demo.py
```

→ Word نمونه با بخش‌های:
۱ مقدمه، ۲ تحلیل وضعیت بارگذاری، ۳ پیش‌بینی پیک بار، ۴ ایستگاه‌های نزدیک به محل تقاضا، ۵ خطوط نزدیک به محل تقاضا، ۶/۷ نتایج پخش بار، ۸ کنترل بارگذاری فیدر، ۹ نتیجه‌گیری و پیشنهادات، پیوست الف — دقیقاً مطابق گزارش مرجع ۱۴۰۵.

---

## 🔧 اصول طراحی

- **SIMPLE FOR ENGINEER — POWERFUL UNDER THE HOOD**: کاربر فقط اطلاعات اصلی را وارد می‌کند؛ متن، جداول، شکل‌ها، شماره‌گذاری و فهرست مطالب خودکار تولید می‌شود
- **هیچ Thresholdی Hard-Code نیست** — همه از تنظیمات/قواعد JSON
- **هیچ داده مهندسی‌ای ساخته نمی‌شود**؛ داده نبود = پیام شفاف (اصل NEVER INVENT ENGINEERING DATA)
- **نクス ۱ración**: نیازی به ویرایش دستی `project.json` نیست — همه از UI
- **ردیابی منبع**: هر داده را می‌توان از کجا آمده است (Excel / CSV / دستی / محاسبه / PowerFactory)
- **متن گزارش فقط از داده + قواعد تعریف‌شده تولید می‌شود** — بدون حدس یا جایگزینی
- **قالب‌بندی مطابق 글꼴‌ها و ساختار報告 مرجع** (دفترچه TAV111-10/00)
- **RTL و Persian 번호‌گذاری**: Word خروجی با شماره صفحه، TOC، کپشن فارسی

---

## 📝 مستندات تکمیلی

| فایل | محتوا |
|------|-------|
| `docs/STUDY_RULE_SET_v1.1.0.md` | مستند کامل ۵۹ Rule (بازتولید با `python tools/export_rule_set.py`) |
| `docs/REPORT_LAYOUT_v1.3.0.md` | مستند چیدمان ۹بخشی مرجع |
| `docs/INCREMENTAL_FIXES_v1.2.0.md` | جزئیات اصلاحات v1.2.0 |
| `docs/EXE_BUILD_FIX_v1.1.2.md` | جزئیات رفع کرش exe |

---

## 📄 مستندات پیش‌فرض

- **نرم‌افزار**: ReportForge v1.4.0
- **پلتفرم**: ویندوز (PySide6 + python-docx)
- **نیازمندی‌ها**: Python 3.12+ و پکیج‌های `requirements.txt`
- **پشتیبانی**: فایل‌های Excel/CSV، خروجی Word فارسی RTL، گزارش پیش‌نمایش HTML
- **لایسنس**: proprietery — شرکت توزیع نیروی برق استان اردبیل / طراحی آرنا

---

*ReportForge — گزارش‌یار مطالعات فنی شبکه توزیع*  
*نسخه ۱.۴.۰ — به‌روز در ۱۴۰۳/۱۰/۱۲*
