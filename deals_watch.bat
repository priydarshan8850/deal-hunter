@echo off
REM ============================================================
REM  DEAL HUNTER - watch prices while this PC is on
REM  Checks every 30 min, pops a Windows notification + emails
REM  you the moment a discount hits your target price.
REM
REM  Keep this window open (or minimise it). Close it to stop.
REM ============================================================
title Deal Hunter - watching prices
cd /d "%~dp0"
"C:\Users\priyd\AppData\Local\Programs\Python\Python313\python.exe" -u watch.py
pause
