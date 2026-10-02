# -*- coding: utf-8 -*-
"""مسیر منابع همراه برنامه (لوگو، اسپلش، فونت، داده‌ها).

هم در حالت اجرا از سورس (dev) و هم در exe ساخته‌شده با PyInstaller کار می‌کند:
  - onefile: فایل‌ها در sys._MEIPASS (پوشه استخراج موقت) کنار هم قرار می‌گیرند
  - onedir : پوشه resource کنار فایل exe کپی می‌شود
  - dev    : پوشه resource در ریشه پروژه (کنار run.bat)
"""
from __future__ import annotations

import sys
from pathlib import Path

RESOURCE_DIRNAME = "resource"


def app_root() -> Path:
    """ریشه نصب برنامه — در exe پوشه فایل اجرایی، در dev پوشه ریشه پروژه."""
    if getattr(sys, "frozen", False):  # PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    """مسیر یک فایل از پوشه resource را برمی‌گرداند (اگر وجود نداشت، مسیر مرجع)."""
    rel = Path(RESOURCE_DIRNAME, *parts)
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:                       # PyInstaller onefile / onedir
        candidates.append(Path(meipass) / rel)
    candidates.append(app_root() / rel)   # onedir (کنار exe) یا dev (کنار سورس)
    for cand in candidates:
        if cand.exists():
            return cand
    return candidates[-1]


def first_existing(*paths: str) -> Path | None:
    """اولین مسیر موجود از ورودی‌ها؛ برای fallback (مثلاً ico → png)."""
    for p in paths:
        path = Path(p)
        if path.exists():
            return path
    return None
