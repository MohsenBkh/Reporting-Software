# -*- coding: utf-8 -*-
"""صفحهٔ «تنظیمات حفاظتی» ریکلوزر و سکشنالایزر با اعتبارسنجی زنده (Rule Engine).

* فرم‌ها فقط داده را به ``project.recloser`` / ``project.sectionalizer`` می‌نویسند؛
  هیچ منطق مهندسی در UI نیست — نتایج از ``evaluate_study`` می‌آیند.
* Validation کنار ورودی: فهرست یافته‌ها با آیکن/رنگ وضعیت، منبع و شاهد در Tooltip.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QCheckBox, QFrame, QLabel, QListWidget, QListWidgetItem,
                               QSplitter, QTabWidget, QVBoxLayout, QWidget)

from app.core.studies import StudyKind
from app.rules.domains import build_protection_engine, evaluate_study
from app.rules.trace import trace_link
from app.ui import theme as theme_mod
from app.ui.shell.dashboard_model import result_view
from app.ui.shell.design import SPACING
from app.ui.shell.settings_editor import ProtectionSettingsEditor
from app.ui.widgets import page_header, scrollable


def _card(title: str, sub: str = "") -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("Card")
    v = QVBoxLayout(card)
    v.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"])
    t = QLabel(title)
    t.setObjectName("CardTitle")
    v.addWidget(t)
    if sub:
        s = QLabel(sub)
        s.setObjectName("CardSub")
        s.setWordWrap(True)
        v.addWidget(s)
    return card, v


class _DevicePanel(QWidget):
    changed = Signal()

    def __init__(self, kind: StudyKind, parent=None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.info = None
        rec = kind is StudyKind.RECLOSER
        body = QWidget()
        v = QVBoxLayout(body)
        v.setSpacing(SPACING["md"])
        self.warn = QLabel("")
        self.warn.setObjectName("FieldError")
        self.warn.setWordWrap(True)
        v.addWidget(self.warn)
        card, cv = _card(f"تنظیمات حفاظتی {'ریکلوزر' if rec else 'سکشنالایزر'}",
                         "مقادیر خالی «ناموجود» تلقی می‌شوند و در قواعد MISSING_DATA می‌دهند.")
        self.editor = ProtectionSettingsEditor(reclosing=rec, counter=not rec)
        cv.addWidget(self.editor)
        v.addWidget(card)
        ref_title = "تنظیمات رله/تجهیز بالادست" if rec else "تنظیمات ریکلوزر مرجع"
        ref_sub = ("برای بررسی هماهنگی؛ در صورت خالی بودن از رله سر فیدر شبکه مشترک خوانده می‌شود."
                   if rec else "در صورت فعال بودن پیوند، از ریکلوزر همین پروژه خوانده می‌شود.")
        card2, c2v = _card(ref_title, ref_sub)
        self.link = None
        if not rec:
            self.link = QCheckBox("استفاده از ریکلوزر پروژه به‌عنوان مرجع")
            self.link.toggled.connect(lambda *_: self._emit())
            c2v.addWidget(self.link)
        self.ref_editor = ProtectionSettingsEditor(reclosing=not rec, counter=False)
        c2v.addWidget(self.ref_editor)
        v.addWidget(card2)
        v.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(scrollable(body))
        self.editor.changed.connect(self._emit)
        self.ref_editor.changed.connect(self._emit)
        self._loading = False

    @property
    def _ref_attr(self) -> str:
        return "upstream_settings" if self.kind is StudyKind.RECLOSER else "reference_recloser_settings"

    def load(self, info) -> None:
        self.info = info
        self._loading = True
        ok = hasattr(info, "settings")
        self.warn.setText("" if ok else "مدل داده هنوز به‌روز نشده است؛ patch مرحلهٔ ۱ (models.py) را اعمال کنید.")
        self.setEnabled(ok)
        if ok:
            self.editor.load(info.settings)
            self.ref_editor.load(getattr(info, self._ref_attr))
            if self.link is not None:
                self.link.setChecked(bool(getattr(info, "link_to_project_recloser", True)))
        self._loading = False

    def store(self) -> None:
        if self.info is None or not hasattr(self.info, "settings"):
            return
        self.editor.store(self.info.settings)
        self.ref_editor.store(getattr(self.info, self._ref_attr))
        if self.link is not None:
            self.info.link_to_project_recloser = self.link.isChecked()

    def _emit(self, *_a) -> None:
        if not self._loading:
            self.changed.emit()


class ProtectionSettingsPage(QWidget):
    changed = Signal()
    evaluated = Signal(object)          # dict[StudyKind, list[RuleResult]]
    goto_requested = Signal(str, str)   # (صفحه، فیلد) — ارجاع به منبع یافته

    def __init__(self, manager, get_workspace: Callable, get_theme: Callable[[], str],
                 kind: Optional[StudyKind] = None, parent=None) -> None:
        super().__init__(parent)
        self.manager, self._ws, self._theme = manager, get_workspace, get_theme
        self._engine = None
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"])
        root.addWidget(page_header(
            "تنظیمات و اعتبارسنجی حفاظتی",
            "تنظیمات ریکلوزر و سکشنالایزر را وارد کنید؛ یافته‌های Rule Engine هم‌زمان نمایش داده می‌شوند."))
        split = QSplitter(Qt.Vertical)
        self.tabs = QTabWidget()
        self.panels: dict[StudyKind, _DevicePanel] = {}
        for k, caption in ((StudyKind.RECLOSER, "ریکلوزر"), (StudyKind.SECTIONALIZER, "سکشنالایزر")):
            if kind is None or kind is k:
                self.panels[k] = _DevicePanel(k)
                self.tabs.addTab(self.panels[k], caption)
        if kind is not None:
            self.tabs.tabBar().setVisible(False)       # مطالعهٔ تک‌تجهیزی: بدون تب
        split.addWidget(self.tabs)
        box = QWidget()
        bv = QVBoxLayout(box)
        bv.setContentsMargins(0, 0, 0, 0)
        self.lbl_summary = QLabel("")
        self.lbl_summary.setObjectName("Muted")
        self.results = QListWidget()
        self.results.setObjectName("ValidationList")
        self.results.setWordWrap(True)
        bv.addWidget(self.lbl_summary)
        bv.addWidget(self.results, 1)
        split.addWidget(box)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        root.addWidget(split, 1)
        self.results.itemDoubleClicked.connect(self._on_result_clicked)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(400)             # Debounce اعتبارسنجی زنده
        self._timer.timeout.connect(self.validate)
        for p in self.panels.values():
            p.changed.connect(self._on_changed)
        self.tabs.currentChanged.connect(lambda _i: self.validate())

    def _on_result_clicked(self, item) -> None:
        route, fld = item.data(Qt.UserRole) or ("", "")
        if route:
            self.goto_requested.emit(route, fld)

    def focus_field(self, key: str) -> bool:
        panel = self.panels.get(self.current_kind())
        if panel is None:
            return False
        if key.startswith("reference"):
            return panel.ref_editor.focus_field("f51.pickup_a")
        return panel.editor.focus_field(key)

    def show_kind(self, kind: StudyKind) -> None:
        if kind in self.panels:
            self.tabs.setCurrentWidget(self.panels[kind])

    def current_kind(self) -> StudyKind:
        kinds = list(self.panels)
        idx = max(0, min(self.tabs.currentIndex(), len(kinds) - 1))
        return kinds[idx]

    def refresh(self) -> None:
        p = self.manager.project
        if p is None:
            return
        for kind, panel in self.panels.items():
            panel.load(getattr(p, kind.value))
        self.validate()

    def save_to_project(self) -> None:
        for panel in self.panels.values():
            panel.store()

    def _on_changed(self) -> None:
        self.save_to_project()
        self.changed.emit()
        self._timer.start()

    def validate(self) -> None:
        p, ws = self.manager.project, self._ws()
        self.results.clear()
        if p is None or ws is None:
            return
        self._engine = self._engine or build_protection_engine()
        all_results = {}
        for kind in self.panels:
            all_results[kind] = evaluate_study(p, ws, kind, self._engine)
        shown = all_results[self.current_kind()]
        theme = self._theme()
        for r in shown:
            state, text, tip = result_view(r)
            link = trace_link(r, self.current_kind())
            item = QListWidgetItem(text + ("   ↗" if link.has_target else ""))
            item.setToolTip(tip + ("\n" + link.to_text() if link.has_target else ""))
            item.setData(Qt.UserRole, (link.route, link.field))
            fg, _bg = theme_mod.state_colors(theme, state)
            item.setForeground(QBrush(QColor(fg)))
            self.results.addItem(item)
        review = sum(1 for r in shown if r.engineer_review_required)
        self.lbl_summary.setText(f"{len(shown)} یافته · {review} مورد نیازمند بازبینی مهندس")
        self.evaluated.emit(all_results)
