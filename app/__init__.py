# -*- coding: utf-8 -*-
"""ReportForge — گزارش‌یار مطالعات فنی اتصال مصارف سنگین به شبکه توزیع.

نکتهٔ مهم: محافظ‌های ورود (import-guard) پیش از هر چیز اجرا می‌شوند تا برنامه در
حالت exe ساخته‌شده با PyInstaller هم بدون خطا بالا بیاید:

    AttributeError: '_SixMetaPathImporter' object has no attribute '_path'

جزئیات و علت ریشه‌ای: ``app/utils/import_guard.py``.
"""
from __future__ import annotations

from app.utils import import_guard as _import_guard  # noqa: F401  isort:skip

_import_guard.apply_frozen_guards()

APP_NAME = "ReportForge"
APP_NAME_FA = "گزارش‌یار مطالعات"
APP_VERSION = "1.4.0"
