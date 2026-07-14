@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   ロト6予想 - 常時アクセス（PCオフでもOK）
echo ========================================
echo.
echo  ログイン不要の安定URLを開きます
echo  https://coldcandy.github.io/loto6-predictor/
echo.
start "" "https://coldcandy.github.io/loto6-predictor/"
python tools\online_healthcheck.py
echo.
pause
