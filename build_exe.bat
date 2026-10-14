@echo off
rem ============================================================
rem  Build ReportForge.exe with PyInstaller (onefile, windowed)
rem  Output: dist\ReportForge.exe
rem  - splash screen: resource\splash.png (shown at launch, closed
rem    when the main window is displayed)
rem  - icon: resource\logo.ico   - fonts: app\ui\fonts\*.ttf
rem  ASCII-only batch file.
rem ============================================================
setlocal EnableExtensions
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
chcp 65001 >nul
title ReportForge - build exe
cd /d "%~dp0"

set "PY="
for %%C in (python py) do if not defined PY (
    where %%C >nul 2>nul
    if not errorlevel 1 (
        %%C -c "import sys" >nul 2>nul
        if not errorlevel 1 set "PY=%%C"
    )
)
if not defined PY (
    echo [ERROR] Python was not found. Install Python 3.11+ first.
    pause
    exit /b 1
)
echo Using Python: %PY%

rem --- 1) Check the files that are bundled into the exe ---
set "MISSING="
for %%F in ("resource\logo.ico" "resource\logo.png" "resource\splash.png" "app\ui\fonts\Vazirmatn-Regular.ttf" "app\ui\fonts\Vazirmatn-Medium.ttf" "app\ui\fonts\Vazirmatn-SemiBold.ttf" "app\ui\fonts\Vazirmatn-Bold.ttf" "ReportForge.spec" "reportforge.py") do (
    if not exist %%F (
        echo [ERROR] Missing required file: %%~F
        set "MISSING=1"
    )
)
if defined MISSING (
    pause
    exit /b 1
)

rem --- 2) Libraries (runtime + PyInstaller) ---
%PY% -c "import six,dateutil.rrule,numpy,pandas,matplotlib,openpyxl,docx,jdatetime,arabic_reshaper,bidi,PySide6,PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo Installing build requirements - needs internet ...
    %PY% -m pip install -r requirements-build.txt
    if errorlevel 1 (
        echo [ERROR] Library installation failed. Check your internet connection.
        pause
        exit /b 1
    )
)

rem --- 3) Bootloader splash needs tkinter (Tcl/Tk) ---
%PY% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo [WARN] tkinter is not installed in this Python.
    echo        The exe will be built WITHOUT the bootloader splash;
    echo        the Qt splash is shown a little later at start-up instead.
    echo        To get the instant splash, re-install Python with "tcl/tk and IDLE".
)

rem --- 4) Build ---
echo Building ReportForge.exe ...
%PY% -m PyInstaller --clean --noconfirm ReportForge.spec
if errorlevel 1 (
    echo [ERROR] Build failed. See messages above.
    pause
    exit /b 1
)

echo.
echo Build OK: dist\ReportForge.exe
echo.

rem ------------------------------------------------------------
rem  Start-up self-check: runs the produced exe with --smoke-test
rem  and prints ReportForge-smoke.txt.
rem  "start /wait" is required because the exe is a GUI app.
rem ------------------------------------------------------------
if exist "dist\ReportForge-smoke.txt" del "dist\ReportForge-smoke.txt"
echo Running start-up self-check ...
start /wait "" "dist\ReportForge.exe" --smoke-test
if exist "dist\ReportForge-smoke.txt" (
    echo.
    type "dist\ReportForge-smoke.txt"
) else (
    echo [WARN] self-check report was not created. Run it manually:
    echo        dist\ReportForge.exe --smoke-test
)

echo.
echo Done. The application itself is at: dist\ReportForge.exe
pause
endlocal
