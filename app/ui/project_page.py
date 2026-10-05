# -*- coding: utf-8 -*-
"""صفحه پروژه — اطلاعات پایه با فرم Dynamic (بخش ۷ سند)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from app.core.models import REQUEST_INCREASE, REQUEST_NEW, Project
from app.core.report_types import (REPORT_TYPE_HEAVY, REPORT_TYPE_RECLOSER,
                                   REPORT_TYPE_SECTIONALIZER)
from app.utils.jalali import today_jalali


class ProjectPage(QWidget):
    changed = Signal()

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        # محتوای بلند داخل QScrollArea تا فرم‌ها با کمبود فضا فشرده نشوند
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

        title = QLabel("اطلاعات پروژه")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.form = form

        self.ed_name = QLineEdit()
        self.ed_number = QLineEdit()
        self.ed_date = QLineEdit(today_jalali())
        self.ed_applicant = QLineEdit()
        self.cb_type = QComboBox()
        self.cb_type.addItem("افزایش قدرت", REQUEST_INCREASE)
        self.cb_type.addItem("تأمین برق جدید", REQUEST_NEW)
        self.sp_existing = QDoubleSpinBox()
        self.sp_existing.setRange(0, 1e7)
        self.sp_existing.setDecimals(0)
        self.sp_existing.setGroupSeparatorShown(True)
        self.sp_requested = QDoubleSpinBox()
        self.sp_requested.setRange(0, 1e7)
        self.sp_requested.setDecimals(0)
        self.sp_requested.setGroupSeparatorShown(True)
        self.lbl_added = QLabel("—")
        self.ed_substation = QLineEdit()
        self.ed_office = QLineEdit()
        self.ed_expert = QLineEdit()

        # نوع گزارش (v1.3.0): سنگین / سکشنالایزر / ریکلوزر
        self.cb_report_type = QComboBox()
        self.cb_report_type.addItem("متقاضیان سنگین (یک مگاوات و بالاتر)",
                                    REPORT_TYPE_HEAVY)
        self.cb_report_type.addItem("مطالعه سکشنالایزر", REPORT_TYPE_SECTIONALIZER)
        self.cb_report_type.addItem("مطالعه ریکلوزر", REPORT_TYPE_RECLOSER)

        form.addRow("عنوان پروژه:", self.ed_name)
        form.addRow("شماره گزارش:", self.ed_number)
        form.addRow("تاریخ گزارش:", self.ed_date)
        form.addRow("نام متقاضی:", self.ed_applicant)
        form.addRow("نوع گزارش:", self.cb_report_type)
        form.addRow("نوع درخواست:", self.cb_type)
        form.addRow("توان فعلی (kW):", self.sp_existing)
        form.addRow("توان جدید (kW):", self.sp_requested)
        form.addRow("افزایش قدرت (محاسبه خودکار):", self.lbl_added)
        form.addRow("نام پست فوق توزیع:", self.ed_substation)
        form.addRow("نام امور:", self.ed_office)
        form.addRow("نام کارشناس:", self.ed_expert)
        root.addLayout(form)

        # --- گروه مانور (اختیاری) ---
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

        # --- گروه موقعیت محل ---
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

        # --- گروه سکشنالایزر (v1.3.0 — اسکلت؛ جزئیات تکمیلی بعداً) ---
        grp3 = QGroupBox("مشخصات سکشنالایزر (برای گزارش نوع «مطالعه سکشنالایزر»)")
        f3 = QFormLayout(grp3)
        self.sz_feeder = QLineEdit()
        self.sz_location = QLineEdit()
        self.sz_location.setPlaceholderText("شرح نقطه نصب (مثلاً تیر شماره …)")
        self.sz_objective = QLineEdit()
        self.sp_sz_fault = QDoubleSpinBox()
        self.sp_sz_fault.setRange(0, 1e4)
        self.sp_sz_fault.setDecimals(3)
        self.sp_sz_minfault = QDoubleSpinBox()
        self.sp_sz_minfault.setRange(0, 1e4)
        self.sp_sz_minfault.setDecimals(3)
        self.sp_sz_pickup = QDoubleSpinBox()
        self.sp_sz_pickup.setRange(0, 1e5)
        self.sp_sz_pickup.setDecimals(1)
        self.sp_sz_tms = QDoubleSpinBox()
        self.sp_sz_tms.setRange(0, 1e3)
        self.sp_sz_tms.setDecimals(2)
        self.sz_upstream = QLineEdit()
        self.sz_coordination = QLineEdit()
        f3.addRow("فیدر هدف:", self.sz_feeder)
        f3.addRow("محل نصب:", self.sz_location)
        f3.addRow("هدف نصب:", self.sz_objective)
        f3.addRow("جریان اتصال کوتاه در محل نصب (kA):", self.sp_sz_fault)
        f3.addRow("حداقل جریان اتصال کوتاه (kA):", self.sp_sz_minfault)
        f3.addRow("جریان تنظیم پیکاپ (A):", self.sp_sz_pickup)
        f3.addRow("تنظیم زمانی (TMS):", self.sp_sz_tms)
        f3.addRow("تجهیز حفاظتی بالادست:", self.sz_upstream)
        f3.addRow("توضیح هماهنگی حفاظت:", self.sz_coordination)
        root.addWidget(grp3)
        self.grp_sectionalizer = grp3

        # --- اتصال سیگنال‌ها ---
        for w in (self.ed_name, self.ed_number, self.ed_date, self.ed_applicant,
                  self.ed_substation, self.ed_office, self.ed_expert,
                  self.cb_man_source, self.cb_man_target, self.ed_man_date,
                  self.ed_man_note, self.ed_location, self.ed_cable,
                  self.sz_feeder, self.sz_location, self.sz_objective,
                  self.sz_upstream, self.sz_coordination):
            w.textChanged.connect(self._on_change)
        for w in (self.sp_existing, self.sp_requested, self.sp_man_mw, self.sp_distance,
                  self.sp_sz_fault, self.sp_sz_minfault, self.sp_sz_pickup,
                  self.sp_sz_tms):
            w.valueChanged.connect(self._on_change)
        self.cb_type.currentIndexChanged.connect(self._on_type_change)
        self.grp_maneuver.toggled.connect(self._on_change)
        self.cb_report_type.currentIndexChanged.connect(self._on_report_type_change)

        self._loading = False   # جلوگیری از پیام «ریکلوزر» هنگام بارگذاری پروژه
        self._on_type_change()
        self._on_report_type_change()

    # ------------------------------------------------------------------
    def _on_type_change(self, *args) -> None:
        """فرم Dynamic: نمایش فیلدهای لازم برای هر نوع درخواست (بخش ۷)."""
        is_increase = self.cb_type.currentData() == REQUEST_INCREASE
        self.sp_existing.setVisible(is_increase)
        # برچسب «توان فعلی» هم همراه فیلد مخفی/نمایش داده شود
        lbl = self.form.labelForField(self.sp_existing)
        if lbl is not None:
            lbl.setVisible(is_increase)
        self._update_added()
        self.changed.emit()

    def _on_report_type_change(self, *args) -> None:
        """نمایش گروه متناسب با نوع گزارش؛ ریکلوزر هنوز پیاده‌سازی نشده است."""
        rt = self.cb_report_type.currentData()
        if rt == REPORT_TYPE_RECLOSER and not getattr(self, "_loading", False):
            QMessageBox.information(
                self, "قالب ریکلوزر",
                "قالب گزارش «مطالعه ریکلوزر» در نسخه‌های بعدی اضافه می‌شود. "
                "جزئیات این قالب پس از دریافت از کارفرما پیاده‌سازی خواهد شد.")
            self.cb_report_type.blockSignals(True)
            idx = self.cb_report_type.findData(REPORT_TYPE_HEAVY)
            if idx >= 0:
                self.cb_report_type.setCurrentIndex(idx)
            self.cb_report_type.blockSignals(False)
            rt = REPORT_TYPE_HEAVY
        self.grp_sectionalizer.setVisible(rt == REPORT_TYPE_SECTIONALIZER)
        # در گزارش سکشنالایزر، فرم‌های توان/درخواست موضوعیت ندارند اما برای
        # حفظ داده‌های مشترک (نام متقاضی، شماره گزارش و …) فرم دست نمی‌خورد.
        self.changed.emit()

    def _update_added(self) -> None:
        existing = self.sp_existing.value()
        requested = self.sp_requested.value()
        if self.cb_type.currentData() == REQUEST_INCREASE and requested > 0 and existing > 0:
            delta = requested - existing
            self.lbl_added.setText(f"{delta:+,.0f} kW")
            if delta < 0:
                self.lbl_added.setStyleSheet("color:#B02A2A; font-weight:bold;")
            else:
                self.lbl_added.setStyleSheet("color:#2E7D32;")
        else:
            self.lbl_added.setText("—")

    def _on_change(self, *args) -> None:
        self._update_added()
        self.changed.emit()

    # ------------------------------------------------------------------
    def load_from(self, project: Project) -> None:
        self._loading = True
        self.ed_name.setText(project.name)
        self.ed_number.setText(project.report_number)
        self.ed_date.setText(project.date_jalali)
        self.ed_applicant.setText(project.applicant_name)
        rt = getattr(project, "report_type", "") or REPORT_TYPE_HEAVY
        idx = self.cb_report_type.findData(rt)
        if idx >= 0:
            self.cb_report_type.setCurrentIndex(idx)
        idx = self.cb_type.findData(project.request_type)
        if idx >= 0:
            self.cb_type.setCurrentIndex(idx)
        self.sp_existing.setValue(project.existing_power_kw or 0)
        self.sp_requested.setValue(project.requested_power_kw or 0)
        self.ed_substation.setText(project.substation)
        self.ed_office.setText(project.office)
        self.ed_expert.setText(project.expert_name)
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
        sz = project.sectionalizer
        self.sz_feeder.setText(sz.feeder_name)
        self.sz_location.setText(sz.installation_location)
        self.sz_objective.setText(sz.objective)
        self.sp_sz_fault.setValue(sz.fault_current_ka or 0)
        self.sp_sz_minfault.setValue(sz.min_fault_current_ka or 0)
        self.sp_sz_pickup.setValue(sz.pickup_current_a or 0)
        self.sp_sz_tms.setValue(sz.tms or 0)
        self.sz_upstream.setText(sz.upstream_device)
        self.sz_coordination.setText(sz.coordination_note)
        self._update_added()
        self._on_report_type_change()   # هنوز با _loading = True → پیام ریکلوزر نمی‌آید
        self._loading = False

    def save_to(self, project: Project) -> None:
        project.name = self.ed_name.text().strip()
        project.report_number = self.ed_number.text().strip()
        project.date_jalali = self.ed_date.text().strip()
        project.applicant_name = self.ed_applicant.text().strip()
        project.report_type = self.cb_report_type.currentData() or REPORT_TYPE_HEAVY
        project.request_type = self.cb_type.currentData()
        project.existing_power_kw = self.sp_existing.value() or None
        project.requested_power_kw = self.sp_requested.value() or None
        project.substation = self.ed_substation.text().strip()
        project.office = self.ed_office.text().strip()
        project.expert_name = self.ed_expert.text().strip()
        project.maneuver.enabled = self.grp_maneuver.isChecked()
        project.maneuver.source_feeder = self.cb_man_source.text().strip()
        project.maneuver.target_feeder = self.cb_man_target.text().strip()
        project.maneuver.transferred_mw = self.sp_man_mw.value() or None
        project.maneuver.date_jalali = self.ed_man_date.text().strip()
        project.maneuver.note = self.ed_man_note.text().strip()
        project.location_note = self.ed_location.text().strip()
        project.location_distance_m = self.sp_distance.value() or None
        project.cable_suggestion = self.ed_cable.text().strip()
        sz = project.sectionalizer
        sz.feeder_name = self.sz_feeder.text().strip()
        sz.installation_location = self.sz_location.text().strip()
        sz.objective = self.sz_objective.text().strip()
        sz.fault_current_ka = self.sp_sz_fault.value() or None
        sz.min_fault_current_ka = self.sp_sz_minfault.value() or None
        sz.pickup_current_a = self.sp_sz_pickup.value() or None
        sz.tms = self.sp_sz_tms.value() or None
        sz.upstream_device = self.sz_upstream.text().strip()
        sz.coordination_note = self.sz_coordination.text().strip()
