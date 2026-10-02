# -*- coding: utf-8 -*-
"""صفحه تنظیمات — شرکت، فونت، Thresholdهای Rule Engine (بخش ۳۰ سند)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFontComboBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSpinBox, QVBoxLayout,
                               QWidget)


class SettingsPage(QWidget):
    changed = Signal()

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        # محتوای بلند داخل QScrollArea تا فرم‌ها با کمبود فضا فشرده نشوند
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("Page")
        root = QVBoxLayout(body)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(12)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        title = QLabel("تنظیمات")
        title.setObjectName("PageTitle")
        root.addWidget(title)

        # --- اطلاعات شرکت ---
        grp1 = QGroupBox("اطلاعات شرکت (سربرگ و جلد گزارش)")
        f1 = QFormLayout(grp1)
        self.ed_company = QLineEdit(settings.company_name)
        self.ed_unit = QLineEdit(settings.unit_name)
        self.ed_office = QLineEdit(settings.office_name)
        self.ed_prefix = QLineEdit(settings.report_prefix)
        self.ed_output = QLineEdit(settings.output_dir)
        btn_output = QPushButton("...")
        btn_output.setFixedWidth(36)
        self.ed_logo = QLineEdit(getattr(settings, "company_logo", ""))
        self.ed_logo.setPlaceholderText("خالی = لوگوی پیش‌فرض همراه برنامه (resource/logo.png)")
        btn_logo = QPushButton("...")
        btn_logo.setFixedWidth(36)
        btn_logo.setToolTip("انتخاب تصویر لوگو (PNG / JPG / ICO)")
        f1.addRow("نام شرکت:", self.ed_company)
        f1.addRow("نام واحد:", self.ed_unit)
        f1.addRow("نام دفتر/گروه:", self.ed_office)
        f1.addRow("پیشوند شماره گزارش:", self.ed_prefix)
        row_out = QHBoxLayout()
        row_out.addWidget(self.ed_output)
        row_out.addWidget(btn_output)
        f1.addRow("مسیر خروجی پیش‌فرض:", row_out)
        row_logo = QHBoxLayout()
        row_logo.addWidget(self.ed_logo)
        row_logo.addWidget(btn_logo)
        f1.addRow("لوگوی جلد گزارش:", row_logo)
        root.addWidget(grp1)

        # --- فونت ---
        grp2 = QGroupBox("فونت گزارش Word")
        f2 = QFormLayout(grp2)
        self.cb_body = QFontComboBox()
        self.cb_body.setCurrentText(settings.fonts.body_font)
        self.sp_body = QSpinBox()
        self.sp_body.setRange(8, 24)
        self.sp_body.setValue(settings.fonts.body_size)
        self.cb_heading = QFontComboBox()
        self.cb_heading.setCurrentText(settings.fonts.heading_font)
        f2.addRow("فونت متن:", self.cb_body)
        f2.addRow("اندازه متن:", self.sp_body)
        f2.addRow("فونت تیترها:", self.cb_heading)
        root.addWidget(grp2)

        # --- Thresholdهای Rule Engine ---
        th = settings.thresholds
        grp3 = QGroupBox("حدآستانه‌های موتور قواعد (Thresholds)")
        f3 = QFormLayout(grp3)
        self.sp_vmin = QDoubleSpinBox()
        self.sp_vmin.setRange(0.8, 1.1)
        self.sp_vmin.setDecimals(3)
        self.sp_vmin.setValue(th.voltage_min_pu)
        self.sp_vmax = QDoubleSpinBox()
        self.sp_vmax.setRange(0.8, 1.2)
        self.sp_vmax.setDecimals(3)
        self.sp_vmax.setValue(th.voltage_max_pu)
        self.sp_vchg = QDoubleSpinBox()
        self.sp_vchg.setRange(0.5, 30)
        self.sp_vchg.setDecimals(1)
        self.sp_vchg.setValue(th.voltage_change_max_pct)
        self.sp_l1 = QDoubleSpinBox()
        self.sp_l1.setRange(0, 100)
        self.sp_l1.setValue(th.loading_light_pct)
        self.sp_l2 = QDoubleSpinBox()
        self.sp_l2.setRange(0, 150)
        self.sp_l2.setValue(th.loading_normal_pct)
        self.sp_l3 = QDoubleSpinBox()
        self.sp_l3.setRange(0, 200)
        self.sp_l3.setValue(th.loading_semi_pct)
        self.sp_l4 = QDoubleSpinBox()
        self.sp_l4.setRange(0, 300)
        self.sp_l4.setValue(th.loading_heavy_pct)
        self.sp_fc_years = QSpinBox()
        self.sp_fc_years.setRange(1, 15)
        self.sp_fc_years.setValue(th.forecast_years)
        self.sp_fc_min = QSpinBox()
        self.sp_fc_min.setRange(2, 10)
        self.sp_fc_min.setValue(th.forecast_min_history)
        self.sp_growth_lo = QDoubleSpinBox()
        self.sp_growth_lo.setRange(0, 30)
        self.sp_growth_lo.setDecimals(1)
        self.sp_growth_lo.setValue(th.growth_low_pct)
        self.sp_growth_hi = QDoubleSpinBox()
        self.sp_growth_hi.setRange(0, 50)
        self.sp_growth_hi.setDecimals(1)
        self.sp_growth_hi.setValue(th.growth_high_pct)
        f3.addRow("حداقل ولتاژ مجاز (p.u.):", self.sp_vmin)
        f3.addRow("حداکثر ولتاژ مجاز (p.u.):", self.sp_vmax)
        f3.addRow("حداکثر تغییر ولتاژ پس از بار جدید (٪):", self.sp_vchg)
        f3.addRow("مرز کم‌بار/عادی (٪ معیار):", self.sp_l1)
        f3.addRow("مرز عادی/نسبتاً پربار (٪):", self.sp_l2)
        f3.addRow("مرز نسبتاً پربار/پربار (٪):", self.sp_l3)
        f3.addRow("مرز پربار/بحرانی (٪):", self.sp_l4)
        f3.addRow("افق پیش‌بینی (سال):", self.sp_fc_years)
        f3.addRow("حداقل داده تاریخی برای رگرسیون:", self.sp_fc_min)
        f3.addRow("رشد کم زیر (٪/سال):", self.sp_growth_lo)
        f3.addRow("رشد زیاد بالای (٪/سال):", self.sp_growth_hi)
        root.addWidget(grp3)

        # --- کیفیت داده پیش‌بینی ---
        grp4 = QGroupBox("کنترل کیفیت داده پیش‌بینی (در صورت عدم رعایت: REQUIRES_ENGINEER_REVIEW)")
        f4 = QFormLayout(grp4)
        th = settings.thresholds
        self.sp_r2 = QDoubleSpinBox(); self.sp_r2.setRange(0, 1); self.sp_r2.setDecimals(2); self.sp_r2.setSingleStep(0.05)
        self.sp_r2.setValue(th.forecast_r2_min)
        self.sp_sigma = QDoubleSpinBox(); self.sp_sigma.setRange(1, 10); self.sp_sigma.setDecimals(1)
        self.sp_sigma.setValue(th.forecast_outlier_sigma)
        self.sp_jump = QDoubleSpinBox(); self.sp_jump.setRange(1, 200); self.sp_jump.setDecimals(0)
        self.sp_jump.setValue(th.forecast_jump_pct)
        self.sp_gap = QSpinBox(); self.sp_gap.setRange(1, 10)
        self.sp_gap.setValue(th.forecast_max_gap_years)
        f4.addRow("حداقل R² قابل قبول:", self.sp_r2)
        f4.addRow("آستانه Outlier (برابر انحراف معیار):", self.sp_sigma)
        f4.addRow("جهش سالانه نشانه تغییر ساختاری/مانور (٪):", self.sp_jump)
        f4.addRow("حداکثر فاصله مجاز بین سال‌های داده (سال):", self.sp_gap)
        root.addWidget(grp4)

        # --- ظاهر ---
        grp5 = QGroupBox("ظاهر برنامه")
        f5 = QFormLayout(grp5)
        self.cb_theme = QComboBox()
        from app.ui.theme import THEME_LABELS
        for k, v in THEME_LABELS.items():
            self.cb_theme.addItem(v, k)
        self.cb_theme.setCurrentIndex(max(0, self.cb_theme.findData(settings.theme)))
        f5.addRow("Theme:", self.cb_theme)
        root.addWidget(grp5)

        # --- دکمه‌ها ---
        btns = QHBoxLayout()
        btn_save = QPushButton("ذخیره تنظیمات")
        btn_save.setObjectName("primary")
        btn_defaults = QPushButton("بازگشت به پیش‌فرض‌ها")
        btns.addWidget(btn_save)
        btns.addWidget(btn_defaults)
        btns.addStretch(1)
        root.addLayout(btns)
        root.addStretch(1)

        btn_save.clicked.connect(self.save)
        btn_defaults.clicked.connect(self._reset)
        btn_output.clicked.connect(self._pick_output)
        btn_logo.clicked.connect(self._pick_logo)

    # ------------------------------------------------------------------
    def save(self) -> None:
        s = self.settings
        s.company_name = self.ed_company.text().strip()
        s.unit_name = self.ed_unit.text().strip()
        s.office_name = self.ed_office.text().strip()
        s.report_prefix = self.ed_prefix.text().strip()
        s.output_dir = self.ed_output.text().strip()
        s.company_logo = self.ed_logo.text().strip()
        s.theme = self.cb_theme.currentData() or "light"
        s.fonts.body_font = self.cb_body.currentText()
        s.fonts.body_size = self.sp_body.value()
        s.fonts.heading_font = self.cb_heading.currentText()
        th = s.thresholds
        th.voltage_min_pu = self.sp_vmin.value()
        th.voltage_max_pu = self.sp_vmax.value()
        th.voltage_change_max_pct = self.sp_vchg.value()
        th.loading_light_pct = self.sp_l1.value()
        th.loading_normal_pct = self.sp_l2.value()
        th.loading_semi_pct = self.sp_l3.value()
        th.loading_heavy_pct = self.sp_l4.value()
        th.forecast_years = self.sp_fc_years.value()
        th.forecast_min_history = self.sp_fc_min.value()
        th.growth_low_pct = self.sp_growth_lo.value()
        th.growth_high_pct = self.sp_growth_hi.value()
        th.forecast_r2_min = self.sp_r2.value()
        th.forecast_outlier_sigma = self.sp_sigma.value()
        th.forecast_jump_pct = self.sp_jump.value()
        th.forecast_max_gap_years = self.sp_gap.value()
        s.save()
        self.changed.emit()

    def _reset(self) -> None:
        from app.core.settings import AppSettings
        fresh = AppSettings()
        self.settings.thresholds = fresh.thresholds
        self.settings.fonts = fresh.fonts
        th, f = self.settings.thresholds, self.settings.fonts
        self.sp_vmin.setValue(th.voltage_min_pu)
        self.sp_vmax.setValue(th.voltage_max_pu)
        self.sp_vchg.setValue(th.voltage_change_max_pct)
        self.sp_l1.setValue(th.loading_light_pct)
        self.sp_l2.setValue(th.loading_normal_pct)
        self.sp_l3.setValue(th.loading_semi_pct)
        self.sp_l4.setValue(th.loading_heavy_pct)
        self.sp_fc_years.setValue(th.forecast_years)
        self.sp_fc_min.setValue(th.forecast_min_history)
        self.sp_growth_lo.setValue(th.growth_low_pct)
        self.sp_growth_hi.setValue(th.growth_high_pct)
        self.sp_r2.setValue(th.forecast_r2_min)
        self.sp_sigma.setValue(th.forecast_outlier_sigma)
        self.sp_jump.setValue(th.forecast_jump_pct)
        self.sp_gap.setValue(th.forecast_max_gap_years)
        self.cb_body.setCurrentText(f.body_font)
        self.sp_body.setValue(f.body_size)
        self.cb_heading.setCurrentText(f.heading_font)
        self.changed.emit()

    def _pick_output(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "مسیر خروجی پیش‌فرض")
        if path:
            self.ed_output.setText(path)

    def _pick_logo(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        start = self.ed_logo.text().strip() or str(
            Path(__file__).resolve().parents[2] / "resource")
        path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب لوگوی جلد گزارش", start,
            "تصاویر (*.png *.jpg *.jpeg *.bmp *.ico)")
        if path:
            self.ed_logo.setText(path)
