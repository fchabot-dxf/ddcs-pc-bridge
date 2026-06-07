@echo off
REM ============================================================
REM  Build the DDCS Bridge desktop app -> dist\DDCS-Bridge.exe
REM  (pywebview window + gateway + console, one standalone file)
REM  Double-click to (re)build. Needs Python.
REM ============================================================
cd /d "%~dp0"
python -m pip install --quiet pywebview pyinstaller
python -m PyInstaller --noconfirm --name DDCS-Bridge --onefile --windowed ^
  --add-data "web/ui;web/ui" --collect-all webview desktop.py
echo.
echo Built: dist\DDCS-Bridge.exe
pause
