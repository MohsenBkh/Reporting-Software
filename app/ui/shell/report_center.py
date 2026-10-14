# -*- coding: utf-8 -*-
"""Report Center یکپارچه: انتخاب مطالعات ← پیش‌نمایش/ویرایش ← تولید خروجی (Word).

«پیش‌نمایش گزارش» و «تولید گزارش» دیگر صفحه‌های جدا نیستند؛ سه تب یک مرکز واحدند و
«گزارش جاری» (plan) بالای مرکز مشخص می‌کند پیش‌نمایش/تولید برای کدام خروجی است.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton, QTabWidget,
                               QVBoxLayout, QWidget)

from app.report.composer import plan_reports
from app.ui.shell.design import SPACING

TAB_KEYS = ("select", "preview", "generate", "ai")
PLAN_TO_REPORT_TYPE = {"heavy": "heavy", "recloser": "recloser", "sectionalizer": "sectionalizer",
                       "combined_protection": "combined_protection"}


class ReportCenter(QWidget):
    plan_changed = Signal(str)            # کلید گزارش جاری
    generate_all_requested = Signal(list)

    def __init__(self, selection_page: QWidget, preview_page: QWidget, generate_page: QWidget,
                 manager, get_workspace: Callable, ai_page: Optional[QWidget] = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.manager, self._ws = manager, get_workspace
        self.selection_page, self.preview_page, self.generate_page = (
            selection_page, preview_page, generate_page)
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        bar.setContentsMargins(SPACING["lg"], SPACING["sm"], SPACING["lg"], SPACING["sm"])
        bar.addWidget(QLabel("گزارش جاری:"))
        self.cb_plan = QComboBox()
        self.cb_plan.setMinimumWidth(320)
        self.cb_plan.currentIndexChanged.connect(self._on_plan)
        bar.addWidget(self.cb_plan)
        self.btn_all = QPushButton("تولید همهٔ گزارش‌ها")
        self.btn_all.setToolTip("گزارش‌ها به‌ترتیب و یکی‌یکی تولید می‌شوند.")
        self.btn_all.clicked.connect(self._generate_all)
        bar.addWidget(self.btn_all)
        bar.addStretch(1)
        root.addLayout(bar)
        self.tabs = QTabWidget()
        self.tabs.addTab(selection_page, "انتخاب مطالعات و بخش‌ها")
        self.tabs.addTab(preview_page, "پیش‌نمایش و ویرایش متن")
        self.tabs.addTab(generate_page, "تولید و خروجی")
        self.ai_page = ai_page
        if ai_page is not None:
            self.tabs.addTab(ai_page, "دستیار هوش مصنوعی")
        root.addWidget(self.tabs, 1)

    def show_tab(self, key: str) -> None:
        if key in TAB_KEYS:
            self.tabs.setCurrentIndex(TAB_KEYS.index(key))

    def plans(self):
        ws = self._ws()
        return plan_reports(ws.selection, ws.report_prefs.output_mode) if ws else []

    def refresh_plans(self) -> None:
        """بازسازی فهرست «گزارش جاری» و انتخاب گزارشی که با ``report_type`` پروژه می‌خواند."""
        self._loading = True
        plans = self.plans()
        current_type = getattr(self.manager.project, "report_type", "") if self.manager.project else ""
        keep = next((i for i, p in enumerate(plans)
                     if PLAN_TO_REPORT_TYPE.get(p.key) == current_type), 0)
        self.cb_plan.clear()
        for p in plans:
            self.cb_plan.addItem(p.title, p.key)
        if plans:
            self.cb_plan.setCurrentIndex(keep)
        self.btn_all.setEnabled(len(plans) > 1)
        self._loading = False

    def current_plan_key(self) -> str:
        return self.cb_plan.currentData() or ""

    def _on_plan(self, _i: int) -> None:
        if not self._loading and self.cb_plan.currentData():
            self.plan_changed.emit(self.cb_plan.currentData())

    def _generate_all(self) -> None:
        keys = [p.key for p in self.plans()]
        if keys:
            self.generate_all_requested.emit(keys)
