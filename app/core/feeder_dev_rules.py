# -*- coding: utf-8 -*-
"""موتور قواعد مطالعه «توسعه و اصلاح فیدر» — v2.5.0.

قواعد و ادبیات تحلیل از سه دفترچه نمونه استخراج شده‌اند:

1. «اصلاح خط مسیر اوچ‌بلاغ به سمت کوراماللو — فیدر 5 گرمی» (FD-26-001)
2. «جابه‌جایی خط 20 کیلوولت داخل روستای قره‌آغاج — فیدر 5 گرمی» (FD-26-002)
3. «توسعه و احداث شبکه جهت فیدر جدید از پست فوق توزیع آغدام — پارس‌آباد»

اصل مهندسی گزارش‌ساز: هیچ عددی ساخته نمی‌شود؛ هر جمله فقط از داده‌های
ثبت‌شده کاربر استنتاج می‌شود و هر قاعده «شاهد» (source) دارد.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.core.models import PRESENCE_YES, CandidateBus, FeederDevelopmentInfo, Project

# --- آستانه‌های قواعد (برگرفته از ادبیات نمونه‌ها) ---------------------------
LOADING_HIGH_PCT = 70.0       # نمونه ۱: بارگیری 78.5٪ «نسبتاً بالا»
LOADING_CRITICAL_PCT = 90.0   # نمونه ۳: بهره‌برداری «در وضعیت ظرفیت کامل»
PF_LOW = 0.9                  # نمونه ۱/۲: ضریب قدرت 0.92 «مناسب»
LOAD_SWING_RATIO = 2.0        # نمونه ۱: فاصله 5.5/2.3 → «ماهیت فصلی و متغیر»
VOLT_LOW_PU = 0.95            # نمونه ۳: 0.828 پریونیت «وضعیت نامناسب»
VOLT_HIGH_PU = 1.05           # نمونه ۱: 1.06 پریونیت بعد از اصلاح (قابل توجه)

INFO, WARNING = "info", "warning"


@dataclass
class FdFinding:
    """یک یافته موتور قواعد: متن + شدت + شاهد (برای ردیابی)."""

    key: str
    severity: str
    title: str
    text: str
    source: str = ""           # قاعده/نمونه مبنا


def _num(v: float) -> str:
    return f"{v:g}"


# ---------------------------------------------------------------------------
# قواعد سطح فیدر (جدول «مشخصات فیدرهای محدوده مطالعه»)
# ---------------------------------------------------------------------------
def feeder_findings(info: FeederDevelopmentInfo) -> list[FdFinding]:
    out: list[FdFinding] = []
    for f in info.feeders or []:
        name = f.name or "فیدر مورد مطالعه"
        if f.loading_pct is not None:
            if f.loading_pct >= LOADING_CRITICAL_PCT:
                out.append(FdFinding(
                    f"fd.loading.{name}", WARNING, "بارگیری بحرانی",
                    f"بارگیری {name} برابر {_num(f.loading_pct)} درصد است و فیدر عملاً در "
                    "وضعیت ظرفیت کامل بهره‌برداری می‌شود؛ تعدیل بار این فیدر در اولویت است.",
                    "نمونه ۳ (فیدرهای اجیرلو در پیک تابستان)"))
            elif f.loading_pct >= LOADING_HIGH_PCT:
                out.append(FdFinding(
                    f"fd.loading.{name}", INFO, "بارگیری نسبتاً بالا",
                    f"بارگیری {name} برابر {_num(f.loading_pct)} درصد است و فیدر از ظرفیت "
                    "بهره‌برداری خود به میزان چشمگیری استفاده می‌کند؛ این موضوع در ارزیابی "
                    "نتایج پخش بار و تصمیم‌گیری درباره طرح باید مد نظر قرار گیرد.",
                    "نمونه ۱ (بارگیری 78.5٪ فیدر 5 گرمی)"))
        if f.peak_load_mw and f.min_load_mw and f.min_load_mw > 0:
            if f.peak_load_mw / f.min_load_mw >= LOAD_SWING_RATIO:
                out.append(FdFinding(
                    f"fd.swing.{name}", INFO, "نوسان فصلی بار",
                    f"فاصله آشکار میان حداکثر بار ({_num(f.peak_load_mw)} مگاوات) و حداقل بار "
                    f"({_num(f.min_load_mw)} مگاوات) {name} ماهیت فصلی و متغیر تغذیه این مسیر "
                    "را بازتاب می‌دهد و ضرورت توجه به رفتار بار در حالت‌های مختلف بهره‌برداری "
                    "را آشکار می‌کند.",
                    "نمونه ۱/۲ (بار 5.5 در برابر 2.3 مگاوات)"))
        if f.power_factor is not None:
            if f.power_factor < PF_LOW:
                out.append(FdFinding(
                    f"fd.pf.{name}", WARNING, "ضریب قدرت پایین",
                    f"ضریب قدرت {name} برابر {_num(f.power_factor)} و کمتر از {_num(PF_LOW)} است؛ "
                    "سهم توان راکتیو بر سطح ولتاژ و تلفات شبکه اثرگذار است و اصلاح آن "
                    "(خازن‌گذاری) باید بررسی شود.",
                    "نمونه ۲ (روند صعودی توان راکتیو در ماه‌های گرم)"))
            else:
                out.append(FdFinding(
                    f"fd.pf.{name}", INFO, "ضریب قدرت مناسب",
                    f"ضریب قدرت {name} برابر {_num(f.power_factor)} و در محدوده مناسب است.",
                    "نمونه ۲ (ضریب قدرت 0.92 «مقدار مناسبی است»)"))
    return out


# ---------------------------------------------------------------------------
# قواعد نیروگاه و اتوبوستر (مشترک پروژه)
# ---------------------------------------------------------------------------
def asset_findings(project: Project) -> list[FdFinding]:
    out: list[FdFinding] = []
    plants = list(getattr(project, "power_plants", []) or [])
    if getattr(project, "has_power_plants", "") == PRESENCE_YES and plants:
        solar_mw = sum((p.rated_mw or 0) for p in plants if p.kind == "solar")
        if solar_mw > 0:
            out.append(FdFinding(
                "fd.plants.solar", INFO, "امکان جریان معکوس توان",
                f"اتصال نیروگاه خورشیدی به ظرفیت مجموع {_num(solar_mw)} مگاوات می‌تواند در "
                "ساعات تولید، مقادیر منفی توان اکتیو (جریان معکوس توان) در پروفیل بار فیدر "
                "ایجاد کند؛ این رفتار باید در تفسیر نمودار پروفیل بار لحاظ شود.",
                "نمونه ۱/۲ (مقادیر منفی P به دلیل نیروگاه خورشیدی 6 مگاواتی)"))
        others = [p for p in plants if p.kind in ("chp", "gas", "thermal", "wind")]
        if others:
            names = "، ".join(f"{p.kind_label}"
                              + (f" ({_num(p.rated_mw)} مگاوات)" if p.rated_mw else "")
                              for p in others)
            out.append(FdFinding(
                "fd.plants.dispatch", INFO, "اثر نیروگاه بر پروفیل ولتاژ",
                f"حضور نیروگاه {names} در محدوده مطالعه بر پروفیل ولتاژ و جهت توان مؤثر است "
                "و باید در سناریوهای پخش بار قبل/بعد از اصلاح مدل شود.",
                "نمونه ۱ (نیروگاه CHP ۱٫۵ مگاواتی پس از انشعاب فرعی)"))
    ab = getattr(project, "autobooster", None)
    if ab is not None and ab.present == PRESENCE_YES:
        extra = f" با ظرفیت جریانی {_num(ab.current_a)} آمپر" if ab.current_a else ""
        count = f" (تعداد {int(ab.count)})" if ab.count else ""
        out.append(FdFinding(
            "fd.booster", INFO, "اثر اتوبوستر بر ولتاژ",
            f"حضور اتوبوستر{count}{extra} در وضعیت موجود فیدر لحاظ شده است؛ تپ اتوبوستر "
            "در سناریوهای پخش بار باید ثبت شود، زیرا تغییر ولتاژ پایین‌دست به آن وابسته است.",
            "نمونه ۱ (علت افزایش ولتاژ: اتوبوستر و CHP، تپ سوم در پیک بار)"))
    return out


# ---------------------------------------------------------------------------
# قواعد مقایسه قبل/بعد (پارامترهای کلی پخش بار)
# ---------------------------------------------------------------------------
_METRICS = (("حداقل ولتاژ شبکه", "min_voltage_kv_before", "min_voltage_kv_after", "کیلوولت", +1),
            ("تلفات توان", "losses_kw_before", "losses_kw_after", "کیلووات", -1),
            ("حداکثر بارگیری تجهیزات فیدر", "max_loading_pct_before", "max_loading_pct_after",
             "درصد", -1))


def metric_findings(info: FeederDevelopmentInfo) -> list[FdFinding]:
    """هر پارامتر: بدون تغییر / بهبود / افت — با مقدار و جهت درست مهندسی."""
    out: list[FdFinding] = []
    for label, kb, ka, unit, good_dir in _METRICS:
        vb, va = getattr(info, kb), getattr(info, ka)
        if vb is None or va is None:
            continue
        if va == vb:
            out.append(FdFinding(
                f"fd.metric.{kb}", INFO, f"{label}: بدون تغییر",
                f"{label} در مقدار {_num(vb)} {unit} ثابت مانده است.",
                "نمونه ۲ (هر سه پارامتر بدون تغییر)"))
            continue
        delta = va - vb
        improved = (delta > 0) if good_dir > 0 else (delta < 0)
        if improved:
            out.append(FdFinding(
                f"fd.metric.{kb}", INFO, f"{label}: بهبود",
                f"{label} از {_num(vb)} به {_num(va)} {unit} "
                f"{'افزایش' if delta > 0 else 'کاهش'} یافته است"
                + (f" (کاهش {_num(abs(delta))} {unit})." if good_dir < 0 else "."),
                "نمونه ۳ (کاهش ۹۳۹ کیلوواتی مجموع تلفات)"))
        else:
            out.append(FdFinding(
                f"fd.metric.{kb}", WARNING, f"{label}: افت شاخص",
                f"{label} از {_num(vb)} به {_num(va)} {unit} تغییر کرده و نسبت به حالت قبل "
                "بدتر شده است؛ علت باید در شرح طرح توجیه شود.",
                "قاعده جهت بهبود شاخص‌ها"))
    return out


# ---------------------------------------------------------------------------
# قواعد شینه‌های کاندید (جدول ۴ نمونه ۱)
# ---------------------------------------------------------------------------
def bus_findings(info: FeederDevelopmentInfo, nominal_kv: Optional[float] = None) -> list[FdFinding]:
    out: list[FdFinding] = []
    nominal = nominal_kv or _nominal_kv(info)
    for b in getattr(info, "candidate_buses", []) or []:
        name = b.name or "شینه کاندید"
        vb, va = b.voltage_kv_before, b.voltage_kv_after
        if vb is not None and va is not None:
            if va > vb:
                txt = (f"ولتاژ شینه «{name}» از {_num(vb)} به {_num(va)} کیلوولت رسیده است که "
                       "بیانگر بهبود وضعیت ولتاژ در این گره است.")
                sev = INFO
            elif va < vb:
                txt = (f"ولتاژ شینه «{name}» از {_num(vb)} به {_num(va)} کیلوولت کاهش یافته است؛ "
                       "اثر طرح بر این گره باید بررسی و توجیه شود.")
                sev = WARNING
            else:
                txt = f"ولتاژ شینه «{name}» در مقدار {_num(vb)} کیلوولت بدون تغییر مانده است."
                sev = INFO
            out.append(FdFinding(f"fd.bus.v.{name}", sev, f"ولتاژ شینه {name}", txt,
                                 "نمونه ۱ (جدول ۴: 19.64 ← 21.14 کیلوولت)"))
        # کنترل پریونیت نسبت به ولتاژ نامی
        if nominal:
            for tag, v in (("قبل", vb), ("بعد", va)):
                if v is None:
                    continue
                pu = v / nominal
                if pu < VOLT_LOW_PU:
                    out.append(FdFinding(
                        f"fd.bus.pu.{name}.{tag}", WARNING, "افت ولتاژ شینه",
                        f"ولتاژ شینه «{name}» در حالت {tag} برابر {pu:.3f} برابر ولتاژ نامی است "
                        f"و از حد {VOLT_LOW_PU:g} پایین‌تر است؛ وضعیت نامناسب پروفیل ولتاژ.",
                        "نمونه ۳ (حداقل ولتاژ 0.828 پریونیت «وضعیت نامناسب»)"))
                elif pu > VOLT_HIGH_PU:
                    out.append(FdFinding(
                        f"fd.bus.pu.{name}.{tag}", WARNING, "ولتاژ بالاتر از حد",
                        f"ولتاژ شینه «{name}» در حالت {tag} برابر {pu:.2f} برابر ولتاژ نامی است و "
                        f"از حد {VOLT_HIGH_PU:g} فراتر رفته است؛ تنظیم تپ اتوبوستر/ترانس و کنترل "
                        "ولتاژ در بار کم بررسی شود.",
                        "نمونه ۱ (1.06 برابر ولتاژ نامی پس از اصلاح)"))
        tb, ta = b.trafo_loading_pct_before, b.trafo_loading_pct_after
        if tb is not None and ta is not None and ta != tb:
            out.append(FdFinding(
                f"fd.bus.t.{name}", INFO, f"بارگیری ترانسفورماتور {name}",
                f"بارگیری ترانسفورماتور توزیع شینه «{name}» از {_num(tb)} به {_num(ta)} درصد "
                f"{'کاهش' if ta < tb else 'افزایش'} یافته است.",
                "نمونه ۱ (23.37 ← 21.86 درصد)"))
    return out


def _nominal_kv(info: FeederDevelopmentInfo) -> Optional[float]:
    for f in info.feeders or []:
        if f.voltage_kv:
            return f.voltage_kv
    return None


# ---------------------------------------------------------------------------
# قواعد کامل‌بودن داده (هشدارها)
# ---------------------------------------------------------------------------
def completeness_findings(info: FeederDevelopmentInfo) -> list[FdFinding]:
    out: list[FdFinding] = []
    pairs = [(kb, ka, label) for label, kb, ka, _u, _d in _METRICS]
    half = [label for kb, ka, label in pairs
            if (getattr(info, kb) is None) != (getattr(info, ka) is None)]
    if half:
        out.append(FdFinding(
            "fd.incomplete.metrics", WARNING, "نتایج پخش بار ناقص",
            "برای مقایسه قبل/بعد، هر دو مقدار این پارامترها لازم است: " + "، ".join(half) + ".",
            "ساختار جدول ۴ نمونه‌ها"))
    for b in getattr(info, "candidate_buses", []) or []:
        if b.name and (b.voltage_kv_before is None) != (b.voltage_kv_after is None):
            out.append(FdFinding(
                f"fd.incomplete.bus.{b.name}", WARNING, "شینه کاندید ناقص",
                f"برای شینه «{b.name}» فقط یکی از مقادیر ولتاژ قبل/بعد ثبت شده است.",
                "ساختار جدول ۴ نمونه ۱"))
    return out


# ---------------------------------------------------------------------------
# ارزیابی کامل + متن‌های خودکار گزارش
# ---------------------------------------------------------------------------
def evaluate(project: Project) -> list[FdFinding]:
    """اجرای همه قواعد روی پروژه؛ خروجی برای تحلیل، گزارش و بازبینی مهندس."""
    info = getattr(project, "feeder_dev", None)
    if info is None:
        return []
    out: list[FdFinding] = []
    out.extend(feeder_findings(info))
    out.extend(asset_findings(project))
    out.extend(metric_findings(info))
    out.extend(bus_findings(info))
    out.extend(completeness_findings(info))
    return out


def network_paragraphs(project: Project) -> list[str]:
    """جمله‌های تحلیلی فصل «مشخصات شبکه و وضعیت موجود» (داده‌محور)."""
    info = getattr(project, "feeder_dev", None)
    if info is None:
        return []
    return [f.text for f in feeder_findings(info) + asset_findings(project)]


def after_paragraphs(project: Project) -> list[str]:
    """جمله‌های تحلیلی فصل «پخش بار بعد از اصلاح» (شینه‌های کاندید)."""
    info = getattr(project, "feeder_dev", None)
    if info is None:
        return []
    return [f.text for f in bus_findings(info) if f.severity == INFO or "کاهش یافته" in f.text]


def conclusion_paragraph(project: Project) -> str:
    """نتیجه‌گیری خودکار به سبک نمونه‌ها — فقط از مقادیر ثبت‌شده.

    * همه پارامترها بدون تغییر → ادبیات نمونه ۲ («ثابت مانده... اثر منفی ندارد»).
    * دست‌کم یک بهبود → ادبیات نمونه ۳ (کمی‌سازی بهبود).
    * افت شاخص → صراحتاً اعلام و ارجاع به توجیه طرح.
    """
    info = getattr(project, "feeder_dev", None)
    if info is None:
        return ""
    ms = metric_findings(info)
    if not ms:
        return ""
    unchanged = [m for m in ms if "ثابت مانده" in m.text]
    worse = [m for m in ms if m.severity == WARNING]
    improved = [m for m in ms if m not in unchanged and m not in worse]
    parts: list[str] = ["بر اساس نتایج پخش بار ثبت‌شده، پس از اجرای طرح پیشنهادی "]
    if unchanged and not improved and not worse:
        parts = ["بر اساس نتایج پخش بار ثبت‌شده، پس از اجرای طرح پیشنهادی پارامترهای "
                 "پخش بار فیدر تغییر نکرده‌اند؛ به‌طوری که "
                 + "، ".join(m.text.rstrip("؛.") for m in unchanged)
                 + ". بر همین اساس، اجرای طرح اثر منفی بر شاخص‌های بهره‌برداری شبکه "
                   "(ولتاژ، تلفات و بارگیری) ندارد و توجیه اصلی اجرای آن باید ملاک "
                   "جمع‌بندی قرار گیرد."]
    else:
        seg = []
        if improved:
            seg.append("، ".join(m.text.rstrip("؛.") for m in improved))
        if unchanged:
            seg.append("، ".join(m.text.rstrip("؛.") for m in unchanged))
        if worse:
            seg.append("، ".join(m.text.rstrip("؛.") for m in worse))
        parts.append("؛ ".join(seg) + ".")
        if worse:
            parts.append(" افت شاخص‌های یادشده باید در شرح طرح توجیه شود.")
    bus_txts = [f.text.rstrip("؛.") for f in bus_findings(info)
                if f.key.startswith("fd.bus.v.") and "بهبود" in f.text]
    if bus_txts:
        parts.append(" همچنین " + "؛ ".join(bus_txts) + ".")
    parts.append(" تصمیم نهایی دربارهٔ اجرای طرح با مهندس مطالعه است.")
    return "".join(parts)
