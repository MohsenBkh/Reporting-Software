# -*- coding: utf-8 -*-
"""محاسبات منحنی جریان–زمان (TCC) رله‌های جریانی — IEC 60255-151.

پیش‌فرض‌های نرم‌افزار (مطابق دفترچه‌های نمونه):
    * نوع منحنی پیش‌فرض: NI (Normal Inverse)
    * جریان بر حسب آمپر (A)
    * TMS بر حسب درصد (مثلاً TMS = 5% یعنی ضریب 0.05)

منحنی‌های پشتیبانی‌شده (ثابت‌های استاندارد IEC):

    t(I) = TMS × k / ((I / Ipickup)^α − 1)

    NI (Normal Inverse)    : k = 0.14 ، α = 0.02
    VI (Very Inverse)      : k = 13.5 ، α = 1.0
    EI (Extremely Inverse) : k = 80.0 ، α = 2.0

این ماژول عمداً از Qt و matplotlib مستقل است تا هم موتور قواعد (Rule Engine)
و هم مولد نمودار (chart_generator) از یک منبع واحد محاسبه استفاده کنند.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.protection_models import (FunctionSetting, ProtectionSettings,
                                        TIME_UNIT_MS, TIME_UNIT_PERCENT, TIME_UNIT_S)

#: نوع منحنی پیش‌فرض رله‌های جریانی
DEFAULT_CURVE = "NI"

#: ثابت‌های استاندارد IEC 60255 — نام منحنی ← (k, α)
IEC_CURVES: dict[str, tuple[float, float]] = {
    "NI": (0.14, 0.02),     # Normal Inverse
    "VI": (13.5, 1.0),      # Very Inverse
    "EI": (80.0, 2.0),      # Extremely Inverse
}

CURVE_LABELS_FA = {
    "NI": "استاندارد معکوس (NI)",
    "VI": "بسیار معکوس (VI)",
    "EI": "فوق‌معکوس (EI)",
}

_ALIASES = {
    "NI": "NI", "N.I": "NI", "SI": "NI", "NORMAL INVERSE": "NI", "NORMALINVERSE": "NI",
    "STANDARD INVERSE": "NI", "IEC NI": "NI", "IEC-NI": "NI",
    "VI": "VI", "V.I": "VI", "VERY INVERSE": "VI", "VERYINVERSE": "VI", "IEC VI": "VI",
    "EI": "EI", "E.I": "EI", "EXTREMELY INVERSE": "EI", "EXTREMELYINVERSE": "EI",
    "IEC EI": "EI",
}


def normalize_curve(name: Optional[str]) -> Optional[str]:
    """نام منحنی کاربر → کلید استاندارد (NI/VI/EI)؛ ناشناخته = ``None``.

    رشتهٔ خالی (ثبت‌نشده) به منحنی پیش‌فرض ``NI`` نگاشت می‌شود.
    """
    t = (name or "").strip().upper().replace("‌", "")
    if not t:
        return DEFAULT_CURVE
    return _ALIASES.get(t)


def tms_factor(time_value: Optional[float], time_unit: str) -> Optional[float]:
    """مقدار TMS ثبت‌شده → ضریب بدون واحد (پیش‌فرض ورودی: درصد).

    * واحد ``percent`` یا خالی: مقدار ÷ ۱۰۰ (مثلاً 5% → 0.05)
    * واحد ``s``: مقدار همان ضریب TMS فرض می‌شود (ورود مستقیم ضریب)
    * واحد ``ms``: زمان ثابت است، نه TMS → ``None``
    """
    if time_value is None:
        return None
    if time_unit in ("", TIME_UNIT_PERCENT):
        return time_value / 100.0
    if time_unit == TIME_UNIT_S:
        return time_value
    return None


def trip_time(current_a: float, pickup_a: float, tms: float,
              curve: str = DEFAULT_CURVE) -> Optional[float]:
    """زمان عملکرد (ثانیه) تابع تأخیری در جریان ``current_a``.

    برای جریان کمتر یا مساوی Pickup (رله تحریک نمی‌شود) ``None`` برمی‌گردد.
    """
    const = IEC_CURVES.get(curve or DEFAULT_CURVE)
    if const is None or pickup_a <= 0 or tms is None or current_a <= pickup_a:
        return None
    k, alpha = const
    m = current_a / pickup_a
    try:
        return tms * k / (m ** alpha - 1.0)
    except (OverflowError, ZeroDivisionError):
        return None


@dataclass
class RelayCurve:
    """منحنی یک تابع جریانی یک تجهیز (برای رسم/مقایسه).

    * تابع تأخیری (۵۱/۵۱N): ``tms`` و ``curve`` معتبر است.
    * تابع آنی (۵۰/۵۰N): ``fixed_time_s`` (زمان ثابت) معتبر است.
    """

    device: str                      # نام تجهیز (رله سر خط / ریکلوزر / سکشنالایزر)
    function: str                    # برچسب تابع (۵۱، ۵۰، ۵۱N، ۵۰N)
    pickup_a: float
    tms: Optional[float] = None      # ضریب بدون واحد (نه درصد)
    curve: str = DEFAULT_CURVE
    fixed_time_s: Optional[float] = None

    @property
    def is_inverse(self) -> bool:
        return self.fixed_time_s is None

    def time_at(self, current_a: float) -> Optional[float]:
        if self.fixed_time_s is not None:
            return self.fixed_time_s if current_a > self.pickup_a else None
        if self.tms is None:
            return None
        return trip_time(current_a, self.pickup_a, self.tms, self.curve)


def delayed_curve(device: str, label: str, f: FunctionSetting) -> Optional[RelayCurve]:
    """``FunctionSetting`` تابع تأخیری → ``RelayCurve``؛ دادهٔ ناکافی = ``None``."""
    if f is None or f.pickup_a is None or f.pickup_a <= 0:
        return None
    curve = normalize_curve(f.curve)
    tms = tms_factor(f.time_value, f.time_unit)
    if f.time_unit == TIME_UNIT_MS and f.time_value is not None:
        # کاربر زمان ثابت ثبت کرده است (رفتار Definite Time)
        return RelayCurve(device, label, f.pickup_a, fixed_time_s=f.time_value / 1000.0)
    if curve is None or tms is None:
        return None
    return RelayCurve(device, label, f.pickup_a, tms=tms, curve=curve)


def instant_curve(device: str, label: str, f: FunctionSetting) -> Optional[RelayCurve]:
    """``FunctionSetting`` تابع آنی (۵۰/۵۰N) → ``RelayCurve`` زمان‌ثابت."""
    if f is None or f.pickup_a is None or f.pickup_a <= 0:
        return None
    if f.time_value is None:
        t = 0.0                                # آنی بدون تأخیر ثبت‌شده
    elif f.time_unit == TIME_UNIT_MS:
        t = f.time_value / 1000.0
    elif f.time_unit == TIME_UNIT_S:
        t = f.time_value
    else:                                      # درصد برای تابع آنی معنا ندارد
        t = f.time_value / 1000.0
    return RelayCurve(device, label, f.pickup_a, fixed_time_s=t)


def device_curves(device: str, settings: ProtectionSettings,
                  group: str = "phase") -> list[RelayCurve]:
    """منحنی‌های یک تجهیز برای گروه ``phase`` (۵۱/۵۰) یا ``ground`` (۵۱N/۵۰N)."""
    out: list[RelayCurve] = []
    if settings is None:
        return out
    if group == "phase":
        pairs = (("۵۱", settings.f51, delayed_curve), ("۵۰", settings.f50, instant_curve))
    else:
        pairs = (("۵۱N", settings.f51n, delayed_curve), ("۵۰N", settings.f50n, instant_curve))
    for label, f, make in pairs:
        c = make(device, label, f)
        if c is not None:
            out.append(c)
    return out


def coordination_ok(down: RelayCurve, up: RelayCurve,
                    currents: list[float]) -> Optional[bool]:
    """آیا منحنی تجهیز پایین‌دست در جریان‌های دادهشده زیر منحنی بالادست است؟

    فقط نقاطی مقایسه می‌شوند که هر دو رله عمل می‌کنند؛ اگر هیچ نقطهٔ مشترکی
    نباشد ``None`` (غیرقابل‌قضاوت) برمی‌گردد.
    """
    seen = False
    for i in currents:
        td, tu = down.time_at(i), up.time_at(i)
        if td is None or tu is None:
            continue
        seen = True
        if td >= tu:
            return False
    return True if seen else None
