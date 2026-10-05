# -*- coding: utf-8 -*-
"""صفحه تنظیمات — شرکت، فونت، Thresholdهای Rule Engine (بخش ۳۰ سند)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFontComboBox,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea,
                               QSpinBox, QVBoxLayout, QWidget)

from app.ui.widgets import OptionalSpin


def make_spin_opt(value, minimum: float, maximum: float, decimals: int, suffix: str = ""):
    """ورودی عددی الزامی با مقدار پیش‌فرض (برای دامنه شمول مصرف سنگین)."""
    from app.ui.widgets import make_spin
    w = make_spin(minimum, maximum, decimals,
                  float(value) if value is not None else minimum)
    w.setSuffix(suffix)
    return w


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

        # ------------------------------------------------------------------
        # «تغییرات آرنا» — آستانه‌های مطالعه مصارف سنگین (بخش study)
        # ------------------------------------------------------------------
        study = settings.study
        grp4 = QGroupBox("حدآستانه‌های مطالعه مصارف سنگین (TAV111-10/00)")
        f4 = QFormLayout(grp4)
        self.sp_heavy = make_spin_opt(study.heavy_consumer_min_kw, 0, 1e7, 0, " kW")
        self.opt_ss_tol = OptionalSpin(study.substation_loading_tolerance_pct, 0, 100, 2, " ٪")
        self.opt_line_tol = OptionalSpin(study.line_current_tolerance_pct, 0, 100, 2, " ٪")
        self.opt_ss_warn = OptionalSpin(study.study_substation_loading_warn_pct, 0, 200, 2, " ٪")
        self.opt_sc_limit = OptionalSpin(study.study_sc_limit_ka, 0, 200, 3, " kA")
        self.opt_sum_tol = OptionalSpin(study.load_sum_tolerance_kw, 0, 1e6, 1, " kW")
        # v1.2.0 — آستانه‌های بارگذاری کل فیدر (سیاست بهره‌برداری/دستور کارفرما)
        self.opt_ld_crit = OptionalSpin(study.feeder_loading_critical_mw, 0, 100, 2, " MW")
        self.opt_ld_sev = OptionalSpin(study.feeder_loading_severe_mw, 0, 100, 2, " MW")
        f4.addRow("دامنه شمول مصرف سنگین (مگاوات و بالاتر):", self.sp_heavy)
        f4.addRow("تلورانس کنترل بارگیری ایستگاه:", self.opt_ss_tol)
        f4.addRow("تلورانس کنترل سازگاری جریان خط:", self.opt_line_tol)
        f4.addRow("حد هشدار بارگیری ترانس ایستگاه نزدیک:", self.opt_ss_warn)
        f4.addRow("حد مجاز جریان اتصال کوتاه تجهیزات:", self.opt_sc_limit)
        f4.addRow("تلورانس کنترل مجموع بار متقاضیان:", self.opt_sum_tol)
        f4.addRow("آستانهٔ بارگذاری بحرانی فیدر (پیک فیدر + بار جدید):", self.opt_ld_crit)
        f4.addRow("آستانهٔ بارگذاری شدیداً بحرانی فیدر:", self.opt_ld_sev)
        note_ld = QLabel(
            "این دو آستانه از «سیاست بهره‌برداری / دستور کارفرما» می‌آیند (پیش‌فرض ۷ و ۸ مگاوات) "
            "و در سند TAV111-10/00 عددی برای آن‌ها ارائه نشده است. اگر خالی شوند، Ruleهای "
            "بارگذاری با وضعیت MISSING_RULE ثبت می‌شوند و هیچ داوری‌ای انجام نمی‌شود.")
        note_ld.setObjectName("Muted")
        note_ld.setWordWrap(True)
        f4.addRow("", note_ld)
        note4 = QLabel("هر موردی که «تعریف‌شده» نباشد، Rule وابسته به آن با وضعیت "
                       "MISSING_RULE ثبت می‌شود و هیچ مقدار پیش‌فرضی فرض نمی‌گردد.")
        note4.setObjectName("Muted")
        note4.setWordWrap(True)
        f4.addRow("", note4)
        root.addWidget(grp4)

        # ------------------------------------------------------------------
        # پارامترهای هزینه بررسی اقتصادی (بخش costs)
        # ------------------------------------------------------------------
        costs = settings.costs
        grp5 = QGroupBox("پارامترهای هزینه بررسی اقتصادی (میلیون تومان)")
        f5 = QFormLayout(grp5)
        self.opt_cost_oh = OptionalSpin(costs.overhead_per_km_million, 0, 1e6, 1, " /km")
        self.opt_cost_ug = OptionalSpin(costs.underground_per_km_million, 0, 1e6, 1, " /km")
        self.opt_cost_ground = OptionalSpin(costs.ground_substation_million, 0, 1e8, 1, " M")
        self.opt_cost_switch = OptionalSpin(costs.switchgear_million, 0, 1e8, 1, " M")
        self.opt_cost_prot = OptionalSpin(costs.protection_million, 0, 1e8, 1, " M")
        self.opt_cost_other = OptionalSpin(costs.other_equipment_million, 0, 1e8, 1, " M")
        f5.addRow("احداث شبکه هوایی (هر کیلومتر):", self.opt_cost_oh)
        f5.addRow("احداث شبکه زمینی (هر کیلومتر):", self.opt_cost_ug)
        f5.addRow("احداث پست زمینی:", self.opt_cost_ground)
        f5.addRow("تجهیزات کلیدزنی:", self.opt_cost_switch)
        f5.addRow("تجهیزات حفاظتی:", self.opt_cost_prot)
        f5.addRow("سایر تجهیزات کلیدی:", self.opt_cost_other)
        note5 = QLabel("در نبود این پارامترها، برآورد هزینه ساخته نمی‌شود و وضعیت "
                       "MISSING_DATA ثبت می‌گردد (هیچ عددی هارد‌کد نشده است).")
        note5.setObjectName("Muted")
        note5.setWordWrap(True)
        f5.addRow("", note5)
        root.addWidget(grp5)

        # ------------------------------------------------------------------
        # v1.2.0 — بخش‌های گزارش (On/Off)
        # ------------------------------------------------------------------
        from app.core.report_sections import REPORT_SECTIONS
        grp6 = QGroupBox("بخش‌های گزارش — کدام بخش‌ها در گزارش بیایند؟ (On/Off)")
        g6 = QGridLayout(grp6)
        self.chk_sections: dict[str, QCheckBox] = {}
        for i, (key, label) in enumerate(REPORT_SECTIONS):
            chk = QCheckBox(label)
            chk.setChecked(settings.section_enabled(key))
            self.chk_sections[key] = chk
            g6.addWidget(chk, i // 2, i % 2)
        note6 = QLabel("بخش خاموش، در گزارش و در پیوست ردیابی نمی‌آید؛ داده‌های آن حذف "
                       "نمی‌شود و با روشن‌کردن دوباره بازمی‌گردد. (On/Off تک‌تک ردیف‌های "
                       "ورودی در جدول‌های همان صفحه قابل تنظیم است.)")
        note6.setObjectName("Muted")
        note6.setWordWrap(True)
        g6.addWidget(note6, (len(REPORT_SECTIONS) + 1) // 2, 0, 1, 2)
        root.addWidget(grp6)


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
        # --- مطالعه مصارف سنگین («تغییرات آرنا») ---
        st = s.study
        st.heavy_consumer_min_kw = self.sp_heavy.value()
        st.substation_loading_tolerance_pct = self.opt_ss_tol.value()
        st.line_current_tolerance_pct = self.opt_line_tol.value()
        st.study_substation_loading_warn_pct = self.opt_ss_warn.value()
        st.study_sc_limit_ka = self.opt_sc_limit.value()
        st.load_sum_tolerance_kw = self.opt_sum_tol.value()
        st.feeder_loading_critical_mw = self.opt_ld_crit.value()
        st.feeder_loading_severe_mw = self.opt_ld_sev.value()
        c = s.costs
        c.overhead_per_km_million = self.opt_cost_oh.value()
        c.underground_per_km_million = self.opt_cost_ug.value()
        c.ground_substation_million = self.opt_cost_ground.value()
        c.switchgear_million = self.opt_cost_switch.value()
        c.protection_million = self.opt_cost_prot.value()
        c.other_equipment_million = self.opt_cost_other.value()
        for key, chk in getattr(self, "chk_sections", {}).items():
            setattr(s.report_sections, key, chk.isChecked())
        s.save()
        self.changed.emit()

    def _reset(self) -> None:
        from app.core.settings import AppSettings
        fresh = AppSettings()
        self.settings.thresholds = fresh.thresholds
        self.settings.fonts = fresh.fonts
        self.settings.study = fresh.study
        self.settings.costs = fresh.costs
        self.settings.report_sections = fresh.report_sections
        for key, chk in getattr(self, "chk_sections", {}).items():
            chk.setChecked(True)
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
        st2, c2 = self.settings.study, self.settings.costs
        self.sp_heavy.setValue(st2.heavy_consumer_min_kw or 0.0)
        self.opt_ss_tol.setValue(st2.substation_loading_tolerance_pct)
        self.opt_line_tol.setValue(st2.line_current_tolerance_pct)
        self.opt_ss_warn.setValue(st2.study_substation_loading_warn_pct)
        self.opt_sc_limit.setValue(st2.study_sc_limit_ka)
        self.opt_sum_tol.setValue(st2.load_sum_tolerance_kw)
        self.opt_cost_oh.setValue(c2.overhead_per_km_million)
        self.opt_cost_ug.setValue(c2.underground_per_km_million)
        self.opt_cost_ground.setValue(c2.ground_substation_million)
        self.opt_cost_switch.setValue(c2.switchgear_million)
        self.opt_cost_prot.setValue(c2.protection_million)
        self.opt_cost_other.setValue(c2.other_equipment_million)
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
