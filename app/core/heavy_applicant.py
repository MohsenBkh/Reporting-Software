# -*- coding: utf-8 -*-
"""ماژول مطالعه متقاضیان سنگین — «تغییرات آرنا» v1.1.0.

این dataclass تمام داده‌های مربوط به مطالعه مصارف سنگین را از Project جدا می‌کند
تا بتواند مستقل از Protection Studies مدیریت شود.

ساختار با داده‌های فعلی کاملاً سازگار است و فقط یک لایه abstaction اضافه می‌کند
تا در آینده هر مطالعه مستقلی مدیریت شود.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

# برای جلوگیری از circular import، از TYPE_CHECKING برای type hints استفاده می‌کنیم
# و برای default_factories از sys.modules دسترسی پیدا می‌کنیم
if TYPE_CHECKING:
    from app.core.models import (CoincidentDemand, DemandInfo, Feeder, LineCandidate,
                                 NeighborFeeder, SubstationCandidate, SupplyScenario)


def _make_demand_info():
    """ساخت DemandInfo به‌طور تاخیر‌دار برای جلوگیری از circular import."""
    models = sys.modules.get("app.core.models")
    if models is not None:
        try:
            return models.DemandInfo()
        except AttributeError:
            pass
    # اگر models وجود ندارد، import مستقیم (توجه: این ممکن است circular import ایجاد کند)
    from app.core import models as m
    return m.DemandInfo()


@dataclass
class HeavyApplicantStudy:
    """داده‌های مطالعه متقاضیان سنگین — از مدل Project جدا شده است.

    این ساختار تمام ورودی‌های مطالعه مصارف سنگین را در خود نگه می‌دارد:
    - مشخصات متقاضی
    - نوع درخواست
    - توان موجود / درخواستی
    - اطلاعات تقاضا (با/بدون ضریب همزمانی)
    - ایستگاه‌های نزدیک
    - خطوط نزدیک
    - متقاضیان همزمان
    - فیدرهای همجوار
    - پیک‌های سالانه
    - سناریوهای تأمین
    - نتایج Power Flow قبل و بعد
    - پست‌ها و خطوط نزدیک
    - فیدرهای همجوار
    - Coincident Demand
    - سناریوهای تأمین
    - Cross Validation
    - تحلیل فنی
    """

    # --- اطلاعات پایه متقاضی ---
    applicant_name: str = ""
    request_type: str = "increase"  # new | increase
    existing_power_kw: Optional[float] = None   # توان فعلی (kW)
    requested_power_kw: Optional[float] = None  # توان درخواستی/جدید (kW)

    # --- اطلاعات تقاضا ---
    demand: "DemandInfo" = field(default_factory=_make_demand_info)

    # --- ایستگاه‌های نزدیک ---
    nearby_substations: "list[SubstationCandidate]" = field(default_factory=list)

    # --- خطوط نزدیک ---
    nearby_lines: "list[LineCandidate]" = field(default_factory=list)

    # --- متقاضیان همزمان ---
    coincident_demands: "list[CoincidentDemand]" = field(default_factory=list)

    # --- فیدرهای همجوار (بازآرایی) ---
    neighbor_feeders: "list[NeighborFeeder]" = field(default_factory=list)

    # --- سناریوهای تأمین ---
    scenarios: "list[SupplyScenario]" = field(default_factory=list)

    # --- کنترل ناسازگاری داده‌ها (Cross Validation) ---
    reported_total_additional_load_kw: Optional[float] = None
    demand_used_in_analysis_kw: Optional[float] = None
    network_voltage_kv: Optional[float] = None

    # --- بررسی توپولوژیکی تأمین مشترک ---
    joint_supply_feasible: Optional[bool] = None
    joint_supply_note: str = ""
    joint_supply_evidence: str = ""

    # --- معیار صریح انتخاب سناریو ---
    scenario_selection_criterion: str = ""

    # --- متن‌های ویرایش‌شده کارشناس ---
    manual_texts: dict[str, str] = field(default_factory=dict)

    # --- فیدرها (برای نتایج Power Flow) ---
    feeders: "list[Feeder]" = field(default_factory=list)

    # --- پیک‌های سالانه (مبنای پیش‌بینی) ---
    annual_peaks: list = field(default_factory=list)  # list of tuples (year, value_mw)

    # ---Notes---
    notes: str = ""

    # --- Property: active (On/Off) items ---
    @property
    def active_feeders(self) -> "list[Feeder]":
        return [f for f in self.feeders if getattr(f, "enabled", True)]

    @property
    def active_substations(self) -> "list[SubstationCandidate]":
        return [s for s in self.nearby_substations if getattr(s, "enabled", True)]

    @property
    def active_lines(self) -> "list[LineCandidate]":
        return [ln for ln in self.nearby_lines if getattr(ln, "enabled", True)]

    @property
    def active_coincident_demands(self) -> "list[CoincidentDemand]":
        return [c for c in self.coincident_demands if getattr(c, "enabled", True)]

    @property
    def active_scenarios(self) -> "list[SupplyScenario]":
        return [s for s in self.scenarios if getattr(s, "enabled", True)]

    @property
    def active_neighbor_feeders(self) -> "list[NeighborFeeder]":
        return [n for n in self.neighbor_feeders if getattr(n, "enabled", True)]

    @property
    def active_feeder_names(self) -> list[str]:
        return [f.name for f in self.active_feeders if f.name]

    @property
    def feeder_names(self) -> list[str]:
        return [f.name for f in self.feeders if f.name]

    @property
    def added_power_mw(self) -> Optional[float]:
        """توان اضافه‌شده (MW) — افزایش قدرت یا کل بار جدید."""
        if self.request_type == "increase":
            if self.existing_power_kw is None or self.requested_power_kw is None:
                return None
            return round((self.requested_power_kw - self.existing_power_kw) / 1000.0, 3)
        if self.requested_power_kw is None:
            return None
        return round(self.requested_power_kw / 1000.0, 3)

    @property
    def power_delta_kw(self) -> Optional[float]:
        """افزایش قدرت = توان جدید − توان فعلی."""
        if self.request_type != "increase":
            return None
        if self.existing_power_kw is None or self.requested_power_kw is None:
            return None
        return self.requested_power_kw - self.existing_power_kw

    @property
    def request_type_label(self) -> str:
        """برچسب فارسی نوع درخواست."""
        return "افزایش قدرت" if self.request_type == "increase" else "تأمین برق جدید"

    @property
    def title_text(self) -> str:
        """عنوان گزارش مطابق ادبیات نمونه‌ها."""
        if self.request_type == "increase":
            return (f"افزایش قدرت {self.applicant_name} از قدرت "
                    f"{self._num(self.existing_power_kw)} به {self._num(self.requested_power_kw)} کیلووات")
        return f"تأمین برق به {self.applicant_name} به ظرفیت {self._num(self.requested_power_kw)} کیلووات"

    @staticmethod
    def _num(v: Optional[float]) -> str:
        return "" if v is None else f"{v:,.0f}".replace(",", "")

    def has_study_data(self) -> bool:
        """آیا داده‌های مطالعه مصارف سنگین در پروژه ثبت شده است؟"""
        d = self.demand or _make_demand_info()
        demand_rows = bool(getattr(d, "enabled", True)) and (
            d.without_coincidence_kw is not None
            or d.with_coincidence_kw is not None
            or d.existing_demand_kw is not None
        )
        return bool(demand_rows
                    or self.active_substations
                    or self.active_lines
                    or self.active_coincident_demands
                    or self.active_scenarios
                    or self.reported_total_additional_load_kw is not None
                    or self.demand_used_in_analysis_kw is not None
                    or self.joint_supply_feasible is not None)
