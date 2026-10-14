# -*- coding: utf-8 -*-
"""Property Inspector — نمای Context Sensitive شیء انتخاب‌شده."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QFrame, QGridLayout, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

from app.ui.shell.design import SPACING
from app.ui.shell.inspector_model import InspectorModel


class PropertyInspector(QWidget):
    include_toggled = Signal(str, bool)       # (کلید شیء، مقدار)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._key = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACING["sm"], SPACING["sm"], SPACING["sm"], SPACING["sm"])
        self.card = QFrame()
        self.card.setObjectName("InspectorCard")
        self.grid_host = QVBoxLayout(self.card)
        self.grid_host.setContentsMargins(SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"])
        self.grid_host.setSpacing(SPACING["sm"])
        self.title = QLabel("—")
        self.title.setObjectName("InspectorTitle")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("Muted")
        self.subtitle.setWordWrap(True)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(SPACING["lg"])
        self.grid.setVerticalSpacing(SPACING["xs"])
        self.chk_include = QCheckBox("درج در گزارش (Include in Report)")
        self.chk_include.toggled.connect(self._on_include)
        for w in (self.title, self.subtitle):
            self.grid_host.addWidget(w)
        self.grid_host.addLayout(self.grid)
        self.grid_host.addWidget(self.chk_include)
        self.grid_host.addStretch(1)
        outer.addWidget(self.card)
        outer.addStretch(1)
        self.show_model(InspectorModel(title="شیئی انتخاب نشده است"))

    def show_model(self, model: InspectorModel) -> None:
        self.title.setText(model.title)
        self.subtitle.setText(model.subtitle)
        self.subtitle.setVisible(bool(model.subtitle))
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for row, (key, value) in enumerate(model.rows):
            k, v = QLabel(key), QLabel(value)
            k.setObjectName("InspectorKey")
            v.setObjectName("InspectorValue")
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.grid.addWidget(k, row, 0)
            self.grid.addWidget(v, row, 1)
        self._key = model.include_key
        self.chk_include.blockSignals(True)
        self.chk_include.setVisible(model.include_key is not None)
        self.chk_include.setChecked(bool(model.include_value))
        self.chk_include.blockSignals(False)

    def _on_include(self, checked: bool) -> None:
        if self._key:
            self.include_toggled.emit(self._key, checked)
