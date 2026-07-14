@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo  ロト6予想 - PC起動同期
echo ========================================
echo クラウドから取得 → 当選保存 → 学習 → 予想更新
echo.
python tools\local_boot_sync.py
echo.
echo ロト6予想番号 GUI を起動しています...
echo ブラウザが自動で開きます。閉じるにはこのウィンドウで Ctrl+C を押してください。
echo.
pip install -r requirements.txt -q
python -m streamlit run streamlit_app.py --server.enableCORS false --server.enableXsrfProtection false --server.enableWebsocketCompression false
