# -*- coding: utf-8 -*-
"""Report Composer — مولد بخش‌های گزارش مبتنی بر Component.

این ماژول مسئول تولید بخش‌های گزارش بر اساس مطالعات انتخاب‌شده است:
- برای هر مطالعه، مولد اختصاصی مورد استفاده قرار می‌گیرد
- برای Protection Studies (ریکلوزر + سکشنالایزر)، گزارش ترکیبی تولید می‌شود
- ترتیب بخش‌ها بر اساس ReportCenter قابل تنظیم است
"""
from __future__ import annotations

from typing import Optional

from app.core.models import Project, ReportCenter, STUDY_HEAVY, STUDY_RECLOSER, STUDY_SECTIONALIZER
from app.core.report_center import ProtectionReportConfig
from app.report.sections import GeneratedReport, ReportSection
from app.report.study_sections import StudySections
from app.report.sectionalizer import SectionalizerGenerator


# کلید بخش‌های گزارش ترکیبی
SEC_NETWORK_INFO = "network_info"
SEC_EXISTING_PROTECTION = "existing_protection"
SEC_RECLOSER_STUDY = "recloser_study"
SEC_SECTIONALIZER_STUDY = "sectionalizer_study"
SEC_COORDINATION = "coordination"
SEC_EQUIPMENT_INVENTORY = "equipment_inventory"
SEC_PERFORMANCE_SCENARIO = "performance_scenario"
SEC_CONCLUSION = "conclusion"
SEC_FINAL_RECOMMENDATION = "final_recommendation"

# پیش‌فرض ترتیب بخش‌های گزارش ترکیبی
DEFAULT_COMBINED_SECTION_ORDER = [
    SEC_NETWORK_INFO,           # ۱. مشخصات شبکه
    SEC_EXISTING_PROTECTION,    # ۲. وضعیت حفاظتی موجود
    SEC_RECLOSER_STUDY,         # ۳. مطالعه ریکلوزر
    SEC_SECTIONALIZER_STUDY,    # ۴. مطالعه سکشنالایزر
    SEC_COORDINATION,           # ۵. هماهنگی حفاظتی
    SEC_EQUIPMENT_INVENTORY,    # ۶. جانمایی تجهیزات
    SEC_PERFORMANCE_SCENARIO,   # ۷. سناریوی عملکرد
    SEC_CONCLUSION,             # ۸. جمع‌بندی
    SEC_FINAL_RECOMMENDATION,   # ۹. پیشنهاد نهایی
]


class ReportComposer:
    """سازندهٔ گزارش بر اساس مطالعات انتخاب‌شده.

    این کلاس:
    - مطالعات انتخاب‌شده را دریافت می‌کند
    - برای هر مطالعه مولد مناسب را انتخاب می‌کند
    - بخش‌های گزارش را تولید می‌کند
    - برای Protection Studies گزارش ترکیبی تولید می‌کند
    """

    def __init__(self, project: Project, settings, texts, engine, charts_dir,
                 image_resolver=None, profile_loader=None):
        self.project = project
        self.settings = settings
        self.texts = texts
        self.engine = engine
        self.charts_dir = charts_dir
        self.image_resolver = image_resolver
        self.profile_loader = profile_loader
        # ذخیره هشدارها از Generators
        self.report_warnings: list[str] = []

    def compose_report(self) -> GeneratedReport:
        """تولید گزارش کامل بر اساس مطالعات انتخاب‌شده."""
        report = GeneratedReport(sections=[])

        # تعیین مطالعات انتخاب‌شده
        report_center = self.project.report_center
        selected_studies = report_center.report_studies()

        # تولید بخش‌های هر مطالعه
        sections = []

        # 1. Heavy Applicant Study
        if STUDY_HEAVY in selected_studies:
            sections.extend(self._compose_heavy_applicant())

        # 2. Protection Studies
        has_recloser = STUDY_RECLOSER in selected_studies
        has_sectionalizer = STUDY_SECTIONALIZER in selected_studies

        if has_recloser or has_sectionalizer:
            if report_center.protection_report.combined and has_recloser and has_sectionalizer:
                # گزارش ترکیبی
                sections.extend(self._compose_combined_protection())
            else:
                # گزارش‌های جداگانه
                if has_recloser:
                    sections.extend(self._compose_recloser())
                if has_sectionalizer:
                    sections.extend(self._compose_sectionalizer())

        report.sections = sections
        report.warnings = self.report_warnings
        return report

    def _compose_heavy_applicant(self) -> list[ReportSection]:
        """تولید بخش‌های گزارش مطالعه متقاضیان سنگین."""
        # استفاده از TextGenerator برای مطالعه متقاضیان سنگین
        from app.report.text_generator import TextGenerator

        gen = TextGenerator(
            self.project, self.settings, self.texts,
            self.engine, self.charts_dir,
            self.image_resolver, self.profile_loader
        )
        return gen.build_all()

    def _compose_recloser(self) -> list[ReportSection]:
        """تولید بخش‌های گزارش مطالعه ریکلوزر."""
        # ریکلوزر هنوز پیاده‌سازی نشده
        # اما برای سازگاری، چارچوب ایجاد می‌شود
        self.report_warnings.append(
            "قالب گزارش ریکلوزر در برنامه است و در نسخه‌های بعدی فعال می‌شود."
        )
        return []

    def _compose_sectionalizer(self) -> list[ReportSection]:
        """تولید بخش‌های گزارش مطالعه سکشنالایزر."""
        # استفاده از SectionalizerGenerator موجود
        gen = SectionalizerGenerator(
            self.project, self.settings, self.texts,
            self.engine, self.charts_dir,
            self.image_resolver, self.profile_loader
        )
        sections = gen.build_all()
        # ذخیره warnings از generator
        self.report_warnings = list(gen.report_warnings)
        return sections

    def _compose_combined_protection(self) -> list[ReportSection]:
        """تولید بخش‌های گزارش ترکیبی ریکلوزر + سکشنالایزر."""
        sections = []

        # ترتیب بخش‌ها بر اساس ReportCenter
        section_order = self.project.report_center.protection_report.section_order

        for section_key in section_order:
            if section_key == SEC_NETWORK_INFO:
                sections.append(self._build_network_info_section())
            elif section_key == SEC_EXISTING_PROTECTION:
                sections.append(self._build_existing_protection_section())
            elif section_key == SEC_RECLOSER_STUDY:
                sections.append(self._build_recloser_study_section())
            elif section_key == SEC_SECTIONALIZER_STUDY:
                sections.append(self._build_sectionalizer_study_section())
            elif section_key == SEC_COORDINATION:
                sections.append(self._build_coordination_section())
            elif section_key == SEC_EQUIPMENT_INVENTORY:
                sections.append(self._build_equipment_inventory_section())
            elif section_key == SEC_PERFORMANCE_SCENARIO:
                sections.append(self._build_performance_scenario_section())
            elif section_key == SEC_CONCLUSION:
                sections.append(self._build_conclusion_section())
            elif section_key == SEC_FINAL_RECOMMENDATION:
                sections.append(self._build_final_recommendation_section())

        return sections

    def _build_network_info_section(self) -> ReportSection:
        """بخش ۱: مشخصات شبکه."""
        sec = ReportSection(SEC_NETWORK_INFO, "مشخصات شبکه")
        # TODO: پر کردن با اطلاعات شبکه
        return sec

    def _build_existing_protection_section(self) -> ReportSection:
        """بخش ۲: وضعیت حفاظتی موجود."""
        sec = ReportSection(SEC_EXISTING_PROTECTION, "وضعیت حفاظتی موجود")
        # TODO: پر کردن با اطلاعات حفاظتی موجود
        return sec

    def _build_recloser_study_section(self) -> ReportSection:
        """بخش ۳: مطالعه ریکلوزر."""
        sec = ReportSection(SEC_RECLOSER_STUDY, "مطالعه ریکلوزر")
        # TODO: پر کردن با نتایج مطالعه ریکلوزر
        return sec

    def _build_sectionalizer_study_section(self) -> ReportSection:
        """بخش ۴: مطالعه سکشنالایزر."""
        sec = ReportSection(SEC_SECTIONALIZER_STUDY, "مطالعه سکشنالایزر")
        # TODO: پر کردن با نتایج مطالعه سکشنالایزر
        return sec

    def _build_coordination_section(self) -> ReportSection:
        """بخش ۵: هماهنگی حفاظتی."""
        sec = ReportSection(SEC_COORDINATION, "هماهنگی حفاظت")
        # TODO: پر کردن با تحلیل هماهنگی
        return sec

    def _build_equipment_inventory_section(self) -> ReportSection:
        """بخش ۶: جانمایی تجهیزات."""
        sec = ReportSection(SEC_EQUIPMENT_INVENTORY, "جانمایی تجهیزات")
        # TODO: پر کردن با roseList تجهیزات
        return sec

    def _build_performance_scenario_section(self) -> ReportSection:
        """بخش ۷: سناریوی عملکرد."""
        sec = ReportSection(SEC_PERFORMANCE_SCENARIO, "سناریوی عملکرد")
        # TODO: پر کردن با سناریوی عملکرد
        return sec

    def _build_conclusion_section(self) -> ReportSection:
        """بخش ۸: جمع‌بندی."""
        sec = ReportSection(SEC_CONCLUSION, "جمع‌بندی")
        # TODO: پر کردن با جمع‌بندی
        return sec

    def _build_final_recommendation_section(self) -> ReportSection:
        """بخش ۹: پیشنهاد نهایی."""
        sec = ReportSection(SEC_FINAL_RECOMMENDATION, "پیشنهاد نهایی")
        # TODO: پر کردن با پیشنهاد نهایی
        return sec
