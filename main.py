# -*- coding: utf-8 -*-
"""نقطه ورود نرم‌افزار ReportForge — گزارش‌یار مطالعات."""
from __future__ import annotations

import sys
from pathlib import Path

# ----------------------------------------------------------------------------
# مهم: کتابخانه‌های علمی/سندی باید «قبل از» PySide6 وارد شوند.
# جزئیات و هوک: app/pyside_compat.py
# ترتیب این importها را تغییر ندهید (تست test_import_order_before_pyside آن را قفل می‌کند).
# ----------------------------------------------------------------------------
from app import pyside_compat as _pyside_compat  # noqa: F401  isort:skip

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import QApplication

_pyside_compat.patch_six_import_hook()


def _setup_app_icon(app: QApplication) -> None:
    """آیکون برنامه از resource (در exe هم کار می‌کند)."""
    from app.utils.resources import first_existing, resource_path
    ico = first_existing(str(resource_path("logo.ico")), str(resource_path("logo.png")))
    if ico is not None:
        app.setWindowIcon(QIcon(str(ico)))


def _show_splash(app: QApplication):
    """اسپلش اسکرین از resource؛ در نبود فایل None برمی‌گردد."""
    from app.utils.resources import resource_path
    splash_file = resource_path("splash.png")
    if not splash_file.exists():
        return None
    try:
        from PySide6.QtWidgets import QSplashScreen
        pixmap = QPixmap(str(splash_file))
        if pixmap.isNull():
            return None
        splash = QSplashScreen(pixmap)
        splash.show()
        app.processEvents()
        return splash
    except Exception:  # noqa: BLE001 — اسپلش حیاتی نیست
        return None


def main() -> int:
    from app.utils.errors import install_excepthook, setup_logging
    setup_logging()
    app = QApplication(sys.argv)
    install_excepthook()
    app.setApplicationName("ReportForge")
    app.setLayoutDirection(Qt.RightToLeft)

    # فونت رابط کاربری: Vazirmatn (فقط خود برنامه؛ فونت گزارش از تنظیمات می‌آید)
    from app.ui.fonts import apply_ui_font
    apply_ui_font(app)

    _setup_app_icon(app)
    splash = _show_splash(app)

    from app import APP_NAME_FA
    app.setApplicationDisplayName(APP_NAME_FA)

    from app.ui.main_window import MainWindow
    window = MainWindow()

    # Theme توسط MainWindow از تنظیمات اعمال می‌شود (Light/Dark)
    window.show()
    if splash is not None:
        splash.finish(window)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
