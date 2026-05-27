@echo off
setlocal enabledelayedexpansion
title Stock Bot - ngrok Free Permanent URL Setup

echo.
echo  ============================================================
echo   Stock Bot Tracker -- ngrok Free Permanent URL Setup
echo   100%% free, no credit card, URL never changes on restart.
echo  ============================================================
echo.

set "DIR=%~dp0"
set "NGROK_EXE=%DIR%ngrok.exe"
set "DOCS_CONFIG=%DIR%docs\config.js"
set "ENV_FILE=%DIR%.env"

:: ─────────────────────────────────────────────────────────────────────────────
:: STEP 1 — Download ngrok.exe
:: ─────────────────────────────────────────────────────────────────────────────
echo  STEP 1/4  --  Download ngrok
echo  ─────────────────────────────────────────────────────────
echo.

if exist "!NGROK_EXE!" (
    echo [OK] ngrok.exe already present -- skipping download
    goto :step2
)

echo  Downloading ngrok for Windows (x64)...
powershell -NonInteractive -Command ^
    "try { $zip = [System.IO.Path]::GetTempFileName() + '.zip'; Invoke-WebRequest -Uri 'https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip' -OutFile $zip -UseBasicParsing; Expand-Archive -Path $zip -DestinationPath '%DIR%' -Force; Remove-Item $zip; Write-Output 'DOWNLOAD_OK' } catch { Write-Output ('FAIL: ' + $_.Exception.Message) }" 2>nul

if exist "!NGROK_EXE!" (
    echo [OK] ngrok.exe downloaded and extracted
) else (
    echo [WARN] Automatic download failed.
    echo.
    echo  Please download ngrok manually:
    echo    1. Go to:  https://ngrok.com/download
    echo    2. Download the Windows (AMD64) zip
    echo    3. Extract ngrok.exe into this folder:
    echo       %DIR%
    echo    4. Re-run this script
    echo.
    pause & exit /b 1
)

:step2
:: ─────────────────────────────────────────────────────────────────────────────
:: STEP 2 — Create free ngrok account and get auth token
:: ─────────────────────────────────────────────────────────────────────────────
echo.
echo  STEP 2/4  --  Create free ngrok account
echo  ─────────────────────────────────────────────────────────
echo.
echo  1. Open:  https://dashboard.ngrok.com/signup
echo     (sign up free -- no credit card required)
echo.
echo  2. After signing in, go to:
echo     https://dashboard.ngrok.com/get-started/your-authtoken
echo.
echo  3. Copy your authtoken (long string starting with numbers_)
echo.
set /p NGROK_TOKEN="  Paste your ngrok authtoken here: "

if "!NGROK_TOKEN!"=="" (
    echo.
    echo [ERROR] No authtoken entered. Cannot continue without it.
    pause & exit /b 1
)

echo.
echo  Saving authtoken to ngrok config...
"!NGROK_EXE!" config add-authtoken "!NGROK_TOKEN!"
if errorlevel 1 (
    echo [ERROR] Failed to save authtoken. Check it and try again.
    pause & exit /b 1
)
echo [OK] Authtoken saved

:: ─────────────────────────────────────────────────────────────────────────────
:: STEP 3 — Get your free static domain
:: ─────────────────────────────────────────────────────────────────────────────
echo.
echo  STEP 3/4  --  Get your free static domain
echo  ─────────────────────────────────────────────────────────
echo.
echo  ngrok gives you ONE free static domain per account.
echo.
echo  1. Open:  https://dashboard.ngrok.com/domains
echo  2. Click "New Domain" (or "Create Domain")
echo  3. ngrok assigns you a random permanent URL like:
echo       proud-rabbit-definitely.ngrok-free.app
echo  4. Copy that domain name (WITHOUT https://)
echo.
set /p NGROK_DOMAIN="  Paste your static domain (e.g. proud-rabbit-definitely.ngrok-free.app): "

if "!NGROK_DOMAIN!"=="" (
    echo.
    echo [ERROR] No domain entered. Cannot continue.
    pause & exit /b 1
)

:: Strip https:// if user pasted the full URL
set "NGROK_DOMAIN=!NGROK_DOMAIN:https://=!"

echo [OK] Static domain: !NGROK_DOMAIN!
set "PERM_URL=https://!NGROK_DOMAIN!"

:: ─────────────────────────────────────────────────────────────────────────────
:: STEP 4 — Save to .env and docs/config.js
:: ─────────────────────────────────────────────────────────────────────────────
echo.
echo  STEP 4/4  --  Saving configuration
echo  ─────────────────────────────────────────────────────────
echo.

:: Write NGROK_STATIC_DOMAIN to .env (remove old line if present, add new one)
if exist "!ENV_FILE!" (
    powershell -NonInteractive -Command ^
        "$lines = Get-Content '!ENV_FILE!' | Where-Object { $_ -notmatch '^NGROK_STATIC_DOMAIN=' }; ($lines + 'NGROK_STATIC_DOMAIN=!NGROK_DOMAIN!') | Set-Content '!ENV_FILE!' -Encoding utf8"
    echo [OK] Added NGROK_STATIC_DOMAIN to .env
) else (
    echo NGROK_STATIC_DOMAIN=!NGROK_DOMAIN! >> "!ENV_FILE!"
    echo [OK] Created .env with NGROK_STATIC_DOMAIN
)

:: Update docs/config.js
if exist "!DOCS_CONFIG!" (
    powershell -NonInteractive -Command ^
        "$url = '!PERM_URL!'; $c = Get-Content '!DOCS_CONFIG!' -Raw; $c = [regex]::Replace($c, 'https://[^\"'']+', $url); Set-Content '!DOCS_CONFIG!' $c -Encoding utf8"
    echo [OK] Updated docs\config.js with permanent URL
)

:: ─────────────────────────────────────────────────────────────────────────────
:: Summary
:: ─────────────────────────────────────────────────────────────────────────────
echo.
echo  ============================================================
echo   Setup complete!  Your permanent URL:
echo.
echo   !PERM_URL!
echo.
echo   This URL NEVER changes -- bookmark it on your phone!
echo  ============================================================
echo.
echo  To push the URL to your GitHub Pages remote dashboard:
echo    git add docs\config.js
echo    git commit -m "Set permanent ngrok URL"
echo    git push
echo.
echo  The bot will use this URL automatically from now on.
echo  (ngrok.exe must stay in the project folder)
echo.
pause
