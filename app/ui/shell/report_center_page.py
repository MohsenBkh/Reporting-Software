# -*- coding: utf-8 -*-
"""Report Center — انتخاب مطالعات، شکل خروجی و ترتیب/فعال‌بودن بخش‌های گزارش حفاظتی.

پیش‌نمایش و تولید خروجی در همان Report Center یکپارچه (``app/ui/shell/report_center.py``)
و با صفحه‌های «پیش‌نمایش» و «تولید گزارش» موجود انجام می‌شود؛ این صفحه فقط «انتخاب» است.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QPushButton, QRadioButton,
                               QVBoxLayout, QWidget)

from app.core.studies import STUDY_LABELS_FA, StudyKind
from app.core.workspace import OUTPUT_COMBINED, OUTPUT_SEPARATE
from app.report.composer import ReportComposer, plan_reports
from app.ui.shell.design import SPACING
from app.ui.widgets import page_header


class ReportCenterPage(QWidget):
    changed = Signal()

    def __init__(self, manager, get_workspace: Callable, parent=None) -> None:
        super().__init__(parent)
        self.manager, self._ws = manager, get_workspace
        self._loading = False
        self.composer = ReportComposer()
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"])
        root.setSpacing(SPACING["md"])
        root.addWidget(page_header("انتخاب مطالعات و بخش‌های گزارش",
                                  "مطالعاتی که باید گزارش شوند، شکل خروجی و ترتیب بخش‌ها را مشخص کنید."))
        row = QHBoxLayout()
        root.addLayout(row, 1)
        col = QVBoxLayout()
        row.addLayout(col, 1)
        # --- مطالعات ---
        card = QFrame()
        card.setObjectName("Card")
        cv = QVBoxLayout(card)
        t = QLabel("مطالعات")
        t.setObjectName("CardTitle")
        cv.addWidget(t)
        self.chk: dict[StudyKind, QCheckBox] = {}
        for kind in StudyKind:
            c = QCheckBox(STUDY_LABELS_FA[kind])
            c.toggled.connect(self._on_selection)
            self.chk[kind] = c
            cv.addWidget(c)
        col.addWidget(card)
        # --- خروجی ---
        card2 = QFrame()
        card2.setObjectName("Card")
        c2 = QVBoxLayout(card2)
        t2 = QLabel("خروجی مطالعات حفاظتی")
        t2.setObjectName("CardTitle")
        c2.addWidget(t2)
        self.rb_combined = QRadioButton("یک گزارش ترکیبی")
        self.rb_separate = QRadioButton("دو گزارش مستقل")
        grp = QButtonGroup(self)
        for rb in (self.rb_combined, self.rb_separate):
            grp.addButton(rb)
            rb.toggled.connect(self._on_output)
            c2.addWidget(rb)
        self.lbl_plan = QLabel("")
        self.lbl_plan.setObjectName("Muted")
        self.lbl_plan.setWordWrap(True)
        c2.addWidget(self.lbl_plan)
        col.addWidget(card2)
        col.addStretch(1)
        # --- بخش‌ها ---
        card3 = QFrame()
        card3.setObjectName("Card")
        c3 = QVBoxLayout(card3)
        t3 = QLabel("بخش‌های گزارش حفاظتی (ترتیب قابل تغییر)")
        t3.setObjectName("CardTitle")
        c3.addWidget(t3)
        self.sections = QListWidget()
        self.sections.itemChanged.connect(self._on_sections)
        c3.addWidget(self.sections, 1)
        mv = QHBoxLayout()
        for text, delta in (("▲ بالا", -1), ("▼ پایین", 1)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, d=delta: self._move(d))
            mv.addWidget(b)
        mv.addStretch(1)
        c3.addLayout(mv)
        row.addWidget(card3, 1)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        ws = self._ws()
        if ws is None:
            return
        self._loading = True
        for kind, c in self.chk.items():
            c.setChecked(ws.selection.is_selected(kind))
        (self.rb_combined if ws.report_prefs.output_mode == OUTPUT_COMBINED
         else self.rb_separate).setChecked(True)
        both = ws.selection.recloser and ws.selection.sectionalizer
        self.rb_combined.setEnabled(both)
        self.rb_separate.setEnabled(both)
        self.sections.clear()
        disabled = set(ws.report_prefs.disabled_sections)
        for comp in self.composer.ordered(_OrderOnly(ws.report_prefs)):
            it = QListWidgetItem(comp.title)
            it.setData(Qt.UserRole, comp.key)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked if comp.key in disabled else Qt.Checked)
            self.sections.addItem(it)
        self._loading = False
        self._update_plan()

    def plans(self):
        ws = self._ws()
        return plan_reports(ws.selection, ws.report_prefs.output_mode) if ws else []

    def _update_plan(self) -> None:
        self.lbl_plan.setText("خروجی: " + ("، ".join(p.filename_stem for p in self.plans()) or "—"))

    def _on_selection(self, *_a) -> None:
        ws = self._ws()
        if ws is None or self._loading:
            return
        for kind, c in self.chk.items():
            setattr(ws.selection, kind.value, c.isChecked())
        both = ws.selection.recloser and ws.selection.sectionalizer
        self.rb_combined.setEnabled(both)
        self.rb_separate.setEnabled(both)
        self._update_plan()
        self.changed.emit()

    def _on_output(self, *_a) -> None:
        ws = self._ws()
        if ws is None or self._loading:
            return
        ws.report_prefs.output_mode = (OUTPUT_COMBINED if self.rb_combined.isChecked()
                                       else OUTPUT_SEPARATE)
        self._update_plan()
        self.changed.emit()

    def _on_sections(self, *_a) -> None:
        ws = self._ws()
        if ws is None or self._loading:
            return
        order, disabled = [], []
        for i in range(self.sections.count()):
            it = self.sections.item(i)
            key = it.data(Qt.UserRole)
            order.append(key)
            if it.checkState() != Qt.Checked:
                disabled.append(key)
        ws.report_prefs.section_order, ws.report_prefs.disabled_sections = order, disabled
        self.changed.emit()

    def _move(self, delta: int) -> None:
        row = self.sections.currentRow()
        new = row + delta
        if row < 0 or not 0 <= new < self.sections.count():
            return
        self._loading = True
        it = self.sections.takeItem(row)
        self.sections.insertItem(new, it)
        self.sections.setCurrentRow(new)
        self._loading = False
        self._on_sections()


class _OrderOnly:
    """آداپتور: ``ReportComposer.ordered`` فقط ترتیب را بخواند (وضعیت تیک جدا اعمال می‌شود)."""

    def __init__(self, prefs) -> None:
        self.section_order = list(prefs.section_order)
        self.disabled_sections: list[str] = []
