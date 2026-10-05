# -*- coding: utf-8 -*-
"""مولد متن گزارش — ترکیب Rule Engine و کتابخانه متن (بخش ۱۸ و ۱۹ سند).

اصل: متن بر اساس وضعیت واقعی داده‌ها انتخاب می‌شود، نه متن ثابت.
"""
from __future__ import annotations

from pathlib import Path

from app.core import calculations as calc
from app.core.findings import (DOMAIN_LABELS_FA, SEVERITY_LABELS_FA, STATUS_LABELS_FA,
                               Finding, finding_key, resolve)
from app.core import traceability as trace
from app.core.models import REVIEW_PENDING
from app.core.forecast import FLAG_LABELS_FA
from app.core.models import (Project, REQUEST_INCREASE, REQUEST_NEW)
from app.core.settings import AppSettings
from app.report.chart_generator import forecast_chart, profile_chart
from app.report.sections import FigureBlock, Paragraph, ReportSection, TableSpec
from app.report.template_manager import TemplateManager
from app.rules.rule_engine import RuleEngine
from app.utils.formatting import fmt

SECTION_INTRO = "intro"
SECTION_LOADING = "loading"
SECTION_FORECAST = "forecast"
SECTION_BEFORE = "before"
SECTION_AFTER = "after"
SECTION_CONCLUSION = "conclusion"


class TextGenerator:
    def __init__(self, project: Project, settings: AppSettings,
                 texts: TemplateManager, engine: RuleEngine,
                 charts_dir: Path, image_resolver=None,
                 profile_loader=None) -> None:
        self.project = project
        # ورودی‌های خاموش (کلید On/Off) در گزارش نمی‌آیند (v1.2.0)
        self.feeders = list(project.active_feeders) if hasattr(project, "active_feeders") else list(project.feeders)
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
        # نتایج Ruleهای تحلیلی مطالعه مصارف سنگین («تغییرات آرنا» v1.1.0)
        self.study_results: list = []


    # ------------------------------------------------------------------
    # Finding + بازبینی مهندس (v1.0.3)
    # ------------------------------------------------------------------
    def _emit(self, sec: ReportSection, domain: str, feeder, rule, text: str) -> None:
        """ثبت Finding و درج متن نهایی (با لحاظ Accept/Edit/Reject/Override مهندس)."""
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
        if final:
            sec.blocks.append(Paragraph(final))

    def _emit_rule_result(self, sec: ReportSection, result, owner_key: str = "") -> None:
        """ثبت Finding حاصل از یک Rule تحلیلی (خروجی استاندارد Rule Engine).

        * متن گزارش فقط از ``result.recommended_text`` و آن هم تنها وقتی داده‌ها
          معتبر باشند تولید می‌شود (MISSING_RULE / DATA_ERROR متن تولید نمی‌کنند).
        * تصمیم مهندس (Accept/Edit/Reject/Override) مطابق مکانیزم v1.0.3 اعمال و
          ماندگار می‌شود.
        """
        # کلید پایدار و یکتا برای هر Rule: <حوزه>:<مورد>:<شناسه Rule>
        rule_key = result.rule_key or result.rule_id
        suffix = f"{owner_key}:{rule_key}" if owner_key else rule_key
        key = finding_key(result.category, suffix)
        base_text = result.recommended_text if result.text_available else ""
        auto_text = base_text or result.finding
        final, dec, stale = resolve(self.project, key, auto_text)
        self.findings.append(Finding(
            key=key, domain=result.category,
            feeder_name=result.owner or "کل پروژه",
            rule_id=result.rule_id, rule_name=result.rule_name or result.rule_id,
            severity=result.severity, auto_text=auto_text, status=dec.status,
            comment=dec.comment, final_text=final, stale=stale))
        if stale:
            self.report_warnings.append(
                f"داده‌های ورودی پس از بازبینی «{result.rule_name or result.rule_id}» تغییر کرده است؛ "
                "تصمیم قبلی مهندس اعمال شد ولی نیاز به بازبینی مجدد دارد.")
        if final and (base_text or dec.status != REVIEW_PENDING):
            sec.blocks.append(Paragraph(final))

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
    def _figures_for_section(self, section_key: str, kinds: tuple[str, ...] = ()) -> list[FigureBlock]:
        """شکل‌های یک بخش گزارش — بر پایهٔ «محل قرارگیری» و «نوع» شکل (v1.2.0).

        * شکلی که «محل قرارگیری» صریح دارد، فقط در همان بخش درج می‌شود.
        * شکل بدون محل صریح، در بخشی درج می‌شود که «نوع» آن را مجاز کرده باشد
          (سازگاری کامل با پروژه‌های ۱.۱.x).
        * ترتیب درج: مقدار «اولویت/ترتیب» و سپس ترتیب ورود در فهرست تصاویر.
        * کپشن مستقل شکل (در صورت ثبت) بر کپشن خودکار مقدم است.
        """
        from app.core.report_sections import section_of_image
        if self.settings is not None and not self.settings.section_enabled(section_key):
            return []
        candidates: list[tuple[int, int, object]] = []
        for index, img in enumerate(getattr(self.project, "active_images", self.project.images)):
            if img.uid in self._used_images:
                continue
            explicit = section_of_image(img)
            if explicit:
                if explicit != section_key:
                    continue
            else:
                if img.kind not in kinds:
                    continue
            candidates.append((int(getattr(img, "order", 0) or 0), index, img))
        candidates.sort(key=lambda t: (t[0], t[1]))

        blocks: list[FigureBlock] = []
        for _order, _index, img in candidates:
            path = self.image_resolver(img)
            if not path:
                continue
            self._used_images.add(img.uid)
            n = self._next_fig()
            custom = (getattr(img, "caption", "") or "").strip()
            caption = custom or self.texts.render(
                "T-CAP-FIG-USER", {"N": str(n), "TITLE": img.title or img.kind_label})
            blocks.append(FigureBlock(path=str(path), caption=caption))
        return blocks

    def _figures_of_kind(self, kind: str) -> list[FigureBlock]:
        """سازگاری با نسخه‌های قبل: شکل‌های یک «نوع» (در هر بخشی) که هنوز درج نشده‌اند."""
        blocks: list[FigureBlock] = []
        for img in getattr(self.project, "active_images", self.project.images):
            if img.kind != kind or img.uid in self._used_images:
                continue
            path = self.image_resolver(img)
            if not path:
                continue
            self._used_images.add(img.uid)
            n = self._next_fig()
            custom = (getattr(img, "caption", "") or "").strip()
            caption = custom or self.texts.render(
                "T-CAP-FIG-USER", {"N": str(n), "TITLE": img.title or img.kind_label})
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

        # بند ب — موقعیت محل (نمونه ۲)
        has_location = p.location_note or p.location_distance_m or self._kind_count("location")
        if has_location:
            loc_figs = self._figures_for_section(SECTION_INTRO, ("location",))
            suffix = "" if loc_figs else "-NOFIG"
            fig_no = str(self.fig_no + 1) if loc_figs else ""
            if p.location_note or p.location_distance_m:
                location_text = self.texts.render("T-LOCATION-DETAIL" + suffix, {
                    "LOCATION_NOTE": p.location_note or "",
                    "DISTANCE_M": fmt(p.location_distance_m, 0),
                    "CABLE_TYPE": p.cable_suggestion or "—",
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
            man_figs = self._figures_for_section(SECTION_INTRO, ("network",))
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

    def _active_names(self) -> list[str]:
        """نام فیدرهای فعال (کلید On/Off) — برای عناوین گزارش."""
        return [f.name for f in self.feeders if f.name]

    def _kind_count(self, kind: str) -> int:
        images = getattr(self.project, "active_images", self.project.images)
        return sum(1 for i in images if i.kind == kind)

    # ------------------------------------------------------------------
    # بخش ۲ — تحلیل بارگذاری
    # ------------------------------------------------------------------
    def build_loading(self) -> tuple[ReportSection, ReportSection]:
        p, s = self.project, self.settings
        names = " و ".join(self._fl(n) for n in self._active_names()) or "—"
        multi = len(self.feeders) > 1
        stripped = " و ".join(self._strip_feeder(n) for n in self._active_names()).strip()
        title = "تحلیل وضعیت بارگذاری فیدر" + ("های" if multi else "")
        if stripped:
            title += f" {stripped}"
        sec = ReportSection(SECTION_LOADING, title)

        profile_figs_count = sum(1 for f in self.feeders if f.profile_stats.n_points)
        has_profile_figs = profile_figs_count > 0
        figs, sfig = self._figs_label(profile_figs_count)
        tbl_label = str(self.tbl_no + 1)

        if multi:
            intro_id = "T-LOAD-INTRO-MF" if has_profile_figs else "T-LOAD-INTRO-MF-NOFIG"
        else:
            intro_id = "T-LOAD-INTRO-1F" if has_profile_figs else "T-LOAD-INTRO-1F-NOFIG"
        sec.blocks.append(Paragraph(self.texts.render(intro_id, {
            "NAMES": names, "FIGS": figs, "S_FIG": sfig, "TBL_PEAK": tbl_label})))

        added = p.added_power_mw()

        for f in self.feeders:
            ctx = calc.build_feeder_context(f, p, s)
            # پیک بار
            if f.profile_stats.n_points:
                st = f.profile_stats
                sec.blocks.append(Paragraph(self.texts.render("T-LOAD-PROFILE", {
                    "NAME": self._fl(f.name), "START": st.period_start,
                    "END": st.period_end, "PEAK": fmt(st.peak_p_mw, 2)})))
            else:
                sec.blocks.append(Paragraph(self.texts.render("T-LOAD-PROFILE-NODATA", {
                    "NAME": self._fl(f.name), "PEAK": fmt(f.peak_load_mw, 2)})))

            # طبقه‌بندی بارگذاری (Rule Engine)
            rule = self.engine.first_match("loading", ctx)
            if rule:
                self._emit(sec, "loading", f, rule, self.texts.render(rule.text_id, {
                    "CAPACITY": fmt(f.capacity_mw, 2),
                    "PEAK": fmt(f.peak_load_mw, 2)}))

            # اثر بار جدید بر طبقه بارگذاری
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

        # جدول ۱ — پیک بار
        peak_tbl = self._peak_table()
        if peak_tbl:
            sec.blocks.append(peak_tbl)

        # شکل‌های پروفیل بار (نمودار خودکار) — حتی پس از بازکردن مجدد پروژه
        for f in self.feeders:
            df = self._profile_df(f)
            if df is None or (hasattr(df, "empty") and df.empty):
                continue
            out = self.charts_dir / f"profile_{f.uid}.png"
            if profile_chart(df, f.name, out):
                n = self._next_fig()
                caption = self.texts.render("T-CAP-FIG-PROFILE", {"N": str(n), "NAME": self._fl(f.name)})
                sec.blocks.append(FigureBlock(path=str(out), caption=caption))

        # تصاویر کاربر از نوع network که در مقدمه استفاده نشده‌اند
        sec.blocks.extend(self._figures_for_section(SECTION_LOADING, ("network", "profile")))

        return sec, self._build_forecast(names)

    def _peak_table(self) -> TableSpec | None:
        """جدول ۱ نمونه‌ها: پیک آمپر / پیک مگاوات / ضریب توان — یک ستون به ازای هر فیدر."""
        p = self.project
        feeders = [f for f in self.feeders]
        if not feeders:
            return None
        year = max((f.peak_year for f in self.feeders if f.peak_year), default=None)
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
    # پیش‌بینی — زیربخش بخش ۲
    # ------------------------------------------------------------------
    def _build_forecast(self, names: str) -> ReportSection:
        p, s = self.project, self.settings
        sec = ReportSection(SECTION_FORECAST, "پیش‌بینی پیک بار در افق پنج‌ساله")

        any_fc = False
        for f in self.feeders:
            ctx = calc.build_feeder_context(f, p, s)
            fc = f.forecast
            # v1.2.0: سطرهای خاموش («در گزارش» = Off) در نمودار/متن نمی‌آیند؛
            # مقدارشان در مدل حفظ می‌شود.
            fc_points = f.active_forecast_points
            off_fc = len(fc.points) - len(fc_points)
            # سری «داده واقعی» (ورودی دستی سال‌های گذشته) — مستقل از پروفیل بار
            hist_y, hist_v = list(fc.history_years), list(fc.history_values)
            if not hist_y and f.annual_peaks:
                _peaks = f.active_annual_peaks
                hist_y = [p2.year for p2 in _peaks]
                hist_v = [p2.value_mw for p2 in _peaks]
            fig_path = None
            if fc_points or len(hist_y) >= 2:
                out = self.charts_dir / f"forecast_{f.uid}.png"
                if forecast_chart(hist_y, hist_v, fc_points, out):
                    fig_path = out

            rule = self.engine.first_match("forecast", ctx)
            if rule:
                any_fc = True
                fig_label = str(self.fig_no + 1) if fig_path else "—"
                end_year = fc_points[-1].year if fc_points else fc.end_year()
                end_mw = fc_points[-1].value_mw if fc_points else fc.end_value()
                text = self.texts.render(rule.text_id, {
                    "FIG": fig_label, "NAME": self._fl(f.name),
                    "YEARS": str(s.thresholds.forecast_years),
                    "END_YEAR": str(end_year or "—"),
                    "END_MW": fmt(end_mw, 2),
                    "QUALITY": self._quality_text(fc)})
                self._emit(sec, "forecast", f, rule, text)
                if off_fc:
                    note = self.texts.render("T-FORECAST-ONOFF-NOTE", {
                        "OFF_COUNT": str(off_fc), "NAME": self._fl(f.name)})
                    if note:
                        sec.blocks.append(Paragraph(note))
                if fig_path:
                    n = self._next_fig()
                    caption = self.texts.render("T-CAP-FIG-FORECAST", {
                        "N": str(n), "YEARS": str(s.thresholds.forecast_years),
                        "NAME": self._fl(f.name)})
                    sec.blocks.append(FigureBlock(path=str(fig_path), caption=caption))

        if not any_fc and not self.feeders:
            sec.blocks.append(Paragraph(self.texts.render("T-FORECAST-NO-DATA", {})))

        return sec

    # ------------------------------------------------------------------
    # بخش ۳ — نتایج پخش بار قبل
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

        for f in self.feeders:
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

        sec.blocks.extend(self._figures_for_section(SECTION_BEFORE, ("before",)))
        return sec

    # ------------------------------------------------------------------
    # بخش ۴ — نتایج پخش بار پس از اعمال بار
    # ------------------------------------------------------------------
    def build_after(self) -> ReportSection:
        p, s = self.project, self.settings
        word = "افزایش قدرت" if p.request_type == REQUEST_INCREASE else "اتصال بار جدید"
        sec = ReportSection(SECTION_AFTER, f"نتایج پخش بار پس از {word}")

        names = " و ".join(self._fl(n) for n in self._active_names()) or "—"
        multi = len(self.feeders) > 1
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
        for f in self.feeders:
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
            for domain in ("after_voltage", "current", "loss"):
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
                self._emit(sec, domain, f, rule, self.texts.render(rule.text_id, vals))
            if (f.before.applicant_bus_voltage_pu is not None
                    and f.after.applicant_bus_voltage_pu is not None):
                sec.blocks.append(Paragraph(self.texts.render("T-VOLT-BUS", {
                    "VB1": self._v(f.before.applicant_bus_voltage_pu),
                    "VB2": self._v(f.after.applicant_bus_voltage_pu)})))


        # جدول ۲ — نتایج
        result_tbl = self._result_table()
        if result_tbl:
            sec.blocks.append(result_tbl)
        sec.blocks.extend(self._figures_for_section(SECTION_AFTER, ("after", "other")))
        return sec

    def _result_table(self) -> TableSpec | None:
        """جدول ۲ نمونه‌ها: وضعیت فعلی / اثر افزایش قدرت."""
        p = self.project
        feeders = [f for f in self.feeders if f.before.is_complete() or f.after.is_complete()]
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
    # بخش ۵ — جمع‌بندی
    # ------------------------------------------------------------------
    def build_conclusion(self) -> ReportSection:
        p, s = self.project, self.settings
        sec = ReportSection(SECTION_CONCLUSION, "جمع‌بندی")
        ctx = calc.build_project_context(p, s)
        rule = self.engine.first_match("conclusion", ctx)
        names = " و ".join(self._fl(n) for n in self._active_names()) or "—"
        multi = len(self.feeders) > 1
        if rule:
            text = self.texts.render(rule.text_id, {
                "REQUEST_PHRASE": ("افزایش قدرت" if p.request_type == REQUEST_INCREASE
                                   else "اتصال بار جدید") + f" {p.applicant_name}",
                "APPLICANT_NAME": p.applicant_name,
                "S": "" if not multi else "های", "NAMES": names,
                "MAXCHG": fmt(s.thresholds.voltage_change_max_pct, 0),
                "ISSUE_SUMMARY": calc.issue_summary(p, s)})
            self._emit(sec, "conclusion", None, rule, text)
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
    def _build_study_sections(self) -> list[ReportSection]:
        """بخش‌های مطالعه مصارف سنگین: تقاضا، ایستگاه‌ها، خطوط، متقاضیان همزمان،
        نکات تحلیلی، سناریوهای تأمین و بررسی اقتصادی («تغییرات آرنا» v1.1.0)."""
        from app.core import scenarios as scenario_mod
        from app.core.study import collect_study_results
        from app.report.study_sections import StudySections

        scenario_mod.ensure_scenarios(self.project, self.settings, self.engine)
        self.study_results = collect_study_results(
            self.project, self.settings, self.engine, scenarios=self.project.scenarios)
        builder = StudySections(self.project, self.settings, self.texts,
                                self.study_results, self._next_tbl,
                                self._emit_rule_result)
        return builder.build_all()

    def build_all(self) -> list[ReportSection]:
        """ساخت کل گزارش + اعمال ویرایش‌های دستی کارشناس (بخش ۲۱).

        بخش‌هایی که کاربر آن‌ها را خاموش کرده (تنظیمات → بخش‌های گزارش) در
        گزارش و در تحلیل ظاهر نمی‌شوند؛ داده‌های آن‌ها پاک نمی‌شود.
        """
        intro = self.build_intro()
        loading, forecast = self.build_loading()
        before = self.build_before()
        after = self.build_after()
        study = self._build_study_sections()
        conclusion = self.build_conclusion()
        sections = [intro, loading, forecast, before, after] + study + [conclusion]
        if getattr(self.settings, "include_appendices", True):
            sections += self.build_appendices()
        sections = [sec for sec in sections if self.settings.section_enabled(sec.key)]

        # شکل‌های هر بخش: بخش‌های عمومی شکل‌های خود را در جای مناسب درج کرده‌اند؛
        # برای سایر بخش‌ها (مطالعه، جمع‌بندی، پیوست) شکل‌های منسوب به همان بخش
        # در پایان بخش درج می‌شود (فقط شکل‌هایی که «محل قرارگیری» دارند).
        handled = {SECTION_INTRO, SECTION_LOADING, SECTION_BEFORE, SECTION_AFTER}
        for sec in sections:
            if sec.key in handled:
                continue
            sec.blocks.extend(self._figures_for_section(sec.key))

        # v1.2.0 — شکلی که «محل قرارگیری» صریح دارد ولی بخشش در این گزارش ساخته
        # نشده است (مثلاً بخش مطالعه بدون داده) نباید بی‌صدا حذف شود: بخشی با همان
        # عنوان و ترتیب صحیح ساخته می‌شود و شکل‌ها در آن درج می‌گردند.
        from app.core.report_sections import REPORT_SECTIONS, SECTION_ORDER
        existing = {sec.key for sec in sections}
        for key, label in REPORT_SECTIONS:
            if key in existing or not self.settings.section_enabled(key):
                continue
            figs = self._figures_for_section(key)
            if not figs:
                continue
            extra = ReportSection(key, label)
            extra.blocks.extend(figs)
            sections.append(extra)
            existing.add(key)
        sections.sort(key=lambda sec: SECTION_ORDER.index(sec.key)
                      if sec.key in SECTION_ORDER else len(SECTION_ORDER))

        # متن دستی کارشناس: پاراگراف‌های بخش را جایگزین می‌کند (جداول/شکل‌ها حفظ می‌شوند)
        for sec in sections:
            manual = (self.project.manual_texts or {}).get(sec.key, "").strip()
            if manual:
                new_blocks = []
                inserted = False
                for b in sec.blocks:
                    if isinstance(b, Paragraph) and not inserted:
                        for part in [x.strip() for x in manual.split("\n\n") if x.strip()]:
                            new_blocks.append(Paragraph(part))
                        inserted = True
                    elif not isinstance(b, Paragraph):
                        new_blocks.append(b)
                if not inserted:
                    new_blocks = [Paragraph(x.strip()) for x in manual.split("\n\n") if x.strip()] + new_blocks
                sec.blocks = new_blocks
                setattr(sec, "manual", True)
        return sections
