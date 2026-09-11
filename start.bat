@echo off
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0run.py" demo %*
) else (
  python "%~dp0run.py" demo %*
)
if errorlevel 1 pause
