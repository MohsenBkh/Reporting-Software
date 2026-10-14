# -*- coding: utf-8 -*-
"""صفحهٔ «اطلاعات متقاضی و درخواست» — ورودی‌های اختصاصی مطالعهٔ متقاضی سنگین (v2.0.0).

شامل: نام متقاضی، نوع درخواست، توان فعلی و جدید، افزایش قدرت (محاسبهٔ خودکار)،
کادر مانور/بازآرایی شبکه و کادر موقعیت محل. این بخش قبلاً داخل «اطلاعات پروژه» بود؛
اکنون فقط در «ورود داده — متقاضی سنگین» نمایش داده می‌شود.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QLineEdit,
                               QComboBox, QScrollArea, QVBoxLayout, QWidget)

from app.core.models import REQUEST_INCREASE, REQUEST_NEW, Project


class ApplicantPage(QWidget):
    changed = Signal()

    def __init__(self, settings=None, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("Page")
        root = QVBoxLayout(body)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(12)
        scroll.setWidget(body)
        outer.addWidget(scroll)
        title = QLabel("اطلاعات متقاضی و درخواست")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        grp0 = QGroupBox("مشخصات متقاضی و درخواست")
        form = QFormLayout(grp0)
        form.setLabelAlignment(Qt.AlignRight)
        self.form = form
        self.ed_applicant = QLineEdit()
        self.cb_type = QComboBox()
        self.cb_type.addItem("افزایش قدرت", REQUEST_INCREASE)
        self.cb_type.addItem("تأمین برق جدید", REQUEST_NEW)
        self.sp_existing = self._kw_spin()
        self.sp_requested = self._kw_spin()
        self.lbl_added = QLabel("—")
        form.addRow("نام متقاضی:", self.ed_applicant)
        form.addRow("نوع درخواست:", self.cb_type)
        form.addRow("توان فعلی (kW):", self.sp_existing)
        form.addRow("توان جدید (kW):", self.sp_requested)
        form.addRow("افزایش قدرت (محاسبه خودکار):", self.lbl_added)
        root.addWidget(grp0)

        grp = QGroupBox("مانور / بازآرایی شبکه (اختیاری)")
        grp.setCheckable(True)
        grp.setChecked(False)
        self.grp_maneuver = grp
        mform = QFormLayout(grp)
        self.cb_man_source = QLineEdit()
        self.cb_man_target = QLineEdit()
        self.sp_man_mw = QDoubleSpinBox()
        self.sp_man_mw.setRange(0, 1e4)
        self.sp_man_mw.setDecimals(2)
        self.ed_man_date = QLineEdit()
        self.ed_man_note = QLineEdit()
        mform.addRow("فیدر مبدأ:", self.cb_man_source)
        mform.addRow("فیدر مقصد:", self.cb_man_target)
        mform.addRow("بار منتقل‌شده (MW):", self.sp_man_mw)
        mform.addRow("تاریخ مانور:", self.ed_man_date)
        mform.addRow("توضیحات (عدم قطعیت‌ها):", self.ed_man_note)
        root.addWidget(grp)

        grp2 = QGroupBox("موقعیت محل (اختیاری)")
        f2 = QFormLayout(grp2)
        self.ed_location = QLineEdit()
        self.ed_location.setPlaceholderText("مثال: اراضی شامل اسبی به مختصات X: 4230283 ، Y: 259094")
        self.sp_distance = QDoubleSpinBox()
        self.sp_distance.setRange(0, 1e6)
        self.sp_distance.setDecimals(0)
        self.ed_cable = QLineEdit()
        f2.addRow("توضیح موقعیت:", self.ed_location)
        f2.addRow("فاصله تا نزدیک‌ترین تیر (m):", self.sp_distance)
        f2.addRow("پیشنهاد نوع کابل:", self.ed_cable)
        root.addWidget(grp2)
        root.addStretch(1)

        self._loading = False
        for w in (self.ed_applicant, self.cb_man_source, self.cb_man_target, self.ed_man_date,
                  self.ed_man_note, self.ed_location, self.ed_cable):
            w.textChanged.connect(self._on_change)
        for w in (self.sp_existing, self.sp_requested, self.sp_man_mw, self.sp_distance):
            w.valueChanged.connect(self._on_change)
        self.cb_type.currentIndexChanged.connect(self._on_type_change)
        self.grp_maneuver.toggled.connect(self._on_change)
        self._on_type_change()

    @staticmethod
    def _kw_spin() -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(0, 1e7)
        sp.setDecimals(0)
        sp.setGroupSeparatorShown(True)
        return sp

    # ------------------------------------------------------------------
    def focus_field(self, name: str) -> bool:
        w = {"ed_applicant": self.ed_applicant, "sp_requested": self.sp_requested,
             "sp_existing": self.sp_existing, "cb_type": self.cb_type}.get(name)
        if w is None:
            return False
        w.setFocus()
        return True

    def _on_type_change(self, *_a) -> None:
        """فرم Dynamic: «توان فعلی» فقط برای افزایش قدرت نمایش داده می‌شود."""
        is_increase = self.cb_type.currentData() == REQUEST_INCREASE
        self.sp_existing.setVisible(is_increase)
        lbl = self.form.labelForField(self.sp_existing)
        if lbl is not None:
            lbl.setVisible(is_increase)
        self._update_added()
        self._on_change()

    def _update_added(self) -> None:
        existing, requested = self.sp_existing.value(), self.sp_requested.value()
        if self.cb_type.currentData() == REQUEST_INCREASE and requested > 0 and existing > 0:
            delta = requested - existing
            self.lbl_added.setText(f"{delta:+,.0f} kW")
            self.lbl_added.setProperty("badge_state", "error" if delta < 0 else "normal")
        else:
            self.lbl_added.setText("—")

    def _on_change(self, *_a) -> None:
        self._update_added()
        if not self._loading:
            self.changed.emit()

    # ------------------------------------------------------------------
    def load_from(self, project: Project) -> None:
        self._loading = True
        self.ed_applicant.setText(project.applicant_name)
        idx = self.cb_type.findData(project.request_type)
        if idx >= 0:
            self.cb_type.setCurrentIndex(idx)
        self.sp_existing.setValue(project.existing_power_kw or 0)
        self.sp_requested.setValue(project.requested_power_kw or 0)
        m = project.maneuver
        self.grp_maneuver.setChecked(m.enabled)
        self.cb_man_source.setText(m.source_feeder)
        self.cb_man_target.setText(m.target_feeder)
        self.sp_man_mw.setValue(m.transferred_mw or 0)
        self.ed_man_date.setText(m.date_jalali)
        self.ed_man_note.setText(m.note)
        self.ed_location.setText(project.location_note or "")
        self.sp_distance.setValue(project.location_distance_m or 0)
        self.ed_cable.setText(project.cable_suggestion or "")
        self._update_added()
        self._loading = False

    def save_to(self, project: Project) -> None:
        project.applicant_name = self.ed_applicant.text().strip()
        project.request_type = self.cb_type.currentData()
        project.existing_power_kw = self.sp_existing.value() or None
        project.requested_power_kw = self.sp_requested.value() or None
        project.maneuver.enabled = self.grp_maneuver.isChecked()
        project.maneuver.source_feeder = self.cb_man_source.text().strip()
        project.maneuver.target_feeder = self.cb_man_target.text().strip()
        project.maneuver.transferred_mw = self.sp_man_mw.value() or None
        project.maneuver.date_jalali = self.ed_man_date.text().strip()
        project.maneuver.note = self.ed_man_note.text().strip()
        project.location_note = self.ed_location.text().strip()
        project.location_distance_m = self.sp_distance.value() or None
        project.cable_suggestion = self.ed_cable.text().strip()
