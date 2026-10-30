@echo off
setlocal
cd /d "%~dp0"

rem Never install dependencies into the system Python.
if defined COACH_PYTHON goto custom_python
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul
    if not errorlevel 1 goto launcher_python
)
where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul
    if not errorlevel 1 goto system_python
)
echo Coach requires Python 3.11+ installed on this computer.
echo Install Python from https://www.python.org/downloads/ and rerun.
pause
exit /b 1

:launcher_python
py -3 "%~dp0scripts\bootstrap.py" %*
set "COACH_EXIT=%ERRORLEVEL%"
if not "%COACH_EXIT%"=="0" pause
exit /b %COACH_EXIT%

:system_python
python "%~dp0scripts\bootstrap.py" %*
set "COACH_EXIT=%ERRORLEVEL%"
if not "%COACH_EXIT%"=="0" pause
exit /b %COACH_EXIT%

:custom_python
"%COACH_PYTHON%" "%~dp0scripts\bootstrap.py" %*
set "COACH_EXIT=%ERRORLEVEL%"
if not "%COACH_EXIT%"=="0" pause
exit /b %COACH_EXIT%