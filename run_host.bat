@echo off
title DualDesk - Host (Primary PC)
echo ==============================================================
echo              DualDesk - Host (Primary PC)
echo ==============================================================
echo.
echo Starting DualDesk in HOST mode...
echo This PC will share its virtual extended desktop with your
echo second laptop over your local Wi-Fi / Ethernet LAN.
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m dualdesk --role host %*
) else (
    python -m dualdesk --role host %*
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] DualDesk exited with error code %ERRORLEVEL%.
    pause
)
