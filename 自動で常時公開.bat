@echo off

chcp 65001 >nul

set PYTHONUNBUFFERED=1

cd /d "%~dp0"

echo ========================================

echo   ロト6予想 - 自動で常時公開

echo   PCの電源が切れていても使えます

echo ========================================

echo.

pip install -r requirements.txt -q

python tools\auto_sync_cloud.py

echo.

pause

