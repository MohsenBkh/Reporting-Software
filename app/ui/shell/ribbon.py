# -*- coding: utf-8 -*-
"""Ribbon — نوار منوی ریبونی مشابه Microsoft Word (برگه‌ها ← گروه‌ها ← دکمه‌ها).

ساختار: نوار عنوان آبی ← ردیف برگه‌ها (File | Project | ...) ← پنل برگهٔ فعال با گروه‌های
دارای عنوان در پایین. دکمه‌ها ``QAction`` هستند تا میان‌بر کیبورد و وضعیت (فعال/غیرفعال/تیک)
یک‌جا مدیریت شود. دابل‌کلیک روی برگه، پنل را جمع/باز می‌کند.
رنگ‌ها فقط از توکن‌های ``theme.py`` (کلیدهای ``ribbon_*``) خوانده می‌شوند.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QStackedWidget, QToolButton,
                               QVBoxLayout, QWidget)

from app.ui import theme as theme_mod
from app.ui.icons import icon

# اندازه‌های فشرده (v2.1.1): آیکون‌ها و فونت ریبون کوچک‌تر شد تا فضای کار بزرگ‌تر بماند
LARGE_ICON, SMALL_ICON = 24, 14
PANEL_HEIGHT = 86          # ارتفاع پنل ریبون (قبلاً ۱۰۴)
LARGE_MIN_WIDTH = 52       # حداقل عرض دکمه‌های بزرگ (قبلاً ۶۴)


def ribbon_qss(tokens: dict) -> str:
    t = tokens
    return f"""
QFrame#RibbonTitle {{ background: {t['title_bg']}; }}
QLabel#RibbonAppTitle {{ color: {t['title_text']}; font-weight: 600; padding: 2px 8px; font-size: 9pt; }}
QLabel#RibbonProject {{ color: {t['title_text']}; padding: 2px 8px; font-size: 9pt; }}
QFrame#RibbonTabRow {{ background: {t['title_bg']}; }}
QToolButton#RibbonTab {{ background: transparent; color: {t['ribbon_tab_text']}; border: none;
    padding: 4px 12px; font-size: 9pt; }}
QToolButton#RibbonTab:hover {{ background: {t['ribbon_tab_hover']}; }}
QToolButton#RibbonTab:checked {{ background: {t['ribbon_tab_active_bg']}; color: {t['ribbon_tab_active_text']};
    font-weight: 600; }}
QToolButton#RibbonTab[fileTab="true"] {{ background: {t['file_tab_bg']}; font-weight: 600; }}
QToolButton#RibbonTab[fileTab="true"]:checked {{ background: {t['ribbon_tab_active_bg']}; color: {t['ribbon_tab_active_text']}; }}
QStackedWidget#RibbonPanel {{ background: {t['ribbon_bg']}; border-bottom: 1px solid {t['ribbon_border']}; }}
QFrame#RibbonGroup {{ background: transparent; }}
QFrame#RibbonSep {{ background: {t['ribbon_border']}; max-width: 1px; min-width: 1px; }}
QLabel#RibbonGroupTitle {{ color: {t['muted']}; font-size: 7.5pt; padding: 0 4px 1px 4px; }}
QToolButton#RibbonButton {{ background: transparent; color: {t['text']}; border: 1px solid transparent;
    border-radius: 3px; padding: 2px 4px; font-size: 8.5pt; }}
QToolButton#RibbonButton:hover {{ background: {t['ribbon_hover']}; border-color: {t['ribbon_hover_border']}; }}
QToolButton#RibbonButton:pressed, QToolButton#RibbonButton:checked {{ background: {t['ribbon_pressed']};
    border-color: {t['ribbon_hover_border']}; }}
QToolButton#RibbonButton:disabled {{ color: {t['disabled']}; }}
QStatusBar {{ background: {t['status_bg']}; color: {t['status_text']}; border-top: none; }}
QStatusBar QLabel {{ color: {t['status_text']}; padding: 0 8px; }}
"""


class RibbonGroup(QFrame):
    def __init__(self, title: str, bar: "RibbonBar", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("RibbonGroup")
        self._bar = bar
        v = QVBoxLayout(self)
        v.setContentsMargins(3, 1, 3, 0)
        v.setSpacing(0)
        self.row = QHBoxLayout()
        self.row.setSpacing(2)
        v.addLayout(self.row, 1)
        lbl = QLabel(title)
        lbl.setObjectName("RibbonGroupTitle")
        lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(lbl)

    def add_action(self, action: QAction, icon_name: str, large: bool = True) -> QToolButton:
        b = QToolButton()
        b.setObjectName("RibbonButton")
        b.setDefaultAction(action)
        b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon if large else Qt.ToolButtonTextBesideIcon)
        b.setIconSize(QSize(LARGE_ICON, LARGE_ICON) if large else QSize(SMALL_ICON, SMALL_ICON))
        b.setAutoRaise(False)
        b.setCursor(Qt.PointingHandCursor)
        if large:
            b.setMinimumWidth(LARGE_MIN_WIDTH)
        self.row.addWidget(b)
        self._bar._register(action, icon_name, LARGE_ICON if large else SMALL_ICON)
        return b

    def add_column(self, items: list[tuple[QAction, str]]) -> None:
        """چند دکمهٔ کوچک زیر هم (مثل ستون‌های Word)."""
        col = QVBoxLayout()
        col.setSpacing(0)
        for action, icon_name in items:
            b = QToolButton()
            b.setObjectName("RibbonButton")
            b.setDefaultAction(action)
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setIconSize(QSize(SMALL_ICON, SMALL_ICON))
            b.setCursor(Qt.PointingHandCursor)
            col.addWidget(b)
            self._bar._register(action, icon_name, SMALL_ICON)
        col.addStretch(1)
        self.row.addLayout(col)


class RibbonPage(QWidget):
    def __init__(self, bar: "RibbonBar", parent=None) -> None:
        super().__init__(parent)
        self._bar = bar
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(4, 2, 4, 1)
        self.lay.setSpacing(0)
        self.lay.addStretch(1)

    def add_group(self, title: str) -> RibbonGroup:
        if self.lay.count() > 1:                       # جداکنندهٔ عمودی بین گروه‌ها
            sep = QFrame()
            sep.setObjectName("RibbonSep")
            self.lay.insertWidget(self.lay.count() - 1, sep)
        g = RibbonGroup(title, self._bar)
        self.lay.insertWidget(self.lay.count() - 1, g)
        return g


class RibbonBar(QWidget):
    tab_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._theme = "light"
        self._icons: list[tuple[QAction, str, int]] = []
        self._tabs: dict[str, QToolButton] = {}
        self._pages: dict[str, RibbonPage] = {}
        self._collapsed = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = QFrame()
        title.setObjectName("RibbonTitle")
        th = QHBoxLayout(title)
        th.setContentsMargins(4, 0, 4, 0)
        self.lbl_app = QLabel("")
        self.lbl_app.setObjectName("RibbonAppTitle")
        self.lbl_project = QLabel("")
        self.lbl_project.setObjectName("RibbonProject")
        th.addWidget(self.lbl_app)
        th.addWidget(self.lbl_project, 1)
        self.title_layout = th                           # ویجت‌های اضافی (نشان وضعیت و ...)
        root.addWidget(title)

        row = QFrame()
        row.setObjectName("RibbonTabRow")
        self.tab_row = QHBoxLayout(row)
        self.tab_row.setContentsMargins(4, 0, 4, 0)
        self.tab_row.setSpacing(0)
        self.tab_row.addStretch(1)
        root.addWidget(row)

        self.panel = QStackedWidget()
        self.panel.setObjectName("RibbonPanel")
        self.panel.setFixedHeight(PANEL_HEIGHT)
        root.addWidget(self.panel)

    # ------------------------------------------------------------------
    def add_tab(self, key: str, title: str, file_tab: bool = False) -> RibbonPage:
        b = QToolButton()
        b.setObjectName("RibbonTab")
        b.setText(title)
        b.setCheckable(True)
        b.setAutoExclusive(True)
        b.setProperty("fileTab", file_tab)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _=False, k=key: self.set_current(k))
        b.installEventFilter(self)
        self.tab_row.insertWidget(self.tab_row.count() - 1, b)
        page = RibbonPage(self)
        self.panel.addWidget(page)
        self._tabs[key], self._pages[key] = b, page
        if len(self._tabs) == 1:
            self.set_current(key)
        return page

    def set_current(self, key: str) -> None:
        if key not in self._pages:
            return
        for k, b in self._tabs.items():
            b.setChecked(k == key)
        self.panel.setCurrentWidget(self._pages[key])
        if self._collapsed:
            self.set_collapsed(False)
        self.tab_changed.emit(key)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self.panel.setVisible(not collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def eventFilter(self, obj, event):               # noqa: N802
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonDblClick and obj in self._tabs.values():
            self.set_collapsed(not self._collapsed)
            return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    def set_titles(self, app_title: str, project_text: str) -> None:
        self.lbl_app.setText(app_title)
        self.lbl_project.setText(project_text)

    def _register(self, action: QAction, icon_name: str, size: int) -> None:
        self._icons.append((action, icon_name, size))
        action.setIcon(icon(icon_name, theme_mod.tokens(self._theme)["text"], size))

    def apply_theme(self, theme: str) -> None:
        """رنگ آیکن‌ها را با Theme جاری هماهنگ می‌کند."""
        self._theme = theme
        color = theme_mod.tokens(theme)["text"]
        for action, name, size in self._icons:
            try:
                action.setIcon(icon(name, color, size))
            except Exception:  # noqa: BLE001 — آیکن حیاتی نیست
                pass
