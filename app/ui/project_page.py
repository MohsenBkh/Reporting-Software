# -*- coding: utf-8 -*-
"""صفحه «اطلاعات پروژه» — فقط اطلاعات عمومی مشترک بین همهٔ مطالعات (v2.0.0).

شش فیلد عمومی: عنوان پروژه، شماره گزارش، تاریخ گزارش، نام پست فوق توزیع، نام امور و
نام کارشناس. اطلاعات اختصاصی هر مطالعه (متقاضی سنگین، ریکلوزر، سکشنالایزر) در بخش
«ورود داده» همان مطالعه وارد می‌شود؛ انتخاب نوع مطالعات هنگام ساخت پروژهٔ جدید
(یا از منوی «مطالعات») انجام می‌شود، نه در این صفحه.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFormLayout, QFrame, QLabel, QLineEdit, QScrollArea,
                               QVBoxLayout, QWidget)

from app.core.models import Project
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
    def load_from(self, project: Project) -> None:
        self._loading = True
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
