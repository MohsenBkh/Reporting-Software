# -*- coding: utf-8 -*-
"""تنظیمات نرم‌افزار — هیچ Thresholdی در کد Hard-Code نمی‌شود (بخش ۱۱ و ۳۰ سند)."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

if getattr(sys, "frozen", False):
    # حالت exe: پوشه کنار برنامه ممکن است موقت/فقط‌خواندنی باشد؛
    # تنظیمات باید ماندگار بماند → AppData کاربر
    DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "ReportForge" / "data"
else:
    DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"


@dataclass
class FontSettings:
    body_font: str = "B Nazanin"
    body_size: int = 13
    heading_font: str = "B Titr"
    heading1_size: int = 16
    heading2_size: int = 14
    latin_font: str = "Times New Roman"


@dataclass
class ThresholdSettings:
    """حدآستانه‌های موتور قواعد — قابل ویرایش از صفحه تنظیمات."""
    voltage_min_pu: float = 0.95          # حد پایین ولتاژ مجاز (p.u.)
    voltage_max_pu: float = 1.05          # حد بالای ولتاژ مجاز (p.u.)
    voltage_change_max_pct: float = 5.0   # حداکثر تغییر مجاز ولتاژ پس از اعمال بار (٪)
    loading_light_pct: float = 25.0       # زیر این مقدار: کم‌بار
    loading_normal_pct: float = 70.0      # زیر این مقدار: عادی و نسبتاً کم‌بار
    loading_semi_pct: float = 85.0        # زیر این مقدار: نسبتاً پربار
    loading_heavy_pct: float = 100.0      # زیر/مساوی: پربار — بالاتر: بحرانی
    loss_change_warn_pct: float = 15.0    # هشدار افزایش تلفات (٪)
    forecast_years: int = 5               # افق پیش‌بینی
    forecast_min_history: int = 3         # حداقل داده تاریخی برای رگرسیون
    growth_low_pct: float = 2.0           # رشد سالانه زیر این مقدار: پایدار (٪)
    growth_high_pct: float = 4.0          # رشد سالانه بالای این مقدار: قابل توجه (٪)
    # --- کیفیت داده پیش‌بینی (v1.0.3) ---
    forecast_r2_min: float = 0.6          # حداقل R² قابل قبول برای اتکا به رگرسیون
    forecast_outlier_sigma: float = 3.0   # آستانه باقیمانده (Leave-One-Out) برای Outlier
    forecast_jump_pct: float = 25.0       # جهش/افت سالانه بیش از این مقدار = تغییر ساختاری (مانور؟)
    forecast_max_gap_years: int = 1       # بیشترین فاصله مجاز بین سال‌های متوالی داده
    # --- محدوده‌های منطقی برای اعتبارسنجی ورودی (v1.0.3) ---
    plausible_voltage_min_pu: float = 0.5
    plausible_voltage_max_pu: float = 1.3
    plausible_pf_min: float = 0.5
    plausible_current_max_a: float = 2000.0
    plausible_peak_max_mw: float = 40.0


@dataclass
class AppSettings:
    company_name: str = "شرکت توزیع نیروی برق استان اردبیل"
    unit_name: str = "معاونت مهندسی و برنامه‌ریزی و مطالعات فنی"
    office_name: str = "گروه هدف‌گذاری مهندسی و نظارت"
    company_logo: str = ""                # مسیر لوگوی صفحه جلد؛ خالی = resource/logo.png همراه برنامه
    template_file: str = ""               # فایل قالب متن کاربر؛ خالی = پیش‌فرض‌های داخلی
    report_prefix: str = "DM-18-"         # پیشوند شماره گزارش
    output_dir: str = ""                  # خروجی پیش‌فرض؛ خالی = داخل پوشه پروژه
    recent_projects: list[str] = field(default_factory=list)
    theme: str = "light"                  # light | dark
    template_name: str = "standard"       # قالب گزارش
    include_appendices: bool = True       # پیوست ردیابی داده/تصمیمات مهندس
    open_folder_after: bool = True        # باز کردن پوشه خروجی پس از تولید
    fonts: FontSettings = field(default_factory=FontSettings)
    thresholds: ThresholdSettings = field(default_factory=ThresholdSettings)

    # ------------------------------------------------------------------
    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> "AppSettings":
        s = cls()
        if SETTINGS_FILE.exists():
            try:
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                s._apply(data)
            except (json.JSONDecodeError, OSError):
                pass
        return s

    def _apply(self, data: dict[str, Any]) -> None:
        for section in ("fonts", "thresholds"):
            if section in data and isinstance(data[section], dict):
                sub = getattr(self, section)
                for f in fields(sub):
                    if f.name in data[section]:
                        setattr(sub, f.name, data[section][f.name])
        for name in ("company_name", "unit_name", "office_name", "report_prefix", "output_dir",
                     "company_logo", "template_file"):
            if name in data:
                setattr(self, name, data[name])
        if data.get("theme") in ("light", "dark"):
            self.theme = data["theme"]
        for flag in ("include_appendices", "open_folder_after"):
            if isinstance(data.get(flag), bool):
                setattr(self, flag, data[flag])
        if isinstance(data.get("template_name"), str):
            self.template_name = data["template_name"]
        if isinstance(data.get("recent_projects"), list):
            self.recent_projects = [str(x) for x in data["recent_projects"]]

    # ------------------------------------------------------------------
    def add_recent(self, project_path: str, max_items: int = 10) -> None:
        p = str(Path(project_path).resolve())
        self.recent_projects = [p] + [x for x in self.recent_projects if x != p]
        self.recent_projects = self.recent_projects[:max_items]
        self.save()

    def thresholds_flat(self) -> dict[str, float]:
        """حدآستانه‌ها به‌صورت dict تخت برای موتور قواعد."""
        return {k: v for k, v in asdict(self.thresholds).items()}
