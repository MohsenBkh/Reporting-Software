# -*- coding: utf-8 -*-
"""صفحه «مطالعه سکشنالایزر و ریکلوزر» — مشخصات پایه و محل نصب.

طراحی بر اساس الگوهای رابط گرافیکی گالری طراحی ویندوز (WinUI Gallery،
الگوی کارت‌ها، سربرگ صفحه و نوارهای اطلاع‌رسانی):

* دو تب (Pivot): **سکشنالایزر** و **ریکلوزر**؛ با ``only`` فقط یک تجهیز نمایش داده می‌شود
  (هر مطالعه صفحهٔ ورود داده مستقل خود را دارد).
* هر تب فرم یکسانی دارد (محل نصب، سطح اتصال کوتاه، تنظیمات حفاظتی، هماهنگی)
  و داده‌هایش را در ``Project.sectionalizer`` / ``Project.recloser`` ذخیره می‌کند.
* تنظیمات کامل توابع حفاظتی (۵۱/۵۰/۵۱N/۵۰N، شات، Counter و ...) در صفحهٔ
  «تنظیمات حفاظتی» Shell مهندسی (``app/ui/shell``) ثبت می‌شود.
* نوع گزارش از «Report Center» تنظیم می‌شود (نه از این صفحه).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFormLayout, QFrame, QLabel, QLineEdit, QTabWidget,
                               QVBoxLayout, QWidget)

from app.core.settings import AppSettings
from app.ui.widgets import make_spin, page_header, scrollable

PREFIX_OF_KIND = {"sectionalizer": "secz", "recloser": "rcls"}


def _card(title: str, subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
    """کارت به سبک کارت‌های گالری طراحی ویندوز: عنوان + توضیح + بدنه."""
    card = QFrame()
    card.setObjectName("Card")
    v = QVBoxLayout(card)
    v.setContentsMargins(16, 14, 16, 14)
    v.setSpacing(8)
    t = QLabel(title)
    t.setObjectName("CardTitle")
    v.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("CardSub")
        s.setWordWrap(True)
        v.addWidget(s)
    return card, v


class ProtectionPage(QWidget):
    """ورود داده‌های مطالعه سکشنالایزر و ریکلوزر (تب مجزا)."""

    changed = Signal()

    def __init__(self, manager, settings: AppSettings, only: str | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.only = only          # None | "secz" | "rcls" — فقط یک تجهیز نمایش داده شود
        self.manager = manager
        self.settings = settings
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header(
            "مطالعه سکشنالایزر و ریکلوزر",
            "داده‌های مطالعه نصب تجهیزات حفاظتی (سکشنالایزر و ریکلوزر). این بخش از "
            "مطالعه مصارف سنگین جداست؛ هر تجهیز تب مستقل خود را دارد و گزارش هر "
            "کدام با قالب خودش (یا گزارش ترکیبی) تولید می‌شود."))

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        if only in (None, "secz"):
            self.tabs.addTab(scrollable(self._build_device_tab("secz")), "سکشنالایزر")
        if only in (None, "rcls"):
            self.tabs.addTab(scrollable(self._build_device_tab("rcls")), "ریکلوزر")
        if only is not None:
            self.tabs.tabBar().setVisible(False)

    # ------------------------------------------------------------------
    def _build_device_tab(self, prefix: str) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(10)

        # --- کارت ۱: شبکه و محل نصب ---
        card1, v1 = _card("۱) شبکه و محل نصب",
                          "فیدر هدف، نقطه نصب و هدف از نصب تجهیز.")
        f1 = QFormLayout()
        f1.setLabelAlignment(Qt.AlignRight)
        feeder = QLineEdit()
        location = QLineEdit()
        location.setPlaceholderText("مثال: تیر شماره ۱۲۳، تقاطع بلوار کشاورز")
        coordinates = QLineEdit()
        coordinates.setPlaceholderText("مثال: 48.283541, 38.561204 یا UTM: 39S 612345 4268900")
        objective = QLineEdit()
        objective.setPlaceholderText("مثال: ایزوله‌سازی سریع منطقه خطا و کاهش خاموشی")
        f1.addRow("فیدر هدف:", feeder)
        f1.addRow("محل نصب:", location)
        f1.addRow("مختصات محل نصب:", coordinates)
        f1.addRow("هدف نصب:", objective)
        v1.addLayout(f1)
        v.addWidget(card1)

        # --- کارت ۲: سطح اتصال کوتاه و تنظیمات حفاظتی ---
        card2, v2 = _card("۲) سطح اتصال کوتاه و تنظیمات حفاظتی",
                          "مقادیر ناموجود در گزارش با برچسب «ناموجود» درج می‌شوند (نه صفر). "
                          "تنظیمات کامل توابع در تب «تنظیمات حفاظتی» ثبت می‌شود.")
        f2 = QFormLayout()
        f2.setLabelAlignment(Qt.AlignRight)
        fault = make_spin(0, 1e4, 3, 0.0)
        fault.setSuffix(" kA")
        minfault = make_spin(0, 1e4, 3, 0.0)
        minfault.setSuffix(" kA")
        pickup = make_spin(0, 1e5, 1, 0.0)
        pickup.setSuffix(" A")
        tms = make_spin(0, 1e3, 2, 0.0)
        f2.addRow("جریان اتصال کوتاه در محل نصب:", fault)
        f2.addRow("حداقل جریان اتصال کوتاه:", minfault)
        f2.addRow("جریان تنظیم پیکاپ:", pickup)
        f2.addRow("تنظیم زمانی (TMS):", tms)
        v2.addLayout(f2)
        v.addWidget(card2)

        # --- کارت ۳: هماهنگی حفاظت ---
        card3, v3 = _card("۳) هماهنگی حفاظت",
                          "تجهیز حفاظتی بالادست و ملاحظات هماهنگی با آن.")
        f3 = QFormLayout()
        f3.setLabelAlignment(Qt.AlignRight)
        upstream = QLineEdit()
        upstream.setPlaceholderText("مثال: ریکلوزر پست فوق توزیع نمونه")
        coordination = QLineEdit()
        f3.addRow("تجهیز حفاظتی بالادست:", upstream)
        f3.addRow("توضیح هماهنگی حفاظت:", coordination)
        v3.addLayout(f3)
        v.addWidget(card3)
        v.addStretch(1)

        fields = {"feeder_name": feeder, "installation_location": location,
                  "coordinates": coordinates, "objective": objective,
                  "fault_current_ka": fault,
                  "min_fault_current_ka": minfault, "pickup_current_a": pickup,
                  "tms": tms, "upstream_device": upstream,
                  "coordination_note": coordination}
        setattr(self, f"{prefix}_fields", fields)
        for w in (feeder, location, coordinates, objective, upstream, coordination):
            w.textChanged.connect(self._on_change)
        for w in (fault, minfault, pickup, tms):
            w.valueChanged.connect(self._on_change)
        return page

    # ------------------------------------------------------------------
    def _device_info(self, prefix: str):
        p = self.manager.project
        if p is None:
            return None
        if prefix == "secz":
            return p.sectionalizer
        return p.recloser

    def _on_change(self, *args) -> None:
        if not self._loading:
            self.changed.emit()

    # ------------------------------------------------------------------
    def focus_field(self, name: str) -> bool:
        """Focus روی فیلد تجهیز (مثلاً installation_location)."""
        for prefix in ("secz", "rcls"):
            w = (getattr(self, f"{prefix}_fields", None) or {}).get(name)
            if w is not None:
                w.setFocus()
                return True
        return False

    def refresh(self) -> None:
        self.load_from_project()

    def load_from_project(self) -> None:
        p = self.manager.project
        self._loading = True
        for prefix in ("secz", "rcls"):
            fields = getattr(self, f"{prefix}_fields", None)
            if fields is None:
                continue
            info = self._device_info(prefix)
            for name, widget in fields.items():
                value = getattr(info, name, None) if info is not None else None
                if isinstance(widget, QLineEdit):
                    widget.setText(value or "")
                else:
                    widget.setValue(value if value is not None else 0.0)
        self._loading = False

    def save_to_project(self) -> None:
        p = self.manager.project
        if p is None:
            return
        for prefix in ("secz", "rcls"):
            info = self._device_info(prefix)
            fields = getattr(self, f"{prefix}_fields", None)
            if info is None or fields is None:
                continue
            for name, widget in fields.items():
                if isinstance(widget, QLineEdit):
                    setattr(info, name, widget.text().strip())
                else:
                    setattr(info, name, widget.value() or None)
