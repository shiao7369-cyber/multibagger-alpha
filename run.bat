@echo off
title Multibagger Alpha Screener
color 0A
echo ============================================================
echo   Multibagger Alpha Screener
echo   Based on Yartseva (2025) CAFE Working Paper #33
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 未安裝或未加入 PATH
    echo 請至 https://www.python.org/downloads/ 下載安裝
    pause
    exit /b 1
)

:: Install dependencies if needed
echo [1/2] 安裝 / 更新依賴套件...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [WARN] 部分套件安裝失敗，嘗試繼續...
)

:: Start server
echo [2/2] 啟動伺服器...
echo.
echo  >>> 請開啟瀏覽器前往: http://127.0.0.1:5000
echo  >>> 按下 Ctrl+C 可停止伺服器
echo.
python app.py

pause
