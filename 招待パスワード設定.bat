@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   招待パスワード設定
echo ========================================
echo.

if not exist ".streamlit\secrets.toml" (
  copy /Y ".streamlit\secrets.toml.example" ".streamlit\secrets.toml" >nul
  echo secrets.toml を作成しました。
) else (
  echo secrets.toml は既にあります。
)

echo.
echo メモ帳で開き、username / password を家族用に書き換えて保存してください。
echo （このファイルは Git に上がらないので安全です）
echo.
notepad ".streamlit\secrets.toml"
echo.
echo 設定後、予想GUI.bat または 外から起動.bat を起動してください。
echo Streamlit Cloud を使う場合は、同じ内容を Cloud の Secrets に貼ります。
echo.
pause
