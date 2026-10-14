# -*- coding: utf-8 -*-
"""بخش‌های گزارش مطالعه مصارف سنگین — «تغییرات آرنا» v1.1.0.

ساختار بخش‌ها از دفترچه مطالعات مصارف سنگین (TAV111-10/00) پیروی می‌کند:

    ۱) اطلاعات تقاضا                       (جدول صفحه ۲ دفترچه)
    ۲) ایستگاه‌های نزدیک به محل تقاضا        (جدول صفحه ۲ دفترچه)
    ۳) خطوط نزدیک به محل تقاضا              (جدول صفحه ۳ دفترچه)
    ۴) متقاضیان و تقاضاهای همزمان محدوده
    ۵) نکات تحلیلی و کنترل کیفیت Ruleها     (صفحه ۴ دفترچه)
    ۶) سناریوهای پیشنهادی تأمین برق          (صفحه ۴ دفترچه)
    ۷) بررسی اقتصادی سناریوها                (صفحه ۴ دفترچه)

هر Finding فقط از خروجی استاندارد Rule Engine ساخته می‌شود و متن نهایی تنها زمانی
درج می‌گردد که داده‌های لازم معتبر باشند؛ در غیر این صورت وضعیت
MISSING_DATA / MISSING_RULE / DATA_ERROR / REQUIRES_ENGINEER_REVIEW ثبت می‌شود.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from app.core.models import Project, SupplyScenario
from app.core.settings import AppSettings
from app.core.study import cost_estimate
from app.report.sections import ReportSection, Paragraph, TableSpec
from app.report.template_manager import TemplateManager
from app.rules.outcome import (RuleResult, STATUS_LABELS_FA,
                               render_template as _render)
from app.utils.formatting import fmt

MISSING_DATA_LABEL = "MISSING_DATA"
MISSING_RULE_LABEL = "MISSING_RULE"

SECTION_DEMAND = "study_demand"
SECTION_SUBSTATIONS = "study_substations"
SECTION_LINES = "study_lines"
SECTION_COINCIDENT = "study_coincident"
SECTION_LOADING = "study_loading"
SECTION_ANALYSIS = "study_analysis"
SECTION_SCENARIOS = "study_scenarios"
SECTION_ECONOMICS = "study_economics"
SECTION_CONCLUSION = "study_conclusion"


class StudySections:
    """سازنده بخش‌های مطالعه — مشترک بین Preview و Word Generator."""

    def __init__(self, project: Project, settings: AppSettings,
                 texts: TemplateManager, results: list[RuleResult],
                 next_tbl: Callable[[], int],
                 emit: Callable[..., None]) -> None:
        self.project = project
        self.settings = settings
        self.texts = texts
        self.results = results
        self.next_tbl = next_tbl
        self.emit = emit
        self.by_domain: dict[str, list[RuleResult]] = {}
        for r in results:
            self.by_domain.setdefault(r.category, []).append(r)

    # ------------------------------------------------------------------
    def t(self, text_id: str, values: Optional[dict[str, Any]] = None,
          default: str = "") -> str:
        """رندر از کتابخانه متن؛ در نبود کلید (قالب کاربر قدیمی) از پیش‌فرض داخلی."""
        values = values or {}
        text = self.texts.render(text_id, {k: v for k, v in values.items()})
        return text or _render(default, values)

    def _results(self, *domains: str) -> list[RuleResult]:
        out: list[RuleResult] = []
        for d in domains:
            out.extend(self.by_domain.get(d, []))
        return out

    def _emit_all(self, sec: ReportSection, results: list[RuleResult],
                  owner_key_of: Optional[Callable[[RuleResult], str]] = None) -> None:
        for r in results:
            key = owner_key_of(r) if owner_key_of else ""
            self.emit(sec, r, key)

    def _has_data(self) -> bool:
        p = self.project
        return bool(p.demand.without_coincidence_kw is not None
                    or p.demand.with_coincidence_kw is not None
                    or p.nearby_substations or p.nearby_lines
                    or p.coincident_demands or p.scenarios)

    # ------------------------------------------------------------------
    def build_all(self) -> list[ReportSection]:
        from app.core.study import has_study_data
        if not has_study_data(self.project):
            return []
        out: list[ReportSection] = []
        for builder in (self.build_demand, self.build_substations, self.build_lines,
                        self.build_coincident, self.build_feeder_loading,
                        self.build_analysis, self.build_scenarios,
                        self.build_economics, self.build_conclusions):
            sec = builder()                       # type: ignore[operator]
            if sec is not None and self.settings.section_enabled(sec.key):
                out.append(sec)
        return out

    # ------------------------------------------------------------------
    # ۱) اطلاعات تقاضا
    # ------------------------------------------------------------------
    def build_demand(self) -> Optional[ReportSection]:
        results = self._results("study_demand")
        d = self.project.demand
        if not getattr(d, "enabled", True):
            return None                       # کلید On/Off اطلاعات تقاضا
        if not results and d.with_coincidence_kw is None and d.without_coincidence_kw is None:
            return None
        sec = ReportSection(SECTION_DEMAND, self.t(
            "T-STUDY-DEMAND-TITLE", default="اطلاعات تقاضا"))
        sec.blocks.append(Paragraph(self.t(
            "T-STUDY-DEMAND-INTRO",
            {"APPLICANT": self.project.applicant_name or "—"},
            default="اطلاعات تقاضای متقاضی «{APPLICANT}» به‌شرح جدول زیر است.")))
        n = self.next_tbl()
        sec.blocks.append(TableSpec(
            caption=self.t("T-CAP-DEMAND-TABLE", {"N": str(n)},
                           default="جدول {N}: اطلاعات تقاضا"),
            header_rows=[[self.t("T-HDR-ITEM", default="اطلاعات"),
                          self.t("T-HDR-VALUE-KW", default="مقدار (kW)")]],
            body_rows=[
                [self.t("T-ROW-DEMAND-WITH", default="میزان تقاضا با ضریب همزمانی"),
                 fmt(d.with_coincidence_kw, 0)],
                [self.t("T-ROW-DEMAND-WITHOUT", default="میزان تقاضا بدون ضریب همزمانی"),
                 fmt(d.without_coincidence_kw, 0)],
                [self.t("T-ROW-EXISTING-DEMAND", default="میزان دیماند موجود"),
                 fmt(d.existing_demand_kw, 0)],
            ]))
        self._emit_all(sec, results)
        return sec

    # ------------------------------------------------------------------
    # ۲) ایستگاه‌های نزدیک به محل تقاضا
    # ------------------------------------------------------------------
    def build_substations(self) -> Optional[ReportSection]:
        stations = self.project.active_substations
        results = self._results("study_substation")
        if not stations and not results:
            return None
        sec = ReportSection(SECTION_SUBSTATIONS, self.t(
            "T-STUDY-SUBSTATION-TITLE", default="ایستگاه‌های نزدیک به محل تقاضا"))
        sec.blocks.append(Paragraph(self.t(
            "T-STUDY-SUBSTATION-INTRO", {},
            default="مشخصات ایستگاه‌های نزدیک به محل تقاضا (فاصله، ظرفیت، بارگیری "
                    "ترانس‌ها و تعداد فیدر) به‌شرح جدول زیر است.")))
        if stations:
            names = [s.display_name for s in stations]
            rows = [
                ([self.t("T-ROW-SS-DISTANCE", default="فاصله تقریبی تا محل تقاضا (km)")],
                 [fmt(s.distance_km, 2) for s in stations]),
                ([self.t("T-ROW-SS-CAPACITY", default="ظرفیت ایستگاه (MVA)")],
                 [fmt(s.transformer_capacity_mva, 2) for s in stations]),
                ([self.t("T-ROW-SS-T1-LOAD",
                         {"YEAR": str(self._peak_year(stations))},
                         default="درصد بارگیری ترانس T1 در پیک بار {YEAR}")],
                 [self._pct(s.t1_loading_percent) for s in stations]),
                ([self.t("T-ROW-SS-T2-LOAD",
                         {"YEAR": str(self._peak_year(stations))},
                         default="درصد بارگیری ترانس T2 در پیک بار {YEAR}")],
                 [self._pct(s.t2_loading_percent) for s in stations]),
                ([self.t("T-ROW-SS-T1-PEAK",
                         {"YEAR": str(self._peak_year(stations))},
                         default="میزان بارگیری ترانس T1 در پیک بار {YEAR} (MVA)")],
                 [fmt(s.t1_peak_mva, 2) for s in stations]),
                ([self.t("T-ROW-SS-T2-PEAK",
                         {"YEAR": str(self._peak_year(stations))},
                         default="میزان بارگیری ترانس T2 در پیک بار {YEAR} (MVA)")],
                 [fmt(s.t2_peak_mva, 2) for s in stations]),
                ([self.t("T-ROW-SS-FEEDERS", default="تعداد فیدر برقرار")],
                 [fmt(s.feeder_count, 0) for s in stations]),
            ]
            n = self.next_tbl()
            sec.blocks.append(TableSpec(
                caption=self.t("T-CAP-SUBSTATION-TABLE", {"N": str(n)},
                               default="جدول {N}: ایستگاه‌های نزدیک به محل تقاضا"),
                header_rows=[[self.t("T-HDR-SS-NAME-INFO", default="نام ایستگاه / اطلاعات")] + names],
                body_rows=[[label[0]] + values for label, values in rows]))
        self._emit_all(sec, results, owner_key_of=lambda r: f"ss:{self._uid(r.owner)}")
        return sec

    # ------------------------------------------------------------------
    # ۳) خطوط نزدیک به محل تقاضا
    # ------------------------------------------------------------------
    def build_lines(self) -> Optional[ReportSection]:
        lines = self.project.active_lines
        results = self._results("study_line")
        if not lines and not results:
            return None
        sec = ReportSection(SECTION_LINES, self.t(
            "T-STUDY-LINE-TITLE", default="خطوط نزدیک به محل تقاضا"))
        sec.blocks.append(Paragraph(self.t(
            "T-STUDY-LINE-INTRO", {},
            default="مقایسه وضعیت خطوط نزدیک به محل تقاضا، پیش و پس از اتصال بار "
                    "جدید بر اساس پیک بار گزارش‌شده، در جدول زیر ارائه می‌شود.")))
        if lines:
            names = [l.display_name for l in lines]
            year = str(self._peak_year(lines))
            rows = [
                ([self.t("T-ROW-LN-DISTANCE", default="فاصله تقریبی تا محل تقاضا (m)")],
                 [fmt(l.distance_m, 0) for l in lines]),
                ([self.t("T-ROW-LN-PEAK-ALL", {"YEAR": year},
                         default="پیک بار خط در سال {YEAR}")],
                 [self._line_peak_cell(l) for l in lines]),
                ([self.t("T-ROW-LN-VDROP-BEFORE", {"YEAR": year},
                         default="افت ولتاژ انتهای خط قبل از اتصال بار جدید "
                                 "بر اساس پیک بار {YEAR}")],
                 [self._pct(l.vdrop_before_percent, 2) for l in lines]),
                ([self.t("T-ROW-LN-VDROP-AFTER", {"YEAR": year},
                         default="افت ولتاژ انتهای خط بعد از اتصال بار جدید "
                                 "بر اساس پیک بار {YEAR}")],
                 [self._pct(l.vdrop_after_percent, 2) for l in lines]),
                ([self.t("T-ROW-LN-DELTA",
                         default="تغییر افت ولتاژ ناشی از بار جدید (واحد درصد)")],
                 [self._delta_txt(l.vdrop_after_percent, l.vdrop_before_percent) for l in lines]),
                ([self.t("T-ROW-LN-SC-MAX", default="حداکثر جریان اتصال کوتاه (kA)")],
                 [fmt(l.sc_max_ka, 3) for l in lines]),
                ([self.t("T-ROW-LN-SC-MIN", default="حداقل جریان اتصال کوتاه (kA)")],
                 [fmt(l.sc_min_ka, 3) for l in lines]),
            ]
            n = self.next_tbl()
            sec.blocks.append(TableSpec(
                caption=self.t("T-CAP-LINE-TABLE", {"N": str(n)},
                               default="جدول {N}: خطوط نزدیک به محل تقاضا"),
                header_rows=[[self.t("T-HDR-LN-NAME-INFO", default="نام خط / اطلاعات")] + names],
                body_rows=[[label[0]] + values for label, values in rows]))
        self._emit_all(sec, results, owner_key_of=lambda r: f"ln:{self._uid(r.owner)}")
        return sec

    # ------------------------------------------------------------------
    # ۴) متقاضیان و تقاضاهای همزمان
    # ------------------------------------------------------------------
    def build_coincident(self) -> Optional[ReportSection]:
        rows = self.project.active_coincident_demands
        results = self._results("study_coincidence")
        if not rows and not results:
            return None
        sec = ReportSection(SECTION_COINCIDENT, self.t(
            "T-STUDY-COINCIDENT-TITLE", default="متقاضیان و تقاضاهای همزمان محدوده"))
        if rows:
            body = []
            for c in rows:
                body.append([
                    c.name or "—",
                    fmt(c.existing_or_requested_power_kw, 0),
                    fmt(c.new_requested_power_kw, 0),
                    fmt(c.computed_delta_kw(), 0),
                    c.location or "—",
                    c.supply_feasibility or "—",
                ])
            n = self.next_tbl()
            sec.blocks.append(TableSpec(
                caption=self.t("T-CAP-COINCIDENT-TABLE", {"N": str(n)},
                               default="جدول {N}: متقاضیان و تقاضاهای همزمان محدوده مطالعاتی"),
                header_rows=[[self.t("T-HDR-CD-NAME", default="نام متقاضی"),
                              self.t("T-HDR-CD-EXISTING", default="توان موجود/درخواستی (kW)"),
                              self.t("T-HDR-CD-NEW", default="توان جدید (kW)"),
                              self.t("T-HDR-CD-DELTA", default="افزایش بار (kW)"),
                              self.t("T-HDR-CD-LOCATION", default="محل"),
                              self.t("T-HDR-CD-FEASIBILITY", default="امکان تأمین")]],
                body_rows=body))
        self._emit_all(sec, results)
        return sec

    # ------------------------------------------------------------------
    # ۴-۲) بارگذاری فیدر و راهکارهای تعدیل بار (v1.2.0)
    # ------------------------------------------------------------------
    def build_feeder_loading(self) -> Optional[ReportSection]:
        """کنترل «پیک فیدر + بار اضافه‌شدهٔ متقاضی» در برابر آستانه‌های مصوب کارفرما."""
        from app.core.study import feeder_loading_contexts
        results = self._results("study_loading")
        feeders = list(self.project.active_feeders)
        if not feeders and not results:
            return None
        sec = ReportSection(SECTION_LOADING, self.t(
            "T-STUDY-LOADING-TITLE",
            default="کنترل بارگذاری فیدر و راهکارهای تعدیل بار"))
        sec.blocks.append(Paragraph(self.t(
            "T-STUDY-LOADING-INTRO", {},
            default="بارگذاری کل هر فیدر برابر «پیک بار فیدر + بار اضافه‌شدهٔ جدید متقاضی» "
                    "محاسبه و با آستانه‌های مصوب (بارگذاری بحرانی و شدیداً بحرانی) مقایسه "
                    "می‌شود. در صورت عبور از آستانه، راهکارهای تعدیل بار شامل بازآرایی فیدر "
                    "با فیدر همجوار نزدیک ثبت‌شده و در صورت لزوم احداث فیدر جدید پیشنهاد "
                    "می‌گردد؛ انتخاب راهکار نهایی با مهندس است.")))

        if feeders:
            th = self.settings.study
            crit_txt = fmt(th.feeder_loading_critical_mw, 2) if th.feeder_loading_critical_mw is not None else MISSING_RULE_LABEL
            sev_txt = fmt(th.feeder_loading_severe_mw, 2) if th.feeder_loading_severe_mw is not None else MISSING_RULE_LABEL
            ctxs = feeder_loading_contexts(self.project, self.settings)
            n = self.next_tbl()
            rows: list[list[str]] = []
            for ctx in ctxs:
                if not ctx.get("has_feeder_total_load"):
                    status = MISSING_DATA_LABEL
                elif ctx.get("feeder_total_ge_severe"):
                    status = self.t("T-STUDY-LOADING-SEVERE", default="شدیداً بحرانی")
                elif ctx.get("feeder_total_ge_critical"):
                    status = self.t("T-STUDY-LOADING-CRITICAL", default="بحرانی")
                else:
                    status = self.t("T-STUDY-LOADING-OK", default="زیر آستانه")
                measure = "—"
                if ctx.get("has_rearrange_candidate") and (ctx.get("feeder_total_ge_critical")
                                                           or ctx.get("feeder_total_ge_severe")):
                    measure = self.t("T-STUDY-LOADING-REARRANGE", {
                        "NAME": ctx.get("rearrange_feeder_name"),
                        "MW": fmt(ctx.get("transfer_proposed_mw"), 3)},
                        default="بازآرایی: انتقال حدود {MW} مگاوات به فیدر همجوار {NAME} "
                                "(در صورت عدم کفایت: احداث فیدر جدید)")
                elif ctx.get("feeder_total_ge_critical") or ctx.get("feeder_total_ge_severe"):
                    measure = self.t("T-STUDY-LOADING-NEW-FEEDER", {},
                                     default="احداث فیدر جدید / تقویت فیدر "
                                             "(فیدر همجوار در ورودی‌ها ثبت نشده است)")
                rows.append([
                    str(ctx.get("feeder_name") or "—"),
                    fmt(ctx.get("feeder_peak_load_mw"), 3),
                    fmt(ctx.get("added_load_mw"), 3),
                    fmt(ctx.get("feeder_total_load_mw"), 3),
                    f"{crit_txt} / {sev_txt}",
                    status,
                    measure,
                ])
            sec.blocks.append(TableSpec(
                caption=self.t("T-CAP-LOADING-TABLE", {"N": str(n)},
                               default="جدول {N}: کنترل بارگذاری کل فیدر و راهکار پیشنهادی"),
                header_rows=[[
                    self.t("T-HDR-LD-FEEDER", default="فیدر"),
                    self.t("T-HDR-LD-PEAK", default="پیک فیدر (MW)"),
                    self.t("T-HDR-LD-ADDED", default="بار اضافه‌شده (MW)"),
                    self.t("T-HDR-LD-TOTAL", default="بار کل (MW)"),
                    self.t("T-HDR-LD-THRESHOLD", default="آستانهٔ بحرانی/شدید (MW)"),
                    self.t("T-HDR-LD-STATUS", default="وضعیت بارگذاری"),
                    self.t("T-HDR-LD-MEASURE", default="راهکار پیشنهادی (تعدیل بار)"),
                ]],
                body_rows=rows))
        self._emit_all(sec, results)
        return sec

    # ------------------------------------------------------------------
    # ۵) نکات تحلیلی + کنترل کیفیت Ruleها
    # ------------------------------------------------------------------
    def build_analysis(self) -> Optional[ReportSection]:
        results = self._results("study_topology", "study_crosscheck", "study_rearrange")
        if not results:
            return None
        sec = ReportSection(SECTION_ANALYSIS, self.t(
            "T-STUDY-ANALYSIS-TITLE", default="نکات تحلیلی مطالعات تأمین برق"))
        sec.blocks.append(Paragraph(self.t(
            "T-STUDY-ANALYSIS-INTRO", {},
            default="نکات زیر حاصل اجرای Ruleهای تحلیلی مطالعه است؛ هر مورد شامل "
                    "ورودی، محاسبه، قاعده، یافته، شاهد و منبع است و قابل ردیابی می‌باشد.")))
        self._emit_all(sec, results)
        # جدول کنترل کیفیت: وضعیت همه Ruleهای مطالعه
        if self.results:
            n = self.next_tbl()
            body = [[r.rule_id, r.category, STATUS_LABELS_FA.get(r.status, r.status),
                     r.owner or "—", (r.finding or "—")[:180]] for r in self.results]
            sec.blocks.append(TableSpec(
                caption=self.t("T-CAP-RULE-QUALITY-TABLE", {"N": str(n)},
                               default="جدول {N}: کنترل کیفیت Ruleها و وضعیت هر نتیجه"),
                header_rows=[[self.t("T-HDR-RQ-ID", default="Rule ID"),
                              self.t("T-HDR-RQ-DOMAIN", default="حوزه"),
                              self.t("T-HDR-RQ-STATUS", default="وضعیت"),
                              self.t("T-HDR-RQ-OWNER", default="مورد"),
                              self.t("T-HDR-RQ-FINDING", default="یافته")]],
                body_rows=body))
        return sec

    # ------------------------------------------------------------------
    # ۶) سناریوهای پیشنهادی تأمین
    # ------------------------------------------------------------------
    def build_scenarios(self) -> Optional[ReportSection]:
        rows = self.project.active_scenarios
        results = self._results("study_scenario")
        if not rows and not results:
            return None
        sec = ReportSection(SECTION_SCENARIOS, self.t(
            "T-STUDY-SCENARIO-TITLE", default="سناریوهای پیشنهادی تأمین برق"))
        if rows:
            cols = [s.display_title for s in rows]
            metrics = [
                (self.t("T-ROW-SC-KIND", default="نوع سناریو"), [s.kind_label for s in rows]),
                (self.t("T-ROW-SC-BASIS", default="مبنای فنی (Technical Basis)"),
                 [s.technical_basis or MISSING_DATA_LABEL for s in rows]),
                (self.t("T-ROW-SC-CHANGES", default="تغییرات لازم شبکه"),
                 [s.required_network_changes or MISSING_DATA_LABEL for s in rows]),
                (self.t("T-ROW-SC-FEEDER", default="فیدر نامزد (Candidate Feeder)"),
                 [s.candidate_feeder or MISSING_DATA_LABEL for s in rows]),
                (self.t("T-ROW-SC-EQUIP", default="تجهیزات موردنیاز"),
                 ["، ".join(s.required_equipment) or MISSING_DATA_LABEL for s in rows]),
                (self.t("T-ROW-SC-EVIDENCE", default="شاهد پشتیبان (Supporting Evidence)"),
                 [s.evidence or MISSING_DATA_LABEL for s in rows]),
                (self.t("T-ROW-SC-COST", default="هزینه (میلیون تومان)"),
                 [fmt(s.estimated_cost_million, 0) if s.estimated_cost_million is not None
                  else MISSING_DATA_LABEL for s in rows]),
                (self.t("T-ROW-SC-REVIEW", default="وضعیت بازبینی (Review Status)"),
                 [self.t(f"T-REVIEW-{s.review_status}", default=s.review_status) for s in rows]),
            ]
            n = self.next_tbl()
            sec.blocks.append(TableSpec(
                caption=self.t("T-CAP-SCENARIO-TABLE", {"N": str(n)},
                               default="جدول {N}: سناریوهای تأمین برق"),
                header_rows=[[self.t("T-HDR-ITEM", default="اطلاعات")] + cols],
                body_rows=[[label] + values for label, values in metrics]))
        self._emit_all(sec, results)
        return sec

    # ------------------------------------------------------------------
    # ۷) بررسی اقتصادی سناریوها
    # ------------------------------------------------------------------
    def build_economics(self) -> Optional[ReportSection]:
        rows = self.project.active_scenarios
        results = self._results("study_economics")
        if not rows and not results:
            return None
        sec = ReportSection(SECTION_ECONOMICS, self.t(
            "T-STUDY-ECONOMICS-TITLE", default="بررسی اقتصادی سناریوها"))
        sec.blocks.append(Paragraph(self.t(
            "T-STUDY-ECONOMICS-INTRO", {},
            default="هزینه هر سناریو جداگانه ثبت و نمایش داده می‌شود. در نبود داده هزینه، "
                    "مقدار «" + MISSING_DATA_LABEL + "» درج می‌گردد و هیچ مقدار صفر یا "
                    "جایگزینی ساخته نمی‌شود.")))
        if rows:
            estimates = [cost_estimate(s, self.project, self.settings) for s in rows]
            cols = [s.display_title for s in rows]

            def col_vals(getter) -> list[str]:
                return [getter(s, e) for s, e in zip(rows, estimates)]

            metrics = [
                (self.t("T-ROW-EC-LENGTH", default="طول شبکه موردنیاز (km)"),
                 col_vals(lambda s, e: fmt(s.required_line_length_km, 2))),
                (self.t("T-ROW-EC-OH", default="درصد خط هوایی"),
                 col_vals(lambda s, e: self._pct(s.overhead_percent, 0))),
                (self.t("T-ROW-EC-UG", default="درصد خط زمینی"),
                 col_vals(lambda s, e: self._pct(s.underground_percent, 0))),
                (self.t("T-ROW-EC-COST-ITEMS", default="اقلام هزینه ثبت‌شده"),
                 col_vals(lambda s, e: "، ".join(f"{k}: {fmt(v, 0)}"
                                                 for k, v in (s.cost_items or {}).items()
                                                 if v is not None) or MISSING_DATA_LABEL)),
                (self.t("T-ROW-EC-GROUND", default="هزینه پست زمینی"),
                 col_vals(lambda s, e: fmt(self.settings.costs.ground_substation_million, 0))),
                (self.t("T-ROW-EC-SWITCH", default="هزینه تجهیزات کلیدزنی/حفاظتی"),
                 col_vals(lambda s, e: self._switch_cost_txt())),
                (self.t("T-ROW-EC-EXCLUDED", default="اقلام خارج از برآورد"),
                 col_vals(lambda s, e: "، ".join(s.cost_excluded_items) or "—")),
                (self.t("T-ROW-EC-COST", default="هزینه ثبت‌شده سناریو (میلیون تومان)"),
                 col_vals(lambda s, e: fmt(s.estimated_cost_million, 0)
                          if s.estimated_cost_million is not None else MISSING_DATA_LABEL)),
                (self.t("T-ROW-EC-ESTIMATE", default="برآورد پارامتریک (میلیون تومان)"),
                 col_vals(lambda s, e: fmt(e["estimated_total"], 0)
                          if e["estimated_total"] is not None else MISSING_DATA_LABEL)),
                (self.t("T-ROW-EC-MISSING", default="اقلام/پارامترهای ناموجود"),
                 col_vals(lambda s, e: "، ".join(e["missing_items"]) or "—")),
            ]
            n = self.next_tbl()
            sec.blocks.append(TableSpec(
                caption=self.t("T-CAP-COST-TABLE", {"N": str(n)},
                               default="جدول {N}: بررسی اقتصادی سناریوها"),
                header_rows=[[self.t("T-HDR-ITEM", default="اطلاعات")] + cols],
                body_rows=[[label] + values for label, values in metrics]))
        self._emit_all(sec, results,
                       owner_key_of=lambda r: f"scenario:{self._scenario_kind(r.owner)}")
        return sec

    # ------------------------------------------------------------------
    # ۸) نتیجه‌گیری و پیشنهادات — جدول سه‌ردیفی مطابق صفحه ۴ دفترچه
    #    (نکات تحلیلی / سناریوهای پیشنهادی / بررسی اقتصادی سناریوها)
    # ------------------------------------------------------------------
    def build_conclusions(self) -> Optional[ReportSection]:
        if not self.project.active_scenarios and not self.results:
            return None
        sec = ReportSection(SECTION_CONCLUSION, self.t(
            "T-STUDY-CONCLUSION-TITLE", default="نتیجه‌گیری و پیشنهادات"))
        spec = TableSpec(
            caption="",                      # عنوان داخل جدول است، نه بالای آن
            header_rows=[[self.t("T-STUDY-CONCLUSION-TITLE",
                                 default="نتیجه‌گیری و پیشنهادات")]],
            body_rows=[
                [self.t("T-ROW-CONC-NOTES", default="نکات تحلیلی"),
                 self._conclusion_notes()],
                [self.t("T-ROW-CONC-SCENARIOS", default="سناریوهای پیشنهادی"),
                 self._conclusion_scenarios()],
                [self.t("T-ROW-CONC-ECON", default="بررسی اقتصادی سناریوها")
                 + self._costs_exclusion_note(), self._conclusion_economics()],
            ],
            merges=[(0, 0, 1)],
        )
        sec.blocks.append(spec)
        return sec

    def _conclusion_notes(self) -> str:
        """نکات تحلیلی — از خروجی Ruleها (بدون تولید متن حدسی)."""
        keys = ("CD-LIST", "CD-TOTAL-LOAD", "TP-SHARED-SUPPLY-REVIEW",
                "TP-SHARED-SUPPLY-EVIDENCED",
                "XC-LOAD-SUM-MISMATCH", "XC-DEMAND-BASE-MISMATCH",
                "DATA_INCONSISTENCY", "D-COINCIDENCE-NOT-APPLIED",
                "SC-NO-SELECTION-CRITERION",
                # v1.2.0 — بارگذاری فیدر و راهکارهای تعدیل بار
                "LD-SEVERE", "LD-CRITICAL", "LD-REARRANGE-PROPOSAL",
                "LD-REARRANGE-NO-CANDIDATE")
        lines: list[str] = []
        picked: set[str] = set()

        def _add(text: str) -> None:
            if text and text.strip():
                lines.append(f"{self._fa(len(lines) + 1)}- {text.strip()}")

        for key in keys:
            for r in self.results:
                if (r.rule_key or r.rule_id) == key and key not in picked:
                    _add(r.finding)
                    picked.add(key)
                    break
        # سهم متقاضی از افت ولتاژ هر خط (Delta = After − Before)
        for r in self.results:
            if (r.rule_key or r.rule_id) == "LN-DELTA-CALC":
                _add(r.finding)
        for r in self.results:                      # هزینه صفر بدون مبنا و مانند آن
            if r.status in ("DATA_ERROR",) and (r.rule_key or r.rule_id) not in picked:
                _add(r.finding)
                picked.add(r.rule_key or r.rule_id)
        if not lines:
            return MISSING_DATA_LABEL
        return "\n".join(lines)

    def _conclusion_scenarios(self) -> str:
        """سناریوهای پیشنهادی — متن هر سناریو عیناً از Rule Engine (بدون توصیه)."""
        if not self.project.active_scenarios:
            return MISSING_DATA_LABEL
        lines: list[str] = []
        for s in self.project.active_scenarios:
            basis = s.technical_basis or MISSING_DATA_LABEL
            candidate = s.candidate_feeder or MISSING_DATA_LABEL
            lines.append(f"{self._fa(len(lines) + 1)}- {s.title or s.kind_label}: {basis} "
                         f"فیدر نامزد: {candidate}.")
        if not (self.project.scenario_selection_criterion or "").strip():
            lines.append("توجه: انتخاب بین سناریوها توسط مهندس مطالعات انجام می‌شود؛ "
                         "معیار انتخاب سناریو در Rule Set تعریف نشده است.")
        return "\n".join(lines)

    def _costs_exclusion_note(self) -> str:
        """عبارت داخل پرانتز تصویر: اقلام خارج از برآورد هزینه."""
        excluded: list[str] = []
        for s in self.project.active_scenarios:
            for item in s.cost_excluded_items:
                if item not in excluded:
                    excluded.append(item)
        if not excluded:
            return ""
        return " (بدون در نظر گرفتن " + " و ".join(excluded) + " به میلیون تومان)"

    def _conclusion_economics(self) -> str:
        """بررسی اقتصادی سناریوها — هزینه ثبت‌شده یا برآورد پارامتریک یا MISSING_DATA."""
        if not self.project.active_scenarios:
            return MISSING_DATA_LABEL
        lines: list[str] = []
        n = 0
        for s in self.project.active_scenarios:
            est = cost_estimate(s, self.project, self.settings)
            route = ""
            if s.required_line_length_km is not None:
                route = (f" (طول شبکه {fmt(s.required_line_length_km, 2)} کیلومتر"
                         f"{'، ' + fmt(s.overhead_percent, 0) + '٪ هوایی' if s.overhead_percent is not None else ''}"
                         f"{' و ' + fmt(s.underground_percent, 0) + '٪ زمینی' if s.underground_percent is not None else ''})")
            if s.estimated_cost_million is not None:
                cost = f"{fmt(s.estimated_cost_million, 0)} میلیون تومان"
            elif est["estimated_total"] is not None:
                cost = (f"برآورد پارامتریک {fmt(est['estimated_total'], 0)} میلیون تومان "
                        f"برای اقلام قابل‌محاسبه؛ {MISSING_DATA_LABEL} برای "
                        + "، ".join(est["missing_items"]))
            else:
                cost = MISSING_DATA_LABEL
            n += 1
            lines.append(f"{self._fa(n)}- هزینه {s.title or s.kind_label}: {cost}{route}.")
            if s.cost_excluded_items:
                lines.append(f"   در برآورد هزینه {s.title or s.kind_label}، اقلام "
                             + "، ".join(s.cost_excluded_items)
                             + f" لحاظ نشده است ({MISSING_DATA_LABEL}).")
        return "\n".join(lines)

    @staticmethod
    def _fa(n: int) -> str:
        """عدد با ارقام فارسی برای شماره‌گذاری بندهای نتیجه‌گیری."""
        return str(n).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

    # ------------------------------------------------------------------
    # ابزارها
    # ------------------------------------------------------------------
    @staticmethod
    def _peak_year(items) -> object:
        years = [getattr(x, "peak_year", None) for x in items]
        years = [y for y in years if y]
        return max(years) if years else "—"

    @staticmethod
    def _line_peak_cell(l) -> str:
        """خانه «پیک بار خط در سال …» — مطابق تصویر: MVA / MW / A در یک خانه."""
        parts = []
        if l.peak_mva is not None:
            parts.append(f"{fmt(l.peak_mva, 2)} MVA")
        if l.peak_mw is not None:
            parts.append(f"{fmt(l.peak_mw, 2)} MW")
        if l.peak_current_a is not None:
            parts.append(f"{fmt(l.peak_current_a, 1)} A")
        return "\n".join(parts) if parts else "—"

    def _switch_cost_txt(self) -> str:
        c = self.settings.costs
        parts = [fmt(x, 0) for x in (c.switchgear_million, c.protection_million,
                                     c.other_equipment_million) if x is not None]
        return " / ".join(parts) if parts else MISSING_DATA_LABEL

    @staticmethod
    def _pct(value: Optional[float], digits: int = 2) -> str:
        return f"{fmt(value, digits)}٪" if value is not None else "—"

    @staticmethod
    def _delta_txt(after: Optional[float], before: Optional[float]) -> str:
        if after is None or before is None:
            return "—"
        d = after - before
        return f"{d:+.2f}"

    def _uid(self, owner: str) -> str:
        """شناسه پایدار برای کلید Finding (نام → uid در صورت وجود)."""
        for coll in (self.project.active_substations, self.project.active_lines):
            for item in coll:
                if item.display_name == owner:
                    return item.uid
        return owner or "general"

    def _scenario_kind(self, owner: str) -> str:
        for s in self.project.active_scenarios:
            if s.display_title == owner:
                return s.kind
        return owner or "general"
