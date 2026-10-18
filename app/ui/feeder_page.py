# -*- coding: utf-8 -*-
"""صفحه فیدرها — لیست فیدرها + فرم مشخصات + نتایج قبل/بعد + پروفیل و پیش‌بینی."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QSpinBox, QSplitter,
                               QTabWidget, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from app.core import loading_profile as lp
from app.core import forecast as fc_mod
from app.ui.excel_table import enable_excel_table
from app.ui.widgets import configure_data_table, fit_columns, scrollable
from app.core.models import Feeder, ForecastPoint
from app.core import traceability as trace
from app.ui.widgets import make_spin, page_header
from app.utils.errors import handle_error


ONOFF_COL = "در گزارش (On/Off)"
PEAK_COLS = [ONOFF_COL, "سال", "پیک واقعی (MW)", "منبع"]
# جدول پیش‌بینی (بخش ۲) — ستون ۰ = کلید «در گزارش» همان سال پیش‌بینی
FC_COLS = [ONOFF_COL, "سال", "پیک پیش‌بینی (MW)"]
FC_YEAR_COL = "سال"
FC_VALUE_COL = "پیک پیش‌بینی (MW)"


def _num_text(value) -> str:
    """نمایش عدد برای جدول‌های سال/پیک (سال بدون اعشار)."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if f == int(f):
        return str(int(f))
    return f"{f:g}"


class FeederPage(QWidget):
    changed = Signal()

    def __init__(self, manager, settings, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.settings = settings
        self.current: Feeder | None = None
        self._loading_ui = False
        self._peak_year_edited = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        self.header = page_header("ورود داده", "")
        root.addWidget(self.header)
        self._section = "input"

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # --- لیست فیدرها ---
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SingleSelection)
        self.list.currentRowChanged.connect(self._on_select)
        self.list.itemChanged.connect(self._list_item_changed)
        lv.addWidget(self.list, 1)
        lbl_list = QLabel("تیک کنار هر فیدر = لحاظ‌شدن آن در تحلیل و گزارش (On/Off)")
        lbl_list.setObjectName("Muted")
        lbl_list.setWordWrap(True)
        lv.addWidget(lbl_list)
        btns = QHBoxLayout()
        self.btn_add = QPushButton("+ فیدر")
        self.btn_del = QPushButton("حذف")
        self.btn_del.setObjectName("danger")
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_del)
        btns.addStretch(1)
        lv.addLayout(btns)
        splitter.addWidget(left)

        # --- فرم فیدر ---
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(12, 0, 0, 0)

        grp1 = self.grp_info = QGroupBox("مشخصات فیدر")
        f1 = QFormLayout(grp1)
        self.ed_name = QLineEdit()
        self.ed_substation = QLineEdit()
        self.sp_peak = make_spin(0, 1e4, 2)
        self.sp_peak_year = QSpinBox()
        self.sp_peak_year.setRange(1300, 1500)
        self.sp_pf = make_spin(0, 1, 2)
        self.sp_peak_i = make_spin(0, 1e4, 0)
        self.sp_imax = make_spin(0, 1e4, 0)
        self.sp_capacity = make_spin(0, 1e4, 2)
        self.ed_notes = QLineEdit()
        f1.addRow("نام فیدر:", self.ed_name)
        f1.addRow("نام پست:", self.ed_substation)
        f1.addRow("پیک بار (MW):", self.sp_peak)
        f1.addRow("سال پیک:", self.sp_peak_year)
        f1.addRow("ضریب توان در پیک:", self.sp_pf)
        f1.addRow("پیک جریان (A):", self.sp_peak_i)
        f1.addRow("حداکثر جریان مجاز هادی (A):", self.sp_imax)
        f1.addRow("معیار بارگذاری (MW):", self.sp_capacity)
        f1.addRow("توضیحات:", self.ed_notes)
        self.chk_enabled = QCheckBox("این فیدر در تحلیل و گزارش لحاظ شود (On/Off)")
        self.chk_enabled.setToolTip("خاموش = فیدر در Findings، جدول‌ها، پیش‌بینی و گزارش نمی‌آید؛ "
                                    "داده‌هایش حذف نمی‌شود و هر زمان می‌توانید روشن کنید.")
        self.chk_enabled.toggled.connect(self._enabled_toggled)
        f1.addRow("", self.chk_enabled)
        rv.addWidget(grp1)

        # --- پیش‌نمایش داده‌های واردشده (Data Preview) ---
        self.grp_preview = QGroupBox("پیش‌نمایش داده‌های همه فیدرها")
        vp = QVBoxLayout(self.grp_preview)
        self.preview_table = QTableWidget(0, 6)
        self.preview_table.setHorizontalHeaderLabels(
            ["فیدر", "پیک (MW)", "ضریب توان", "جریان مجاز (A)", "معیار (MW)", "وضعیت داده"])
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setMaximumHeight(170)
        enable_excel_table(self.preview_table, editable=False, auto_add_row=False)
        vp.addWidget(self.preview_table)
        rv.addWidget(self.grp_preview)

        # --- نتایج پخش بار ---
        grp2 = self.grp_pf = QGroupBox("نتایج پخش بار (PowerFactory)")
        v2 = QVBoxLayout(grp2)
        tabs = QTabWidget()
        self.tbl_before = self._results_table()
        self.tbl_after = self._results_table()
        tabs.addTab(self._wrap(self.tbl_before), "وضعیت فعلی (قبل)")
        tabs.addTab(self._wrap(self.tbl_after), "پس از اعمال بار (بعد)")
        v2.addWidget(tabs)
        rv.addWidget(grp2)

        # --- پروفیل بار (مستقل از پیش‌بینی) ---
        grp3 = self.grp_profile = QGroupBox("پروفیل بار (مبنای تحلیل پروفیل — نه پیش‌بینی)")
        v3 = QVBoxLayout(grp3)
        pbtns = QHBoxLayout()
        self.btn_import_profile = QPushButton("Import از Excel/CSV")
        self.btn_paste_profile = QPushButton("Paste داده")
        self.btn_stats = QPushButton("نمایش آمار")
        pbtns.addWidget(self.btn_import_profile)
        pbtns.addWidget(self.btn_paste_profile)
        pbtns.addWidget(self.btn_stats)
        pbtns.addStretch(1)
        v3.addLayout(pbtns)
        lbl_p = QLabel("پروفیل بار فقط برای تحلیل پروفیل (پیک، دامنه، ضریب توان) استفاده می‌شود و "
                       "مبنای محاسبه پیش‌بینی نیست. داده پیش‌بینی را در بخش پایین وارد کنید.")
        lbl_p.setObjectName("Muted")
        lbl_p.setWordWrap(True)
        v3.addWidget(lbl_p)
        self.profile_table = QTableWidget()
        self.profile_table.setMinimumHeight(150)
        self.profile_table.setMaximumHeight(200)
        enable_excel_table(self.profile_table, editable=False, auto_add_row=False)
        v3.addWidget(self.profile_table)
        rv.addWidget(grp3)

        # --- پیش‌بینی بار: داده واقعی و پیش‌بینی، دو بخش جدا ---
        grp4 = self.grp_forecast = QGroupBox("پیش‌بینی بار — داده واقعی و پیش‌بینی (دو بخش مستقل)")
        v4 = QVBoxLayout(grp4)
        lbl_f = QLabel("بخش ۱: پیک واقعی سال‌های گذشته را دستی وارد کنید. بخش ۲: نتیجه پیش‌بینی "
                       "سال‌های آینده به‌صورت جداگانه نمایش/ثبت می‌شود "
                       "(در حالت دستی، بخش ۲ را خودتان پر می‌کنید).")
        lbl_f.setObjectName("Muted")
        lbl_f.setWordWrap(True)
        v4.addWidget(lbl_f)

        self.lbl_peaks_title = QLabel("بخش ۱ — داده واقعی: پیک سال‌های گذشته")
        self.lbl_peaks_title.setObjectName("SectionTitle")
        v4.addWidget(self.lbl_peaks_title)
        self.tbl_peaks = QTableWidget(0, len(PEAK_COLS))
        self.tbl_peaks.setMinimumHeight(140)
        configure_data_table(self.tbl_peaks, PEAK_COLS, min_width=90)
        _pk = enable_excel_table(self.tbl_peaks, editable=True, auto_add_row=True)
        _pk.changed.connect(self._peaks_changed)
        self.tbl_peaks.itemChanged.connect(self._peaks_changed)
        lbl_pk = QLabel("ستون «در گزارش» = On/Off همان سال؛ سال غیرفعال در پیش‌بینی و گزارش "
                        "لحاظ نمی‌شود ولی داده‌اش پاک نمی‌شود.")
        lbl_pk.setObjectName("Muted")
        lbl_pk.setWordWrap(True)
        v4.addWidget(self.tbl_peaks, 2)
        pk_bar = QHBoxLayout()
        self.btn_peak_add = QPushButton("+ سال")
        self.btn_peak_del = QPushButton("حذف سال انتخاب‌شده")
        self.btn_peak_del.setObjectName("danger")
        self.btn_peak_profile = QPushButton("درج یک‌بارهٔ پیک‌های پروفیل (اختیاری)")
        self.btn_peak_profile.setObjectName("ghost")
        self.btn_peak_profile.setToolTip(
            "اگر پروفیل بار (چند سال) وارد شده باشد، پیک هر سال به جدول واقعی افزوده می‌شود؛ "
            "پس از درج قابل ویرایش است.")
        pk_bar.addWidget(self.btn_peak_add)
        pk_bar.addWidget(self.btn_peak_del)
        pk_bar.addWidget(self.btn_peak_profile)
        pk_bar.addStretch(1)
        v4.addLayout(pk_bar)

        f4 = QFormLayout()
        self.cb_fc_method = QComboBox()
        self.cb_fc_method.addItem("رگرسیون خطی روی داده واقعی (محاسبه خودکار)", "regression")
        self.cb_fc_method.addItem("ورود دستی پیش‌بینی (بخش ۲ را خودم پر می‌کنم)", "manual")
        f4.addRow("روش پیش‌بینی:", self.cb_fc_method)
        v4.addLayout(f4)

        self.lbl_fc_points_title = QLabel("بخش ۲ — پیش‌بینی سال‌های آینده")
        self.lbl_fc_points_title.setObjectName("SectionTitle")
        v4.addWidget(self.lbl_fc_points_title)
        self.tbl_fc_points = QTableWidget(0, len(FC_COLS))
        self.tbl_fc_points.setMinimumHeight(120)
        configure_data_table(self.tbl_fc_points, FC_COLS, min_width=100)
        _fp = enable_excel_table(self.tbl_fc_points, editable=True, auto_add_row=True)
        _fp.changed.connect(self._fc_points_changed)
        self.tbl_fc_points.itemChanged.connect(self._fc_points_changed)
        v4.addWidget(self.tbl_fc_points, 2)
        fc_bar = QHBoxLayout()
        self.btn_fc_add = QPushButton("+ سال پیش‌بینی")
        self.btn_fc_del = QPushButton("حذف سال انتخاب‌شده")
        self.btn_fc_del.setObjectName("danger")
        self.btn_fc_add.clicked.connect(lambda: self._add_year_row(self.tbl_fc_points))
        self.btn_fc_del.clicked.connect(lambda: self._del_year_row(self.tbl_fc_points, "سال پیش‌بینی"))
        fc_bar.addWidget(self.btn_fc_add)
        fc_bar.addWidget(self.btn_fc_del)
        fc_bar.addStretch(1)
        v4.addLayout(fc_bar)

        run_bar = QHBoxLayout()
        self.btn_auto_forecast = QPushButton("محاسبه پیش‌بینی سال‌های بعد (رگرسیون)")
        self.btn_auto_forecast.setObjectName("primary")
        self.btn_manual_fc = QPushButton("ثبت پیش‌بینی دستی")
        run_bar.addWidget(self.btn_auto_forecast)
        run_bar.addWidget(self.btn_manual_fc)
        run_bar.addStretch(1)
        v4.addLayout(run_bar)
        self.lbl_fc_status = QLabel("پیش‌بینی: —")
        self.lbl_fc_status.setObjectName("Muted")
        self.lbl_fc_status.setWordWrap(True)
        v4.addWidget(self.lbl_fc_status)
        rv.addWidget(grp4)

        rv.addStretch(1)
        splitter.addWidget(scrollable(right))
        splitter.setSizes([260, 640])

        # --- اتصال سیگنال‌ها ---
        self.btn_add.clicked.connect(self._add_feeder)
        self.btn_del.clicked.connect(self._del_feeder)
        for w in (self.ed_name, self.ed_substation, self.ed_notes):
            w.textChanged.connect(self._field_changed)
        for sp in (self.sp_peak, self.sp_peak_year, self.sp_pf, self.sp_peak_i,
                   self.sp_imax, self.sp_capacity):
            sp.valueChanged.connect(self._field_changed)
        self.tbl_before.itemChanged.connect(self._table_changed)
        self.tbl_after.itemChanged.connect(self._table_changed)
        self.btn_import_profile.clicked.connect(self._import_profile)
        self.btn_paste_profile.clicked.connect(self._paste_profile)
        self.btn_stats.clicked.connect(self._show_stats)
        self.btn_auto_forecast.clicked.connect(self._auto_forecast)
        self.btn_manual_fc.clicked.connect(self._manual_forecast)
        self.btn_peak_add.clicked.connect(lambda: self._add_year_row(self.tbl_peaks))
        self.btn_peak_del.clicked.connect(lambda: self._del_year_row(self.tbl_peaks, "سال واقعی"))
        self.btn_peak_profile.clicked.connect(self._peaks_from_profile)
        self.cb_fc_method.currentIndexChanged.connect(self._fc_method_changed)

    # ------------------------------------------------------------------
    @staticmethod
    def _results_table() -> QTableWidget:
        t = QTableWidget(4, 2)
        t.setHorizontalHeaderLabels(["پارامتر", "مقدار"])
        rows = [("جریان ابتدای فیدر (A)", "current"),
                ("تلفات (kW)", "loss"),
                ("حداقل ولتاژ فیدر (p.u.)", "vmin"),
                ("ولتاژ باس بار متقاضی (p.u.)", "vbus")]
        for i, (label, key) in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(label))
            t.setItem(i, 1, QTableWidgetItem(""))
            t.item(i, 0).setFlags(Qt.ItemIsEnabled)
        t.horizontalHeader().setStretchLastSection(True)
        enable_excel_table(t, editable=True, auto_add_row=False)
        return t

    @staticmethod
    def _wrap(table: QTableWidget) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 4, 4, 4)
        v.addWidget(table)
        return w

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._loading_ui = True
        self.list.clear()
        if not self.manager.project:
            self._loading_ui = False
            return
        for f in self.manager.project.feeders:
            it = QListWidgetItem(f.name or "(بی‌نام)")
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if getattr(f, "enabled", True) else Qt.Unchecked)
            if not getattr(f, "enabled", True):
                it.setToolTip("این فیدر در گزارش لحاظ نمی‌شود (On/Off).")
            self.list.addItem(it)
        # انتخاب لیست با فیدر جاری همگام شود (پس از افزودن/حذف)
        idx = next((i for i, fd in enumerate(self.manager.project.feeders)
                    if fd is self.current), -1)
        if idx >= 0:
            self.list.setCurrentRow(idx)
        elif self.list.count():
            self.current = self.manager.project.feeders[0]
            self.list.setCurrentRow(0)
        else:
            self.current = None
        self._loading_ui = False
        self._load_current()

    def _enabled_toggled(self, on: bool) -> None:
        """کلید On/Off فرم مشخصات فیدر (همگام با تیک لیست)."""
        if self._loading_ui:
            return
        f = self.current
        if f is None:
            return
        f.enabled = bool(on)
        self.manager.dirty = True
        self.changed.emit()
        self.refresh()

    def _list_item_changed(self, item: QListWidgetItem) -> None:
        """کلید On/Off فیدر در لیست — داده پاک نمی‌شود، فقط از گزارش/تحلیل حذف می‌شود."""
        if self._loading_ui or self.manager.project is None:
            return
        row = self.list.row(item)
        if not (0 <= row < len(self.manager.project.feeders)):
            return
        feeder = self.manager.project.feeders[row]
        feeder.enabled = item.checkState() == Qt.Checked
        item.setToolTip("" if feeder.enabled else "این فیدر در گزارش لحاظ نمی‌شود (On/Off).")
        self.manager.dirty = True
        self.changed.emit()
        self.refresh()

    def _on_select(self, row: int) -> None:
        if self._loading_ui:
            return
        self._save_current()
        if 0 <= row < len(self.manager.project.feeders):
            self.current = self.manager.project.feeders[row]
        else:
            self.current = None
        self._load_current()

    def _load_current(self) -> None:
        self._loading_ui = True
        f = self.current
        enabled = f is not None
        for w in (self.ed_name, self.ed_substation, self.ed_notes):
            w.setEnabled(enabled)
        for sp in (self.sp_peak, self.sp_peak_year, self.sp_pf, self.sp_peak_i,
                   self.sp_imax, self.sp_capacity):
            sp.setEnabled(enabled)
        self.tbl_before.setEnabled(enabled)
        self.tbl_after.setEnabled(enabled)
        self.btn_import_profile.setEnabled(enabled)
        self.btn_paste_profile.setEnabled(enabled)
        self.btn_auto_forecast.setEnabled(enabled)
        self.btn_manual_fc.setEnabled(enabled)
        for w in (self.btn_peak_add, self.btn_peak_del, self.btn_peak_profile,
                  self.btn_fc_add, self.btn_fc_del, self.tbl_peaks,
                  self.tbl_fc_points, self.cb_fc_method):
            w.setEnabled(enabled)
        if f is None:
            self._loading_ui = False
            return
        self.chk_enabled.setChecked(getattr(f, "enabled", True))
        self.ed_name.setText(f.name)
        self.ed_substation.setText(f.substation)
        self.sp_peak.setValue(f.peak_load_mw or 0)
        self._peak_year_edited = False
        self.sp_peak_year.setValue(f.peak_year or 1404)
        self.sp_pf.setValue(f.power_factor or 0)
        self.sp_peak_i.setValue(f.peak_current_a or 0)
        self.sp_imax.setValue(f.max_current_a or 0)
        self.sp_capacity.setValue(f.capacity_mw or 0)
        self.ed_notes.setText(f.notes)
        self._fill_results(self.tbl_before, f.before)
        self._fill_results(self.tbl_after, f.after)
        df = self.manager.get_profile(f)
        self._show_profile(df)
        # بخش ۱ (داده واقعی) از مدل؛ اگر خالی بود از تاریخچه پیش‌بینی قبلی (سازگاری با پروژه‌های قدیمی)
        peaks = [(p.year, p.value_mw, p.source or "MANUAL") for p in f.annual_peaks]
        flags: list[bool] | None = [getattr(p, "enabled", True) for p in f.annual_peaks]
        if not peaks and f.forecast.history_years:
            # سازگاری با پروژه‌های قدیمی: تاریخچهٔ پیش‌بینی به «داده واقعی» منتقل می‌شود
            peaks = [(y, v, "PROFILE") for y, v in zip(f.forecast.history_years,
                                                      f.forecast.history_values)]
            flags = None
        self._fill_peaks_table(peaks, flags)
        # بخش ۲ (پیش‌بینی)
        method = "manual" if f.forecast.method == "manual" else "regression"
        idx = self.cb_fc_method.findData(method)
        self.cb_fc_method.blockSignals(True)
        self.cb_fc_method.setCurrentIndex(max(0, idx))
        self.cb_fc_method.blockSignals(False)
        self._fill_fc_table(f.manual_forecast or f.forecast.points)
        self._fc_method_changed()
        self._update_fc_label()
        self._loading_ui = False
        self._refresh_preview()

    @staticmethod
    def _fill_results(table: QTableWidget, result) -> None:
        keys = ["current", "loss", "vmin", "vbus"]
        vals = [result.current_a, result.loss_kw, result.min_voltage_pu,
                result.applicant_bus_voltage_pu]
        digits = [0, 0, 3, 3]
        for i, (v, d) in enumerate(zip(vals, digits)):
            table.item(i, 1).setText("" if v is None else f"{v:.{d}f}".rstrip("0").rstrip(".") if d else str(int(v)))

    def _save_current(self) -> None:
        f = self.current
        if f is None:
            return
        _snap = trace.snapshot(f)
        f.enabled = self.chk_enabled.isChecked()
        f.name = self.ed_name.text().strip()
        f.substation = self.ed_substation.text().strip()
        f.peak_load_mw = self.sp_peak.value() or None
        # سال پیک فقط اگر کاربر ویرایشش کرده یا قبلاً مقدار داشته، ذخیره شود
        # (عدد ۱۴۰۴ فقط نمایش پیش‌فرض است، نه داده)
        if f.peak_year is not None or self._peak_year_edited:
            f.peak_year = self.sp_peak_year.value()
        f.power_factor = self.sp_pf.value() or None
        f.peak_current_a = self.sp_peak_i.value() or None
        f.max_current_a = self.sp_imax.value() or None
        f.capacity_mw = self.sp_capacity.value() or None
        f.notes = self.ed_notes.text().strip()
        self._read_results(self.tbl_before, f.before)
        self._read_results(self.tbl_after, f.after)
        trace.mark_manual_changes(f, _snap)

    @staticmethod
    def _read_results(table: QTableWidget, result) -> None:
        def val(i: int):
            txt = table.item(i, 1).text().strip().replace("،", "")
            if not txt:
                return None
            try:
                return float(txt)
            except ValueError:
                return None
        result.current_a = val(0)
        result.loss_kw = val(1)
        result.min_voltage_pu = val(2)
        result.applicant_bus_voltage_pu = val(3)

    # ------------------------------------------------------------------
    def _add_feeder(self) -> None:
        if not self.manager.project:
            return
        self._save_current()
        f = Feeder(name=f"فیدر {len(self.manager.project.feeders) + 1}")
        self.manager.project.feeders.append(f)
        self.manager.dirty = True
        self.current = f
        self.refresh()
        self.changed.emit()

    def _del_feeder(self) -> None:
        f = self.current
        if f is None or not self.manager.project:
            return
        if QMessageBox.question(self, "حذف فیدر", f"فیدر «{f.name}» حذف شود؟") != QMessageBox.Yes:
            return
        self.manager.project.feeders.remove(f)
        self.manager.dirty = True
        self.current = None
        self.refresh()
        self.changed.emit()

    def _table_changed(self, *_args) -> None:
        if self._loading_ui or self.current is None:
            return
        self._save_current()
        self.manager.dirty = True
        self._refresh_preview()
        self.changed.emit()

    # ------------------------------------------------------------------
    # بخش‌های صفحه: ورود داده / پروفیل و پیش‌بینی / پخش بار
    # ------------------------------------------------------------------
    SECTIONS = {
        "input": ("ورود داده", "مشخصات فیدرها، پیک بار و معیار بارگذاری؛ داده‌ها پیش از تحلیل اعتبارسنجی می‌شوند."),
        "profile": ("پروفیل بار و پیش‌بینی", "پروفیل بار از Excel/CSV (تحلیل پروفیل)؛ پیش‌بینی سال‌های بعد بر پایه «پیک سال‌های گذشته» که دستی وارد می‌کنید — دو بخش کاملاً جدا."),
        "loadflow": ("نتایج پخش بار (PowerFactory)", "نتایج قبل و بعد از اعمال بار؛ ولتاژ بر حسب p.u.، جریان بر حسب A و تلفات بر حسب kW."),
    }

    def show_section(self, name: str) -> None:
        name = name if name in self.SECTIONS else "input"
        self._section = name
        title, sub = self.SECTIONS[name]
        self.header.title_label.setText(title)
        sub_lbl = self.header.layout().itemAt(1)
        if sub_lbl is not None and sub_lbl.widget() is not None:
            sub_lbl.widget().setText(sub)
        self.grp_info.setVisible(name == "input")
        self.grp_preview.setVisible(name == "input")
        self.grp_pf.setVisible(name == "loadflow")
        self.grp_profile.setVisible(name == "profile")
        self.grp_forecast.setVisible(name == "profile")
        if name == "input":
            self._refresh_preview()

    def _refresh_preview(self) -> None:
        proj = self.manager.project
        tbl = self.preview_table
        tbl.setRowCount(0)
        if not proj:
            return
        from app.utils.formatting import fmt
        for f in proj.feeders:
            row = tbl.rowCount()
            tbl.insertRow(row)
            missing = f.peak_load_mw is None or not f.name
            vals = [f.display_name, fmt(f.peak_load_mw, 2), fmt(f.power_factor, 2),
                    fmt(f.max_current_a, 0), fmt(f.capacity_mw, 2),
                    "ناقص" if missing else ("کامل" if f.capacity_mw and f.max_current_a else "بخشی")]
            for c, v in enumerate(vals):
                tbl.setItem(row, c, QTableWidgetItem(v))

    def _field_changed(self, *args) -> None:
        if self._loading_ui:
            return
        if self.sender() is self.sp_peak_year:
            self._peak_year_edited = True
        self._save_current()
        row = self.list.currentRow()
        if 0 <= row < len(self.manager.project.feeders):
            self.list.item(row).setText(self.ed_name.text() or "(بی‌نام)")
        self.manager.dirty = True
        self.changed.emit()

    # ------------------------------------------------------------------
    # پروفیل بار
    # ------------------------------------------------------------------
    def _import_profile(self) -> None:
        f = self.current
        if f is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب فایل پروفیل بار", "",
            "Excel/CSV (*.xlsx *.xls *.csv)")
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                df = pd.read_csv(path, encoding="utf-8-sig")
            else:
                df = pd.read_excel(path)
        except Exception as exc:  # noqa: BLE001
            handle_error(self, exc, "خواندن فایل پروفیل")
            return
        std, errors = lp.parse_profile(df)
        if errors:
            QMessageBox.critical(self, "خطای ساختار فایل", "\n".join(errors))
            return
        std = lp.filter_feeder(std, f.name)
        if std.empty:
            std, _ = lp.parse_profile(df)  # بدون فیلتر فیدر
        self.manager.set_profile(f, std)
        f.profile_stats = lp.compute_stats(std)
        f.data_sources["profile"] = f"CSV|{Path(path).name}"
        self._show_profile(std)
        self.changed.emit()
        QMessageBox.information(self, "پروفیل بار",
                                f"{len(std)} نقطه وارد شد.\nپیک: {f.profile_stats.peak_p_mw} MW در {f.profile_stats.peak_date}")

    def _paste_profile(self) -> None:
        f = self.current
        if f is None:
            return
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getMultiLineText(
            self, "Paste پروفیل بار",
            "ستون‌ها: Date / Feeder / P_MW / Q_MVAR (جداشده با Tab یا کاما)\n"
            "می‌توانید مستقیماً از Excel کپی و اینجا Paste کنید:",
            "")
        if not ok or not text.strip():
            return
        std, errors = lp.parse_profile(text)
        if errors and std.empty:
            QMessageBox.critical(self, "خطا", "\n".join(errors))
            return
        std = lp.filter_feeder(std, f.name) if "feeder" in std.columns else std
        if std.empty:
            std, _ = lp.parse_profile(text)
        self.manager.set_profile(f, std)
        f.profile_stats = lp.compute_stats(std)
        self._show_profile(std)
        self.changed.emit()

    def _show_profile(self, df: pd.DataFrame | None) -> None:
        if df is None or df.empty:
            self.profile_table.setRowCount(0)
            self.profile_table.setColumnCount(0)
            return
        cols = [c for c in ("date", "feeder", "p_mw", "q_mvar") if c in df.columns]
        show = df[cols].head(500)
        self.profile_table.setColumnCount(len(cols))
        self.profile_table.setRowCount(len(show))
        self.profile_table.setHorizontalHeaderLabels(cols)
        for r in range(len(show)):
            for c, col in enumerate(cols):
                self.profile_table.setItem(r, c, QTableWidgetItem(str(show.iloc[r][col])))

    def _show_stats(self) -> None:
        f = self.current
        if f is None:
            return
        st = f.profile_stats
        if not st.n_points:
            QMessageBox.information(self, "آمار پروفیل", "پروفیلی وارد نشده است.")
            return
        QMessageBox.information(
            self, "آمار پروفیل بار",
            f"تعداد نقاط: {st.n_points}\n"
            f"بازه: {st.period_start} تا {st.period_end}\n"
            f"پیک P: {st.peak_p_mw} MW در {st.peak_date}\n"
            f"پیک Q: {st.peak_q_mvar} MVAr\n"
            f"ضریب توان در پیک: {st.power_factor_at_peak}\n"
            f"حداقل/میانگین P: {st.min_p_mw} / {st.avg_p_mw} MW")

    # ------------------------------------------------------------------
    # پیش‌بینی
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # پیش‌بینی: بخش ۱ داده واقعی (ورود دستی) — بخش ۲ پیش‌بینی، کاملاً جدا
    # ------------------------------------------------------------------
    def _loading_guard(self) -> bool:
        return getattr(self, "_loading_ui", False) or getattr(self, "_loading_fc", False)

    def _set_fc_loading(self, on: bool) -> None:
        self._loading_fc = on

    # ---- جدول داده واقعی (پیک سال‌های گذشته) ----
    def _peak_rows_full(self, active_only: bool = False) -> list[tuple[int, int, float, str]]:
        """(شماره ردیف جدول، سال، پیک MW، منبع) — خانه خالی نادیده گرفته می‌شود.

        با ``active_only=True`` ردیف‌های On/Off خاموش («در گزارش») حذف می‌شوند.
        """
        rows: list[tuple[int, int, float, str]] = []
        for r in range(self.tbl_peaks.rowCount()):
            if active_only and not self._onoff_state(self.tbl_peaks, r):
                continue
            y = self._cell_num(self.tbl_peaks, r, 1)
            v = self._cell_num(self.tbl_peaks, r, 2)
            if y is None or v is None:
                continue
            rows.append((r, int(y), float(v),
                         self._cell_text(self.tbl_peaks, r, 3) or "MANUAL"))
        return rows

    def _peak_rows(self, active_only: bool = False) -> list[tuple[int, float, str]]:
        """(سال، پیک MW، منبع) — نمای سه‌عضوی برای مصرف‌کننده‌های موجود."""
        return [(y, v, src) for _r, y, v, src in self._peak_rows_full(active_only)]

    @staticmethod
    def _onoff_state(table: QTableWidget, r: int, col: int = 0) -> bool:
        """وضعیت کلید «در گزارش» ردیف (پیش‌فرض: روشن)."""
        item = table.item(r, col)
        if item is None:
            return True
        state = item.data(Qt.CheckStateRole)
        if state is None:
            return True                     # کلید هرگز تنظیم نشده (یا متن بازنویسی شده) → روشن
        return Qt.CheckState(state) == Qt.Checked

    def _set_onoff(self, table: QTableWidget, r: int, state: bool, col: int = 0) -> None:
        item = table.item(r, col)
        if item is None:
            item = QTableWidgetItem("")
            table.setItem(r, col, item)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
        item.setCheckState(Qt.Checked if state else Qt.Unchecked)
        item.setTextAlignment(Qt.AlignCenter)
        item.setToolTip("روشن = این ردیف در گزارش و محاسبات لحاظ می‌شود.")

    def _fill_peaks_table(self, rows: list[tuple[int, float, str]],
                          enabled: list[bool] | None = None) -> None:
        """پرکردن جدول پیک‌ها؛ ستون ۰ = کلید «در گزارش» همان سال."""
        self._set_fc_loading(True)
        try:
            t = self.tbl_peaks
            t.setRowCount(0)
            for i, (y, v, src) in enumerate(rows):
                r = t.rowCount()
                t.insertRow(r)
                t.setItem(r, 0, QTableWidgetItem(""))
                self._set_onoff(t, r, True if enabled is None else
                                (i < len(enabled) and enabled[i]))
                for c, val in enumerate((y, v, src), start=1):
                    item = QTableWidgetItem(_num_text(val))
                    item.setTextAlignment(Qt.AlignCenter)
                    if c == 3:
                        item.setFlags(Qt.ItemIsEnabled)
                    t.setItem(r, c, item)
            fit_columns(t, min_width=90)
        finally:
            self._set_fc_loading(False)

    def _save_peaks(self) -> None:
        f = self.current
        if f is None:
            return
        f.annual_peaks = [ForecastPoint(year=y, value_mw=v, source=src,
                                        enabled=self._onoff_state(self.tbl_peaks, row))
                          for row, y, v, src in self._peak_rows_full()]
        self.manager.dirty = True

    def _peaks_changed(self, *_a) -> None:
        if self._loading_guard():
            return
        fit_columns(self.tbl_peaks)
        self._save_peaks()
        self.changed.emit()

    def _peaks_from_profile(self) -> None:
        """درج یک‌بارهٔ پیک سال‌های پروفیل در جدول واقعی — فقط با درخواست صریح کاربر."""
        f = self.current
        if f is None:
            return
        df = self.manager.get_profile(f)
        if df is None or df.empty:
            QMessageBox.warning(self, "پیک‌های پروفیل",
                                "پروفیلی وارد نشده است؛ ابتدا پروفیل بار را Import/Paste کنید.")
            return
        years, values = lp.annual_peaks(df)
        if not years:
            QMessageBox.warning(self, "پیک‌های پروفیل", "از پروفیل فعلی پیک سالانه استخراج نشد.")
            return
        added = 0
        current = [(y, v, src) for _r, y, v, src in self._peak_rows_full()]
        flags = [self._onoff_state(self.tbl_peaks, r) for r, _y, _v, _s in self._peak_rows_full()]
        pairs = sorted(zip(current, flags), key=lambda x: x[0][0])
        current = [c for c, _f in pairs]
        flags = [f for _c, f in pairs]
        for y, v in zip(years, values):
            if any(y == cy for cy, _v, _s in current):
                continue
            current.append((y, v, "PROFILE"))
            flags.append(True)
            added += 1
        current.sort(key=lambda x: x[0])
        self._fill_peaks_table(current, flags)
        self._save_peaks()
        self.manager.save()
        self.changed.emit()
        QMessageBox.information(
            self, "پیک‌های پروفیل",
            f"{added} پیک سالانه از پروفیل در «داده واقعی» درج شد (منبع: PROFILE).\n"
            "می‌توانید مقادیر را ویرایش کنید؛ این جدول مبنای پیش‌بینی است.")

    # ---- جدول پیش‌بینی (بخش ۲) ----
    @staticmethod
    def _column(table: QTableWidget, title: str, default: int) -> int:
        """شماره ستون بر مبنای **عنوان ستون** (نگاشت هرگز بر پایهٔ شماره ستون نیست)."""
        for c in range(table.columnCount()):
            head = table.horizontalHeaderItem(c)
            if head is not None and head.text().strip() == title:
                return c
        return default

    def _fc_rows_full(self, active_only: bool = False) -> list[tuple[int, int, float, bool]]:
        """(شماره ردیف، سال، پیک MW، روشن) — نگاشت با عنوان ستون، نه شماره ستون.

        با ``active_only=True`` سطرهای خاموش («در گزارش» = Off) حذف می‌شوند؛ مقدارشان
        در جدول باقی می‌ماند و فقط از گزارش/محاسبه خارج می‌گردد.
        """
        t = self.tbl_fc_points
        c_year = self._column(t, FC_YEAR_COL, self._onoff_column(t))
        c_val = self._column(t, FC_VALUE_COL, c_year + 1)
        rows: list[tuple[int, int, float, bool]] = []
        for r in range(t.rowCount()):
            on = self._onoff_state(t, r) if self._onoff_column(t) else True
            if active_only and not on:
                continue
            y = self._cell_num(t, r, c_year)
            v = self._cell_num(t, r, c_val)
            if y is None or v is None:
                continue
            rows.append((r, int(y), float(v), on))
        return sorted(rows, key=lambda x: x[1])

    def _fc_rows(self, active_only: bool = False) -> list[tuple[int, float]]:
        """(سال، پیک پیش‌بینی) — نمای دوعضوی برای مصرف‌کننده‌های موجود."""
        return [(y, v) for _r, y, v, _on in self._fc_rows_full(active_only)]

    def _fc_enabled(self) -> list[bool]:
        """پرچم On/Off همهٔ سطرهای جدول (برای ذخیره در مدل)."""
        t = self.tbl_fc_points
        onoff = self._onoff_column(t)
        if not onoff:
            return [True] * t.rowCount()
        return [self._onoff_state(t, r) for r in range(t.rowCount())]

    def _fill_fc_table(self, points: list) -> None:
        self._set_fc_loading(True)
        try:
            t = self.tbl_fc_points
            t.setRowCount(0)
            c_year = self._column(t, FC_YEAR_COL, self._onoff_column(t))
            c_val = self._column(t, FC_VALUE_COL, c_year + 1)
            for p in points:
                r = t.rowCount()
                t.insertRow(r)
                for c in range(t.columnCount()):
                    item = QTableWidgetItem("")
                    item.setTextAlignment(Qt.AlignCenter)
                    t.setItem(r, c, item)
                if self._onoff_column(t):
                    self._set_onoff(t, r, bool(getattr(p, "enabled", True)))
                t.item(r, c_year).setText(_num_text(p.year))
                t.item(r, c_val).setText(_num_text(p.value_mw))
            fit_columns(t, min_width=100)
        finally:
            self._set_fc_loading(False)

    def _save_fc_flags(self) -> None:
        """ذخیرهٔ وضعیت On/Off سطرهای پیش‌بینی در مدل (مقادیر دست‌نخورده می‌مانند)."""
        f = self.current
        if f is None:
            return
        flags = self._fc_enabled()
        for group in (f.forecast.points, f.manual_forecast):
            for i, p in enumerate(group):
                if i < len(flags):
                    p.enabled = flags[i]
        self.manager.dirty = True

    def _fc_points_changed(self, *_a) -> None:
        if self._loading_guard():
            return
        fit_columns(self.tbl_fc_points)
        self._save_fc_flags()
        if self.cb_fc_method.currentData() == "manual":
            self.btn_manual_fc.setEnabled(True)
        self.changed.emit()

    # ---- ابزار سطر ----
    def _add_year_row(self, table: QTableWidget) -> None:
        flag_col = self._onoff_column(table)
        last = self._cell_num(table, table.rowCount() - 1, flag_col) if table.rowCount() else None
        base = int(last) if last else ((self.current.peak_year or 1403) if self.current else 1403)
        r = table.rowCount()
        table.insertRow(r)
        if flag_col > 0:
            table.setItem(r, 0, QTableWidgetItem(""))
            self._set_onoff(table, r, True)
        item = QTableWidgetItem(str(base + 1)); item.setTextAlignment(Qt.AlignCenter)
        table.setItem(r, flag_col, item)
        for c in range(flag_col + 1, table.columnCount()):
            it = QTableWidgetItem(""); it.setTextAlignment(Qt.AlignCenter)
            table.setItem(r, c, it)
        fit_columns(table)
        if table is self.tbl_peaks:
            self._save_peaks()
        self.changed.emit()

    def _del_year_row(self, table: QTableWidget, what: str) -> None:
        row = table.currentRow()
        if row < 0:
            QMessageBox.information(self, "حذف سطر", f"ابتدا یک {what} را انتخاب کنید.")
            return
        table.removeRow(row)
        fit_columns(table)
        if table is self.tbl_peaks:
            self._save_peaks()
        self.changed.emit()

    def _onoff_column(self, table: QTableWidget) -> int:
        """شماره ستون داده‌ای اول (۱ اگر جدول ستون «در گزارش» داشته باشد)."""
        first = table.horizontalHeaderItem(0)
        return 1 if (first is not None and first.text() == ONOFF_COL) else 0

    @staticmethod
    def _cell_num(table: QTableWidget, r: int, c: int):
        item = table.item(r, c)
        if item is None:
            return None
        raw = item.text().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
                                                  "01234567890123456789"))
        raw = raw.replace("٬", "").replace(",", "").strip()
        try:
            return float(raw)
        except ValueError:
            return None

    @staticmethod
    def _cell_text(table: QTableWidget, r: int, c: int) -> str:
        item = table.item(r, c)
        return item.text().strip() if item else ""

    # ---- روش پیش‌بینی ----
    def _fc_method_changed(self, *_a) -> None:
        manual = self.cb_fc_method.currentData() == "manual"
        self.btn_auto_forecast.setVisible(not manual)
        self.btn_manual_fc.setVisible(manual)
        self.tbl_fc_points.setEditTriggers(
            QTableWidget.AllEditTriggers if manual else QTableWidget.NoEditTriggers)
        for w in (self.btn_fc_add, self.btn_fc_del):
            w.setVisible(manual)
        if manual and self.tbl_fc_points.rowCount() == 0 and self.current is not None:
            start = 0
            if self.current.annual_peaks:
                start = max(p.year for p in self.current.annual_peaks)
            elif self.current.peak_year:
                start = self.current.peak_year
            horizon = self.settings.thresholds.forecast_years or 5
            self._fill_fc_table([ForecastPoint(year=start + k, value_mw=0.0, enabled=True)
                                 for k in range(1, int(horizon) + 1)])

    def _auto_forecast(self) -> None:
        """محاسبه پیش‌بینی از «داده واقعی» واردشده — پروفیل بار مبنای محاسبه نیست."""
        f = self.current
        if f is None:
            return
        self._save_peaks()
        active = [p for p in f.annual_peaks if getattr(p, "enabled", True)]
        years = [p.year for p in active]
        values = [p.value_mw for p in active]
        th = self.settings.thresholds
        min_pts = th.forecast_min_history
        if len(years) < min_pts:
            QMessageBox.warning(
                self, "پیش‌بینی",
                "داده واقعی کافی نیست.\n"
                f"پیک {min_pts} سال گذشته (یا بیشتر) را در «بخش ۱ — داده واقعی» وارد کنید.\n"
                f"تعداد واردشده: {len(years)} سال.\n\n"
                "هیچ مقدار پیش‌فرض یا استخراج خودکار از پروفیل بار انجام نمی‌شود.")
            return
        fc = fc_mod.linear_forecast(years, values, th.forecast_years, min_pts, th=th)
        f.forecast = fc
        self.manager.dirty = True
        self._fill_fc_table(fc.points)
        self._update_fc_label()
        self.changed.emit()
        if fc.method == "none":
            QMessageBox.warning(self, "پیش‌بینی", fc.note or "پیش‌بینی قابل اتکا محاسبه نشد.")
        else:
            r2 = f" — R² = {fc.r2}" if fc.r2 is not None else ""
            warn = f"\n⚠ نیازمند بررسی مهندس: {fc.note}" if fc.needs_review else ""
            QMessageBox.information(
                self, "پیش‌بینی سال‌های بعد",
                f"مبنای محاسبه: {len(years)} سال داده واقعی واردشده{r2}\n"
                f"پیک سال {fc.end_year()}: {fc.end_value()} MW{warn}")

    def _manual_forecast(self) -> None:
        """ثبت پیش‌بینی دستی (بخش ۲) — مستقل از داده واقعی و بدون هیچ تغییری در آن."""
        f = self.current
        if f is None:
            return
        rows = self._fc_rows_full()
        if not rows:
            QMessageBox.warning(self, "پیش‌بینی دستی",
                                "هیچ سطر پرشده‌ای در بخش ۲ وجود ندارد؛ سال و پیک پیش‌بینی را وارد کنید.")
            return
        active = [(y, v) for _r, y, v, on in rows if on]
        excluded = len(rows) - len(active)
        # همهٔ سطرها (حتی خاموش) در مدل می‌مانند؛ محاسبه فقط روی سطرهای روشن انجام می‌شود.
        f.manual_forecast = [ForecastPoint(year=y, value_mw=v, source="MANUAL", enabled=on)
                             for _r, y, v, on in rows]
        if not active:
            QMessageBox.warning(self, "پیش‌بینی دستی",
                                "همهٔ سطرهای بخش ۲ غیرفعال (Off) هستند؛ پیش‌بینی ثبت نشد.\n"
                                "برای ثبت، حداقل یک سطر را روشن (On) کنید.")
            self.manager.dirty = True
            self.changed.emit()
            return
        points = sorted(active)
        f.forecast = fc_mod.manual_forecast(points)
        self.manager.dirty = True
        self._update_fc_label()
        self.changed.emit()
        note = f"\n{excluded} سطر غیرفعال (Off) در محاسبه لحاظ نشد." if excluded else ""
        QMessageBox.information(self, "پیش‌بینی دستی",
                                f"{len(points)} سال پیش‌بینی دستی ثبت شد "
                                f"(آخرین: {points[-1][0]} ← {points[-1][1]} MW).{note}")

    def _update_fc_label(self) -> None:
        f = self.current
        if f is None:
            self.lbl_fc_status.setText("پیش‌بینی: —")
            return
        fc = f.forecast
        if not fc.available:
            msg = "پیش‌بینی: موجود نیست"
            if fc.needs_review and fc.note:
                msg += f" — ⚠ نیازمند بررسی مهندس: {fc.note}"
        else:
            kind = "رگرسیون خطی" if fc.method == "regression" else "دستی"
            r2 = f"، R² = {fc.r2}" if fc.r2 is not None else ""
            msg = f"پیش‌بینی: {kind}{r2} — پیک سال {fc.end_year()}: {fc.end_value()} MW"
            if fc.needs_review:
                msg += f"\n⚠ REQUIRES_ENGINEER_REVIEW — {fc.note}"
        self.lbl_fc_status.setText(msg)
        self.lbl_fc_status.setWordWrap(True)
