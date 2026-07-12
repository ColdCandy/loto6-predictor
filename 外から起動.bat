@echo off
chcp 65001 >nul
set PYTHONUNBUFFERED=1
cd /d "%~dp0"
echo ========================================
echo   ロト6予想 - 外からアクセス版
echo   おばあちゃん家など遠隔から使えます
echo ========================================
echo.
echo  同じWi-Fiが不要です。
echo  表示されたURLをスマホに送るだけ！
echo.
echo  停止するとき → 接続停止.bat をダブルクリック
echo.
echo  ※ Connection error が出る場合:
echo     常時アクセス開く.bat を使うと PCオフでも安定します
echo.
pip install -r requirements.txt -q
python tools\start_remote_server.py
pause
