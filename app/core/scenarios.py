# -*- coding: utf-8 -*-
"""تولید سناریوهای تأمین برق — «تغییرات آرنا» v1.1.0.

منطق مطابق دفترچه مطالعات مصارف سنگین:

* **Scenario 1** — احداث حداقل یک فیدر جدید (در صورت نیاز و امکان فنی).
* **Scenario 2** — استفاده از فیدر موجود/جایگزین در صورت عدم امکان احداث فیدر جدید.

Rule Engine این سناریوها را *تولید* می‌کند و **هیچ‌سناریویی را انتخاب یا توصیه
نمی‌کند**؛ انتخاب نهایی فقط با مهندس است مگر معیار انتخاب صریحاً در Rule Set تعریف
شده باشد (در نسخه فعلی معیاری تعریف نشده است).

برای هر سناریو ثبت می‌شود:
Technical Basis / Required Network Changes / Candidate Feeder / Estimated Cost /
Required Equipment / Supporting Evidence / Review Status
"""
from __future__ import annotations

from typing import Optional

from app.core.models import Project, SupplyScenario
from app.core.settings import AppSettings
from app.core.study import coincidence_context, scenario_context
from app.rules.rule_engine import RuleEngine


def generate_scenarios(project: Project, settings: AppSettings,
                       engine: RuleEngine) -> list[SupplyScenario]:
    """تولید سناریوها با Ruleهای JSON — خروجی صرفاً «گزینه‌های قابل بررسی» است."""
    ctx = scenario_context(project, settings, [])
    out: list[SupplyScenario] = []
    for spec in engine.generate_scenarios(ctx):
        out.append(SupplyScenario(
            kind=spec.kind,
            rule_id=spec.rule_id,
            title=spec.title,
            technical_basis=spec.technical_basis,
            required_network_changes=spec.required_network_changes,
            candidate_feeder=spec.candidate_feeder,
            required_equipment=list(spec.required_equipment),
            evidence=spec.evidence,
            review_status=spec.review_status,
            source=spec.source,
            source_page=spec.source_page,
        ))
    return out


def ensure_scenarios(project: Project, settings: AppSettings, engine: RuleEngine,
                     regenerate: bool = False) -> list[SupplyScenario]:
    """تضمین وجود سناریوها در پروژه.

    * اگر سناریویی ثبت شده باشد (ورودی کارشناس/ویرایش‌شده)، دست‌نخورده می‌ماند.
    * در غیر این صورت (یا با regenerate=True) سناریوها از Rule Engine تولید و
      در پروژه ذخیره می‌شوند تا در بازبینی/گزارش پایدار بمانند.
    """
    if project.scenarios and not regenerate:
        return project.scenarios
    project.scenarios = generate_scenarios(project, settings, engine)
    return project.scenarios


def scenario_by_key(project: Project, key: str) -> Optional[SupplyScenario]:
    for s in project.scenarios:
        if s.key == key:
            return s
    return None


def total_load_kw(project: Project, settings: AppSettings) -> Optional[float]:
    """مجموع بار اضافه‌شده محدوده (متقاضی + سایر متقاضیان) — فقط با داده موجود."""
    ctx = coincidence_context(project, settings)
    return ctx.get("cd_total_new_load_kw")
