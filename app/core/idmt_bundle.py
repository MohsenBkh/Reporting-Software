# -*- coding: utf-8 -*-
"""پیوند با نرم‌افزار «هماهنگی حفاظت فیدر — IDMT Coordination» (نسخه ۰۸).

کاربر داده‌های مطالعه ریکلوزر/سکشنالایزر را یک‌بار در ابزار IDMT وارد می‌کند و
با دکمه «خروجی گزارش‌ساز» یک بسته JSON صادر می‌شود که شامل:

* ``project``  — ورودی‌های خام مطالعه (schema 8 خود ابزار)؛
* ``resolved`` — تنظیمات نهایی فاز/زمین ریکلوزر، سرخط و سکشنالایزرها + توالی
  (Shot/Dead/Reclaim/Counter) پس از اعمال قواعد TAV111-02/00؛
* ``charts``   — نمودارهای TCC فاز/زمین، نمودار توالی عملکرد (ولتاژ/جریان/شمارنده)
  و برگه تنظیمات A4 به‌صورت PNG با انکد base64.

این ماژول بسته را می‌خواند، تنظیمات را روی مدل داده ReportForge می‌نشاند و
تصاویر را به بخش‌های گزارش نسبت می‌دهد:

* TCC فاز/زمین          → بخش «هماهنگی حفاظتی» (``prot_coordination``)
* توالی و شمارنده        → بخش «سناریوی عملکرد» (``prot_scenario``)
* برگه تنظیمات A4        → پیوست جدید «برگه تنظیمات» (``prot_settings_sheet``)

هیچ مقدار مهندسی در این ماژول «ساخته» نمی‌شود؛ فقط خروجی محاسبات خود ابزار
IDMT منتقل می‌شود. نبود داده = ``None``.
"""
from __future__ import annotations

import base64
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.core.protection_models import (FunctionSetting, ProtectionSettings,
                                        TIME_UNIT_MS, TIME_UNIT_PERCENT,
                                        TIME_UNIT_S)

BUNDLE_KIND = "idmt-reportforge-bundle"
IDMT_TITLE_PREFIX = "IDMT — "          # شناسه تصاویر واردشده (برای واردکردن مجدد)

# نگاشت نمودارهای بسته → (نوع شکل، بخش گزارش، عنوان/کپشن، ترتیب)
CHART_PLACEMENTS: list[tuple[str, str, str, str, int]] = [
    ("tcc_phase", "tcc", "prot_coordination",
     "منحنی هماهنگی جریان–زمان (TCC) — حفاظت اضافه‌جریان فاز (۵۰/۵۱)", 10),
    ("tcc_earth", "tcc", "prot_coordination",
     "منحنی هماهنگی جریان–زمان (TCC) — حفاظت ارت‌فالت (۵۰N/۵۱N)", 11),
    ("sequence_phase", "sequence", "prot_scenario",
     "توالی عملکرد و شمارنده — خطای فاز (ولتاژ، جریان و وضعیت کلیدها)", 10),
    ("sequence_earth", "sequence", "prot_scenario",
     "توالی عملکرد و شمارنده — خطای زمین (ولتاژ، جریان و وضعیت کلیدها)", 11),
    ("sheet", "settings_sheet", "prot_settings_sheet",
     "برگه تنظیمات نهایی هماهنگی حفاظتی فاز و زمین (خروجی IDMT)", 10),
]


class IdmtBundleError(ValueError):
    """فایل انتخابی بسته معتبر IDMT نیست."""


@dataclass
class IdmtImportResult:
    """خلاصه نتیجه ورود بسته — برای نمایش به کاربر."""
    applied: list[str] = field(default_factory=list)      # چه داده‌هایی نشانده شد
    warnings: list[str] = field(default_factory=list)     # هشدارها (ناقص/چندتایی و ...)
    images: list[str] = field(default_factory=list)       # عنوان تصاویر واردشده
    failures: list[str] = field(default_factory=list)     # قواعد ناموفق خود IDMT

    @property
    def summary(self) -> str:
        parts = [f"{len(self.applied)} گروه داده", f"{len(self.images)} تصویر"]
        if self.failures:
            parts.append(f"{len(self.failures)} قاعده ناموفق IDMT")
        return "، ".join(parts)


# ---------------------------------------------------------------------------
# خواندن بسته
# ---------------------------------------------------------------------------
def load_bundle(path: str | Path) -> dict:
    """خواندن و اعتبارسنجی فایل بسته (یا پروژه خام IDMT)."""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        raise IdmtBundleError(f"فایل JSON خوانده نشد: {exc}") from exc
    if not isinstance(data, dict):
        raise IdmtBundleError("ساختار فایل، بسته IDMT نیست.")
    if data.get("kind") == BUNDLE_KIND:
        if not isinstance(data.get("project"), dict):
            raise IdmtBundleError("بسته IDMT فاقد بخش project است.")
        return data
    # فایل «خروجی JSON» خود ابزار (فقط ورودی‌ها؛ بدون تنظیمات نهایی و نمودار)
    if data.get("schema") in (7, 8) and isinstance(data.get("inputs"), dict):
        return {"kind": BUNDLE_KIND, "project": data, "resolved": None, "charts": {}}
    raise IdmtBundleError(
        "فایل انتخابی بسته گزارش‌ساز نیست. در ابزار IDMT از دکمه «خروجی گزارش‌ساز» استفاده کنید.")


def _num(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None           # NaN → None


def _fmt(v: Optional[float]) -> str:
    return f"{v:g}" if v is not None else "—"


# ---------------------------------------------------------------------------
# نگاشت تنظیمات یک تجهیز (dict خروجی IDMT → ProtectionSettings)
# ---------------------------------------------------------------------------
def _function_from(settings: Optional[dict]) -> tuple[FunctionSetting, FunctionSetting]:
    """تنظیمات یک mode (فاز یا زمین) → (تابع تأخیری، تابع آنی)."""
    s = settings or {}
    delayed = FunctionSetting()
    pickup = _num(s.get("pickup"))
    if pickup is not None:
        delayed.pickup_a = pickup
    if s.get("delayMode") == "DT":
        delayed.curve = "DT"
        dt = _num(s.get("dt"))
        if dt is not None:
            delayed.time_value, delayed.time_unit = dt, TIME_UNIT_S
    else:
        delayed.curve = str(s.get("curve") or "")
        tms = _num(s.get("tms"))
        if tms is not None:                 # ضریب TMS ابزار → درصد (قرارداد گزارش‌ساز)
            delayed.time_value = round(tms * 100.0, 6)
            delayed.time_unit = TIME_UNIT_PERCENT
    instant = FunctionSetting()
    if s.get("instEnabled"):
        ip = _num(s.get("instPickup"))
        it = _num(s.get("instTime"))
        if ip is not None:
            instant.pickup_a = ip
        if it is not None:                  # ثانیه → میلی‌ثانیه
            instant.time_value, instant.time_unit = round(it * 1000.0, 6), TIME_UNIT_MS
    return delayed, instant


def _protection_settings(phase: Optional[dict], earth: Optional[dict],
                         note: str = "") -> ProtectionSettings:
    ps = ProtectionSettings()
    ps.f51, ps.f50 = _function_from(phase)
    ps.f51n, ps.f50n = _function_from(earth)
    if note:
        ps.note = note
    return ps


# ---------------------------------------------------------------------------
# اعمال بسته روی پروژه
# ---------------------------------------------------------------------------
def apply_bundle_to_project(project, bundle: dict) -> IdmtImportResult:
    """نشاندن داده‌های بسته روی ``Project`` (ریکلوزر + سکشنالایزر + سرخط).

    تصاویر جداگانه با :func:`import_bundle_images` وارد می‌شوند (نیازمند
    ``ProjectManager``). مقادیر موجود در بسته جایگزین مقادیر قبلی می‌شوند؛
    داده‌هایی که در بسته نیستند دست‌نخورده می‌مانند.
    """
    res = IdmtImportResult()
    src = bundle.get("project") or {}
    resolved = bundle.get("resolved")
    meta = src.get("meta") or {}
    inputs = src.get("inputs") or {}
    in_phase, in_earth = inputs.get("phase") or {}, inputs.get("earth") or {}
    system = src.get("system") or {}
    note = _source_note(bundle)

    # --- مشخصات مشترک مطالعه -------------------------------------------
    feeder = str(meta.get("feeder") or "").strip()
    title = str(meta.get("title") or "").strip()
    if title and not (project.name or "").strip():
        project.name = title
    voltage = _num(system.get("voltage"))
    fault_max_ka = _div(_num(in_phase.get("faultMax")), 1000.0)
    fault_min_ka = _div(_num(in_phase.get("faultMin")), 1000.0)
    load_a = _num(in_phase.get("load"))
    ct_primary = _num(in_phase.get("ct"))

    rec = project.recloser
    if feeder:
        rec.feeder_name = feeder
    if voltage is not None:
        rec.nominal_voltage_kv = voltage
    if fault_max_ka is not None:
        rec.fault_current_ka = fault_max_ka
    if fault_min_ka is not None:
        rec.min_fault_current_ka = fault_min_ka
    if load_a is not None:
        rec.load_current_a = load_a
    res.applied.append("مشخصات مطالعه (فیدر، ولتاژ، جریان‌های خطا و بار)")

    if resolved is None:
        res.warnings.append(
            "فایل انتخابی فقط ورودی‌های خام IDMT بود؛ برای انتقال تنظیمات نهایی و "
            "نمودارها از دکمه «خروجی گزارش‌ساز» ابزار استفاده کنید.")
        return res

    r_phase, r_earth = resolved.get("phase") or {}, resolved.get("earth") or {}
    cycle = resolved.get("cycle") or {}

    # --- ریکلوزر: توابع ۵۱/۵۰/۵۱N/۵۰N + چرخه وصل مجدد --------------------
    rec.settings = _protection_settings(r_phase.get("rec"), r_earth.get("rec"), note)
    if ct_primary is not None:
        rec.settings.ct_ratio = _fmt(ct_primary)
    shots = _num(cycle.get("shots"))
    if shots is not None:
        rec.settings.shots = int(shots)
    reclaim = _num(cycle.get("reclaim"))
    if reclaim is not None:
        rec.settings.reclaim_time_s = reclaim
    dead = [_num(x) for x in (cycle.get("deadTimes") or [])]
    if dead and all(d is not None for d in dead):
        rec.settings.dead_times_s = [float(d) for d in dead]
    f51 = rec.settings.f51
    if f51.pickup_a is not None:
        rec.pickup_current_a = f51.pickup_a
    res.applied.append("تنظیمات نهایی ریکلوزر (۵۱/۵۰/۵۱N/۵۰N + Shot/Dead/Reclaim)")

    # --- رله سرخط (بالادست) ---------------------------------------------
    head_ps = _protection_settings(r_phase.get("head"), r_earth.get("head"), note)
    if head_ps.any_function_set():
        rec.upstream_settings = head_ps
        if not (rec.upstream_device or "").strip():
            rec.upstream_device = "رله سر خط فیدر"
        res.applied.append("تنظیمات رله سرخط (مرجع هماهنگی)")

    # --- سکشنالایزر (اولین تجهیز بسته) ------------------------------------
    p_secs = r_phase.get("sections") or []
    e_secs = r_earth.get("sections") or []
    c_secs = cycle.get("sections") or []
    if p_secs or e_secs:
        if len(p_secs) > 1:
            res.warnings.append(
                f"بسته شامل {len(p_secs)} سکشنالایزر است؛ فقط تجهیز اول به مدل "
                "گزارش‌ساز منتقل شد.")
        sp = p_secs[0] if p_secs else {}
        se = e_secs[0] if e_secs else {}
        sc = c_secs[0] if c_secs else {}
        secz = project.sectionalizer
        name = str(sp.get("name") or sp.get("id") or "").strip()
        if name:
            secz.name = name
        if feeder:
            secz.feeder_name = feeder
        if voltage is not None:
            secz.nominal_voltage_kv = voltage
        if fault_max_ka is not None:
            secz.fault_current_ka = fault_max_ka
        if fault_min_ka is not None:
            secz.min_fault_current_ka = fault_min_ka
        s_load = _num(sp.get("load"))
        if s_load is not None:
            secz.load_current_a = s_load
        secz.settings = _protection_settings(sp.get("settings"), se.get("settings"), note)
        s_ct = _num(sp.get("ct"))
        if s_ct is not None:
            secz.settings.ct_ratio = _fmt(s_ct)
        ctrl = sc.get("settings") or {}
        counter = _num(ctrl.get("counter"))
        if counter is not None:
            secz.settings.counter = int(counter)
        dead_i = _num(ctrl.get("deadI"))
        if dead_i is not None and s_ct:
            secz.settings.dead_line_current_pct = round(dead_i / s_ct * 100.0, 3)
        dead_u = _num(ctrl.get("deadU"))
        if dead_u is not None and voltage:
            secz.settings.dead_line_voltage_pct = round(dead_u / voltage * 100.0, 3)
        sf51 = secz.settings.f51
        if sf51.pickup_a is not None:
            secz.pickup_current_a = sf51.pickup_a
        secz.link_to_project_recloser = True
        res.applied.append("تنظیمات نهایی سکشنالایزر (توابع + Counter + Dead line)")

    # --- قواعد ناموفق خود IDMT — برای اطلاع مهندس -------------------------
    for f in resolved.get("failures") or []:
        title_f = str(f.get("title") or f.get("id") or "قاعده")
        res.failures.append(f"{title_f} (هدف: {f.get('target')} — مقدار: {f.get('actual')})")
    if res.failures:
        res.warnings.append(
            "ابزار IDMT برای برخی قواعد وضعیت «ناموفق» گزارش کرده است؛ پیش از تولید "
            "گزارش، تنظیمات را در خود ابزار بازبینی کنید.")
    return res


def _div(v: Optional[float], by: float) -> Optional[float]:
    return None if v is None else v / by


def _source_note(bundle: dict) -> str:
    ver = bundle.get("version") or ""
    when = str(bundle.get("exportedAt") or "")[:10]
    note = f"منبع تنظیمات: IDMT Coordination نسخه {ver}".strip()
    if when:
        note += f" — خروجی {when}"
    return note


# ---------------------------------------------------------------------------
# ورود تصاویر بسته به پروژه
# ---------------------------------------------------------------------------
def import_bundle_images(manager, bundle: dict,
                         result: Optional[IdmtImportResult] = None) -> IdmtImportResult:
    """ذخیره نمودارهای بسته به‌عنوان شکل‌های پروژه (با جایگزینی ورود قبلی)."""
    res = result or IdmtImportResult()
    charts = bundle.get("charts") or {}
    if not any(charts.values()):
        res.warnings.append("بسته فاقد نمودار بود؛ شکل‌های TCC/توالی/برگه وارد نشدند.")
        return res
    project = getattr(manager, "project", None)
    if project is None:
        res.warnings.append("پروژه‌ای باز نیست؛ تصاویر وارد نشدند.")
        return res
    # حذف تصاویر ورود قبلی IDMT (واردکردن مجدد = جایگزینی، نه تکرار)
    stale = [img for img in project.images
             if (img.title or "").startswith(IDMT_TITLE_PREFIX)]
    for img in stale:
        manager.remove_image(img.uid)
    with tempfile.TemporaryDirectory(prefix="idmt_charts_") as tmp:
        for key, kind, section_key, caption, order in CHART_PLACEMENTS:
            b64 = charts.get(key)
            if not b64:
                continue
            try:
                raw = base64.b64decode(b64)
            except Exception:  # noqa: BLE001
                res.warnings.append(f"تصویر «{key}» بسته قابل خواندن نبود.")
                continue
            tmp_file = Path(tmp) / f"{key}.png"
            tmp_file.write_bytes(raw)
            title = IDMT_TITLE_PREFIX + caption
            if manager.import_image(tmp_file, title=title, kind=kind,
                                    section_key=section_key, order=order,
                                    caption=caption):
                res.images.append(title)
    return res


def import_idmt_file(manager, path: str | Path) -> IdmtImportResult:
    """ورود کامل: فایل → داده‌ها + تصاویر. خطاها به IdmtBundleError تبدیل می‌شوند."""
    bundle = load_bundle(path)
    project = getattr(manager, "project", None)
    if project is None:
        raise IdmtBundleError("ابتدا یک پروژه باز یا ایجاد کنید.")
    res = apply_bundle_to_project(project, bundle)
    import_bundle_images(manager, bundle, res)
    manager.dirty = True
    return res
