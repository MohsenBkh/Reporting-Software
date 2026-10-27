# -*- coding: utf-8 -*-
"""صفحه «اطلاعات پروژه» — فقط اطلاعات عمومی مشترک بین همهٔ مطالعات (v2.0.0).

شش فیلد عمومی: عنوان پروژه، شماره گزارش، تاریخ گزارش، نام پست فوق توزیع، نام امور و
نام کارشناس. اطلاعات اختصاصی هر مطالعه (متقاضی سنگین، ریکلوزر، سکشنالایزر) در بخش
«ورود داده» همان مطالعه وارد می‌شود؛ انتخاب نوع مطالعات هنگام ساخت پروژهٔ جدید
(یا از منوی «مطالعات») انجام می‌شود، نه در این صفحه.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QSpinBox,
                               QVBoxLayout, QWidget)

from app.core.models import Project
from app.core.report_coding import (OFFICE_CODES, STUDY_CODE_LABELS,
                                    describe_report_number, make_report_number)
from app.utils.jalali import today_jalali


class ProjectPage(QWidget):
    changed = Signal()

    def __init__(self, settings, parent=None) -> None:
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

        title = QLabel("اطلاعات پروژه")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        sub = QLabel("اطلاعات عمومی که در همهٔ گزارش‌ها (متقاضی سنگین، ریکلوزر، سکشنالایزر) مشترک است.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        root.addWidget(sub)

        card = QFrame()
        card.setObjectName("Card")
        form = QFormLayout(card)
        form.setLabelAlignment(Qt.AlignRight)
        form.setContentsMargins(18, 16, 18, 16)
        form.setVerticalSpacing(10)
        self.form = form
        self.ed_name = QLineEdit()
        self.ed_number = QLineEdit()
        self.ed_date = QLineEdit(today_jalali())
        self.ed_substation = QLineEdit()
        self.ed_office = QLineEdit()
        self.ed_expert = QLineEdit()
        form.addRow("عنوان پروژه:", self.ed_name)
        form.addRow("شماره گزارش:", self.ed_number)
        # --- v2.5.0: سازنده کد مدرک مطابق «کدگذاری مطالعات.xlsx» ---------------
        code_row = QHBoxLayout()
        self.cb_study_code = QComboBox()
        for code, label in STUDY_CODE_LABELS.items():
            self.cb_study_code.addItem(f"{label} ({code})", code)
        self.cb_office_code = QComboBox()
        for name, code in OFFICE_CODES.items():
            self.cb_office_code.addItem(f"{name} ({code})", code)
        self.sp_serial = QSpinBox()
        self.sp_serial.setRange(1, 999)
        self.sp_serial.setToolTip("شماره گزارش — از 001 شروع می‌شود")
        self.btn_make_code = QPushButton("درج کد")
        self.btn_make_code.setToolTip(
            "ساخت کد مدرک به قالب «کد مطالعه-کد امور-شماره» (مثال: PD-13-001) و درج در «شماره گزارش»")
        code_row.addWidget(self.cb_study_code, 2)
        code_row.addWidget(self.cb_office_code, 2)
        code_row.addWidget(self.sp_serial, 1)
        code_row.addWidget(self.btn_make_code, 1)
        form.addRow("کدگذاری مدرک:", code_row)
        self.lbl_code_hint = QLabel("")
        self.lbl_code_hint.setObjectName("Muted")
        self.lbl_code_hint.setWordWrap(True)
        form.addRow("", self.lbl_code_hint)
        self.btn_make_code.clicked.connect(self._insert_code)
        self.ed_number.textChanged.connect(self._update_code_hint)
        form.addRow("تاریخ گزارش:", self.ed_date)
        form.addRow("نام پست فوق توزیع:", self.ed_substation)
        form.addRow("نام امور:", self.ed_office)
        form.addRow("نام کارشناس:", self.ed_expert)
        root.addWidget(card)
        root.addStretch(1)

        self._loading = False
        for w in (self.ed_name, self.ed_number, self.ed_date, self.ed_substation,
                  self.ed_office, self.ed_expert):
            w.textChanged.connect(self._on_change)

    def focus_field(self, name: str) -> bool:
        w = {"ed_name": self.ed_name, "ed_number": self.ed_number, "ed_date": self.ed_date,
             "ed_substation": self.ed_substation, "ed_office": self.ed_office,
             "ed_expert": self.ed_expert}.get(name)
        if w is None:
            return False
        w.setFocus()
        w.selectAll()
        return True

    def _on_change(self, *_a) -> None:
        if not self._loading:
            self.changed.emit()

    # ------------------------------------------------------------------
    # v2.5.0 — کدگذاری مدرک
    # ------------------------------------------------------------------
    def _insert_code(self) -> None:
        """ساخت کد از سه جزء انتخابی و درج در فیلد «شماره گزارش»."""
        code = make_report_number(self.cb_study_code.currentData(),
                                  self.cb_office_code.currentData(),
                                  self.sp_serial.value())
        self.ed_number.setText(code)
        # اگر «نام امور» خالی است، از انتخاب کدگذاری پر شود
        if not self.ed_office.text().strip():
            office = self.cb_office_code.currentText().split("(")[0].strip()
            self.ed_office.setText(office)

    def _update_code_hint(self, *_a) -> None:
        text = self.ed_number.text().strip()
        if not text:
            self.lbl_code_hint.setText("")
            return
        desc = describe_report_number(text)
        self.lbl_code_hint.setText(
            desc if desc else
            "⚠ قالب کد با ساختار کدگذاری مطالعات (مثل PD-13-001) هم‌خوان نیست.")

    # ------------------------------------------------------------------
    def load_from(self, project: Project) -> None:
        from app.core.report_coding import (office_code_for_name, parse_report_number,
                                            study_code_for_report_type)
        self._loading = True
        # پیش‌فرض‌های سازنده کد از وضعیت پروژه (کد موجود > نوع مطالعه/نام امور)
        parsed = parse_report_number(project.report_number)
        sc = parsed[0] if parsed else study_code_for_report_type(project.report_type)
        oc = parsed[1] if parsed else office_code_for_name(project.office)
        if sc:
            i = self.cb_study_code.findData(sc)
            if i >= 0:
                self.cb_study_code.setCurrentIndex(i)
        if oc:
            i = self.cb_office_code.findData(oc)
            if i >= 0:
                self.cb_office_code.setCurrentIndex(i)
        if parsed:
            self.sp_serial.setValue(parsed[2])
        self.ed_name.setText(project.name)
        self.ed_number.setText(project.report_number)
        self.ed_date.setText(project.date_jalali)
        self.ed_substation.setText(project.substation)
        self.ed_office.setText(project.office)
        self.ed_expert.setText(project.expert_name)
        self._loading = False

    def save_to(self, project: Project) -> None:
        project.name = self.ed_name.text().strip()
        project.report_number = self.ed_number.text().strip()
        project.date_jalali = self.ed_date.text().strip()
        project.substation = self.ed_substation.text().strip()
        project.office = self.ed_office.text().strip()
        project.expert_name = self.ed_expert.text().strip()
