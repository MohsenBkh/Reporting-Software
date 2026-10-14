# -*- coding: utf-8 -*-
"""مدل Dashboard مهندسی و نمای نتایج Rule — مستقل از Qt."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.core.project_tree import build_dashboard
from app.core.studies import PROTECTION_KINDS, StudyKind
from app.core.workspace import Workspace, resolve_study_inputs
from app.rules.outcome import STATUS_LABELS_FA
from app.ui.shell.design import GLYPH, RESULT_STATE_TO_BADGE, STUDY_STATE_TO_BADGE


@dataclass
class CheckItem:
    label: str
    state: str          # completed | warning | error | review | pending | info
    detail: str = ""

    @property
    def glyph(self) -> str:
        return GLYPH.get(self.state, "○")


def result_view(result: Any) -> tuple[str, str, str]:
    """(state، متن نمایشی، Tooltip) برای یک RuleResult."""
    state = RESULT_STATE_TO_BADGE.get(result.status, "info")
    label = STATUS_LABELS_FA.get(result.status, result.status)
    review = " ◆ نیازمند بازبینی مهندس" if result.engineer_review_required else ""
    text = f"{GLYPH.get(state, '')} {label}: {result.finding or result.rule_name}{review}"
    tip = "\n".join(p for p in (
        f"قاعده: {result.rule_key}", f"منبع: {result.source} — {result.source_page}"
        if result.source else "", f"شاهد: {result.evidence}" if result.evidence else "") if p)
    return state, text, tip


def validation_checklist(project: Any, workspace: Workspace, *, input_errors: int,
                         input_warnings: int, results_by_kind: Optional[dict],
                         report_generated: bool) -> list[CheckItem]:
    """چک‌لیست وضعیت اعتبارسنجی (✓ / ⚠ / ○) برای Dashboard."""
    items = [CheckItem(
        "اعتبارسنجی ورودی‌ها",
        "error" if input_errors else ("warning" if input_warnings else "completed"),
        f"{input_errors} خطا · {input_warnings} هشدار")]
    # داده‌های شبکه برای مطالعات حفاظتی انتخاب‌شده
    sel = [k for k in workspace.selection.kinds() if k in PROTECTION_KINDS]
    if sel:
        missing = []
        for k in sel:
            inp = resolve_study_inputs(project, workspace, k)
            for key, label in (("fault_current_ka", "Isc"), ("load_current_a", "جریان بار")):
                if not inp[key].present:
                    missing.append(f"{label} ({k.value})")
        items.append(CheckItem("اعتبارسنجی شبکه", "warning" if missing else "completed",
                               "، ".join(missing) or "داده‌های مشترک شبکه کامل است"))
    else:
        items.append(CheckItem("اعتبارسنجی شبکه", "pending", "مطالعه حفاظتی انتخاب نشده"))
    # بازبینی مهندس
    if results_by_kind:
        pending = sum(1 for rows in results_by_kind.values() for r in rows
                      if r.engineer_review_required)
        items.append(CheckItem("بازبینی مهندس", "review" if pending else "completed",
                               f"{pending} مورد نیازمند بازبینی"))
    else:
        items.append(CheckItem("بازبینی مهندس", "pending", "ارزیابی نشده"))
    items.append(CheckItem("تولید گزارش", "completed" if report_generated else "pending",
                           "تولید شده" if report_generated else "هنوز تولید نشده"))
    return items


def dashboard_cards(project: Any, workspace: Workspace,
                    results_by_kind: Optional[dict] = None) -> list[dict]:
    out = []
    for key, info in build_dashboard(project, workspace, results_by_kind).items():
        out.append({"key": key, "title": info["label"], "status": info["status"],
                    "status_label": info["status_label"],
                    "badge": STUDY_STATE_TO_BADGE.get(info["status"], "info")})
    return out
