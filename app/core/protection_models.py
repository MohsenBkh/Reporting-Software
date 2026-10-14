# -*- coding: utf-8 -*-
"""مدل داده تنظیمات حفاظتی — مشترک بین ریکلوزر، سکشنالایزر و رله‌های بالادست.

* هیچ مقدار پیش‌فرض مهندسی ندارد: نبود داده = ``None`` (نه صفر).
* وابسته به ``app.core.models`` نیست تا ایمپورت چرخه‌ای ایجاد نشود؛ ``models.py``
  این ماژول را ایمپورت می‌کند.
* ساختار بر اساس جداول تنظیمات دفترچه‌های نمونه (۵۱ / ۵۰ / ۵۱N / ۵۰N، Shot،
  Dead time، Reclaim time، Counter، Dead line) طراحی شده است.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Optional

FUNCTION_KEYS = ("f51", "f50", "f51n", "f50n")
FUNCTION_LABELS_FA = {
    "f51": "جریان زیاد تأخیری فاز (۵۱)",
    "f50": "جریان زیاد لحظه‌ای فاز (۵۰)",
    "f51n": "جریان زیاد تأخیری زمین (۵۱N)",
    "f50n": "جریان زیاد لحظه‌ای زمین (۵۰N)",
}
TIME_UNIT_PERCENT = "percent"   # TMS بر حسب درصد (مثلاً 7.5%)
TIME_UNIT_MS = "ms"             # زمان ثابت (مثلاً 120ms)
TIME_UNIT_S = "s"
TIME_UNIT_LABELS = {TIME_UNIT_PERCENT: "%", TIME_UNIT_MS: "ms", TIME_UNIT_S: "s", "": ""}


@dataclass
class FunctionSetting:
    """تنظیم یک تابع حفاظتی."""

    curve: str = ""                          # مثلاً NI
    pickup_a: Optional[float] = None         # Pickup (A اولیه)
    time_value: Optional[float] = None       # TMS یا زمان
    time_unit: str = ""                      # percent | ms | s

    def is_set(self) -> bool:
        return self.pickup_a is not None

    def time_text(self) -> str:
        if self.time_value is None:
            return "ناموجود"
        unit = TIME_UNIT_LABELS.get(self.time_unit, self.time_unit)
        return f"{_num(self.time_value)}{unit}"


@dataclass
class ProtectionSettings:
    """مجموعه تنظیمات یک تجهیز حفاظتی."""

    f51: FunctionSetting = field(default_factory=FunctionSetting)
    f50: FunctionSetting = field(default_factory=FunctionSetting)
    f51n: FunctionSetting = field(default_factory=FunctionSetting)
    f50n: FunctionSetting = field(default_factory=FunctionSetting)
    shots: Optional[int] = None                       # تعداد Shot (ریکلوزر)
    dead_times_s: list[float] = field(default_factory=list)
    reclaim_time_s: Optional[float] = None
    counter: Optional[int] = None                     # شمارنده (سکشنالایزر)
    dead_line_current_pct: Optional[float] = None     # % جریان نامی
    dead_line_voltage_pct: Optional[float] = None     # % ولتاژ نامی
    ct_ratio: str = ""
    note: str = ""

    def function(self, key: str) -> FunctionSetting:
        return getattr(self, key)

    def functions(self) -> dict[str, FunctionSetting]:
        return {k: getattr(self, k) for k in FUNCTION_KEYS}

    def any_function_set(self) -> bool:
        return any(f.is_set() for f in self.functions().values())

    def is_empty(self) -> bool:
        """آیا هیچ دادهٔ واقعی ثبت نشده است؟

        نام منحنی و واحد زمان به‌تنهایی «داده» نیستند (پیش‌فرض‌های رابط کاربری:
        منحنی NI و TMS درصدی)؛ تنها مقادیر عددی/متنی ثبت‌شده ملاک‌اند.
        """
        if any(f.pickup_a is not None or f.time_value is not None
               for f in self.functions().values()):
            return False
        return not (self.shots is not None or self.dead_times_s
                    or self.reclaim_time_s is not None or self.counter is not None
                    or self.dead_line_current_pct is not None
                    or self.dead_line_voltage_pct is not None
                    or self.ct_ratio.strip() or self.note.strip())

    # --- سریال‌سازی ------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "ProtectionSettings":
        data = data or {}
        obj = cls()
        for key in FUNCTION_KEYS:
            raw = data.get(key)
            if isinstance(raw, dict):
                known = {f.name for f in dataclasses.fields(FunctionSetting)}
                setattr(obj, key, FunctionSetting(**{k: v for k, v in raw.items() if k in known}))
        for key in ("shots", "reclaim_time_s", "counter", "dead_line_current_pct",
                    "dead_line_voltage_pct", "ct_ratio", "note"):
            if key in data:
                setattr(obj, key, data[key])
        if isinstance(data.get("dead_times_s"), list):
            obj.dead_times_s = list(data["dead_times_s"])
        return obj


def _num(v: float) -> str:
    return f"{v:g}"
