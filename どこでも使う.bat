@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo クラウドに合わせて同期してからHTMLを開きます...
python tools\local_boot_sync.py
if not exist "dist\ロト6予想.html" (
  python tools\build_standalone.py
)
start "" "dist\ロト6予想.html"
