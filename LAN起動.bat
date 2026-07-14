@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   ロト6予想 - LAN公開 全機能
echo   スマホ・タブレットからも使えます
echo ========================================
echo.
echo  クラウド同期・学習を実行してから起動します...
python tools\local_boot_sync.py
echo.
echo  停止するとき → 接続停止.bat をダブルクリック
echo.
pip install -r requirements.txt -q
python tools\start_lan_server.py
pause
