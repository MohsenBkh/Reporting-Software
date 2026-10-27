# -*- coding: utf-8 -*-
"""ویرایشگر «فیدرهای محدودهٔ مطالعه و شبکه» برای مطالعات ریکلوزر و سکشنالایزر.

v2.3.0 — صفحهٔ مشترک: فیدرهای محدودهٔ مطالعه یک‌بار وارد می‌شوند (``kind=None``)
و برای هر دو مطالعهٔ ریکلوزر و سکشنالایزر استفاده می‌شوند؛ داده‌ی هر فیدر در
«شبکه مشترک» (``Workspace.common_network``) ذخیره می‌شود.

ورودی‌ها:
  ۱) مشخصات فیدر و سطح اتصال کوتاه سه‌فاز و تکفاز پست
  ۲) وجود منابع تولید پراکنده  ۳) سناریوهای بهره‌برداری عادی و اضطراری
تنظیمات رلهٔ ابتدای فیدر و سایر تجهیزات حفاظتی دیگر اینجا وارد نمی‌شوند؛
آن‌ها با «ورود از IDMT» (بسته خروجی گزارش‌ساز ابزار IDMT) منتقل می‌شوند.
نبود داده = ``None`` (هیچ مقدار پیش‌فرضی ساخته نمی‌شود).
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QInputDialog,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget)

from app.core.studies import STUDY_LABELS_FA, StudyKind
from app.core.workspace import FeederNetworkData, Workspace
from app.ui.shell.settings_editor import OptionalNumberEdit
from app.ui.widgets import page_header, scrollable

DG_CHOICES = [(None, "نامشخص"), (False, "ندارد"), (True, "دارد")]
# صفحهٔ مشترک محدودهٔ فیدرها روی هر دو مطالعهٔ حفاظتی اعمال می‌شود
PROTECTION_KINDS = (StudyKind.RECLOSER, StudyKind.SECTIONALIZER)


class NetworkEditor(QWidget):
    changed = Signal()

    def __init__(self, manager, get_workspace: Callable[[], Optional[Workspace]],
                 kind: Optional[StudyKind] = None, parent=None) -> None:
        super().__init__(parent)
        self.manager, self._ws = manager, get_workspace
        self.kind = StudyKind(kind) if kind is not None else None
        self._feeder: Optional[FeederNetworkData] = None
        self._loading = False

        title = ("فیدرهای محدودهٔ مطالعه و اطلاعات شبکه" if self.kind is None else
                 f"فیدرهای محدودهٔ مطالعه {STUDY_LABELS_FA[self.kind]} و اطلاعات شبکه")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.addWidget(page_header(
            title,
            "فیدرهای محدودهٔ مطالعه را یک‌بار اینجا وارد کنید؛ همین فهرست برای هر دو مطالعهٔ "
            "ریکلوزر و سکشنالایزر استفاده می‌شود. تنظیمات رلهٔ ابتدای فیدر و سایر تجهیزات "
            "حفاظتی از «ورود از IDMT» منتقل می‌شوند."))
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

        # v2.3.0 — تنظیمات رلهٔ ابتدای فیدر و سایر تجهیزات حفاظتی از این صفحه حذف
        # شدند؛ این داده‌ها از «ورود از IDMT» (بسته خروجی گزارش‌ساز) منتقل می‌شوند.
        note_idmt = QLabel("تنظیمات رلهٔ ابتدای فیدر و سایر تجهیزات حفاظتی موجود، با "
                           "«Studies ← ورود از IDMT» از بسته خروجی ابزار IDMT وارد می‌شوند.")
        note_idmt.setObjectName("Muted")
        note_idmt.setWordWrap(True)
        bv.addWidget(note_idmt)

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

        # v2.5.0 — نیروگاه‌ها و اتوبوستر (مشترک همه مطالعات؛ روی Project ذخیره می‌شود)
        from app.ui.shell.network_assets import NetworkAssetsWidget
        g6 = QGroupBox("نیروگاه‌ها و اتوبوستر")
        v6 = QVBoxLayout(g6)
        self.assets = NetworkAssetsWidget(self.manager)
        self.assets.changed.connect(self.changed)
        v6.addWidget(self.assets)
        bv.addWidget(g6)
        # گروه‌های وابسته به فیدر انتخابی (نیروگاه/اتوبوستر مشترک است و همیشه فعال می‌ماند)
        self._feeder_groups = (g1, g4, g5)
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
        self._set_form_enabled(False)

    # ------------------------------------------------------------------
    # محدودهٔ فیدرها — حالت مشترک (kind=None): اجتماع محدودهٔ هر دو مطالعه؛
    # افزودن/حذف روی هر دو اعمال می‌شود تا فیدرها فقط یک‌بار وارد شوند.
    def _scope_kinds(self) -> tuple[StudyKind, ...]:
        return PROTECTION_KINDS if self.kind is None else (self.kind,)

    def _scope_names(self, ws: Workspace) -> list[str]:
        names: list[str] = []
        for k in self._scope_kinds():
            for n in ws.scope(k):
                if all(n.casefold() != m.casefold() for m in names):
                    names.append(n)
        return names

    # ------------------------------------------------------------------
    def _set_form_enabled(self, on: bool) -> None:
        # v2.5.0: فقط گروه‌های وابسته به فیدر غیرفعال می‌شوند؛ کارت مشترک
        # «نیروگاه‌ها و اتوبوستر» حتی بدون انتخاب فیدر هم قابل ویرایش است.
        for g in getattr(self, "_feeder_groups", (self.form_body,)):
            g.setEnabled(on)
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
        self.assets.load_from(project)          # v2.5.0 — نیروگاه‌ها و اتوبوستر
        names = self._scope_names(ws)
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
        """Focus روی ورودی: sc3 | sc1 | load | feeders | dg | scenarios | topology."""
        target = {"sc3": self.ed_sc3, "sc1": self.ed_sc1, "load": self.ed_load,
                  "feeders": self.list, "dg": self.cb_dg, "scenarios": self.txt_normal,
                  "topology": self.ed_topology, "voltage": self.ed_voltage,
                  "relay": self.list}.get(key)   # «relay» از IDMT وارد می‌شود → فهرست فیدرها
        if target is None:
            return False
        target.setFocus()
        return True

    def save_to_project(self) -> None:          # برای هماهنگی با ``_collect_forms`` پنجره
        self._store()
        self.assets.save_to_project()           # v2.5.0 — نیروگاه‌ها و اتوبوستر

    # ------------------------------------------------------------------
    def _on_select(self, row: int) -> None:
        if self._loading:
            return
        ws = self._ws()
        names = self._scope_names(ws) if ws else []
        if ws is None or not (0 <= row < len(names)):
            self._feeder = None
            self._set_form_enabled(False)
            return
        self._feeder = ws.common_network.feeder(names[row])
        if self._feeder is None:                 # حفاظت در برابر ناسازگاری Scope و شبکه
            for k in self._scope_kinds():
                ws.add_to_scope(k, names[row])
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
            idx = self.cb_dg.findData(f.has_dg)
            self.cb_dg.setCurrentIndex(max(idx, 0))
            self.ed_dg_note.setText(f.dg_note)
            self.txt_normal.setPlainText(f.normal_scenario)
            self.txt_emergency.setPlainText(f.emergency_scenario)
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
    def _add_to_scope(self, name: str) -> None:
        ws = self._ws()
        name = (name or "").strip()
        if ws is None or not name:
            return
        for k in self._scope_kinds():
            ws.add_to_scope(k, name)
        self.refresh()
        names = self._scope_names(ws)
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
        for k in self._scope_kinds():
            ws.remove_from_scope(k, self._feeder.name)        # داده‌ی شبکه مشترک پاک نمی‌شود
        self._feeder = None
        self.refresh()
        self.changed.emit()
