# -*- coding: utf-8 -*-
"""اسکلت تولید گزارش «مطالعه سکشنالایزر» — نسخه ۱.۳.۰.

این ماژول قابلیت گزارش‌سازی نوع «سکشنالایزر» را فعال می‌کند. ساختار پنج‌بخشی
آماده است و جزئیات تکمیلی (که کارفرما متعاقباً ارسال می‌کند) با افزودن فیلد به
``SectionalizerInfo`` و متن به ``sectionalizer.json`` بدون تغییر ساختار اضافه می‌شود.

رابط این کلاس عمداً با ``TextGenerator`` هم‌شکل است تا ``pipeline`` بتواند هر دو
را به‌صورت یکنواخت فراخوانی کند:

    gen.build_all() -> list[ReportSection]
    gen.findings / gen.report_warnings
"""
from __future__ import annotations

from typing import Optional

from app.core.models import Project
from app.core.settings import AppSettings
from app.report.sections import FigureBlock, Paragraph, ReportSection, TableSpec
from app.report.template_manager import TemplateManager
from app.utils.formatting import fmt

MISSING = "ناموجود"

SECTION_OVERVIEW = "secz_overview"
SECTION_NETWORK = "secz_network"
SECTION_SETTINGS = "secz_settings"
SECTION_COORDINATION = "secz_coordination"
SECTION_CONCLUSION = "secz_conclusion"


class SectionalizerGenerator:
    """سازندهٔ بخش‌های گزارش سکشنالایزر (هم‌شکل با ``TextGenerator``)."""

    def __init__(self, project: Project, settings: AppSettings,
                 texts: TemplateManager, engine=None, charts_dir=None,
                 image_resolver=None, profile_loader=None) -> None:
        self.project = project
        self.settings = settings
        self.texts = texts
        # امضای سازنده با TextGenerator یکسان است؛ آرگومان‌های اضافی برای
        # گزارش سکشنالایزر در حال حاضر استفاده نمی‌شوند.
        self.image_resolver = image_resolver
        self.findings: list = []
        self.report_warnings: list[str] = []
        self._tbl_no = 0
        self._fig_no = 0
        self._used_images: set[str] = set()

    # ------------------------------------------------------------------
    def _t(self, text_id: str, values: Optional[dict] = None,
           default: str = "") -> str:
        """رندر متن از کتابخانه؛ در نبود کلید، پیش‌فرض داخلی جایگزین می‌شود."""
        text = self.texts.render(text_id, values or {})
        if text:
            return text
        try:
            return default.format_map(values or {})
        except (KeyError, IndexError):
            return default

    def _next_tbl(self) -> int:
        self._tbl_no += 1
        return self._tbl_no

    def _figures_for_section(self, section_key: str) -> list[FigureBlock]:
        """شکل‌های فعال منسوب به این بخش (کلید «محل قرارگیری» تصویر).

        مانند ``TextGenerator``: فقط شکل‌هایی که «محل قرارگیری» صریحشان همین
        بخش باشد درج می‌شوند و ترتیب با «اولویت/ترتیب» تعیین می‌گردد.
        """
        images = getattr(self.project, "active_images", self.project.images)
        candidates = []
        for index, img in enumerate(images):
            if img.uid in self._used_images:
                continue
            if (getattr(img, "section_key", "") or "") != section_key:
                continue
            candidates.append((int(getattr(img, "order", 0) or 0), index, img))
        candidates.sort(key=lambda t: (t[0], t[1]))

        out: list[FigureBlock] = []
        for _order, _index, img in candidates:
            if self.image_resolver is not None:
                path = self.image_resolver(img)
                if not path:
                    continue
            else:
                path = img.file_name
            self._used_images.add(img.uid)
            self._fig_no += 1
            caption = ((getattr(img, "caption", "") or "").strip()
                       or img.title or f"شکل {self._fig_no}")
            out.append(FigureBlock(path=str(path), caption=caption))
        return out

    # ------------------------------------------------------------------
    def build_overview(self) -> Optional[ReportSection]:
        p, sz = self.project, self.project.sectionalizer
        sec = ReportSection(SECTION_OVERVIEW, self._t(
            "T-SECZ-OVERVIEW-TITLE", default="کلیات و مقدمه"))
        objective = sz.objective or "افزایش قابلیت اطمینان و ایزوله‌سازی سریع‌تر خطاها"
        sec.blocks.append(Paragraph(self._t("T-SECZ-OVERVIEW-MAIN",
                                            {"OBJECTIVE": objective},
                                            default="این گزارش به بررسی فنی نصب "
                                                    "سکشنالایزر می‌پردازد. هدف از نصب، "
                                                    "{OBJECTIVE} است.")))
        sec.blocks.append(Paragraph(self._t("T-SECZ-OVERVIEW-APPLICANT", {
            "APPLICANT": p.applicant_name or MISSING,
            "REPORT_NO": p.report_number or MISSING,
            "DATE": p.date_jalali or MISSING,
        }, default="الف) درخواست‌دهنده: {APPLICANT}؛ شماره گزارش: {REPORT_NO}؛ "
                   "تاریخ: {DATE}."), style="item"))
        sec.blocks.extend(self._figures_for_section(SECTION_OVERVIEW))
        return sec

    def build_network(self) -> Optional[ReportSection]:
        p, sz = self.project, self.project.sectionalizer
        sec = ReportSection(SECTION_NETWORK, self._t(
            "T-SECZ-NETWORK-TITLE", default="شبکه و محل نصب"))
        feeder = sz.feeder_name or (p.feeders[0].name if p.feeders else MISSING)
        location = sz.installation_location or MISSING
        upstream = sz.upstream_device or MISSING
        sec.blocks.append(Paragraph(self._t("T-SECZ-NETWORK-MAIN", {
            "FEEDER": feeder, "LOCATION": location, "UPSTREAM": upstream,
        }, default="سکشنالایزر مورد مطالعه بر روی {FEEDER} در نقطه {LOCATION} "
                   "نصب می‌گردد. تجهیزات حفاظتی بالادست شامل {UPSTREAM} می‌باشد.")))
        missing = [label for label, value in (
            ("نام فیدر هدف", sz.feeder_name),
            ("محل نصب", sz.installation_location),
            ("تجهیز حفاظتی بالادست", sz.upstream_device)) if not value]
        if missing:
            self.report_warnings.append(
                "داده‌های ناقص بخش شبکه و محل نصب: " + "، ".join(missing))
        sec.blocks.extend(self._figures_for_section(SECTION_NETWORK))
        return sec

    def build_settings(self) -> Optional[ReportSection]:
        sz = self.project.sectionalizer
        sec = ReportSection(SECTION_SETTINGS, self._t(
            "T-SECZ-SETTINGS-TITLE",
            default="سطح اتصال کوتاه و تنظیمات حفاظتی"))
        sec.blocks.append(Paragraph(self._t(
            "T-SECZ-SETTINGS-INTRO", {},
            default="سطح اتصال کوتاه در محل نصب و تنظیمات حفاظتی سکشنالایزر "
                    "به‌شرح جدول زیر است.")))
        rows = [
            ("جریان اتصال کوتاه در محل نصب (kA)", sz.fault_current_ka, 3),
            ("حداقل جریان اتصال کوتاه (kA)", sz.min_fault_current_ka, 3),
            ("جریان تنظیم پیکاپ (A)", sz.pickup_current_a, 1),
            ("تنظیم زمانی (TMS)", sz.tms, 2),
        ]
        body = [[label, fmt(value, digits) if value is not None else MISSING]
                for label, value, digits in rows]
        n = self._next_tbl()
        sec.blocks.append(TableSpec(
            caption=f"جدول {n}: مشخصات و تنظیمات حفاظتی سکشنالایزر",
            header_rows=[["پارامتر", "مقدار"]],
            body_rows=body))
        if not sz.is_complete():
            self.report_warnings.append(
                "تنظیمات حفاظتی سکشنالایزر ناقص است؛ مقادیر ناموجود باید "
                "پیش از بهره‌برداری تکمیل شوند.")
        sec.blocks.extend(self._figures_for_section(SECTION_SETTINGS))
        return sec

    def build_coordination(self) -> Optional[ReportSection]:
        sz = self.project.sectionalizer
        sec = ReportSection(SECTION_COORDINATION, self._t(
            "T-SECZ-COORDINATION-TITLE", default="هماهنگی حفاظت"))
        note = sz.coordination_note or (
            "توضیحات هماهنگی حفاظت متعاقباً بر اساس جزئیات ارسالی تکمیل می‌شود.")
        sec.blocks.append(Paragraph(self._t("T-SECZ-COORDINATION-MAIN",
                                            {"NOTE": note},
                                            default="هماهنگی حفاظت بین سکشنالایزر "
                                                    "و تجهیزات بالادست باید به‌گونه‌ای "
                                                    "باشد که تنها ناحیه معیوب ایزوله "
                                                    "شود. {NOTE}")))
        sec.blocks.extend(self._figures_for_section(SECTION_COORDINATION))
        return sec

    def build_conclusion(self) -> Optional[ReportSection]:
        sec = ReportSection(SECTION_CONCLUSION, self._t(
            "T-SECZ-CONCLUSION-TITLE", default="نتیجه‌گیری و پیشنهادات"))
        sec.blocks.append(Paragraph(self._t(
            "T-SECZ-CONCLUSION-INTRO", {},
            default="بر اساس اطلاعات موجود، ساختار گزارش مطالعه سکشنالایزر تهیه "
                    "شده است؛ نتیجه‌گیری نهایی پس از تکمیل داده‌های ورودی و انجام "
                    "مطالعات تکمیلی صادر می‌شود.")))
        sec.blocks.extend(self._figures_for_section(SECTION_CONCLUSION))
        return sec

    # ------------------------------------------------------------------
    def build_all(self) -> list[ReportSection]:
        """ساخت همهٔ بخش‌های گزارش سکشنالایزر با رعایت کلید On/Off بخش‌ها."""
        out: list[ReportSection] = []
        for builder in (self.build_overview, self.build_network,
                        self.build_settings, self.build_coordination,
                        self.build_conclusion):
            sec = builder()
            if sec is not None and self.settings.section_enabled(sec.key):
                out.append(sec)
        return out
