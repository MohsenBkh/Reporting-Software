# -*- coding: utf-8 -*-
"""پروژه‌های نمونه مشترک بین تست‌ها (سناریوهای مهندسی)."""
from __future__ import annotations

from app.core import forecast as fc_mod
from app.core.models import (CoincidentDemand, DemandInfo, Feeder, LineCandidate,
                             Maneuver, PowerFlowResult, Project, REQUEST_INCREASE,
                             REQUEST_NEW, SubstationCandidate)


def make_project(kind: str = "increase", **over) -> Project:
    p = Project(name="پروژه تست", report_number="DM-18-100", date_jalali="1405/06/15",
                applicant_name="متقاضی تست", request_type=REQUEST_INCREASE,
                existing_power_kw=1000, requested_power_kw=1500, expert_name="مهندس تست")
    if kind == "new":
        p.request_type = REQUEST_NEW
        p.existing_power_kw = None
        p.requested_power_kw = 1500
    for k, v in over.items():
        setattr(p, k, v)
    return p


def make_feeder(name="فیدر ۱", peak=5.0, capacity=7.0, imax=400.0,
                before=(180, 400, 0.97, 0.98), after=(205, 420, 0.96, 0.97),
                years=None, values=None) -> Feeder:
    f = Feeder(name=name, substation="پست تست", peak_load_mw=peak, capacity_mw=capacity,
               max_current_a=imax, power_factor=0.93, peak_year=1405,
               before=PowerFlowResult(*before), after=PowerFlowResult(*after))
    if years:
        f.forecast = fc_mod.linear_forecast(years, values, 5, 3)
    return f


# ---------------------------------------------------------------------------
# پروژه نمونه «مطالعه مصارف سنگین» — بازسازی داده‌های چهار صفحه مرجع
# (TAV111-10/00، صفحات ۱۰ تا ۱۲ از ۱۵) برای تست Rule Engine مطالعه
# ---------------------------------------------------------------------------
def make_study_project(**over) -> Project:
    p = make_project(kind="increase",
                     name="مطالعه تأمین برق متقاضی نمونه",
                     applicant_name="شرکت نمونه صنعتی",
                     existing_power_kw=0, requested_power_kw=1200)
    p.network_voltage_kv = 20.0
    p.reported_total_additional_load_kw = 3000.0
    p.demand_used_in_analysis_kw = 1200.0
    p.demand = DemandInfo(without_coincidence_kw=1200.0, with_coincidence_kw=1200.0,
                          existing_demand_kw=None)
    p.nearby_substations = [
        SubstationCandidate(name="شهرک صنعتی", distance_km=4, transformer_capacity_mva=40,
                            t1_loading_percent=61.05, t2_loading_percent=91.32,
                            t1_peak_mva=27.62, t2_peak_mva=36.53, feeder_count=16,
                            peak_year=1403),
        SubstationCandidate(name="صنعت", distance_km=7, transformer_capacity_mva=18.25,
                            t1_loading_percent=81.21, t2_loading_percent=73.84,
                            t1_peak_mva=14.82, t2_peak_mva=13.47, feeder_count=11,
                            peak_year=1403),
    ]
    p.nearby_lines = [
        LineCandidate(name="فیدر ۴۱۵ فاز ۵", distance_m=30, peak_mva=3.5, peak_mw=3.48,
                      peak_current_a=101, vdrop_before_percent=1.17,
                      vdrop_after_percent=1.85, sc_max_ka=8.63, sc_min_ka=0.710,
                      peak_year=1403),
        LineCandidate(name="فیدر ۴۰۱ دفتر شهرک", distance_m=500, peak_mva=7.55, peak_mw=7.08,
                      peak_current_a=217.8, vdrop_before_percent=3.3,
                      vdrop_after_percent=3.83, sc_max_ka=8.63, sc_min_ka=0.720,
                      peak_year=1403),
    ]
    p.coincident_demands = [
        CoincidentDemand(name="متقاضی الف", existing_or_requested_power_kw=2250,
                         new_requested_power_kw=2750, location="شهرک صنعتی بزرگ",
                         supply_feasibility="—"),
        CoincidentDemand(name="متقاضی ب", existing_or_requested_power_kw=700,
                         new_requested_power_kw=1800, location="شهرک صنعتی بزرگ",
                         supply_feasibility="—"),
        CoincidentDemand(name="متقاضی ج", existing_or_requested_power_kw=1800,
                         new_requested_power_kw=2000, location="شهرک صنعتی بزرگ",
                         supply_feasibility="—"),
    ]
    for k, v in over.items():
        setattr(p, k, v)
    return p
