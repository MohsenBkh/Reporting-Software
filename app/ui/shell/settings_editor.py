# -*- coding: utf-8 -*-
"""ویرایشگر تنظیمات حفاظتی (۵۱/۵۰/۵۱N/۵۰N + چرخه وصل مجدد) — فیلد اختیاری، نه صفر."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGridLayout, QLabel, QLineEdit,
                               QWidget)

from app.core.protection_models import (FUNCTION_KEYS, FUNCTION_LABELS_FA, FunctionSetting,
                                        ProtectionSettings, TIME_UNIT_MS, TIME_UNIT_PERCENT,
                                        TIME_UNIT_S)
from app.core.tcc import DEFAULT_CURVE, IEC_CURVES

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٫٬،", "0123456789..,")
UNITS = [("", "—"), (TIME_UNIT_PERCENT, "%"), (TIME_UNIT_MS, "ms"), (TIME_UNIT_S, "s")]
#: توابع تأخیری: منحنی پیش‌فرض NI و TMS بر حسب درصد؛ توابع آنی: زمان ثابت (ms)
DELAYED_KEYS = ("f51", "f51n")
CURVE_CHOICES = list(IEC_CURVES)      # NI / VI / EI


def parse_optional_float(text: str) -> Optional[float]:
    """متن → عدد؛ خالی یا نامعتبر = None (هیچ‌وقت صفر)."""
    t = (text or "").translate(_FA_DIGITS).replace(",", "").strip()
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


class OptionalNumberEdit(QLineEdit):
    """فیلد عددی اختیاری؛ ورودی نامعتبر با property ``invalid`` علامت می‌خورد."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("—")
        self.setLayoutDirection(Qt.LeftToRight)
        self.setAlignment(Qt.AlignRight)
        self.setValidator(QDoubleValidator(-1e9, 1e9, 4, self))
        self.textChanged.connect(self._flag)

    def _flag(self, text: str) -> None:
        bad = bool(text.strip()) and parse_optional_float(text) is None
        self.setProperty("invalid", bad)
        self.style().unpolish(self)
        self.style().polish(self)

    def value(self) -> Optional[float]:
        return parse_optional_float(self.text())

    def set_value(self, v: Optional[float]) -> None:
        self.setText("" if v is None else f"{v:g}")


class ProtectionSettingsEditor(QWidget):
    """جدول توابع حفاظتی + پارامترهای وصل مجدد؛ خواندن/نوشتن ``ProtectionSettings``."""

    changed = Signal()

    def __init__(self, *, reclosing: bool, counter: bool, parent=None) -> None:
        super().__init__(parent)
        self._rows: dict[str, tuple] = {}
        grid = QGridLayout(self)
        for col, head in enumerate(("تابع", "منحنی", "TMS / زمان", "واحد", "Pickup (A)")):
            h = QLabel(head)
            h.setObjectName("SectionTitle")
            grid.addWidget(h, 0, col)
        self._order: list[QWidget] = []
        for r, key in enumerate(FUNCTION_KEYS, start=1):
            delayed = key in DELAYED_KEYS
            curve = QComboBox()
            curve.setEditable(True)
            if not delayed:
                curve.addItem("")                      # توابع آنی: منحنی ندارند
            for name in CURVE_CHOICES:                 # NI (پیش‌فرض) / VI / EI
                curve.addItem(name)
            curve.lineEdit().setPlaceholderText(DEFAULT_CURVE if delayed else "—")
            time_ = OptionalNumberEdit()
            unit = QComboBox()
            for code, label in UNITS:
                unit.addItem(label, code)
            pickup = OptionalNumberEdit()
            grid.addWidget(QLabel(FUNCTION_LABELS_FA[key]), r, 0)
            for c, w in enumerate((curve, time_, unit, pickup), start=1):
                grid.addWidget(w, r, c)
                self._order.append(w)
            curve.currentTextChanged.connect(self._emit)
            time_.textChanged.connect(self._emit)
            pickup.textChanged.connect(self._emit)
            unit.currentIndexChanged.connect(self._emit)
            self._rows[key] = (curve, time_, unit, pickup)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.shots = self.dead_times = self.reclaim = None
        self.counter = self.dl_current = self.dl_voltage = None
        if reclosing:
            self.shots = OptionalNumberEdit()
            self.dead_times = QLineEdit()
            self.dead_times.setPlaceholderText("مثال: 2, 30")
            self.reclaim = OptionalNumberEdit()
            form.addRow("تعداد Shot:", self.shots)
            form.addRow("Dead time ها (s):", self.dead_times)
            form.addRow("Reclaim time (s):", self.reclaim)
        if counter:
            self.counter = OptionalNumberEdit()
            self.dl_current = OptionalNumberEdit()
            self.dl_voltage = OptionalNumberEdit()
            form.addRow("Counter:", self.counter)
            form.addRow("Dead line — جریان (٪ In):", self.dl_current)
            form.addRow("Dead line — ولتاژ (٪ Un):", self.dl_voltage)
        grid.addLayout(form, len(FUNCTION_KEYS) + 1, 0, 1, 5)
        for w in (self.shots, self.dead_times, self.reclaim, self.counter,
                  self.dl_current, self.dl_voltage):
            if w is not None:
                w.textChanged.connect(self._emit)
                self._order.append(w)
        for a, b in zip(self._order, self._order[1:]):       # Tab Order صحیح
            QWidget.setTabOrder(a, b)
        self._loading = False

    def _emit(self, *_a) -> None:
        if not self._loading:
            self.changed.emit()

    def focus_field(self, key: str) -> bool:
        """Focus روی فیلد دقیق: «f51.pickup_a» | «f50n.time_value» | shots | reclaim | counter | dead_line."""
        target = None
        if "." in key:
            fn, attr = key.split(".", 1)
            row = self._rows.get(fn)
            if row is not None:
                target = {"curve": row[0], "time_value": row[1], "time_unit": row[2],
                          "pickup_a": row[3]}.get(attr)
        else:
            target = {"shots": self.shots, "dead_times": self.dead_times, "reclaim": self.reclaim,
                      "counter": self.counter, "dead_line": self.dl_current}.get(key)
        if target is None:
            return False
        target.setFocus()
        sel = getattr(target, "selectAll", None)
        if callable(sel):
            sel()
        return True

    # --- مدل ↔ فرم ---------------------------------------------------------
    def load(self, s: ProtectionSettings) -> None:
        self._loading = True
        for key, (curve, time_, unit, pickup) in self._rows.items():
            f = s.function(key)
            delayed = key in DELAYED_KEYS
            # پیش‌فرض‌ها: منحنی NI و TMS درصدی برای توابع تأخیری، زمان ms برای آنی
            curve.setCurrentText(f.curve or (DEFAULT_CURVE if delayed else ""))
            time_.set_value(f.time_value)
            default_unit = TIME_UNIT_PERCENT if delayed else TIME_UNIT_MS
            idx = unit.findData(f.time_unit or default_unit)
            unit.setCurrentIndex(max(idx, 0))
            pickup.set_value(f.pickup_a)
        if self.shots is not None:
            self.shots.set_value(None if s.shots is None else float(s.shots))
            self.dead_times.setText(", ".join(f"{t:g}" for t in s.dead_times_s))
            self.reclaim.set_value(s.reclaim_time_s)
        if self.counter is not None:
            self.counter.set_value(None if s.counter is None else float(s.counter))
            self.dl_current.set_value(s.dead_line_current_pct)
            self.dl_voltage.set_value(s.dead_line_voltage_pct)
        self._loading = False

    def store(self, s: ProtectionSettings) -> None:
        for key, (curve, time_, unit, pickup) in self._rows.items():
            setattr(s, key, FunctionSetting(
                curve=curve.currentText().strip(), pickup_a=pickup.value(),
                time_value=time_.value(), time_unit=unit.currentData() or ""))
        if self.shots is not None:
            v = self.shots.value()
            s.shots = None if v is None else int(v)
            s.dead_times_s = [t for t in (parse_optional_float(p)
                                          for p in self.dead_times.text().replace("،", ",").split(","))
                              if t is not None]
            s.reclaim_time_s = self.reclaim.value()
        if self.counter is not None:
            v = self.counter.value()
            s.counter = None if v is None else int(v)
            s.dead_line_current_pct = self.dl_current.value()
            s.dead_line_voltage_pct = self.dl_voltage.value()
