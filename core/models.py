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
@dataclass
class ForecastPoint:
    year: int = 0
    value_mw: float = 0.0


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
    notes: str = ""
    # منبع هر داده ورودی: نام فیلد -> "EXCEL:file" | "CSV:file" | "MANUAL" (v1.0.3)
    data_sources: dict[str, str] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.name or "بی‌نام"


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
    ForecastPoint: {},
    ForecastResult: {},
    ProfileStats: {},
    Feeder: {"before": PowerFlowResult, "after": PowerFlowResult,
             "profile_stats": ProfileStats, "forecast": ForecastResult},
    ProjectImage: {},
    ReviewDecision: {},
    Project: {"maneuver": Maneuver},
}

# فیلدهای لیستی که عضو آن‌ها dataclass است — هنگام بازسازی از JSON
_NESTED_LISTS: dict[type, dict[str, type]] = {
    ForecastResult: {"points": ForecastPoint},
    Feeder: {"manual_forecast": ForecastPoint},
    Project: {"feeders": Feeder, "images": ProjectImage},
}


def feeder_from_dict(data: dict) -> Feeder:
    f = _build(Feeder, data, _NESTED[Feeder])
    f.manual_forecast = [ForecastPoint(**p) for p in (data.get("manual_forecast") or [])]
    return f


def project_from_dict(data: dict) -> Project:
    p = _build(Project, data, _NESTED[Project])
    p.feeders = [feeder_from_dict(fd) for fd in (data.get("feeders") or [])]
    p.images = [_build(ProjectImage, im, {}) for im in (data.get("images") or [])]
    p.reviews = {}
    for key, rd in (data.get("reviews") or {}).items():
        if isinstance(rd, dict):
            dec = _build(ReviewDecision, rd, {})
            if dec.status not in REVIEW_STATUSES:
                dec.status = REVIEW_PENDING
            p.reviews[key] = dec
    return p
