@echo off
title DualDesk - Client (Second Laptop / Receiver)
echo ==============================================================
echo        DualDesk - Client (Second Laptop / Receiver)
echo ==============================================================
echo.
echo Starting DualDesk in CLIENT mode...
echo This laptop will act as your auxiliary extended monitor.
echo Go to the Devices tab to scan for or enter your Host PC's IP.
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m dualdesk --role client %*
) else (
    python -m dualdesk --role client %*
)

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] DualDesk exited with error code %ERRORLEVEL%.
    pause
)
