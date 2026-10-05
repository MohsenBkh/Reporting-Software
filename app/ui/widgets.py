# -*- coding: utf-8 -*-
"""ابزارهای مشترک UI — layout RTL، فرم‌ساز و اجزای کمکی."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QFrame, QPushButton,
                               QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
                               QGridLayout, QHeaderView, QHBoxLayout, QLabel,
                               QLineEdit, QLayout, QScrollArea, QSpinBox,
                               QTableWidget, QVBoxLayout, QWidget)


def hline() -> QLayout:
    from PySide6.QtWidgets import QFrame
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    lay = QHBoxLayout()
    lay.addWidget(f)
    return lay


class FormRow:
    """ساخت سریع فرم با فیلدهای دارای واحد (بخش ۳۶ سند)."""

    @staticmethod
    def with_unit(widget, unit: str) -> QWidget:
        if not unit:
            return widget
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(widget)
        lay.addWidget(QLabel(unit))
        return box


def make_spin(minimum: float = 0.0, maximum: float = 1e9, decimals: int = 3,
              value=None) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(minimum, maximum)
    sp.setDecimals(decimals)
    sp.setGroupSeparatorShown(False)
    if value is not None:
        sp.setValue(float(value))
    return sp


def form_layout(rows: list[tuple[str, QWidget]]) -> QFormLayout:
    form = QFormLayout()
    for label, widget in rows:
        form.addRow(label, widget)
    return form


def vstack(widgets: list, spacing: int = 10) -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setSpacing(spacing)
    for w in widgets:
        lay.addWidget(w)
    lay.addStretch(1)
    return box


# ---------------------------------------------------------------------------
# اجزای مشترک UI حرفه‌ای (v1.0.3)
# ---------------------------------------------------------------------------
class StatusBadge(QLabel):
    """نشان وضعیت: normal | warning | error | review | completed | info | pending."""

    def __init__(self, text: str = "", state: str = "normal", parent=None) -> None:
        super().__init__(text, parent)
        self.setProperty("badge", True)
        self.setAlignment(Qt.AlignCenter)
        self.set_state(state, text or None)

    def set_state(self, state: str, text: str | None = None) -> None:
        if text is not None:
            self.setText(text)
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)


class Card(QFrame):
    """کارت اطلاعات با عنوان، مقدار و توضیح (خلاصه پروژه/نتایج)."""

    def __init__(self, title: str = "", value: str = "—", caption: str = "",
                 state: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(2)
        top = QHBoxLayout()
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("CardCaption")
        top.addWidget(self.lbl_title)
        top.addStretch(1)
        self.badge = StatusBadge("", state or "normal")
        self.badge.setVisible(state is not None)
        top.addWidget(self.badge)
        lay.addLayout(top)
        self.lbl_value = QLabel(value)
        self.lbl_value.setObjectName("CardValue")
        lay.addWidget(self.lbl_value)
        self.lbl_caption = QLabel(caption)
        self.lbl_caption.setObjectName("CardCaption")
        self.lbl_caption.setWordWrap(True)
        lay.addWidget(self.lbl_caption)

    def set(self, value: str, caption: str = "", state: str | None = None,
            badge_text: str | None = None) -> None:
        self.lbl_value.setText(value)
        self.lbl_caption.setText(caption)
        if state is None:
            self.badge.setVisible(False)
        else:
            self.badge.setVisible(True)
            self.badge.set_state(state, badge_text)


def page_header(title: str, subtitle: str = "") -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 4)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("PageTitle")
    lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("PageSubtitle")
        s.setWordWrap(True)
        lay.addWidget(s)
    box.title_label = t  # type: ignore[attr-defined]
    return box


def section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("SectionTitle")
    return lbl


def tool_button(text: str, tooltip: str = "", object_name: str = "") -> QPushButton:
    b = QPushButton(text)
    if tooltip:
        b.setToolTip(tooltip)
    if object_name:
        b.setObjectName(object_name)
    b.setCursor(Qt.PointingHandCursor)
    return b


class StepBar(QFrame):
    """نوار مراحل Workflow: پروژه ← ورود داده ← اعتبارسنجی ← تحلیل ← بازبینی ← پیش‌نمایش ← تولید."""

    step_clicked = Signal(str)

    def __init__(self, steps: list[tuple[str, str]], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("StepBar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 6, 16, 6)
        lay.setSpacing(2)
        self.chips: dict[str, QPushButton] = {}
        self._labels = dict(steps)
        for i, (key, label) in enumerate(steps):
            b = QPushButton(f"{i + 1}. {label}")
            b.setObjectName("StepChip")
            b.setProperty("step", "todo")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.step_clicked.emit(k))
            self.chips[key] = b
            lay.addWidget(b)
            if i < len(steps) - 1:
                sep = QLabel("‹")
                sep.setObjectName("Muted")
                lay.addWidget(sep)
        lay.addStretch(1)

    def set_state(self, key: str, state: str, tooltip: str = "") -> None:
        """state: todo | current | done | warning | error"""
        b = self.chips[key]
        b.setProperty("step", state)
        marks = {"done": "✓ ", "error": "✕ ", "warning": "! "}
        idx = list(self.chips).index(key) + 1
        b.setText(f"{marks.get(state, '')}{idx}. {self._labels[key]}")
        b.setToolTip(tooltip)
        b.style().unpolish(b)
        b.style().polish(b)


def state_item(text: str, state: str, theme: str = "light"):
    """سلول جدول رنگی بر اساس وضعیت (Normal/Warning/Error/Requires Review/...)."""
    from PySide6.QtWidgets import QTableWidgetItem
    from app.ui import theme as th
    fg, bg = th.state_colors(theme, state)
    it = QTableWidgetItem(text)
    it.setForeground(QBrush(QColor(fg)))
    it.setBackground(QBrush(QColor(bg)))
    it.setTextAlignment(Qt.AlignCenter)
    return it


class OptionalSpin(QWidget):
    """ورودی عددی اختیاری — تا وقتی تیک «تعریف‌شده» نخورده باشد مقدار None است.

    مطابق اصل «هیچ آستانه‌ای اختراع نمی‌شود»: مقدار خالی به MISSING_RULE /
    MISSING_DATA منجر می‌شود، نه به صفر.
    """

    def __init__(self, value=None, minimum: float = 0.0, maximum: float = 1e9,
                 decimals: int = 2, suffix: str = "", label: str = "تعریف‌شده",
                 parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.chk = QCheckBox(label)
        self.chk.setChecked(value is not None)
        self.spin = make_spin(minimum, maximum, decimals,
                              float(value) if value is not None else minimum)
        self.spin.setSuffix(suffix)
        self.spin.setEnabled(self.chk.isChecked())
        self.chk.toggled.connect(self.spin.setEnabled)
        lay.addWidget(self.chk)
        lay.addWidget(self.spin, 1)

    # ------------------------------------------------------------------
    def value(self):
        """مقدار عددی یا None وقتی کاربر آن را تعریف‌نشده گذاشته است."""
        return self.spin.value() if self.chk.isChecked() else None

    def setValue(self, value) -> None:
        self.chk.setChecked(value is not None)
        if value is not None:
            self.spin.setValue(float(value))

    def spinbox(self):
        return self.spin


def configure_data_table(table: QTableWidget, cols: list[str],
                         min_width: int = 92) -> None:
    """آماده‌سازی جدول داده‌ورودی (RTL) — عرض ستون‌ها بعد از پر شدن محاسبه می‌شود."""
    table.setHorizontalHeaderLabels(cols)
    table.setAlternatingRowColors(True)
    table.setTextElideMode(Qt.ElideNone)
    table.setWordWrap(True)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)
    table.horizontalHeader().setStretchLastSection(False)
    table.horizontalHeader().setMinimumSectionSize(min_width)
    table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)


def fit_columns(table: QTableWidget, min_width: int = 92, max_width: int = 260) -> None:
    """عرض ستون‌ها = بیشترین مقدار بین «عنوان ستون» و «محتوای سلول‌ها» تا متن بریده نشود."""
    table.resizeColumnsToContents()
    fm = table.fontMetrics()
    hdr_fm = table.horizontalHeader().fontMetrics()
    for c in range(table.columnCount()):
        label = table.horizontalHeaderItem(c)
        need = max(fm.horizontalAdvance(label.text()) if label else 0,
                   hdr_fm.horizontalAdvance(label.text()) if label else 0) + 34
        table.setColumnWidth(c, min(max(need, table.columnWidth(c), min_width), max_width))


def scrollable(widget: QWidget):
    from PySide6.QtWidgets import QScrollArea
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    widget.setObjectName("Page")
    sa.setWidget(widget)
    return sa
