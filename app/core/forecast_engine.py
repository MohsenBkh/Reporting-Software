# -*- coding: utf-8 -*-
"""Forecast Engine — زیرساخت روش‌های پیش‌بینی، مستقل از UI و Study.

    ForecastEngine
    ├── linear_regression   ← فعال (به ``app.core.forecast.linear_forecast`` تکیه دارد)
    ├── holt                ← برنامه‌ریزی‌شده (Interface آماده؛ پیاده‌سازی نشده)
    ├── ets                 ← برنامه‌ریزی‌شده
    └── arima               ← برنامه‌ریزی‌شده

روش‌های پیاده‌سازی‌نشده هرگز عدد تولید نمی‌کنند؛ فراخوانی آن‌ها
``ForecastMethodUnavailable`` می‌دهد. برای افزودن روش جدید کافی است یک
``ForecastMethod`` ثبت شود (``ForecastEngine.register``).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

METHOD_LINEAR = "linear_regression"
METHOD_HOLT = "holt"
METHOD_ETS = "ets"
METHOD_ARIMA = "arima"


class ForecastMethodUnavailable(NotImplementedError):
    """روش پیش‌بینی هنوز پیاده‌سازی نشده است."""


@dataclass
class ForecastRequest:
    years: list[int]
    values: list[float]
    horizon: int = 5
    min_points: int = 3
    thresholds: Any = None                       # ThresholdSettings (اختیاری)
    maneuver_years: Optional[list[int]] = None


class ForecastMethod(ABC):
    key: str = ""
    label: str = ""
    available: bool = False

    @abstractmethod
    def forecast(self, request: ForecastRequest):
        """بازگرداندن ``ForecastResult``."""


class LinearRegressionMethod(ForecastMethod):
    key, label, available = METHOD_LINEAR, "رگرسیون خطی", True

    def forecast(self, request: ForecastRequest):
        from app.core.forecast import linear_forecast      # ایمپورت تنبل: بدون چرخه
        return linear_forecast(request.years, request.values, request.horizon,
                               request.min_points, request.thresholds,
                               request.maneuver_years)


class _PlannedMethod(ForecastMethod):
    available = False

    def __init__(self, key: str, label: str) -> None:
        self.key, self.label = key, label

    def forecast(self, request: ForecastRequest):
        raise ForecastMethodUnavailable(
            f"روش پیش‌بینی «{self.label}» هنوز پیاده‌سازی نشده است.")


@dataclass
class ForecastEngine:
    methods: dict[str, ForecastMethod] = field(default_factory=dict)

    def register(self, method: ForecastMethod) -> None:
        self.methods[method.key] = method

    def get(self, key: str) -> ForecastMethod:
        try:
            return self.methods[key]
        except KeyError:
            raise KeyError(f"روش پیش‌بینی ناشناخته: {key}") from None

    def available_methods(self) -> list[ForecastMethod]:
        return [m for m in self.methods.values() if m.available]

    def forecast(self, key: str, request: ForecastRequest):
        return self.get(key).forecast(request)


def default_engine() -> ForecastEngine:
    engine = ForecastEngine()
    engine.register(LinearRegressionMethod())
    for key, label in ((METHOD_HOLT, "Holt"), (METHOD_ETS, "ETS"), (METHOD_ARIMA, "ARIMA")):
        engine.register(_PlannedMethod(key, label))
    return engine
