# -*- coding: utf-8 -*-
"""ویجت مشترک «نیروگاه‌ها و اتوبوستر» — v2.5.0.

در بخش «ورود داده» همه مطالعات (متقاضی سنگین، فیدرهای محدوده حفاظتی و
توسعه/اصلاح فیدر) تکرار می‌شود و روی ``project.has_power_plants``،
``project.power_plants`` و ``project.autobooster`` می‌نویسد:

* نیروگاه: ابتدا سؤال «وجود دارد؟» و سپس «تعداد»؛ به تعداد انتخاب‌شده فرم
  نیروگاه باز می‌شود (نوع: خورشیدی/گازی/حرارتی/CHP/بادی، توان نامی،
  ظرفیت بهره‌برداری، توضیحات محل نصب).
* اتوبوستر: سؤال وجود + تعداد، ظرفیت جریانی (A) و توضیحات محل نصب.

همه مقادیر اختیاری‌اند: خالی = «ثبت‌نشده»، نه صفر.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFormLayout, QFrame, QLabel, QLineEdit,
                               QSpinBox, QVBoxLayout, QWidget)

from app.core.models import (PLANT_KINDS, PRESENCE_LABELS, PRESENCE_NO,
                             PRESENCE_UNSET, PRESENCE_YES, PowerPlant)
from app.ui.shell.settings_editor import OptionalNumberEdit

MAX_PLANTS = 10


class _PlantForm(QWidget):
    """فرم یک نیروگاه."""

    def __init__(self, index: int, parent=None) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignRight)
        form.setContentsMargins(8, 4, 8, 4)
        t = QLabel(f"نیروگاه {index + 1}")
        t.setObjectName("CardTitle")
        form.addRow(t)
        self.cb_kind = QComboBox()
        self.cb_kind.addItem("— انتخاب نوع —", "")
        for key, label in PLANT_KINDS.items():
            self.cb_kind.addItem(label, key)
        self.rated_mw = OptionalNumberEdit()
        self.rated_mw.setPlaceholderText("مثال: 1.5")
        self.operation_mw = OptionalNumberEdit()
        self.operation_mw.setPlaceholderText("ظرفیت واقعی بهره‌برداری")
        self.location_note = QLineEdit()
        self.location_note.setPlaceholderText("توضیحات محل نصب (روستا/کیلومتر مسیر و ...)")
        form.addRow("نوع نیروگاه:", self.cb_kind)
        form.addRow("توان نامی (MW):", self.rated_mw)
        form.addRow("ظرفیت بهره‌برداری (MW):", self.operation_mw)
        form.addRow("توضیحات محل نصب:", self.location_note)

    def load(self, plant: PowerPlant) -> None:
        i = self.cb_kind.findData(plant.kind)
        self.cb_kind.setCurrentIndex(i if i >= 0 else 0)
        self.rated_mw.set_value(plant.rated_mw)
        self.operation_mw.set_value(plant.operation_mw)
        self.location_note.setText(plant.location_note)

    def value(self) -> PowerPlant:
        return PowerPlant(kind=self.cb_kind.currentData() or "",
                          rated_mw=self.rated_mw.value(),
                          operation_mw=self.operation_mw.value(),
                          location_note=self.location_note.text().strip())


class NetworkAssetsWidget(QWidget):
    """کارت «نیروگاه‌ها و اتوبوستر» — خواندن/نوشتن مستقیم روی Project."""

    changed = Signal()

    def __init__(self, manager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self._loading = False
        self._plant_forms: list[_PlantForm] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # --- نیروگاه‌ها -----------------------------------------------------
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.cb_has_plants = QComboBox()
        for key in (PRESENCE_UNSET, PRESENCE_YES, PRESENCE_NO):
            self.cb_has_plants.addItem(PRESENCE_LABELS[key], key)
        self.sp_plant_count = QSpinBox()
        self.sp_plant_count.setRange(1, MAX_PLANTS)
        form.addRow("آیا نیروگاه در محدوده مطالعه وجود دارد؟", self.cb_has_plants)
        form.addRow("تعداد نیروگاه‌های موجود:", self.sp_plant_count)
        root.addLayout(form)

        self.plants_box = QWidget()
        self.plants_lay = QVBoxLayout(self.plants_box)
        self.plants_lay.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.plants_box)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("Separator")
        root.addWidget(line)

        # --- اتوبوستر -------------------------------------------------------
        form2 = QFormLayout()
        form2.setLabelAlignment(Qt.AlignRight)
        self.cb_has_booster = QComboBox()
        for key in (PRESENCE_UNSET, PRESENCE_YES, PRESENCE_NO):
            self.cb_has_booster.addItem(PRESENCE_LABELS[key], key)
        self.sp_booster_count = QSpinBox()
        self.sp_booster_count.setRange(1, 20)
        self.booster_current = OptionalNumberEdit()
        self.booster_current.setPlaceholderText("مثال: 200")
        self.booster_note = QLineEdit()
        self.booster_note.setPlaceholderText("توضیحات محل نصب")
        form2.addRow("آیا اتوبوستر (AutoBooster) وجود دارد؟", self.cb_has_booster)
        form2.addRow("تعداد:", self.sp_booster_count)
        form2.addRow("ظرفیت جریانی (A):", self.booster_current)
        form2.addRow("توضیحات محل نصب:", self.booster_note)
        root.addLayout(form2)

        # --- سیگنال‌ها -------------------------------------------------------
        self.cb_has_plants.currentIndexChanged.connect(self._plants_presence_changed)
        self.sp_plant_count.valueChanged.connect(self._plant_count_changed)
        self.cb_has_booster.currentIndexChanged.connect(self._emit)
        self.sp_booster_count.valueChanged.connect(self._emit)
        self.booster_current.textChanged.connect(self._emit)
        self.booster_note.textChanged.connect(self._emit)
        self._sync_visibility()

    # ------------------------------------------------------------------
    def _plants_presence_changed(self, *_a) -> None:
        self._sync_visibility()
        self._rebuild_plant_forms(self._current_plants())
        self._emit()

    def _plant_count_changed(self, *_a) -> None:
        self._rebuild_plant_forms(self._current_plants())
        self._emit()

    def _sync_visibility(self) -> None:
        has = self.cb_has_plants.currentData() == PRESENCE_YES
        self.sp_plant_count.setEnabled(has)
        self.plants_box.setVisible(has)
        has_b = self.cb_has_booster.currentData() == PRESENCE_YES
        for w in (self.sp_booster_count, self.booster_current, self.booster_note):
            w.setEnabled(has_b)

    def _current_plants(self) -> list[PowerPlant]:
        return [f.value() for f in self._plant_forms]

    def _rebuild_plant_forms(self, existing: list[PowerPlant]) -> None:
        """به تعداد انتخاب‌شده فرم نیروگاه باز می‌کند؛ مقادیر قبلی حفظ می‌شود."""
        want = self.sp_plant_count.value() if self.cb_has_plants.currentData() == PRESENCE_YES else 0
        for f in self._plant_forms:
            f.setParent(None)
            f.deleteLater()
        self._plant_forms = []
        for i in range(want):
            form = _PlantForm(i)
            if i < len(existing):
                form.load(existing[i])
            for w in (form.cb_kind,):
                w.currentIndexChanged.connect(self._emit)
            for w in (form.rated_mw, form.operation_mw, form.location_note):
                w.textChanged.connect(self._emit)
            self.plants_lay.addWidget(form)
            self._plant_forms.append(form)

    def _emit(self, *_a) -> None:
        self._sync_visibility()
        if not self._loading:
            self.save_to_project()
            self.changed.emit()

    # ------------------------------------------------------------------
    # مدل ↔ فرم
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        project = getattr(self.manager, "project", None)
        if project is not None:
            self.load_from(project)

    def load_from(self, project) -> None:
        self._loading = True
        has = getattr(project, "has_power_plants", "") or PRESENCE_UNSET
        i = self.cb_has_plants.findData(has)
        self.cb_has_plants.setCurrentIndex(i if i >= 0 else 0)
        plants = list(getattr(project, "power_plants", []) or [])
        if plants:
            self.sp_plant_count.setValue(min(MAX_PLANTS, len(plants)))
        self._rebuild_plant_forms(plants)
        ab = getattr(project, "autobooster", None)
        if ab is not None:
            i = self.cb_has_booster.findData(ab.present or PRESENCE_UNSET)
            self.cb_has_booster.setCurrentIndex(i if i >= 0 else 0)
            if ab.count:
                self.sp_booster_count.setValue(int(ab.count))
            self.booster_current.set_value(ab.current_a)
            self.booster_note.setText(ab.location_note)
        self._sync_visibility()
        self._loading = False

    def save_to_project(self) -> None:
        project = getattr(self.manager, "project", None)
        if project is None:
            return
        project.has_power_plants = self.cb_has_plants.currentData() or ""
        project.power_plants = (self._current_plants()
                                if project.has_power_plants == PRESENCE_YES else [])
        ab = project.autobooster
        ab.present = self.cb_has_booster.currentData() or ""
        if ab.present == PRESENCE_YES:
            ab.count = self.sp_booster_count.value()
            ab.current_a = self.booster_current.value()
            ab.location_note = self.booster_note.text().strip()
        else:
            ab.count, ab.current_a, ab.location_note = None, None, ""
