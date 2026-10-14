# -*- coding: utf-8 -*-
"""v2.0.0 — Forecast Engine: رابط روش‌ها؛ روش‌های برنامه‌ریزی‌شده عدد تولید نمی‌کنند."""
from __future__ import annotations

from app.core.forecast_engine import (ForecastMethodUnavailable, ForecastRequest,
                                      default_engine)


def test_registry_lists_planned_and_available_methods():
    eng = default_engine()
    assert set(eng.methods) == {"linear_regression", "holt", "ets", "arima"}
    assert [m.key for m in eng.available_methods()] == ["linear_regression"]


def test_planned_methods_raise_instead_of_inventing_numbers():
    eng = default_engine()
    for key in ("holt", "ets", "arima"):
        try:
            eng.forecast(key, ForecastRequest(years=[1, 2, 3], values=[1.0, 2.0, 3.0]))
        except ForecastMethodUnavailable:
            continue
        raise AssertionError(key)


def test_unknown_method_key():
    try:
        default_engine().get("nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_linear_method_delegates_to_existing_linear_forecast(monkeypatch):
    import app.core.forecast as fc
    called = {}
    monkeypatch.setattr(fc, "linear_forecast", lambda *a, **k: called.setdefault("args", a) or "ok")
    default_engine().forecast("linear_regression",
                              ForecastRequest(years=[1, 2, 3], values=[1.0, 2.0, 3.0], horizon=2))
    assert called["args"][2] == 2
