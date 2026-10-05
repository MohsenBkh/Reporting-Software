# -*- coding: utf-8 -*-
"""صفحه پروژه — اطلاعات پایه با فرم Dynamic (بخش ۷ سند) + انتخاب نوع گزارش (v1.1.0)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QTableWidget,
                               QTableWidgetItem, QTextEdit, QVBoxLayout,
                               QWidget)

from app.core.models import REQUEST_INCREASE, REQUEST_NEW, Project
from app.core.report_types import (REPORT_HEAVY, REPORT_RECLOSER, REPORT_SECTIONALIZER,
                                   REPORT_TYPE_LABELS)
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

        self.cb_report_type = QComboBox()
        for key in (REPORT_HEAVY, REPORT_SECTIONALIZER, REPORT_RECLOSER):
            label = REPORT_TYPE_LABELS[key]
            if key == REPORT_RECLOSER:
                label += " (به‌زودی)"
            self.cb_report_type.addItem(label, key)
        # ریکلوزر هنوز فعال نیست — آیتم غیرقابل انتخاب
        _recloser_item = self.cb_report_type.model().item(
            self.cb_report_type.findData(REPORT_RECLOSER))
        _recloser_item.setFlags(_recloser_item.flags() & ~Qt.ItemIsEnabled)
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

        form.addRow("نوع گزارش:", self.cb_report_type)
        form.addRow("عنوان پروژه:", self.ed_name)
        form.addRow("شماره گزارش:", self.ed_number)
        form.addRow("تاریخ گزارش:", self.ed_date)
        form.addRow("نام متقاضی:", self.ed_applicant)
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
        self.ed_location.setPlaceholderText("مثال: 38: X: 732021, Y: 4377580")
        self.sp_distance = QDoubleSpinBox()
        self.sp_distance.setRange(0, 1e6)
        self.sp_distance.setDecimals(0)
        self.ed_conductor = QLineEdit()
        self.ed_conductor.setPlaceholderText("مثال: AL-126 (ACSR-Hyena)")
        f2.addRow("توضیح موقعیت (مختصات):", self.ed_location)
        f2.addRow("فاصله تا نزدیک‌ترین تیر (m):", self.sp_distance)
        f2.addRow("نوع هادی شبکه موجود:", self.ed_conductor)
        root.addWidget(grp2)

        # --- گروه ایستگاه‌های نزدیک به محل تقاضا (بخش ۴ گزارش) ---
        grp4 = QGroupBox("ایستگاه‌های نزدیک به محل تقاضا (اختیاری)")
        v4 = QVBoxLayout(grp4)
        self.tbl_stations = self._make_table(
            ["نام ایستگاه", "فاصله (km)", "ظرفیت (MVA)", "بارگیری T1 (٪)",
             "بارگیری T2 (٪)", "بار T1 (MVA)", "بار T2 (MVA)", "تعداد فیدر برقرار"])
        v4.addWidget(self.tbl_stations)
        v4.addLayout(self._row_buttons(self.tbl_stations, "st"))
        root.addWidget(grp4)
        self.grp_stations = grp4

        # --- گروه خطوط نزدیک به محل تقاضا (بخش ۵ گزارش) ---
        grp5 = QGroupBox("خطوط نزدیک به محل تقاضا (اختیاری)")
        v5 = QVBoxLayout(grp5)
        self.tbl_lines = self._make_table(
            ["نام خط", "فاصله (m)", "پیک (MVA)", "پیک (MW)", "پیک (A)",
             "افت ولتاژ قبل (٪)", "افت ولتاژ بعد (٪)"])
        v5.addWidget(self.tbl_lines)
        v5.addLayout(self._row_buttons(self.tbl_lines, "ln"))
        root.addWidget(grp5)
        self.grp_lines = grp5

        # --- سناریوهای پیشنهادی (بخش ۹ گزارش) ---
        grp6 = QGroupBox("سناریوهای پیشنهادی — نتیجه‌گیری (اختیاری)")
        v6 = QVBoxLayout(grp6)
        self.ed_scenarios = QTextEdit()
        self.ed_scenarios.setAcceptRichText(False)
        self.ed_scenarios.setPlaceholderText(
            "مثال: سناریو بازآرایی فیدر ... با فیدر ... به عنوان راهکار پیشنهادی؛ "
            "مختصات نقاط مانور و نتایج پخش بار پس از بازآرایی...")
        self.ed_scenarios.setFixedHeight(90)
        v6.addWidget(self.ed_scenarios)
        root.addWidget(grp6)
        self.grp_scenarios = grp6

        # --- گروه اطلاعات مطالعه سکشنالایزر ---
        grp3 = QGroupBox("اطلاعات مطالعه سکشنالایزر")
        f3 = QFormLayout(grp3)
        self.ed_secz_feeder = QLineEdit()
        self.ed_secz_feeder.setPlaceholderText("مثال: فیدر 7 گلخانه")
        self.ed_secz_location = QLineEdit()
        self.ed_secz_purpose = QLineEdit()
        self.ed_secz_notes = QLineEdit()
        self.ed_secz_notes.setPlaceholderText("سایر جزئیات — با ارسال اطلاعات تکمیلی، بخش‌های گزارش به‌روز می‌شود")
        f3.addRow("فیدر هدف مطالعه:", self.ed_secz_feeder)
        f3.addRow("محل پیشنهادی نصب:", self.ed_secz_location)
        f3.addRow("هدف / دلیل نصب:", self.ed_secz_purpose)
        f3.addRow("توضیحات:", self.ed_secz_notes)
        root.addWidget(grp3)
        self.grp_secz = grp3

        # --- اتصال سیگنال‌ها ---
        for w in (self.ed_name, self.ed_number, self.ed_date, self.ed_applicant,
                  self.ed_substation, self.ed_office, self.ed_expert,
                  self.cb_man_source, self.cb_man_target, self.ed_man_date,
                  self.ed_man_note, self.ed_location, self.ed_conductor,
                  self.ed_secz_feeder, self.ed_secz_location,
                  self.ed_secz_purpose, self.ed_secz_notes):
            w.textChanged.connect(self._on_change)
        for w in (self.sp_existing, self.sp_requested, self.sp_man_mw, self.sp_distance):
            w.valueChanged.connect(self._on_change)
        self.cb_type.currentIndexChanged.connect(self._on_type_change)
        self.cb_report_type.currentIndexChanged.connect(self._on_report_type_change)
        self.grp_maneuver.toggled.connect(self._on_change)
        self.ed_scenarios.textChanged.connect(self._on_change)
        self.tbl_stations.itemChanged.connect(lambda *_: self._on_change())
        self.tbl_lines.itemChanged.connect(lambda *_: self._on_change())

        self._on_report_type_change()
        self._on_type_change()

    # ------------------------------------------------------------------
    @staticmethod
    def _make_table(headers: list[str]) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setStretchLastSection(True)
        t.setAlternatingRowColors(True)
        t.setMaximumHeight(130)
        return t

    def _row_buttons(self, table: QTableWidget, prefix: str) -> QHBoxLayout:
        row = QHBoxLayout()
        add = QPushButton("+ ردیف")
        delete = QPushButton("حذف ردیف")

        def _add() -> None:
            r = table.rowCount()
            table.insertRow(r)
            for c in range(table.columnCount()):
                table.setItem(r, c, QTableWidgetItem(""))
            table.editItem(table.item(r, 0))
            self._on_change()

        def _del() -> None:
            rows = sorted({i.row() for i in table.selectedIndexes()}, reverse=True)
            if not rows and table.rowCount():
                rows = [table.rowCount() - 1]
            for r in rows:
                table.removeRow(r)
            self._on_change()

        add.clicked.connect(_add)
        delete.clicked.connect(_del)
        row.addWidget(add)
        row.addWidget(delete)
        row.addStretch(1)
        setattr(self, f"_btn_{prefix}_add", add)
        setattr(self, f"_btn_{prefix}_del", delete)
        return row

    @staticmethod
    def _cell(table: QTableWidget, r: int, c: int) -> str:
        item = table.item(r, c)
        return item.text().strip() if item else ""

    @staticmethod
    def _num(text: str) -> float | None:
        text = text.strip().replace("٫", ".")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _fill_stations(self, project: Project) -> None:
        t = self.tbl_stations
        t.setRowCount(0)
        for st in project.nearby_stations:
            r = t.rowCount()
            t.insertRow(r)
            vals = [st.name, st.distance_km, st.capacity_mva, st.t1_loading_pct,
                    st.t2_loading_pct, st.t1_loading_mva, st.t2_loading_mva, st.feeder_count]
            for c, v in enumerate(vals):
                t.setItem(r, c, QTableWidgetItem("" if v is None else str(v)))

    def _read_stations(self) -> list:
        from app.core.models import NearbyStation
        out = []
        t = self.tbl_stations
        for r in range(t.rowCount()):
            name = self._cell(t, r, 0)
            if not name:
                continue
            fc = self._num(self._cell(t, r, 7))
            out.append(NearbyStation(
                name=name, distance_km=self._num(self._cell(t, r, 1)),
                capacity_mva=self._num(self._cell(t, r, 2)),
                t1_loading_pct=self._num(self._cell(t, r, 3)),
                t2_loading_pct=self._num(self._cell(t, r, 4)),
                t1_loading_mva=self._num(self._cell(t, r, 5)),
                t2_loading_mva=self._num(self._cell(t, r, 6)),
                feeder_count=int(fc) if fc is not None else None))
        return out

    def _fill_lines(self, project: Project) -> None:
        t = self.tbl_lines
        t.setRowCount(0)
        for ln in project.nearby_lines:
            r = t.rowCount()
            t.insertRow(r)
            vals = [ln.name, ln.distance_m, ln.peak_mva, ln.peak_mw, ln.peak_a,
                    ln.vdrop_before_pct, ln.vdrop_after_pct]
            for c, v in enumerate(vals):
                t.setItem(r, c, QTableWidgetItem("" if v is None else str(v)))

    def _read_lines(self) -> list:
        from app.core.models import NearbyLine
        out = []
        t = self.tbl_lines
        for r in range(t.rowCount()):
            name = self._cell(t, r, 0)
            if not name:
                continue
            out.append(NearbyLine(
                name=name, distance_m=self._num(self._cell(t, r, 1)),
                peak_mva=self._num(self._cell(t, r, 2)),
                peak_mw=self._num(self._cell(t, r, 3)),
                peak_a=self._num(self._cell(t, r, 4)),
                vdrop_before_pct=self._num(self._cell(t, r, 5)),
                vdrop_after_pct=self._num(self._cell(t, r, 6))))
        return out

    def _is_heavy(self) -> bool:
        return self.cb_report_type.currentData() == REPORT_HEAVY

    def _on_report_type_change(self, *args) -> None:
        """فرم Dynamic بر اساس نوع گزارش: مصارف سنگین یا سکشنالایزر."""
        heavy = self._is_heavy()
        if self.cb_report_type.currentData() == REPORT_RECLOSER:
            heavy = False
        # فیلدهای مخصوص متقاضیان سنگین
        for w in (self.cb_type, self.sp_existing, self.sp_requested, self.lbl_added):
            w.setVisible(heavy)
        for w in (self.cb_type, self.sp_existing, self.sp_requested, self.lbl_added):
            lbl = self.form.labelForField(w)
            if lbl is not None:
                lbl.setVisible(heavy)
        self.grp_maneuver.setVisible(heavy)
        self.grp_stations.setVisible(heavy)
        self.grp_lines.setVisible(heavy)
        self.grp_scenarios.setVisible(heavy)
        self.grp_secz.setVisible(not heavy)
        if not heavy:
            # در مطالعات غیر مصارف سنگین، «نام متقاضی» عنوان مطالعه است
            self.form.labelForField(self.ed_applicant).setText("عنوان/متقاضی مطالعه:")
        else:
            self.form.labelForField(self.ed_applicant).setText("نام متقاضی:")
        self._update_added()
        self.changed.emit()

    def _on_type_change(self, *args) -> None:
        """فرم Dynamic: نمایش فیلدهای لازم برای هر نوع درخواست (بخش ۷)."""
        is_increase = self.cb_type.currentData() == REQUEST_INCREASE
        self.sp_existing.setVisible(is_increase and self._is_heavy())
        # برچسب «توان فعلی» هم همراه فیلد مخفی/نمایش داده شود
        lbl = self.form.labelForField(self.sp_existing)
        if lbl is not None:
            lbl.setVisible(is_increase and self._is_heavy())
        self._update_added()
        self.changed.emit()

    def _update_added(self) -> None:
        existing = self.sp_existing.value()
        requested = self.sp_requested.value()
        if (self._is_heavy() and self.cb_type.currentData() == REQUEST_INCREASE
                and requested > 0 and existing > 0):
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
        idx = self.cb_report_type.findData(project.report_type or REPORT_HEAVY)
        if idx >= 0:
            self.cb_report_type.setCurrentIndex(idx)
        self.ed_name.setText(project.name)
        self.ed_number.setText(project.report_number)
        self.ed_date.setText(project.date_jalali)
        self.ed_applicant.setText(project.applicant_name)
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
        self.ed_conductor.setText(project.conductor_type or project.cable_suggestion or "")
        self._fill_stations(project)
        self._fill_lines(project)
        self.ed_scenarios.setPlainText(project.conclusion_scenarios or "")
        secz = project.sectionalizer
        self.ed_secz_feeder.setText(secz.feeder_name or "")
        self.ed_secz_location.setText(secz.location or "")
        self.ed_secz_purpose.setText(secz.purpose or "")
        self.ed_secz_notes.setText(secz.notes or "")
        self._on_report_type_change()
        self._update_added()

    def save_to(self, project: Project) -> None:
        project.report_type = self.cb_report_type.currentData() or REPORT_HEAVY
        project.name = self.ed_name.text().strip()
        project.report_number = self.ed_number.text().strip()
        project.date_jalali = self.ed_date.text().strip()
        project.applicant_name = self.ed_applicant.text().strip()
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
        project.conductor_type = self.ed_conductor.text().strip()
        project.nearby_stations = self._read_stations()
        project.nearby_lines = self._read_lines()
        project.conclusion_scenarios = self.ed_scenarios.toPlainText().strip()
        project.sectionalizer.feeder_name = self.ed_secz_feeder.text().strip()
        project.sectionalizer.location = self.ed_secz_location.text().strip()
        project.sectionalizer.purpose = self.ed_secz_purpose.text().strip()
        project.sectionalizer.notes = self.ed_secz_notes.text().strip()
