# -*- coding: utf-8 -*-
"""Data Model اصلی نرم‌افزار.

تمام اطلاعات پروژه در همین مدل نگهداری و بین UI و مولد گزارش جابه‌جا می‌شود.
(اصل بخش ۳۲ سند: اطلاعات نباید پراکنده نگهداری شوند)
"""
from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.report_types import (REPORT_TYPE_HEAVY,
                                   REPORT_TYPE_SECTIONALIZER)

REQUEST_NEW = "new"          # تأمین برق جدید
REQUEST_INCREASE = "increase"  # افزایش قدرت

REQUEST_TYPE_LABELS = {REQUEST_NEW: "تأمین برق جدید", REQUEST_INCREASE: "افزایش قدرت"}


def _uid() -> str:
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
@dataclass
class PowerFlowResult:
    """نتیجه پخش بار یک فیدر در یک وضعیت (قبل یا بعد)."""
    current_a: Optional[float] = None            # جریان ابتدای فیدر (A)
    loss_kw: Optional[float] = None              # تلفات (kW)
    min_voltage_pu: Optional[float] = None       # حداقل ولتاژ فیدر (p.u.)
    applicant_bus_voltage_pu: Optional[float] = None  # ولتاژ باس بار متقاضی (p.u.)
    note: str = ""

    def is_complete(self) -> bool:
        return all(v is not None for v in
                   (self.current_a, self.loss_kw, self.min_voltage_pu))


# ---------------------------------------------------------------------------
@dataclass
class Maneuver:
    """مانور / بازآرایی شبکه (اختیاری)."""
    enabled: bool = False
    source_feeder: str = ""     # فیدر مبدأ
    target_feeder: str = ""     # فیدر مقصد
    transferred_mw: Optional[float] = None  # مقدار تقریبی بار منتقل‌شده
    date_jalali: str = ""       # تاریخ مانور
    note: str = ""              # توضیحات کارشناس (عدم قطعیت و ...)


# ---------------------------------------------------------------------------
# v1.3.0 — داده‌های مطالعه سکشنالایزر (اسکلت؛ جزئیات تکمیلی بعداً توسط کارفرما
# ارسال می‌شود — فیلدها اختیاری‌اند و نبود داده = None و نه صفر)
# ---------------------------------------------------------------------------
@dataclass
class SectionalizerInfo:
    """اطلاعات مطالعه نصب سکشنالایزر.

    ساختار آمادهٔ گسترش است: هر فیلد جدیدی که کارفرما مشخص کند بدون شکستن
    پروژه‌های قدیمی به همین dataclass اضافه می‌شود (بازسازی از dict با
    ``_build`` فقط فیلدهای شناخته‌شده را می‌خواند).
    """

    installation_location: str = ""              # شرح محل نصب / نقطه نصب
    feeder_name: str = ""                        # فیدر هدف
    objective: str = ""                          # هدف نصب (مثلاً ایزوله‌سازی منطقه خطا)
    fault_current_ka: Optional[float] = None     # جریان اتصال کوتاه در محل نصب (kA)
    min_fault_current_ka: Optional[float] = None  # حداقل جریان اتصال کوتاه (kA)
    pickup_current_a: Optional[float] = None     # جریان تنظیم پیکاپ (A)
    tms: Optional[float] = None                  # تنظیم زمانی (TMS)
    upstream_device: str = ""                    # تجهیز حفاظتی بالادست
    coordination_note: str = ""                  # توضیح هماهنگی حفاظت

    def is_complete(self) -> bool:
        """حداقل داده‌های لازم برای صدور جدول تنظیمات."""
        return (self.fault_current_ka is not None
                and self.pickup_current_a is not None)


# ---------------------------------------------------------------------------
# «تغییرات آرنا» v1.1.0 — ساختار داده‌های مطالعه مصارف سنگین
# (منطبق با صورت‌مسئله Rule Engine: A) تقاضا B) پست‌ها C) خطوط D) متقاضیان همزمان
#  E) سناریوهای تأمین — همه مقادیر اختیاری: نبود داده = None و نه صفر)
# ---------------------------------------------------------------------------
@dataclass
class DemandInfo:
    """اطلاعات تقاضا (جدول «اطلاعات تقاضا» دفترچه مطالعات)."""

    without_coincidence_kw: Optional[float] = None   # Demand_without_coincidence_kW
    with_coincidence_kw: Optional[float] = None      # Demand_with_coincidence_kW
    existing_demand_kw: Optional[float] = None       # Existing_demand_kW
    enabled: bool = True                             # کلید On/Off — در گزارش/تحلیل لحاظ شود؟

    def coincidence_factor(self) -> Optional[float]:
        """ضریب همزمانی = تقاضای با ضریب / تقاضای بدون ضریب (فقط اگر داده باشد)."""
        if not self.without_coincidence_kw or self.with_coincidence_kw is None:
            return None
        return self.with_coincidence_kw / self.without_coincidence_kw

    def analysis_demand_kw(self) -> Optional[float]:
        """تقاضای مبنای تحلیل — در نبود ضریب همزمانی، بدون جایگزینی فرض نمی‌شود."""
        if self.with_coincidence_kw is not None:
            return self.with_coincidence_kw
        return self.without_coincidence_kw

    def is_complete(self) -> bool:
        return (self.without_coincidence_kw is not None
                and self.with_coincidence_kw is not None)


@dataclass
class SubstationCandidate:
    """ایستگاه نزدیک به محل تقاضا (جدول «ایستگاه‌های نزدیک به محل تقاضا»)."""

    uid: str = field(default_factory=_uid)
    name: str = ""
    distance_km: Optional[float] = None                 # Distance_km
    transformer_capacity_mva: Optional[float] = None    # Transformer_Capacity_MVA (برای هر ترانس)
    t1_loading_percent: Optional[float] = None          # T1_Loading_Percent
    t2_loading_percent: Optional[float] = None          # T2_Loading_Percent
    t1_peak_mva: Optional[float] = None                 # T1_Peak_MVA
    t2_peak_mva: Optional[float] = None                 # T2_Peak_MVA
    feeder_count: Optional[int] = None                  # Feeder_Count
    peak_year: Optional[int] = None
    office: str = ""
    enabled: bool = True                                # کلید On/Off (v1.2.0)

    @property
    def display_name(self) -> str:
        return self.name or "بی‌نام"

    def missing_fields(self) -> list[str]:
        """فیلدهای ناموجود (فارسی) — برای گزارش MISSING_DATA."""
        labels = (("فاصله", self.distance_km),
                  ("ظرفیت ترانس", self.transformer_capacity_mva),
                  ("درصد بارگیری T1", self.t1_loading_percent),
                  ("درصد بارگیری T2", self.t2_loading_percent),
                  ("پیک T1", self.t1_peak_mva),
                  ("پیک T2", self.t2_peak_mva),
                  ("تعداد فیدر", self.feeder_count))
        return [label for label, value in labels if value is None]


@dataclass
class LineCandidate:
    """خط نزدیک به محل تقاضا (جدول «خطوط نزدیک به محل تقاضا»)."""

    uid: str = field(default_factory=_uid)
    name: str = ""
    office: str = ""
    distance_m: Optional[float] = None                  # Distance_m
    peak_mva: Optional[float] = None                    # Peak_MVA
    peak_mw: Optional[float] = None                     # Peak_MW
    peak_current_a: Optional[float] = None              # Peak_Current_A
    vdrop_before_percent: Optional[float] = None        # Voltage_Drop_Before_Percent
    vdrop_after_percent: Optional[float] = None         # Voltage_Drop_After_Percent
    sc_max_ka: Optional[float] = None                   # Max_3Phase_SC_Current_kA
    sc_min_ka: Optional[float] = None                   # Min_3Phase_SC_Current_kA
    max_current_a: Optional[float] = None               # ظرفیت هدایتی (در سند مرجع ارائه نشده)
    peak_year: Optional[int] = None
    enabled: bool = True                                # کلید On/Off (v1.2.0)

    @property
    def display_name(self) -> str:
        return self.name or "بی‌نام"

    def missing_fields(self) -> list[str]:
        labels = (("فاصله", self.distance_m),
                  ("پیک MVA", self.peak_mva),
                  ("افت ولتاژ قبل", self.vdrop_before_percent),
                  ("افت ولتاژ بعد", self.vdrop_after_percent))
        return [label for label, value in labels if value is None]


@dataclass
class CoincidentDemand:
    """تقاضای همزمان / سایر متقاضیان محدوده."""

    uid: str = field(default_factory=_uid)
    name: str = ""
    existing_or_requested_power_kw: Optional[float] = None   # Existing_or_Requested_Power
    new_requested_power_kw: Optional[float] = None           # New_Requested_Power
    delta_power_kw: Optional[float] = None                   # Delta_Power (اگر ثبت نشده باشد محاسبه می‌شود)
    location: str = ""                                       # Location
    supply_feasibility: str = ""                             # Supply_Feasibility
    enabled: bool = True                                     # کلید On/Off (v1.2.0)

    def computed_delta_kw(self) -> Optional[float]:
        """افزایش بار متقاضی: مقدار ثبت‌شده یا تفاضل توان جدید و موجود."""
        if self.delta_power_kw is not None:
            return self.delta_power_kw
        if (self.new_requested_power_kw is not None
                and self.existing_or_requested_power_kw is not None):
            return self.new_requested_power_kw - self.existing_or_requested_power_kw
        return None

    def missing_fields(self) -> list[str]:
        labels = (("نام متقاضی", self.name),
                  ("توان جدید", self.new_requested_power_kw),
                  ("محل", self.location))
        return [label for label, value in labels
                if value is None or (isinstance(value, str) and not value.strip())]


# ---------------------------------------------------------------------------
SCENARIO_NEW_FEEDER = "new_feeder"
SCENARIO_EXISTING_FEEDER = "existing_feeder"
SCENARIO_ALTERNATIVE_FEEDER = "alternative_feeder"
SCENARIO_REARRANGEMENT = "rearrangement"      # v1.2.0 — بازآرایی/انتقال بار
SCENARIO_KIND_LABELS = {
    SCENARIO_NEW_FEEDER: "احداث فیدر جدید",
    SCENARIO_EXISTING_FEEDER: "تأمین از فیدر موجود",
    SCENARIO_ALTERNATIVE_FEEDER: "تأمین از فیدر جایگزین",
    SCENARIO_REARRANGEMENT: "بازآرایی فیدر (انتقال بار)",
}


@dataclass
class SupplyScenario:
    """سناریوی تأمین برق — تولیدشده توسط Rule Engine یا واردشده توسط کارشناس."""

    uid: str = field(default_factory=_uid)
    kind: str = SCENARIO_NEW_FEEDER          # New_Feeder | Existing_Feeder | Alternative_Feeders
    rule_id: str = ""                        # Rule تولیدکننده سناریو
    title: str = ""
    technical_basis: str = ""                # Technical Basis
    required_network_changes: str = ""       # Required Network Changes
    candidate_feeder: str = ""               # Candidate Feeder
    required_equipment: list[str] = field(default_factory=list)   # Required Equipment
    evidence: str = ""                       # Supporting Evidence
    review_status: str = "REQUIRES_ENGINEER_REVIEW"               # Review Status
    # --- بررسی اقتصادی (پارامتریک؛ نبود داده = None) ---
    estimated_cost_million: Optional[float] = None  # Economic_Cost (میلیون تومان)
    cost_items: dict[str, Optional[float]] = field(default_factory=dict)
    cost_excluded_items: list[str] = field(default_factory=list)
    cost_note: str = ""
    # --- مسیر و تجهیزات ---
    required_line_length_km: Optional[float] = None  # Required_Line_Length
    overhead_percent: Optional[float] = None          # Overhead_Percent
    underground_percent: Optional[float] = None       # Underground_Percent
    required_switchgear: str = ""                     # Required_Switchgear
    source: str = "TAV111-10/00"
    source_page: str = ""
    enabled: bool = True                                     # کلید On/Off (v1.2.0)

    @property
    def kind_label(self) -> str:
        return SCENARIO_KIND_LABELS.get(self.kind, self.kind)

    @property
    def display_title(self) -> str:
        return self.title or self.kind_label

    @property
    def key(self) -> str:
        """کلید پایدار شناسایی سناریو (مستقل از uid)."""
        return f"scenario:{self.kind}"

    def missing_fields(self) -> list[str]:
        labels = (("مبنای فنی", self.technical_basis),
                  ("تغییرات لازم شبکه", self.required_network_changes),
                  ("فیدر نامزد", self.candidate_feeder),
                  ("تجهیزات موردنیاز", self.required_equipment),
                  ("شاهد پشتیبان", self.evidence))
        return [label for label, value in labels
                if value is None or (isinstance(value, (str, list)) and not value)]

    def overhead_km(self) -> Optional[float]:
        if self.required_line_length_km is None or self.overhead_percent is None:
            return None
        return self.required_line_length_km * self.overhead_percent / 100.0

    def underground_km(self) -> Optional[float]:
        if self.required_line_length_km is None or self.underground_percent is None:
            return None
        return self.required_line_length_km * self.underground_percent / 100.0


# ---------------------------------------------------------------------------
# v1.2.0 — فیدرهای همجوار (کاندید بازآرایی بار)
# ---------------------------------------------------------------------------
@dataclass
class NeighborFeeder:
    """فیدر نزدیک برای بازآرایی/انتقال بار (ورودی جدید نسخه ۱.۲.۰).

    مقادیر اختیاری‌اند: نبود داده = None (هیچ مقدار جایگزینی ساخته نمی‌شود).
    """

    uid: str = field(default_factory=_uid)
    name: str = ""                                  # نام فیدر همجوار
    office: str = ""                                # امور/دفتر
    substation: str = ""                            # پست مبدأ
    peak_load_mw: Optional[float] = None            # پیک بار فعلی (MW)
    capacity_mw: Optional[float] = None             # معیار/ظرفیت بارگذاری (MW)
    peak_current_a: Optional[float] = None          # پیک جریان (A)
    max_current_a: Optional[float] = None           # حداکثر جریان مجاز هادی (A)
    distance_km: Optional[float] = None             # فاصله تا محل تقاضا (km)
    transferable_mw: Optional[float] = None         # بار قابل انتقال ثبت‌شده (MW) — اختیاری
    note: str = ""
    enabled: bool = True                            # کلید On/Off

    @property
    def display_name(self) -> str:
        return self.name or "بی‌نام"

    def free_capacity_mw(self) -> Optional[float]:
        """ظرفیت آزاد = ظرفیت − پیک (فقط با داده کامل؛ در غیر این صورت None)."""
        if self.capacity_mw is None or self.peak_load_mw is None:
            return None
        return self.capacity_mw - self.peak_load_mw

    def missing_fields(self) -> list[str]:
        labels = (("نام فیدر", self.name), ("پیک بار", self.peak_load_mw))
        return [label for label, value in labels
                if value is None or (isinstance(value, str) and not value.strip())]


# ---------------------------------------------------------------------------
@dataclass
class ForecastPoint:
    year: int = 0
    value_mw: float = 0.0
    source: str = "MANUAL"        # MANUAL | PROFILE | EXCEL | FORECAST
    enabled: bool = True          # v1.2.0 — On/Off ردیف سال (سال خاموش در گزارش/برازش نمی‌آید)


# ---------------------------------------------------------------------------
@dataclass
class ForecastResult:
    """نتیجه پیش‌بینی بار یک فیدر."""
    method: str = "none"        # none | regression | manual
    points: list[ForecastPoint] = field(default_factory=list)          # پیش‌بینی
    history_years: list[int] = field(default_factory=list)             # سال‌های داده تاریخی
    history_values: list[float] = field(default_factory=list)          # پیک تاریخی (MW)
    r2: Optional[float] = None
    slope_mw_per_year: Optional[float] = None
    note: str = ""
    # --- کیفیت داده (v1.0.3) ---
    review_status: str = "OK"            # OK | REQUIRES_ENGINEER_REVIEW
    quality_flags: list[str] = field(default_factory=list)   # کدهای کیفیت (LOW_R2, OUTLIER, ...)
    outlier_years: list[int] = field(default_factory=list)
    jump_years: list[int] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return self.review_status == "REQUIRES_ENGINEER_REVIEW"

    @property
    def available(self) -> bool:
        return self.method != "none" and len(self.points) > 0

    def end_value(self) -> Optional[float]:
        return self.points[-1].value_mw if self.points else None

    def end_year(self) -> Optional[int]:
        return self.points[-1].year if self.points else None


# ---------------------------------------------------------------------------
@dataclass
class ProfileStats:
    """آمار استخراج‌شده از پروفیل بار."""
    peak_p_mw: Optional[float] = None
    peak_date: str = ""                 # تاریخ پیک (شمسی)
    peak_q_mvar: Optional[float] = None
    power_factor_at_peak: Optional[float] = None
    min_p_mw: Optional[float] = None
    max_p_mw: Optional[float] = None
    avg_p_mw: Optional[float] = None
    period_start: str = ""
    period_end: str = ""
    n_points: int = 0


# ---------------------------------------------------------------------------
@dataclass
class Feeder:
    uid: str = field(default_factory=_uid)
    name: str = ""                       # نام فیدر
    substation: str = ""                 # نام پست فوق توزیع
    peak_load_mw: Optional[float] = None  # پیک بار (MW)
    peak_year: Optional[int] = None       # سال پیک (شمسی)
    power_factor: Optional[float] = None  # ضریب توان در پیک
    peak_current_a: Optional[float] = None  # پیک جریان (A)
    max_current_a: Optional[float] = None   # حداکثر جریان مجاز هادی (A)
    capacity_mw: Optional[float] = None     # معیار/ظرفیت بارگذاری (MW)
    before: PowerFlowResult = field(default_factory=PowerFlowResult)
    after: PowerFlowResult = field(default_factory=PowerFlowResult)
    profile_file: str = ""                # نام فایل پروفیل داخل پوشه پروژه
    profile_stats: ProfileStats = field(default_factory=ProfileStats)
    forecast: ForecastResult = field(default_factory=ForecastResult)
    manual_forecast: list[ForecastPoint] = field(default_factory=list)
    # «تغییرات آرنا» — پیک سالانه واقعی که کاربر وارد می‌کند (مبنای پیش‌بینی).
    # پروفیل بار فقط برای تحلیل پروفیل است و مبنای پیش‌بینی قرار نمی‌گیرد.
    annual_peaks: list[ForecastPoint] = field(default_factory=list)
    notes: str = ""
    enabled: bool = True                  # کلید On/Off: در تحلیل و گزارش لحاظ شود؟ (v1.2.0)
    # منبع هر داده ورودی: نام فیلد -> "EXCEL:file" | "CSV:file" | "MANUAL" (v1.0.3)
    data_sources: dict[str, str] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.name or "بی‌نام"

    # --- v1.2.0: کلید «در گزارش» (On/Off) روی هر سطر ورودی ---
    @property
    def active_forecast_points(self) -> list[ForecastPoint]:
        """سطرهای پیش‌بینی روشن (On) — مقادیر سطرهای Off حفظ می‌شود ولی در گزارش نمی‌آید."""
        return [p for p in self.forecast.points if getattr(p, "enabled", True)]

    @property
    def active_manual_forecast(self) -> list[ForecastPoint]:
        return [p for p in self.manual_forecast if getattr(p, "enabled", True)]

    @property
    def active_annual_peaks(self) -> list[ForecastPoint]:
        return [p for p in self.annual_peaks if getattr(p, "enabled", True)]


# ---------------------------------------------------------------------------
IMAGE_KINDS = {
    "location": "موقعیت محل",
    "network": "شبکه / آرایش فیدر",
    "profile": "پروفیل بار",
    "forecast": "پیش‌بینی",
    "before": "خروجی پخش بار — قبل",
    "after": "خروجی پخش بار — بعد",
    "other": "سایر",
}


@dataclass
class ProjectImage:
    uid: str = field(default_factory=_uid)
    file_name: str = ""    # نام فایل کپی‌شده در پوشه images پروژه
    title: str = ""        # عنوان شکل
    kind: str = "other"    # یکی از IMAGE_KINDS
    # --- v1.2.0: محل قرارگیری، ترتیب و کپشن مستقل ---
    section_key: str = ""  # کلید بخش گزارش (خالی = از نوع شکل استخراج می‌شود)
    order: int = 0         # اولویت/ترتیب نمایش در بخش (کمتر = جلوتر)
    caption: str = ""      # کپشن مستقل (خالی = کپشن خودکار برنامه)
    enabled: bool = True   # کلید On/Off: در گزارش بیاید یا نه

    @property
    def kind_label(self) -> str:
        return IMAGE_KINDS.get(self.kind, IMAGE_KINDS["other"])


# ---------------------------------------------------------------------------
REVIEW_PENDING = "pending"
REVIEW_ACCEPTED = "accepted"
REVIEW_EDITED = "edited"
REVIEW_REJECTED = "rejected"
REVIEW_OVERRIDDEN = "overridden"
REVIEW_STATUSES = (REVIEW_PENDING, REVIEW_ACCEPTED, REVIEW_EDITED,
                   REVIEW_REJECTED, REVIEW_OVERRIDDEN)


@dataclass
class ReviewDecision:
    """تصمیم مهندس درباره یک Finding — با Generate مجدد از بین نمی‌رود."""
    status: str = REVIEW_PENDING
    comment: str = ""
    replacement_text: str = ""     # متن جایگزین (Edit / Override)
    auto_text_hash: str = ""       # خلاصه متن خودکار هنگام ثبت تصمیم (تشخیص کهنه‌شدن)
    updated_at: str = ""


# ---------------------------------------------------------------------------
@dataclass
class Project:
    """پروژه مطالعه — واحد اصلی ذخیره‌سازی."""
    uid: str = field(default_factory=_uid)
    name: str = ""                        # عنوان پروژه
    report_number: str = ""               # مثلاً DM-18-001
    date_jalali: str = ""                 # 1405/06/15

    # نوع گزارش (v1.3.0): heavy | sectionalizer | recloser
    report_type: str = REPORT_TYPE_HEAVY
    sectionalizer: SectionalizerInfo = field(default_factory=SectionalizerInfo)

    applicant_name: str = ""              # نام متقاضی
    request_type: str = REQUEST_INCREASE  # new | increase
    existing_power_kw: Optional[float] = None   # توان فعلی (kW)
    requested_power_kw: Optional[float] = None  # توان درخواستی/جدید (kW)

    substation: str = ""                  # نام پست فوق توزیع
    office: str = ""                      # نام امور
    expert_name: str = ""                 # نام کارشناس

    # --- موقعیت محل (عمدتاً برای تأمین برق جدید) ---
    location_note: str = ""               # توضیح موقعیت (مختصات و ...)
    location_distance_m: Optional[float] = None  # فاصله تا نزدیک‌ترین تیر (m)
    cable_suggestion: str = ""            # پیشنهاد نوع کابل

    maneuver: Maneuver = field(default_factory=Maneuver)
    feeders: list[Feeder] = field(default_factory=list)
    images: list[ProjectImage] = field(default_factory=list)

    # --- «تغییرات آرنا» v1.1.0: داده‌های مطالعه مصارف سنگین ---
    demand: DemandInfo = field(default_factory=DemandInfo)
    nearby_substations: list[SubstationCandidate] = field(default_factory=list)
    nearby_lines: list[LineCandidate] = field(default_factory=list)
    neighbor_feeders: list[NeighborFeeder] = field(default_factory=list)   # v1.2.0
    coincident_demands: list[CoincidentDemand] = field(default_factory=list)
    scenarios: list[SupplyScenario] = field(default_factory=list)
    # کنترل ناسازگاری داده‌ها (Cross Validation) — مقادیر مرجع گزارش
    reported_total_additional_load_kw: Optional[float] = None   # Reported_Total_Additional_Load
    demand_used_in_analysis_kw: Optional[float] = None          # Demand used in analysis
    network_voltage_kv: Optional[float] = None                  # سطح ولتاژ شبکه (برای کنترل جریان)
    # بررسی توپولوژیکی تأمین مشترک چند نقطه تقاضا
    joint_supply_feasible: Optional[bool] = None
    joint_supply_note: str = ""
    joint_supply_evidence: str = ""            # شاهد مسیر/آرایش شبکه (GIS/PowerFactory)
    # معیار صریح انتخاب سناریو (در صورت تعریف‌نشدن، موتور توصیه‌ای نمی‌کند)
    scenario_selection_criterion: str = ""

    # متن‌های ویرایش‌شده دستی کارشناس: کلید بخش -> متن
    manual_texts: dict[str, str] = field(default_factory=dict)

    # تصمیمات بازبینی مهندس: کلید Finding -> ReviewDecision (v1.0.3)
    reviews: dict[str, ReviewDecision] = field(default_factory=dict)

    created_at: str = ""
    updated_at: str = ""
    last_report_path: str = ""            # آخرین خروجی Word تولیدشده (v1.0.3)
    last_report_at: str = ""

    # ------------------------------------------------------------------
    @property
    def request_type_label(self) -> str:
        return REQUEST_TYPE_LABELS.get(self.request_type, self.request_type)

    # ------------------------------------------------------------------
    # v1.2.0 — ورودی‌های فعال (On/Off)
    # ------------------------------------------------------------------
    @property
    def active_feeders(self) -> list["Feeder"]:
        """فیدرهایی که کلید «در گزارش» آن‌ها روشن است."""
        return [f for f in self.feeders if getattr(f, "enabled", True)]

    @property
    def active_substations(self) -> list[SubstationCandidate]:
        return [s for s in self.nearby_substations if getattr(s, "enabled", True)]

    @property
    def active_lines(self) -> list[LineCandidate]:
        return [ln for ln in self.nearby_lines if getattr(ln, "enabled", True)]

    @property
    def active_coincident_demands(self) -> list[CoincidentDemand]:
        return [c for c in self.coincident_demands if getattr(c, "enabled", True)]

    @property
    def active_scenarios(self) -> list[SupplyScenario]:
        return [s for s in self.scenarios if getattr(s, "enabled", True)]

    @property
    def active_neighbor_feeders(self) -> list["NeighborFeeder"]:
        return [n for n in self.neighbor_feeders if getattr(n, "enabled", True)]

    @property
    def active_images(self) -> list[ProjectImage]:
        return [i for i in self.images if getattr(i, "enabled", True)]

    @property
    def active_feeder_names(self) -> list[str]:
        return [f.name for f in self.active_feeders if f.name]

    @property
    def feeder_names(self) -> list[str]:
        return [f.name for f in self.feeders if f.name]

    def added_power_mw(self) -> Optional[float]:
        """توان اضافه‌شده (MW) — افزایش قدرت یا کل بار جدید."""
        if self.request_type == REQUEST_INCREASE:
            if self.existing_power_kw is None or self.requested_power_kw is None:
                return None
            return round((self.requested_power_kw - self.existing_power_kw) / 1000.0, 3)
        if self.requested_power_kw is None:
            return None
        return round(self.requested_power_kw / 1000.0, 3)

    def power_delta_kw(self) -> Optional[float]:
        """افزایش قدرت = توان جدید − توان فعلی (محاسبه خودکار، بخش ۳۷)."""
        if self.request_type != REQUEST_INCREASE:
            return None
        if self.existing_power_kw is None or self.requested_power_kw is None:
            return None
        return self.requested_power_kw - self.existing_power_kw

    def title_text(self) -> str:
        """عنوان گزارش مطابق ادبیات نمونه‌ها."""
        if self.report_type == REPORT_TYPE_SECTIONALIZER:
            sz = self.sectionalizer
            where = sz.installation_location or sz.feeder_name or "محل تعیین‌شده"
            return f"مطالعه نصب سکشنالایزر در {where}"
        if self.request_type == REQUEST_INCREASE:
            return (f"افزایش قدرت {self.applicant_name} از قدرت "
                    f"{self._num(self.existing_power_kw)} به {self._num(self.requested_power_kw)} کیلووات")
        return f"تأمین برق به {self.applicant_name} به ظرفیت {self._num(self.requested_power_kw)} کیلووات"

    @staticmethod
    def _num(v: Optional[float]) -> str:
        return "" if v is None else f"{v:,.0f}".replace(",", "")


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------
def to_dict(obj: Any) -> Any:
    """تبدیل بازگشتی dataclass/list/dict به انواع JSON-پذیر."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_dict(v) for v in obj]
    return obj


def _build(cls, data: dict, nested: dict[str, type]) -> Any:
    """ساخت dataclass از dict با احترام به فیلدهای تودرتوی شناخته‌شده.

    فیلدهای لیستی که نوع عضو آن‌ها dataclass است (مثل ForecastResult.points)
    نیز به‌درستی بازسازی می‌شوند — وگرنه پس از بازکردن پروژه، دیکشنری خام
    جای شیء می‌نشیند و دسترسی به ویژگی‌ها خطا می‌دهد.
    """
    list_members = _NESTED_LISTS.get(cls, {})
    kwargs = {}
    hints = {f.name: f for f in dataclasses.fields(cls)}
    for key, value in (data or {}).items():
        if key not in hints:
            continue
        member_type = list_members.get(key)
        if member_type is not None and isinstance(value, list):
            kwargs[key] = [
                _build(member_type, v, _NESTED.get(member_type, {}))
                if isinstance(v, dict) else v
                for v in value
            ]
            continue
        ftype = nested.get(key)
        if ftype is not None and isinstance(value, dict):
            kwargs[key] = _build(ftype, value, _NESTED.get(ftype, {}))
        else:
            kwargs[key] = value
    return cls(**kwargs)


_NESTED: dict[type, dict[str, type]] = {
    PowerFlowResult: {},
    Maneuver: {},
    SectionalizerInfo: {},
    ForecastPoint: {},
    ForecastResult: {},
    ProfileStats: {},
    Feeder: {"before": PowerFlowResult, "after": PowerFlowResult,
             "profile_stats": ProfileStats, "forecast": ForecastResult},
    ProjectImage: {},
    ReviewDecision: {},
    DemandInfo: {},
    SubstationCandidate: {},
    LineCandidate: {},
    CoincidentDemand: {},
    SupplyScenario: {},
    Project: {"maneuver": Maneuver, "demand": DemandInfo,
              "sectionalizer": SectionalizerInfo},
}

# فیلدهای لیستی که عضو آن‌ها dataclass است — هنگام بازسازی از JSON
_NESTED_LISTS: dict[type, dict[str, type]] = {
    ForecastResult: {"points": ForecastPoint},
    Feeder: {"manual_forecast": ForecastPoint, "annual_peaks": ForecastPoint},
    Project: {"feeders": Feeder, "images": ProjectImage,
              "nearby_substations": SubstationCandidate,
              "nearby_lines": LineCandidate,
              "coincident_demands": CoincidentDemand,
              "scenarios": SupplyScenario,
              "neighbor_feeders": NeighborFeeder},
}


def feeder_from_dict(data: dict) -> Feeder:
    f = _build(Feeder, data, _NESTED[Feeder])
    f.manual_forecast = [ForecastPoint(**p) for p in (data.get("manual_forecast") or [])]
    f.annual_peaks = [ForecastPoint(**p) for p in (data.get("annual_peaks") or [])]
    return f


def project_from_dict(data: dict) -> Project:
    p = _build(Project, data, _NESTED[Project])
    p.feeders = [feeder_from_dict(fd) for fd in (data.get("feeders") or [])]
    p.images = [_build(ProjectImage, im, {}) for im in (data.get("images") or [])]
    # داده‌های مطالعه مصارف سنگین (v1.1.0)
    p.nearby_substations = [_build(SubstationCandidate, x, {})
                            for x in (data.get("nearby_substations") or [])]
    p.nearby_lines = [_build(LineCandidate, x, {})
                      for x in (data.get("nearby_lines") or [])]
    p.coincident_demands = [_build(CoincidentDemand, x, {})
                            for x in (data.get("coincident_demands") or [])]
    p.scenarios = [_build(SupplyScenario, x, {})
                   for x in (data.get("scenarios") or [])]
    p.reviews = {}
    for key, rd in (data.get("reviews") or {}).items():
        if isinstance(rd, dict):
            dec = _build(ReviewDecision, rd, {})
            if dec.status not in REVIEW_STATUSES:
                dec.status = REVIEW_PENDING
            p.reviews[key] = dec
    return p
