# -*- coding: utf-8 -*-
"""صفحه تصاویر — افزودن/حذف تصاویر گزارش با نوع و عنوان (بخش ۲۵ سند)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QSplitter,
                               QVBoxLayout, QWidget)

from app.core.models import IMAGE_KINDS


class ImagesPage(QWidget):
    changed = Signal()

    def __init__(self, manager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.current_item = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        title = QLabel("تصاویر گزارش")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_select)
        lv.addWidget(self.list, 1)
        btns = QHBoxLayout()
        self.btn_add = QPushButton("+ افزودن تصویر")
        self.btn_del = QPushButton("حذف")
        self.btn_del.setObjectName("danger")
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_del)
        btns.addStretch(1)
        lv.addLayout(btns)
        splitter.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(12, 0, 0, 0)
        self.preview = QLabel("تصویری انتخاب نشده")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(300)
        rv.addWidget(self.preview, 1)

        form = QHBoxLayout()
        self.cb_kind = QComboBox()
        for key, label in IMAGE_KINDS.items():
            self.cb_kind.addItem(label, key)
        self.ed_title = QLineEdit()
        self.ed_title.setPlaceholderText("عنوان شکل (اختیاری — در کپشن استفاده می‌شود)")
        form.addWidget(QLabel("نوع:"))
        form.addWidget(self.cb_kind)
        form.addWidget(QLabel("عنوان:"))
        form.addWidget(self.ed_title, 1)
        rv.addLayout(form)
        splitter.addWidget(right)
        splitter.setSizes([300, 560])

        self.btn_add.clicked.connect(self._add_image)
        self.btn_del.clicked.connect(self._del_image)
        self.cb_kind.currentIndexChanged.connect(self._meta_changed)
        self.ed_title.textChanged.connect(self._meta_changed)

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self.list.clear()
        if not self.manager.project:
            return
        for img in self.manager.project.images:
            self.list.addItem(QListWidgetItem(
                f"[{img.kind_label}] {img.title or img.file_name}"))
        if self.manager.project.images:
            self.list.setCurrentRow(0)

    def _on_select(self, row: int) -> None:
        self.current_item = None
        if not self.manager.project:
            return
        if 0 <= row < len(self.manager.project.images):
            img = self.manager.project.images[row]
            self.current_item = img
            self.cb_kind.setCurrentIndex(self.cb_kind.findData(img.kind))
            self.ed_title.setText(img.title)
            path = self.manager.image_path(img)
            if path:
                pm = QPixmap(str(path))
                if not pm.isNull():
                    self.preview.setPixmap(pm.scaled(
                        self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    return
        self.preview.setText("تصویری انتخاب نشده")
        self.preview.setPixmap(QPixmap())

    def _meta_changed(self, *args) -> None:
        img = self.current_item
        if img is None:
            return
        img.kind = self.cb_kind.currentData()
        img.title = self.ed_title.text().strip()
        self.manager.dirty = True
        row = self.list.currentRow()
        if row >= 0:
            self.list.item(row).setText(f"[{img.kind_label}] {img.title or img.file_name}")
        self.changed.emit()

    # ------------------------------------------------------------------
    def _add_image(self) -> None:
        if not self.manager.project:
            QMessageBox.information(self, "تصاویر", "ابتدا یک پروژه باز کنید.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "انتخاب تصاویر", "", "تصاویر (*.png *.jpg *.jpeg *.bmp)")
        for p in paths:
            self.manager.import_image(p, "", "other")
        self.refresh()
        self.changed.emit()

    def _del_image(self) -> None:
        img = self.current_item
        if img is None:
            return
        self.manager.remove_image(img.uid)
        self.current_item = None
        self.refresh()
        self.changed.emit()
