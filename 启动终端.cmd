@echo off
chcp 65001 >nul
cd /d "%~dp0"
mode con cols=197 lines=60 >nul 2>nul
where py >nul 2>nul
if not errorlevel 1 (
 py -3 player.py %*
) else (
 python player.py %*
)
if errorlevel 1 pause
