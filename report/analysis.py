# -*- coding: utf-8 -*-
"""سرویس تحلیل با کش — Findings، گزارش ساخته‌شده و اثر انگشت ورودی (v1.0.3).

صفحات «تحلیل مهندسی»، «بازبینی» و «پیش‌نمایش» همگی از یک خروجی مشترک استفاده می‌کنند؛
با تغییر داده‌های پروژه (به‌جز تصمیمات بازبینی که خودشان نتیجه را تغییر می‌دهند)
کش نامعتبر می‌شود.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from app.core.models import Project, to_dict
from app.core.settings import AppSettings
from app.report import pipeline
from app.report.sections import GeneratedReport
from app.report.template_manager import TemplateManager
from app.rules.rule_engine import RuleEngine


def project_fingerprint(project: Project, settings: AppSettings) -> str:
    d = to_dict(project)
    for k in ("updated_at",):
        d.pop(k, None)
    payload = json.dumps([d, to_dict(settings.thresholds), settings.include_appendices],
                         ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


class AnalysisService:
    def __init__(self, manager, settings: AppSettings,
                 texts: Optional[TemplateManager] = None,
                 engine: Optional[RuleEngine] = None) -> None:
        self.manager = manager
        self.settings = settings
        self.texts = texts or TemplateManager.from_settings(settings)
        self.engine = engine or RuleEngine()
        self._report: Optional[GeneratedReport] = None
        self._fp: str = ""

    def invalidate(self) -> None:
        self._report = None
        self._fp = ""

    def get(self, force: bool = False) -> Optional[GeneratedReport]:
        project = self.manager.project
        if project is None:
            return None
        fp = project_fingerprint(project, self.settings)
        if force or self._report is None or fp != self._fp:
            charts = Path(self.manager.charts_dir())
            self._report = pipeline.build_sections(
                project, self.settings, self.texts, self.engine, charts,
                image_resolver=self.manager.image_path,
                profile_loader=self.manager.get_profile)
            self._fp = fp
        return self._report

    def findings(self):
        rep = self.get()
        return rep.findings if rep else []
