# -*- coding: utf-8 -*-
"""تولید مستند Rule Set مطالعه مصارف سنگین — «تغییرات آرنا» v1.2.0.

اجرا:

    python tools/export_rule_set.py

خروجی: docs/STUDY_RULE_SET_v1.2.0.md  (فهرست Ruleها + Ruleهای فاقد Threshold +
ناسازگاری‌های داده‌ای نمونه + راهنمای پیکربندی)

این ابزار مستقیماً از فایل‌های Rule (`app/rules/data/study_rules/*.json`) و موتور
قواعد، مستند را می‌سازد تا مستند و کد هرگز از هم جدا نشوند.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.settings import AppSettings                      # noqa: E402
from app.rules.outcome import STATUS_LABELS_FA, SEVERITY_BY_STATUS  # noqa: E402
from app.rules.rule_engine import RuleEngine                    # noqa: E402

OUT = ROOT / "docs" / "STUDY_RULE_SET_v1.2.0.md"

DOMAIN_TITLES = {
    "study_demand": "A) اطلاعات تقاضا",
    "study_substation": "B) ایستگاه‌های نزدیک به محل تقاضا",
    "study_line": "C) خطوط نزدیک به محل تقاضا",
    "study_coincidence": "D) تقاضاهای همزمان و سایر متقاضیان",
    "study_topology": "D-۲) تأمین مشترک چند نقطه تقاضا (توپولوژی)",
    "study_scenario": "E) سناریوهای تأمین",
    "study_economics": "E-۲) بررسی اقتصادی سناریوها",
    "study_crosscheck": "کنترل ناسازگاری داده‌ها (Cross Validation)",
    "study_loading": "F) بارگذاری کل فیدر (پیک + بار جدید) و راهکارهای تعدیل بار",
    "study_rearrange": "F-۲) بازآرایی فیدر و انتقال بار به فیدر همجوار",
}

SAMPLE_INCONSISTENCIES = [
    ("ناسازگاری درصد بارگیری ترانس T1 ایستگاه «شهرک صنعتی»",
     "SS-LOADING-MISMATCH / SS-LOADING-CHECK-NO-THRESHOLD",
     "درصد بارگیری ثبت‌شده T1 = ۶۱.۰۵٪ در حالی که نسبت پیک به ظرفیت (۲۷.۶۲ از ۴۰ MVA) "
     "مقدار ۶۹.۰۵٪ می‌دهد؛ اختلاف ۸ واحد درصد. موتور این اختلاف را محاسبه و در "
     "calculated_values قرار می‌دهد، اما تا تعیین تلورانس کنترل "
     "(`substation_loading_tolerance_pct`) هیچ‌کدام از دو مقدار را صحیح فرض نمی‌کند "
     "(وضعیت MISSING_RULE)."),
    ("هزینه صفر سناریو ۲ بدون مبنای هزینه",
     "EC-COST-ZERO-NO-BASIS (DATA_ERROR)",
     "در جدول بررسی اقتصادی، «هزینه سناریو ۲: ۰» ثبت شده در حالی که هیچ قلم هزینه "
     "(طول شبکه، درصد هوایی/زمینی، تجهیزات) برای آن وجود ندارد. مطابق Rule Set، نبود "
     "داده هزینه باید MISSING_DATA ثبت شود؛ صفر فقط با مبنای مستند معتبر است."),
    ("عدم ذکر اقلام خارج از برآورد سناریو ۱",
     "EC-EXCLUDED-ITEMS (MISSING_DATA)",
     "متن مرجع صریحاً «هزینه کلید ایستگاه» و «احداث پست زمینی» و «هزینه تأمین» را از برآورد "
     "۵۱۳۰ میلیون تومان مستثنی کرده است. این اقلام به‌صورت MISSING_DATA ثبت می‌شوند "
     "(نه صفر) و در جدول بررسی اقتصادی نمایش داده می‌شوند."),
    ("طول مسیر سناریو ۱ (۲ کیلومتر) در برابر فاصله نزدیک‌ترین ایستگاه (۴ کیلومتر)",
     "EC-ROUTE-LENGTH-VS-DISTANCE (REQUIRES_ENGINEER_REVIEW)",
     "طول شبکه موردنیاز سناریو ۱ برابر ۲ کیلومتر است، در حالی که نزدیک‌ترین ایستگاه جدول "
     "«ایستگاه‌های نزدیک» ۴ کیلومتر فاصله دارد. موتور نتیجه نمی‌گیرد که داده غلط است؛ "
     "بلکه منبع تغذیه و مسیر سناریو را «نیازمند مستندسازی» علامت می‌زند."),
    ("نتیجه‌گیری «عدم امکان تأمین یکجا بر پایه پراکندگی مکانی»",
     "TP-SHARED-SUPPLY-REVIEW (REQUIRES_ENGINEER_REVIEW)",
     "سند مرجع نتیجه می‌گیرد که چون ۴ تقاضا در نقاط پراکنده قرار دارند، تأمین یکجای آن‌ها "
     "ممکن نیست. این نتیجه از روی فاصله مکانی گرفته شده و شاهد توپولوژیکی (مسیر فیدر، "
     "آرایش شبکه، ظرفیت انتقال) ندارد؛ Rule Engine این مورد را فاقد شاهد لازم می‌داند و "
     "بررسی توپولوژیکی را درخواست می‌کند."),
    ("نبود ظرفیت هدایتی خطوط و حد مجاز اتصال کوتاه",
     "LN-CURRENT-LIMIT-MISSING (MISSING_DATA) / LN-SC-LIMIT-MISSING (MISSING_RULE)",
     "جدول «خطوط نزدیک» فقط پیک بار و جریان اتصال کوتاه را می‌دهد و ظرفیت هدایتی/حد مجاز "
     "اتصال کوتاه را ارائه نمی‌کند؛ بنابراین مقایسه جریان با ظرفیت و داوری درباره تحمل "
     "تجهیزات انجام نمی‌شود و مقادیر صرفاً ثبت می‌گردند."),
    ("مجموع افزایش بار متقاضیان = ۳۰۰۰ kW (سازگار)",
     "XC-LOAD-SUM-OK (PASS)",
     "مجموع افزایش بار سه متقاضی همزمان (۵۰۰ + ۱۱۰۰ + ۲۰۰ = ۱۸۰۰ kW) به‌همراه افزایش بار "
     "متقاضی اصلی (۱۲۰۰ kW) برابر ۳۰۰۰ kW و با «کل بار اضافه‌شده گزارش‌شده» (۳ مگاوات) "
     "سازگار است؛ این کنترل با Rule `XC-LOAD-SUM-OK` تأیید می‌شود."),
    ("پیوست‌نشدن ظرفیت هدایتی و سهم متقاضی از بار خطوط",
     "LN-ABSOLUTE-VS-DELTA / LN-PREEXISTING-DROP",
     "افت ولتاژ انتهای خط ۴۰۱ از ۳.۳٪ به ۳.۸۳٪ و خط ۴۱۵ از ۱.۱۷٪ به ۱.۸۵٪ رسیده است؛ "
     "سهم متقاضی تنها ۰.۵۳ و ۰.۶۸ واحد درصد است. موتور به‌صراحت مقدار مطلق را از تغییر "
     "ناشی از متقاضی تفکیک می‌کند تا در گزارش به‌اشتباه به بار جدید نسبت داده نشود."),
]


def _fmt_thresholds(rule) -> str:
    if not rule.thresholds:
        return "—"
    parts = []
    for t in rule.thresholds:
        basis = {"document": "سند مرجع", "config": "پیکربندی", "undefined": "تعریف‌نشده"}.get(
            t.basis, t.basis)
        parts.append(f"`{t.key}` ({basis})")
    return "، ".join(parts)


def _fmt_requires(rule) -> str:
    return "، ".join(f"`{k}`" for k in rule.requires) or "—"


def build() -> str:
    engine = RuleEngine()
    s = AppSettings()
    lines: list[str] = []
    add = lines.append

    add("# مجموعه Ruleهای مطالعه مصارف سنگین — نسخه ۱.۲.۰ («تغییرات آرنا»)")
    add("")
    add("این مستند به‌صورت خودکار از فایل‌های Rule و موتور قواعد تولید می‌شود "
        "(`python tools/export_rule_set.py`).")
    add("")
    add("**سند مرجع:** TAV111-10/00 — «دستورالعمل مطالعات فنی اتصال مصارف سنگین به شبکه توزیع» "
        "(فایل پیوست، صفحات ۱۰ تا ۱۲ از ۱۵: جدول اطلاعات تقاضا، جدول ایستگاه‌های نزدیک، "
        "جدول خطوط نزدیک، نتیجه‌گیری و پیشنهادات).")
    add("")
    add("**اصل حاکم:** هیچ معیار، حد مجاز یا نتیجه‌ای خارج از محتوای سند و داده ورودی "
        "ساخته نمی‌شود. اگر برای تصمیم‌گیری آستانه لازم باشد و در سند/پیکربندی نباشد، "
        "وضعیت `MISSING_RULE` ثبت می‌گردد؛ اگر داده لازم نباشد، `MISSING_DATA`.")
    add("")
    add("## ۱. خروجی استاندارد هر Rule")
    add("")
    add("```json")
    add(json.dumps({
        "rule_id": "...", "category": "...",
        "status": "PASS | WARNING | FAIL | INFO | DATA_ERROR | REQUIRES_ENGINEER_REVIEW | MISSING_RULE | MISSING_DATA",
        "input_values": {}, "calculated_values": {}, "finding": "...", "evidence": "...",
        "source": "TAV111-10/00", "source_page": "...", "recommended_text": "...",
        "engineer_review_required": True,
        "meta": {"rule_key": "...", "rule_name": "...", "owner": "...",
                 "thresholds": {}, "missing": [], "severity": "..."},
    }, ensure_ascii=False, indent=2))
    add("```")
    add("")
    add("زنجیره ردیابی هر نتیجه: **Input → Calculation → Rule → Finding → Evidence → Report Text** "
        "(متد `RuleResult.trace_lines()`).")
    add("")
    add("## ۲. نگاشت وضعیت‌ها")
    add("")
    add("| وضعیت | معنی | شدت در نرم‌افزار | متن گزارش |")
    add("|---|---|---|---|")
    for st, label in STATUS_LABELS_FA.items():
        no_text = "تولید نمی‌شود" if st in ("MISSING_RULE", "DATA_ERROR") else (
            "تولید می‌شود (در نبود داده با برچسب MISSING_DATA)" if st == "MISSING_DATA"
            else "تولید می‌شود")
        add(f"| `{st}` | {label} | {SEVERITY_BY_STATUS.get(st, '-')} | {no_text} |")
    add("")

    # --- جدول Ruleها ---
    add("## ۳. فهرست Ruleهای استخراج‌شده")
    add("")
    total_analysis = 0
    for domain, title in DOMAIN_TITLES.items():
        rules = engine.analysis_by_domain(domain)
        if not rules:
            continue
        add(f"### {title}")
        add("")
        add("| شناسه گزارش‌شده (Rule ID) | شناسه داخلی | نام | وضعیت | داده‌های الزامی | آستانه‌ها | صفحه مرجع |")
        add("|---|---|---|---|---|---|---|")
        for r in rules:
            total_analysis += 1
            reported = r.rule_id or r.id
            add(f"| `{reported}` | `{r.id}` | {r.name} | `{r.status}` | {_fmt_requires(r)} "
                f"| {_fmt_thresholds(r)} | {r.source_page} |")
        add("")

    add("### Ruleهای تولید سناریو (kind = scenario)")
    add("")
    add("| شناسه | نام | نوع سناریو | شرط تولید | وضعیت بازبینی | صفحه مرجع |")
    add("|---|---|---|---|---|---|")
    for r in sorted(engine.scenario_rules.values(), key=lambda x: -x.priority):
        add(f"| `{r.id}` | {r.name} | `{r.kind}` | `{r.condition}` | `{r.review_status}` "
            f"| {r.source_page} |")
    add("")
    add(f"**جمع:** {total_analysis} Rule تحلیلی + {len(engine.scenario_rules)} Rule تولید سناریو.")
    add("")

    # --- Ruleهای فاقد Threshold ---
    add("## ۴. Ruleهای فاقد Threshold (نیازمند تعیین آستانه توسط مهندس)")
    add("")
    add("فهرست زیر همه وابستگی‌های آستانه‌ای Ruleهای تحلیلی را نشان می‌دهد. ردیف‌هایی که "
        "«مقدار پیش‌فرض فعلی» آن‌ها `None` است، در وضعیت جاری به `MISSING_RULE` منجر "
        "می‌شوند: هیچ مقدار جایگزینی فرض نمی‌شود و متن گزارش تولید نمی‌گردد تا مهندس "
        "آستانه را تعیین کند. ردیف‌هایی که مبنای «سند مرجع» دارند، از متن دستورالعمل "
        "گرفته شده‌اند (مانند دامنه شمول ۱ مگاوات و سقف تغییر ولتاژ).")
    add("")
    add("| شناسه داخلی | آستانه لازم | مبنای اعلام‌شده | مقدار پیش‌فرض فعلی | صفحه مرجع |")
    add("|---|---|---|---|---|")
    flat = s.thresholds_flat()
    for r in sorted(engine.analysis_rules.values(), key=lambda x: (-x.priority, x.id)):
        for t in r.thresholds:
            value = flat.get(t.key)
            value_txt = "تعریف‌نشده (None)" if value is None else f"`{value}`"
            basis = {"document": "سند مرجع", "config": "پیکربندی (قابل ویرایش)",
                     "undefined": "تعریف‌نشده"}.get(t.basis, t.basis)
            add(f"| `{r.id}` | `{t.key}` — {t.label} | {basis} | {value_txt} | {r.source_page} |")
    add("")
    add("**آستانه‌های تعریف‌شده در پیکربندی (مقدار پیش‌فرض):**")
    add("")
    for key in ("heavy_consumer_min_kw", "voltage_change_max_pct", "voltage_min_pu",
                "voltage_max_pu", "loading_light_pct", "loading_normal_pct",
                "loading_semi_pct", "loading_heavy_pct"):
        add(f"- `{key}` = `{flat.get(key)}`")
    add("")
    add("**پارامترهای هزینه (پیش‌فرض خالی — تا تعیین‌نشدن، برآورد هزینه ساخته نمی‌شود):**")
    add("")
    for key in ("cost_overhead_per_km_million", "cost_underground_per_km_million",
                "cost_ground_substation_million", "cost_switchgear_million",
                "cost_protection_million", "cost_other_equipment_million"):
        add(f"- `{key}` = `{flat.get(key)}`")
    add("")

    # --- ناسازگاری‌های نمونه ---
    add("## ۵. ناسازگاری‌ها و نکات داده‌ای نمونه مرجع")
    add("")
    add("تحلیل زیر بر پایه چهار صفحه پیوست (صفحات ۱۰ تا ۱۲ از ۱۵) و با اجرای همین Rule Set "
        "روی داده‌های همان صفحات تهیه شده است:")
    add("")
    add("| مورد | Rule مرتبط | توضیح |")
    add("|---|---|---|")
    for title, rule, note in SAMPLE_INCONSISTENCIES:
        add(f"| {title} | `{rule}` | {note} |")
    add("")

    # --- پیکربندی ---
    add("## ۶. پیکربندی آستانه‌ها و پارامترهای هزینه")
    add("")
    add("تنظیمات در `app/data/settings.json` (یا در حالت exe: `%APPDATA%\\ReportForge\\data\\settings.json`) "
        "در دو بخش جدید ذخیره می‌شود:")
    add("")
    add("```json")
    add(json.dumps({
        "study": {
            "heavy_consumer_min_kw": 1000.0,
            "substation_loading_tolerance_pct": None,
            "line_current_tolerance_pct": None,
            "study_substation_loading_warn_pct": None,
            "study_sc_limit_ka": None,
            "load_sum_tolerance_kw": None,
        },
        "costs": {
            "overhead_per_km_million": None,
            "underground_per_km_million": None,
            "ground_substation_million": None,
            "switchgear_million": None,
            "protection_million": None,
            "other_equipment_million": None,
        },
    }, ensure_ascii=False, indent=2))
    add("```")
    add("")
    add("هر مقدار `None` به‌معنای «تعریف‌نشده» است و به `MISSING_RULE`/`MISSING_DATA` "
        "منجر می‌شود؛ هیچ مقدار پیش‌فرض مهندسی‌ای جایگزین آن نمی‌شود.")
    add("")

    # --- اتصال به گزارش ---
    add("## ۷. اتصال Rule Engine به مولد گزارش Word")
    add("")
    add("| بخش گزارش | Ruleهای تغذیه‌کننده | داده ورودی |")
    add("|---|---|---|")
    add("| اطلاعات تقاضا | `study_demand` (D-*) | جدول اطلاعات تقاضا |")
    add("| ایستگاه‌های نزدیک | `study_substation` (SS-*) | جدول ایستگاه‌های نزدیک |")
    add("| خطوط نزدیک | `study_line` (LN-*) | جدول خطوط نزدیک |")
    add("| متقاضیان همزمان | `study_coincidence` (CD-*) | تقاضاهای همزمان/سایر متقاضیان |")
    add("| نکات تحلیلی و کنترل کیفیت | `study_topology` + `study_crosscheck` | داده‌های پروژه |")
    add("| سناریوهای تأمین | `study_scenario` (SC-*) | تولید از داده مطالعه |")
    add("| بررسی اقتصادی | `study_economics` (EC-*) | مسیر + پارامترهای هزینه |")
    add("")
    add("خروجی هر Rule به‌صورت هم‌زمان دو شکل دارد: (۱) نتیجه ماشین‌خوان (`RuleResult.to_dict()`) "
        "و (۲) متن مهندسی فارسی (`recommended_text`) که فقط با معتبر بودن داده‌ها تولید می‌شود.")
    add("")
    add("## ۸. فایل‌های دامنه و نام‌گذاری JSON")
    add("")
    for path in sorted((ROOT / "app" / "rules" / "data" / "study_rules").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        add(f"- `{path.relative_to(ROOT)}` — {data.get('description', '')}")
    add("")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"written: {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
