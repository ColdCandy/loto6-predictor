@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   Streamlit Cloud を半自動で設定
echo ========================================
echo.
echo  Redeploy は Git push で自動です。
echo  Secrets だけ「貼る」作業が1回必要です（安全のため）。
echo.
python tools\setup_streamlit_cloud.py
echo.
pause
