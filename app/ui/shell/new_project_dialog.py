# -*- coding: utf-8 -*-
"""پنجرهٔ «پروژهٔ جدید» — انتخاب نوع مطالعات (چندتایی) پیش از ساخت پروژه."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout)

from app.core.studies import STUDY_LABELS_FA, StudyKind, StudySelection

DESCRIPTIONS = {
    StudyKind.HEAVY: "تأمین برق یا افزایش قدرت متقاضیان یک مگاوات و بالاتر (پخش بار، پیش‌بینی، سناریوها).",
    StudyKind.RECLOSER: "جایابی و تنظیم ریکلوزر و هماهنگی حفاظتی با رله بالادست.",
    StudyKind.SECTIONALIZER: "جایابی و تنظیم سکشنالایزر و هماهنگی با ریکلوزر.",
    StudyKind.FEEDER_DEV: "توسعه و اصلاح فیدر: اصلاح خط موجود، احداث فیدر جدید یا "
                          "بازآرایی شبکه با مقایسه پخش بار قبل و بعد از طرح.",
}


class NewProjectDialog(QDialog):
    """حداقل یک مطالعه باید انتخاب شود؛ ورودی هر مطالعه بعداً جداگانه وارد می‌شود."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("پروژه جدید — نوع مطالعات")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        head = QLabel("مطالعاتی که در این پروژه انجام می‌شود را انتخاب کنید:")
        head.setObjectName("SectionTitle")
        lay.addWidget(head)
        self.checks: dict[StudyKind, QCheckBox] = {}
        for kind in StudyKind:
            cb = QCheckBox(STUDY_LABELS_FA[kind])
            cb.setToolTip(DESCRIPTIONS[kind])
            cb.toggled.connect(self._validate)
            self.checks[kind] = cb
            lay.addWidget(cb)
            d = QLabel(DESCRIPTIONS[kind])
            d.setObjectName("Muted")
            d.setWordWrap(True)
            d.setContentsMargins(24, 0, 0, 4)
            lay.addWidget(d)
        self.lbl_hint = QLabel("ریکلوزر و سکشنالایزر را می‌توان مستقل یا در یک گزارش ترکیبی گزارش کرد.")
        self.lbl_hint.setObjectName("Muted")
        self.lbl_hint.setWordWrap(True)
        lay.addWidget(self.lbl_hint)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                       | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        self.checks[StudyKind.HEAVY].setChecked(True)
        self._validate()

    def selection(self) -> StudySelection:
        return StudySelection(**{k.value: c.isChecked() for k, c in self.checks.items()})

    def _validate(self, *_a) -> None:
        ok = not self.selection().is_empty()
        btn = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if btn is not None:
            btn.setEnabled(ok)
