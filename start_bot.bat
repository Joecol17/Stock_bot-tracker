@echo off
setlocal enabledelayedexpansion
title Stock Trading Bot

:: Always run from the folder this .bat file lives in
cd /d "%~dp0"

echo ============================================================
echo  Stock Trading Bot - Starting Up
echo ============================================================
echo.

:: ---------------------------------------------------------------
:: 1. Load .env file
:: ---------------------------------------------------------------
if not exist ".env" (
    echo [ERROR] .env file not found.
    echo Copy .env.example to .env and fill in your API key.
    pause
    exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    set "line=%%A"
    if not "!line:~0,1!"=="#" (
        if not "%%A"=="" (
            set "%%A=%%B"
        )
    )
)
echo [OK] Config loaded from .env

:: ---------------------------------------------------------------
:: 2. Check API key and secret are set
:: ---------------------------------------------------------------
if "%TRADING212_API_KEY%"=="your_actual_api_key_here" (
    echo.
    echo [ERROR] You haven't set your Trading 212 API key yet.
    echo Open .env and replace "your_actual_api_key_here" with your real key.
    echo.
    pause
    exit /b 1
)
if "%TRADING212_API_KEY%"=="" (
    echo [ERROR] TRADING212_API_KEY is not set in .env
    pause
    exit /b 1
)
if "%TRADING212_API_SECRET%"=="your_actual_api_secret_here" (
    echo.
    echo [ERROR] You haven't set your Trading 212 API secret yet.
    echo Open .env and replace "your_actual_api_secret_here" with your real secret.
    echo.
    pause
    exit /b 1
)
if "%TRADING212_API_SECRET%"=="" (
    echo [ERROR] TRADING212_API_SECRET is not set in .env
    pause
    exit /b 1
)
echo [OK] API key and secret found

:: ---------------------------------------------------------------
:: 3. Check Python is available
:: ---------------------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Download Python from https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found

:: ---------------------------------------------------------------
:: 4. Install / update Python dependencies
:: ---------------------------------------------------------------
echo.
echo Installing dependencies...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] pip install failed. Check your internet connection.
    pause
    exit /b 1
)
echo [OK] Dependencies ready

:: ---------------------------------------------------------------
:: 5. Check Ollama is installed
:: ---------------------------------------------------------------
ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Ollama is not installed or not in PATH.
    echo Download from https://ollama.com/download
    pause
    exit /b 1
)
echo [OK] Ollama found

:: ---------------------------------------------------------------
:: 6. Start Ollama server if not already running
:: ---------------------------------------------------------------
ollama list >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama server...
    start /b "" ollama serve
    timeout /t 3 /nobreak >nul
    echo [OK] Ollama server started
) else (
    echo [OK] Ollama server already running
)

:: ---------------------------------------------------------------
:: 7. Check the configured model is pulled
:: ---------------------------------------------------------------
ollama list | findstr /i "%OLLAMA_MODEL%" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARNING] Model "%OLLAMA_MODEL%" not found locally. Pulling it now...
    echo This may take a few minutes on first run.
    ollama pull %OLLAMA_MODEL%
    if errorlevel 1 (
        echo [ERROR] Could not pull model "%OLLAMA_MODEL%". Check your Ollama installation.
        pause
        exit /b 1
    )
)
echo [OK] Model %OLLAMA_MODEL% is ready

:: ---------------------------------------------------------------
:: 8. Show current settings and confirm before trading
:: ---------------------------------------------------------------
echo.
echo ============================================================
echo  Settings
echo ============================================================
echo  Mode:            %TRADING212_DEMO_MODE% (DEMO=true, LIVE=false)
echo  Model:           %OLLAMA_MODEL%
echo  Trade quantity:  %DEFAULT_TRADE_QUANTITY% share(s) per order
echo  Max daily trades:%MAX_DAILY_TRADES%
echo ============================================================
echo.
if /i "%TRADING212_DEMO_MODE%"=="false" (
    echo  [!] WARNING: LIVE MODE IS ON - real money will be used!
    echo.
)
set /p "confirm=Press ENTER to start the bot, or Ctrl+C to cancel..."

:: ---------------------------------------------------------------
:: 9. Start Mission Control dashboard server (background window)
:: ---------------------------------------------------------------
echo.
echo Starting Mission Control dashboard...
start "Mission Control" cmd /k "cd /d "%~dp0" && python api_server.py"

:: Give Flask a moment to start before opening the browser
timeout /t 2 /nobreak >nul
start "" "http://localhost:5000"
echo [OK] Dashboard opened at http://localhost:5000

:: ---------------------------------------------------------------
:: 10. Run the trading bot (this window)
:: ---------------------------------------------------------------
echo.
echo Starting trading bot... (Press Ctrl+C to stop)
echo.
python auto_trader.py

echo.
echo Bot has stopped.
echo The dashboard window will stay open - close it manually when done.
pause
