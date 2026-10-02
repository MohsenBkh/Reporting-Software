# -*- coding: utf-8 -*-
"""سازگاری PySide6 با six/dateutil روی Python 3.12.

Import-Hook خود PySide6 (shibokensupport) اگر برای اولین بار six.moves را
بعد از PySide6 ببیند، با خطای زیر کرش می‌کند:

    AttributeError: '_SixMetaPathImporter' object has no attribute '_path'

این ماژول باید قبل از PySide6 import شود. پس از بارگذاری PySide6 هم
``patch_six_import_hook`` هوک را برای ماژول‌های six بی‌اثر می‌کند تا
ورودهای دیگر (مثل تست‌ها) ایمن بمانند.
"""
from __future__ import annotations

import sys

import six  # noqa: F401
import six.moves  # noqa: F401
from six.moves import _thread, range  # noqa: F401

if sys.platform == "win32":
    from six.moves import winreg  # noqa: F401

import dateutil.tz  # noqa: F401
import dateutil.rrule  # noqa: F401
import numpy  # noqa: F401
import pandas  # noqa: F401
import matplotlib  # noqa: F401
import matplotlib.pyplot  # noqa: F401
import matplotlib.dates  # noqa: F401
import openpyxl  # noqa: F401
import docx  # noqa: F401


def patch_six_import_hook() -> None:
    """هوک shiboken را برای بسته‌ی six دور می‌زند (پس از import شدن PySide6)."""
    feat = sys.modules.get("shibokensupport.feature")
    if feat is None:
        return
    orig = getattr(feat, "feature_imported", None)
    if orig is None or getattr(orig, "_reportforge_patched", False):
        return

    def _safe_feature_imported(module, *args, **kwargs):  # noqa: ANN001
        name = getattr(module, "__name__", "") or ""
        if name == "six" or name.startswith("six."):
            return None
        return orig(module, *args, **kwargs)

    _safe_feature_imported._reportforge_patched = True  # type: ignore[attr-defined]
    feat.feature_imported = _safe_feature_imported
