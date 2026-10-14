# -*- coding: utf-8 -*-
"""ویرایشگر «فیدرهای محدودهٔ مطالعه و شبکه» برای مطالعات ریکلوزر و سکشنالایزر.

هر مطالعه ورودی‌های خودش را در همین ویرایشگر وارد می‌کند (محدودهٔ فیدرها مستقل است)،
ولی داده‌ی هر فیدر یک‌بار در «شبکه مشترک» (``Workspace.common_network``) ذخیره می‌شود؛
اگر دو مطالعه فیدر یکسانی داشته باشند، اطلاعات آن دوباره‌خوانی/تکراری نمی‌شود.

ورودی‌ها (به ترتیب جدول «اصلاحات»):
  ۱) سطح اتصال کوتاه سه‌فاز و تکفاز پست  ۲) تنظیمات رله‌های اضافه جریان و ارت‌فالت ابتدای فیدر
  ۳) تنظیمات سایر تجهیزات موجود در فیدر  ۴) وجود منابع تولید پراکنده
  ۵) سناریوهای بهره‌برداری عادی و اضطراری
نبود داده = ``None`` (هیچ مقدار پیش‌فرضی ساخته نمی‌شود).
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget)

from app.core.protection_models import ProtectionSettings
from app.core.studies import STUDY_LABELS_FA, StudyKind
from app.core.workspace import (DEVICE_FEEDER_RELAY, DEVICE_FUSE, DEVICE_RECLOSER,
                                DEVICE_SECTIONALIZER, ExistingProtectionDevice,
                                FeederNetworkData, Workspace)
from app.ui.shell.settings_editor import OptionalNumberEdit, ProtectionSettingsEditor
from app.ui.widgets import page_header, scrollable

DEVICE_OTHER = "other"
DEVICE_TYPE_LABELS = [(DEVICE_RECLOSER, "ریکلوزر"), (DEVICE_SECTIONALIZER, "سکشنالایزر"),
                      (DEVICE_FUSE, "فیوز"), (DEVICE_OTHER, "سایر")]
DG_CHOICES = [(None, "نامشخص"), (False, "ندارد"), (True, "دارد")]


class NetworkEditor(QWidget):
    changed = Signal()

    def __init__(self, manager, get_workspace: Callable[[], Optional[Workspace]],
                 kind: StudyKind, parent=None) -> None:
        super().__init__(parent)
        self.manager, self._ws, self.kind = manager, get_workspace, StudyKind(kind)
        self._feeder: Optional[FeederNetworkData] = None
        self._device: Optional[ExistingProtectionDevice] = None
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.addWidget(page_header(
            f"فیدرهای محدودهٔ مطالعه {STUDY_LABELS_FA[self.kind]} و اطلاعات شبکه",
            "فیدرهای محدودهٔ این مطالعه را اضافه کنید و برای هر فیدر اطلاعات شبکه و حفاظت موجود را "
            "وارد کنید. داده‌ی هر فیدر یک‌بار ذخیره می‌شود و بین مطالعات مشترک است."))
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        root.addWidget(split, 1)

        # ---------------- لیست فیدرها ----------------
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._on_select)
        lv.addWidget(self.list, 1)
        self.cb_project = QComboBox()
        self.btn_add_project = QPushButton("افزودن از فیدرهای پروژه")
        self.btn_add_new = QPushButton("+ فیدر جدید")
        self.btn_remove = QPushButton("حذف از محدوده")
        self.btn_remove.setObjectName("danger")
        lv.addWidget(self.cb_project)
        for b in (self.btn_add_project, self.btn_add_new, self.btn_remove):
            lv.addWidget(b)
        self.btn_add_project.clicked.connect(self._add_from_project)
        self.btn_add_new.clicked.connect(self._add_new)
        self.btn_remove.clicked.connect(self._remove)
        split.addWidget(left)

        # ---------------- فرم ----------------
        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setSpacing(10)
        self.lbl_empty = QLabel("فیدری انتخاب نشده است.")
        self.lbl_empty.setObjectName("Muted")
        bv.addWidget(self.lbl_empty)

        g1 = QGroupBox("مشخصات فیدر و سطح اتصال کوتاه پست")
        f1 = QFormLayout(g1)
        self.ed_substation = QLineEdit()
        self.ed_voltage = OptionalNumberEdit()
        self.ed_load = OptionalNumberEdit()
        self.ed_sc3 = OptionalNumberEdit()
        self.ed_sc1 = OptionalNumberEdit()
        self.ed_topology = QLineEdit()
        f1.addRow("پست:", self.ed_substation)
        f1.addRow("ولتاژ (kV):", self.ed_voltage)
        f1.addRow("جریان بار فیدر (A):", self.ed_load)
        f1.addRow("اتصال کوتاه سه‌فاز پست (kA):", self.ed_sc3)
        f1.addRow("اتصال کوتاه تکفاز پست (kA):", self.ed_sc1)
        f1.addRow("توپولوژی / توضیح:", self.ed_topology)
        bv.addWidget(g1)

        g2 = QGroupBox("تنظیمات رله‌های اضافه جریان و ارت‌فالت ابتدای فیدر")
        v2 = QVBoxLayout(g2)
        self.relay_editor = ProtectionSettingsEditor(reclosing=False, counter=False)
        v2.addWidget(self.relay_editor)
        bv.addWidget(g2)

        g3 = QGroupBox("تنظیمات سایر تجهیزات حفاظتی موجود در فیدر (ریکلوزر، سکشنالایزر، فیوز و ...)")
        v3 = QVBoxLayout(g3)
        self.dev_list = QListWidget()
        self.dev_list.setMaximumHeight(110)
        self.dev_list.currentRowChanged.connect(self._on_select_device)
        v3.addWidget(self.dev_list)
        bar = QHBoxLayout()
        self.btn_dev_add = QPushButton("+ تجهیز")
        self.btn_dev_del = QPushButton("حذف تجهیز")
        self.btn_dev_del.setObjectName("danger")
        bar.addWidget(self.btn_dev_add)
        bar.addWidget(self.btn_dev_del)
        bar.addStretch(1)
        v3.addLayout(bar)
        f3 = QFormLayout()
        self.ed_dev_name = QLineEdit()
        self.cb_dev_type = QComboBox()
        for code, label in DEVICE_TYPE_LABELS:
            self.cb_dev_type.addItem(label, code)
        self.ed_dev_loc = QLineEdit()
        f3.addRow("نام تجهیز:", self.ed_dev_name)
        f3.addRow("نوع:", self.cb_dev_type)
        f3.addRow("محل نصب:", self.ed_dev_loc)
        v3.addLayout(f3)
        self.dev_editor = ProtectionSettingsEditor(reclosing=True, counter=True)
        v3.addWidget(self.dev_editor)
        bv.addWidget(g3)
        self.btn_dev_add.clicked.connect(self._add_device)
        self.btn_dev_del.clicked.connect(self._del_device)

        g4 = QGroupBox("منابع تولید پراکنده (DG)")
        f4 = QFormLayout(g4)
        self.cb_dg = QComboBox()
        for value, label in DG_CHOICES:
            self.cb_dg.addItem(label, value)
        self.ed_dg_note = QLineEdit()
        f4.addRow("وضعیت:", self.cb_dg)
        f4.addRow("توضیح (ظرفیت/محل):", self.ed_dg_note)
        bv.addWidget(g4)

        g5 = QGroupBox("سناریوهای بهره‌برداری")
        f5 = QFormLayout(g5)
        self.txt_normal = QPlainTextEdit()
        self.txt_emergency = QPlainTextEdit()
        for t in (self.txt_normal, self.txt_emergency):
            t.setMinimumHeight(70)
        f5.addRow("سناریوی عادی:", self.txt_normal)
        f5.addRow("سناریوی اضطراری:", self.txt_emergency)
        bv.addWidget(g5)
        bv.addStretch(1)
        self.form_body = body
        split.addWidget(scrollable(body))
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([240, 760])

        for w in (self.ed_substation, self.ed_voltage, self.ed_load, self.ed_sc3, self.ed_sc1,
                  self.ed_topology, self.ed_dg_note):
            w.textChanged.connect(self._on_edit)
        self.cb_dg.currentIndexChanged.connect(self._on_edit)
        for t in (self.txt_normal, self.txt_emergency):
            t.textChanged.connect(self._on_edit)
        self.relay_editor.changed.connect(self._on_edit)
        for w in (self.ed_dev_name, self.ed_dev_loc):
            w.textChanged.connect(self._on_device_edit)
        self.cb_dev_type.currentIndexChanged.connect(self._on_device_edit)
        self.dev_editor.changed.connect(self._on_device_edit)
        self._set_form_enabled(False)

    # ------------------------------------------------------------------
    def _set_form_enabled(self, on: bool) -> None:
        self.form_body.setEnabled(on)
        self.lbl_empty.setVisible(not on)

    def refresh(self) -> None:
        ws, project = self._ws(), self.manager.project
        self._loading = True
        keep = self._feeder.name if self._feeder else ""
        self.list.clear()
        self.cb_project.clear()
        if ws is None or project is None:
            self._loading = False
            return
        names = ws.scope(self.kind)
        for n in names:
            self.list.addItem(QListWidgetItem(n))
        for f in getattr(project, "feeders", []):
            if f.name and all(f.name.casefold() != n.casefold() for n in names):
                self.cb_project.addItem(f.name)
        self.btn_add_project.setEnabled(self.cb_project.count() > 0)
        self._loading = False
        row = next((i for i, n in enumerate(names) if n == keep), 0 if names else -1)
        if row >= 0:
            self.list.setCurrentRow(row)
            self._on_select(row)
        else:
            self._feeder = None
            self._set_form_enabled(False)

    def focus_field(self, key: str) -> bool:
        """Focus روی ورودی: sc3 | sc1 | load | feeders | relay | dg | scenarios | topology."""
        target = {"sc3": self.ed_sc3, "sc1": self.ed_sc1, "load": self.ed_load,
                  "feeders": self.list, "dg": self.cb_dg, "scenarios": self.txt_normal,
                  "topology": self.ed_topology, "voltage": self.ed_voltage}.get(key)
        if key == "relay":
            return self.relay_editor.focus_field("f51.pickup_a")
        if target is None:
            return False
        target.setFocus()
        return True

    def save_to_project(self) -> None:          # برای هماهنگی با ``_collect_forms`` پنجره
        self._store()

    # ------------------------------------------------------------------
    def _on_select(self, row: int) -> None:
        if self._loading:
            return
        ws = self._ws()
        names = ws.scope(self.kind) if ws else []
        if ws is None or not (0 <= row < len(names)):
            self._feeder = None
            self._set_form_enabled(False)
            return
        self._feeder = ws.common_network.feeder(names[row])
        if self._feeder is None:                 # حفاظت در برابر ناسازگاری Scope و شبکه
            ws.add_to_scope(self.kind, names[row])
            self._feeder = ws.common_network.feeder(names[row])
        self._load_feeder()

    def _load_feeder(self) -> None:
        f = self._feeder
        self._loading = True
        self._set_form_enabled(f is not None)
        if f is not None:
            self.ed_substation.setText(f.substation)
            self.ed_voltage.set_value(f.voltage_kv)
            self.ed_load.set_value(f.load_current_a)
            self.ed_sc3.set_value(f.max_fault_current_ka)
            self.ed_sc1.set_value(f.sc_1ph_ka)
            self.ed_topology.setText(f.topology_note)
            relay = f.device(DEVICE_FEEDER_RELAY)
            self.relay_editor.load(relay.settings if relay else ProtectionSettings())
            idx = self.cb_dg.findData(f.has_dg)
            self.cb_dg.setCurrentIndex(max(idx, 0))
            self.ed_dg_note.setText(f.dg_note)
            self.txt_normal.setPlainText(f.normal_scenario)
            self.txt_emergency.setPlainText(f.emergency_scenario)
            self._fill_devices()
        self._loading = False

    def _store(self) -> None:
        f = self._feeder
        if f is None or self._loading:
            return
        f.substation = self.ed_substation.text().strip()
        f.voltage_kv = self.ed_voltage.value()
        f.load_current_a = self.ed_load.value()
        f.max_fault_current_ka = self.ed_sc3.value()
        f.sc_1ph_ka = self.ed_sc1.value()
        f.topology_note = self.ed_topology.text().strip()
        s = ProtectionSettings()
        self.relay_editor.store(s)
        relay = f.device(DEVICE_FEEDER_RELAY)
        if relay is None and not s.is_empty():
            relay = ExistingProtectionDevice(name="رله ابتدای فیدر", device_type=DEVICE_FEEDER_RELAY)
            f.existing_protection.insert(0, relay)
        if relay is not None:
            relay.settings = s
        f.has_dg = self.cb_dg.currentData()
        f.dg_note = self.ed_dg_note.text().strip()
        f.normal_scenario = self.txt_normal.toPlainText().strip()
        f.emergency_scenario = self.txt_emergency.toPlainText().strip()

    def _on_edit(self, *_a) -> None:
        if self._loading:
            return
        self._store()
        self.changed.emit()

    # ------------------------------------------------------------------
    def _others(self) -> list[ExistingProtectionDevice]:
        f = self._feeder
        return [d for d in (f.existing_protection if f else []) if d.device_type != DEVICE_FEEDER_RELAY]

    def _fill_devices(self) -> None:
        self.dev_list.clear()
        for d in self._others():
            label = dict(DEVICE_TYPE_LABELS).get(d.device_type, d.device_type)
            self.dev_list.addItem(QListWidgetItem(f"{d.name or '(بی‌نام)'} — {label}"))
        if self.dev_list.count():
            self.dev_list.setCurrentRow(0)
            self._on_select_device(0)
        else:
            self._device = None
            self._set_device_enabled(False)

    def _set_device_enabled(self, on: bool) -> None:
        for w in (self.ed_dev_name, self.cb_dev_type, self.ed_dev_loc, self.dev_editor,
                  self.btn_dev_del):
            w.setEnabled(on)

    def _on_select_device(self, row: int) -> None:
        devs = self._others()
        if not (0 <= row < len(devs)):
            self._device = None
            self._set_device_enabled(False)
            return
        was = self._loading
        self._loading = True
        self._device = devs[row]
        self._set_device_enabled(True)
        self.ed_dev_name.setText(self._device.name)
        self.cb_dev_type.setCurrentIndex(max(self.cb_dev_type.findData(self._device.device_type), 0))
        self.ed_dev_loc.setText(self._device.location)
        self.dev_editor.load(self._device.settings)
        self._loading = was

    def _on_device_edit(self, *_a) -> None:
        d = self._device
        if d is None or self._loading:
            return
        d.name = self.ed_dev_name.text().strip()
        d.device_type = self.cb_dev_type.currentData() or DEVICE_OTHER
        d.location = self.ed_dev_loc.text().strip()
        self.dev_editor.store(d.settings)
        row = self.dev_list.currentRow()
        label = dict(DEVICE_TYPE_LABELS).get(d.device_type, d.device_type)
        if self.dev_list.item(row) is not None:
            self.dev_list.item(row).setText(f"{d.name or '(بی‌نام)'} — {label}")
        self.changed.emit()

    def _add_device(self) -> None:
        if self._feeder is None:
            return
        self._feeder.existing_protection.append(
            ExistingProtectionDevice(name="تجهیز جدید", device_type=DEVICE_RECLOSER))
        self._loading = True
        self._fill_devices()
        self._loading = False
        self.dev_list.setCurrentRow(self.dev_list.count() - 1)
        self._on_select_device(self.dev_list.count() - 1)
        self.changed.emit()

    def _del_device(self) -> None:
        if self._feeder is None or self._device is None:
            return
        self._feeder.existing_protection.remove(self._device)
        self._device = None
        self._loading = True
        self._fill_devices()
        self._loading = False
        self.changed.emit()

    # ------------------------------------------------------------------
    def _add_to_scope(self, name: str) -> None:
        ws = self._ws()
        name = (name or "").strip()
        if ws is None or not name:
            return
        ws.add_to_scope(self.kind, name)
        self.refresh()
        names = ws.scope(self.kind)
        self.list.setCurrentRow(next((i for i, n in enumerate(names)
                                      if n.casefold() == name.casefold()), 0))
        self.changed.emit()

    def _add_from_project(self) -> None:
        ws, project = self._ws(), self.manager.project
        name = self.cb_project.currentText()
        if ws is None or project is None or not name:
            return
        src = next((f for f in project.feeders if f.name == name), None)
        if ws.common_network.feeder(name) is None:
            ws.common_network.upsert(FeederNetworkData(
                name=name, substation=getattr(src, "substation", "") or "",
                voltage_kv=getattr(project, "network_voltage_kv", None),
                load_current_a=getattr(src, "peak_current_a", None), source="PROJECT:feeders"))
        self._add_to_scope(name)

    def _add_new(self) -> None:
        name, ok = QInputDialog.getText(self, "فیدر جدید", "نام فیدر:")
        if ok:
            self._add_to_scope(name)

    def _remove(self) -> None:
        ws = self._ws()
        if ws is None or self._feeder is None:
            return
        ws.remove_from_scope(self.kind, self._feeder.name)    # داده‌ی شبکه مشترک پاک نمی‌شود
        self._feeder = None
        self.refresh()
        self.changed.emit()
