# -*- coding: utf-8 -*-
"""مولد متن گزارش متقاضیان سنگین — ترکیب Rule Engine و کتابخانه متن (بخش ۱۸ و ۱۹ سند).

ساختار بخش‌ها مطابق آخرین گزارش مرجع (مهر ۱۴۰۵):
    ۱ مقدمه ← ۲ تحلیل بارگذاری ← ۳ پیش‌بینی ← ۴ ایستگاه‌های نزدیک ← ۵ خطوط نزدیک
    ← ۶ پخش بار قبل ← ۷ پخش بار بعد ← ۸ کنترل بارگذاری و تعدیل بار ← ۹ نتیجه‌گیری و پیشنهادات

اصل: متن بر اساس وضعیت واقعی داده‌ها انتخاب می‌شود، نه متن ثابت.
"""
from __future__ import annotations

from pathlib import Path

from app.core import calculations as calc
from app.core.findings import (DOMAIN_LABELS_FA, SEVERITY_LABELS_FA, STATUS_LABELS_FA,
                               Finding, finding_key, resolve)
from app.core import traceability as trace
from app.core.forecast import FLAG_LABELS_FA
from app.core.models import (REVIEW_PENDING, Feeder, Project,
                             REQUEST_INCREASE, REQUEST_NEW)
from app.core.settings import AppSettings
from app.report.chart_generator import forecast_chart, profile_chart
from app.report.sections import FigureBlock, Paragraph, ReportSection, TableSpec
from app.report.template_manager import TemplateManager
from app.rules.rule_engine import RuleEngine
from app.utils.formatting import fmt

SECTION_INTRO = "intro"
SECTION_LOADING = "loading"
SECTION_FORECAST = "forecast"
SECTION_STATIONS = "stations"
SECTION_LINES = "lines"
SECTION_BEFORE = "before"
SECTION_AFTER = "after"
SECTION_CONTROL = "control"
SECTION_CONCLUSION = "conclusion"


class TextGenerator:
    def __init__(self, project: Project, settings: AppSettings,
                 texts: TemplateManager, engine: RuleEngine,
                 charts_dir: Path, image_resolver=None,
                 profile_loader=None) -> None:
        self.project = project
        self.settings = settings
        self.texts = texts
        self.engine = engine
        self.charts_dir = Path(charts_dir)
        self.image_resolver = image_resolver or (lambda img: None)
        # بارگذاری پروفیل فیدر (از حافظه یا CSV پروژه) — تا پس از بازکردن
        # مجدد پروژه هم نمودار پروفیل تولید شود.
        self.profile_loader = profile_loader
        self.fig_no = 0
        self.tbl_no = 0
        # تصاویری که در گزارش استفاده شده‌اند تا دوباره درج نشوند
        self._used_images: set[str] = set()
        # Finding های مهندسی این گزارش (برای صفحه تحلیل و بازبینی) — v1.0.3
        self.findings: list[Finding] = []
        self.report_warnings: list[str] = []


    # ------------------------------------------------------------------
    # Finding + بازبینی مهندس (v1.0.3)
    # ------------------------------------------------------------------
    def _resolve_text(self, domain: str, feeder, rule, text: str) -> str:
        """ثبت Finding و اعمال تصمیم مهندس؛ متن نهایی را برمی‌گرداند (بدون درج)."""
        fuid = feeder.uid if feeder is not None else ""
        key = finding_key(domain, fuid)
        final, dec, stale = resolve(self.project, key, text)
        self.findings.append(Finding(
            key=key, domain=domain,
            feeder_name=feeder.display_name if feeder is not None else "کل پروژه",
            rule_id=rule.id, rule_name=rule.name, severity=rule.severity,
            auto_text=text, status=dec.status, comment=dec.comment,
            final_text=final, stale=stale))
        if stale:
            self.report_warnings.append(
                f"داده‌های ورودی پس از بازبینی «{rule.name}» تغییر کرده است؛ تصمیم قبلی مهندس اعمال شد ولی نیاز به بازبینی مجدد دارد.")
        return final

    def _emit(self, sec: ReportSection, domain: str, feeder, rule, text: str,
              style: str = "body") -> None:
        """ثبت Finding و درج متن نهایی (با لحاظ Accept/Edit/Reject/Override مهندس)."""
        final = self._resolve_text(domain, feeder, rule, text)
        if final:
            sec.blocks.append(Paragraph(final, style=style))

    @staticmethod
    def _quality_text(fc) -> str:
        return "، ".join(FLAG_LABELS_FA.get(f, f) for f in fc.quality_flags) or "کیفیت داده نامشخص"

    # ------------------------------------------------------------------
    # ابزارهای کمکی
    # ------------------------------------------------------------------
    def _next_fig(self) -> int:
        self.fig_no += 1
        return self.fig_no

    def _next_tbl(self) -> int:
        self.tbl_no += 1
        return self.tbl_no

    def _figs_label(self, count: int) -> tuple[str, str]:
        """برای شماره شکل‌های متوالی: («2», «») یا («4 و 5», «های»)."""
        nums = list(range(self.fig_no + 1, self.fig_no + 1 + count))
        if not nums:
            return "—", ""
        if len(nums) == 1:
            return str(nums[0]), ""
        return " و ".join(str(n) for n in nums), "‌های"

    def _phrase_added(self) -> str:
        """عبارت «بار X مگاواتی متقاضی» یا «افزایش قدرت متقاضی»."""
        p = self.project
        added = p.added_power_mw()
        if p.request_type == REQUEST_INCREASE:
            return f"افزایش قدرت {p.applicant_name}"
        if added is not None:
            return f"بار {fmt(added, 2)} مگاواتی {p.applicant_name}"
        return f"بار جدید {p.applicant_name}"

    def _v(self, x, digits=3) -> str:
        return fmt(x, digits)

    def _peak_year(self) -> str:
        """سال پیک مرجع گزارش (بیشترین سال پیک ثبت‌شده فیدرها)."""
        year = max((f.peak_year for f in self.project.feeders if f.peak_year),
                   default=None)
        return str(year) if year else "—"

    @staticmethod
    def _fl(name: str) -> str:
        """برچسب فیدر: اگر نام با «فیدر» شروع نشود، پیشوند اضافه می‌شود."""
        name = (name or "").strip()
        return name if name.startswith("فیدر") else f"فیدر {name}".strip()

    @staticmethod
    def _strip_feeder(name: str) -> str:
        """حذف واژه «فیدر» از ابتدای نام — برای عناوینی که خودشان پیشوند دارند."""
        name = (name or "").strip()
        if name.startswith("فیدر"):
            return name[len("فیدر"):].strip()
        return name

    # ------------------------------------------------------------------
    # تصاویر کاربر بر اساس نوع
    # ------------------------------------------------------------------
    def _figures_of_kind(self, kind: str) -> list[FigureBlock]:
        blocks = []
        for img in self.project.images:
            if img.kind != kind or img.uid in self._used_images:
                continue
            path = self.image_resolver(img)
            if not path:
                continue
            self._used_images.add(img.uid)
            n = self._next_fig()
            caption = self.texts.render("T-CAP-FIG-USER", {"N": str(n), "TITLE": img.title or img.kind_label})
            blocks.append(FigureBlock(path=str(path), caption=caption))
        return blocks

    def _profile_df(self, feeder: Feeder):
        """DataFrame پروفیل فیدر — از loader (حافظه/CSV) یا attribute گذرا."""
        if self.profile_loader is not None:
            df = self.profile_loader(feeder)
            if df is not None:
                return df
        return getattr(feeder, "_profile_df", None)

    # ------------------------------------------------------------------
    # بخش ۱ — مقدمه
    # ------------------------------------------------------------------
    def build_intro(self) -> ReportSection:
        p, s = self.project, self.settings
        sec = ReportSection(SECTION_INTRO, "مقدمه")

        if p.request_type == REQUEST_INCREASE:
            request_phrase = f"افزایش قدرت {p.applicant_name}"
            item = self.texts.render("T-INTRO-ITEM-INCREASE", {
                "APPLICANT_NAME": p.applicant_name,
                "EXISTING_KW": fmt(p.existing_power_kw, 0),
                "NEW_KW": fmt(p.requested_power_kw, 0)})
        else:
            request_phrase = f"تأمین برق به {p.applicant_name}"
            item = self.texts.render("T-INTRO-ITEM-NEW", {
                "APPLICANT_NAME": p.applicant_name,
                "REQUESTED_KW": fmt(p.requested_power_kw, 0)})

        sec.blocks.append(Paragraph(
            self.texts.render("T-INTRO-MAIN", {"REQUEST_PHRASE": request_phrase})))
        sec.blocks.append(Paragraph(item, style="item"))

        # بند ب — موقعیت محل (مطابق گزارش مرجع: مختصات، فاصله، نوع هادی)
        has_location = p.location_note or p.location_distance_m or self._kind_count("location")
        if has_location:
            loc_figs = self._figures_of_kind("location")
            suffix = "" if loc_figs else "-NOFIG"
            fig_no = str(self.fig_no + 1) if loc_figs else ""
            if p.location_note or p.location_distance_m:
                conductor = (p.conductor_type or p.cable_suggestion or "").strip()
                base = "T-LOCATION-DETAIL" if conductor else "T-LOCATION-DETAIL-NOCOND"
                location_text = self.texts.render(base + suffix, {
                    "LOCATION_NOTE": p.location_note or "",
                    "DISTANCE_M": fmt(p.location_distance_m, 0),
                    "CONDUCTOR_TYPE": conductor,
                    "FIG_NO": fig_no})
            else:
                location_text = self.texts.render("T-LOCATION-DEFAULT" + suffix, {
                    "SUBSTATION": p.substation or "مربوطه", "FIG_NO": fig_no})
            sec.blocks.append(Paragraph(
                self.texts.render("T-INTRO-ITEM-LOCATION", {"LOCATION_TEXT": location_text}),
                style="item"))
            sec.blocks.extend(loc_figs)

        # مانور / بازآرایی
        if p.maneuver.enabled:
            man = p.maneuver
            man_figs = self._figures_of_kind("network")
            fig_no = str(self.fig_no + 1) if man_figs else "—"
            if man.transferred_mw is not None:
                transfer = self.texts.render("T-MANEUVER-TRANSFER", {
                    "SOURCE": self._fl(man.source_feeder),
                    "TARGET": self._fl(man.target_feeder),
                    "TRANSFERRED_MW": fmt(man.transferred_mw, 2)})
            else:
                transfer = self.texts.render("T-MANEUVER-TRANSFER-NOMW", {
                    "SOURCE": self._fl(man.source_feeder),
                    "TARGET": self._fl(man.target_feeder)})
            note = man.note or ""
            if not man.date_jalali:
                note = (note + " " + self.texts.render("T-MANEUVER-UNCERTAIN", {})).strip()
            sec.blocks.append(Paragraph(self.texts.render("T-MANEUVER", {
                "OFFICE": p.office or "مربوطه", "TRANSFER_TEXT": transfer,
                "FIG_NO": fig_no, "MANEUVER_NOTE": note})))
            sec.blocks.extend(man_figs)

        return sec

    def _kind_count(self, kind: str) -> int:
        return sum(1 for i in self.project.images if i.kind == kind)

    # ------------------------------------------------------------------
    # بخش ۲ — تحلیل وضعیت بارگذاری
    # ------------------------------------------------------------------
    def build_loading(self) -> ReportSection:
        p, s = self.project, self.settings
        names = " و ".join(self._fl(n) for n in p.feeder_names) or "—"
        multi = len(p.feeders) > 1
        stripped = " و ".join(self._strip_feeder(n) for n in p.feeder_names).strip()
        title = "تحلیل وضعیت بارگذاری فیدر" + ("های" if multi else "")
        if stripped:
            title += f" {stripped}"
        sec = ReportSection(SECTION_LOADING, title)

        profile_figs_count = sum(1 for f in p.feeders if f.profile_stats.n_points)
        has_profile_figs = profile_figs_count > 0
        figs, sfig = self._figs_label(profile_figs_count)
        tbl_label = str(self.tbl_no + 1)

        if multi:
            intro_id = "T-LOAD-INTRO-MF" if has_profile_figs else "T-LOAD-INTRO-MF-NOFIG"
        else:
            intro_id = "T-LOAD-INTRO-1F" if has_profile_figs else "T-LOAD-INTRO-1F-NOFIG"
        sec.blocks.append(Paragraph(self.texts.render(intro_id, {
            "NAMES": names, "FIGS": figs, "S_FIG": sfig, "TBL_PEAK": tbl_label})))

        # شرح پروفیل بار هر فیدر
        for f in p.feeders:
            if f.profile_stats.n_points:
                st = f.profile_stats
                sec.blocks.append(Paragraph(self.texts.render("T-LOAD-PROFILE", {
                    "NAME": self._fl(f.name), "START": st.period_start,
                    "END": st.period_end, "PEAK": fmt(st.peak_p_mw, 2)})))
            else:
                sec.blocks.append(Paragraph(self.texts.render("T-LOAD-PROFILE-NODATA", {
                    "NAME": self._fl(f.name), "PEAK": fmt(f.peak_load_mw, 2)})))

        # طبقه‌بندی بارگذاری (Rule Engine)
        for f in p.feeders:
            ctx = calc.build_feeder_context(f, p, s)
            rule = self.engine.first_match("loading", ctx)
            if rule:
                self._emit(sec, "loading", f, rule, self.texts.render(rule.text_id, {
                    "CAPACITY": fmt(f.capacity_mw, 2),
                    "PEAK": fmt(f.peak_load_mw, 2)}))

        # جدول ۱ — پیک بار
        peak_tbl = self._peak_table()
        if peak_tbl:
            sec.blocks.append(peak_tbl)

        # شکل‌های پروفیل بار (نمودار خودکار) — حتی پس از بازکردن مجدد پروژه
        for f in p.feeders:
            df = self._profile_df(f)
            if df is None or (hasattr(df, "empty") and df.empty):
                continue
            out = self.charts_dir / f"profile_{f.uid}.png"
            if profile_chart(df, f.name, out):
                n = self._next_fig()
                caption = self.texts.render("T-CAP-FIG-PROFILE", {"N": str(n), "NAME": self._fl(f.name)})
                sec.blocks.append(FigureBlock(path=str(out), caption=caption))

        # اثر بار جدید بر طبقه بارگذاری — مطابق گزارش مرجع پس از شکل پروفیل
        added = p.added_power_mw()
        for f in p.feeders:
            ctx = calc.build_feeder_context(f, p, s)
            after_pct = ctx.get("loading_after_pct")
            if after_pct is not None and added is not None and f.capacity_mw:
                if after_pct > s.thresholds.loading_heavy_pct:
                    text_id = "T-LOAD-WITH-NEW-CRITICAL"
                elif ctx.get("loading_after_class") != ctx.get("loading_class"):
                    text_id = "T-LOAD-WITH-NEW-CHANGE"
                else:
                    text_id = "T-LOAD-WITH-NEW-STABLE"
                sec.blocks.append(Paragraph(self.texts.render(text_id, {
                    "ADDED": fmt(added, 2),
                    "CLASS_AFTER": ctx.get("loading_after_class", "—"),
                    "CAPACITY": fmt(f.capacity_mw, 2)})))

        return sec

    def _peak_table(self) -> TableSpec | None:
        """جدول ۱ نمونه‌ها: پیک آمپر / پیک مگاوات / ضریب توان — یک ستون به ازای هر فیدر."""
        p = self.project
        feeders = [f for f in p.feeders]
        if not feeders:
            return None
        year = max((f.peak_year for f in p.feeders if f.peak_year), default=None)
        sub = p.substation or (feeders[0].substation if feeders else "")
        n = self._next_tbl()
        caption = self.texts.render("T-CAP-PEAK-TABLE", {
            "N": str(n), "S": "" if len(feeders) == 1 else "های",
            "SUB": sub, "YEAR": str(year or "—")})
        header = ["مشخصه"] + [f.name for f in feeders]
        rows = [
            [self.texts.render("T-HDR-PEAK-A", {})] + [fmt(f.peak_current_a, 0) for f in feeders],
            [self.texts.render("T-HDR-PEAK-MW", {})] + [fmt(f.peak_load_mw, 2) for f in feeders],
            [self.texts.render("T-HDR-PF", {})] + [fmt(f.power_factor, 2) for f in feeders],
        ]
        return TableSpec(caption=caption, header_rows=[header], body_rows=rows)

    # ------------------------------------------------------------------
    # بخش ۳ — پیش‌بینی پیک بار در افق پنج‌ساله
    # ------------------------------------------------------------------
    def build_forecast(self) -> ReportSection:
        p, s = self.project, self.settings
        sec = ReportSection(SECTION_FORECAST, "پیش‌بینی پیک بار در افق پنج‌ساله")

        any_fc = False
        for f in p.feeders:
            ctx = calc.build_feeder_context(f, p, s)
            fc = f.forecast
            fig_path = None
            if fc.available or len(fc.history_years) >= 2:
                out = self.charts_dir / f"forecast_{f.uid}.png"
                if forecast_chart(fc.history_years, fc.history_values, fc.points, out):
                    fig_path = out

            rule = self.engine.first_match("forecast", ctx)
            if rule:
                any_fc = True
                fig_label = str(self.fig_no + 1) if fig_path else "—"
                text = self.texts.render(rule.text_id, {
                    "FIG": fig_label, "NAME": self._fl(f.name),
                    "YEARS": str(s.thresholds.forecast_years),
                    "END_YEAR": str(fc.end_year() or "—"),
                    "END_MW": fmt(fc.end_value(), 2),
                    "QUALITY": self._quality_text(fc)})
                self._emit(sec, "forecast", f, rule, text)
                if fig_path:
                    n = self._next_fig()
                    caption = self.texts.render("T-CAP-FIG-FORECAST", {
                        "N": str(n), "YEARS": str(s.thresholds.forecast_years),
                        "NAME": self._fl(f.name)})
                    sec.blocks.append(FigureBlock(path=str(fig_path), caption=caption))
                # یادداشت روش/کیفیت پیش‌بینی (متن کارشناس) — پس از شکل
                if (fc.note or "").strip():
                    sec.blocks.append(Paragraph(fc.note.strip()))

        if not any_fc and not p.feeders:
            sec.blocks.append(Paragraph(self.texts.render("T-FORECAST-NO-DATA", {})))

        return sec

    # ------------------------------------------------------------------
    # بخش ۴ — ایستگاه‌های نزدیک به محل تقاضا
    # ------------------------------------------------------------------
    def build_stations(self) -> ReportSection | None:
        p = self.project
        stations = [st for st in p.nearby_stations if st.has_data()]
        if not stations:
            return None
        sec = ReportSection(SECTION_STATIONS, "ایستگاه‌های نزدیک به محل تقاضا")

        items = []
        for st in stations:
            items.append(self.texts.render("T-STATIONS-SUMMARY-ITEM", {
                "NAME": st.name,
                "DISTANCE": fmt(st.distance_km, 2),
                "CAPACITY": fmt(st.capacity_mva, 2),
                "FEEDERS": str(st.feeder_count) if st.feeder_count is not None else "—"}))
        summary = " و ".join(items) + "."
        sec.blocks.append(Paragraph(
            self.texts.render("T-STATIONS-INTRO", {"SUMMARY": summary})))

        year = self._peak_year()
        n = self._next_tbl()
        header = [self.texts.render("T-STN-HDR", {})] + [st.name for st in stations]

        def row(tid: str, values: list[str], **kw) -> list[str]:
            return [self.texts.render(tid, kw)] + values

        def pct(v) -> str:
            return "—" if v is None else f"{fmt(v, 1)}٪"

        rows = [
            row("T-STN-DIST", [fmt(st.distance_km, 2) for st in stations]),
            row("T-STN-CAP", [fmt(st.capacity_mva, 2) for st in stations]),
            row("T-STN-T1-PCT", [pct(st.t1_loading_pct) for st in stations], YEAR=year),
            row("T-STN-T2-PCT", [pct(st.t2_loading_pct) for st in stations], YEAR=year),
            row("T-STN-T1-MVA", [fmt(st.t1_loading_mva, 2) for st in stations], YEAR=year),
            row("T-STN-T2-MVA", [fmt(st.t2_loading_mva, 2) for st in stations], YEAR=year),
            row("T-STN-FEEDERS", [str(st.feeder_count) if st.feeder_count is not None else "—"
                                  for st in stations]),
        ]
        sec.blocks.append(TableSpec(
            caption=self.texts.render("T-CAP-STATIONS-TABLE", {"N": str(n)}),
            header_rows=[header], body_rows=rows))
        return sec

    # ------------------------------------------------------------------
    # بخش ۵ — خطوط نزدیک به محل تقاضا
    # ------------------------------------------------------------------
    def build_lines(self) -> ReportSection | None:
        p = self.project
        lines = [ln for ln in p.nearby_lines if ln.has_data()]
        if not lines:
            return None
        sec = ReportSection(SECTION_LINES, "خطوط نزدیک به محل تقاضا")
        sec.blocks.append(Paragraph(self.texts.render("T-LINES-INTRO", {})))

        year = self._peak_year()
        n = self._next_tbl()
        header = [self.texts.render("T-LIN-HDR", {})] + [ln.name for ln in lines]

        def peak_cell(ln) -> str:
            parts = []
            if ln.peak_mva is not None:
                parts.append(f"{fmt(ln.peak_mva, 2)} MVA")
            if ln.peak_mw is not None:
                parts.append(f"{fmt(ln.peak_mw, 2)} MW")
            if ln.peak_a is not None:
                parts.append(f"{fmt(ln.peak_a, 0)} A")
            return "\n".join(parts) if parts else "—"

        def pct(v) -> str:
            return "—" if v is None else f"{fmt(v, 1)}٪"

        def delta(ln) -> str:
            d = ln.vdrop_delta_pct()
            return "—" if d is None else f"{d:+.2f}"

        rows = [
            [self.texts.render("T-LIN-DIST", {})] + [fmt(ln.distance_m, 0) for ln in lines],
            [self.texts.render("T-LIN-PEAK", {"YEAR": year})] + [peak_cell(ln) for ln in lines],
            [self.texts.render("T-LIN-VDROP-BEFORE", {"YEAR": year})] + [pct(ln.vdrop_before_pct) for ln in lines],
            [self.texts.render("T-LIN-VDROP-AFTER", {"YEAR": year})] + [pct(ln.vdrop_after_pct) for ln in lines],
            [self.texts.render("T-LIN-VDROP-DELTA", {})] + [delta(ln) for ln in lines],
        ]
        sec.blocks.append(TableSpec(
            caption=self.texts.render("T-CAP-LINES-TABLE", {"N": str(n)}),
            header_rows=[header], body_rows=rows))

        # یادداشت «افت ولتاژ موجود، ناشی از متقاضی نیست»
        for ln in lines:
            d = ln.vdrop_delta_pct()
            if (ln.vdrop_before_pct or 0) > 0 and (d is None or abs(d) < 0.05):
                sec.blocks.append(Paragraph(
                    self.texts.render("T-LINES-NOTE", {"NAME": ln.name}), style="note"))
        return sec

    # ------------------------------------------------------------------
    # بخش ۶ — نتایج پخش بار قبل
    # ------------------------------------------------------------------
    def build_before(self) -> ReportSection:
        p = self.project
        word = "افزایش قدرت" if p.request_type == REQUEST_INCREASE else "اتصال بار جدید"
        sec = ReportSection(SECTION_BEFORE, f"نتایج پخش بار قبل از {word}")

        before_figs = [i for i in p.images if i.kind == "before"]
        figs, sfig = self._figs_label(len(before_figs))
        intro_id = "T-BEFORE-INTRO" if before_figs else "T-BEFORE-INTRO-NOFIG"
        sec.blocks.append(Paragraph(self.texts.render(intro_id, {
            "ADDED_PHRASE": self._phrase_added(), "FIGS": figs})))

        for f in p.feeders:
            if f.before.is_complete():
                text = self.texts.render("T-BEFORE-FEEDER", {
                    "NAME": self._fl(f.name), "V": self._v(f.before.min_voltage_pu),
                    "I": fmt(f.before.current_a, 0), "LOSS": fmt(f.before.loss_kw, 0)})
                if f.before.applicant_bus_voltage_pu is not None:
                    text += " " + self.texts.render("T-BEFORE-FEEDER-BUS", {
                        "VBUS": self._v(f.before.applicant_bus_voltage_pu)})
                sec.blocks.append(Paragraph(text))
            else:
                sec.blocks.append(Paragraph(
                    self.texts.render("T-BEFORE-NONE", {"NAME": f.name}), style="note"))

        sec.blocks.extend(self._figures_of_kind("before"))
        return sec

    # ------------------------------------------------------------------
    # بخش ۷ — نتایج پخش بار پس از اعمال بار
    # ------------------------------------------------------------------
    def build_after(self) -> ReportSection:
        p, s = self.project, self.settings
        word = "افزایش قدرت" if p.request_type == REQUEST_INCREASE else "اتصال بار جدید"
        sec = ReportSection(SECTION_AFTER, f"نتایج پخش بار پس از {word}")

        names = " و ".join(self._fl(n) for n in p.feeder_names) or "—"
        multi = len(p.feeders) > 1
        after_figs = [i for i in p.images if i.kind in ("after", "other")]
        figs, sfig = self._figs_label(len(after_figs))
        tbl_label = str(self.tbl_no + 1)
        after_phrase = ("اعمال بار جدید" if p.request_type == REQUEST_NEW
                        else "افزایش قدرت")
        request_word = ("افزایش قدرت" if p.request_type == REQUEST_INCREASE
                        else "بار")

        intro_id = "T-AFTER-INTRO" if after_figs else "T-AFTER-INTRO-NOFIG"
        sec.blocks.append(Paragraph(self.texts.render(intro_id, {
            "EFFECT_PHRASE": self._phrase_added(), "S": "" if not multi else "های",
            "NAMES": names, "AFTER_PHRASE": after_phrase,
            "S_FIG": sfig if after_figs else "", "FIGS": figs if after_figs else "—",
            "TBL": tbl_label})))

        th = s.thresholds
        for f in p.feeders:
            ctx = calc.build_feeder_context(f, p, s)
            if not (ctx["has_before"] and ctx["has_after"]):
                continue
            common = {
                "NAME": self._fl(f.name), "MAXCHG": fmt(th.voltage_change_max_pct, 0),
                "CHG": fmt(ctx["d_v_pct"], 1),
                "VB": self._v(f.before.min_voltage_pu),
                "VA": self._v(f.after.min_voltage_pu),
                "REQUEST_WORD": request_word,
            }
            for domain, style in (("after_voltage", "body"),
                                  ("current", "bullet"), ("loss", "bullet")):
                rule = self.engine.first_match(domain, ctx)
                if not rule:
                    continue
                vals = dict(common)
                if domain == "current":
                    vals.update({"I1": fmt(f.before.current_a, 0),
                                 "I2": fmt(f.after.current_a, 0),
                                 "IMAX": fmt(f.max_current_a, 0),
                                 "LOADING": fmt(ctx["i_loading_pct"], 0)})
                if domain == "loss":
                    vals.update({"L1": fmt(f.before.loss_kw, 0),
                                 "L2": fmt(f.after.loss_kw, 0),
                                 "PCT": fmt(abs(ctx["d_loss_pct"] or 0), 0)})
                self._emit(sec, domain, f, rule, self.texts.render(rule.text_id, vals),
                           style=style)
            if (f.before.applicant_bus_voltage_pu is not None
                    and f.after.applicant_bus_voltage_pu is not None):
                sec.blocks.append(Paragraph(self.texts.render("T-VOLT-BUS", {
                    "VB1": self._v(f.before.applicant_bus_voltage_pu),
                    "VB2": self._v(f.after.applicant_bus_voltage_pu)}), style="bullet"))

        # جدول نتایج قبل/بعد
        result_tbl = self._result_table()
        if result_tbl:
            sec.blocks.append(result_tbl)
        sec.blocks.extend(self._figures_of_kind("after"))
        sec.blocks.extend(self._figures_of_kind("other"))
        return sec

    def _result_table(self) -> TableSpec | None:
        """جدول نتایج نمونه‌ها: وضعیت فعلی / اثر اعمال بار جدید."""
        p = self.project
        feeders = [f for f in p.feeders if f.before.is_complete() or f.after.is_complete()]
        if not feeders:
            return None
        n = self._next_tbl()
        caption = self.texts.render("T-CAP-RESULT-TABLE", {"N": str(n), "TITLE": p.title_text()})
        h1 = ["وضعیت"]
        h2 = ["وضعیت"]
        merges: list[tuple[int, int, int]] = []
        for i, f in enumerate(feeders):
            start = 1 + i * 4
            merges.append((0, start, start + 3))
            h1.append(f.name)
            h1.extend([""] * 3)
            h2.extend([self.texts.render("T-HDR-CURRENT", {}),
                       self.texts.render("T-HDR-LOSS", {}),
                       self.texts.render("T-HDR-VMIN", {}),
                       self.texts.render("T-HDR-VBUS", {})])
        case_now = self.texts.render("T-HDR-CASE-NOW", {})
        case_new = (self.texts.render("T-HDR-CASE-NEW-SUPPLY", {})
                    if p.request_type == REQUEST_NEW
                    else self.texts.render("T-HDR-CASE-NEW", {}))
        row_now = [case_now]
        row_new = [case_new]
        for f in feeders:
            row_now += [fmt(f.before.current_a, 0), fmt(f.before.loss_kw, 0),
                        self._v(f.before.min_voltage_pu), self._v(f.before.applicant_bus_voltage_pu)]
            row_new += [fmt(f.after.current_a, 0), fmt(f.after.loss_kw, 0),
                        self._v(f.after.min_voltage_pu), self._v(f.after.applicant_bus_voltage_pu)]
        return TableSpec(caption=caption, header_rows=[h1, h2],
                         body_rows=[row_now, row_new], merges=merges)

    # ------------------------------------------------------------------
    # بخش ۸ — کنترل بارگذاری فیدر و راهکارهای تعدیل بار
    # ------------------------------------------------------------------
    def _control_needed(self) -> bool:
        """بخش کنترل فقط وقتی می‌آید که تعدیل بار لازم باشد یا داده‌ای ثبت شده باشد."""
        p, s = self.project, self.settings
        for f in p.feeders:
            if (f.control_solution or "").strip() or f.adjacent_feeders:
                return True
            ctx = calc.build_feeder_context(f, p, s)
            pct_after = ctx.get("loading_after_pct")
            if pct_after is not None and pct_after > s.thresholds.loading_heavy_pct:
                return True
        return False

    def build_control(self) -> ReportSection | None:
        if not self._control_needed():
            return None
        p, s = self.project, self.settings
        sec = ReportSection(SECTION_CONTROL, "کنترل بارگذاری فیدر و راهکارهای تعدیل بار")

        added = p.added_power_mw()
        names = " و ".join(self._fl(n) for n in p.feeder_names) or "—"
        # فیدر بحرانی با بیشترین بارگذاری پس از اعمال بار جدید
        critical = []
        for f in p.feeders:
            ctx = calc.build_feeder_context(f, p, s)
            pct_after = ctx.get("loading_after_pct")
            if pct_after is not None and pct_after > s.thresholds.loading_heavy_pct:
                critical.append((f, ctx))
        if critical:
            critical.sort(key=lambda t: t[1]["loading_after_pct"], reverse=True)
            f, ctx = critical[0]
            sec.blocks.append(Paragraph(self.texts.render("T-CONTROL-INTRO-CRITICAL", {
                "ADDED": fmt(added, 2), "YEAR": self._peak_year(),
                "NAME": self._fl(f.name),
                "CLASS": ctx.get("loading_after_class", "بحرانی"),
                "TOTAL": fmt(ctx.get("loading_total_mw"), 2)})))
        else:
            sec.blocks.append(Paragraph(self.texts.render("T-CONTROL-INTRO-OK", {
                "ADDED": fmt(added, 2), "NAMES": names})))

        # فیدرهای همجوار کاندید تعدیل بار
        for f in p.feeders:
            if not f.adjacent_feeders:
                continue
            lst = "، ".join(
                (f"{self._fl(a.name)} با بار {fmt(a.load_mw, 2)} مگاوات"
                 if a.load_mw is not None else self._fl(a.name))
                for a in f.adjacent_feeders if a.name)
            if lst:
                sec.blocks.append(Paragraph(self.texts.render("T-CONTROL-ADJACENT", {
                    "NAME": self._fl(f.name),
                    "COUNT": str(len(f.adjacent_feeders)), "LIST": lst})))

        # جدول کنترل بارگذاری کل فیدر و راهکار پیشنهادی
        feeders = [f for f in p.feeders if f.capacity_mw or (f.control_solution or "").strip()
                   or f.adjacent_feeders]
        if feeders and added is not None:
            n = self._next_tbl()
            header = [self.texts.render("T-CTL-H-FEEDER", {}),
                      self.texts.render("T-CTL-H-PEAK", {}),
                      self.texts.render("T-CTL-H-ADDED", {}),
                      self.texts.render("T-CTL-H-TOTAL", {}),
                      self.texts.render("T-CTL-H-CLASS", {}),
                      self.texts.render("T-CTL-H-SOLUTION", {})]
            body = []
            for f in feeders:
                ctx = calc.build_feeder_context(f, p, s)
                pct_after = ctx.get("loading_after_pct")
                klass = ctx.get("loading_after_class", "—") if pct_after is not None else "—"
                solution = (f.control_solution or "").strip()
                if not solution and f.adjacent_feeders:
                    lst = "\n".join(
                        (f"{self._fl(a.name)} با بار {fmt(a.load_mw, 2)} مگاوات"
                         if a.load_mw is not None else self._fl(a.name))
                        for a in f.adjacent_feeders if a.name)
                    if lst:
                        solution = self.texts.render("T-CTL-SOL-ADJACENT", {"LIST": lst})
                body.append([self._fl(f.name), fmt(f.peak_load_mw, 2), fmt(added, 2),
                             fmt(ctx.get("loading_total_mw"), 2), klass, solution or "—"])
            sec.blocks.append(TableSpec(
                caption=self.texts.render("T-CAP-CONTROL-TABLE", {"N": str(n)}),
                header_rows=[header], body_rows=body))

        # شکل‌های فیدرهای همجوار و پخش بار بازآرایی + تصاویر شبکه باقی‌مانده
        sec.blocks.extend(self._figures_of_kind("adjacent"))
        sec.blocks.extend(self._figures_of_kind("reconfig"))
        sec.blocks.extend(self._figures_of_kind("network"))
        return sec

    # ------------------------------------------------------------------
    # بخش ۹ — نتیجه‌گیری و پیشنهادات
    # ------------------------------------------------------------------
    def build_conclusion(self) -> ReportSection:
        p, s = self.project, self.settings
        sec = ReportSection(SECTION_CONCLUSION, "نتیجه‌گیری و پیشنهادات")
        ctx = calc.build_project_context(p, s)
        rule = self.engine.first_match("conclusion", ctx)
        names = " و ".join(self._fl(n) for n in p.feeder_names) or "—"
        multi = len(p.feeders) > 1
        if rule:
            text = self.texts.render(rule.text_id, {
                "REQUEST_PHRASE": ("افزایش قدرت" if p.request_type == REQUEST_INCREASE
                                   else "اتصال بار جدید"),
                "APPLICANT_NAME": p.applicant_name,
                "S": "" if not multi else "های", "NAMES": names,
                "MAXCHG": fmt(s.thresholds.voltage_change_max_pct, 0),
                "ISSUE_SUMMARY": calc.issue_summary(p, s)})
            analysis = self._resolve_text("conclusion", None, rule, text)
        else:
            analysis = self.texts.render("T-CONCL-NODATA", {})

        scenarios = (p.conclusion_scenarios or "").strip()
        if not scenarios and p.maneuver.enabled:
            scenarios = self.texts.render("T-CONCL-SCENARIO-MANEUVER", {
                "SOURCE": self._fl(p.maneuver.source_feeder),
                "TARGET": self._fl(p.maneuver.target_feeder)})

        hdr = self.texts.render("T-CONCL-HDR", {})
        header_rows = [[hdr, hdr]]
        body_rows = [[self.texts.render("T-CONCL-ROW-ANALYSIS", {}), analysis or "—"]]
        if scenarios:
            body_rows.append([self.texts.render("T-CONCL-ROW-SCENARIOS", {}), scenarios])
        sec.blocks.append(TableSpec(caption="", header_rows=header_rows,
                                    body_rows=body_rows, merges=[(0, 0, 1)]))
        return sec


    # ------------------------------------------------------------------
    # پیوست‌ها: ردیابی داده‌ها + تصمیمات بازبینی مهندس (v1.0.3)
    # ------------------------------------------------------------------
    def build_appendices(self) -> list[ReportSection]:
        out: list[ReportSection] = []
        rows = trace.build_trace(self.project, self.settings)
        if rows:
            sec = ReportSection("appendix_trace", "پیوست الف- ردیابی منبع داده‌ها")
            sec.blocks.append(Paragraph(
                "منبع هر یک از مقادیر مهم مورد استفاده در این گزارش (ورودی Excel/CSV، ورود دستی، "
                "محاسبه یا نتیجه نرم‌افزار PowerFactory) در جدول زیر ثبت شده است."))
            n = self._next_tbl()
            body = [[r.feeder, r.item, f"{r.value} {r.unit}".strip(), r.source_label] for r in rows]
            sec.blocks.append(TableSpec(
                caption=f"جدول {n}: ردیابی منبع داده‌های گزارش",
                header_rows=[["فیدر", "کمیت", "مقدار", "منبع"]], body_rows=body))
            out.append(sec)
        decided = [f for f in self.findings if f.status != REVIEW_PENDING or f.comment]
        if decided:
            sec = ReportSection("appendix_review", "پیوست ب- تصمیمات بازبینی مهندس")
            n = self._next_tbl()
            body = [[f.feeder_name, DOMAIN_LABELS_FA.get(f.domain, f.domain),
                     STATUS_LABELS_FA.get(f.status, f.status), f.comment or "—"] for f in decided]
            sec.blocks.append(TableSpec(
                caption=f"جدول {n}: تصمیمات و توضیحات مهندس مطالعات",
                header_rows=[["مورد", "حوزه", "تصمیم", "توضیح مهندس"]], body_rows=body))
            out.append(sec)
        return out

    # ------------------------------------------------------------------
    def build_all(self) -> list[ReportSection]:
        """ساخت کل گزارش با ترتیب بخش‌های گزارش مرجع + ویرایش‌های دستی کارشناس."""
        from app.report.sections import apply_manual_texts
        intro = self.build_intro()
        loading = self.build_loading()
        forecast = self.build_forecast()
        stations = self.build_stations()
        lines = self.build_lines()
        before = self.build_before()
        after = self.build_after()
        control = self.build_control()
        conclusion = self.build_conclusion()
        sections = [intro, loading, forecast]
        if stations is not None:
            sections.append(stations)
        if lines is not None:
            sections.append(lines)
        sections += [before, after]
        if control is not None:
            sections.append(control)
        sections.append(conclusion)
        if getattr(self.settings, "include_appendices", True):
            sections += self.build_appendices()
        return apply_manual_texts(sections, self.project)
