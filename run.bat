@echo off
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt || goto :err
py -3 coach.py
exit /b 0
:err
echo Python dependency setup failed.
pause