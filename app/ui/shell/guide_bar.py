# -*- coding: utf-8 -*-
"""نوار راهنمای گام‌به‌گام (GuideBar) — گام جاری، الزامات ناتمام (قابل کلیک) و دکمه‌ها."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.core.guided_flow import GuideModel
from app.ui.shell.design import SPACING


class GuideBar(QFrame):
    goto_requested = Signal(str, str)        # (صفحه، فیلد)
    override_requested = Signal(str)         # کلید گام
    ack_protection_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("GuideBar")
        self._model = GuideModel()
        v = QVBoxLayout(self)
        v.setContentsMargins(SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"])
        v.setSpacing(SPACING["xs"])
        top = QHBoxLayout()
        self.lbl_title = QLabel("")
        self.lbl_title.setObjectName("GuideTitle")
        self.lbl_msg = QLabel("")
        self.lbl_msg.setObjectName("Muted")
        self.btn_go = QPushButton("ادامه ◀")
        self.btn_go.setObjectName("primary")
        self.btn_go.clicked.connect(self._on_go)
        self.btn_ack = QPushButton("تأیید بازبینی یافته‌های حفاظتی")
        self.btn_ack.clicked.connect(self.ack_protection_requested)
        self.btn_override = QPushButton("ادامه با وجود نقص")
        self.btn_override.setToolTip("گام بعد با وجود موارد ناتمام باز می‌شود (در گزارش هشدار درج می‌شود).")
        self.btn_override.clicked.connect(self._on_override)
        top.addWidget(self.lbl_title)
        top.addWidget(self.lbl_msg, 1)
        for b in (self.btn_ack, self.btn_override, self.btn_go):
            top.addWidget(b)
        v.addLayout(top)
        self.links = QHBoxLayout()
        self.links.setSpacing(SPACING["xs"])
        v.addLayout(self.links)

    def set_model(self, m: GuideModel) -> None:
        self._model = m
        self.setVisible(bool(m.title))
        self.lbl_title.setText(m.title)
        self.lbl_msg.setText(m.message)
        self.btn_go.setVisible(bool(m.goto) and not m.finished)
        self.btn_override.setVisible(m.can_override)
        self.btn_ack.setVisible(m.needs_protection_ack)
        while self.links.count():
            item = self.links.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for req in m.links:
            b = QPushButton(f"↗ {req.label}")
            b.setObjectName("ghost")
            b.setToolTip(f"رفتن به: {req.target}" + (f" ← {req.field}" if req.field else ""))
            b.clicked.connect(lambda _=False, t=req.target, f=req.field: self.goto_requested.emit(t, f))
            self.links.addWidget(b)
        if m.more:
            self.links.addWidget(QLabel(f"… و {m.more} مورد دیگر"))
        self.links.addStretch(1)

    def _on_go(self) -> None:
        self.goto_requested.emit(self._model.goto, self._model.goto_field)

    def _on_override(self) -> None:
        if self._model.step is not None:
            self.override_requested.emit(self._model.step.key)
