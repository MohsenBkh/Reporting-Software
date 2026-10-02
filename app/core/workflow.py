# -*- coding: utf-8 -*-
"""Workflow پروژه: New Project → Input → Validation → Analysis → Engineering Review
→ Report Preview → Generate Report. وضعیت هر مرحله برای نوار مراحل و داشبورد (v1.0.3).

منطق UI-مستقل است تا قابل تست باشد.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.findings import Finding, SEV_ERROR, SEV_REVIEW, SEV_WARNING, unresolved
from app.core.models import Project
from app.core.validation import (ERROR, STEP_INPUT, STEP_LOADFLOW, STEP_PROFILE,
                                 STEP_PROJECT, ValidationItem, WARNING, summary_counts)

STEPS = [("project", "پروژه جدید"), ("input", "ورود داده"), ("validation", "اعتبارسنجی"),
         ("analysis", "تحلیل"), ("review", "بازبینی مهندس"), ("preview", "پیش‌نمایش"),
         ("generate", "تولید گزارش")]
STEP_KEYS = [k for k, _ in STEPS]

# state: todo | current | done | warning | error
@dataclass
class StepInfo:
    state: str
    tip: str = ""


def _worst(items: list[ValidationItem], steps: tuple[str, ...]) -> tuple[str, list[ValidationItem]]:
    sel = [i for i in items if i.step in steps and i.status in (ERROR, WARNING)]
    if any(i.status == ERROR for i in sel):
        return "error", sel
    if sel:
        return "warning", sel
    return "done", sel


def compute_steps(project: Project | None, items: list[ValidationItem],
                  findings: list[Finding], report_generated: bool = False) -> dict[str, StepInfo]:
    if project is None:
        return {k: StepInfo("todo") for k in STEP_KEYS}
    errors, warns = summary_counts(items)
    steps: dict[str, StepInfo] = {}

    st, sel = _worst(items, (STEP_PROJECT,))
    steps["project"] = StepInfo(st, "؛ ".join(i.message for i in sel[:3]))
    st, sel = _worst(items, (STEP_INPUT, STEP_LOADFLOW, STEP_PROFILE))
    steps["input"] = StepInfo(st, "؛ ".join(i.message for i in sel[:3]))
    steps["validation"] = StepInfo("error" if errors else ("warning" if warns else "done"),
                                   f"{errors} خطا، {warns} هشدار")
    if errors:
        steps["analysis"] = StepInfo("todo", "ابتدا خطاهای اعتبارسنجی را برطرف کنید.")
        steps["review"] = StepInfo("todo")
        steps["preview"] = StepInfo("todo")
        steps["generate"] = StepInfo("todo")
    else:
        bad = [f for f in findings if f.severity in (SEV_ERROR, SEV_REVIEW)]
        steps["analysis"] = StepInfo("done", f"{len(findings)} Finding"
                                     + (f" — {len(bad)} مورد خطا/نیازمند بررسی" if bad else ""))
        pending = unresolved(findings)
        steps["review"] = StepInfo("warning" if pending else "done",
                                   f"{len(pending)} مورد در انتظار بازبینی" if pending else "همه موارد بازبینی شد")
        steps["preview"] = StepInfo("done" if not pending else "todo")
        steps["generate"] = StepInfo("done" if report_generated else "todo")

    # مرحله جاری: اولین مرحله‌ای که کامل نشده
    for k in STEP_KEYS:
        if steps[k].state in ("todo", "error", "warning"):
            if steps[k].state == "todo":
                steps[k] = StepInfo("current", steps[k].tip)
            break
    return steps


def next_step(steps: dict[str, StepInfo]) -> str:
    for k in STEP_KEYS:
        if steps[k].state in ("current", "error", "warning", "todo"):
            return k
    return "generate"


def overall_status(project: Project | None, items: list[ValidationItem],
                   findings: list[Finding], report_generated: bool) -> tuple[str, str]:
    """(state, متن) برای Badge وضعیت پروژه: normal | warning | error | review | completed."""
    if project is None:
        return "pending", "بدون پروژه"
    errors, warns = summary_counts(items)
    if errors:
        return "error", "Error — داده ناقص/نامعتبر"
    if any(f.needs_attention for f in findings):
        has_review = any(f.severity == SEV_REVIEW or f.stale for f in findings if f.needs_attention)
        return "review", "Requires Review" if has_review else "Warning — نیازمند بازبینی"
    if warns:
        return "warning", "Warning"
    if report_generated:
        return "completed", "Completed"
    return "normal", "Normal — آماده تولید"
