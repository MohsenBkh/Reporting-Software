# -*- coding: utf-8 -*-
"""Guided Flow — فرایند گام‌به‌گام بر اساس نوع مطالعات (v2.0.0).

نرم‌افزار گام‌های بعدی را بر اساس مطالعات انتخاب‌شده نمایش می‌دهد و باز شدن گام بعد
منوط به تکمیل «الزامات» گام جاری است. هر الزام به صفحه و فیلد دقیق ارجاع دارد
(``target`` + ``field``) تا کاربر بداند کجا را کامل کند.

گام‌ها: ۱ اطلاعات پروژه ← ۲ ورود داده ← ۳ اعتبارسنجی ← ۴ تحلیل ← ۵ بازبینی مهندس ←
۶ پیش‌نمایش ← ۷ تولید گزارش.

* قفل‌بودن گام «راهنمایی» است، نه ممنوعیت: کاربر می‌تواند با «ادامه با وجود نقص» گام را
  رد کند (``Workspace.flow_overrides``)؛ تولید گزارش هم همیشه ممکن است.
* منطق این ماژول مستقل از UI است (قابل تست).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.studies import PROTECTION_KINDS, STUDY_LABELS_FA, StudyKind
from app.core.validation import ERROR, ValidationItem, validate_heavy
from app.core.workspace import Workspace, resolve_study_inputs

STEP_KEYS = ("project", "input", "validation", "analysis", "review", "preview", "generate")
STEP_TITLES = {"project": "اطلاعات پروژه", "input": "ورود داده", "validation": "اعتبارسنجی",
               "analysis": "تحلیل مهندسی", "review": "بازبینی مهندس", "preview": "پیش‌نمایش گزارش",
               "generate": "تولید گزارش"}
# گام ← صفحهٔ شروع (کلید ناوبری)
STEP_ROUTE_DEFAULT = {"project": "project", "input": "applicant", "validation": "validation",
                      "analysis": "analysis", "review": "review", "preview": "preview",
                      "generate": "generate"}


@dataclass
class Requirement:
    label: str
    done: bool
    target: str = ""          # کلید ناوبری صفحه
    field: str = ""           # فیلد دقیق (برای Focus)
    study: str = ""           # مطالعهٔ مربوط (heavy | recloser | sectionalizer)


@dataclass
class FlowStep:
    key: str
    number: int
    title: str
    requirements: list[Requirement] = field(default_factory=list)
    complete: bool = False       # الزامات کامل است
    overridden: bool = False     # کاربر با نقص رد کرده است
    unlocked: bool = True        # گام قبل کامل (یا ردشده) است
    manual: bool = False         # تکمیل با تأیید کاربر (تحلیل/بازبینی/پیش‌نمایش)

    @property
    def passed(self) -> bool:
        """آیا برای باز شدن گام بعد کافی است؟"""
        return self.complete or self.overridden

    @property
    def missing(self) -> list[Requirement]:
        return [r for r in self.requirements if not r.done]

    @property
    def state(self) -> str:
        if not self.unlocked:
            return "locked"
        if self.complete:
            return "done"
        if self.overridden:
            return "warning"
        return "current"

    def reason_locked(self) -> str:
        return f"ابتدا گام «{STEP_TITLES.get(self.key, self.key)}» را کامل کنید."


# ---------------------------------------------------------------------------
# الزامات هر گام
# ---------------------------------------------------------------------------
def _project_requirements(project: Any) -> list[Requirement]:
    return [Requirement("شماره گزارش", bool(project.report_number), "project", "ed_number"),
            Requirement("تاریخ گزارش", bool(project.date_jalali), "project", "ed_date")]


def _heavy_requirements(project: Any, settings: Any) -> list[Requirement]:
    """الزامات متقاضی سنگین: اطلاعات متقاضی/توان (صفحهٔ «اطلاعات متقاضی») + خطاهای (ERROR)
    اعتبارسنجی همان مطالعه برای فیدرها و پخش بار (بدون تکرار قواعد)."""
    from app.core.models import REQUEST_INCREASE
    out = [Requirement("متقاضی سنگین: نام متقاضی", bool(project.applicant_name), "applicant",
                       "ed_applicant", "heavy"),
           Requirement("متقاضی سنگین: توان درخواستی/جدید (kW)", project.requested_power_kw is not None,
                       "applicant", "sp_requested", "heavy")]
    if project.request_type == REQUEST_INCREASE:
        out.append(Requirement("متقاضی سنگین: توان فعلی (kW)", project.existing_power_kw is not None,
                               "applicant", "sp_existing", "heavy"))
    for it in validate_heavy(project, settings):
        if it.status == ERROR and it.step != "project":      # اطلاعات عمومی در گام ۱ است
            out.append(Requirement(it.message, False, it.target or "input", it.field, "heavy"))
    return out


def _protection_requirements(project: Any, workspace: Workspace, kind: StudyKind) -> list[Requirement]:
    label = STUDY_LABELS_FA[kind]
    info = getattr(project, kind.value)
    inputs = resolve_study_inputs(project, workspace, kind)
    settings = getattr(info, "settings", None)
    f51 = getattr(getattr(settings, "f51", None), "pickup_a", None)
    return [
        Requirement(f"{label}: حداقل یک فیدر در محدودهٔ مطالعه", bool(workspace.scope(kind)),
                    f"{kind.value}.network", "feeders", kind.value),
        Requirement(f"{label}: جریان اتصال کوتاه (سه‌فاز پست یا محل نصب)",
                    inputs["fault_current_ka"].present, f"{kind.value}.network", "sc3", kind.value),
        Requirement(f"{label}: محل نصب تجهیز",
                    bool(getattr(info, "installation_location", "")),
                    f"{kind.value}.device", "installation_location", kind.value),
        Requirement(f"{label}: تنظیم Pickup تابع ۵۱", f51 is not None,
                    f"{kind.value}.settings", "f51.pickup_a", kind.value),
    ]


def input_requirements(project: Any, workspace: Workspace, settings: Any) -> list[Requirement]:
    reqs: list[Requirement] = []
    if workspace.selection.heavy:
        reqs += _heavy_requirements(project, settings)
    for kind in PROTECTION_KINDS:
        if workspace.selection.is_selected(kind):
            reqs += _protection_requirements(project, workspace, kind)
    return reqs


# ---------------------------------------------------------------------------
def compute_flow(project: Any, workspace: Workspace, settings: Any, *,
                 validation_errors: Optional[int] = None,
                 heavy_unresolved: Optional[int] = None,
                 report_generated: bool = False) -> list[FlowStep]:
    """وضعیت ۷ گام؛ گام بعد فقط وقتی باز می‌شود که گام قبل کامل یا «ردشده» باشد."""
    done, over = set(workspace.flow_done), set(workspace.flow_overrides)
    steps: list[FlowStep] = []

    def add(key: str, reqs: list[Requirement], complete: Optional[bool] = None,
            manual: bool = False) -> None:
        s = FlowStep(key, len(steps) + 1, STEP_TITLES[key], reqs,
                     complete if complete is not None else all(r.done for r in reqs),
                     key in over, manual=manual)
        s.unlocked = all(p.passed for p in steps)
        steps.append(s)

    add("project", _project_requirements(project))
    add("input", input_requirements(project, workspace, settings))
    errors = validation_errors if validation_errors is not None else sum(
        1 for r in steps[1].requirements if not r.done)
    add("validation", [Requirement(f"رفع خطاهای اعتبارسنجی ({errors} خطا)", errors == 0,
                                   "validation")])
    add("analysis", [Requirement("اجرای تحلیل و قواعد مهندسی", "analysis" in done, "analysis")],
        manual=True)
    review_reqs = []
    if workspace.selection.heavy:
        n = heavy_unresolved if heavy_unresolved is not None else 0
        review_reqs.append(Requirement(f"بازبینی نتایج متقاضی سنگین ({n} مورد باز)", n == 0,
                                       "review", "", "heavy"))
    if workspace.selection.protection_kinds():
        review_reqs.append(Requirement("تأیید بازبینی یافته‌های حفاظتی", "review" in done,
                                       "recloser.settings" if workspace.selection.recloser
                                       else "sectionalizer.settings", "", "protection"))
    add("review", review_reqs or [Requirement("بازبینی", True, "review")], manual=True)
    add("preview", [Requirement("مشاهدهٔ پیش‌نمایش گزارش", "preview" in done, "preview")],
        manual=True)
    add("generate", [Requirement("تولید گزارش", report_generated, "generate")])
    return steps


def next_step(steps: list[FlowStep]) -> Optional[FlowStep]:
    """نخستین گامی که هنوز کامل/ردشده نیست."""
    return next((s for s in steps if not s.passed), None)


def is_route_allowed(steps: list[FlowStep], step_key: str) -> bool:
    s = next((x for x in steps if x.key == step_key), None)
    return True if s is None else s.unlocked


# ---------------------------------------------------------------------------
# مدل نوار راهنما (GuideBar) — مستقل از Qt
# ---------------------------------------------------------------------------
@dataclass
class GuideModel:
    step: Optional[FlowStep] = None
    title: str = ""
    message: str = ""
    links: list[Requirement] = field(default_factory=list)   # الزامات ناتمام (قابل کلیک)
    more: int = 0                                             # تعداد الزامات نمایش‌داده‌نشده
    goto: str = ""                                            # مقصد دکمهٔ «ادامه»
    goto_field: str = ""
    can_override: bool = False
    needs_protection_ack: bool = False
    finished: bool = False


def guide_model(steps: list[FlowStep], selection: Any, max_links: int = 4) -> GuideModel:
    if not steps:
        return GuideModel()                       # بدون پروژه: نوار نمایش داده نمی‌شود
    cur = next_step(steps)
    if cur is None:
        return GuideModel(title="همهٔ گام‌ها کامل است", message="گزارش آماده تولید/ویرایش نهایی است.",
                          finished=True)
    missing = cur.missing
    first = missing[0] if missing else None
    msg = (f"{len(missing)} مورد باید تکمیل شود تا گام بعد باز شود." if missing
           else "این گام آماده است؛ برای ثبت آن صفحهٔ گام را باز کنید.")
    return GuideModel(
        step=cur, title=f"گام {cur.number} از {len(steps)} — {cur.title}", message=msg,
        links=missing[:max_links], more=max(0, len(missing) - max_links),
        goto=(first.target if first else STEP_ROUTE_DEFAULT.get(cur.key, "")),
        goto_field=(first.field if first else ""),
        can_override=bool(missing) and cur.key != "generate",
        needs_protection_ack=(cur.key == "review" and bool(selection.protection_kinds())
                              and any(r.study == "protection" for r in missing)))
