@echo off
REM ============================================================
REM  DDCS Bridge - START THE GATEWAY
REM  Just DOUBLE-CLICK this file. Your browser opens the console.
REM  To STOP the gateway: close this black window.
REM ============================================================
REM  This default works on ANY PC with no CNC hardware (UI/dev).
REM  For the REAL machine: remove "--no-slave", and set the disk +
REM  serial port, e.g.:  --dest "\\192.168.0.99\CNCDISK" --port COM6
REM ============================================================
cd /d "%~dp0"
echo Starting the DDCS Bridge gateway...  (close this window to stop)
echo.
python -m fairy.bridge run --serve --open --no-slave --console web/ui --backend local --root _bridge_data --dest _bridge_data\controller
echo.
echo Gateway stopped. Press any key to close.
pause >nul
