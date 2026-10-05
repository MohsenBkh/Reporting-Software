# -*- coding: utf-8 -*-
"""صفحه فیدرها — لیست فیدرها + فرم مشخصات + نتایج قبل/بعد + پروفیل و پیش‌بینی."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QSpinBox, QSplitter, QTabWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from app.core import loading_profile as lp
from app.core import forecast as fc_mod
from app.core.models import Feeder
from app.core import traceability as trace
from app.ui.widgets import make_spin, page_header
from app.utils.errors import handle_error


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
        self.list.currentRowChanged.connect(self._on_select)
        lv.addWidget(self.list, 1)
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
        rv.addWidget(grp1)

        # --- کنترل بارگذاری و راهکارهای تعدیل بار (بخش ۸ گزارش) ---
        grp_ctl = self.grp_control = QGroupBox("کنترل بارگذاری و راهکار تعدیل بار (اختیاری)")
        vc = QVBoxLayout(grp_ctl)
        fc = QFormLayout()
        self.ed_solution = QLineEdit()
        self.ed_solution.setPlaceholderText(
            "مثال: بازآرایی با فیدرهای همجوار / احداث فیدر جدید")
        fc.addRow("راهکار پیشنهادی (تعدیل بار):", self.ed_solution)
        vc.addLayout(fc)
        self.tbl_adjacent = QTableWidget(0, 2)
        self.tbl_adjacent.setHorizontalHeaderLabels(["نام فیدر همجوار", "پیک بار (MW)"])
        self.tbl_adjacent.horizontalHeader().setStretchLastSection(True)
        self.tbl_adjacent.setAlternatingRowColors(True)
        self.tbl_adjacent.setMaximumHeight(120)
        vc.addWidget(self.tbl_adjacent)
        abtns = QHBoxLayout()
        self.btn_adj_add = QPushButton("+ فیدر همجوار")
        self.btn_adj_del = QPushButton("حذف ردیف")
        abtns.addWidget(self.btn_adj_add)
        abtns.addWidget(self.btn_adj_del)
        abtns.addStretch(1)
        vc.addLayout(abtns)
        rv.addWidget(grp_ctl)

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

        # --- پروفیل و پیش‌بینی ---
        grp3 = self.grp_profile = QGroupBox("پروفیل بار و پیش‌بینی")
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
        self.profile_table = QTableWidget()
        self.profile_table.setMaximumHeight(160)
        v3.addWidget(self.profile_table)

        f3 = QFormLayout()
        self.btn_auto_forecast = QPushButton("محاسبه پیش‌بینی ۵ ساله (رگرسیون)")
        self.btn_manual_fc = QPushButton("ویرایش دستی پیش‌بینی")
        self.lbl_fc_status = QLabel("پیش‌بینی: —")
        self.lbl_fc_status.setObjectName("Muted")
        f3.addRow(self.btn_auto_forecast)
        f3.addRow(self.btn_manual_fc)
        f3.addRow(self.lbl_fc_status)
        v3.addLayout(f3)
        rv.addWidget(grp3)

        rv.addStretch(1)
        splitter.addWidget(right)
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
        self.ed_solution.textChanged.connect(self._field_changed)
        self.tbl_adjacent.itemChanged.connect(self._table_changed)
        self.btn_adj_add.clicked.connect(self._add_adjacent)
        self.btn_adj_del.clicked.connect(self._del_adjacent)

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
            self.list.addItem(QListWidgetItem(f.name or "(بی‌نام)"))
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
        self.ed_solution.setEnabled(enabled)
        self.tbl_adjacent.setEnabled(enabled)
        self.btn_adj_add.setEnabled(enabled)
        self.btn_adj_del.setEnabled(enabled)
        self.tbl_before.setEnabled(enabled)
        self.tbl_after.setEnabled(enabled)
        self.btn_import_profile.setEnabled(enabled)
        self.btn_paste_profile.setEnabled(enabled)
        self.btn_auto_forecast.setEnabled(enabled)
        self.btn_manual_fc.setEnabled(enabled)
        if f is None:
            self._loading_ui = False
            return
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
        self.ed_solution.setText(f.control_solution or "")
        self._fill_adjacent(f)
        self._fill_results(self.tbl_before, f.before)
        self._fill_results(self.tbl_after, f.after)
        df = self.manager.get_profile(f)
        self._show_profile(df)
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
        f.control_solution = self.ed_solution.text().strip()
        f.adjacent_feeders = self._read_adjacent()
        self._read_results(self.tbl_before, f.before)
        self._read_results(self.tbl_after, f.after)
        trace.mark_manual_changes(f, _snap)

    # ------------------------------------------------------------------
    def _fill_adjacent(self, f: Feeder) -> None:
        t = self.tbl_adjacent
        t.setRowCount(0)
        for a in f.adjacent_feeders:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, QTableWidgetItem(a.name))
            t.setItem(r, 1, QTableWidgetItem("" if a.load_mw is None else str(a.load_mw)))

    def _read_adjacent(self) -> list:
        from app.core.models import AdjacentFeeder
        out = []
        t = self.tbl_adjacent
        for r in range(t.rowCount()):
            name = (t.item(r, 0).text().strip() if t.item(r, 0) else "")
            txt = (t.item(r, 1).text().strip() if t.item(r, 1) else "")
            if not name:
                continue
            try:
                load = float(txt.replace("٫", ".")) if txt else None
            except ValueError:
                load = None
            out.append(AdjacentFeeder(name=name, load_mw=load))
        return out

    def _add_adjacent(self) -> None:
        if self.current is None:
            return
        t = self.tbl_adjacent
        r = t.rowCount()
        t.insertRow(r)
        t.setItem(r, 0, QTableWidgetItem(""))
        t.setItem(r, 1, QTableWidgetItem(""))
        t.editItem(t.item(r, 0))

    def _del_adjacent(self) -> None:
        t = self.tbl_adjacent
        rows = sorted({i.row() for i in t.selectedIndexes()}, reverse=True)
        for r in rows or ([t.rowCount() - 1] if t.rowCount() else []):
            t.removeRow(r)
        self._table_changed()

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
        "profile": ("پروفیل بار و پیش‌بینی", "ورود پروفیل بار از Excel/CSV، پیک سالانه و پیش‌بینی ۵ ساله همراه با کنترل کیفیت داده."),
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
    def _auto_forecast(self) -> None:
        f = self.current
        if f is None:
            return
        df = self.manager.get_profile(f)
        if df is None or df.empty:
            QMessageBox.warning(self, "پیش‌بینی",
                                "ابتدا پروفیل بار فیدر را وارد کنید (پیک سالانه از آن استخراج می‌شود).")
            return
        years, values = lp.annual_peaks(df)
        th = self.settings.thresholds
        fc = fc_mod.linear_forecast(years, values, th.forecast_years, th.forecast_min_history, th=th)
        f.forecast = fc
        self.manager.dirty = True
        self._update_fc_label()
        self.changed.emit()
        if fc.method == "none":
            QMessageBox.warning(self, "پیش‌بینی", fc.note or "داده کافی برای پیش‌بینی قابل اتکا وجود ندارد.")
        else:
            r2 = f" ، R² = {fc.r2}" if fc.r2 is not None else ""
            QMessageBox.information(self, "پیش‌بینی ۵ ساله",
                                    f"روش: رگرسیون خطی{r2}\n"
                                    f"پیک سال {fc.end_year()}: {fc.end_value()} MW")

    def _manual_forecast(self) -> None:
        f = self.current
        if f is None:
            return
        from PySide6.QtWidgets import QInputDialog
        existing = "\n".join(f"{p.year}\t{p.value_mw}" for p in f.forecast.points)
        text, ok = QInputDialog.getMultiLineText(
            self, "ویرایش دستی پیش‌بینی",
            "هر سطر: سال<TAB>پیک پیش‌بینی‌شده (MW)\nمثال: 1405\t6.9",
            existing)
        if not ok:
            return
        pts = []
        for line in text.splitlines():
            parts = line.replace("،", " ").split()
            if len(parts) >= 2:
                try:
                    pts.append((int(float(parts[0])), float(parts[1])))
                except ValueError:
                    continue
        if not pts:
            f.forecast = fc_mod.ForecastResult(method="none")
        else:
            f.forecast = fc_mod.manual_forecast(pts)
        self.manager.dirty = True
        self._update_fc_label()
        self.changed.emit()

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
