# -*- coding: utf-8 -*-
"""مولد گزارش مطالعه سکشنالایزر (v1.1.0).

ساختار گزارش فعال است و چرخه کامل «پروژه → پیش‌نمایش → تولید Word» را پشتیبانی
می‌کند؛ جزئیات فنی هر بخش متعاقباً توسط کارشناس ارسال و در همین ساختار تکمیل
می‌شود (متن همه بخش‌ها از صفحه «پیش‌نمایش گزارش» قابل ویرایش است).
"""
from __future__ import annotations

from pathlib import Path

from app.core.models import Project
from app.core.settings import AppSettings
from app.report.sections import Paragraph, ReportSection, apply_manual_texts
from app.report.template_manager import TemplateManager

SECTION_INTRO = "intro"
SECTION_SPEC = "secz_spec"
SECTION_LOCATION = "secz_location"
SECTION_PROTECTION = "secz_protection"
SECTION_CONCLUSION = "secz_conclusion"


class SectionalizerTextGenerator:
    """رابط مشترک با TextGenerator: build_all + findings + report_warnings."""

    def __init__(self, project: Project, settings: AppSettings,
                 texts: TemplateManager, engine=None,
                 charts_dir: Path | None = None, image_resolver=None,
                 profile_loader=None) -> None:
        self.project = project
        self.settings = settings
        self.texts = texts
        self.findings: list = []
        self.report_warnings: list[str] = [
            "ساختار گزارش سکشنالایزر مقدماتی است؛ جزئیات فنی بخش‌ها متعاقباً تکمیل می‌شود."]

    # ------------------------------------------------------------------
    def _placeholder(self) -> Paragraph:
        return Paragraph(self.texts.render("T-SECZ-PLACEHOLDER", {}), style="note")

    def build_intro(self) -> ReportSection:
        p = self.project
        secz = p.sectionalizer
        sec = ReportSection(SECTION_INTRO, "مقدمه")
        purpose = (secz.purpose or "").strip()
        if purpose and not purpose.endswith("."):
            purpose += "."
        sec.blocks.append(Paragraph(self.texts.render("T-SECZ-INTRO", {
            "FEEDER": secz.feeder_name or "فیدر مورد نظر",
            "PURPOSE": purpose})))
        location = (secz.location or "").strip()
        if location:
            sec.blocks.append(Paragraph(
                self.texts.render("T-SECZ-LOCATION-PAR", {"LOCATION": location}),
                style="item"))
        notes = (secz.notes or "").strip()
        if notes:
            for part in notes.split("\n\n"):
                if part.strip():
                    sec.blocks.append(Paragraph(part.strip()))
        return sec

    def build_all(self) -> list[ReportSection]:
        sections = [self.build_intro()]
        titles = {
            SECTION_SPEC: self.texts.render("T-SECZ-SPEC-TITLE", {}),
            SECTION_LOCATION: self.texts.render("T-SECZ-LOC-TITLE", {}),
            SECTION_PROTECTION: self.texts.render("T-SECZ-PROT-TITLE", {}),
            SECTION_CONCLUSION: self.texts.render("T-SECZ-CONCL-TITLE", {}),
        }
        for key in (SECTION_SPEC, SECTION_LOCATION, SECTION_PROTECTION, SECTION_CONCLUSION):
            sec = ReportSection(key, titles.get(key) or key)
            sec.blocks.append(self._placeholder())
            sections.append(sec)
        return apply_manual_texts(sections, self.project)
