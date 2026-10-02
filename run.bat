@echo off
rem ============================================================
rem  ReportForge launcher (v1.0.3)
rem  ASCII-only batch file - do NOT add non-English text here.
rem  cmd.exe cannot parse UTF-8 batch files reliably.
rem ============================================================
setlocal EnableExtensions
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
chcp 65001 >nul
title ReportForge

cd /d "%~dp0"
if not exist "app\main.py" (
    echo [ERROR] app\main.py was not found next to run.bat.
    echo         Extract the whole ZIP first and keep the folder layout.
    pause
    exit /b 1
)

rem --- Find a Python interpreter that actually runs ---
set "PY="
for %%C in (python py) do if not defined PY (
    where %%C >nul 2>nul
    if not errorlevel 1 (
        %%C -c "import sys" >nul 2>nul
        if not errorlevel 1 set "PY=%%C"
    )
)
if not defined PY if exist "%LocalAppData%\Programs\Python\Python314\python.exe" set "PY=%LocalAppData%\Programs\Python\Python314\python.exe"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PY=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PY if exist "%ProgramFiles%\Python314\python.exe" set "PY=%ProgramFiles%\Python314\python.exe"
if not defined PY if exist "%ProgramFiles%\Python313\python.exe" set "PY=%ProgramFiles%\Python313\python.exe"
if not defined PY if exist "%ProgramFiles%\Python312\python.exe" set "PY=%ProgramFiles%\Python312\python.exe"
if not defined PY if exist "%ProgramFiles%\Python311\python.exe" set "PY=%ProgramFiles%\Python311\python.exe"
if not defined PY (
    echo [ERROR] Python was not found on this computer.
    echo         Install Python 3.11 or newer from https://www.python.org/downloads/
    echo         During setup, enable "Add python.exe to PATH", then run run.bat again.
    pause
    exit /b 1
)

echo Using Python: %PY%

rem --- Check required libraries; auto-install on first run ---
rem Import scientific libs BEFORE PySide6 (Python 3.12 six.moves hook crash).
%PY% -c "import six,six.moves,dateutil.rrule,numpy,pandas,matplotlib.pyplot,openpyxl,docx,jdatetime,arabic_reshaper,bidi; import PySide6" >nul 2>nul
if errorlevel 1 (
    echo.
    echo Some required libraries are missing.
    echo Installing them now - needs internet, may take a few minutes...
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Library installation failed.
        echo         Check your internet connection, then run run.bat again.
        pause
        exit /b 1
    )
)

echo Starting ReportForge...
%PY% -m app.main %*
if errorlevel 1 pause
endlocal

