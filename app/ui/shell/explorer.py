# -*- coding: utf-8 -*-
"""Project Explorer — درخت پروژه (QTreeWidget) بر پایهٔ ``app.core.project_tree``."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from app.core.project_tree import TreeNode

_KEY_ROLE = Qt.UserRole


class ProjectExplorer(QTreeWidget):
    node_selected = Signal(str)     # انتخاب تک‌کلیک → Inspector
    node_activated = Signal(str)    # دوبار کلیک/Enter → باز شدن تب Workspace
    node_clicked = Signal(str)      # کلیک کاربر (نه انتخاب برنامه‌ای) → باز شدن صفحه

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ProjectExplorer")
        self.setHeaderHidden(True)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setUniformRowHeights(True)
        self.setExpandsOnDoubleClick(False)
        self._items: dict[str, QTreeWidgetItem] = {}
        self.currentItemChanged.connect(self._on_current)
        self.itemActivated.connect(self._on_activated)
        self.itemDoubleClicked.connect(self._on_activated)
        self.itemClicked.connect(self._on_clicked)

    def set_tree(self, root: Optional[TreeNode]) -> None:
        current = self.current_key()
        self.blockSignals(True)
        self.clear()
        self._items.clear()
        if root is not None:
            self._add(root, None)
            self.expandAll()
            if current in self._items:
                self.setCurrentItem(self._items[current])
        self.blockSignals(False)

    def current_key(self) -> str:
        item = self.currentItem()
        return item.data(0, _KEY_ROLE) if item else ""

    def select_key(self, key: str) -> None:
        item = self._items.get(key)
        if item is not None:
            self.setCurrentItem(item)

    def _add(self, node: TreeNode, parent: Optional[QTreeWidgetItem]) -> None:
        item = QTreeWidgetItem(self if parent is None else parent, [node.label])
        item.setData(0, _KEY_ROLE, node.key)
        if node.tooltip:
            item.setToolTip(0, node.tooltip)
        if node.locked:                              # گام قفل: غیرفعال (تا تکمیل گام قبل)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
        self._items[node.key] = item
        for child in node.children:
            self._add(child, item)

    def _on_current(self, cur, _prev) -> None:
        if cur is not None:
            self.node_selected.emit(cur.data(0, _KEY_ROLE))

    def _on_activated(self, item, _col=0) -> None:
        if item is not None:
            self.node_activated.emit(item.data(0, _KEY_ROLE))

    def _on_clicked(self, item, _col=0) -> None:
        if item is not None:
            self.node_clicked.emit(item.data(0, _KEY_ROLE))
