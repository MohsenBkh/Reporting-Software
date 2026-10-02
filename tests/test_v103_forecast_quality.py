# -*- coding: utf-8 -*-
"""v1.0.3 — کنترل کیفیت داده پیش‌بینی."""
import pytest

from app.core import forecast as fc
from app.core.settings import ThresholdSettings

Y = [1399 + i for i in range(6)]


def test_clean_series_is_ok():
    r = fc.linear_forecast(Y, [10, 10.6, 11.1, 11.7, 12.2, 12.8])
    assert r.method == "regression" and r.review_status == fc.STATUS_OK
    assert r.quality_flags == [] and r.r2 > 0.95 and len(r.points) == 5


def test_too_few_points_requires_review_and_no_fake_numbers():
    r = fc.linear_forecast([1403, 1404], [10, 11])
    assert r.method == "none" and r.points == []
    assert r.needs_review and fc.FLAG_INSUFFICIENT in r.quality_flags


def test_low_r2_flagged():
    r = fc.linear_forecast(Y, [10, 14, 9, 13, 10, 12])
    assert r.needs_review and fc.FLAG_LOW_R2 in r.quality_flags


def test_outlier_detected_with_year():
    r = fc.linear_forecast([1399 + i for i in range(8)], [10, 10.5, 11, 11.5, 30, 12.5, 13, 13.5])
    assert fc.FLAG_OUTLIER in r.quality_flags and 1403 in r.outlier_years


def test_structural_jump_flagged_as_possible_maneuver():
    r = fc.linear_forecast(Y, [10, 10.4, 10.9, 6.5, 7, 7.4])
    assert fc.FLAG_STRUCTURAL in r.quality_flags and 1402 in r.jump_years


def test_gap_in_years_flagged():
    r = fc.linear_forecast([1399, 1400, 1403, 1404], [10, 10.5, 12, 12.4])
    assert fc.FLAG_GAPS in r.quality_flags and r.needs_review


def test_constant_series_does_not_crash():
    r = fc.linear_forecast(Y, [5] * 6)
    assert r.method == "regression" and fc.FLAG_FLAT in r.quality_flags
    assert all(p.value_mw == 5 for p in r.points)


def test_thresholds_are_configurable_not_hardcoded():
    vals = [10, 10.6, 11.1, 11.7, 12.2, 12.8]
    strict = ThresholdSettings(forecast_r2_min=1.01)
    assert fc.linear_forecast(Y, vals, th=strict).needs_review
    assert not fc.linear_forecast(Y, vals).needs_review


def test_manual_forecast_untouched():
    r = fc.manual_forecast([(1406, 5.5), (1407, 5.0)])
    assert r.method == "manual" and not r.needs_review
    assert [p.value_mw for p in r.points] == [5.5, 5.0]


def test_duplicate_years_and_nan_are_cleaned():
    r = fc.linear_forecast([1400, 1400, 1401, 1402, 1403], [1, 2, float("nan"), 3, 4])
    assert r.history_years == sorted(set(r.history_years))
