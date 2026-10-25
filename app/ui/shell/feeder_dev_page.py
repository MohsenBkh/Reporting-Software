# -*- coding: utf-8 -*-
"""صفحه ورود داده مطالعه «توسعه و اصلاح فیدر» — v2.4.0.

اسکلت دفترچه مطابق نمونه‌های واقعی (اصلاح خط اوچ‌بلاغ / فیدر جدید پست آغدام):
مشخصات کلی طرح ← جدول فیدرهای محدوده ← وضعیت موجود و پخش بار قبل ←
راه‌حل پیشنهادی (شرح طرح) ← پخش بار بعد و نتیجه‌گیری.
همه مقادیر اختیاری‌اند: خالی = «ناموجود» در گزارش، نه صفر.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QPlainTextEdit, QPushButton, QScrollArea,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app.core.models import FeederDevRow
from app.ui.shell.design import SPACING
from app.ui.shell.settings_editor import OptionalNumberEdit, parse_optional_float
from app.ui.widgets import page_header

#: گزینه‌های پیشنهادی «نوع طرح» (قابل ویرایش — متن آزاد هم پذیرفته می‌شود)
PLAN_KINDS = ("اصلاح خط موجود", "احداث فیدر جدید", "بازآرایی و تعدیل بار شبکه")

#: ستون‌های جدول فیدرها: (عنوان، صفت FeederDevRow، عددی؟)
FEEDER_COLUMNS = [
    ("پست و فیدر", "name", False),
    ("ولتاژ (kV)", "voltage_kv", True),
    ("طول خط (km)", "length_km", True),
    ("حداکثر بار (MW)", "peak_load_mw", True),
    ("حداقل بار (MW)", "min_load_mw", True),
    ("بارگیری (%)", "loading_pct", True),
    ("ضریب قدرت", "power_factor", True),
]


def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    lay = QVBoxLayout(card)
    t = QLabel(title)
    t.setObjectName("CardTitle")
    lay.addWidget(t)
    return card, lay


class FeederDevPage(QWidget):
    """فرم کامل مطالعه توسعه و اصلاح فیدر؛ خواندن/نوشتن ``project.feeder_dev``."""

    changed = Signal()

    def __init__(self, manager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"])
        root.setSpacing(SPACING["md"])
        root.addWidget(page_header(
            "توسعه و اصلاح فیدر",
            "دفترچه مطالعات توسعه و اصلاح شبکه — مرجع‌ها: WI150900 و TAV111-03/00"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        v = QVBoxLayout(body)
        v.setSpacing(SPACING["md"])
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # --- ۱) مشخصات کلی طرح -------------------------------------------
        card, lay = _card("مشخصات کلی طرح")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.plan_kind = QComboBox()
        self.plan_kind.setEditable(True)
        self.plan_kind.addItem("")
        for k in PLAN_KINDS:
            self.plan_kind.addItem(k)
        self.plan_kind.lineEdit().setPlaceholderText("مثال: اصلاح خط موجود")
        self.substation = QLineEdit()
        self.substation.setPlaceholderText("مثال: پست فوق توزیع خلخال")
        form.addRow("نوع طرح:", self.plan_kind)
        form.addRow("پست فوق توزیع محدوده:", self.substation)
        lay.addLayout(form)
        v.addWidget(card)

        # --- ۲) جدول فیدرهای محدوده مطالعه ---------------------------------
        card, lay = _card("مشخصات فیدرهای محدوده مطالعه")
        self.table = QTableWidget(0, len(FEEDER_COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in FEEDER_COLUMNS])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 240)
        self.table.setMinimumHeight(140)
        lay.addWidget(self.table)
        btns = QHBoxLayout()
        b_add = QPushButton("➕ افزودن فیدر")
        b_del = QPushButton("➖ حذف فیدر انتخابی")
        b_add.clicked.connect(self._add_row)
        b_del.clicked.connect(self._remove_row)
        btns.addWidget(b_add)
        btns.addWidget(b_del)
        btns.addStretch(1)
        lay.addLayout(btns)
        v.addWidget(card)

        # --- ۳) وضعیت موجود و پخش بار قبل از اصلاح --------------------------
        card, lay = _card("وضعیت موجود و پخش بار قبل از اصلاح")
        self.existing_description = self._text(
            "تحلیل وضعیت موجود فیدرها (بارگیری، ضریب قدرت، مشکلات ولتاژ و ...)")
        self.before_description = self._text(
            "شرح نتایج پخش بار شبکه قبل از اصلاح (DIgSILENT یا نرم‌افزار مشابه)")
        lay.addWidget(QLabel("تحلیل وضعیت موجود:"))
        lay.addWidget(self.existing_description)
        lay.addWidget(QLabel("شرح پخش بار قبل از اصلاح:"))
        lay.addWidget(self.before_description)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.min_voltage_kv_before = OptionalNumberEdit()
        self.losses_kw_before = OptionalNumberEdit()
        self.max_loading_pct_before = OptionalNumberEdit()
        form.addRow("حداقل ولتاژ شبکه — قبل (kV):", self.min_voltage_kv_before)
        form.addRow("تلفات توان — قبل (kW):", self.losses_kw_before)
        form.addRow("حداکثر بارگیری فیدر — قبل (%):", self.max_loading_pct_before)
        lay.addLayout(form)
        v.addWidget(card)

        # --- ۴) راه‌حل پیشنهادی (شرح طرح) -----------------------------------
        card, lay = _card("راه‌حل پیشنهادی (شرح طرح)")
        self.proposal_description = self._text(
            "شرح طرح: مسیر خط جدید، نقاط مانور، برچیدن خط قدیمی و ...")
        lay.addWidget(self.proposal_description)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.new_line_length_km = OptionalNumberEdit()
        self.conductor_type = QLineEdit()
        self.conductor_type.setPlaceholderText("مثال: هاینا ۱۲۶")
        self.removed_line_length_km = OptionalNumberEdit()
        form.addRow("طول خط جدید/اصلاحی (km):", self.new_line_length_km)
        form.addRow("نوع هادی:", self.conductor_type)
        form.addRow("طول خط برچیده‌شده (km):", self.removed_line_length_km)
        lay.addLayout(form)
        v.addWidget(card)

        # --- ۵) پخش بار بعد از اصلاح و نتیجه‌گیری ----------------------------
        card, lay = _card("پخش بار بعد از اصلاح و نتیجه‌گیری")
        self.after_description = self._text("شرح نتایج پخش بار شبکه بعد از اجرای طرح")
        lay.addWidget(self.after_description)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.min_voltage_kv_after = OptionalNumberEdit()
        self.losses_kw_after = OptionalNumberEdit()
        self.max_loading_pct_after = OptionalNumberEdit()
        form.addRow("حداقل ولتاژ شبکه — بعد (kV):", self.min_voltage_kv_after)
        form.addRow("تلفات توان — بعد (kW):", self.losses_kw_after)
        form.addRow("حداکثر بارگیری فیدر — بعد (%):", self.max_loading_pct_after)
        lay.addLayout(form)
        self.conclusion = self._text(
            "نتیجه‌گیری (خالی = جمع‌بندی خودکار از مقادیر قبل/بعد ثبت‌شده)")
        lay.addWidget(QLabel("نتیجه‌گیری:"))
        lay.addWidget(self.conclusion)
        v.addWidget(card)

        # --- ۶) متن مقدمه (اختیاری) ----------------------------------------
        card, lay = _card("مقدمه (اختیاری)")
        self.intro = self._text(
            "خالی = متن استاندارد مقدمه با مرجع‌های WI150900 و TAV111-03/00")
        lay.addWidget(self.intro)
        v.addWidget(card)
        v.addStretch(1)

        # --- سیگنال تغییر ---------------------------------------------------
        for w in (self.substation, self.conductor_type, self.new_line_length_km,
                  self.removed_line_length_km, self.min_voltage_kv_before,
                  self.losses_kw_before, self.max_loading_pct_before,
                  self.min_voltage_kv_after, self.losses_kw_after,
                  self.max_loading_pct_after):
            w.textChanged.connect(self._emit)
        self.plan_kind.currentTextChanged.connect(self._emit)
        for t in (self.intro, self.existing_description, self.before_description,
                  self.proposal_description, self.after_description, self.conclusion):
            t.textChanged.connect(self._emit)
        self.table.itemChanged.connect(self._emit)

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

    def _add_row(self) -> None:
        self.table.insertRow(self.table.rowCount())
        self._emit()

    def _remove_row(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._emit()

    # ------------------------------------------------------------------
    # مدل ↔ فرم
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        project = getattr(self.manager, "project", None)
        if project is not None:
            self.load_from(project)

    def load_from(self, project) -> None:
        info = getattr(project, "feeder_dev", None)
        if info is None:
            return
        self._loading = True
        self.plan_kind.setCurrentText(info.plan_kind)
        self.substation.setText(info.substation)
        self.intro.setPlainText(info.intro)
        self.existing_description.setPlainText(info.existing_description)
        self.before_description.setPlainText(info.before_description)
        self.proposal_description.setPlainText(info.proposal_description)
        self.after_description.setPlainText(info.after_description)
        self.conclusion.setPlainText(info.conclusion)
        self.conductor_type.setText(info.conductor_type)
        for w, val in ((self.new_line_length_km, info.new_line_length_km),
                       (self.removed_line_length_km, info.removed_line_length_km),
                       (self.min_voltage_kv_before, info.min_voltage_kv_before),
                       (self.losses_kw_before, info.losses_kw_before),
                       (self.max_loading_pct_before, info.max_loading_pct_before),
                       (self.min_voltage_kv_after, info.min_voltage_kv_after),
                       (self.losses_kw_after, info.losses_kw_after),
                       (self.max_loading_pct_after, info.max_loading_pct_after)):
            w.set_value(val)
        self.table.setRowCount(0)
        for f in info.feeders:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, (_t, attr, numeric) in enumerate(FEEDER_COLUMNS):
                val = getattr(f, attr)
                text = "" if val in (None, "") else (f"{val:g}" if numeric else str(val))
                self.table.setItem(r, c, QTableWidgetItem(text))
        self._loading = False

    def save_to_project(self) -> None:
        project = getattr(self.manager, "project", None)
        info = getattr(project, "feeder_dev", None)
        if info is None:
            return
        info.plan_kind = self.plan_kind.currentText().strip()
        info.substation = self.substation.text().strip()
        info.intro = self.intro.toPlainText().strip()
        info.existing_description = self.existing_description.toPlainText().strip()
        info.before_description = self.before_description.toPlainText().strip()
        info.proposal_description = self.proposal_description.toPlainText().strip()
        info.after_description = self.after_description.toPlainText().strip()
        info.conclusion = self.conclusion.toPlainText().strip()
        info.conductor_type = self.conductor_type.text().strip()
        info.new_line_length_km = self.new_line_length_km.value()
        info.removed_line_length_km = self.removed_line_length_km.value()
        info.min_voltage_kv_before = self.min_voltage_kv_before.value()
        info.losses_kw_before = self.losses_kw_before.value()
        info.max_loading_pct_before = self.max_loading_pct_before.value()
        info.min_voltage_kv_after = self.min_voltage_kv_after.value()
        info.losses_kw_after = self.losses_kw_after.value()
        info.max_loading_pct_after = self.max_loading_pct_after.value()
        rows: list[FeederDevRow] = []
        for r in range(self.table.rowCount()):
            row = FeederDevRow()
            empty = True
            for c, (_t, attr, numeric) in enumerate(FEEDER_COLUMNS):
                item = self.table.item(r, c)
                text = (item.text() if item is not None else "").strip()
                if not text:
                    continue
                empty = False
                setattr(row, attr, parse_optional_float(text) if numeric else text)
            if not empty:
                rows.append(row)
        info.feeders = rows

    # ------------------------------------------------------------------
    def focus_field(self, *_keys) -> bool:
        self.plan_kind.setFocus()
        return True
