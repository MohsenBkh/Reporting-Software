# -*- coding: utf-8 -*-
"""پیش‌بارگذاری وابستگی‌ها و ایزوله‌سازی تنظیمات برای تست‌ها."""
import os
import tempfile

# مسیر جداگانه برای تنظیمات تا اجرای تست‌ها فایل تنظیمات همراه برنامه را بازنویسی نکند
os.environ.setdefault("REPORTFORGE_HOME", tempfile.mkdtemp(prefix="reportforge_test_"))

from app import pyside_compat as _pyside_compat  # noqa: F401,E402
