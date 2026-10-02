# -*- coding: utf-8 -*-
"""صفحه «پیش‌نمایش گزارش» — ساختار، پیش‌نمایش بخش‌ها، ویرایش متن، جدول‌ها و نمودارها (v1.0.3)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QSplitter, QTabWidget,
                               QTextBrowser, QTextEdit, QVBoxLayout, QWidget)

from app.report import pipeline
from app.report.sections import FigureBlock, Paragraph, TableSpec
from app.ui.widgets import StatusBadge, page_header


class PreviewPage(QWidget):
    changed = Signal()

    def __init__(self, manager, settings, analysis, parent=None) -> None:
        super().__init__(parent)
        self.manager, self.settings, self.analysis = manager, settings, analysis
        self.report = None
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header(
            "پیش‌نمایش گزارش",
            "ساختار گزارش، متن بخش‌ها، جدول‌ها و نمودارها. متن هر بخش قابل ویرایش است و با تولید مجدد حفظ می‌شود."))

        bar = QHBoxLayout()
        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("Muted")
        bar.addWidget(self.lbl_info, 1)
        self.btn_refresh = QPushButton("به‌روزرسانی پیش‌نمایش")
        bar.addWidget(self.btn_refresh)
        root.addLayout(bar)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)
        self.section_list = QListWidget()
        self.section_list.currentRowChanged.connect(self._on_section)
        splitter.addWidget(self.section_list)

        self.tabs = QTabWidget()
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setStyleSheet("QTextBrowser { background: #FFFFFF; color: #111111; border: 1px solid #C8CED6; }")
        self.tabs.addTab(self.browser, "پیش‌نمایش")
        edit = QWidget()
        ev = QVBoxLayout(edit)
        hint = QLabel("متن بخش انتخابی (جدول‌ها و شکل‌ها بدون تغییر می‌مانند):")
        hint.setObjectName("Muted")
        ev.addWidget(hint)
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        ev.addWidget(self.editor, 1)
        eb = QHBoxLayout()
        self.btn_save_text = QPushButton("ذخیره ویرایش متن")
        self.btn_save_text.setObjectName("primary")
        self.btn_reset_text = QPushButton("بازگشت به متن خودکار")
        self.badge_manual = StatusBadge("ویرایش دستی فعال", "info")
        self.badge_manual.setVisible(False)
        eb.addWidget(self.btn_save_text)
        eb.addWidget(self.btn_reset_text)
        eb.addWidget(self.badge_manual)
        eb.addStretch(1)
        ev.addLayout(eb)
        self.tabs.addTab(edit, "ویرایش متن")
        splitter.addWidget(self.tabs)
        splitter.setSizes([260, 740])

        self.btn_refresh.clicked.connect(lambda: self.refresh(force=True))
        self.btn_save_text.clicked.connect(self.save_manual_text)
        self.btn_reset_text.clicked.connect(self.reset_manual_text)

    # ------------------------------------------------------------------
    def refresh(self, force: bool = False) -> None:
        keep = self.section_list.currentRow()
        self.section_list.clear()
        self.browser.clear()
        if not self.manager.project:
            self.report = None
            return
        self.report = self.analysis.get(force=force)
        if self.report is None:
            return
        n_tbl = sum(1 for s in self.report.sections for b in s.blocks if isinstance(b, TableSpec))
        n_fig = sum(1 for s in self.report.sections for b in s.blocks if isinstance(b, FigureBlock))
        self.lbl_info.setText(f"{len(self.report.sections)} بخش · {n_tbl} جدول · {n_fig} شکل")
        for i, sec in enumerate(self.report.sections):
            mark = "  ✎" if getattr(sec, "manual", False) else ""
            title = sec.title if sec.key.startswith("appendix") else f"{i + 1}- {sec.title}"
            self.section_list.addItem(QListWidgetItem(title + mark))
        self.browser.setHtml(pipeline.report_to_html(self.report, self.manager.project, self.settings))
        if self.section_list.count():
            self.section_list.setCurrentRow(max(0, keep))

    def _on_section(self, row: int) -> None:
        if self.report is None or not (0 <= row < len(self.report.sections)):
            return
        sec = self.report.sections[row]
        self.editor.setPlainText("\n\n".join(p.text for p in sec.paragraphs()))
        self.editor.setProperty("row", row)
        manual = bool((self.manager.project.manual_texts or {}).get(sec.key, "").strip())
        self.badge_manual.setVisible(manual)
        editable = not sec.key.startswith("appendix")
        for w in (self.editor, self.btn_save_text, self.btn_reset_text):
            w.setEnabled(editable)
        # حرکت به بخش در پیش‌نمایش
        self.browser.scrollToAnchor(f"sec{row}")
        cursor = self.browser.document().find(sec.title)
        if not cursor.isNull():
            self.browser.setTextCursor(cursor)
            self.browser.ensureCursorVisible()

    def save_manual_text(self) -> None:
        if self.report is None:
            return
        row = self.editor.property("row")
        if row is None or not (0 <= row < len(self.report.sections)):
            return
        sec = self.report.sections[row]
        manual = self.editor.toPlainText().strip()
        auto = "\n\n".join(p.text for p in sec.paragraphs())
        if not manual:
            QMessageBox.warning(self, "ویرایش متن", "متن بخش نمی‌تواند خالی باشد. برای بازگشت به متن خودکار از دکمه مربوط استفاده کنید.")
            return
        if manual == auto:
            QMessageBox.information(self, "ویرایش متن", "متن تغییری نکرده است.")
            return
        if not getattr(sec, "manual", False):
            ret = QMessageBox.question(
                self, "ویرایش متن",
                "ویرایش شما جایگزین متن خودکار این بخش می‌شود و در تولیدهای بعدی نیز حفظ خواهد شد.\nادامه می‌دهید؟",
                QMessageBox.Yes | QMessageBox.No)
            if ret != QMessageBox.Yes:
                return
        self.manager.project.manual_texts[sec.key] = manual
        self.manager.dirty = True
        self.analysis.invalidate()
        self.changed.emit()
        self.refresh(force=True)

    def reset_manual_text(self) -> None:
        row = self.editor.property("row")
        if self.report is None or row is None:
            return
        sec = self.report.sections[row]
        if self.manager.project.manual_texts.pop(sec.key, None) is not None:
            self.manager.dirty = True
            self.analysis.invalidate()
            self.changed.emit()
            self.refresh(force=True)
