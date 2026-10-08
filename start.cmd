@echo off
title Story Factory
cd /d "%~dp0"
echo =======================
echo   Story Factory
echo =======================
echo.
echo Starting pipeline...
echo.
python orchestrator.py
echo.
if %ERRORLEVEL% equ 0 (
    echo Pipeline completed successfully.
) else (
    echo Pipeline failed. Check output above for details.
)
echo.
pause
