# -*- coding: utf-8 -*-
"""صفحه تصاویر/شکل‌های گزارش — v1.2.0.

قابلیت‌های افزوده‌شده نسبت به ۱.۱.x:

* **محل قرارگیری مستقل**: هر شکل می‌تواند به یک «بخش گزارش» صریح نسبت داده شود
  (مقدمه، تحلیل بارگذاری، بخش‌های مطالعه، جمع‌بندی، پیوست…). در حالت «خودکار»،
  بخش از روی «نوع شکل» تعیین می‌شود (سازگاری کامل با پروژه‌های قدیمی).
* **اولویت/ترتیب**: عدد کوچک‌تر جلوتر می‌آید؛ دو دکمهٔ بالا/پایین هم ترتیب را
  جابه‌جا می‌کند. ترتیب نهایی درج: (ترتیب بخش، اولویت، ترتیب ورود).
* **کپشن مستقل**: متن کپشن دستی بر کپشن خودکار برنامه مقدم است.
* **چند شکل برای هر آیتم**: افزودن چند فایل به‌صورت هم‌زمان و/یا «تکثیر» یک شکل
  برای ساخت شکل دیگری با عنوان/کپشن/محل متفاوت.
* **کلید On/Off هر شکل**: شکل خاموش در گزارش نمی‌آید ولی داده‌اش پاک نمی‌شود.

این صفحه هیچ متنی از خود نمی‌سازد؛ فقط فرادادهٔ شکل‌ها را ثبت/مرتب می‌کند.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPlainTextEdit,
                               QPushButton, QSpinBox, QSplitter, QVBoxLayout,
                               QWidget)

from app.core.models import IMAGE_KINDS
from app.core.report_sections import REPORT_SECTIONS, section_label

AUTO_SECTION = ""          # «خودکار بر اساس نوع شکل»


class ImagesPage(QWidget):
    changed = Signal()

    def __init__(self, manager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.current_item = None
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        title = QLabel("تصاویر و شکل‌های گزارش")
        title.setObjectName("PageTitle")
        root.addWidget(title)
        hint = QLabel("هر شکل عنوان، بخش (محل درج)، کپشن و اولویت مستقل خود را دارد. "
                      "یک بخش می‌تواند چند شکل داشته باشد؛ ترتیب درج با «اولویت» تعیین می‌شود "
                      "(عدد کمتر = جلوتر).")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        root.addWidget(hint)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # ---------------------------------------------------------------- چپ
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_select)
        self.list.itemChanged.connect(self._item_changed)
        lv.addWidget(self.list, 1)

        order_bar = QHBoxLayout()
        self.btn_up = QPushButton("▲ بالا")
        self.btn_down = QPushButton("▼ پایین")
        self.btn_up.setToolTip("جلوتر بردن شکل در همان بخش (کاهش اولویت)")
        self.btn_down.setToolTip("عقب‌تر بردن شکل در همان بخش (افزایش اولویت)")
        order_bar.addWidget(self.btn_up)
        order_bar.addWidget(self.btn_down)
        order_bar.addStretch(1)
        lv.addLayout(order_bar)

        btns = QHBoxLayout()
        self.btn_add = QPushButton("+ افزودن تصاویر")
        self.btn_dup = QPushButton("تکثیر شکل")
        self.btn_del = QPushButton("حذف")
        self.btn_del.setObjectName("danger")
        self.btn_dup.setToolTip("ساخت شکل جدید با همان تنظیمات (برای جایگزینی فایل)")
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_dup)
        btns.addWidget(self.btn_del)
        btns.addStretch(1)
        lv.addLayout(btns)

        self.lbl_stats = QLabel("")
        self.lbl_stats.setObjectName("Muted")
        self.lbl_stats.setWordWrap(True)
        lv.addWidget(self.lbl_stats)
        splitter.addWidget(left)

        # --------------------------------------------------------------- راست
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(12, 0, 0, 0)
        self.preview = QLabel("تصویری انتخاب نشده")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(260)
        rv.addWidget(self.preview, 1)

        form = QFormLayout()
        self.cb_kind = QComboBox()
        for key, label in IMAGE_KINDS.items():
            self.cb_kind.addItem(label, key)
        self.ed_title = QLineEdit()
        self.ed_title.setPlaceholderText("عنوان شکل — در فهرست شکل‌ها و کپشن خودکار")
        self.cb_section = QComboBox()
        self.cb_section.addItem(section_label(AUTO_SECTION), AUTO_SECTION)
        for key, label in REPORT_SECTIONS:
            self.cb_section.addItem(label, key)
        self.sp_order = QSpinBox()
        self.sp_order.setRange(-999, 999)
        self.sp_order.setToolTip("عدد کمتر = جلوتر در همان بخش")
        self.ed_caption = QPlainTextEdit()
        self.ed_caption.setPlaceholderText(
            "کپشن اختصاصی (خالی = کپشن خودکار برنامه). می‌تواند چند خطی باشد.")
        self.ed_caption.setMaximumHeight(64)
        self.chk_enabled = QCheckBox("این شکل در گزارش درج شود (On/Off)")
        self.lbl_file = QLabel("—")
        self.lbl_file.setObjectName("Muted")
        self.lbl_file.setWordWrap(True)

        form.addRow("نوع شکل:", self.cb_kind)
        form.addRow("عنوان شکل:", self.ed_title)
        form.addRow("بخش گزارش (محل درج):", self.cb_section)
        form.addRow("اولویت/ترتیب در بخش:", self.sp_order)
        form.addRow("کپشن اختصاصی:", self.ed_caption)
        form.addRow("", self.chk_enabled)
        form.addRow("فایل:", self.lbl_file)
        rv.addLayout(form)

        self.lbl_where = QLabel("")
        self.lbl_where.setObjectName("Muted")
        self.lbl_where.setWordWrap(True)
        rv.addWidget(self.lbl_where)
        splitter.addWidget(right)
        splitter.setSizes([320, 620])

        self.btn_add.clicked.connect(self._add_image)
        self.btn_dup.clicked.connect(self._duplicate_image)
        self.btn_del.clicked.connect(self._del_image)
        self.btn_up.clicked.connect(lambda: self._move(-1))
        self.btn_down.clicked.connect(lambda: self._move(+1))
        self.cb_kind.currentIndexChanged.connect(self._meta_changed)
        self.cb_section.currentIndexChanged.connect(self._meta_changed)
        self.ed_title.textChanged.connect(self._meta_changed)
        self.ed_caption.textChanged.connect(self._meta_changed)
        self.sp_order.valueChanged.connect(self._meta_changed)
        self.chk_enabled.toggled.connect(self._meta_changed)

    # ------------------------------------------------------------------
    # فهرست
    # ------------------------------------------------------------------
    def _ordered_images(self) -> list:
        """شکل‌ها به ترتیب درج در گزارش: (ترتیب بخش، اولویت، ترتیب ورود)."""
        if not self.manager.project:
            return []
        order_index = {key: i for i, (key, _l) in enumerate(REPORT_SECTIONS)}
        imgs = list(self.manager.project.images)
        return sorted(
            imgs,
            key=lambda img: (order_index.get(img.section_key or "", 0),
                             int(getattr(img, "order", 0) or 0), imgs.index(img)))

    def refresh(self) -> None:
        self._loading = True
        try:
            self.list.clear()
            if not self.manager.project:
                return
            for img in self._ordered_images():
                item = QListWidgetItem(self._row_text(img))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if getattr(img, "enabled", True) else Qt.Unchecked)
                item.setData(Qt.UserRole, img.uid)
                self.list.addItem(item)
            if self.list.count():
                self.list.setCurrentRow(0)
            else:
                self.current_item = None
            self._update_stats()
        finally:
            self._loading = False

    @staticmethod
    def _row_text(img) -> str:
        where = section_label(img.section_key) if img.section_key else "خودکار"
        title = img.title or img.file_name or "(بی‌نام)"
        return f"[{img.kind_label}] {title}  —  {where}  ·  اولویت {int(img.order or 0)}"

    def _update_stats(self) -> None:
        if not self.manager.project:
            self.lbl_stats.setText("")
            return
        imgs = list(self.manager.project.images)
        active = [i for i in imgs if getattr(i, "enabled", True)]
        sections = len({i.section_key for i in active if i.section_key})
        self.lbl_stats.setText(
            f"تعداد شکل‌ها: {len(imgs)} — فعال: {len(active)}"
            + (f" — بخش‌های صریح: {sections}" if sections else ""))

    def _on_select(self, row: int) -> None:
        self.current_item = None
        images = self._ordered_images()
        if not (0 <= row < len(images)):
            self.preview.setText("تصویری انتخاب نشده")
            self.preview.setPixmap(QPixmap())
            self.lbl_file.setText("—")
            return
        img = images[row]
        self.current_item = img
        self._loading = True
        try:
            self.cb_kind.setCurrentIndex(max(0, self.cb_kind.findData(img.kind)))
            self.ed_title.setText(img.title)
            idx = self.cb_section.findData(img.section_key or AUTO_SECTION)
            self.cb_section.setCurrentIndex(idx if idx >= 0 else 0)
            self.sp_order.setValue(int(getattr(img, "order", 0) or 0))
            self.ed_caption.setPlainText(getattr(img, "caption", "") or "")
            self.chk_enabled.setChecked(getattr(img, "enabled", True))
            self.lbl_file.setText(img.file_name or "—")
            self.lbl_where.setText(
                "بخش انتخابی: " + (section_label(img.section_key) if img.section_key
                                   else "خودکار بر اساس نوع شکل"))
        finally:
            self._loading = False
        path = self.manager.image_path(img)
        if path:
            pm = QPixmap(str(path))
            if not pm.isNull():
                self.preview.setPixmap(pm.scaled(
                    self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        self.preview.setText("فایل تصویر یافت نشد")
        self.preview.setPixmap(QPixmap())

    # ------------------------------------------------------------------
    # ویرایش فراداده
    # ------------------------------------------------------------------
    def _meta_changed(self, *args) -> None:
        img = self.current_item
        if img is None or self._loading:
            return
        img.kind = self.cb_kind.currentData()
        img.title = self.ed_title.text().strip()
        img.section_key = self.cb_section.currentData() or ""
        img.order = int(self.sp_order.value())
        img.caption = self.ed_caption.toPlainText().strip()
        img.enabled = self.chk_enabled.isChecked()
        self.manager.dirty = True
        self._reload_row_text()
        self.changed.emit()

    def _reload_row_text(self) -> None:
        """به‌روزرسانی متن/تیک ردیف جاری بدون مرتب‌سازی مجدد فهرست."""
        img = self.current_item
        row = self.list.currentRow()
        if img is None or row < 0:
            return
        self._loading = True
        try:
            item = self.list.item(row)
            item.setText(self._row_text(img))
            item.setCheckState(Qt.Checked if getattr(img, "enabled", True) else Qt.Unchecked)
        finally:
            self._loading = False
        self._update_stats()

    def _item_changed(self, item: QListWidgetItem) -> None:
        """کلید On/Off شکل از فهرست."""
        if self._loading or self.manager.project is None:
            return
        uid = item.data(Qt.UserRole)
        img = next((i for i in self.manager.project.images if i.uid == uid), None)
        if img is None:
            return
        img.enabled = item.checkState() == Qt.Checked
        self.manager.dirty = True
        if img is self.current_item:
            self._loading = True
            self.chk_enabled.setChecked(img.enabled)
            self._loading = False
        self._update_stats()
        self.changed.emit()

    # ------------------------------------------------------------------
    # افزودن / تکثیر / حذف / ترتیب
    # ------------------------------------------------------------------
    def _add_image(self) -> None:
        if not self.manager.project:
            QMessageBox.information(self, "تصاویر", "ابتدا یک پروژه باز کنید.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "انتخاب تصاویر (چند فایل مجاز است)", "",
            "تصاویر (*.png *.jpg *.jpeg *.bmp)")
        if not paths:
            return
        # تنظیمات شکل بعدی بر پایهٔ شکل جاری (تا افزودن چند شکل به یک بخش ساده باشد)
        base_section = self.cb_section.currentData() or ""
        base_kind = self.cb_kind.currentData() or "other"
        base_order = len([i for i in self.manager.project.images
                          if (i.section_key or "") == base_section
                          and getattr(i, "enabled", True)])
        for n, path in enumerate(paths):
            if not self.manager.import_image(path, "", base_kind, section_key=base_section,
                                             order=base_order + n * 10):
                QMessageBox.warning(self, "تصاویر", f"افزودن تصویر ناموفق بود:\n{path}")
        self.refresh()
        self.changed.emit()

    def _duplicate_image(self) -> None:
        """ساخت شکل جدید با همان تنظیمات (فایل قابل تعویض) — چند شکل برای یک آیتم."""
        src = self.current_item
        if src is None:
            QMessageBox.information(self, "تصاویر", "ابتدا یک شکل را انتخاب کنید.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "فایل شکل جدید", "",
                                              "تصاویر (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        ok = self.manager.import_image(path, "", src.kind, section_key=src.section_key,
                                       order=int(getattr(src, "order", 0) or 0) + 10)
        if not ok:
            QMessageBox.warning(self, "تصاویر", "افزودن تصویر ناموفق بود.")
            return
        new = self.manager.project.images[-1]
        new.caption = getattr(src, "caption", "") or ""
        new.enabled = getattr(src, "enabled", True)
        self.refresh()
        row = next((r for r in range(self.list.count())
                    if self.list.item(r).data(Qt.UserRole) == new.uid), 0)
        self.list.setCurrentRow(row)
        self.changed.emit()

    def _del_image(self) -> None:
        img = self.current_item
        if img is None:
            return
        self.manager.remove_image(img.uid)
        self.current_item = None
        self.refresh()
        self.changed.emit()

    @staticmethod
    def _effective_section(img) -> str:
        """بخشی که شکل در آن درج می‌شود: صریح، یا پیش‌فرض «نوع» (برای سازگاری)."""
        from app.core.report_sections import default_sections_of_kind
        return (img.section_key or default_sections_of_kind(img.kind)[0])

    def _move(self, step: int) -> None:
        """جابه‌جایی اولویت شکل جاری با شکل قبلی/بعدیِ **همان بخش**.

        ترتیب فقط داخل یک بخش معنا دارد؛ جابه‌جایی بین دو بخش مجاز نیست.
        """
        img = self.current_item
        if img is None:
            return
        section = self._effective_section(img)
        images = [i for i in self._ordered_images()
                  if self._effective_section(i) == section]
        if img not in images:
            return
        idx = images.index(img)
        new_idx = idx + step
        if not (0 <= new_idx < len(images)):
            return
        other = images[new_idx]
        mine = int(getattr(img, "order", 0) or 0)
        theirs = int(getattr(other, "order", 0) or 0)
        if mine == theirs:                      # اولویت برابر → با فاصلهٔ ۱۰ جابه‌جا کن
            img.order = theirs - 10 if step < 0 else theirs + 10
        else:
            img.order, other.order = theirs, mine
        self.manager.dirty = True
        uid = img.uid
        self.refresh()
        row = next((r for r in range(self.list.count())
                    if self.list.item(r).data(Qt.UserRole) == uid), -1)
        if row >= 0:
            self.list.setCurrentRow(row)
        self.changed.emit()

    # ------------------------------------------------------------------
    def select_uid(self, uid: str) -> None:
        for r in range(self.list.count()):
            if self.list.item(r).data(Qt.UserRole) == uid:
                self.list.setCurrentRow(r)
                return
