@echo off
chcp 65001 >nul
set PYTHONUNBUFFERED=1
cd /d "%~dp0"
echo ========================================
echo   ロト6予想 - 常時アクセス自動設定
echo   PCの電源が切れていても使えます
echo ========================================
echo.
echo  GitHub にアップロードして
echo  24時間いつでもアクセスできる URL を作成します。
echo.
pip install -r requirements.txt -q
python tools\setup_cloud_deploy.py
echo.
pause
