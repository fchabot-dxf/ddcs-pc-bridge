@echo off
REM ============================================================
REM  DDCS Bridge - START THE GATEWAY
REM  Just DOUBLE-CLICK this file. Your browser opens the console.
REM  To STOP the gateway: close this black window.
REM ============================================================
REM  Starts unconfigured. Open the SETUP tab and enter your controller disk
REM  (a network share, e.g. \\10.0.0.50\cncdisk). For Modbus progress on the
REM  Expert, also tick Beacons (then restart). V4.1 = leave Beacons off.
REM ============================================================
cd /d "%~dp0"
echo Starting the DDCS Bridge gateway...  (close this window to stop)
echo.
python -m fairy.bridge run --serve --open --no-slave --console web/ui --backend local --root _bridge_data
echo.
echo Gateway stopped. Press any key to close.
pause >nul
