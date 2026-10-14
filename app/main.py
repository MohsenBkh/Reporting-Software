# -*- coding: utf-8 -*-
"""نقطه ورود نرم‌افزار ReportForge — گزارش‌یار مطالعات.

اسپلش (Splash):
* در فایل اجرایی (exe): اسپلش «Bootloader» PyInstaller بلافاصله پس از اجرا (حتی پیش از
  بالا آمدن پایتون و استخراج فایل‌ها) نمایش داده می‌شود و تا نمایش پنجرهٔ اصلی می‌ماند
  (``pyi_splash.close()`` فقط پس از ``window.show()``).
* در اجرا از سورس (run.bat): اسپلش Qt (``QSplashScreen``) با همان تصویر ``resource/splash.png``
  نمایش داده می‌شود و تا نمایش پنجرهٔ اصلی می‌ماند.
هر دو حالت هم‌زمان فعال نمی‌شوند.
"""
from __future__ import annotations

import sys
from pathlib import Path

# ----------------------------------------------------------------------------
# مهم: کتابخانه‌های علمی/سندی باید «قبل از» PySide6 وارد شوند.
# جزئیات و هوک: app/pyside_compat.py
# ترتیب این importها را تغییر ندهید (تست test_import_order_before_pyside آن را قفل می‌کند).
# ----------------------------------------------------------------------------
from app import pyside_compat as _pyside_compat  # noqa: F401  isort:skip
from app.utils.import_guard import apply_frozen_guards as _apply_frozen_guards  # noqa: F401  isort:skip

_frozen = _apply_frozen_guards()  # محافظ exe: inspect + six + shiboken

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import QApplication

_pyside_compat.patch_six_import_hook()  # پس از PySide6: هوک shiboken را بی‌اثر می‌کند

# اسپلش Bootloader با Tk رسم می‌شود و متن فارسی را درست شکل نمی‌دهد؛ برای آن متن انگلیسی.
BOOT_MESSAGES = {"libs": "Loading libraries...", "ui": "Building user interface...",
                 "data": "Preparing project..."}
SPLASH_MESSAGES = {
    "libs": "در حال بارگذاری کتابخانه‌ها…",
    "ui": "در حال ساخت رابط کاربری…",
    "data": "در حال آماده‌سازی پروژه…",
}


# ----------------------------------------------------------------------------
# اسپلش
# ----------------------------------------------------------------------------
def _bootloader_splash():
    """ماژول ``pyi_splash`` اگر اسپلش Bootloader فعال باشد؛ در غیر این صورت None."""
    try:
        import pyi_splash  # type: ignore[import-not-found]  # فقط در exe با Splash وجود دارد
        return pyi_splash
    except Exception:  # noqa: BLE001
        return None


def close_bootloader_splash() -> None:
    """بستن اسپلش Bootloader (بی‌خطر؛ اگر فعال نباشد کاری نمی‌کند)."""
    pyi = _bootloader_splash()
    if pyi is not None:
        try:
            pyi.close()
        except Exception:  # noqa: BLE001
            pass


def _splash_message(splash, key: str, app: QApplication) -> None:
    """متن وضعیت روی اسپلش و پردازش رویدادها تا اسپلش «یخ» نزند."""
    text = SPLASH_MESSAGES.get(key, key)
    if splash is not None:
        splash.showMessage(text, Qt.AlignBottom | Qt.AlignHCenter, QColor("#FFFFFF"))
    else:
        pyi = _bootloader_splash()
        if pyi is not None:
            try:
                pyi.update_text(BOOT_MESSAGES.get(key, ""))
            except Exception:  # noqa: BLE001
                pass
    app.processEvents()


def _show_splash(app: QApplication):
    """اسپلش Qt از resource؛ اگر اسپلش Bootloader فعال یا فایل موجود نباشد None."""
    if _bootloader_splash() is not None:
        return None                       # در exe اسپلش Bootloader کافی است (دو اسپلش نشان نمی‌دهیم)
    from app.utils.resources import resource_path
    splash_file = resource_path("splash.png")
    if not splash_file.exists():
        return None
    try:
        from PySide6.QtWidgets import QSplashScreen
        pixmap = QPixmap(str(splash_file))
        if pixmap.isNull():
            return None
        splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
        splash.setFont(QFont("Vazirmatn", 11))
        splash.show()
        app.processEvents()
        return splash
    except Exception:  # noqa: BLE001 — اسپلش حیاتی نیست
        return None


def _setup_app_icon(app: QApplication) -> None:
    """آیکون برنامه از resource (در exe هم کار می‌کند)."""
    from app.utils.resources import first_existing, resource_path
    ico = first_existing(str(resource_path("logo.ico")), str(resource_path("logo.png")))
    if ico is not None:
        app.setWindowIcon(QIcon(str(ico)))


# ----------------------------------------------------------------------------
def main() -> int:
    if "--smoke-test" in sys.argv[1:] or "--self-check" in sys.argv[1:]:
        close_bootloader_splash()
        from app.utils.selfcheck import run_smoke_test
        return run_smoke_test()

    from app.utils.errors import install_excepthook, setup_logging
    setup_logging()
    app = QApplication(sys.argv)
    install_excepthook()
    app.setApplicationName("ReportForge")
    app.setLayoutDirection(Qt.RightToLeft)

    # اسپلش در نخستین فرصت (پیش از بارگذاری سنگین ماژول‌ها و ساخت پنجره)
    splash = _show_splash(app)
    _splash_message(splash, "libs", app)

    # فونت رابط کاربری: Vazirmatn (فقط خود برنامه؛ فونت گزارش از تنظیمات می‌آید)
    from app.ui.fonts import apply_ui_font
    apply_ui_font(app)
    _setup_app_icon(app)

    from app import APP_NAME_FA
    app.setApplicationDisplayName(APP_NAME_FA)

    _splash_message(splash, "ui", app)
    try:
        from app.ui.shell.engineering_window import EngineeringWindow
        _splash_message(splash, "data", app)
        window = EngineeringWindow()
    except Exception:
        close_bootloader_splash()           # اسپلش روی پیام خطا نماند
        if splash is not None:
            splash.close()
        raise

    # Theme توسط پنجره از تنظیمات اعمال می‌شود (Light/Dark)
    window.show()
    window.raise_()
    window.activateWindow()
    app.processEvents()
    # اسپلش تا همین‌جا (نمایش پنجرهٔ اصلی) می‌ماند
    if splash is not None:
        splash.finish(window)
    close_bootloader_splash()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
