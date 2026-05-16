@echo off
setlocal enabledelayedexpansion
title Stock Bot · Mission Control

echo ============================================================
echo  Stock Bot Tracker
echo ============================================================
echo.

:: ---------------------------------------------------------------
:: 1. Check Python
:: ---------------------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Download from https://www.python.org/downloads/
    pause & exit /b 1
)
echo [OK] Python found

:: ---------------------------------------------------------------
:: 2. Install / update dependencies
:: ---------------------------------------------------------------
echo Installing dependencies...
python -m pip install -r requirements.txt --quiet
echo [OK] Dependencies ready

:: ---------------------------------------------------------------
:: 3. Load .env
:: ---------------------------------------------------------------
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
        set "line=%%A"
        if not "!line:~0,1!"=="#" if not "%%A"=="" set "%%A=%%B"
    )
    echo [OK] Config loaded from .env
) else (
    echo [INFO] No .env found - copy .env.example to .env to configure your API key
)

:: ---------------------------------------------------------------
:: 4. Start Ollama if installed
:: ---------------------------------------------------------------
ollama --version >nul 2>&1
if not errorlevel 1 (
    ollama list >nul 2>&1
    if errorlevel 1 (
        echo Starting Ollama...
        start /b "" ollama serve
        timeout /t 3 /nobreak >nul
    )
    if defined OLLAMA_MODEL (
        ollama list | findstr /i "%OLLAMA_MODEL%" >nul 2>&1
        if errorlevel 1 (
            echo Pulling model %OLLAMA_MODEL%...
            ollama pull %OLLAMA_MODEL%
        )
        echo [OK] Ollama ready ^(%OLLAMA_MODEL%^)
    )
) else (
    echo [INFO] Ollama not found - AI decisions will be skipped
)

:: ---------------------------------------------------------------
:: 5. Show settings & warn if live mode
:: ---------------------------------------------------------------
echo.
echo ============================================================
if defined TRADING212_DEMO_MODE (
    echo  Mode:   %TRADING212_DEMO_MODE%  ^(DEMO=true / LIVE=false^)
) else (
    echo  Mode:   DEMO ^(default^)
)
if defined OLLAMA_MODEL    echo  Model:  %OLLAMA_MODEL%
if defined DEFAULT_TRADE_QUANTITY echo  Qty:    %DEFAULT_TRADE_QUANTITY% share^(s^) per order
if defined MAX_DAILY_TRADES echo  Limit:  %MAX_DAILY_TRADES% trades/day
echo ============================================================
if /i "%TRADING212_DEMO_MODE%"=="false" (
    echo.
    echo  [!] WARNING: LIVE MODE - real money will be used!
)
echo.
set /p "confirm=Press ENTER to launch, or Ctrl+C to cancel..."

:: ---------------------------------------------------------------
:: 6. Launch dashboard in a separate window + open browser
:: ---------------------------------------------------------------
echo.
echo Opening dashboard at http://localhost:5000 ...
start "Dashboard" cmd /k "python dashboard.py"
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: ---------------------------------------------------------------
:: 7. Run the trading bot
:: ---------------------------------------------------------------
echo Starting trading bot... (Ctrl+C to stop)
echo.
python auto_trader.py

echo.
echo Bot stopped. Close the Dashboard window manually if needed.
pause
