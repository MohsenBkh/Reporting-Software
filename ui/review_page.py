# -*- coding: utf-8 -*-
"""صفحه «بازبینی مهندس» — Accept / Edit / Reject / Override / Comment (v1.0.3).

تصمیمات در project.reviews ذخیره می‌شوند و با Generate مجدد از بین نمی‌روند.
Reject و Override بدون ثبت توضیح (Comment) پذیرفته نمی‌شوند تا ردپای مهندسی بماند.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QMessageBox, QPlainTextEdit,
                               QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget)

from app.core.findings import (DOMAIN_LABELS_FA, SEVERITY_LABELS_FA, STATUS_LABELS_FA,
                               Finding, set_decision)
from app.core.models import (REVIEW_ACCEPTED, REVIEW_EDITED, REVIEW_OVERRIDDEN,
                             REVIEW_PENDING, REVIEW_REJECTED)
from app.ui.icons import icon
from app.ui.theme import tokens
from app.ui.widgets import StatusBadge, page_header, section_title

SEV_STATE = {"normal": "normal", "warning": "warning", "error": "error", "review": "review"}
DEC_STATE = {REVIEW_PENDING: "pending", REVIEW_ACCEPTED: "completed", REVIEW_EDITED: "info",
             REVIEW_OVERRIDDEN: "info", REVIEW_REJECTED: "warning"}
DEC_MARK = {REVIEW_PENDING: "○", REVIEW_ACCEPTED: "✓", REVIEW_EDITED: "✎",
            REVIEW_OVERRIDDEN: "⇄", REVIEW_REJECTED: "✕"}


class ReviewPage(QWidget):
    changed = Signal()

    def __init__(self, manager, settings, analysis, parent=None) -> None:
        super().__init__(parent)
        self.manager, self.settings, self.analysis = manager, settings, analysis
        self._findings: list[Finding] = []
        self._current: Finding | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header(
            "بازبینی مهندس",
            "نتیجه‌گیری‌های تولیدشده را تأیید، ویرایش، رد یا Override کنید. تصمیمات شما هنگام تولید مجدد گزارش حفظ می‌شود."))

        top = QHBoxLayout()
        self.lbl_summary = QLabel("")
        self.lbl_summary.setObjectName("Muted")
        top.addWidget(self.lbl_summary, 1)
        self.cb_filter = QComboBox()
        self.cb_filter.addItems(["همه موارد", "در انتظار بازبینی", "تصمیم‌گرفته‌شده", "نیازمند توجه (هشدار/خطا/کهنه)"])
        self.cb_filter.currentIndexChanged.connect(self._fill_list)
        top.addWidget(self.cb_filter)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_select)
        splitter.addWidget(self.list)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(12, 0, 0, 0)
        rv.setSpacing(8)
        head = QHBoxLayout()
        self.lbl_title = section_title("—")
        head.addWidget(self.lbl_title, 1)
        self.b_sev = StatusBadge("", "normal")
        self.b_dec = StatusBadge("", "pending")
        self.b_stale = StatusBadge("ورودی تغییر کرده — بازبینی مجدد", "review")
        head.addWidget(self.b_sev)
        head.addWidget(self.b_dec)
        head.addWidget(self.b_stale)
        rv.addLayout(head)
        self.lbl_rule = QLabel("")
        self.lbl_rule.setObjectName("Muted")
        rv.addWidget(self.lbl_rule)

        rv.addWidget(QLabel("متن تولیدشده از Rule Engine (فقط‌خواندنی):"))
        self.txt_auto = QTextEdit()
        self.txt_auto.setReadOnly(True)
        self.txt_auto.setMaximumHeight(120)
        rv.addWidget(self.txt_auto)

        rv.addWidget(QLabel("متن نهایی در گزارش (برای Edit / Override ویرایش کنید):"))
        self.txt_final = QTextEdit()
        self.txt_final.setAcceptRichText(False)
        self.txt_final.setMaximumHeight(140)
        rv.addWidget(self.txt_final)

        rv.addWidget(QLabel("توضیح مهندس (Comment — برای Reject و Override الزامی است):"))
        self.txt_comment = QPlainTextEdit()
        self.txt_comment.setMaximumHeight(70)
        rv.addWidget(self.txt_comment)

        btns = QHBoxLayout()
        self.b_accept = QPushButton(" تأیید (Accept)")
        self.b_accept.setObjectName("primary")
        self.b_edit = QPushButton(" ویرایش (Edit)")
        self.b_override = QPushButton(" Override")
        self.b_reject = QPushButton(" رد (Reject)")
        self.b_reject.setObjectName("danger")
        self.b_comment = QPushButton(" ثبت توضیح")
        self.b_reset = QPushButton(" بازگشت به خودکار")
        for b, tip in ((self.b_accept, "نتیجه خودکار بدون تغییر در گزارش می‌آید."),
                       (self.b_edit, "متن ویرایش‌شده جایگزین متن خودکار می‌شود."),
                       (self.b_override, "نتیجه مهندس جایگزین نتیجه Rule می‌شود؛ توضیح الزامی است."),
                       (self.b_reject, "این مورد از گزارش حذف می‌شود؛ توضیح الزامی است."),
                       (self.b_comment, "فقط توضیح مهندس ثبت می‌شود (در پیوست ب گزارش می‌آید)."),
                       (self.b_reset, "تصمیم قبلی پاک و متن خودکار برگردانده می‌شود.")):
            b.setToolTip(tip)
            btns.addWidget(b)
        btns.addStretch(1)
        rv.addLayout(btns)
        rv.addStretch(1)
        splitter.addWidget(right)
        splitter.setSizes([380, 620])

        self.b_accept.clicked.connect(lambda: self._decide(REVIEW_ACCEPTED))
        self.b_edit.clicked.connect(lambda: self._decide(REVIEW_EDITED))
        self.b_override.clicked.connect(lambda: self._decide(REVIEW_OVERRIDDEN))
        self.b_reject.clicked.connect(lambda: self._decide(REVIEW_REJECTED))
        self.b_comment.clicked.connect(self._save_comment)
        self.b_reset.clicked.connect(self._reset)
        self.apply_icons()
        self._show(None)

    def apply_icons(self) -> None:
        c = tokens(self.settings.theme)
        on = c["on_primary"]
        for b, name, col in ((self.b_accept, "check", on), (self.b_edit, "edit", c["text"]),
                             (self.b_override, "override", c["text"]), (self.b_reject, "x", c["danger"]),
                             (self.b_comment, "comment", c["text"]), (self.b_reset, "refresh", c["text"])):
            b.setIcon(icon(name, col, 18))

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        keep = self._current.key if self._current else None
        report = self.analysis.get() if self.manager.project else None
        self._findings = list(report.findings) if report else []
        self._fill_list(select_key=keep)

    def _visible(self) -> list[Finding]:
        mode = self.cb_filter.currentIndex()
        if mode == 1:
            return [f for f in self._findings if f.status == REVIEW_PENDING]
        if mode == 2:
            return [f for f in self._findings if f.status != REVIEW_PENDING]
        if mode == 3:
            return [f for f in self._findings if f.needs_attention]
        return list(self._findings)

    def _fill_list(self, *_a, select_key: str | None = None) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        vis = self._visible()
        for f in vis:
            txt = (f"{DEC_MARK.get(f.status, '○')}  {f.feeder_name} — {DOMAIN_LABELS_FA.get(f.domain, f.domain)}"
                   f"  [{SEVERITY_LABELS_FA[f.severity]}]" + ("  ⚠" if f.stale else ""))
            it = QListWidgetItem(txt)
            it.setData(Qt.UserRole, f.key)
            self.list.addItem(it)
        self.list.blockSignals(False)
        total = len(self._findings)
        pending = sum(1 for f in self._findings if f.needs_attention)
        self.lbl_summary.setText(f"{total} مورد · {pending} مورد نیازمند توجه")
        row = 0
        if select_key:
            row = next((i for i, f in enumerate(vis) if f.key == select_key), 0)
        if vis:
            self.list.setCurrentRow(row)
            self._on_select(row)
        else:
            self._show(None)

    def _on_select(self, row: int) -> None:
        vis = self._visible()
        self._show(vis[row] if 0 <= row < len(vis) else None)

    def _show(self, f: Finding | None) -> None:
        self._current = f
        for w in (self.b_accept, self.b_edit, self.b_override, self.b_reject, self.b_comment, self.b_reset,
                  self.txt_final, self.txt_comment):
            w.setEnabled(f is not None)
        if f is None:
            self.lbl_title.setText("موردی برای بازبینی وجود ندارد")
            for w in (self.b_sev, self.b_dec, self.b_stale):
                w.setVisible(False)
            self.lbl_rule.setText("")
            self.txt_auto.clear(); self.txt_final.clear(); self.txt_comment.clear()
            return
        self.lbl_title.setText(f"{f.feeder_name} — {DOMAIN_LABELS_FA.get(f.domain, f.domain)}")
        self.b_sev.setVisible(True); self.b_dec.setVisible(True)
        self.b_sev.set_state(SEV_STATE[f.severity], SEVERITY_LABELS_FA[f.severity])
        self.b_dec.set_state(DEC_STATE.get(f.status, "pending"), STATUS_LABELS_FA.get(f.status, f.status))
        self.b_stale.setVisible(f.stale)
        self.lbl_rule.setText(f"Rule: {f.rule_id} — {f.rule_name}")
        self.txt_auto.setPlainText(f.auto_text)
        self.txt_final.setPlainText(f.final_text or f.auto_text)
        self.txt_comment.setPlainText(f.comment)

    # ------------------------------------------------------------------
    def _commit(self, f: Finding, status: str, replacement: str = "") -> None:
        comment = self.txt_comment.toPlainText()
        set_decision(self.manager.project, f, status, comment, replacement)
        self.manager.dirty = True
        self.analysis.invalidate()
        self.changed.emit()
        self.refresh()

    def _decide(self, status: str) -> None:
        f = self._current
        if f is None:
            return
        comment = self.txt_comment.toPlainText().strip()
        final = self.txt_final.toPlainText().strip()
        if status in (REVIEW_REJECTED, REVIEW_OVERRIDDEN) and not comment:
            QMessageBox.warning(self, "توضیح الزامی است",
                                "برای رد یا Override لطفاً دلیل مهندسی را در کادر «توضیح مهندس» بنویسید.")
            self.txt_comment.setFocus()
            return
        if status in (REVIEW_EDITED, REVIEW_OVERRIDDEN):
            if not final:
                QMessageBox.warning(self, "متن خالی", "متن نهایی نمی‌تواند خالی باشد.")
                return
            if status == REVIEW_EDITED and final == f.auto_text.strip():
                QMessageBox.information(self, "ویرایش", "متن تغییری نکرده است؛ در صورت تأیید از «تأیید» استفاده کنید.")
                return
        if status == REVIEW_REJECTED:
            if QMessageBox.question(self, "رد مورد", "این مورد از گزارش حذف می‌شود. ادامه می‌دهید؟",
                                    QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
        self._commit(f, status, final if status in (REVIEW_EDITED, REVIEW_OVERRIDDEN) else "")

    def _save_comment(self) -> None:
        f = self._current
        if f is None:
            return
        old = self.manager.project.reviews.get(f.key)
        status = old.status if old else REVIEW_PENDING
        repl = old.replacement_text if old else ""
        self._commit(f, status, repl)

    def _reset(self) -> None:
        f = self._current
        if f is None:
            return
        self.manager.project.reviews.pop(f.key, None)
        self.manager.dirty = True
        self.analysis.invalidate()
        self.changed.emit()
        self.refresh()
