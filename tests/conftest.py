# -*- coding: utf-8 -*-
"""پیش‌بارگذاری محیط تست:
۱) مسیر داده‌ها (settings) به پوشهٔ موقت منتقل می‌شود تا فایل تنظیمات
   نصب‌شده (app/data/settings.json) با اجرای تست‌ها تغییر نکند.
۲) پیش‌بارگذاری six/pandas قبل از PySide6 تا تست‌های UI کرش نکنند.
"""
import os
import tempfile

os.environ.setdefault("REPORTFORGE_HOME", tempfile.mkdtemp(prefix="rf_home_"))

from app import pyside_compat as _pyside_compat  # noqa: F401,E402
