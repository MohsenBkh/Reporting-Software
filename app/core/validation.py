# -*- coding: utf-8 -*-
"""اعتبارسنجی قبل از تولید گزارش — Validation Panel (v1.0.3).

بررسی: کامل بودن ورودی، واحدها (مثلاً kW به‌جای MW)، مقادیر غیرمنطقی، داده‌های
ناقص، کیفیت پروفیل/پیش‌بینی. هر آیتم شامل «مرحله» (step) برای هدایت کاربر و
«راهنما» (hint) برای رفع مشکل است. محدوده‌های منطقی از تنظیمات خوانده می‌شود.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from app.core.models import Project, REQUEST_INCREASE
from app.core.report_types import (REPORT_TYPE_RECLOSER, REPORT_TYPE_SECTIONALIZER,
                                   normalize, pending_message)
from app.core.settings import AppSettings

ERROR = "error"      # خطای ضروری → دکمه تولید غیرفعال
WARNING = "warning"  # هشدار → تولید مجاز
OK = "ok"

# مراحل Workflow (برای نمایش محل مشکل)
STEP_PROJECT = "project"
STEP_INPUT = "input"
STEP_LOADFLOW = "loadflow"
STEP_PROFILE = "profile"
STEP_ANALYSIS = "analysis"

_DATE_RE = re.compile(r"^(13|14)\d{2}/(0[1-9]|1[0-2])/(0[1-9]|[12]\d|3[01])$")


@dataclass
class ValidationItem:
    status: str
    message: str
    step: str = ""      # project | input | loadflow | profile | analysis
    hint: str = ""      # راهنمای رفع مشکل
    # «تغییرات آرنا» v1.1.0 — ردیابی Rule متناظر (مثلاً DATA_INCONSISTENCY)
    rule_id: str = ""
    source: str = ""
    source_page: str = ""


def _add(items, status, msg, step="", hint=""):
    items.append(ValidationItem(status, msg, step, hint))


def _fa_digits_to_en(s: str) -> str:
    return s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def validate_project(project: Project, settings: AppSettings) -> list[ValidationItem]:
    th = settings.thresholds
    items: list[ValidationItem] = []

    # ---------------- نوع گزارش (v1.3.0) ----------------
    report_type = normalize(getattr(project, "report_type", ""))
    if report_type == REPORT_TYPE_SECTIONALIZER:
        return validate_sectionalizer(project, settings)
    if report_type == REPORT_TYPE_RECLOSER:
        _add(items, WARNING, pending_message(REPORT_TYPE_RECLOSER), STEP_PROJECT,
             "تا زمان پیاده‌سازی قالب ریکلوزر، نوع گزارش را روی «متقاضیان سنگین» "
             "بگذارید.")
        return items

    # ---------------- اطلاعات پروژه ----------------
    missing = []
    if not project.applicant_name:
        missing.append("نام متقاضی")
    if not project.report_number:
        missing.append("شماره گزارش")
    if not project.date_jalali:
        missing.append("تاریخ گزارش")
    if project.requested_power_kw is None:
        missing.append("توان درخواستی/جدید")
    if project.request_type == REQUEST_INCREASE and project.existing_power_kw is None:
        missing.append("توان فعلی")
    if missing:
        _add(items, ERROR, "اطلاعات پروژه ناقص است: " + "، ".join(missing), STEP_PROJECT,
             "فیلدهای یادشده را در صفحه «پروژه» تکمیل کنید.")
    else:
        _add(items, OK, "اطلاعات پروژه", STEP_PROJECT)

    if project.date_jalali and not _DATE_RE.match(_fa_digits_to_en(project.date_jalali)):
        _add(items, WARNING, f"قالب تاریخ «{project.date_jalali}» استاندارد نیست.", STEP_PROJECT,
             "تاریخ را به‌صورت 1405/06/15 وارد کنید.")

    # ---------------- منطق توان‌ها / واحد ----------------
    rq, ex = project.requested_power_kw, project.existing_power_kw
    if rq is not None and rq <= 0:
        _add(items, ERROR, "توان درخواستی باید بزرگ‌تر از صفر باشد.", STEP_PROJECT)
    if rq is not None and 0 < rq < 20:
        _add(items, WARNING, f"توان درخواستی {rq:g} کیلووات بسیار کوچک است؛ احتمالاً واحد MW وارد شده است.",
             STEP_PROJECT, "توان‌ها باید بر حسب کیلووات (kW) باشند.")
    if rq is not None and rq > th.plausible_peak_max_mw * 1000:
        _add(items, WARNING, f"توان درخواستی {rq:,.0f} کیلووات غیرمعمول بزرگ است؛ واحد بررسی شود.", STEP_PROJECT)
    if project.request_type == REQUEST_INCREASE and ex is not None and rq is not None:
        if rq < ex:
            _add(items, WARNING, "توان جدید کمتر از توان فعلی است — بررسی شود.", STEP_PROJECT)
        elif rq == ex:
            _add(items, ERROR, "توان جدید با توان فعلی برابر است؛ افزایش قدرتی وجود ندارد.", STEP_PROJECT)
    if (rq is not None and rq < 1000 and project.request_type == REQUEST_INCREASE):
        _add(items, WARNING, "توان درخواستی کمتر از ۱۰۰۰ کیلووات است (موضوع دستورالعمل مصارف سنگین نیست).", STEP_PROJECT)

    # ---------------- فیدرها ----------------
    feeders = project.active_feeders          # v1.2.0: فیدرهای خاموش (On/Off) نادیده گرفته می‌شوند
    if not feeders:
        _add(items, ERROR, "هیچ فیدری تعریف نشده است.", STEP_INPUT,
             "در صفحه «ورود داده» حداقل یک فیدر اضافه کنید.")
    else:
        no_name = [i + 1 for i, f in enumerate(feeders) if not f.name]
        if no_name:
            _add(items, ERROR, f"نام فیدر(های) شماره {no_name} خالی است.", STEP_INPUT)
        dup = [n for n, c in Counter(f.name for f in feeders if f.name).items() if c > 1]
        if dup:
            _add(items, ERROR, "نام فیدر تکراری است: " + "، ".join(dup), STEP_INPUT,
                 "هر فیدر باید نام یکتا داشته باشد.")
        no_peak = [f.display_name for f in feeders if f.peak_load_mw is None]
        if no_peak:
            _add(items, ERROR, "پیک بار فیدرهای " + "، ".join(no_peak) + " وارد نشده است.", STEP_INPUT,
                 "پیک بار را وارد کنید یا پروفیل بار را Import نمایید.")
        no_cap = [f.display_name for f in feeders if f.capacity_mw is None]
        if no_cap:
            _add(items, WARNING, "معیار بارگذاری فیدرهای " + "، ".join(no_cap) +
                 " ثبت نشده (طبقه‌بندی بارگذاری «نیازمند بررسی» خواهد بود).", STEP_INPUT)

        for f in feeders:
            n = f.display_name
            if f.peak_load_mw is not None:
                if f.peak_load_mw <= 0:
                    _add(items, ERROR, f"پیک بار فیدر {n} باید مثبت باشد.", STEP_INPUT)
                elif f.peak_load_mw > th.plausible_peak_max_mw:
                    _add(items, WARNING, f"پیک بار فیدر {n} ({f.peak_load_mw:g}) غیرمنطقی بزرگ است؛ احتمالاً kW به‌جای MW وارد شده.",
                         STEP_INPUT, "پیک بار باید بر حسب مگاوات (MW) باشد.")
            if f.power_factor is not None and not (th.plausible_pf_min <= f.power_factor <= 1.0):
                _add(items, WARNING, f"ضریب توان فیدر {n} ({f.power_factor:g}) خارج از محدوده منطقی {th.plausible_pf_min:g} تا ۱ است.", STEP_INPUT)
            if f.peak_year is not None and not (1380 <= f.peak_year <= 1450):
                _add(items, WARNING, f"سال پیک فیدر {n} ({f.peak_year}) باید سال شمسی باشد.", STEP_INPUT)
            if f.max_current_a is not None and f.max_current_a <= 0:
                _add(items, ERROR, f"حداکثر جریان مجاز فیدر {n} باید مثبت باشد.", STEP_INPUT)
            if (f.capacity_mw is not None and f.peak_load_mw is not None
                    and f.capacity_mw > 0 and f.peak_load_mw > f.capacity_mw):
                _add(items, WARNING, f"پیک بار فیدر {n} از معیار بارگذاری آن بیشتر است.", STEP_INPUT)
            if (f.max_current_a and f.peak_current_a and f.peak_current_a > f.max_current_a):
                _add(items, WARNING, f"پیک جریان فیدر {n} از جریان مجاز هادی بیشتر است.", STEP_INPUT)
        _add(items, OK, f"اطلاعات {len(feeders)} فیدر", STEP_INPUT)

    # ---------------- نتایج پخش بار ----------------
    for f in feeders:
        n = f.display_name
        for label, res in (("قبل", f.before), ("بعد", f.after)):
            if not res.is_complete():
                miss = [t for t, v in (("جریان", res.current_a), ("تلفات", res.loss_kw),
                                       ("حداقل ولتاژ", res.min_voltage_pu)) if v is None]
                _add(items, ERROR, f"نتایج «{label}» فیدر {n} ناقص است ({'، '.join(miss)}).", STEP_LOADFLOW,
                     "نتایج PowerFactory را در صفحه «پخش بار» کامل کنید.")
                continue
            for what, v in (("حداقل ولتاژ", res.min_voltage_pu), ("ولتاژ باس متقاضی", res.applicant_bus_voltage_pu)):
                if v is None:
                    continue
                if v > 2:
                    _add(items, ERROR, f"{what} «{label}» فیدر {n} برابر {v:g} است؛ به نظر کیلوولت یا درصد وارد شده.",
                         STEP_LOADFLOW, "ولتاژ باید بر حسب پریونیت (p.u.) باشد، مثلاً 0.97.")
                elif not (th.plausible_voltage_min_pu <= v <= th.plausible_voltage_max_pu):
                    _add(items, WARNING, f"{what} «{label}» فیدر {n} ({v:g} pu) غیرمنطقی است.", STEP_LOADFLOW)
            if res.current_a is not None and (res.current_a < 0 or res.current_a > th.plausible_current_max_a):
                _add(items, WARNING, f"جریان «{label}» فیدر {n} ({res.current_a:g} A) غیرمنطقی است.", STEP_LOADFLOW)
            if res.loss_kw is not None and res.loss_kw < 0:
                _add(items, ERROR, f"تلفات «{label}» فیدر {n} منفی است.", STEP_LOADFLOW)
        if f.before.is_complete() and f.after.is_complete():
            added = project.added_power_mw()
            if added and added > 0:
                if f.after.current_a < f.before.current_a:
                    _add(items, WARNING, f"جریان فیدر {n} پس از افزودن بار کاهش یافته؛ ترتیب قبل/بعد یا سناریو بررسی شود.", STEP_LOADFLOW)
                if f.after.min_voltage_pu > f.before.min_voltage_pu + 0.005:
                    _add(items, WARNING, f"حداقل ولتاژ فیدر {n} پس از افزودن بار افزایش یافته؛ نتایج بررسی شود.", STEP_LOADFLOW)
    if feeders and all(f.before.is_complete() and f.after.is_complete() for f in feeders):
        _add(items, OK, "نتایج پخش بار قبل و بعد", STEP_LOADFLOW)

    # ---------------- پروفیل و پیش‌بینی ----------------
    no_profile = [f.display_name for f in feeders if not f.profile_stats.n_points]
    if no_profile:
        _add(items, WARNING, "پروفیل بار برای فیدرهای " + "، ".join(no_profile) + " وارد نشده است.", STEP_PROFILE)
    else:
        _add(items, OK, "پروفیل بار", STEP_PROFILE)
    for f in feeders:
        st = f.profile_stats
        if st.n_points and st.peak_p_mw is not None and f.peak_load_mw is not None and f.peak_load_mw > 0:
            diff = abs(st.peak_p_mw - f.peak_load_mw) / f.peak_load_mw * 100
            if diff > 10:
                _add(items, WARNING, f"پیک پروفیل فیدر {f.display_name} ({st.peak_p_mw:g}) با پیک واردشده ({f.peak_load_mw:g}) {diff:.0f}٪ اختلاف دارد.", STEP_PROFILE)
    no_fc = [f.display_name for f in feeders if not f.forecast.available]
    if no_fc:
        _add(items, WARNING, "پیش‌بینی برای فیدرهای " + "، ".join(no_fc) + " موجود نیست.", STEP_PROFILE)
    review_fc = [f for f in feeders if f.forecast.needs_review and f.forecast.method != "none"]
    for f in review_fc:
        _add(items, WARNING, f"پیش‌بینی فیدر {f.display_name} نیازمند بررسی مهندس است: {f.forecast.note}",
             STEP_ANALYSIS, "در صفحه «بازبینی مهندس» نتیجه را تأیید، ویرایش یا رد کنید.")
    if feeders and not no_fc and not review_fc:
        _add(items, OK, "پیش‌بینی بار", STEP_PROFILE)

    # ---------------- تصاویر / مانور ----------------
    _add(items, OK if project.images else WARNING,
         "تصاویر" if project.images else "تصویری افزوده نشده (اختیاری).", STEP_INPUT)
    man = project.maneuver
    if man.enabled:
        if not man.note:
            _add(items, WARNING, "مانور فعال است اما توضیح (عدم قطعیت) ندارد.", STEP_PROJECT)
        names = set(project.feeder_names)
        for label, v in (("مبدأ", man.source_feeder), ("مقصد", man.target_feeder)):
            if v and names and v not in names:
                _add(items, WARNING, f"فیدر {label} مانور («{v}») در فهرست فیدرها نیست.", STEP_PROJECT)
        if man.transferred_mw is not None and man.transferred_mw <= 0:
            _add(items, WARNING, "مقدار بار منتقل‌شده در مانور باید مثبت باشد.", STEP_PROJECT)
    # ---------------- کنترل ناسازگاری داده‌های مطالعه (Cross Validation) ----------------
    items.extend(study_validation_items(project, settings))

    items.append(ValidationItem(OK, "قالب گزارش", ""))
    return items


# ---------------------------------------------------------------------------
# v1.3.0 — اعتبارسنجی گزارش نوع «سکشنالایزر» (اسکلت)
# ---------------------------------------------------------------------------
def validate_sectionalizer(project: Project, settings: AppSettings) -> list[ValidationItem]:
    """اعتبارسنجی سبک برای گزارش سکشنالایزر.

    تا ارسال جزئیات تکمیلی توسط کارفرما، فقط فیلدهای اصلی گزارش بررسی می‌شوند؛
    کمبود داده‌های فنی (جریان خطا و تنظیمات) «هشدار» است نه خطا، تا ساخت گزارش
    ممکن بماند و مقادیر ناموجود در جدول با وضعیت «ناموجود» درج شوند.
    """
    items: list[ValidationItem] = []
    sz = project.sectionalizer

    missing = []
    if not project.applicant_name:
        missing.append("نام متقاضی/درخواست‌دهنده")
    if not project.report_number:
        missing.append("شماره گزارش")
    if not project.date_jalali:
        missing.append("تاریخ گزارش")
    if missing:
        _add(items, ERROR, "اطلاعات پروژه ناقص است: " + "، ".join(missing),
             STEP_PROJECT, "فیلدهای یادشده را در صفحه «پروژه» تکمیل کنید.")
    else:
        _add(items, OK, "اطلاعات پروژه", STEP_PROJECT)

    if not sz.feeder_name and not sz.installation_location:
        _add(items, WARNING, "فیدر هدف یا محل نصب سکشنالایزر مشخص نشده است.",
             STEP_INPUT, "در صفحه «پروژه» مشخصات سکشنالایزر را تکمیل کنید.")
    else:
        _add(items, OK, "محل نصب سکشنالایزر", STEP_INPUT)

    if not sz.is_complete():
        _add(items, WARNING,
             "سطح اتصال کوتاه/تنظیمات حفاظتی سکشنالایزر ناقص است؛ مقادیر ناموجود "
             "در گزارش با وضعیت «ناموجود» درج می‌شوند.", STEP_INPUT,
             "جریان اتصال کوتاه و جریان پیکاپ را تکمیل کنید.")
    else:
        _add(items, OK, "تنظیمات حفاظتی سکشنالایزر", STEP_INPUT)

    items.append(ValidationItem(OK, "قالب گزارش", ""))
    return items


# ---------------------------------------------------------------------------
# «تغییرات آرنا» v1.1.0 — کنترل ناسازگاری داده‌ها با Rule Engine
# ---------------------------------------------------------------------------
_RULE_STATUS_MAP = {
    "PASS": OK,
    "INFO": OK,
    "WARNING": WARNING,
    "FAIL": WARNING,
    "DATA_ERROR": WARNING,
    "REQUIRES_ENGINEER_REVIEW": WARNING,
    "MISSING_RULE": WARNING,
    "MISSING_DATA": WARNING,
}


def study_validation_items(project: Project, settings: AppSettings,
                           engine=None) -> list[ValidationItem]:
    """آیتم‌های اعتبارسنجی حاصل از Ruleهای کنترل ناسازگاری/توپولوژی.

    مطابق بند ۵ صورت‌مسئله: مغایرت‌ها با Rule ID = DATA_INCONSISTENCY و وضعیت
    REQUIRES_ENGINEER_REVIEW ثبت می‌شوند؛ موتور مقدار صحیح را حدس نمی‌زند و
    هیچ‌کدام از دو مقدار را خودکار جایگزین نمی‌کند.
    """
    from app.core.study import collect_study_results, has_study_data
    from app.rules.rule_engine import RuleEngine

    if not has_study_data(project):
        return []
    eng = engine or RuleEngine()
    results = collect_study_results(project, settings, eng)
    out: list[ValidationItem] = []
    for r in results:
        if r.category not in ("study_crosscheck", "study_topology"):
            continue
        status = _RULE_STATUS_MAP.get(r.status, WARNING)
        hint = ""
        if r.status == "MISSING_RULE":
            hint = "برای رفع: آستانه‌های تعریف‌نشده را در صفحه «تنظیمات» تعیین کنید."
        elif r.status in ("DATA_ERROR", "REQUIRES_ENGINEER_REVIEW"):
            hint = "داده ورودی را بازبینی کنید؛ نرم‌افزار هیچ مقداری را خودکار اصلاح/جایگزین نمی‌کند."
        out.append(ValidationItem(
            status=status,
            message=r.finding or f"{r.rule_id}: {r.status}",
            step=STEP_INPUT if r.category == "study_crosscheck" else STEP_ANALYSIS,
            hint=hint,
            rule_id=r.rule_id,
            source=r.source,
            source_page=r.source_page))
    return out


def missing_rule_items(project: Project, settings: AppSettings, engine=None) -> list[ValidationItem]:
    """Ruleهایی که به آستانه تعریف‌نشده وابسته‌اند (MISSING_RULE) — برای شفافیت."""
    from app.core.study import collect_study_results, has_study_data
    from app.rules.rule_engine import RuleEngine

    if not has_study_data(project):
        return []
    eng = engine or RuleEngine()
    results = collect_study_results(project, settings, eng)
    missing = sorted({(r.rule_id, tuple(r.missing)) for r in results if r.status == "MISSING_RULE"})
    out: list[ValidationItem] = []
    for rule_id, keys in missing:
        out.append(ValidationItem(
            WARNING,
            f"Rule «{rule_id}» نیازمند آستانه تعریف‌نشده است: {'، '.join(keys)}",
            STEP_ANALYSIS,
            "مقدار آستانه را در صفحه «تنظیمات» وارد کنید تا داوری مهندسی انجام شود (هیچ مقدار پیش‌فرضی فرض نمی‌شود).",
            rule_id=rule_id))
    return out


def has_errors(items: list[ValidationItem]) -> bool:
    return any(i.status == ERROR for i in items)


def summary_counts(items: list[ValidationItem]) -> tuple[int, int]:
    """(تعداد خطا، تعداد هشدار)."""
    return (sum(1 for i in items if i.status == ERROR),
            sum(1 for i in items if i.status == WARNING))
