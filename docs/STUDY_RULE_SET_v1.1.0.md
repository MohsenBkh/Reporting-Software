# مجموعه Ruleهای مطالعه مصارف سنگین — نسخه ۱.۱.۰ («تغییرات آرنا»)

این مستند به‌صورت خودکار از فایل‌های Rule و موتور قواعد تولید می‌شود (`python tools/export_rule_set.py`).

**سند مرجع:** TAV111-10/00 — «دستورالعمل مطالعات فنی اتصال مصارف سنگین به شبکه توزیع» (فایل پیوست، صفحات ۱۰ تا ۱۲ از ۱۵: جدول اطلاعات تقاضا، جدول ایستگاه‌های نزدیک، جدول خطوط نزدیک، نتیجه‌گیری و پیشنهادات).

**اصل حاکم:** هیچ معیار، حد مجاز یا نتیجه‌ای خارج از محتوای سند و داده ورودی ساخته نمی‌شود. اگر برای تصمیم‌گیری آستانه لازم باشد و در سند/پیکربندی نباشد، وضعیت `MISSING_RULE` ثبت می‌گردد؛ اگر داده لازم نباشد، `MISSING_DATA`.

## ۱. خروجی استاندارد هر Rule

```json
{
  "rule_id": "...",
  "category": "...",
  "status": "PASS | WARNING | FAIL | INFO | DATA_ERROR | REQUIRES_ENGINEER_REVIEW | MISSING_RULE | MISSING_DATA",
  "input_values": {},
  "calculated_values": {},
  "finding": "...",
  "evidence": "...",
  "source": "TAV111-10/00",
  "source_page": "...",
  "recommended_text": "...",
  "engineer_review_required": true,
  "meta": {
    "rule_key": "...",
    "rule_name": "...",
    "owner": "...",
    "thresholds": {},
    "missing": [],
    "severity": "..."
  }
}
```

زنجیره ردیابی هر نتیجه: **Input → Calculation → Rule → Finding → Evidence → Report Text** (متد `RuleResult.trace_lines()`).

## ۲. نگاشت وضعیت‌ها

| وضعیت | معنی | شدت در نرم‌افزار | متن گزارش |
|---|---|---|---|
| `PASS` | منطبق | normal | تولید می‌شود |
| `WARNING` | هشدار | warning | تولید می‌شود |
| `FAIL` | عدم انطباق | error | تولید می‌شود |
| `INFO` | اطلاع‌رسانی | normal | تولید می‌شود |
| `DATA_ERROR` | خطای داده | review | تولید نمی‌شود |
| `REQUIRES_ENGINEER_REVIEW` | نیازمند بررسی مهندس | review | تولید می‌شود |
| `MISSING_RULE` | قاعده/آستانه تعریف‌نشده | review | تولید نمی‌شود |
| `MISSING_DATA` | داده ناموجود | review | تولید می‌شود (در نبود داده با برچسب MISSING_DATA) |

## ۳. فهرست Ruleهای استخراج‌شده

### A) اطلاعات تقاضا

| شناسه گزارش‌شده (Rule ID) | شناسه داخلی | نام | وضعیت | داده‌های الزامی | آستانه‌ها | صفحه مرجع |
|---|---|---|---|---|---|---|
| `D-DEMAND-COMPLETE` | `D-DEMAND-COMPLETE` | کنترل کامل بودن اطلاعات تقاضا | `PASS` | `demand_without_coincidence_kw`، `demand_with_coincidence_kw` | — | صفحه ۱۰ از ۱۵ — جدول اطلاعات تقاضا |
| `D-COINCIDENCE-OVER-ONE` | `D-COINCIDENCE-OVER-ONE` | ضریب همزمانی بزرگ‌تر از یک — ناسازگاری داده | `DATA_ERROR` | `demand_without_coincidence_kw`، `demand_with_coincidence_kw` | — | صفحه ۱۰ از ۱۵ — جدول اطلاعات تقاضا |
| `D-COINCIDENCE-NOT-APPLIED` | `D-COINCIDENCE-NOT-APPLIED` | ضریب همزمانی اعمال‌نشده (تقاضا با و بدون ضریب برابر) | `REQUIRES_ENGINEER_REVIEW` | `demand_without_coincidence_kw`، `demand_with_coincidence_kw` | — | صفحه ۱۰ از ۱۵ — جدول اطلاعات تقاضا |
| `D-DEMAND-FALLBACK` | `D-DEMAND-FALLBACK` | نبود ضریب همزمانی — تحلیل بر مبنای تقاضای بدون ضریب | `MISSING_DATA` | `demand_without_coincidence_kw` | — | صفحه ۱۰ از ۱۵ — جدول اطلاعات تقاضا |
| `D-DELTA-POWER` | `D-DELTA-POWER` | محاسبه افزایش قدرت (تفاضل توان جدید و موجود) | `INFO` | `requested_power_kw`، `existing_demand_kw` | — | صفحه ۱۰ از ۱۵ — جدول اطلاعات تقاضا |
| `D-DEMAND-HEAVY-LIMIT` | `D-DEMAND-HEAVY-LIMIT` | کنترل موضوع دستورالعمل مصارف سنگین (۱ مگاوات و بالاتر) | `WARNING` | `demand_for_analysis_kw` | `heavy_consumer_min_kw` (سند مرجع) | صفحه ۱۰ از ۱۵ — جدول اطلاعات تقاضا |
| `D-DEMAND-HEAVY-NO-THRESHOLD` | `D-DEMAND-HEAVY-NO-THRESHOLD` | دامنه شمول دستورالعمل — حد مصرف سنگین تعریف‌نشده | `MISSING_RULE` | `demand_for_analysis_kw` | `heavy_consumer_min_kw` (سند مرجع) | صفحه ۱۰ از ۱۵ — جدول اطلاعات تقاضا |

### B) ایستگاه‌های نزدیک به محل تقاضا

| شناسه گزارش‌شده (Rule ID) | شناسه داخلی | نام | وضعیت | داده‌های الزامی | آستانه‌ها | صفحه مرجع |
|---|---|---|---|---|---|---|
| `SS-LOADING-MISMATCH` | `SS-LOADING-MISMATCH` | ناسازگاری درصد بارگیری ترانس با پیک/ظرفیت ثبت‌شده | `REQUIRES_ENGINEER_REVIEW` | `ss_t1_loading_pct`، `ss_t1_peak_mva`، `ss_transformer_capacity_mva` | `substation_loading_tolerance_pct` (پیکربندی) | صفحه ۱۰ از ۱۵ — جدول ایستگاه‌های نزدیک به محل تقاضا |
| `SS-DATA-INCOMPLETE` | `SS-DATA-INCOMPLETE` | داده ایستگاه ناقص | `MISSING_DATA` | — | — | صفحه ۱۰ از ۱۵ — جدول ایستگاه‌های نزدیک به محل تقاضا |
| `SS-LOADING-CHECK-NO-THRESHOLD` | `SS-LOADING-CHECK-NO-THRESHOLD` | کنترل سازگاری درصد بارگیری با پیک و ظرفیت — آستانه تلورانس تعریف‌نشده | `MISSING_RULE` | `ss_t1_loading_pct`، `ss_t1_peak_mva`، `ss_transformer_capacity_mva` | `substation_loading_tolerance_pct` (پیکربندی) | صفحه ۱۰ از ۱۵ — جدول ایستگاه‌های نزدیک به محل تقاضا |
| `SS-DESCRIBE` | `SS-DESCRIBE` | شرح وضعیت ایستگاه نزدیک | `INFO` | `ss_name`، `ss_distance_km` | — | صفحه ۱۰ از ۱۵ — جدول ایستگاه‌های نزدیک به محل تقاضا |
| `SS-LOADING-LEVEL` | `SS-LOADING-LEVEL` | سطح بارگیری ایستگاه نزدیک | `WARNING` | `ss_max_loading_pct` | `study_substation_loading_warn_pct` (پیکربندی) | صفحه ۱۰ از ۱۵ — جدول ایستگاه‌های نزدیک به محل تقاضا |
| `SS-LOADING-LEVEL-NO-THRESHOLD` | `SS-LOADING-LEVEL-NO-THRESHOLD` | سطح بارگیری ایستگاه نزدیک — حد هشدار تعریف‌نشده | `MISSING_RULE` | `ss_max_loading_pct` | `study_substation_loading_warn_pct` (پیکربندی) | صفحه ۱۰ از ۱۵ — جدول ایستگاه‌های نزدیک به محل تقاضا |
| `SS-NO-DATA` | `SS-NO-DATA` | نبود داده ایستگاه‌های نزدیک | `MISSING_DATA` | — | — | صفحه ۱۰ از ۱۵ — جدول ایستگاه‌های نزدیک به محل تقاضا |

### C) خطوط نزدیک به محل تقاضا

| شناسه گزارش‌شده (Rule ID) | شناسه داخلی | نام | وضعیت | داده‌های الزامی | آستانه‌ها | صفحه مرجع |
|---|---|---|---|---|---|---|
| `LN-VDROP-ORDER-ERROR` | `LN-VDROP-ORDER-ERROR` | ترتیب نامعتبر افت ولتاژ قبل/بعد — خطای داده | `DATA_ERROR` | `line_v_before_pct`، `line_v_after_pct` | — | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-CURRENT-MISMATCH` | `LN-CURRENT-MISMATCH` | ناسازگاری پیک جریان با پیک بار خط | `REQUIRES_ENGINEER_REVIEW` | `line_peak_current_a`، `line_peak_mva` | `line_current_tolerance_pct` (پیکربندی) | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-DELTA-EXCEEDS-LIMIT` | `LN-DELTA-EXCEEDS-LIMIT` | حد تغییر مجاز ولتاژ پس از اتصال بار جدید | `WARNING` | `line_delta_v_pp` | `voltage_change_max_pct` (سند مرجع) | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-SC-INCONSISTENT` | `LN-SC-INCONSISTENT` | ناسازگاری جریان اتصال کوتاه (حداقل بیش از حداکثر) | `DATA_ERROR` | `line_sc_min_ka`، `line_sc_max_ka` | — | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-DELTA-LIMIT-NO-THRESHOLD` | `LN-DELTA-LIMIT-NO-THRESHOLD` | حد تغییر مجاز ولتاژ تعریف‌نشده | `MISSING_RULE` | `line_delta_v_pp` | `voltage_change_max_pct` (سند مرجع) | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-SC-OVER` | `LN-SC-OVER` | جریان اتصال کوتاه بیش از حد مجاز تجهیزات | `WARNING` | `line_sc_max_ka` | `study_sc_limit_ka` (پیکربندی) | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-CURRENT-OVER` | `LN-CURRENT-OVER` | جریان پیک خط بیش از ظرفیت هدایتی | `WARNING` | `line_peak_current_a`، `line_max_current_a` | — | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-DELTA-CALC` | `LN-DELTA-CALC` | محاسبه صریح تغییر قبل/بعد (Delta = After − Before) | `INFO` | `line_v_before_pct`، `line_v_after_pct` | — | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-PEAK-DESCRIBE` | `LN-PEAK-DESCRIBE` | شرح پیک بار خط نزدیک | `INFO` | `line_name`، `line_peak_mva` | — | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-ABSOLUTE-VS-DELTA` | `LN-ABSOLUTE-VS-DELTA` | تفکیک افت ولتاژ مطلق از تغییر ناشی از متقاضی | `INFO` | `line_v_before_pct`، `line_v_after_pct` | — | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-PREEXISTING-DROP` | `LN-PREEXISTING-DROP` | افت ولتاژ موجود، بزرگ‌تر از سهم متقاضی | `INFO` | `line_v_before_pct`، `line_delta_v_pp` | — | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-DATA-INCOMPLETE` | `LN-DATA-INCOMPLETE` | داده قبل/بعد خط ناقص | `MISSING_DATA` | — | — | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-CURRENT-CHECK-NO-THRESHOLD` | `LN-CURRENT-CHECK-NO-THRESHOLD` | کنترل سازگاری پیک جریان با مگاولت‌آمپر — تلورانس تعریف‌نشده | `MISSING_RULE` | `line_peak_current_a`، `line_peak_mva` | `line_current_tolerance_pct` (پیکربندی) | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-SC-LIMIT-MISSING` | `LN-SC-LIMIT-MISSING` | نبود حد مجاز اتصال کوتاه تجهیزات | `MISSING_RULE` | `line_sc_max_ka` | `study_sc_limit_ka` (پیکربندی) | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-CURRENT-LIMIT-MISSING` | `LN-CURRENT-LIMIT-MISSING` | نبود ظرفیت هدایتی خط — مقایسه جریان ممکن نیست | `MISSING_DATA` | `line_peak_current_a` | — | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-CURRENT-OK` | `LN-CURRENT-OK` | جریان پیک خط در محدوده ظرفیت هدایتی | `PASS` | `line_peak_current_a`، `line_max_current_a` | — | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-NO-DATA` | `LN-NO-DATA` | نبود داده خطوط نزدیک | `MISSING_DATA` | — | — | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |

### D) تقاضاهای همزمان و سایر متقاضیان

| شناسه گزارش‌شده (Rule ID) | شناسه داخلی | نام | وضعیت | داده‌های الزامی | آستانه‌ها | صفحه مرجع |
|---|---|---|---|---|---|---|
| `CD-DATA-INCOMPLETE` | `CD-DATA-INCOMPLETE` | داده ناقص متقاضیان همزمان | `MISSING_DATA` | — | — | صفحه ۱۲ از ۱۵ — نکات تحلیلی نتیجه‌گیری |
| `CD-LIST` | `CD-LIST` | فهرست متقاضیان/تقاضاهای همزمان و مجموع افزایش بار | `INFO` | `cd_count`، `cd_sum_delta_kw` | — | صفحه ۱۲ از ۱۵ — نکات تحلیلی نتیجه‌گیری |
| `CD-TOTAL-LOAD` | `CD-TOTAL-LOAD` | مجموع بار اضافه‌شده محدوده (متقاضی + سایر متقاضیان) | `INFO` | `cd_total_new_load_kw`، `demand_for_analysis_kw` | — | صفحه ۱۲ از ۱۵ — نکات تحلیلی نتیجه‌گیری |
| `CD-NONE` | `CD-NONE` | بدون متقاضی همزمان ثبت‌شده | `INFO` | — | — | صفحه ۱۲ از ۱۵ — نکات تحلیلی نتیجه‌گیری |

### D-۲) تأمین مشترک چند نقطه تقاضا (توپولوژی)

| شناسه گزارش‌شده (Rule ID) | شناسه داخلی | نام | وضعیت | داده‌های الزامی | آستانه‌ها | صفحه مرجع |
|---|---|---|---|---|---|---|
| `TP-SHARED-SUPPLY-REVIEW` | `TP-SHARED-SUPPLY-REVIEW` | نیاز به بررسی توپولوژیکی تأمین مشترک | `REQUIRES_ENGINEER_REVIEW` | `n_demand_points` | — | صفحه ۱۲ از ۱۵ — نکات تحلیلی نتیجه‌گیری |
| `TP-SHARED-SUPPLY-NO-EVIDENCE` | `TP-SHARED-SUPPLY-NO-EVIDENCE` | نتیجه توپولوژیکی بدون شاهد مسیر/آرایش شبکه | `DATA_ERROR` | — | — | صفحه ۱۲ از ۱۵ — نکات تحلیلی نتیجه‌گیری |
| `TP-SHARED-SUPPLY-EVIDENCED` | `TP-SHARED-SUPPLY-EVIDENCED` | تأمین مشترک با مبنای توپولوژیکی ثبت‌شده | `INFO` | `joint_supply_feasibility` | — | صفحه ۱۲ از ۱۵ — نکات تحلیلی نتیجه‌گیری |
| `TP-SINGLE-POINT` | `TP-SINGLE-POINT` | تک‌نقطه‌ای بودن تقاضا | `INFO` | `n_demand_points` | — | صفحه ۱۲ از ۱۵ — نکات تحلیلی نتیجه‌گیری |

### E) سناریوهای تأمین

| شناسه گزارش‌شده (Rule ID) | شناسه داخلی | نام | وضعیت | داده‌های الزامی | آستانه‌ها | صفحه مرجع |
|---|---|---|---|---|---|---|
| `SC-NO-SELECTION-CRITERION` | `SC-NO-SELECTION-CRITERION` | نبود معیار صریح انتخاب سناریو | `REQUIRES_ENGINEER_REVIEW` | `scenario_count` | — | صفحه ۱۲ از ۱۵ — سناریوهای پیشنهادی |
| `SC-INFO-INCOMPLETE` | `SC-INFO-INCOMPLETE` | نقص اطلاعات شناسنامه سناریو | `MISSING_DATA` | — | — | صفحه ۱۲ از ۱۵ — سناریوهای پیشنهادی |
| `SC-GENERATED` | `SC-GENERATED` | سناریوهای تولیدشده و لزوم انتخاب توسط مهندس | `INFO` | `scenario_count` | — | صفحه ۱۲ از ۱۵ — سناریوهای پیشنهادی |
| `SC-NONE` | `SC-NONE` | سناریویی تولید نشده است | `MISSING_DATA` | — | — | صفحه ۱۲ از ۱۵ — سناریوهای پیشنهادی |

### E-۲) بررسی اقتصادی سناریوها

| شناسه گزارش‌شده (Rule ID) | شناسه داخلی | نام | وضعیت | داده‌های الزامی | آستانه‌ها | صفحه مرجع |
|---|---|---|---|---|---|---|
| `EC-COST-ZERO-NO-BASIS` | `EC-COST-ZERO-NO-BASIS` | هزینه صفر بدون مبنای هزینه — باید MISSING_DATA ثبت شود | `DATA_ERROR` | — | — | صفحه ۱۲ از ۱۵ — بررسی اقتصادی سناریوها |
| `EC-ROUTE-LENGTH-VS-DISTANCE` | `EC-ROUTE-LENGTH-VS-DISTANCE` | طول شبکه سناریو کمتر از فاصله نزدیک‌ترین منبع — نیازمند بررسی | `REQUIRES_ENGINEER_REVIEW` | `scenario_length_km`، `min_substation_distance_km` | — | صفحه ۱۲ از ۱۵ — بررسی اقتصادی سناریوها |
| `EC-PARAMETRIC-NO-PARAMS` | `EC-PARAMETRIC-NO-PARAMS` | برآورد پارامتریک هزینه — پارامترهای هزینه تعریف‌نشده | `MISSING_RULE` | — | `cost_overhead_per_km_million` (پیکربندی)، `cost_underground_per_km_million` (پیکربندی)، `cost_ground_substation_million` (پیکربندی) | صفحه ۱۲ از ۱۵ — بررسی اقتصادی سناریوها |
| `EC-COST-VALUE` | `EC-COST-VALUE` | هزینه ثبت‌شده سناریو | `INFO` | `scenario_cost_million` | — | صفحه ۱۲ از ۱۵ — بررسی اقتصادی سناریوها |
| `EC-PARAMETRIC-ESTIMATE` | `EC-PARAMETRIC-ESTIMATE` | برآورد پارامتریک هزینه سناریو | `INFO` | `scenario_length_km` | `cost_overhead_per_km_million` (پیکربندی)، `cost_underground_per_km_million` (پیکربندی) | صفحه ۱۲ از ۱۵ — بررسی اقتصادی سناریوها |
| `EC-EXCLUDED-ITEMS` | `EC-EXCLUDED-ITEMS` | اقلام خارج از برآورد هزینه | `MISSING_DATA` | — | — | صفحه ۱۲ از ۱۵ — بررسی اقتصادی سناریوها |
| `EC-COST-MISSING` | `EC-COST-MISSING` | نبود داده هزینه سناریو | `MISSING_DATA` | — | — | صفحه ۱۲ از ۱۵ — بررسی اقتصادی سناریوها |

### کنترل ناسازگاری داده‌ها (Cross Validation)

| شناسه گزارش‌شده (Rule ID) | شناسه داخلی | نام | وضعیت | داده‌های الزامی | آستانه‌ها | صفحه مرجع |
|---|---|---|---|---|---|---|
| `DATA_INCONSISTENCY` | `XC-LOAD-SUM-MISMATCH` | مغایرت مجموع افزایش بار با کل بار اضافه‌شده گزارش‌شده | `REQUIRES_ENGINEER_REVIEW` | `sum_new_demand_changes_kw`، `reported_total_additional_load_kw` | — | صفحه ۱۲ از ۱۵ — کنترل ناسازگاری داده‌ها |
| `DATA_INCONSISTENCY` | `XC-DEMAND-BASE-MISMATCH` | مغایرت تقاضای درخواستی با تقاضای مبنای تحلیل | `REQUIRES_ENGINEER_REVIEW` | `requested_power_kw`، `demand_used_in_analysis_kw` | — | صفحه ۱۲ از ۱۵ — کنترل ناسازگاری داده‌ها |
| `XC-LOAD-SUM-OK` | `XC-LOAD-SUM-OK` | سازگاری مجموع افزایش بار متقاضیان با کل بار اضافه‌شده | `PASS` | `sum_new_demand_changes_kw`، `reported_total_additional_load_kw` | — | صفحه ۱۲ از ۱۵ — کنترل ناسازگاری داده‌ها |
| `XC-DEMAND-BASE-OK` | `XC-DEMAND-BASE-OK` | سازگاری تقاضای درخواستی با تقاضای مبنای تحلیل | `PASS` | `requested_power_kw`، `demand_used_in_analysis_kw` | — | صفحه ۱۲ از ۱۵ — کنترل ناسازگاری داده‌ها |
| `XC-NO-BASELINE-SUM` | `XC-NO-BASELINE-SUM` | نبود مقدار گزارش‌شده برای کنترل مجموع بار | `MISSING_DATA` | — | — | صفحه ۱۲ از ۱۵ — کنترل ناسازگاری داده‌ها |
| `XC-NO-BASELINE-DEMAND` | `XC-NO-BASELINE-DEMAND` | نبود تقاضای مبنای تحلیل | `MISSING_DATA` | — | — | صفحه ۱۲ از ۱۵ — کنترل ناسازگاری داده‌ها |

### Ruleهای تولید سناریو (kind = scenario)

| شناسه | نام | نوع سناریو | شرط تولید | وضعیت بازبینی | صفحه مرجع |
|---|---|---|---|---|---|
| `SC-GEN-NEW-FEEDER` | سناریو ۱ — احداث فیدر جدید | `new_feeder` | `has_demand_for_analysis` | `REQUIRES_ENGINEER_REVIEW` | صفحه ۱۲ از ۱۵ — سناریوهای پیشنهادی |
| `SC-GEN-EXISTING-FEEDER` | سناریو ۲ — تأمین از فیدر موجود | `existing_feeder` | `has_nearby_lines` | `REQUIRES_ENGINEER_REVIEW` | صفحه ۱۲ از ۱۵ — سناریوهای پیشنهادی |
| `SC-GEN-ALTERNATIVE-FEEDER` | سناریو ۳ — تأمین از فیدر جایگزین | `alternative_feeder` | `line_candidates_ge_2` | `REQUIRES_ENGINEER_REVIEW` | صفحه ۱۲ از ۱۵ — سناریوهای پیشنهادی |

**جمع:** 56 Rule تحلیلی + 3 Rule تولید سناریو.

## ۴. Ruleهای فاقد Threshold (نیازمند تعیین آستانه توسط مهندس)

فهرست زیر همه وابستگی‌های آستانه‌ای Ruleهای تحلیلی را نشان می‌دهد. ردیف‌هایی که «مقدار پیش‌فرض فعلی» آن‌ها `None` است، در وضعیت جاری به `MISSING_RULE` منجر می‌شوند: هیچ مقدار جایگزینی فرض نمی‌شود و متن گزارش تولید نمی‌گردد تا مهندس آستانه را تعیین کند. ردیف‌هایی که مبنای «سند مرجع» دارند، از متن دستورالعمل گرفته شده‌اند (مانند دامنه شمول ۱ مگاوات و سقف تغییر ولتاژ).

| شناسه داخلی | آستانه لازم | مبنای اعلام‌شده | مقدار پیش‌فرض فعلی | صفحه مرجع |
|---|---|---|---|---|
| `LN-CURRENT-MISMATCH` | `line_current_tolerance_pct` — تلورانس کنترل سازگاری جریان با بار خط | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-DELTA-EXCEEDS-LIMIT` | `voltage_change_max_pct` — حد مجاز تغییر ولتاژ پس از اتصال بار | سند مرجع | `5.0` | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-DELTA-LIMIT-NO-THRESHOLD` | `voltage_change_max_pct` — حد مجاز تغییر ولتاژ پس از اتصال بار | سند مرجع | `5.0` | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `LN-SC-OVER` | `study_sc_limit_ka` — حد مجاز جریان اتصال کوتاه تجهیزات شبکه | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `EC-PARAMETRIC-NO-PARAMS` | `cost_overhead_per_km_million` — هزینه احداث شبکه هوایی (میلیون تومان بر کیلومتر) | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۲ از ۱۵ — بررسی اقتصادی سناریوها |
| `EC-PARAMETRIC-NO-PARAMS` | `cost_underground_per_km_million` — هزینه احداث شبکه زمینی (میلیون تومان بر کیلومتر) | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۲ از ۱۵ — بررسی اقتصادی سناریوها |
| `EC-PARAMETRIC-NO-PARAMS` | `cost_ground_substation_million` — هزینه احداث پست زمینی (میلیون تومان) | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۲ از ۱۵ — بررسی اقتصادی سناریوها |
| `SS-LOADING-MISMATCH` | `substation_loading_tolerance_pct` — تلورانس کنترل سازگاری درصد بارگیری ایستگاه | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۰ از ۱۵ — جدول ایستگاه‌های نزدیک به محل تقاضا |
| `SS-LOADING-CHECK-NO-THRESHOLD` | `substation_loading_tolerance_pct` — تلورانس کنترل سازگاری درصد بارگیری ایستگاه | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۰ از ۱۵ — جدول ایستگاه‌های نزدیک به محل تقاضا |
| `EC-PARAMETRIC-ESTIMATE` | `cost_overhead_per_km_million` — هزینه احداث شبکه هوایی (میلیون تومان بر کیلومتر) | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۲ از ۱۵ — بررسی اقتصادی سناریوها |
| `EC-PARAMETRIC-ESTIMATE` | `cost_underground_per_km_million` — هزینه احداث شبکه زمینی (میلیون تومان بر کیلومتر) | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۲ از ۱۵ — بررسی اقتصادی سناریوها |
| `SS-LOADING-LEVEL` | `study_substation_loading_warn_pct` — حد هشدار بارگیری ترانس‌های ایستگاه نزدیک | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۰ از ۱۵ — جدول ایستگاه‌های نزدیک به محل تقاضا |
| `SS-LOADING-LEVEL-NO-THRESHOLD` | `study_substation_loading_warn_pct` — حد هشدار بارگیری ترانس‌های ایستگاه نزدیک | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۰ از ۱۵ — جدول ایستگاه‌های نزدیک به محل تقاضا |
| `D-DEMAND-HEAVY-LIMIT` | `heavy_consumer_min_kw` — حد پایین مصرف سنگین | سند مرجع | `1000.0` | صفحه ۱۰ از ۱۵ — جدول اطلاعات تقاضا |
| `LN-CURRENT-CHECK-NO-THRESHOLD` | `line_current_tolerance_pct` — تلورانس کنترل سازگاری جریان با بار خط | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |
| `D-DEMAND-HEAVY-NO-THRESHOLD` | `heavy_consumer_min_kw` — حد پایین مصرف سنگین (دامنه شمول دستورالعمل) | سند مرجع | `1000.0` | صفحه ۱۰ از ۱۵ — جدول اطلاعات تقاضا |
| `LN-SC-LIMIT-MISSING` | `study_sc_limit_ka` — حد مجاز جریان اتصال کوتاه تجهیزات شبکه | پیکربندی (قابل ویرایش) | تعریف‌نشده (None) | صفحه ۱۱ از ۱۵ — جدول خطوط نزدیک به محل تقاضا |

**آستانه‌های تعریف‌شده در پیکربندی (مقدار پیش‌فرض):**

- `heavy_consumer_min_kw` = `1000.0`
- `voltage_change_max_pct` = `5.0`
- `voltage_min_pu` = `0.95`
- `voltage_max_pu` = `1.05`
- `loading_light_pct` = `25.0`
- `loading_normal_pct` = `70.0`
- `loading_semi_pct` = `85.0`
- `loading_heavy_pct` = `100.0`

**پارامترهای هزینه (پیش‌فرض خالی — تا تعیین‌نشدن، برآورد هزینه ساخته نمی‌شود):**

- `cost_overhead_per_km_million` = `None`
- `cost_underground_per_km_million` = `None`
- `cost_ground_substation_million` = `None`
- `cost_switchgear_million` = `None`
- `cost_protection_million` = `None`
- `cost_other_equipment_million` = `None`

## ۵. ناسازگاری‌ها و نکات داده‌ای نمونه مرجع

تحلیل زیر بر پایه چهار صفحه پیوست (صفحات ۱۰ تا ۱۲ از ۱۵) و با اجرای همین Rule Set روی داده‌های همان صفحات تهیه شده است:

| مورد | Rule مرتبط | توضیح |
|---|---|---|
| ناسازگاری درصد بارگیری ترانس T1 ایستگاه «شهرک صنعتی» | `SS-LOADING-MISMATCH / SS-LOADING-CHECK-NO-THRESHOLD` | درصد بارگیری ثبت‌شده T1 = ۶۱.۰۵٪ در حالی که نسبت پیک به ظرفیت (۲۷.۶۲ از ۴۰ MVA) مقدار ۶۹.۰۵٪ می‌دهد؛ اختلاف ۸ واحد درصد. موتور این اختلاف را محاسبه و در calculated_values قرار می‌دهد، اما تا تعیین تلورانس کنترل (`substation_loading_tolerance_pct`) هیچ‌کدام از دو مقدار را صحیح فرض نمی‌کند (وضعیت MISSING_RULE). |
| هزینه صفر سناریو ۲ بدون مبنای هزینه | `EC-COST-ZERO-NO-BASIS (DATA_ERROR)` | در جدول بررسی اقتصادی، «هزینه سناریو ۲: ۰» ثبت شده در حالی که هیچ قلم هزینه (طول شبکه، درصد هوایی/زمینی، تجهیزات) برای آن وجود ندارد. مطابق Rule Set، نبود داده هزینه باید MISSING_DATA ثبت شود؛ صفر فقط با مبنای مستند معتبر است. |
| عدم ذکر اقلام خارج از برآورد سناریو ۱ | `EC-EXCLUDED-ITEMS (MISSING_DATA)` | متن مرجع صریحاً «هزینه کلید ایستگاه» و «احداث پست زمینی» و «هزینه تأمین» را از برآورد ۵۱۳۰ میلیون تومان مستثنی کرده است. این اقلام به‌صورت MISSING_DATA ثبت می‌شوند (نه صفر) و در جدول بررسی اقتصادی نمایش داده می‌شوند. |
| طول مسیر سناریو ۱ (۲ کیلومتر) در برابر فاصله نزدیک‌ترین ایستگاه (۴ کیلومتر) | `EC-ROUTE-LENGTH-VS-DISTANCE (REQUIRES_ENGINEER_REVIEW)` | طول شبکه موردنیاز سناریو ۱ برابر ۲ کیلومتر است، در حالی که نزدیک‌ترین ایستگاه جدول «ایستگاه‌های نزدیک» ۴ کیلومتر فاصله دارد. موتور نتیجه نمی‌گیرد که داده غلط است؛ بلکه منبع تغذیه و مسیر سناریو را «نیازمند مستندسازی» علامت می‌زند. |
| نتیجه‌گیری «عدم امکان تأمین یکجا بر پایه پراکندگی مکانی» | `TP-SHARED-SUPPLY-REVIEW (REQUIRES_ENGINEER_REVIEW)` | سند مرجع نتیجه می‌گیرد که چون ۴ تقاضا در نقاط پراکنده قرار دارند، تأمین یکجای آن‌ها ممکن نیست. این نتیجه از روی فاصله مکانی گرفته شده و شاهد توپولوژیکی (مسیر فیدر، آرایش شبکه، ظرفیت انتقال) ندارد؛ Rule Engine این مورد را فاقد شاهد لازم می‌داند و بررسی توپولوژیکی را درخواست می‌کند. |
| نبود ظرفیت هدایتی خطوط و حد مجاز اتصال کوتاه | `LN-CURRENT-LIMIT-MISSING (MISSING_DATA) / LN-SC-LIMIT-MISSING (MISSING_RULE)` | جدول «خطوط نزدیک» فقط پیک بار و جریان اتصال کوتاه را می‌دهد و ظرفیت هدایتی/حد مجاز اتصال کوتاه را ارائه نمی‌کند؛ بنابراین مقایسه جریان با ظرفیت و داوری درباره تحمل تجهیزات انجام نمی‌شود و مقادیر صرفاً ثبت می‌گردند. |
| مجموع افزایش بار متقاضیان = ۳۰۰۰ kW (سازگار) | `XC-LOAD-SUM-OK (PASS)` | مجموع افزایش بار سه متقاضی همزمان (۵۰۰ + ۱۱۰۰ + ۲۰۰ = ۱۸۰۰ kW) به‌همراه افزایش بار متقاضی اصلی (۱۲۰۰ kW) برابر ۳۰۰۰ kW و با «کل بار اضافه‌شده گزارش‌شده» (۳ مگاوات) سازگار است؛ این کنترل با Rule `XC-LOAD-SUM-OK` تأیید می‌شود. |
| پیوست‌نشدن ظرفیت هدایتی و سهم متقاضی از بار خطوط | `LN-ABSOLUTE-VS-DELTA / LN-PREEXISTING-DROP` | افت ولتاژ انتهای خط ۴۰۱ از ۳.۳٪ به ۳.۸۳٪ و خط ۴۱۵ از ۱.۱۷٪ به ۱.۸۵٪ رسیده است؛ سهم متقاضی تنها ۰.۵۳ و ۰.۶۸ واحد درصد است. موتور به‌صراحت مقدار مطلق را از تغییر ناشی از متقاضی تفکیک می‌کند تا در گزارش به‌اشتباه به بار جدید نسبت داده نشود. |

## ۶. پیکربندی آستانه‌ها و پارامترهای هزینه

تنظیمات در `app/data/settings.json` (یا در حالت exe: `%APPDATA%\ReportForge\data\settings.json`) در دو بخش جدید ذخیره می‌شود:

```json
{
  "study": {
    "heavy_consumer_min_kw": 1000.0,
    "substation_loading_tolerance_pct": null,
    "line_current_tolerance_pct": null,
    "study_substation_loading_warn_pct": null,
    "study_sc_limit_ka": null,
    "load_sum_tolerance_kw": null
  },
  "costs": {
    "overhead_per_km_million": null,
    "underground_per_km_million": null,
    "ground_substation_million": null,
    "switchgear_million": null,
    "protection_million": null,
    "other_equipment_million": null
  }
}
```

هر مقدار `None` به‌معنای «تعریف‌نشده» است و به `MISSING_RULE`/`MISSING_DATA` منجر می‌شود؛ هیچ مقدار پیش‌فرض مهندسی‌ای جایگزین آن نمی‌شود.

## ۷. اتصال Rule Engine به مولد گزارش Word

| بخش گزارش | Ruleهای تغذیه‌کننده | داده ورودی |
|---|---|---|
| اطلاعات تقاضا | `study_demand` (D-*) | جدول اطلاعات تقاضا |
| ایستگاه‌های نزدیک | `study_substation` (SS-*) | جدول ایستگاه‌های نزدیک |
| خطوط نزدیک | `study_line` (LN-*) | جدول خطوط نزدیک |
| متقاضیان همزمان | `study_coincidence` (CD-*) | تقاضاهای همزمان/سایر متقاضیان |
| نکات تحلیلی و کنترل کیفیت | `study_topology` + `study_crosscheck` | داده‌های پروژه |
| سناریوهای تأمین | `study_scenario` (SC-*) | تولید از داده مطالعه |
| بررسی اقتصادی | `study_economics` (EC-*) | مسیر + پارامترهای هزینه |

خروجی هر Rule به‌صورت هم‌زمان دو شکل دارد: (۱) نتیجه ماشین‌خوان (`RuleResult.to_dict()`) و (۲) متن مهندسی فارسی (`recommended_text`) که فقط با معتبر بودن داده‌ها تولید می‌شود.

## ۸. فایل‌های دامنه و نام‌گذاری JSON

- `app/rules/data/study_rules/coincidence_rules.json` — تقاضاهای همزمان و سایر متقاضیان محدوده — فهرست، افزایش بار هر متقاضی و مجموع (مرجع: بخش «نتیجه‌گیری و پیشنهادات»، صفحه ۴ دفترچه / صفحه ۱۲ از ۱۵)
- `app/rules/data/study_rules/crosscheck_rules.json` — کنترل ناسازگاری داده‌ها (Cross Validation) پیش از نتیجه‌گیری — Rule ID برای مغایرت‌ها: DATA_INCONSISTENCY با وضعیت REQUIRES_ENGINEER_REVIEW؛ موتور هیچ مقدار صحیحی را حدس نمی‌زند و هیچ‌کدام از دو مقدار را خودکار جایگزین نمی‌کند (بند ۵ صورت‌مسئله)
- `app/rules/data/study_rules/demand_rules.json` — اطلاعات تقاضا — استخراج و کنترل کامل بودن/سازگاری داده تقاضا (مرجع: جدول «اطلاعات تقاضا»، صفحه ۲ دفترچه / صفحه ۱۰ از ۱۵ سند TAV111-10/00)
- `app/rules/data/study_rules/economics_rules.json` — بررسی اقتصادی سناریوها — هزینه هر سناریو جداگانه ثبت و نمایش داده می‌شود؛ پارامترهای هزینه (طول شبکه، درصد هوایی/زمینی، تجهیزات کلیدی، پست زمینی، تجهیزات حفاظتی/کلیدزنی) پارامتریک‌اند و Hard-Code نمی‌شوند. اگر هزینه یک سناریو موجود نباشد: MISSING_DATA و نه صفر (بند ۴ صورت‌مسئله).
- `app/rules/data/study_rules/line_rules.json` — خطوط نزدیک به محل تقاضا — مقایسه صریح قبل/بعد: پیک بار، جریان، افت ولتاژ و جریان اتصال کوتاه (مرجع: جدول «خطوط نزدیک به محل تقاضا»، صفحه ۳ دفترچه / صفحه ۱۱ از ۱۵)
- `app/rules/data/study_rules/scenario_check_rules.json` — کنترل خروجی سناریوهای تأمین — تولید بدون انتخاب/توصیه خودسرانه (بند ۳ صورت‌مسئله)
- `app/rules/data/study_rules/scenario_rules.json` — تولید سناریوهای تأمین (Scenario 1: احداث فیدر جدید / Scenario 2: استفاده از فیدر موجود یا جایگزین). موتور سناریوها را تولید می‌کند ولی هیچ‌سناریویی را انتخاب یا توصیه نمی‌کند مگر معیار انتخاب صریحاً در Rule Set تعریف شده باشد (در نسخه فعلی تعریف نشده است).
- `app/rules/data/study_rules/substation_rules.json` — ایستگاه‌های نزدیک به محل تقاضا — فاصله، ظرفیت، درصد بارگیری ترانس‌ها و تعداد فیدر (مرجع: جدول «ایستگاه‌های نزدیک به محل تقاضا»، صفحه ۲ دفترچه / صفحه ۱۰ از ۱۵)
- `app/rules/data/study_rules/topology_rules.json` — امکان تأمین مشترک چند نقطه تقاضا از یک مسیر/فیدر — موضوع توپولوژیکی است و نباید از فاصله مکانی نتیجه‌گیری شود (بند ۶ صورت‌مسئله)

