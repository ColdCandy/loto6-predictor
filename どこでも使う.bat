@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   ロト6予想 - どこでも使える版を作成
echo ========================================
echo.
python tools\build_standalone.py --update
if errorlevel 1 (
    echo エラー: Python が必要です。python.org からインストールしてください。
    pause
    exit /b 1
)
echo.
echo ブラウザで開いています...
start "" "dist\ロト6予想.html"
echo.
echo この dist\ロト6予想.html をコピーすれば
echo Pythonなしでどこでも使えます！
pause
