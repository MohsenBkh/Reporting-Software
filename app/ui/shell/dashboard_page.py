# -*- coding: utf-8 -*-
"""Engineering Dashboard — وضعیت مطالعات و چک‌لیست اعتبارسنجی پروژه."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from app.ui.shell.design import SPACING
from app.ui.shell.dashboard_model import CheckItem
from app.ui.widgets import StatusBadge, page_header


class EngineeringDashboard(QWidget):
    open_requested = Signal(str)       # کلید مطالعه برای باز کردن تب

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"])
        root.setSpacing(SPACING["md"])
        root.addWidget(page_header("داشبورد مهندسی",
                                  "وضعیت مطالعات، اعتبارسنجی و بازبینی مهندس پروژه."))
        self.study_box = QFrame()
        self.study_box.setObjectName("DashCard")
        self.study_grid = QGridLayout(self.study_box)
        root.addWidget(self._title("وضعیت مطالعات"))
        root.addWidget(self.study_box)
        self.check_box = QFrame()
        self.check_box.setObjectName("DashCard")
        self.check_grid = QGridLayout(self.check_box)
        root.addWidget(self._title("اعتبارسنجی"))
        root.addWidget(self.check_box)
        root.addStretch(1)

    @staticmethod
    def _title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SectionTitle")
        return lbl

    @staticmethod
    def _clear(grid: QGridLayout) -> None:
        while grid.count():
            w = grid.takeAt(0).widget()
            if w is not None:
                w.deleteLater()

    def set_content(self, cards: list[dict], checks: list[CheckItem]) -> None:
        self._clear(self.study_grid)
        for row, c in enumerate(cards):
            self.study_grid.addWidget(QLabel(c["title"]), row, 0)
            self.study_grid.addWidget(StatusBadge(c["status_label"], c["badge"]), row, 1)
            btn = QPushButton("باز کردن")
            btn.setObjectName("ghost")
            btn.clicked.connect(lambda _=False, k=c["key"]: self.open_requested.emit(k))
            self.study_grid.addWidget(btn, row, 2)
        self._clear(self.check_grid)
        for row, it in enumerate(checks):
            self.check_grid.addWidget(QLabel(f"{it.glyph}  {it.label}"), row, 0)
            detail = QLabel(it.detail)
            detail.setObjectName("Muted")
            self.check_grid.addWidget(detail, row, 1)
