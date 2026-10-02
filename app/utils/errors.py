# -*- coding: utf-8 -*-
"""مدیریت حرفه‌ای خطا — پیام فارسی قابل‌فهم برای کاربر + ثبت جزئیات فنی در Log (v1.0.3).

* کاربر عادی هرگز Traceback فنی نمی‌بیند.
* هر خطا با Traceback کامل در فایل Log (پوشه کاربر) ثبت می‌شود.
* پیام خطا: علت + راه‌حل (در صورت امکان).
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

LOGGER_NAME = "reportforge"

# نام فیلدهای فنی → عنوان فارسی (برای KeyError / AttributeError)
FIELD_LABELS_FA = {
    "feeder_name": "فیدر مورد مطالعه", "name": "نام", "applicant_name": "نام متقاضی",
    "feeders": "فیدرها", "peak_load_mw": "پیک بار فیدر", "capacity_mw": "معیار بارگذاری",
    "requested_power_kw": "توان درخواستی", "existing_power_kw": "توان فعلی",
    "before": "نتایج پخش بار قبل", "after": "نتایج پخش بار بعد",
    "report_number": "شماره گزارش", "date_jalali": "تاریخ گزارش",
}


def log_dir() -> Path:
    base = os.environ.get("REPORTFORGE_HOME")
    if base:
        d = Path(base)
    elif sys.platform == "win32":
        d = Path(os.environ.get("APPDATA", Path.home())) / "ReportForge"
    else:
        d = Path.home() / ".reportforge"
    d = d / "logs"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = Path(os.environ.get("TEMP", "/tmp")) / "reportforge_logs"
        d.mkdir(parents=True, exist_ok=True)
    return d


def setup_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        h = logging.handlers.RotatingFileHandler(
            log_dir() / "reportforge.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(h)
    except OSError:
        logger.addHandler(logging.NullHandler())
    return logger


@dataclass
class UserError:
    title: str
    message: str       # علت
    solution: str = ""  # راه‌حل

    def text(self) -> str:
        return self.message + (f"\n\nراه‌حل: {self.solution}" if self.solution else "")


class ReportForgeError(Exception):
    """خطای دامنه با پیام فارسی آماده نمایش."""

    def __init__(self, message: str, solution: str = "") -> None:
        super().__init__(message)
        self.message, self.solution = message, solution


def friendly_error(exc: BaseException, context: str = "") -> UserError:
    """تبدیل هر استثنا به پیام فارسی قابل‌فهم."""
    title = context or "خطا"
    if isinstance(exc, ReportForgeError):
        return UserError(title, exc.message, exc.solution)
    if isinstance(exc, KeyError):
        key = str(exc.args[0]) if exc.args else ""
        label = FIELD_LABELS_FA.get(key)
        if label:
            if key == "feeder_name":
                return UserError(title, "اطلاعات فیدر وارد نشده است.", "لطفاً فیدر مورد مطالعه را مشخص کنید.")
            return UserError(title, f"اطلاعات «{label}» وارد نشده است.", f"لطفاً «{label}» را تکمیل کنید.")
        return UserError(title, "یکی از اطلاعات لازم یافت نشد.", "ورودی‌های پروژه را بررسی و تکمیل کنید.")
    if isinstance(exc, PermissionError):
        return UserError(title, "دسترسی به فایل یا پوشه امکان‌پذیر نیست؛ ممکن است فایل در برنامه دیگری (مثل Word) باز باشد.",
                         "فایل را ببندید یا مسیر دیگری انتخاب کنید.")
    if isinstance(exc, FileNotFoundError):
        return UserError(title, "فایل یا پوشه موردنظر پیدا نشد.", "مسیر را بررسی کنید؛ ممکن است فایل جابه‌جا یا حذف شده باشد.")
    if isinstance(exc, (UnicodeDecodeError,)):
        return UserError(title, "رمزگذاری (Encoding) فایل قابل خواندن نیست.", "فایل را با قالب UTF-8 یا Excel ذخیره و دوباره امتحان کنید.")
    if isinstance(exc, (ZeroDivisionError,)):
        return UserError(title, "در یکی از محاسبات، تقسیم بر صفر رخ داد (مقدار پایه صفر است).", "مقادیر ورودی (ظرفیت، جریان، پیک) را بررسی کنید.")
    if isinstance(exc, (ValueError, TypeError)):
        return UserError(title, "یکی از مقادیر واردشده معتبر نیست.", "اعداد و واحدها را بررسی کنید (ولتاژ به pu، توان بار به MW).")
    if isinstance(exc, OSError):
        return UserError(title, "عملیات روی فایل ناموفق بود.", "فضای دیسک و دسترسی به مسیر را بررسی کنید.")
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return UserError(title, "یکی از کتابخانه‌های لازم نصب نیست.", "فایل run.bat را اجرا کنید تا نیازمندی‌ها نصب شوند.")
    return UserError(title, "خطای غیرمنتظره‌ای رخ داد.",
                     f"عملیات را دوباره انجام دهید. اگر تکرار شد فایل Log را برای پشتیبانی ارسال کنید ({log_dir()}).")


def log_exception(exc: BaseException, context: str = "") -> None:
    logging.getLogger(LOGGER_NAME).error("%s: %r", context or "error", exc, exc_info=exc)


def handle_error(parent, exc: BaseException, context: str = "خطا", critical: bool = True) -> UserError:
    """ثبت در Log و نمایش پیام فارسی (بدون Traceback)."""
    log_exception(exc, context)
    ue = friendly_error(exc, context)
    try:
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox.critical if critical else QMessageBox.warning
        box(parent, ue.title, ue.text())
    except Exception:  # noqa: BLE001 — نمایش پیام نباید خود خطا بسازد
        pass
    return ue


def install_excepthook() -> None:
    """خطاهای مدیریت‌نشده: Log + پیام فارسی ساده؛ برنامه بسته نمی‌شود."""
    def hook(exc_type, exc, tb):
        log_exception(exc, "unhandled")
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance():
                ue = friendly_error(exc, "خطای برنامه")
                QMessageBox.critical(None, ue.title, ue.text())
        except Exception:  # noqa: BLE001
            pass
    sys.excepthook = hook
