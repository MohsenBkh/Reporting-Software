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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from app.core.protection_models import FUNCTION_KEYS, FUNCTION_LABELS_FA, ProtectionSettings
from app.core.studies import (PROTECTION_KINDS, STUDY_LABELS_FA, StudyKind,
                              StudySelection)
from app.core.workspace import (OUTPUT_COMBINED, OUTPUT_SEPARATE, Workspace,
                                load_workspace_for, resolve_study_inputs)
from app.core.report_sections import (DISCONNECTOR_DEFAULT_SECTION_BY_KIND,
                                      FEEDER_DEV_DEFAULT_SECTION_BY_KIND,
                                      PROTECTION_DEFAULT_SECTION_BY_KIND)
from app.report.protection_narrative import NarrativeEngine, RefParagraph
from app.report.sections import (FigureBlock, GeneratedReport, Paragraph, ReportSection,
                                 TableSpec, number_figures)
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
        kind = getattr(img, "kind", "")
        if explicit:
            targets = {explicit}
        else:       # بدون محل صریح: پیش‌فرض نوع شکل در گزارش حفاظتی/توسعه فیدر/جایابی سکسیونر
            targets = {PROTECTION_DEFAULT_SECTION_BY_KIND.get(kind, ""),
                       FEEDER_DEV_DEFAULT_SECTION_BY_KIND.get(kind, ""),
                       DISCONNECTOR_DEFAULT_SECTION_BY_KIND.get(kind, "")}
        if key in targets:
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
    if getattr(selection, "feeder_dev", False):      # v2.4.0 — دفترچه توسعه و اصلاح فیدر
        plans.append(ReportPlan(StudyKind.FEEDER_DEV.value,
                                "گزارش مطالعه توسعه و اصلاح فیدر",
                                [StudyKind.FEEDER_DEV], "Feeder Development Report"))
    if getattr(selection, "disconnector", False):    # v2.6.0 — دفترچه جایابی سکسیونر
        plans.append(ReportPlan(StudyKind.DISCONNECTOR.value,
                                "گزارش مطالعه جایابی سکسیونر",
                                [StudyKind.DISCONNECTOR], "Disconnector Placement Report"))
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
    # v2.4.0 — قابلیت فیوز سیوینگ ریکلوزر (فقط وقتی ثبت شده باشد درج می‌شود)
    if settings.fuse_saving is not None or (settings.fuse_saving_note or "").strip():
        state = (MISSING if settings.fuse_saving is None
                 else ("فعال" if settings.fuse_saving else "غیرفعال"))
        extra.append(["فیوز سیوینگ (Fuse saving)", state,
                      (settings.fuse_saving_note or "").strip(), ""])
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
    # v2.2.0: نمودارهای TCC از نرم‌افزار «هماهنگی حفاظت فیدر (IDMT)» وارد می‌شوند
    # (ورود از IDMT → شکل‌های بخش هماهنگی)؛ گزارش‌ساز دیگر نمودار TCC نمی‌سازد.
    if _has_section_images(ctx.project, "prot_coordination", kind="tcc"):
        sec.blocks.append(Paragraph(
            "منحنی‌های هماهنگی جریان–زمان (TCC) حفاظت فاز و ارت‌فالت — خروجی "
            "نرم‌افزار هماهنگی حفاظت فیدر (IDMT) بر اساس دستورالعمل TAV111-02/00 — "
            "در شکل‌های زیر ارائه شده‌اند."))
    return sec


def _has_section_images(project: Any, section_key: str, kind: str = "") -> bool:
    """آیا شکلی فعال برای این بخش ثبت شده است؟ (پیش از درج figures_for_section)"""
    for img in getattr(project, "active_images", []) or []:
        key = (getattr(img, "section_key", "") or "").strip() \
            or PROTECTION_DEFAULT_SECTION_BY_KIND.get(getattr(img, "kind", ""), "")
        if key == section_key and (not kind or getattr(img, "kind", "") == kind):
            return True
    return False


def _placement(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("prot_placement", "جانمایی تجهیزات")
    sec.blocks.extend(ctx.text("prot_placement"))
    for kind in ctx.kinds:
        info = ctx.info(kind)
        coords = (getattr(info, "coordinates", "") or "").strip()
        sec.blocks.append(Paragraph(
            f"{STUDY_LABELS_FA[kind]} ({getattr(info, 'name', '')}): "
            f"{getattr(info, 'installation_location', '') or MISSING}"
            + (f" — مختصات محل نصب: {coords}" if coords else ""), style="item"))
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


def _settings_sheet(ctx: ComposeContext) -> ReportSection:
    """پیوست «برگه تنظیمات» — برگه A4 تنظیمات نهایی خروجی نرم‌افزار IDMT.

    فقط وقتی ساخته می‌شود که شکل برگه (ورود از IDMT) در پروژه ثبت شده باشد؛
    در غیر این صورت بخش خالی می‌ماند و از گزارش حذف می‌شود.
    """
    sec = ReportSection("prot_settings_sheet", "پیوست — برگه تنظیمات هماهنگی")
    if _has_section_images(ctx.project, "prot_settings_sheet"):
        sec.blocks.append(Paragraph(
            "برگه تنظیمات نهایی هماهنگی حفاظتی فاز و زمین (خروجی نرم‌افزار هماهنگی "
            "حفاظت فیدر — IDMT) در ادامه پیوست شده است. این برگه شامل تنظیمات نهایی "
            "رله سرخط، ریکلوزر و سکشنالایزر به همراه توالی مشترک وصل مجدد است."))
    return sec


# ---------------------------------------------------------------------------
# v2.4.0 — بخش‌های مطالعه «توسعه و اصلاح فیدر» (دفترچه مطالعات توسعه و اصلاح شبکه)
# اسکلت فصل‌ها مطابق دفترچه‌های نمونه: مقدمه ← مشخصات شبکه و وضعیت موجود ←
# پخش بار قبل ← راه‌حل پیشنهادی ← پخش بار بعد ← نتیجه‌گیری.
# ---------------------------------------------------------------------------
def _fd_num(v: Optional[float], unit: str = "") -> str:
    if v is None:
        return MISSING
    return f"{v:g} {unit}".strip()


def _fd_paras(text: str) -> list[Paragraph]:
    return [Paragraph(line.strip()) for line in (text or "").split("\n") if line.strip()]


def _fd_info(ctx: ComposeContext):
    return getattr(ctx.project, "feeder_dev", None)


def _fd_intro(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("fd_intro", "مقدمه")
    info = _fd_info(ctx)
    if info is None:
        return sec
    if (info.intro or "").strip():
        sec.blocks.extend(_fd_paras(info.intro))
        return sec
    # متن پیش‌فرض مطابق مقدمه دفترچه‌های نمونه (مرجع‌ها: WI150900 و TAV111-03/00)
    kind = (info.plan_kind or "").strip() or "توسعه و اصلاح شبکه فشار متوسط"
    where = f" در محدوده پست {info.substation.strip()}" if (info.substation or "").strip() else ""
    sec.blocks.append(Paragraph(
        "این گزارش بر اساس «دستورالعمل بررسی درخواست و تأمین برق متقاضیان» به شماره "
        "WI150900 و استاندارد شرکت توانیر به شماره TAV111-03/00 تهیه شده است و نتایج "
        f"مطالعه {kind}{where} را ارائه می‌کند."))
    sec.blocks.append(Paragraph(
        "در این مطالعه ابتدا وضعیت موجود فیدرهای محدوده بررسی و سپس نتایج پخش بار "
        "شبکه در دو حالت قبل و بعد از اجرای طرح پیشنهادی مقایسه می‌شود تا اثر طرح بر "
        "پروفیل ولتاژ، بارگیری و تلفات شبکه مشخص شود."))
    return sec


def _fd_network(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("fd_network", "مشخصات شبکه و وضعیت موجود")
    info = _fd_info(ctx)
    if info is None:
        return sec
    sec.blocks.extend(_fd_paras(info.existing_description))
    rows = [[(f.name or MISSING), _fd_num(f.voltage_kv), _fd_num(f.length_km),
             _fd_num(f.peak_load_mw), _fd_num(f.min_load_mw),
             _fd_num(f.loading_pct), _fd_num(f.power_factor)]
            for f in (info.feeders or [])]
    if rows:
        sec.blocks.append(TableSpec(
            caption=f"جدول {ctx.next_table()}: مشخصات فیدرهای محدوده مطالعه",
            header_rows=[["پست و فیدر", "ولتاژ (kV)", "طول خط (km)", "حداکثر بار (MW)",
                          "حداقل بار (MW)", "بارگیری (%)", "ضریب قدرت"]],
            body_rows=rows))
    # v2.5.0 — تحلیل خودکار موتور قواعد (بارگیری/نوسان بار/ضریب قدرت/نیروگاه/اتوبوستر)
    from app.core.feeder_dev_rules import network_paragraphs
    for text in network_paragraphs(ctx.project):
        sec.blocks.append(Paragraph(text))
    # جدول نیروگاه‌های محدوده مطالعه (در صورت ثبت)
    plants = list(getattr(ctx.project, "power_plants", []) or [])
    if getattr(ctx.project, "has_power_plants", "") == "yes" and plants:
        prows = [[p.kind_label, _fd_num(p.rated_mw), _fd_num(p.operation_mw),
                  (p.location_note or MISSING)] for p in plants]
        sec.blocks.append(TableSpec(
            caption=f"جدول {ctx.next_table()}: نیروگاه‌های محدوده مطالعه",
            header_rows=[["نوع نیروگاه", "توان نامی (MW)", "ظرفیت بهره‌برداری (MW)",
                          "محل نصب"]],
            body_rows=prows))
    return sec


_FD_METRICS = (("حداقل ولتاژ شبکه (kV)", "min_voltage_kv_before", "min_voltage_kv_after"),
               ("تلفات توان (kW)", "losses_kw_before", "losses_kw_after"),
               ("حداکثر بارگیری فیدر (%)", "max_loading_pct_before", "max_loading_pct_after"))


def _fd_before(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("fd_before", "وضعیت پخش بار شبکه قبل از اصلاح")
    info = _fd_info(ctx)
    if info is None:
        return sec
    sec.blocks.extend(_fd_paras(info.before_description))
    rows = [[label, _fd_num(getattr(info, b))]
            for label, b, _a in _FD_METRICS if getattr(info, b) is not None]
    if rows:
        sec.blocks.append(TableSpec(
            caption=f"جدول {ctx.next_table()}: نتایج پخش بار شبکه قبل از اصلاح",
            header_rows=[["پارامتر", "مقدار"]], body_rows=rows))
    return sec


def _fd_plan(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("fd_plan", "راه‌حل پیشنهادی (شرح طرح)")
    info = _fd_info(ctx)
    if info is None:
        return sec
    sec.blocks.extend(_fd_paras(info.proposal_description))
    rows = []
    if (info.plan_kind or "").strip():
        rows.append(["نوع طرح", info.plan_kind.strip()])
    if info.new_line_length_km is not None:
        rows.append(["طول خط جدید/اصلاحی (km)", _fd_num(info.new_line_length_km)])
    if (info.conductor_type or "").strip():
        rows.append(["نوع هادی", info.conductor_type.strip()])
    if info.removed_line_length_km is not None:
        rows.append(["طول خط برچیده‌شده (km)", _fd_num(info.removed_line_length_km)])
    if rows:
        sec.blocks.append(TableSpec(
            caption=f"جدول {ctx.next_table()}: مشخصات طرح پیشنهادی",
            header_rows=[["پارامتر", "مقدار"]], body_rows=rows))
    return sec


def _fd_after(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("fd_after", "وضعیت پخش بار شبکه بعد از اصلاح")
    info = _fd_info(ctx)
    if info is None:
        return sec
    sec.blocks.extend(_fd_paras(info.after_description))
    rows = [[label, _fd_num(getattr(info, b)), _fd_num(getattr(info, a))]
            for label, b, a in _FD_METRICS
            if getattr(info, b) is not None or getattr(info, a) is not None]
    if rows:
        sec.blocks.append(TableSpec(
            caption=f"جدول {ctx.next_table()}: مقایسه نتایج پخش بار قبل و بعد از اصلاح",
            header_rows=[["پارامتر", "قبل از اصلاح", "بعد از اصلاح"]], body_rows=rows))
    # v2.5.0 — شینه‌های کاندید: جدول مقایسه ولتاژ/بارگیری ترانس (جدول ۴ نمونه)
    buses = list(getattr(info, "candidate_buses", []) or [])
    if buses:
        brows = [[(b.name or MISSING),
                  _fd_num(b.voltage_kv_before), _fd_num(b.voltage_kv_after),
                  _fd_num(b.trafo_loading_pct_before), _fd_num(b.trafo_loading_pct_after)]
                 for b in buses]
        sec.blocks.append(TableSpec(
            caption=f"جدول {ctx.next_table()}: مقایسه ولتاژ و بارگیری ترانسفورماتور "
                    "شینه‌های کاندید قبل و بعد از اصلاح",
            header_rows=[["شینه کاندید", "ولتاژ قبل (kV)", "ولتاژ بعد (kV)",
                          "بارگیری ترانسفورماتور قبل (%)", "بارگیری ترانسفورماتور بعد (%)"]],
            body_rows=brows))
        from app.core.feeder_dev_rules import after_paragraphs
        for text in after_paragraphs(ctx.project):
            sec.blocks.append(Paragraph(text))
    return sec


def _fd_conclusion(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("fd_conclusion", "نتیجه‌گیری")
    info = _fd_info(ctx)
    if info is None:
        return sec
    if (info.conclusion or "").strip():
        sec.blocks.extend(_fd_paras(info.conclusion))
        return sec
    # v2.5.0 — نتیجه‌گیری خودکار موتور قواعد به سبک دفترچه‌های نمونه
    from app.core.feeder_dev_rules import conclusion_paragraph
    text = conclusion_paragraph(ctx.project)
    if text:
        sec.blocks.append(Paragraph(text))
    return sec


# ---------------------------------------------------------------------------
# v2.6.0 — بخش‌های مطالعه «جایابی سکسیونر» (قالب: Disconnector Format.json)
# متن‌های ثابت قالب عیناً درج می‌شوند؛ مقادیر داخل آکولاد از ورودی کاربر یا
# فایل eens_report.json (نرم‌افزار SwitchLoc) پر می‌شوند؛ خالی = «ناموجود».
# ---------------------------------------------------------------------------
def _dx_info(ctx: ComposeContext):
    return getattr(ctx.project, "disconnector", None)


def _dx(v) -> str:
    """مقدار متنی/عددی متغیر قالب؛ خالی یا None = «ناموجود».

    اعداد حداکثر با ۴ رقم اعشار و بدون صفرهای انتهایی درج می‌شوند تا مقادیر
    واردشده از eens_report.json (مثل 562.1667) عیناً حفظ شوند.
    """
    if v is None:
        return MISSING
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".") if v != int(v) else f"{int(v)}"
    s = str(v).strip()
    return s or MISSING


def _dx_feeder(ctx: ComposeContext, info) -> str:
    return (info.feeder_name or "").strip() or MISSING


def _dx_post(ctx: ComposeContext, info) -> str:
    return ((info.post_name or "").strip()
            or (getattr(ctx.project, "substation", "") or "").strip() or MISSING)


def _dx_office(ctx: ComposeContext) -> str:
    return (getattr(ctx.project, "office", "") or "").strip() or MISSING


# متن ثابت مقدمه — عیناً از قالب (پاراگراف اول بدون متغیر است)
DX_INTRO_FIXED = (
    "مطابق «دستورالعمل جاری‌سازی مطالعات و تحلیل شبکه در شبکه‌های توزیع» شرکت توانیر "
    "با کد TAV111-03/00 و دستورالعمل داخلی مطالعات با کد WI150900، طرح‌های توسعه و "
    "اصلاح شبکه، تعیین محل نصب تجهیزات حفاظتی و مانوری و بررسی آثار آن‌ها بر "
    "بهره‌برداری باید بر پایه مطالعات فنی و مستندات قابل ردیابی انجام شوند. در این "
    "چارچوب، بررسی آرایش فیدر، مدل‌سازی شبکه و ارزیابی هماهنگی حفاظتی تجهیزات پیش از "
    "اجرا، از مراحل اصلی تصمیم‌گیری فنی به شمار می‌رود.")

# متن ثابت الزامات کلیدگذاری — عیناً از قالب (TAV122-02/00؛ بدون متغیر)
DX_SWITCHING_INTRO = (
    "مطابق دستورالعمل «مطالعات جایابی کلید در شبکه‌های توزیع» به شماره TAV122-02/00 "
    "توانیر، در تعیین نقاط مانور علاوه بر رعایت کلیه ضوابط و قیود دستورالعمل‌های "
    "مرتبط، باید موارد ذیل لحاظ گردد:")

DX_SWITCHING_RULES = (
    "در جایگذاری کلیدها، الزامات و فلسفه حفاظت شبکه توزیع برق طبق «دستورالعمل فنی "
    "حفاظت الکتریکی شبکه توزیع» تدوین شده در دفتر مهندسی و راهبری شرکت توانیر رعایت شود.",
    "هر فیدر شهری به فیدر پست‌های دیگر حداقل ۲ نقطه مانور داشته باشد.",
    "هر فیدر (روستایی) حداقل به اندازه ظرفیت یک فیدر خود با پست مجاور مانور داشته باشد.",
    "تعداد نقاط مانور کلیدهای بین دو فیدر (NO) از ۳ بیشتر نباشد. ایجاد نقاط NO باید "
    "با بررسی پیچیدگی بهره‌برداری و هماهنگی معاونت بهره‌برداری و دیسپاچینگ صورت گیرد.",
    "در ابتدای انشعابات طویل، یک کلید با قابلیت حفاظت قرار گیرد.",
    "ابتدا و انتهای هر یک از قسمت‌های فیدر با تعداد وقوع خطای بیش از ۳ در سال و یا "
    "مناطق صعب‌العبور با متوسط زمان دستیابی بیش از یک ساعت، کلید قرار گیرد.",
    "از قرار دادن کلیدها در مکان‌های صعب‌العبور و با دسترسی زمان‌بر جلوگیری شود.")

DX_SWITCHING_PARAMS = (
    "پارامترهای تأثیرگذار در جایابی کلید عبارتند از: وضعیت فعلی شبکه شامل آرایش، "
    "تعداد و نوع کلیدهای موجود در شبکه و توپولوژی شبکه، تأثیر پیاده‌سازی بستر "
    "اتوماسیون و کنترل از راه دور، منافع ناشی از بهبود قابلیت اطمینان، اولویت بارها "
    "از نظر قابلیت اطمینان، رشد بار و عدم قطعیت در بار پیش‌بینی شده، قیود بهره‌برداری "
    "و الزامات فنی شبکه و محدودیت‌های جغرافیایی محل احداث می‌باشد.")

# متدولوژی جایابی — عیناً از قالب
DX_METHODOLOGY = (
    "روش جایابی مورد استفاده در این مطالعه، استفاده از انرژی توزیع‌نشده فیدر می‌باشد "
    "که داده‌های مربوط به آن از سامانه خاموشی فیدرها اقتباس شده است. مقادیر مربوط به "
    "نرخ خرابی و زمان تعمیر نیز از داده‌های خاموشی برنامه‌ریزی‌نشده فیدر بدست آمده "
    "است. خلاصه روابط استفاده‌شده در این مطالعه در ادامه ارائه شده است.")

# روابط قالب (معادل متنی فرمول‌های LaTeX فایل فرمت)
DX_FORMULAS = (
    "λ = N_random / Y_covered ،   r = Σ t_restore / N_events   "
    "(نرخ خرابی و زمان تعمیر از ماتریس خاموشی واقعی)",
    "λ_i = λ_fid × (L_i / Σ L)   (توزیع λ بین قطعه‌ها متناسب با طول)",
    "s = min(t_restore, r)   (زمان بازیابی بار سالم)",
    "EENS = Σ_i (λ_i / 60) × [ r × P_i + s × min(P_down,i, C) + "
    "r × (P_down,i − min(P_down,i, C)) ]")


def _dx_intro_sec(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("dx_intro", "مقدمه")
    info = _dx_info(ctx)
    if info is None:
        return sec
    if (info.intro or "").strip():
        sec.blocks.extend(_fd_paras(info.intro))
        return sec
    sec.blocks.append(Paragraph(DX_INTRO_FIXED))
    feeder = _dx_feeder(ctx, info)
    loc = _dx(info.location)
    sec.blocks.append(Paragraph(
        f"موضوع این دفترچه، مطالعه احداث و نصب یک دستگاه سکسیونر {_dx(info.dx_kind)} "
        f"در موقعیت {loc}، از توابع شهرستان {_dx(info.county)} روی فیدر {feeder} "
        "می‌باشد. هدف از پیشنهاد این تجهیز، فراهم‌کردن امکان کنترل و مانور از راه دور، "
        "محدودسازی محدوده متأثر از خطا و تسهیل جداسازی بخش معیوب از سایر قسمت‌های "
        "شبکه است. میزان تحقق این اهداف به انتخاب محل مناسب، عملکرد صحیح تجهیز "
        f"وابسته خواهد بود. شکل ۱، موقعیت {feeder}، {loc}، محل سکسیونر درخواستی "
        "را نشان می‌دهد."))
    return sec


def _dx_network_sec(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("dx_network", "مشخصات شبکه")
    info = _dx_info(ctx)
    if info is None:
        return sec
    feeder, post = _dx_feeder(ctx, info), _dx_post(ctx, info)
    dg = (info.dg_status or "").strip() or "وضعیت منبع تولید پراکنده روی فیدر ثبت نشده است."
    if not dg.endswith((".", "۔", "؟", "!")):
        dg += "."
    sec.blocks.append(Paragraph(
        f"فیدر {feeder}، با سطح ولتاژ {_dx(info.voltage_kv)} کیلوولت از پست فوق توزیع "
        f"{post} مورد مطالعه قرار گرفته است. جریان بار فیدر {_dx(info.load_current_a)} "
        f"آمپر در نظر گرفته شده است. {dg}"))
    sec.blocks.append(TableSpec(
        caption=f"جدول {ctx.next_table()}: مشخصات فیدر مورد مطالعه",
        header_rows=[["فیدر", "پست", "ولتاژ (kV)", "جریان بار (A)",
                      "توان اکتیو (MW)", "توان راکتیو (MVar)"]],
        body_rows=[[feeder, post, _dx(info.voltage_kv), _dx(info.load_current_a),
                    _dx(info.active_power_mw), _dx(info.reactive_power_mvar)]]))
    return sec


def _dx_switching_sec(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("dx_switching", "الزامات کلیدگذاری")
    if _dx_info(ctx) is None:
        return sec
    sec.blocks.append(Paragraph(DX_SWITCHING_INTRO))
    for i, rule in enumerate(DX_SWITCHING_RULES, start=1):
        sec.blocks.append(Paragraph(f"{i}- {rule}", style="item"))
    sec.blocks.append(Paragraph(DX_SWITCHING_PARAMS))
    return sec


def _dx_placement_sec(ctx: ComposeContext) -> ReportSection:
    info = _dx_info(ctx)
    kind = "" if info is None else (info.dx_kind or "").strip()
    sec = ReportSection("dx_placement", f"جایابی سکسیونر {kind}".strip())
    if info is None:
        return sec
    feeder = _dx_feeder(ctx, info)
    sec.blocks.append(Paragraph(DX_METHODOLOGY))
    for formula in DX_FORMULAS:
        sec.blocks.append(Paragraph(formula, style="item"))
    # پارامترهای مؤثر فیدر (نرخ خرابی و زمان تعمیر)
    sec.blocks.append(Paragraph("پارامترهای مؤثر فیدر (نرخ خرابی و زمان تعمیر):"))
    for label, value in (
            ("شناسه فیدر", _dx(info.feeder_key)),
            ("نرخ خرابی (λ)", f"{_dx(info.failure_rate_per_year)} خرابی در سال"),
            ("زمان تعمیر (r)", f"{_dx(info.repair_time_min)} دقیقه"),
            ("نرخ خرابی گذرا", _dx(info.transient_rate_per_year))):
        sec.blocks.append(Paragraph(f"{label}: {value}", style="item"))
    # مشخصات فنی و نتایج بهینه‌سازی فیدر
    sec.blocks.append(Paragraph("مشخصات فنی و نتایج بهینه‌سازی فیدر:"))
    for label, value in (
            ("شناسه فیدر", _dx(info.feeder_key)),
            ("طول خط", f"{_dx(info.line_length_km)} کیلومتر"),
            ("بار تحت پوشش", f"{_dx(info.covered_load_kw)} کیلووات"),
            ("موقعیت و مشخصات تجهیز پیشنهادی",
             f"{_dx(info.device_note)} | مختصات: {_dx(info.device_coords)}")):
        sec.blocks.append(Paragraph(f"{label}: {value}", style="item"))
    # شاخص‌های قابلیت اطمینان
    sec.blocks.append(Paragraph("شاخص‌های قابلیت اطمینان:"))
    n_sw = _dx(info.switch_count)
    for label, value in (
            ("میزان انرژی توزیع‌نشده پایه",
             f"{_dx(info.eens_base_mwh)} مگاوات‌ساعت در سال"),
            ("تعداد کلید پیشنهادی", f"{n_sw} عدد"),
            ("میزان انرژی توزیع‌نشده پس از نصب",
             f"{_dx(info.eens_after_mwh)} مگاوات‌ساعت در سال"),
            ("درصد بهبود",
             f"{_dx(info.improvement_pct)}٪ کاهش در EENS "
             f"(با نصب {n_sw} دستگاه سکسیونر)")):
        sec.blocks.append(Paragraph(f"{label}: {value}", style="item"))
    sec.blocks.append(TableSpec(
        caption=(f"جدول {ctx.next_table()}: خلاصه نتیجه جایابی سکسیونر مبتنی بر "
                 f"محاسبه انرژی توزیع‌نشده {feeder}"),
        header_rows=[["فیدر", "طول (km)", "بار (kW)", "EENS پایه (MWh/سال)",
                      "EENS نهایی (MWh/سال)", "کاهش (%)"]],
        body_rows=[[feeder, _dx(info.line_length_km), _dx(info.covered_load_kw),
                    _dx(info.eens_base_mwh), _dx(info.eens_after_mwh),
                    _dx(info.improvement_pct)]]))
    sec.blocks.append(Paragraph(
        f"مطابق شکل 2، محل بهینه سکسیونر از نظر مینیمم‌کردن انرژی توزیع‌نشده، در "
        f"{_dx(info.optimal_location)} پیشنهاد شده است. این محل با محل درخواستی امور "
        f"{_dx_office(ctx)} نیز هم‌خوانی دارد."))
    if info.eens_imported:      # ردپای فایل جایابی — نتایج عیناً از خروجی SwitchLoc
        ver = (info.eens_algo_version or "").strip()
        sec.blocks.append(Paragraph(
            "نتایج جایابی این بخش عیناً از فایل خروجی نرم‌افزار جایابی کلید"
            + (f" ({ver})" if ver else "") + " — eens_report.json — وارد شده است."))
    return sec


def _dx_coverage_sec(ctx: ComposeContext) -> ReportSection:
    sec = ReportSection("dx_coverage",
                        "بررسی پوشش‌دهی شبکه‌های اینترنت شرکت‌های ایرانسل و همراه اول")
    info = _dx_info(ctx)
    if info is None:
        return sec
    requested = (info.requested_location or "").strip() or _dx(info.location)
    sec.blocks.append(Paragraph(
        f"طی درخواست امور محترم {_dx_office(ctx)}، یک دستگاه سکسیونر "
        f"{_dx(info.dx_kind)} در {requested} جهت افزایش قابلیت اطمینان شبکه و کاهش "
        "انرژی توزیع‌نشده و همچنین کاهش زمان عیب‌یابی شبکه درخواست شده است. با توجه "
        "به کنترل از راه دور بودن سکسیونر درخواستی، وضعیت پوشش‌دهی شبکه‌های ایرانسل "
        "و همراه اول در شکل‌های 3 و 4 نمایش داده شده است. مطابق شکل‌های مذکور، وضعیت "
        f"پوشش‌دهی اینترنت هر دو شرکت در منطقه مورد بررسی {_dx(info.coverage_status)} "
        "می‌باشد."))
    sec.blocks.append(TableSpec(
        caption=f"جدول {ctx.next_table()}: وضعیت پوشش اینترنت منطقه مورد مطالعه",
        header_rows=[["استان", "مناطق تحت پوشش: شهر / دهستان / روستا / جاده و ...",
                      "وضعیت پوشش اینترنت 3G / 4G / 4.5G"]],
        body_rows=[[_dx(info.province), _dx(info.coverage_areas),
                    _dx(info.coverage_status)]]))
    if (info.conclusion or "").strip():
        sec.blocks.extend(_fd_paras(info.conclusion))
    return sec


@dataclass
class ReportComponent:
    key: str
    title: str
    build: Callable[[ComposeContext], ReportSection]
    requires_kinds: Optional[set[StudyKind]] = None   # None = برای هر مطالعهٔ حفاظتی

    def applies(self, kinds: list[StudyKind]) -> bool:
        if self.requires_kinds is None:     # بخش عمومی حفاظتی — نه برای توسعه فیدر
            return any(k in PROTECTION_KINDS for k in kinds)
        return bool(self.requires_kinds & set(kinds))


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
    ReportComponent("prot_settings_sheet", "پیوست — برگه تنظیمات هماهنگی", _settings_sheet),
    # v2.4.0 — مطالعه «توسعه و اصلاح فیدر» (فقط در گزارش همین مطالعه ظاهر می‌شود)
    ReportComponent("fd_intro", "توسعه فیدر — مقدمه", _fd_intro, {StudyKind.FEEDER_DEV}),
    ReportComponent("fd_network", "توسعه فیدر — مشخصات شبکه و وضعیت موجود", _fd_network,
                    {StudyKind.FEEDER_DEV}),
    ReportComponent("fd_before", "توسعه فیدر — پخش بار قبل از اصلاح", _fd_before,
                    {StudyKind.FEEDER_DEV}),
    ReportComponent("fd_plan", "توسعه فیدر — راه‌حل پیشنهادی", _fd_plan,
                    {StudyKind.FEEDER_DEV}),
    ReportComponent("fd_after", "توسعه فیدر — پخش بار بعد از اصلاح", _fd_after,
                    {StudyKind.FEEDER_DEV}),
    ReportComponent("fd_conclusion", "توسعه فیدر — نتیجه‌گیری", _fd_conclusion,
                    {StudyKind.FEEDER_DEV}),
    # v2.6.0 — مطالعه «جایابی سکسیونر» (قالب Disconnector Format.json)
    ReportComponent("dx_intro", "جایابی سکسیونر — مقدمه", _dx_intro_sec,
                    {StudyKind.DISCONNECTOR}),
    ReportComponent("dx_network", "جایابی سکسیونر — مشخصات شبکه", _dx_network_sec,
                    {StudyKind.DISCONNECTOR}),
    ReportComponent("dx_switching", "جایابی سکسیونر — الزامات کلیدگذاری", _dx_switching_sec,
                    {StudyKind.DISCONNECTOR}),
    ReportComponent("dx_placement", "جایابی سکسیونر — جایابی بر اساس EENS", _dx_placement_sec,
                    {StudyKind.DISCONNECTOR}),
    ReportComponent("dx_coverage", "جایابی سکسیونر — پوشش اینترنت", _dx_coverage_sec,
                    {StudyKind.DISCONNECTOR}),
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
        kinds = [k for k in kinds
                 if k in PROTECTION_KINDS
                 or k in (StudyKind.FEEDER_DEV, StudyKind.DISCONNECTOR)]
        prot_kinds = [k for k in kinds if k in PROTECTION_KINDS]
        ctx = ComposeContext(project, workspace, kinds, narrative=self.narrative,
                             charts_dir=charts_dir)
        # قواعد و متن حفاظتی فقط برای مطالعات حفاظتی اجرا می‌شوند (نه توسعه فیدر)
        ctx.results = self.analyse(project, workspace, prot_kinds, thresholds)
        ctx.vars = self.narrative.build_vars(project, workspace, prot_kinds, ctx.results)
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
            if not sec.blocks:          # بخش بدون هیچ متن/جدول/شکلی درج نمی‌شود
                continue
            sections.append(sec)
        apply_manual_texts(project, sections)
        number_figures(sections)              # شماره‌گذاری سراسری شکل‌ها مانند جدول‌ها
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
