@echo off
rem ============================================================
rem  Build ReportForge.exe with PyInstaller (onefile, windowed)
rem  Output: dist\ReportForge.exe
rem  ASCII-only batch file.
rem ============================================================
setlocal EnableExtensions
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
chcp 65001 >nul
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

%PY% -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    %PY% -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] PyInstaller installation failed. Check internet connection.
        pause
        exit /b 1
    )
)

echo Building ReportForge.exe ...
%PY% -m PyInstaller --clean --noconfirm ReportForge.spec
if errorlevel 1 (
    echo [ERROR] Build failed. See messages above.
    pause
    exit /b 1
)

echo.
echo Build OK: dist\ReportForge.exe
pause
endlocal
