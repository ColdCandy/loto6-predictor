@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  ========================================
echo    接続を完全に停止します
echo  ========================================
echo.
python tools\stop_server.py
echo.
pause
