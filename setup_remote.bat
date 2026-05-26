@echo off
setlocal enabledelayedexpansion
title Stock Bot · Remote Setup Wizard

echo ============================================================
echo  Stock Bot Tracker ^| Remote / Headless Setup Wizard
echo ============================================================
echo  This sets up the bot to run automatically when your PC
echo  boots, with the dashboard accessible from anywhere.
echo ============================================================
echo.

:: Must run as admin for Task Scheduler
net session >nul 2>&1
if errorlevel 1 (
    echo [!] This script needs Administrator privileges.
    echo     Right-click setup_remote.bat and choose "Run as administrator"
    pause & exit /b 1
)

set "DIR=%~dp0"
set "LAUNCHER=%DIR%headless_launcher.py"
set "PYTHON="

:: Find python
for %%P in (python python3) do (
    %%P --version >nul 2>&1
    if not errorlevel 1 if "!PYTHON!"=="" set "PYTHON=%%P"
)
if "!PYTHON!"=="" (
    echo [ERROR] Python not found. Install from https://www.python.org
    pause & exit /b 1
)
echo [OK] Python: !PYTHON!
echo.

:: ─────────────────────────────────────────────────────────────
:: STEP 1 — Task Scheduler auto-start
:: ─────────────────────────────────────────────────────────────
echo [1/4] Registering auto-start with Windows Task Scheduler...
echo.
echo       The bot will launch automatically 2 minutes after Windows boots.
echo       Task name: StockBotTrader
echo.

:: Remove existing task if present
schtasks /Delete /TN "StockBotTrader" /F >nul 2>&1

:: Create new task: runs on ANY user login, 2 minute delay
schtasks /Create ^
  /TN "StockBotTrader" ^
  /TR "\"%PYTHON%\" \"%LAUNCHER%\"" ^
  /SC ONLOGON ^
  /DELAY 0002:00 ^
  /RL HIGHEST ^
  /F >nul 2>&1

if errorlevel 1 (
    echo [ERROR] Could not create Task Scheduler task.
    echo         Make sure you right-clicked "Run as administrator".
    pause & exit /b 1
)
echo [OK] Task created — bot will auto-start 2 min after login

:: ─────────────────────────────────────────────────────────────
:: STEP 2 — Download cloudflared for remote dashboard access
:: ─────────────────────────────────────────────────────────────
echo.
echo [2/4] Remote dashboard access (Cloudflare Tunnel)...
echo.
echo       This gives you a public URL to view the dashboard
echo       from your phone or laptop anywhere in the world.
echo       Free, no account required.
echo.

if exist "%DIR%cloudflared.exe" (
    echo [OK] cloudflared.exe already present — skipping download
) else (
    echo       Downloading cloudflared.exe (~30 MB)...
    powershell -NonInteractive -Command ^
        "try { Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%DIR%cloudflared.exe' -UseBasicParsing; Write-Output 'OK' } catch { Write-Output ('FAIL: ' + $_.Exception.Message) }"
    if exist "%DIR%cloudflared.exe" (
        echo [OK] cloudflared.exe downloaded
    ) else (
        echo [WARN] Download failed. You can get it manually from:
        echo        https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
        echo        Save as cloudflared.exe in the project folder.
    )
)

:: ─────────────────────────────────────────────────────────────
:: STEP 3 — Auto-shutdown after daily cycle
:: ─────────────────────────────────────────────────────────────
echo.
echo [3/4] Auto-shutdown after daily analysis?
echo.
echo       If YES: PC powers off ~2 min after the bot finishes
echo       each day's analysis. Great for saving power.
echo.
choice /C YN /M "       Auto-shutdown (Y=Yes / N=No)"
echo.

if errorlevel 2 (
    set "SHUTDOWN_VAL=false"
    echo [OK] PC will stay on after each daily cycle
) else (
    set "SHUTDOWN_VAL=true"
    echo [OK] PC will auto-shutdown 2 min after the bot finishes
)

:: Write / update BOT_AUTO_SHUTDOWN in .env
if exist "%DIR%.env" (
    :: Remove existing line, append new one
    powershell -NonInteractive -Command ^
        "$content = Get-Content '%DIR%.env' | Where-Object { $_ -notmatch '^BOT_AUTO_SHUTDOWN=' }; $content + 'BOT_AUTO_SHUTDOWN=!SHUTDOWN_VAL!' | Set-Content '%DIR%.env' -Encoding utf8"
) else (
    echo BOT_AUTO_SHUTDOWN=!SHUTDOWN_VAL! > "%DIR%.env"
)

:: ─────────────────────────────────────────────────────────────
:: STEP 4 — Windows auto-login (optional)
:: ─────────────────────────────────────────────────────────────
echo.
echo [4/4] Windows auto-login...
echo.
echo       For the bot to start WITHOUT someone sitting at the PC,
echo       Windows needs to log in automatically after the BIOS wakes it.
echo.
echo       Opening Windows auto-login settings (netplwiz)...
echo       In the window that opens:
echo         1. Uncheck "Users must enter a username and password"
echo         2. Click OK and enter your Windows password
echo.
choice /C YN /M "       Open netplwiz now?"
if not errorlevel 2 (
    start "" netplwiz
    timeout /t 2 /nobreak >nul
)

:: ─────────────────────────────────────────────────────────────
:: SUMMARY
:: ─────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo  Setup complete!
echo ============================================================
echo.
echo  What happens now:
echo   1. Your PC boots (BIOS schedule or Wake-on-LAN)
echo   2. Windows auto-logs in (if you set it in step 4)
echo   3. 2 minutes later, the bot starts automatically
echo   4. The dashboard is available at:
echo      Local:  http://localhost:5000
echo      Remote: Check the sidebar — URL shown when tunnel starts
echo.
echo  IMPORTANT — BIOS scheduled wake:
echo   To have the PC turn on by itself at a set time each day,
echo   see REMOTE_SETUP.md for step-by-step BIOS instructions.
echo   (Every motherboard is different — can't automate this part)
echo.
echo  WAKE-ON-LAN from your phone:
echo   Install "Wake On Lan" app (Android) or "Mocha WOL" (iPhone)
echo   Your PC MAC address:
for /f "skip=3 tokens=3" %%i in ('getmac /fo table /nh') do (
    if "!MAC!"=="" set "MAC=%%i"
)
echo   %MAC%
echo.
echo   Save that MAC address in your WoL app.
echo ============================================================
echo.
pause
