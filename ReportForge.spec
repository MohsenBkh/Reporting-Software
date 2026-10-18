# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — ReportForge.exe (onefile, windowed).

منابع همراه (resource/، فونت‌ها، داده‌های قالب و قواعد) داخل exe بسته می‌شوند و
در زمان اجرا از sys._MEIPASS خوانده می‌شوند (app/utils/resources.py).

اصلاح v1.1.2 — رفع کرش شروع برنامه:
    AttributeError: '_SixMetaPathImporter' object has no attribute '_path'
مسیر خطا: shibokensupport.feature_imported → inspect.getsource →
pyi_rth_inspect (inspect.getfile) → importlib._module_repr_from_spec →
list(spec.loader._path)؛ باگ CPython 3.12.0–3.12.3 (در 3.12.4 رفع شده) که با
ماژول‌های مجازی six.moves فعال می‌شود.
راه‌حل: ``runtime_hooks=['app/pyi_rth_reportforge.py']`` که «پیش از هر کد
برنامه» inspect و ماژول‌های مجازی six و هوک Shiboken را ایمن می‌کند.
"""
import os

from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis

# ساخت نسخهٔ اشکال‌زدایی با کنسول (برای دیدن پیام‌ها هنگام خطا):
#     set REPORTFORGE_SPEC_CONSOLE=1 && build_exe.bat
# در حالت عادی پنجره‌ای (console=False) ساخته می‌شود.
_CONSOLE_DEBUG = bool(os.environ.get("REPORTFORGE_SPEC_CONSOLE"))

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
    ],
    hookspath=[],
    runtime_hooks=['app/pyi_rth_reportforge.py'],
    excludes=[
        'tkinter',
        # کتابخانه‌های سنگین و بی‌استفاده (اگر روی سیستم نصب باشند نباید داخل exe بیایند)
        'numba',
        'llvmlite',
        'IPython',
        'matplotlib.tests',
        'numpy.tests',
        'pandas.tests',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ReportForge',
    debug=False,
    strip=False,
    upx=False,
    console=_CONSOLE_DEBUG,
    icon='resource\\logo.ico',
)
