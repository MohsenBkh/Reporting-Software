# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — ReportForge.exe (onefile, windowed).

منابع همراه (resource/، فونت‌ها، داده‌های قالب و قواعد) داخل exe بسته می‌شوند و
در زمان اجرا از sys._MEIPASS خوانده می‌شوند (app/utils/resources.py).
"""
from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis

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
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter'],
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
    console=False,
    icon='resource\\logo.ico',
)
