# -*- coding: utf-8 -*-
"""فونت رابط کاربری — بارگذاری Vazirmatn از فایل‌های همراه برنامه.

فونت Vazirmatn فقط برای خود نرم‌افزار (منوها، فرم‌ها، جدول‌ها) استفاده می‌شود؛
فونت گزارش Word همچنان از تنظیمات (B Nazanin / B Titr و ...) خوانده می‌شود و
این ماژول هیچ دخالتی در آن ندارد.
"""
from __future__ import annotations

from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent / "fonts"
UI_FONT_FAMILY = "Vazirmatn"
UI_FONT_SIZE_PT = 10.5


def register_ui_fonts() -> list[str]:
    """فایل‌های TTF همراه برنامه را در QFontDatabase ثبت می‌کند.

    خانواده‌هایی که با موفقیت ثبت شده‌اند را برمی‌گرداند (Import های PySide6
    عمداً داخل تابع است تا ترتیب importهای pyside_compat حفظ شود).
    """
    from PySide6.QtGui import QFontDatabase

    families: list[str] = []
    for ttf in sorted(FONT_DIR.glob("*.ttf")):
        try:
            font_id = QFontDatabase.addApplicationFont(str(ttf))
        except Exception:  # noqa: BLE001 — فونت خراب نباید برنامه را بندازد
            continue
        if font_id >= 0:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return families


def apply_ui_font(app) -> bool:
    """Vazirmatn را فونت پیش‌فرض رابط کاربری قرار می‌دهد.

    اگر فونت در دسترس نباشد (نصب نبودن و شکست بارگذاری)، false برمی‌گردد و
    چیزی تغییر نمی‌کند تا Qt از فونت سیستمی استفاده کند.
    """
    from PySide6.QtGui import QFont

    if UI_FONT_FAMILY not in set(register_ui_fonts()):
        return False
    font = QFont(UI_FONT_FAMILY)
    font.setPointSizeF(UI_FONT_SIZE_PT)
    app.setFont(font)
    return True
