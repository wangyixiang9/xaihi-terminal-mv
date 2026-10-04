@echo off
chcp 65001 >nul
cd /d "%~dp0"
title XAIHI
where py >nul 2>nul
if not errorlevel 1 (
  py -3 launch_fixed.py %*
) else (
  python launch_fixed.py %*
)
if errorlevel 1 pause
