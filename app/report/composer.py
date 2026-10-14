# -*- coding: utf-8 -*-
"""Report Composer مبتنی بر Component.

    Selected Studies → Study Analysis (Rule Engine) → Findings
        → Report Composer → Report Sections → (Word/PDF Generator موجود)

* هر بخش یک ``ReportComponent`` ثبت‌شده است؛ افزودن بخش جدید = ثبت یک Component.
* ترتیب و فعال/غیرفعال‌بودن بخش‌ها از ``Workspace.report_prefs`` خوانده می‌شود.
* تولیدکنندهٔ Word/Preview موجود بدون تغییر مصرف‌کنندهٔ ``GeneratedReport`` است.
* هیچ نتیجه‌گیری مهندسی ساخته نمی‌شود: متن جمع‌بندی فقط یافته‌های Rule Engine
  و داده‌های ثبت‌شده را بازتاب می‌دهد و تصمیم نهایی با مهندس است.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from app.core.protection_models import FUNCTION_KEYS, FUNCTION_LABELS_FA, ProtectionSettings
from app.core.tcc import device_curves
from app.core.studies import (PROTECTION_KINDS, STUDY_LABELS_FA, StudyKind,
                              StudySelection)
from app.core.workspace import (OUTPUT_COMBINED, OUTPUT_SEPARATE, Workspace,
                                load_workspace_for, resolve_study_inputs)
from app.core.report_sections import PROTECTION_DEFAULT_SECTION_BY_KIND
from app.report.protection_narrative import NarrativeEngine, RefParagraph
from app.report.sections import (FigureBlock, GeneratedReport, Paragraph, ReportSection,
                                 TableSpec)
from app.rules.trace import trace_link
from app.rules.domains import build_protection_engine, evaluate_study
from app.rules.outcome import STATUS_LABELS_FA

MISSING = "ناموجود"

def figures_for_section(project: Any, resolver: Optional[Callable], key: str) -> list[FigureBlock]:
    """شکل‌های کاربر برای یک بخش: محل صریح (section_key) یا پیش‌فرض بر اساس نوع شکل.

    شکل خاموش (On/Off) یا بدون فایل در دسترس درج نمی‌شود؛ ترتیب با «اولویت» شکل است.
    """
    if resolver is None:
        return []
    images = getattr(project, "active_images", None) or []
    picked = []
    for idx, img in enumerate(images):
        explicit = (getattr(img, "section_key", "") or "").strip()
        target = explicit or PROTECTION_DEFAULT_SECTION_BY_KIND.get(getattr(img, "kind", ""), "")
        if target == key:
            picked.append((getattr(img, "order", 0) or 0, idx, img))
    out: list[FigureBlock] = []
    for _order, _idx, img in sorted(picked, key=lambda t: (t[0], t[1])):
        path = resolver(img)
        if path:
            out.append(FigureBlock(path=str(path),
                                   caption=(getattr(img, "caption", "") or getattr(img, "title", "")
                                            or getattr(img, "kind_label", ""))))
    return out


# ---------------------------------------------------------------------------
# برنامهٔ گزارش‌ها
# ---------------------------------------------------------------------------
@dataclass
class ReportPlan:
    key: str
    title: str
    kinds: list[StudyKind]
    filename_stem: str

    @property
    def is_heavy(self) -> bool:
        return self.kinds == [StudyKind.HEAVY]


def plan_reports(selection: StudySelection, protection_mode: str = OUTPUT_COMBINED
                 ) -> list[ReportPlan]:
    """تعیین گزارش‌های خروجی از انتخاب مطالعات (Report Center).

    * متقاضی سنگین همیشه گزارش مستقل است.
    * اگر فقط یکی از ریکلوزر/سکشنالایزر انتخاب شده باشد، گزارش همان مطالعه.
    * اگر هر دو انتخاب شده باشند: ``combined`` → یک گزارش ترکیبی؛ ``separate`` → دو گزارش.
    """
    plans: list[ReportPlan] = []
    if selection.heavy:
        plans.append(ReportPlan("heavy", "گزارش متقاضی سنگین", [StudyKind.HEAVY],
                                "Heavy Applicant Report"))
    prot = selection.protection_kinds()
    if len(prot) == 2 and protection_mode == OUTPUT_COMBINED:
        plans.append(ReportPlan("combined_protection", "گزارش ترکیبی ریکلوزر و سکشنالایزر",
                                list(prot), "Combined Recloser + Sectionalizer Report"))
    else:
        for kind in prot:
            plans.append(ReportPlan(kind.value, f"گزارش مطالعه {STUDY_LABELS_FA[kind]}", [kind],
                                    "Recloser Report" if kind is StudyKind.RECLOSER
                                    else "Sectionalizer Report"))
    return plans


# ---------------------------------------------------------------------------
# زمینهٔ تولید
# ---------------------------------------------------------------------------
@dataclass
class ComposeContext:
    project: Any
    workspace: Workspace
    kinds: list[StudyKind]
    results: dict[StudyKind, list] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    narrative: NarrativeEngine = field(default_factory=NarrativeEngine)
    vars: dict[str, Any] = field(default_factory=dict)
    charts_dir: Optional[Path] = None
    _tbl: int = 0
    _fig: int = 0

    def next_table(self) -> int:
        self._tbl += 1
        return self._tbl

    def next_figure(self) -> int:
        self._fig += 1
        return self._fig

    def info(self, kind: StudyKind) -> Any:
        return getattr(self.project, kind.value)

    def results_for(self, kind: StudyKind, prefixes: tuple[str, ...] = ()) -> list:
        rows = self.results.get(kind, [])
        if not prefixes:
            return rows
        return [r for r in rows if r.rule_key.startswith(prefixes)]

    def text(self, key: str) -> list[RefParagraph]:
        """پاراگراف‌های قالب‌محور بخش (Narrative Engine)."""
        return self.narrative.section(key, self.vars, self.results)


def _lines(results: list) -> list[RefParagraph]:
    """هر یافته یک خط؛ شناسهٔ Rule برای ردیابی در ``refs`` می‌ماند."""
    out = []
    for r in results:
        text = r.finding or r.rule_name
        out.append(RefParagraph(
            text=f"{STATUS_LABELS_FA.get(r.status, r.status)}: {text}"
                 + (" (نیازمند بازبینی مهندس)" if r.engineer_review_required else ""),
            refs=[r.rule_key], template_id="finding"))
    return out


def _settings_table(ctx: ComposeContext, caption: str, settings: ProtectionSettings) -> TableSpec:
    rows = []
    for key in FUNCTION_KEYS:
        f = settings.function(key)
        rows.append([FUNCTION_LABELS_FA[key], f.curve or MISSING, f.time_text(),
                     MISSING if f.pickup_a is None else f"{f.pickup_a:g}"])
    dead = "، ".join(f"{t:g}" for t in settings.dead_times_s) or MISSING
    extra = [["تعداد Shot", MISSING if settings.shots is None else str(settings.shots), "", ""],
             ["Dead time (s)", dead, "", ""],
             ["Reclaim time (s)", MISSING if settings.reclaim_time_s is None
              else f"{settings.reclaim_time_s:g}", "", ""],
             ["Counter", MISSING if settings.counter is None else str(settings.counter), "", ""]]
    return TableSpec(caption=f"جدول {ctx.next_table()}: {caption}",
                     header_rows=[["تابع / پارامتر", "منحنی", "TMS / زمان", "Pickup (A)"]],
                     body_rows=rows + extra)


# ---------------------------------------------------------------------------
# Componentها
# ---------------------------------------------------------------------------
def _intro(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("prot_intro", "مقدمه")
    sec.blocks.extend(ctx.text("prot_intro"))
    return sec


def _network(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("prot_network", "مشخصات شبکه")
    sec.blocks.extend(ctx.text("prot_network"))
    rows, seen = [], set()
    for kind in ctx.kinds:
        inp = resolve_study_inputs(ctx.project, ctx.workspace, kind)
        name = inp["feeder_name"].value or MISSING
        if name in seen:
            continue
        seen.add(name)
        common = inp["common_feeder"]
        fmtv = lambda r: MISSING if r.value is None else f"{r.value:g}"  # noqa: E731
        rows.append([name, (common.substation if common else "") or MISSING,
                     fmtv(inp["voltage_kv"]), fmtv(inp["load_current_a"]),
                     fmtv(inp["fault_current_ka"]), fmtv(inp["min_fault_current_ka"])])
    sec.blocks.append(TableSpec(
        caption=f"جدول {ctx.next_table()}: مشخصات فیدرهای مورد مطالعه",
        header_rows=[["فیدر", "پست", "ولتاژ (kV)", "جریان بار (A)",
                      "Isc حداکثر (kA)", "Isc حداقل (kA)"]],
        body_rows=rows))
    sec.blocks.extend(_lines(ctx.results_for(ctx.kinds[0], ("PCM-"))) if ctx.kinds else [])
    return sec


def _existing_protection(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("prot_existing", "وضعیت حفاظتی موجود")
    sec.blocks.extend(ctx.text("prot_existing"))
    shown = False
    for kind in ctx.kinds:
        common = resolve_study_inputs(ctx.project, ctx.workspace, kind)["common_feeder"]
        for dev in (common.existing_protection if common else []):
            shown = True
            sec.blocks.append(Paragraph(f"{dev.name or dev.device_type} — {dev.location or MISSING}",
                                        style="item"))
            sec.blocks.append(_settings_table(ctx, f"تنظیمات {dev.name or dev.device_type}",
                                              dev.settings))
    if not shown:
        ctx.warnings.append("وضعیت حفاظتی موجود ثبت نشده است.")
    return sec


def _basic_info_text(info: Any) -> str:
    """مقادیر صفحهٔ «تجهیز مورد مطالعه» (شامل فیلدهای پروژه‌های قدیمی) — فقط آنچه ثبت شده است."""
    parts = []
    for attr, label, unit in (("fault_current_ka", "جریان اتصال کوتاه محل نصب", "کیلوآمپر"),
                              ("min_fault_current_ka", "حداقل جریان اتصال کوتاه", "کیلوآمپر"),
                              ("pickup_current_a", "جریان پیکاپ ثبت‌شده", "آمپر"),
                              ("tms", "تنظیم زمانی (TMS) ثبت‌شده", "")):
        v = getattr(info, attr, None)
        if v is not None:
            parts.append(f"{label} {v:g}" + (f" {unit}" if unit else ""))
    for attr, label in (("upstream_device", "تجهیز بالادست"), ("coordination_note", "توضیح هماهنگی")):
        v = (getattr(info, attr, "") or "").strip()
        if v:
            parts.append(f"{label}: {v}")
    return ("اطلاعات پایهٔ ثبت‌شده: " + "؛ ".join(parts) + ".") if parts else ""


def _study_component(kind: StudyKind, key: str, title: str) -> Callable[[ComposeContext], ReportSection]:
    skip = ("REC-COORD", "REC-CURVE", "SECZ-PK", "SECZ-TMS", "SECZ-COUNTER", "SECZ-DEADLINE",
            "REC-PLACEMENT", "PCM-", "REC-SHOTS", "SECZ-REF")

    def build(ctx: ComposeContext) -> ReportSection:
        info = ctx.info(kind)
        sec = ReportSection(key, title)
        sec.blocks.extend(ctx.text(key))
        base = _basic_info_text(info)
        if base:
            sec.blocks.append(Paragraph(base))
        sec.blocks.append(_settings_table(ctx, f"تنظیمات {STUDY_LABELS_FA[kind]}", info.settings))
        sec.blocks.extend(_lines([r for r in ctx.results_for(kind) if not r.rule_key.startswith(skip)]))
        return sec
    return build


def _coordination_table(ctx: ComposeContext, kind: StudyKind) -> Optional[TableSpec]:
    """جدول مقایسهٔ تنظیمات با مرجع (بالادست برای ریکلوزر، ریکلوزر برای سکشنالایزر)."""
    inp = resolve_study_inputs(ctx.project, ctx.workspace, kind)
    ref = inp["upstream_settings"]
    if ref is None:
        return None
    own = ctx.info(kind).settings
    rows = []
    for key in FUNCTION_KEYS:
        a, b = own.function(key), ref.function(key)
        rows.append([FUNCTION_LABELS_FA[key],
                     MISSING if a.pickup_a is None else f"{a.pickup_a:g}", a.time_text(),
                     MISSING if b.pickup_a is None else f"{b.pickup_a:g}", b.time_text()])
    who = "ریکلوزر" if kind is StudyKind.RECLOSER else "سکشنالایزر"
    ref_who = "تجهیز بالادست" if kind is StudyKind.RECLOSER else "ریکلوزر مرجع"
    return TableSpec(
        caption=f"جدول {ctx.next_table()}: مقایسهٔ تنظیمات {who} با {ref_who} ({inp['upstream_ref']})",
        header_rows=[["تابع", f"Pickup {who} (A)", f"زمان {who}", f"Pickup {ref_who} (A)", f"زمان {ref_who}"]],
        body_rows=rows)


def _relay_devices(ctx: ComposeContext) -> list[tuple[str, ProtectionSettings]]:
    """کلیهٔ رله‌های جریانی گزارش: رله(های) سر خط موجود + تجهیز(های) مورد مطالعه.

    فقط تجهیزاتی برمی‌گردند که دست‌کم یک تابع جریانی ثبت‌شده دارند؛ هیچ مقداری
    حدس زده نمی‌شود.
    """
    devices: list[tuple[str, ProtectionSettings]] = []
    seen_feeders: set[str] = set()
    for kind in ctx.kinds:
        inp = resolve_study_inputs(ctx.project, ctx.workspace, kind)
        common = inp["common_feeder"]
        feeder = inp["feeder_name"].value or ""
        if common is not None and feeder not in seen_feeders:
            seen_feeders.add(feeder)
            for dev in common.existing_protection:
                if dev.settings is not None and dev.settings.any_function_set():
                    devices.append((dev.name or "رله سر خط", dev.settings))
        elif common is None:
            up, up_ref = inp["upstream_settings"], inp["upstream_ref"]
            if up is not None and up.any_function_set() and not any(s is up for _n, s in devices):
                devices.append((up_ref or "تجهیز بالادست", up))
    for kind in ctx.kinds:
        info = ctx.info(kind)
        settings = getattr(info, "settings", None)
        if settings is not None and settings.any_function_set():
            name = (getattr(info, "name", "") or "").strip() or STUDY_LABELS_FA[kind]
            devices.append((f"{STUDY_LABELS_FA[kind]} {name}".strip()
                            if name != STUDY_LABELS_FA[kind] else name, settings))
    return devices


def _tcc_figures(ctx: ComposeContext) -> list[FigureBlock]:
    """نمودارهای پیش‌فرض جریان–زمان (TCC) توابع فاز و زمین همهٔ رله‌های جریانی.

    مطابق شکل‌های ۳ و ۴ دفترچه نمونه فیدر ۴ خلخال؛ منحنی‌های NI/VI/EI با TMS
    درصدی و جریان بر حسب آمپر رسم می‌شوند. اگر دادهٔ تنظیمی ثبت نشده باشد،
    نموداری تولید نمی‌شود (بدون مقدار ساختگی).
    """
    devices = _relay_devices(ctx)
    if not devices:
        return []
    try:
        from app.report.chart_generator import tcc_chart
    except Exception:  # noqa: BLE001 — نبود matplotlib نباید گزارش را متوقف کند
        return []
    markers: dict[str, float] = {}
    if ctx.kinds:
        inp = resolve_study_inputs(ctx.project, ctx.workspace, ctx.kinds[0])
        max_ka, min_ka = inp["fault_current_ka"].value, inp["min_fault_current_ka"].value
        if min_ka is not None:
            markers["Isc حداقل"] = min_ka * 1000.0
        if max_ka is not None:
            markers["Isc حداکثر"] = max_ka * 1000.0
    out_dir = Path(ctx.charts_dir) if ctx.charts_dir else (
        Path(tempfile.gettempdir()) / "reportforge_charts")
    out: list[FigureBlock] = []
    groups = (
        ("phase", "tcc_phase.png",
         "نمودار هماهنگی جریان–زمان حفاظت جریان زیاد زمان‌دار (۵۱) و آنی (۵۰)"),
        ("ground", "tcc_ground.png",
         "نمودار هماهنگی جریان–زمان حفاظت خطای زمین زمان‌دار (۵۱N) و آنی (۵۰N)"),
    )
    for group, filename, title in groups:
        curves = [c for name, s in devices for c in device_curves(name, s, group)]
        if not curves:
            continue
        try:
            path = tcc_chart(curves, out_dir / filename, title="",
                             fault_markers=markers or None)
        except Exception:  # noqa: BLE001
            ctx.warnings.append(f"تولید نمودار جریان–زمان ({group}) ممکن نشد.")
            continue
        if path is not None:
            out.append(FigureBlock(path=str(path),
                                   caption=f"شکل {ctx.next_figure()}: {title}"))
    return out


def _coordination(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("prot_coordination", "هماهنگی حفاظتی")
    sec.blocks.extend(ctx.text("prot_coordination"))
    for kind in ctx.kinds:
        table = _coordination_table(ctx, kind)
        if table is not None:
            sec.blocks.append(table)
        rows = ctx.results_for(kind, ("REC-COORD", "REC-CURVE", "SECZ-PK", "SECZ-TMS",
                                      "SECZ-COUNTER", "SECZ-DEADLINE"))
        sec.blocks.extend(_lines(rows))
    # نمودارهای پیش‌فرض جریان–زمان (TCC) — شکل‌های ۳ و ۴ دفترچه نمونه
    figures = _tcc_figures(ctx)
    if figures:
        sec.blocks.append(Paragraph(
            "منحنی‌های جریان–زمان (TCC) رله‌های جریانی ثبت‌شده — بر اساس منحنی‌های "
            "استاندارد IEC (NI/VI/EI)، جریان بر حسب آمپر و TMS بر حسب درصد — در "
            "شکل‌های زیر مقایسه شده‌اند."))
        sec.blocks.extend(figures)
    return sec


def _placement(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("prot_placement", "جانمایی تجهیزات")
    sec.blocks.extend(ctx.text("prot_placement"))
    for kind in ctx.kinds:
        info = ctx.info(kind)
        sec.blocks.append(Paragraph(
            f"{STUDY_LABELS_FA[kind]} ({getattr(info, 'name', '')}): "
            f"{getattr(info, 'installation_location', '') or MISSING}", style="item"))
        sec.blocks.extend(_lines(ctx.results_for(kind, ("REC-PLACEMENT",))))
    return sec


def _scenario(ctx: ComposeContext) -> ReportSection:
    """سناریوی عملکرد — فقط از داده‌های ثبت‌شده؛ در نبود داده ساخته نمی‌شود."""
    sec = ReportSection("prot_scenario", "سناریوی عملکرد")
    sec.blocks.extend(ctx.text("prot_scenario"))
    if not ctx.vars.get("has_rec_shots") and not ctx.vars.get("has_secz_counter"):
        ctx.warnings.append("سناریوی عملکرد به‌دلیل نبود داده (Shot/Counter) تولید نشد.")
    return sec


def _all_results(ctx: ComposeContext) -> list:
    return [r for rows in ctx.results.values() for r in rows]


def _conclusion(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("prot_conclusion", "جمع‌بندی")
    sec.blocks.extend(ctx.text("prot_conclusion"))
    return sec


def _recommendation(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("prot_recommendation", "پیشنهاد نهایی")
    for r in (r for r in _all_results(ctx) if r.text_available):
        sec.blocks.append(RefParagraph(text=r.recommended_text, refs=[r.rule_key],
                                       template_id="recommended_text"))
    sec.blocks.extend(ctx.text("prot_recommendation"))
    return sec


def _trace(ctx: ComposeContext) -> ReportSection:
    """پیوست ردیابی: هر یافته ← Rule، مقادیر ورودی، منبع و محل اصلاح در نرم‌افزار."""
    sec = ReportSection("prot_trace", "پیوست — ردیابی یافته‌ها")
    rows = []
    for kind in ctx.kinds:
        for r in ctx.results.get(kind, []):
            if r.status == "PASS":
                continue
            t = trace_link(r, kind)
            vals = "، ".join(f"{k}={v:g}" if isinstance(v, (int, float)) and not isinstance(v, bool)
                             else f"{k}={v}" for k, v in t.values.items() if v is not None)
            rows.append([r.rule_key, STATUS_LABELS_FA.get(r.status, r.status), r.finding or r.rule_name,
                         vals or "—", f"{r.source} {r.source_page}".strip() or "—",
                         f"{t.route} ← {t.field}" if t.route else "—"])
    if not rows:
        sec.blocks.append(Paragraph("یافتهٔ غیرمنطبقی برای ردیابی وجود ندارد."))
        return sec
    sec.blocks.append(TableSpec(
        caption=f"جدول {ctx.next_table()}: ردیابی یافته‌ها",
        header_rows=[["Rule", "وضعیت", "یافته", "مقادیر ورودی", "منبع قاعده", "محل اصلاح"]],
        body_rows=rows))
    return sec


@dataclass
class ReportComponent:
    key: str
    title: str
    build: Callable[[ComposeContext], ReportSection]
    requires_kinds: Optional[set[StudyKind]] = None   # None = برای هر مطالعهٔ حفاظتی

    def applies(self, kinds: list[StudyKind]) -> bool:
        return self.requires_kinds is None or bool(self.requires_kinds & set(kinds))


# ترتیب فصل‌ها دقیقاً مطابق فهرست دفترچه نمونه «احداث ریکلوزر — فیدر ۴ خلخال»:
#   ۱ مقدمه — ۲ مشخصات شبکه — ۳ وضعیت حفاظتی موجود — ۴ جانمایی تجهیزات —
#   ۵ مطالعه ریکلوزر (/سکشنالایزر) — ۶ هماهنگی حفاظتی — ۷ سناریوی عملکرد
# بخش‌های تکمیلی (جمع‌بندی، پیشنهاد نهایی، پیوست ردیابی) پس از اسکلت نمونه می‌آیند.
DEFAULT_COMPONENTS: list[ReportComponent] = [
    ReportComponent("prot_intro", "مقدمه", _intro),
    ReportComponent("prot_network", "مشخصات شبکه", _network),
    ReportComponent("prot_existing", "وضعیت حفاظتی موجود", _existing_protection),
    ReportComponent("prot_placement", "جانمایی تجهیزات", _placement),
    ReportComponent("prot_recloser", "مطالعه ریکلوزر",
                    _study_component(StudyKind.RECLOSER, "prot_recloser", "مطالعه ریکلوزر"),
                    {StudyKind.RECLOSER}),
    ReportComponent("prot_sectionalizer", "مطالعه سکشنالایزر",
                    _study_component(StudyKind.SECTIONALIZER, "prot_sectionalizer",
                                     "مطالعه سکشنالایزر"), {StudyKind.SECTIONALIZER}),
    ReportComponent("prot_coordination", "هماهنگی حفاظتی", _coordination),
    ReportComponent("prot_scenario", "سناریوی عملکرد", _scenario),
    ReportComponent("prot_conclusion", "جمع‌بندی", _conclusion),
    ReportComponent("prot_recommendation", "پیشنهاد نهایی", _recommendation),
    ReportComponent("prot_trace", "پیوست — ردیابی یافته‌ها", _trace),
]


def apply_manual_texts(project: Any, sections: list[ReportSection]) -> None:
    """متن ویرایش‌شدهٔ کارشناس/هوش مصنوعی (``project.manual_texts``) جای پاراگراف‌های بخش می‌نشیند؛
    جدول‌ها و شکل‌ها حفظ می‌شوند و بخش با ``manual=True`` علامت می‌خورد."""
    texts = getattr(project, "manual_texts", None) or {}
    for sec in sections:
        manual = (texts.get(sec.key) or "").strip()
        if not manual:
            continue
        keep = [b for b in sec.blocks if not isinstance(b, Paragraph)]
        paras = [Paragraph(line) for line in manual.split("\n") if line.strip()]
        sec.blocks = paras + keep
        sec.manual = True


class ReportComposer:
    """ترکیب‌کنندهٔ گزارش‌های مطالعات حفاظتی از روی Componentهای ثبت‌شده."""

    def __init__(self, components: Optional[list[ReportComponent]] = None, engine=None,
                 narrative: Optional[NarrativeEngine] = None) -> None:
        self.components = list(components or DEFAULT_COMPONENTS)
        self.engine = engine
        self.narrative = narrative or NarrativeEngine()

    def register(self, component: ReportComponent, before: Optional[str] = None) -> None:
        """افزودن/جایگزینی بخش؛ ``before`` = کلید بخشی که بخش جدید قبل از آن می‌آید."""
        self.components = [c for c in self.components if c.key != component.key]
        idx = next((i for i, c in enumerate(self.components) if c.key == before),
                   len(self.components))
        self.components.insert(idx, component)

    def ordered(self, prefs=None) -> list[ReportComponent]:
        comps = list(self.components)
        if prefs is not None and prefs.section_order:
            rank = {k: i for i, k in enumerate(prefs.section_order)}
            comps.sort(key=lambda c: rank.get(c.key, len(rank) + self.components.index(c)))
        disabled = set(getattr(prefs, "disabled_sections", []) or [])
        return [c for c in comps if c.key not in disabled]

    def analyse(self, project: Any, workspace: Workspace, kinds: list[StudyKind],
                thresholds: Optional[dict] = None) -> dict:
        engine = self.engine or build_protection_engine()
        return {k: evaluate_study(project, workspace, k, engine, thresholds) for k in kinds}

    def compose(self, project: Any, workspace: Workspace, kinds: list[StudyKind],
                thresholds: Optional[dict] = None,
                image_resolver: Optional[Callable] = None,
                notices: Optional[list[str]] = None,
                charts_dir: Optional[Path] = None) -> GeneratedReport:
        kinds = [k for k in kinds if k in PROTECTION_KINDS]
        ctx = ComposeContext(project, workspace, kinds, narrative=self.narrative,
                             charts_dir=charts_dir)
        ctx.results = self.analyse(project, workspace, kinds, thresholds)
        ctx.vars = self.narrative.build_vars(project, workspace, kinds, ctx.results)
        sections = []
        if notices:                                       # خطاهای رفع‌نشده در آغاز گزارش
            sections.append(ReportSection("prot_notice", "هشدار — نقص‌های رفع‌نشده", [
                Paragraph("این گزارش با وجود نقص‌های زیر تولید شده است و پیش از استفاده باید بازبینی شود:"),
                *[Paragraph(f"• {n}", style="item") for n in notices]]))
        for comp in self.ordered(workspace.report_prefs):
            if not comp.applies(kinds):
                continue
            sec = comp.build(ctx)
            sec.blocks.extend(figures_for_section(project, image_resolver, sec.key))
            sections.append(sec)
        apply_manual_texts(project, sections)
        report = GeneratedReport(sections=sections)
        report.warnings = list(ctx.warnings)
        report.findings = []
        return report

    def build(self, plan: ReportPlan, project: Any, workspace: Workspace,
              heavy_builder: Optional[Callable[[], GeneratedReport]] = None,
              thresholds: Optional[dict] = None) -> GeneratedReport:
        if plan.is_heavy:
            if heavy_builder is None:
                raise ValueError("برای گزارش متقاضی سنگین heavy_builder لازم است.")
            return heavy_builder()
        return self.compose(project, workspace, plan.kinds, thresholds)


class ProtectionReportGenerator:
    """آداپتور هم‌شکل با ``TextGenerator``/``SectionalizerGenerator`` برای pipeline."""

    def __init__(self, project, settings, texts, engine=None, charts_dir=None,
                 image_resolver=None, profile_loader=None, kinds=None, workspace=None) -> None:
        self.project, self.settings = project, settings
        self.image_resolver = image_resolver
        self.charts_dir = charts_dir
        self.workspace = workspace or getattr(project, "_workspace", None) \
            or load_workspace_for(project)
        self.kinds = kinds or self.workspace.selection.protection_kinds()
        self.findings: list = []
        self.report_warnings: list[str] = []

    def build_all(self) -> list[ReportSection]:
        report = ReportComposer().compose(self.project, self.workspace, self.kinds,
                                          image_resolver=self.image_resolver,
                                          charts_dir=self.charts_dir)
        self.report_warnings = list(report.warnings)
        return report.sections
