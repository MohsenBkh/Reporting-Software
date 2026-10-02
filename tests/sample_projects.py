# -*- coding: utf-8 -*-
"""پروژه‌های نمونه مشترک بین تست‌ها (سناریوهای مهندسی)."""
from __future__ import annotations

from app.core import forecast as fc_mod
from app.core.models import (Feeder, Maneuver, PowerFlowResult, Project,
                             REQUEST_INCREASE, REQUEST_NEW)


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
