# -*- coding: utf-8 -*-
"""مدل نمایشی (View-Model) مستقل از Qt برای Project Explorer و Dashboard.

UI فقط این ساختارها را رندر می‌کند؛ هیچ منطق مهندسی در لایهٔ UI قرار نمی‌گیرد.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.studies import STUDY_LABELS_FA, StudyKind, has_study_data
from app.core.workspace import Workspace

ST_NOT_SELECTED = "not_selected"
ST_EMPTY = "empty"
ST_INCOMPLETE = "incomplete"
ST_REVIEW = "review_required"
ST_COMPLETE = "complete"
ST_UNEVALUATED = "not_evaluated"

STATUS_LABELS_FA = {
    ST_NOT_SELECTED: "انتخاب نشده", ST_EMPTY: "بدون داده", ST_INCOMPLETE: "ناقص",
    ST_REVIEW: "نیازمند بازبینی", ST_COMPLETE: "کامل", ST_UNEVALUATED: "ارزیابی نشده",
}


@dataclass
class TreeNode:
    key: str
    label: str
    node_type: str                       # root | group | study | device | feeder | report
    children: list["TreeNode"] = field(default_factory=list)
    step: str = ""                       # گام Guided Flow که این گره به آن تعلق دارد
    locked: bool = False                 # گام هنوز باز نشده (غیرفعال)
    tooltip: str = ""

    def find(self, key: str) -> Optional["TreeNode"]:
        if self.key == key:
            return self
        for c in self.children:
            hit = c.find(key)
            if hit:
                return hit
        return None

    def keys(self) -> list[str]:
        return [self.key] + [k for c in self.children for k in c.keys()]


STEP_GLYPH = {"done": "✓ ", "error": "✕ ", "warning": "! ", "current": "● ", "todo": "", "locked": "🔒 "}


def _apply_locks(node: TreeNode, step: str, reasons: dict[str, str]) -> None:
    node.step = step
    if step in reasons:
        node.locked, node.tooltip = True, reasons[step]
    for c in node.children:
        _apply_locks(c, step, reasons)


NODE_STEP = {"step.project": "project", "step.input": "input", "images": "input",
             "step.validation": "validation", "step.analysis": "analysis", "step.review": "review",
             "step.preview": "preview", "step.generate": "generate"}


def build_project_tree(project: Any, workspace: Workspace,
                       step_states: Optional[dict[str, str]] = None,
                       locked_steps: Optional[dict[str, str]] = None) -> TreeNode:
    """درخت Project Explorer: مراحل ۱ تا ۷ + مطالعات انتخاب‌شده + تصاویر + تنظیمات.

    ``step_states``: وضعیت هر مرحلهٔ Workflow (done | error | warning | current | todo) که
    به‌صورت نشان کنار عنوان می‌آید؛ نوار مراحل قدیمی حذف و جایش همین درخت است.
    """
    st = step_states or {}

    def lab(step: str, n: int, title: str) -> str:
        return f"{STEP_GLYPH.get(st.get(step, 'todo'), '')}{n}. {title}"

    root = TreeNode("project", getattr(project, "name", "") or "پروژه", "root")
    root.children.append(TreeNode("dashboard", "داشبورد", "group"))
    root.children.append(TreeNode("step.project", lab("project", 1, "اطلاعات پروژه"), "group"))

    inp = TreeNode("step.input", lab("input", 2, "ورود داده"), "group")
    sel = workspace.selection
    if sel.heavy:
        h = TreeNode("input.heavy", "متقاضی سنگین", "study")
        h.children = [TreeNode("heavy.applicant", "اطلاعات متقاضی و درخواست", "group"),
                      TreeNode("heavy.feeders", "فیدرها و پخش بار", "group"),
                      TreeNode("heavy.study", "مطالعه مصارف سنگین", "group")]
        inp.children.append(h)
    for kind, label in ((StudyKind.RECLOSER, "ریکلوزر"), (StudyKind.SECTIONALIZER, "سکشنالایزر")):
        if sel.is_selected(kind):
            n = TreeNode(f"input.{kind.value}", label, "study")
            n.children = [TreeNode(f"{kind.value}.network", "فیدرهای محدوده و شبکه", "group"),
                          TreeNode(f"{kind.value}.device", "تجهیز مورد مطالعه", "device"),
                          TreeNode(f"{kind.value}.settings", "تنظیمات و اعتبارسنجی", "group")]
            for name in workspace.scope(kind):
                n.children[0].children.append(TreeNode(f"feeder:{kind.value}:{name}", name, "feeder"))
            inp.children.append(n)
    if sel.is_selected(StudyKind.FEEDER_DEV):            # v2.4.0
        inp.children.append(TreeNode("input.feeder_dev", "توسعه و اصلاح فیدر", "study"))
    inp.children.append(TreeNode("images", "تصاویر و شکل‌های گزارش", "group"))
    root.children.append(inp)

    root.children.append(TreeNode("step.validation", lab("validation", 3, "اعتبارسنجی"), "group"))
    root.children.append(TreeNode("step.analysis", lab("analysis", 4, "تحلیل مهندسی"), "group"))
    root.children.append(TreeNode("step.review", lab("review", 5, "بازبینی مهندس"), "group"))
    root.children.append(TreeNode("step.preview", lab("preview", 6, "پیش‌نمایش گزارش"), "report"))
    gen = TreeNode("step.generate", lab("generate", 7, "تولید گزارش (Report Center)"), "report")
    gen.children = [TreeNode("report.select", "انتخاب مطالعات و بخش‌ها", "report"),
                    TreeNode("report.ai", "دستیار هوش مصنوعی", "report"),
                    TreeNode("report.generate", "تولید و خروجی Word", "report")]
    root.children.append(gen)
    root.children.append(TreeNode("settings", "تنظیمات نرم‌افزار", "group"))
    for child in root.children:                     # قفل گام‌های هنوز باز‌نشده (Guided Flow)
        step = NODE_STEP.get(child.key, "")
        if step:
            _apply_locks(child, step, locked_steps or {})
    return root


def study_status(project: Any, workspace: Workspace, kind: StudyKind,
                 results: Optional[list] = None) -> str:
    """وضعیت یک مطالعه برای Dashboard؛ هیچ «کامل» بدون ارزیابی اعلام نمی‌شود."""
    kind = StudyKind(kind)
    if not workspace.selection.is_selected(kind):
        return ST_NOT_SELECTED
    if not has_study_data(project, kind):
        return ST_EMPTY
    if kind is StudyKind.FEEDER_DEV:
        # v2.4.0 — مطالعه توسعه فیدر موتور قواعد ندارد؛ داده ثبت‌شده = کامل
        return ST_COMPLETE
    if results is None:
        return ST_UNEVALUATED
    if any(r.status in ("MISSING_DATA", "MISSING_RULE", "DATA_ERROR") for r in results):
        return ST_INCOMPLETE
    if any(r.engineer_review_required or r.status == "FAIL" for r in results):
        return ST_REVIEW
    return ST_COMPLETE


def build_dashboard(project: Any, workspace: Workspace,
                    results_by_kind: Optional[dict] = None) -> dict[str, dict[str, str]]:
    out = {}
    for kind in StudyKind:
        status = study_status(project, workspace, kind,
                              (results_by_kind or {}).get(kind))
        out[kind.value] = {"label": STUDY_LABELS_FA[kind], "status": status,
                           "status_label": STATUS_LABELS_FA[status]}
    return out
