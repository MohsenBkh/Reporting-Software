# -*- coding: utf-8 -*-
"""داشبورد — پروژه‌های اخیر، پروژه جاری و وضعیت، آخرین گزارش‌ها، میانبر عملیات (v1.0.3)."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from app.ui.icons import icon
from app.ui.theme import tokens
from app.ui.excel_table import enable_excel_table
from app.ui.widgets import StatusBadge, page_header, section_title


class HomePage(QWidget):
    new_project_requested = Signal()
    open_project_requested = Signal()
    quick_import_requested = Signal()
    open_recent_requested = Signal(str)
    settings_requested = Signal()
    continue_requested = Signal(str)     # کلید مرحله بعد
    open_file_requested = Signal(str)

    def __init__(self, recent: list[str], theme: str = "light", parent=None) -> None:
        super().__init__(parent)
        self.recent = recent
        self.theme = theme
        self._next_key = "project"
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(14)
        root.addWidget(page_header("داشبورد",
                                   "تولید خودکار گزارش مطالعات فنی اتصال مصارف سنگین به شبکه توزیع"))

        # --- میانبر عملیات ---
        row = QHBoxLayout()
        row.setSpacing(12)
        self.quick: list[tuple[QPushButton, str]] = []
        for cap, desc, ic, sig in (
                ("پروژه جدید", "ایجاد پروژه مطالعه جدید", "plus", self.new_project_requested),
                ("باز کردن پروژه", "انتخاب فایل project.json", "folder", self.open_project_requested),
                ("تولید سریع از Excel", "از قالب استاندارد تا اولین پیش‌نویس گزارش", "excel", self.quick_import_requested),
                ("قالب Excel ورودی", "ذخیره قالب استاندارد ورود داده", "upload", None)):
            b = QPushButton(f"  {cap}\n  {desc}")
            b.setObjectName("QuickAction")
            b.setMinimumHeight(64)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(desc)
            if sig is not None:
                b.clicked.connect(sig.emit)
            else:
                b.clicked.connect(self._template)
            self.quick.append((b, ic))
            row.addWidget(b)
        root.addLayout(row)

        grid = QGridLayout()
        grid.setSpacing(12)
        root.addLayout(grid, 1)

        # --- پروژه جاری ---
        self.card_current = QFrame()
        self.card_current.setObjectName("Card")
        cv = QVBoxLayout(self.card_current)
        cv.setContentsMargins(16, 12, 16, 12)
        top = QHBoxLayout()
        top.addWidget(section_title("پروژه جاری"))
        top.addStretch(1)
        self.badge_status = StatusBadge("بدون پروژه", "pending")
        top.addWidget(self.badge_status)
        cv.addLayout(top)
        self.lbl_name = QLabel("پروژه‌ای باز نیست.")
        self.lbl_name.setObjectName("ProjectName")
        self.lbl_name.setWordWrap(True)
        cv.addWidget(self.lbl_name)
        self.lbl_meta = QLabel("")
        self.lbl_meta.setObjectName("Muted")
        self.lbl_meta.setWordWrap(True)
        cv.addWidget(self.lbl_meta)
        self.lbl_progress = QLabel("")
        cv.addWidget(self.lbl_progress)
        self.btn_continue = QPushButton("ادامه کار")
        self.btn_continue.setObjectName("primary")
        self.btn_continue.setVisible(False)
        self.btn_continue.clicked.connect(lambda: self.continue_requested.emit(self._next_key))
        cv.addWidget(self.btn_continue, 0, Qt.AlignRight)
        cv.addStretch(1)
        grid.addWidget(self.card_current, 0, 0)

        # --- آخرین گزارش‌ها ---
        card_r = QFrame()
        card_r.setObjectName("Card")
        rv = QVBoxLayout(card_r)
        rv.setContentsMargins(16, 12, 16, 12)
        rv.addWidget(section_title("آخرین گزارش‌ها"))
        self.tbl_reports = QTableWidget(0, 2)
        self.tbl_reports.setHorizontalHeaderLabels(["فایل", "تاریخ"])
        self._table(self.tbl_reports)
        self.tbl_reports.itemDoubleClicked.connect(
            lambda it: self.open_file_requested.emit(
                self.tbl_reports.item(it.row(), 0).data(Qt.UserRole) or ""))
        rv.addWidget(self.tbl_reports, 1)
        self.lbl_reports_hint = QLabel("برای باز کردن فایل روی آن دوبار کلیک کنید.")
        self.lbl_reports_hint.setObjectName("Muted")
        rv.addWidget(self.lbl_reports_hint)
        grid.addWidget(card_r, 0, 1)

        # --- پروژه‌های اخیر ---
        card_p = QFrame()
        card_p.setObjectName("Card")
        pv = QVBoxLayout(card_p)
        pv.setContentsMargins(16, 12, 16, 12)
        pv.addWidget(section_title("پروژه‌های اخیر"))
        self.tbl_recent = QTableWidget(0, 3)
        self.tbl_recent.setHorizontalHeaderLabels(["پروژه", "آخرین تغییر", "مسیر"])
        self._table(self.tbl_recent)
        self.tbl_recent.itemDoubleClicked.connect(
            lambda it: self.open_recent_requested.emit(
                self.tbl_recent.item(it.row(), 0).data(Qt.UserRole) or ""))
        pv.addWidget(self.tbl_recent, 1)
        h = QLabel("برای باز کردن پروژه روی آن دوبار کلیک کنید.")
        h.setObjectName("Muted")
        pv.addWidget(h)
        grid.addWidget(card_p, 1, 0, 1, 2)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.refresh_recent(recent)
        self.apply_icons(theme)

    @staticmethod
    def _table(t: QTableWidget) -> None:
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.setSelectionBehavior(QTableWidget.SelectItems)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        # v1.2.0: کپی/انتخاب اکسل‌گونه (Ctrl+C، Ctrl+A، منوی راست‌کلیک)
        enable_excel_table(t, editable=False, auto_add_row=False)

    def apply_icons(self, theme: str) -> None:
        self.theme = theme
        c = tokens(theme)["primary"]
        for b, name in self.quick:
            b.setIcon(icon(name, c, 24))

    # ------------------------------------------------------------------
    def refresh_recent(self, recent: list[str]) -> None:
        self.recent = recent
        t = self.tbl_recent
        t.setRowCount(0)
        for path in recent:
            p = Path(path)
            r = t.rowCount()
            t.insertRow(r)
            exists = p.exists()
            name = p.parent.name or p.name
            it0 = QTableWidgetItem(name + ("" if exists else "  (یافت نشد)"))
            it0.setData(Qt.UserRole, path)
            when = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if exists else "—"
            t.setItem(r, 0, it0)
            t.setItem(r, 1, QTableWidgetItem(when))
            t.setItem(r, 2, QTableWidgetItem(str(p)))
        t.resizeColumnsToContents()
        t.horizontalHeader().setStretchLastSection(True)

    def update_project(self, info: dict | None) -> None:
        """info: name, applicant, type, state, status_text, done, total, next_key, next_label, reports."""
        self.tbl_reports.setRowCount(0)
        if not info:
            self.badge_status.set_state("pending", "بدون پروژه")
            self.lbl_name.setText("پروژه‌ای باز نیست.")
            self.lbl_meta.setText("یک پروژه جدید بسازید یا پروژه موجود را باز کنید.")
            self.lbl_progress.setText("")
            self.btn_continue.setVisible(False)
            return
        self.badge_status.set_state(info["state"], info["status_text"])
        self.lbl_name.setText(info["name"] or "(بدون عنوان)")
        self.lbl_meta.setText(f"متقاضی: {info['applicant'] or '—'}  ·  {info['type']}  ·  {info['feeders']} فیدر")
        self.lbl_progress.setText(f"پیشرفت Workflow: {info['done']} از {info['total']} مرحله")
        self._next_key = info["next_key"]
        self.btn_continue.setText(f"ادامه: {info['next_label']}")
        self.btn_continue.setVisible(True)
        for path, when in info.get("reports", []):
            r = self.tbl_reports.rowCount()
            self.tbl_reports.insertRow(r)
            it = QTableWidgetItem(Path(path).name)
            it.setData(Qt.UserRole, path)
            self.tbl_reports.setItem(r, 0, it)
            self.tbl_reports.setItem(r, 1, QTableWidgetItem(when))
        self.tbl_reports.resizeColumnsToContents()
        self.tbl_reports.horizontalHeader().setStretchLastSection(True)

    def _template(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره قالب Excel استاندارد", "قالب_ورودی_گزارش.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        from app.excel.template import create_template
        from app.utils.errors import handle_error
        try:
            create_template(path)
        except Exception as exc:  # noqa: BLE001
            handle_error(self, exc, "ذخیره قالب Excel")
            return
        QMessageBox.information(self, "قالب Excel",
                                f"قالب استاندارد ذخیره شد:\n{path}\n\n"
                                "شیت‌ها: پروژه، فیدرها، پخش بار، پروفیل بار، پیش‌بینی")
