@echo off
REM One instant price check right now (then closes automatically).
cd /d "%~dp0"
"C:\Users\priyd\AppData\Local\Programs\Python\Python313\python.exe" -u scripts\check_once.py
echo.
pause
