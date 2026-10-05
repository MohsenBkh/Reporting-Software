# -*- coding: utf-8 -*-
"""صفحه «مطالعه سکشنالایزر و ریکلوزر» — تب مجزا، جدا از مطالعه مصارف سنگین.

طراحی بر اساس الگوهای رابط گرافیکی گالری طراحی ویندوز (WinUI Gallery،
الگوی کارت‌ها، سربرگ صفحه و نوارهای اطلاع‌رسانی):

* دو تب (Pivot): **سکشنالایزر** (اسکلت فعال) و **ریکلوزر** (در برنامه).
* هر تب فرم یکسانی دارد (محل نصب، سطح اتصال کوتاه، تنظیمات حفاظتی، هماهنگی)
  و داده‌هایش را در ``Project.sectionalizer`` / ``Project.recloser`` ذخیره می‌کند.
* نوار اطلاع‌رسانی وضعیت «نوع گزارش» را نشان می‌دهد و با یک کلیک نوع گزارش
  پروژه را روی مطالعهٔ همان تجهیز تنظیم می‌کند.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTabWidget,
                               QVBoxLayout, QWidget)

from app.core.models import RecloserInfo, SectionalizerInfo
from app.core.report_types import (REPORT_TYPE_RECLOSER,
                                   REPORT_TYPE_SECTIONALIZER, booklet_title,
                                   is_implemented)
from app.core.settings import AppSettings
from app.ui.widgets import make_spin, page_header, scrollable

_TYPE_OF_TAB = {0: REPORT_TYPE_SECTIONALIZER, 1: REPORT_TYPE_RECLOSER}


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


def _infobar(object_name: str, text: str) -> tuple[QFrame, QLabel]:
    """نوار اطلاع‌رسانی (InfoBar) به سبک گالری طراحی ویندوز."""
    bar = QFrame()
    bar.setObjectName(object_name)
    h = QHBoxLayout(bar)
    h.setContentsMargins(12, 8, 12, 8)
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    h.addWidget(lbl, 1)
    return bar, lbl


class ProtectionPage(QWidget):
    """ورود داده‌های مطالعه سکشنالایزر و ریکلوزر (تب مجزا)."""

    changed = Signal()

    def __init__(self, manager, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
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
            "کدام با قالب خودش تولید می‌شود."))

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(scrollable(self._build_device_tab("secz")), "سکشنالایزر")
        self.tabs.addTab(scrollable(self._build_device_tab("rcls")), "ریکلوزر")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._update_type_bar()

    # ------------------------------------------------------------------
    def _build_device_tab(self, prefix: str) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(2, 2, 2, 2)
        v.setSpacing(10)

        # نوار وضعیت «نوع گزارش» + دکمه تنظیم
        bar, bar_lbl = _infobar("InfoBarInfo", "")
        bh = bar.layout()
        btn_type = QPushButton("تنظیم نوع گزارش پروژه")
        btn_type.setObjectName("primary")
        btn_type.clicked.connect(
            lambda _=False, p=prefix: self._set_report_type(p))
        bh.addWidget(btn_type)
        setattr(self, f"{prefix}_type_bar", bar)
        setattr(self, f"{prefix}_type_lbl", bar_lbl)
        setattr(self, f"{prefix}_type_btn", btn_type)
        v.addWidget(bar)

        if prefix == "rcls":
            warn, _wl = _infobar(
                "InfoBarWarn",
                "قالب گزارش ریکلوزر در برنامه است و در نسخه‌های بعدی فعال می‌شود. "
                "داده‌ها همین‌جا ثبت می‌مانند تا به‌محض ارسال جزئیات، گزارش‌گیری فعال شود.")
            v.addWidget(warn)

        # --- کارت ۱: شبکه و محل نصب ---
        card1, v1 = _card("۱) شبکه و محل نصب",
                          "فیدر هدف، نقطه نصب و هدف از نصب تجهیز.")
        f1 = QFormLayout()
        f1.setLabelAlignment(Qt.AlignRight)
        feeder = QLineEdit()
        location = QLineEdit()
        location.setPlaceholderText("مثال: تیر شماره ۱۲۳، تقاطع بلوار کشاورز")
        objective = QLineEdit()
        objective.setPlaceholderText("مثال: ایزوله‌سازی سریع منطقه خطا و کاهش خاموشی")
        f1.addRow("فیدر هدف:", feeder)
        f1.addRow("محل نصب:", location)
        f1.addRow("هدف نصب:", objective)
        v1.addLayout(f1)
        v.addWidget(card1)

        # --- کارت ۲: سطح اتصال کوتاه و تنظیمات حفاظتی ---
        card2, v2 = _card("۲) سطح اتصال کوتاه و تنظیمات حفاظتی",
                          "مقادیر ناموجود در گزارش با برچسب «ناموجود» درج می‌شوند (نه صفر).")
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

        note, _nl = _infobar(
            "InfoBarInfo",
            "جزئیات تکمیلی این مطالعه پس از ارسال توسط کارفرما به همین ساختار "
            "اضافه می‌شود؛ داده‌های واردشده در پروژه ذخیره می‌مانند.")
        v.addWidget(note)
        v.addStretch(1)

        fields = {"feeder_name": feeder, "installation_location": location,
                  "objective": objective, "fault_current_ka": fault,
                  "min_fault_current_ka": minfault, "pickup_current_a": pickup,
                  "tms": tms, "upstream_device": upstream,
                  "coordination_note": coordination}
        setattr(self, f"{prefix}_fields", fields)
        for w in (feeder, location, objective, upstream, coordination):
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

    def _current_prefix(self) -> str:
        return "secz" if self.tabs.currentIndex() == 0 else "rcls"

    def _on_tab_changed(self, index: int) -> None:
        # هنگام تعویض تب، داده‌های تب قبلی در پروژه ذخیره شود
        self.save_to_project()
        self._update_type_bar()

    def _on_change(self, *args) -> None:
        if not self._loading:
            self.changed.emit()

    # ------------------------------------------------------------------
    def _update_type_bar(self) -> None:
        """متن نوار وضعیت نوع گزارش برای هر دو تب."""
        p = self.manager.project
        for prefix, rtype in (("secz", REPORT_TYPE_SECTIONALIZER),
                              ("rcls", REPORT_TYPE_RECLOSER)):
            lbl = getattr(self, f"{prefix}_type_lbl", None)
            btn = getattr(self, f"{prefix}_type_btn", None)
            if lbl is None:
                continue
            if p is None:
                lbl.setText("پروژه‌ای باز نیست.")
                if btn:
                    btn.setEnabled(False)
                continue
            active = p.report_type == rtype
            implemented = is_implemented(rtype)
            if active:
                lbl.setText(f"نوع گزارش پروژه اکنون «{booklet_title(rtype)}» است و "
                            "گزارش با همین قالب تولید می‌شود.")
                if btn:
                    btn.setEnabled(False)
            elif rtype == REPORT_TYPE_RECLOSER:
                lbl.setText("قالب گزارش ریکلوزر هنوز فعال نشده است؛ پس از فعال‌شدن، "
                            "نوع گزارش از همین‌جا تنظیم می‌شود.")
                if btn:
                    btn.setEnabled(False)
            else:
                lbl.setText(f"نوع گزارش پروژه هنوز «{booklet_title(p.report_type)}» است.")
                if btn:
                    btn.setEnabled(True)

    def _set_report_type(self, prefix: str) -> None:
        p = self.manager.project
        if p is None:
            return
        p.report_type = _TYPE_OF_TAB[0] if prefix == "secz" else _TYPE_OF_TAB[1]
        self._update_type_bar()
        self.changed.emit()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self.load_from_project()

    def load_from_project(self) -> None:
        p = self.manager.project
        self._loading = True
        for prefix in ("secz", "rcls"):
            info = self._device_info(prefix)
            fields = getattr(self, f"{prefix}_fields")
            for name, widget in fields.items():
                value = getattr(info, name, None) if info is not None else None
                if isinstance(widget, QLineEdit):
                    widget.setText(value or "")
                else:
                    widget.setValue(value if value is not None else 0.0)
        self._loading = False
        self._update_type_bar()

    def save_to_project(self) -> None:
        p = self.manager.project
        if p is None:
            return
        for prefix in ("secz", "rcls"):
            info = self._device_info(prefix)
            if info is None:
                continue
            fields = getattr(self, f"{prefix}_fields")
            for name, widget in fields.items():
                if isinstance(widget, QLineEdit):
                    setattr(info, name, widget.text().strip())
                else:
                    setattr(info, name, widget.value() or None)
