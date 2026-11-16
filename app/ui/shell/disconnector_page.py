# -*- coding: utf-8 -*-
"""صفحه ورود داده مطالعه «جایابی سکسیونر» — v2.6.0.

ساختار فرم مطابق قالب «Disconnector Format.json»:
مقدمه ← مشخصات شبکه (جدول ۱) ← الزامات کلیدگذاری (متن ثابت قالب) ←
جایابی سکسیونر بر اساس EENS (ورود از eens_report.json) ← پوشش اینترنت.
متن‌های ثابت قالب در گزارش‌ساز تعبیه شده‌اند؛ اینجا فقط متغیرهای داخل آکولاد
وارد می‌شوند. بخش جایابی همیشه از فایل خروجی نرم‌افزار SwitchLoc
(eens_report.json) وارد می‌شود تا نتایج گزارش عیناً با آن منطبق باشد.
همه مقادیر اختیاری‌اند: خالی = «ناموجود» در گزارش، نه صفر.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QFrame,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from app.core.eens_import import (EENSImportError, apply_eens_to_disconnector,
                                  load_eens_report)
from app.ui.shell.design import SPACING
from app.ui.shell.settings_editor import OptionalNumberEdit
from app.ui.widgets import page_header

#: گزینه‌های پیشنهادی «نوع سکسیونر» (متن آزاد هم پذیرفته می‌شود)
DX_KINDS = ("قابل کنترل از راه دور (موتوردار)", "گازی قابل کنترل از راه دور",
            "هوایی دستی", "سکسیونر (Disconnector)")

#: گزینه‌های پیشنهادی «وضعیت پوشش اینترنت»
COVERAGE_STATES = ("مطلوب", "نسبتاً مطلوب", "ضعیف", "فاقد پوشش")


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    lay = QVBoxLayout(card)
    t = QLabel(title)
    t.setObjectName("CardTitle")
    lay.addWidget(t)
    return card, lay


class DisconnectorPage(QWidget):
    """فرم کامل مطالعه جایابی سکسیونر؛ خواندن/نوشتن ``project.disconnector``."""

    changed = Signal()

    def __init__(self, manager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"])
        root.setSpacing(SPACING["md"])
        root.addWidget(page_header(
            "جایابی سکسیونر",
            "دفترچه مطالعه جایابی سکسیونر — روش انرژی توزیع‌نشده (EENS)؛ "
            "مرجع‌ها: TAV111-03/00، WI150900 و TAV122-02/00"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        v = QVBoxLayout(body)
        v.setSpacing(SPACING["md"])
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # --- ۱) مقدمه — مشخصات تجهیز و موقعیت ------------------------------
        card, lay = _card("۱) مقدمه — مشخصات تجهیز و موقعیت")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.dx_kind = QComboBox()
        self.dx_kind.setEditable(True)
        self.dx_kind.addItem("")
        for k in DX_KINDS:
            self.dx_kind.addItem(k)
        self.dx_kind.lineEdit().setPlaceholderText("مثال: قابل کنترل از راه دور (موتوردار)")
        self.location = QLineEdit()
        self.location.setPlaceholderText("موقعیت جغرافیایی / روستا")
        self.county = QLineEdit()
        self.county.setPlaceholderText("نام شهرستان")
        self.province = QLineEdit()
        self.province.setPlaceholderText("نام استان (برای جدول پوشش اینترنت)")
        self.feeder_name = QLineEdit()
        self.feeder_name.setPlaceholderText("نام فیدر مورد مطالعه")
        self.post_name = QLineEdit()
        self.post_name.setPlaceholderText("نام پست فوق توزیع (خالی = پست پروژه)")
        form.addRow("نوع سکسیونر:", self.dx_kind)
        form.addRow("موقعیت جغرافیایی/روستا:", self.location)
        form.addRow("شهرستان:", self.county)
        form.addRow("استان:", self.province)
        form.addRow("نام فیدر:", self.feeder_name)
        form.addRow("نام پست:", self.post_name)
        lay.addLayout(form)
        self.intro = self._text("متن مقدمه (خالی = متن استاندارد قالب با مرجع‌های "
                                "TAV111-03/00 و WI150900)")
        lay.addWidget(QLabel("متن مقدمه (اختیاری):"))
        lay.addWidget(self.intro)
        v.addWidget(card)

        # --- ۲) مشخصات شبکه (جدول ۱) ---------------------------------------
        card, lay = _card("۲) مشخصات شبکه مورد مطالعه (جدول ۱)")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.voltage_kv = OptionalNumberEdit()
        self.load_current_a = OptionalNumberEdit()
        self.active_power_mw = OptionalNumberEdit()
        self.reactive_power_mvar = OptionalNumberEdit()
        self.dg_status = QLineEdit()
        self.dg_status.setPlaceholderText(
            "مثال: روی این فیدر منبع تولید پراکنده‌ای وجود ندارد")
        form.addRow("سطح ولتاژ (kV):", self.voltage_kv)
        form.addRow("جریان بار (A):", self.load_current_a)
        form.addRow("توان اکتیو (MW):", self.active_power_mw)
        form.addRow("توان راکتیو (MVar):", self.reactive_power_mvar)
        form.addRow("وضعیت منبع تولید پراکنده:", self.dg_status)
        lay.addLayout(form)
        v.addWidget(card)

        # --- ۳) الزامات کلیدگذاری (متن ثابت قالب) ---------------------------
        card, lay = _card("۳) الزامات کلیدگذاری")
        note = QLabel("متن این بخش ثابت است و عیناً از قالب (دستورالعمل "
                      "TAV122-02/00 توانیر — ۷ الزام کلیدگذاری) در گزارش درج می‌شود.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        lay.addWidget(note)
        v.addWidget(card)

        # --- ۴) جایابی سکسیونر — ورود نتایج EENS ---------------------------
        card, lay = _card("۴) جایابی سکسیونر بر اساس EENS — ورود نتایج SwitchLoc")
        import_bar = QHBoxLayout()
        self.btn_import = QPushButton("📥 ورود نتایج جایابی (eens_report.json)")
        self.btn_import.clicked.connect(self._import_eens)
        self.lbl_import = QLabel("نتایج جایابی هنوز وارد نشده است.")
        self.lbl_import.setObjectName("Muted")
        self.lbl_import.setWordWrap(True)
        import_bar.addWidget(self.btn_import)
        import_bar.addWidget(self.lbl_import, 1)
        lay.addLayout(import_bar)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.feeder_key = QLineEdit()
        self.feeder_key.setPlaceholderText("شناسه فیدر در فایل جایابی")
        self.failure_rate = OptionalNumberEdit()
        self.repair_time = OptionalNumberEdit()
        self.transient_rate = OptionalNumberEdit()
        self.line_length_km = OptionalNumberEdit()
        self.covered_load_kw = OptionalNumberEdit()
        self.device_note = QLineEdit()
        self.device_note.setPlaceholderText("مثال: خط هوایی")
        self.device_coords = QLineEdit()
        self.device_coords.setPlaceholderText("مثال: 750552, 4379268 m")
        self.eens_base = OptionalNumberEdit()
        self.eens_after = OptionalNumberEdit()
        self.improvement = OptionalNumberEdit()
        self.switch_count = OptionalNumberEdit()
        self.optimal_location = QLineEdit()
        self.optimal_location.setPlaceholderText("موقعیت بهینه (برای جمله نتیجه بخش ۴)")
        form.addRow("شناسه فیدر:", self.feeder_key)
        form.addRow("نرخ خرابی λ (در سال):", self.failure_rate)
        form.addRow("زمان تعمیر r (دقیقه):", self.repair_time)
        form.addRow("نرخ خرابی گذرا (در سال):", self.transient_rate)
        form.addRow("طول خط (km):", self.line_length_km)
        form.addRow("بار تحت پوشش (kW):", self.covered_load_kw)
        form.addRow("نوع خط/تجهیز:", self.device_note)
        form.addRow("مختصات تجهیز پیشنهادی:", self.device_coords)
        form.addRow("EENS پایه (MWh/سال):", self.eens_base)
        form.addRow("EENS پس از نصب (MWh/سال):", self.eens_after)
        form.addRow("درصد بهبود (%):", self.improvement)
        form.addRow("تعداد کلید پیشنهادی:", self.switch_count)
        form.addRow("موقعیت بهینه:", self.optimal_location)
        lay.addLayout(form)
        v.addWidget(card)

        # --- ۵) پوشش اینترنت ایرانسل و همراه اول ----------------------------
        card, lay = _card("۵) پوشش اینترنت ایرانسل و همراه اول (جدول ۳)")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.requested_location = QLineEdit()
        self.requested_location.setPlaceholderText("موقعیت درخواستی (خالی = موقعیت بخش ۱)")
        self.coverage_areas = QLineEdit()
        self.coverage_areas.setPlaceholderText("مناطق تحت پوشش: شهر / دهستان / روستا / جاده")
        self.coverage_status = QComboBox()
        self.coverage_status.setEditable(True)
        self.coverage_status.addItem("")
        for c in COVERAGE_STATES:
            self.coverage_status.addItem(c)
        form.addRow("موقعیت درخواستی:", self.requested_location)
        form.addRow("مناطق تحت پوشش:", self.coverage_areas)
        form.addRow("وضعیت پوشش اینترنت:", self.coverage_status)
        lay.addLayout(form)
        self.conclusion = self._text("توضیح تکمیلی پایان گزارش (اختیاری)")
        lay.addWidget(QLabel("توضیح تکمیلی (اختیاری):"))
        lay.addWidget(self.conclusion)
        v.addWidget(card)
        v.addStretch(1)

        # --- سیگنال تغییر ---------------------------------------------------
        for w in (self.location, self.county, self.province, self.feeder_name,
                  self.post_name, self.dg_status, self.feeder_key, self.device_note,
                  self.device_coords, self.optimal_location, self.requested_location,
                  self.coverage_areas, self.voltage_kv, self.load_current_a,
                  self.active_power_mw, self.reactive_power_mvar, self.failure_rate,
                  self.repair_time, self.transient_rate, self.line_length_km,
                  self.covered_load_kw, self.eens_base, self.eens_after,
                  self.improvement, self.switch_count):
            w.textChanged.connect(self._emit)
        self.dx_kind.currentTextChanged.connect(self._emit)
        self.coverage_status.currentTextChanged.connect(self._emit)
        for t in (self.intro, self.conclusion):
            t.textChanged.connect(self._emit)

    # ------------------------------------------------------------------
    @staticmethod
    def _text(placeholder: str) -> QPlainTextEdit:
        t = QPlainTextEdit()
        t.setPlaceholderText(placeholder)
        t.setFixedHeight(76)
        return t

    def _emit(self, *_a) -> None:
        if not self._loading:
            self.save_to_project()
            self.changed.emit()

    # ------------------------------------------------------------------
    # ورود eens_report.json (خروجی SwitchLoc)
    # ------------------------------------------------------------------
    def _import_eens(self) -> None:
        project = getattr(self.manager, "project", None)
        info = getattr(project, "disconnector", None)
        if info is None:
            return
        path, _f = QFileDialog.getOpenFileName(
            self, "انتخاب فایل نتایج جایابی (eens_report.json)", "",
            "فایل جایابی SwitchLoc (*.json)")
        if not path:
            return
        try:
            self.import_eens_file(path)
        except EENSImportError as exc:
            QMessageBox.warning(self, "ورود نتایج جایابی", str(exc))

    def import_eens_file(self, path: str) -> str:
        """ورود فایل جایابی و پرکردن فرم/مدل؛ برای تست و فراخوانی برنامه‌ای.

        خطا: :class:`EENSImportError`. برمی‌گرداند شناسه فیدر اعمال‌شده.
        """
        project = getattr(self.manager, "project", None)
        info = getattr(project, "disconnector", None)
        if info is None:
            raise EENSImportError("پروژه‌ای باز نیست.")
        self.save_to_project()                  # ورودی‌های فعلی کاربر حفظ شود
        report = load_eens_report(path)
        feeder_key = apply_eens_to_disconnector(info, report)
        self.load_from(project)
        self.changed.emit()
        return feeder_key

    # ------------------------------------------------------------------
    # مدل ↔ فرم
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        project = getattr(self.manager, "project", None)
        if project is not None:
            self.load_from(project)

    def load_from(self, project) -> None:
        info = getattr(project, "disconnector", None)
        if info is None:
            return
        self._loading = True
        self.dx_kind.setCurrentText(info.dx_kind)
        self.location.setText(info.location)
        self.county.setText(info.county)
        self.province.setText(info.province)
        self.feeder_name.setText(info.feeder_name)
        self.post_name.setText(info.post_name)
        self.dg_status.setText(info.dg_status)
        self.feeder_key.setText(info.feeder_key)
        self.device_note.setText(info.device_note)
        self.device_coords.setText(info.device_coords)
        self.optimal_location.setText(info.optimal_location)
        self.requested_location.setText(info.requested_location)
        self.coverage_areas.setText(info.coverage_areas)
        self.coverage_status.setCurrentText(info.coverage_status)
        self.intro.setPlainText(info.intro)
        self.conclusion.setPlainText(info.conclusion)
        for w, val in ((self.voltage_kv, info.voltage_kv),
                       (self.load_current_a, info.load_current_a),
                       (self.active_power_mw, info.active_power_mw),
                       (self.reactive_power_mvar, info.reactive_power_mvar),
                       (self.failure_rate, info.failure_rate_per_year),
                       (self.repair_time, info.repair_time_min),
                       (self.transient_rate, info.transient_rate_per_year),
                       (self.line_length_km, info.line_length_km),
                       (self.covered_load_kw, info.covered_load_kw),
                       (self.eens_base, info.eens_base_mwh),
                       (self.eens_after, info.eens_after_mwh),
                       (self.improvement, info.improvement_pct),
                       (self.switch_count, None if info.switch_count is None
                        else float(info.switch_count))):
            w.set_value(val)
        if info.eens_imported:
            ver = (info.eens_algo_version or "").strip()
            self.lbl_import.setText(
                "نتایج جایابی از فایل eens_report.json وارد شده است"
                + (f" ({ver})" if ver else "") + ".")
        else:
            self.lbl_import.setText("نتایج جایابی هنوز وارد نشده است.")
        self._loading = False

    def save_to_project(self) -> None:
        project = getattr(self.manager, "project", None)
        info = getattr(project, "disconnector", None)
        if info is None:
            return
        info.dx_kind = self.dx_kind.currentText().strip()
        info.location = self.location.text().strip()
        info.county = self.county.text().strip()
        info.province = self.province.text().strip()
        info.feeder_name = self.feeder_name.text().strip()
        info.post_name = self.post_name.text().strip()
        info.dg_status = self.dg_status.text().strip()
        info.feeder_key = self.feeder_key.text().strip()
        info.device_note = self.device_note.text().strip()
        info.device_coords = self.device_coords.text().strip()
        info.optimal_location = self.optimal_location.text().strip()
        info.requested_location = self.requested_location.text().strip()
        info.coverage_areas = self.coverage_areas.text().strip()
        info.coverage_status = self.coverage_status.currentText().strip()
        info.intro = self.intro.toPlainText().strip()
        info.conclusion = self.conclusion.toPlainText().strip()
        info.voltage_kv = self.voltage_kv.value()
        info.load_current_a = self.load_current_a.value()
        info.active_power_mw = self.active_power_mw.value()
        info.reactive_power_mvar = self.reactive_power_mvar.value()
        info.failure_rate_per_year = self.failure_rate.value()
        info.repair_time_min = self.repair_time.value()
        info.transient_rate_per_year = self.transient_rate.value()
        info.line_length_km = self.line_length_km.value()
        info.covered_load_kw = self.covered_load_kw.value()
        info.eens_base_mwh = self.eens_base.value()
        info.eens_after_mwh = self.eens_after.value()
        info.improvement_pct = self.improvement.value()
        sw = self.switch_count.value()
        info.switch_count = None if sw is None else int(sw)
