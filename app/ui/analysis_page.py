# -*- coding: utf-8 -*-
"""صفحه «تحلیل مهندسی» — شاخص‌ها، Findings و Ruleها، اعتبارسنجی و ردیابی داده (v1.0.3)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

from app.core import calculations as calc
from app.core import traceability as trace
from app.core.findings import (DOMAIN_LABELS_FA, SEV_ERROR, SEV_NORMAL, SEV_REVIEW,
                               SEV_WARNING, SEVERITY_LABELS, STATUS_LABELS_FA)
from app.core.models import (REVIEW_ACCEPTED, REVIEW_EDITED, REVIEW_OVERRIDDEN,
                             REVIEW_PENDING, REVIEW_REJECTED)
from app.core.validation import ERROR, OK, WARNING, summary_counts, validate_project
from app.ui.widgets import Card, page_header, state_item
from app.utils.formatting import fmt

STEP_LABELS = {"project": "پروژه", "input": "ورود داده", "loadflow": "پخش بار",
               "profile": "پروفیل/پیش‌بینی", "analysis": "تحلیل", "": ""}
DECISION_STATE = {REVIEW_PENDING: "pending", REVIEW_ACCEPTED: "completed",
                  REVIEW_EDITED: "info", REVIEW_OVERRIDDEN: "info", REVIEW_REJECTED: "warning"}


class AnalysisPage(QWidget):
    navigate_requested = Signal(str)   # کلید مرحله (project/input/loadflow/profile/review)

    def __init__(self, manager, settings, analysis, parent=None) -> None:
        super().__init__(parent)
        self.manager, self.settings, self.analysis = manager, settings, analysis
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header(
            "تحلیل مهندسی",
            "نتیجه‌گیری‌ها فقط بر پایه Ruleهای تعریف‌شده در Rule Engine ساخته می‌شوند؛ هیچ تصمیم مهندسی خودکار گرفته نمی‌شود."))

        cards = QHBoxLayout()
        self.c_normal = Card("Normal", "0", "موارد در محدوده", "normal")
        self.c_warn = Card("Warning", "0", "هشدار", "warning")
        self.c_err = Card("Error", "0", "خطای مهندسی", "error")
        self.c_review = Card("Requires Review", "0", "نیازمند بررسی مهندس", "review")
        for c in (self.c_normal, self.c_warn, self.c_err, self.c_review):
            cards.addWidget(c)
        root.addLayout(cards)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # --- شاخص‌های فیدر ---
        self.tbl_metrics = QTableWidget(0, 9)
        self.tbl_metrics.setHorizontalHeaderLabels([
            "فیدر", "بارگذاری (٪)", "طبقه", "ولتاژ بعد (pu)", "ΔV ناشی از متقاضی (٪)",
            "وضعیت ولتاژ مطلق", "جریان/مجاز (٪)", "ΔLoss (٪)", "پیش‌بینی"])
        self._table_defaults(self.tbl_metrics)
        self.tabs.addTab(self.tbl_metrics, "شاخص‌های فیدر")

        # --- Findings ---
        self.tbl_find = QTableWidget(0, 7)
        self.tbl_find.setHorizontalHeaderLabels(
            ["فیدر", "حوزه", "Rule", "عنوان قاعده", "وضعیت", "تصمیم مهندس", "نتیجه"])
        self._table_defaults(self.tbl_find)
        self.tbl_find.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.tbl_find, "Findings و Rules")

        # --- اعتبارسنجی ---
        val = QWidget()
        vl = QVBoxLayout(val)
        self.lbl_val = QLabel("")
        self.lbl_val.setObjectName("Muted")
        vl.addWidget(self.lbl_val)
        self.list_val = QListWidget()
        self.list_val.itemDoubleClicked.connect(self._val_clicked)
        vl.addWidget(self.list_val, 1)
        hint = QLabel("برای رفتن به محل مشکل روی هر مورد دوبار کلیک کنید.")
        hint.setObjectName("Muted")
        vl.addWidget(hint)
        self.tabs.addTab(val, "اعتبارسنجی")

        # --- ردیابی ---
        self.tbl_trace = QTableWidget(0, 5)
        self.tbl_trace.setHorizontalHeaderLabels(["فیدر", "کمیت", "مقدار", "واحد", "منبع"])
        self._table_defaults(self.tbl_trace)
        self.tbl_trace.horizontalHeader().setStretchLastSection(True)
        self.tabs.addTab(self.tbl_trace, "ردیابی داده‌ها (Traceability)")

    @staticmethod
    def _table_defaults(t: QTableWidget) -> None:
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        t.horizontalHeader().setMinimumSectionSize(80)

    def show_tab(self, name: str) -> None:
        self.tabs.setCurrentIndex({"metrics": 0, "findings": 1, "validation": 2, "trace": 3}.get(name, 0))

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        project = self.manager.project
        th = self.settings.theme
        for t in (self.tbl_metrics, self.tbl_find, self.tbl_trace):
            t.setRowCount(0)
        self.list_val.clear()
        if project is None:
            return
        items = validate_project(project, self.settings)
        errors, warns = summary_counts(items)
        self.lbl_val.setText(f"{errors} خطا · {warns} هشدار")
        for it in items:
            icon = {"error": "✕", "warning": "!", "ok": "✓"}[it.status]
            txt = f"{icon}  {it.message}"
            if it.hint and it.status != OK:
                txt += f"\n     ← {it.hint}"
            if it.step and it.status != OK:
                txt += f"   [{STEP_LABELS.get(it.step, it.step)}]"
            li = QListWidgetItem(txt)
            li.setData(Qt.UserRole, it.step)
            self.list_val.addItem(li)
        if errors:
            self.c_normal.set("—", "ابتدا خطاهای اعتبارسنجی را برطرف کنید", "normal")
            for c in (self.c_warn, self.c_err, self.c_review):
                c.set("—", "")
            self.c_err.set(str(errors), "خطای اعتبارسنجی ورودی", "error")
            self._fill_trace(project)
            return

        report = self.analysis.get()
        findings = report.findings if report else []
        cnt = {SEV_NORMAL: 0, SEV_WARNING: 0, SEV_ERROR: 0, SEV_REVIEW: 0}
        for f in findings:
            cnt[f.severity] = cnt.get(f.severity, 0) + 1
        self.c_normal.set(str(cnt[SEV_NORMAL]), "موارد در محدوده")
        self.c_warn.set(str(cnt[SEV_WARNING]), "هشدار")
        self.c_err.set(str(cnt[SEV_ERROR]), "خطای مهندسی")
        self.c_review.set(str(cnt[SEV_REVIEW]), "نیازمند بررسی مهندس")

        # --- شاخص‌های فیدر ---
        for f in project.feeders:
            ctx = calc.build_feeder_context(f, project, self.settings)
            r = self.tbl_metrics.rowCount()
            self.tbl_metrics.insertRow(r)
            if ctx["v_caused_bad"]:
                vs, vstate = "خارج از محدوده/تغییر بیش از حد — ناشی از بار جدید", "error"
            elif ctx["v_preexisting"]:
                vs, vstate = "خارج از محدوده — موجود، ناشی از متقاضی نیست", "warning"
            elif ctx["v_after_ok"]:
                vs, vstate = "در محدوده مجاز", "normal"
            else:
                vs, vstate = "نامشخص", "review"
            fc = f.forecast
            fc_txt, fc_state = (("OK", "normal") if fc.available and not fc.needs_review else
                                ("REQUIRES_ENGINEER_REVIEW", "review") if fc.needs_review else ("ندارد", "pending"))
            vals = [f.display_name, fmt(ctx["loading_pct"], 1), ctx["loading_class"],
                    fmt(f.after.min_voltage_pu, 3), fmt(ctx["d_v_pct"], 2)]
            for c, v in enumerate(vals):
                self.tbl_metrics.setItem(r, c, QTableWidgetItem(v))
            self.tbl_metrics.setItem(r, 5, state_item(vs, vstate, th))
            self.tbl_metrics.setItem(r, 6, QTableWidgetItem(fmt(ctx["i_loading_pct"], 1)))
            self.tbl_metrics.setItem(r, 7, QTableWidgetItem(fmt(ctx["d_loss_pct"], 1)))
            self.tbl_metrics.setItem(r, 8, state_item(fc_txt, fc_state, th))
        self.tbl_metrics.resizeColumnsToContents()

        # --- Findings ---
        for fd in findings:
            r = self.tbl_find.rowCount()
            self.tbl_find.insertRow(r)
            for c, v in enumerate([fd.feeder_name, DOMAIN_LABELS_FA.get(fd.domain, fd.domain),
                                   fd.rule_id, fd.rule_name]):
                self.tbl_find.setItem(r, c, QTableWidgetItem(v))
            self.tbl_find.setItem(r, 4, state_item(SEVERITY_LABELS[fd.severity], fd.severity, th))
            dec = STATUS_LABELS_FA.get(fd.status, fd.status) + (" ⚠ کهنه" if fd.stale else "")
            self.tbl_find.setItem(r, 5, state_item(dec, "review" if fd.stale else DECISION_STATE.get(fd.status, "pending"), th))
            self.tbl_find.setItem(r, 6, QTableWidgetItem((fd.final_text or "— (رد شده)").replace("\n", " ")[:160]))
        self.tbl_find.resizeColumnsToContents()
        self.tbl_find.horizontalHeader().setStretchLastSection(True)
        self._fill_trace(project)

    def _fill_trace(self, project) -> None:
        for row in trace.build_trace(project, self.settings):
            r = self.tbl_trace.rowCount()
            self.tbl_trace.insertRow(r)
            for c, v in enumerate([row.feeder, row.item, row.value, row.unit, row.source_label]):
                self.tbl_trace.setItem(r, c, QTableWidgetItem(v))
        self.tbl_trace.resizeColumnsToContents()

    def _val_clicked(self, item: QListWidgetItem) -> None:
        step = item.data(Qt.UserRole)
        if step:
            self.navigate_requested.emit(step)
