@echo off
chcp 65001 >nul
set PYTHONUNBUFFERED=1
cd /d "%~dp0"
echo ========================================
echo   ロト6予想 - 外からアクセス版
echo ========================================
echo.
echo  まず安定URL（PCオフでもOK・推奨）:
echo  https://coldcandy.github.io/loto6-predictor/
echo.
echo  この後、高機能版の一時URLも発行します。
echo  停止するとき → 接続停止.bat
echo.
python -m pip install -r requirements.txt -q
python tools\online_healthcheck.py
echo.
python tools\start_remote_server.py
echo.
pause
