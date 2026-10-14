# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — ReportForge.exe (onefile، پنجره‌ای، با اسپلش Bootloader).

اسپلش: ``resource/splash.png`` توسط Bootloader بلافاصله با اجرای exe نمایش داده می‌شود
(پیش از استخراج فایل‌ها و بالا آمدن پایتون) و ``app/main.py`` آن را فقط پس از نمایش پنجرهٔ
اصلی می‌بندد (``pyi_splash.close()``). اسپلش Bootloader به tkinter/Tcl-Tk نیاز دارد؛ اگر روی
سیستم ساخت نصب نباشد، بدون آن ساخته می‌شود و اسپلش Qt (پس از بالا آمدن پایتون) نمایش داده
می‌شود. برای غیرفعال‌کردن عمدی:  set REPORTFORGE_NO_BOOTSPLASH=1

منابع همراه (resource/، فونت‌ها، داده‌های قالب و قواعد) داخل exe بسته می‌شوند و در زمان اجرا
از sys._MEIPASS خوانده می‌شوند (app/utils/resources.py).

اصلاح v1.1.2 — رفع کرش شروع برنامه:
    AttributeError: '_SixMetaPathImporter' object has no attribute '_path'
باگ CPython 3.12.0–3.12.3 با ماژول‌های مجازی six.moves؛ راه‌حل:
``runtime_hooks=['app/pyi_rth_reportforge.py']`` که پیش از هر کد برنامه inspect و six و
هوک Shiboken را ایمن می‌کند.
"""
import os

from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis

# ساخت نسخهٔ اشکال‌زدایی با کنسول (برای دیدن پیام‌ها هنگام خطا):
#     set REPORTFORGE_SPEC_CONSOLE=1 && build_exe.bat
_CONSOLE_DEBUG = bool(os.environ.get("REPORTFORGE_SPEC_CONSOLE"))

# ---- اسپلش Bootloader (نیازمند tkinter) ----
_SPLASH_FILE = os.path.join('resource', 'splash.png')
_USE_BOOT_SPLASH = False
if os.environ.get("REPORTFORGE_NO_BOOTSPLASH"):
    print("INFO: bootloader splash disabled by REPORTFORGE_NO_BOOTSPLASH")
elif not os.path.exists(_SPLASH_FILE):
    print("WARNING: %s not found; building without bootloader splash" % _SPLASH_FILE)
else:
    try:
        import tkinter  # noqa: F401
        _USE_BOOT_SPLASH = True
    except Exception:  # noqa: BLE001
        print("WARNING: tkinter is not available; building without bootloader splash "
              "(Qt splash will be used instead).")

_EXCLUDES = [
    # کتابخانه‌های سنگین و بی‌استفاده (اگر روی سیستم نصب باشند نباید داخل exe بیایند)
    'numba',
    'llvmlite',
    'IPython',
    'matplotlib.tests',
    'numpy.tests',
    'pandas.tests',
]
if not _USE_BOOT_SPLASH:
    _EXCLUDES.append('tkinter')        # بدون اسپلش Bootloader نیازی به Tk نیست

a = Analysis(
    ['reportforge.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resource', 'resource'),
        ('app/ui/fonts', 'app/ui/fonts'),
        ('app/report/data', 'app/report/data'),
        ('app/rules/data', 'app/rules/data'),
    ],
    hiddenimports=[
        # بسته‌های مجازی six باید داخل exe باشند (app/pyside_compat.py)
        'six',
        'six.moves',
        'six.moves._thread',
        'six.moves.winreg',
        # محافظ‌ها به‌صورت ماژول صریح بارگذاری می‌شوند
        'app.utils.import_guard',
        # رابط Engineering Desktop (v2.0.0) — import درون تابع در main()
        'app.ui.shell.engineering_window',
        'app.rules.domains',
        'app.report.composer',
    ],
    hookspath=[],
    runtime_hooks=['app/pyi_rth_reportforge.py'],
    excludes=_EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

_exe_args = [pyz, a.scripts, a.binaries, a.zipfiles, a.datas]
if _USE_BOOT_SPLASH:
    from PyInstaller.building.splash import Splash

    splash = Splash(
        _SPLASH_FILE,
        binaries=a.binaries,
        datas=a.datas,
        text_pos=(24, 580),            # متن وضعیت پایین تصویر (۸۱۲×۶۰۹)
        text_size=11,
        text_color='white',
        minify_script=True,
        always_on_top=True,
    )
    _exe_args += [splash, splash.binaries]

exe = EXE(
    *_exe_args,
    [],
    name='ReportForge',
    debug=False,
    strip=False,
    upx=False,
    console=_CONSOLE_DEBUG,
    icon='resource\\logo.ico',
)
