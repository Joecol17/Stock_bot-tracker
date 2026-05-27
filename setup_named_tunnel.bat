@echo off
setlocal enabledelayedexpansion
title Stock Bot - Named Tunnel Setup (Permanent URL)

echo.
echo  ============================================================
echo   Stock Bot Tracker -- Named Tunnel Setup
echo   Gives you a PERMANENT public URL that never changes.
echo  ============================================================
echo.
echo  What this does in ~5 minutes:
echo    1. Links cloudflared to your free Cloudflare account
echo    2. Creates a named tunnel called "stockbot"
echo    3. Guides you to assign a permanent public URL
echo    4. Saves tunnel_config.yml + updates docs\config.js
echo.
echo  Requirements:
echo    * Free Cloudflare account  (cloudflare.com/sign-up)
echo    * cloudflared.exe in this folder (run setup_remote.bat first)
echo.

set "DIR=%~dp0"
set "CF_EXE=%DIR%cloudflared.exe"
set "CONFIG_FILE=%DIR%tunnel_config.yml"
set "DOCS_CONFIG=%DIR%docs\config.js"
set "CF_CREDS_DIR=%USERPROFILE%\.cloudflared"

:: ─────────────────────────────────────────────────────────────────────────────
:: Pre-flight: check cloudflared.exe
:: ─────────────────────────────────────────────────────────────────────────────
if not exist "!CF_EXE!" (
    echo [ERROR] cloudflared.exe not found in this folder.
    echo.
    echo  Run setup_remote.bat first — it downloads cloudflared automatically.
    echo.
    pause & exit /b 1
)
echo [OK] cloudflared.exe found

echo.
echo  Press any key to begin...
pause >nul
echo.

:: ─────────────────────────────────────────────────────────────────────────────
:: STEP 1/4 — Cloudflare login
:: ─────────────────────────────────────────────────────────────────────────────
echo  ─────────────────────────────────────────────────────────
echo  STEP 1/4  --  Sign in to Cloudflare
echo  ─────────────────────────────────────────────────────────
echo.
echo  Your browser will open.
echo    - Sign in at cloudflare.com (or create a free account)
echo    - Click "Authorize" when asked
echo.
echo  If you don't have an account, open cloudflare.com/sign-up
echo  in your browser BEFORE pressing Enter below.
echo.
pause

"!CF_EXE!" tunnel login
if errorlevel 1 (
    echo.
    echo [ERROR] Login failed or was cancelled.
    echo         Make sure you clicked "Authorize" in the browser.
    pause & exit /b 1
)
echo.
echo [OK] Authenticated with Cloudflare
echo.

:: ─────────────────────────────────────────────────────────────────────────────
:: STEP 2/4 — Create named tunnel
:: ─────────────────────────────────────────────────────────────────────────────
echo  ─────────────────────────────────────────────────────────
echo  STEP 2/4  --  Create Named Tunnel "stockbot"
echo  ─────────────────────────────────────────────────────────
echo.

"!CF_EXE!" tunnel create stockbot
echo.
echo  (If you see "already exists" that's fine -- continuing.)
echo.

:: Get the tunnel UUID by listing tunnels
set "TUNNEL_UUID="
for /f "tokens=1" %%i in ('"!CF_EXE!" tunnel list 2^>nul ^| findstr /i "stockbot"') do (
    if "!TUNNEL_UUID!"=="" set "TUNNEL_UUID=%%i"
)

if not "!TUNNEL_UUID!"=="" (
    echo [OK] Tunnel UUID: !TUNNEL_UUID!
) else (
    echo [WARN] Could not auto-detect UUID.
    echo        Run:  cloudflared tunnel list   to find it.
    set "TUNNEL_UUID=YOUR-TUNNEL-UUID"
)
echo.

:: Find the credentials JSON file
set "CREDS_FILE="
if exist "!CF_CREDS_DIR!\!TUNNEL_UUID!.json" (
    set "CREDS_FILE=!CF_CREDS_DIR!\!TUNNEL_UUID!.json"
) else (
    :: Fallback: pick the first UUID-like .json in ~/.cloudflared
    for /f "delims=" %%i in ('dir /b "!CF_CREDS_DIR!\*.json" 2^>nul') do (
        if "!CREDS_FILE!"=="" (
            echo %%i | findstr /r "[0-9a-f][0-9a-f][0-9a-f][0-9a-f]" >nul 2>&1
            if not errorlevel 1 set "CREDS_FILE=!CF_CREDS_DIR!\%%i"
        )
    )
)

if "!CREDS_FILE!"=="" set "CREDS_FILE=!CF_CREDS_DIR!\!TUNNEL_UUID!.json"
echo [OK] Credentials: !CREDS_FILE!
echo.

:: ─────────────────────────────────────────────────────────────────────────────
:: STEP 3/4 — Get a permanent public hostname
:: ─────────────────────────────────────────────────────────────────────────────
echo  ─────────────────────────────────────────────────────────
echo  STEP 3/4  --  Assign a Permanent Public URL
echo  ─────────────────────────────────────────────────────────
echo.
echo  Choose one of these two free options:
echo.
echo  ┌─ OPTION A  (No domain needed — recommended) ─────────────────┐
echo  │                                                               │
echo  │  1. Open:  https://one.dash.cloudflare.com                   │
echo  │  2. Go to:  Networks  ^>  Tunnels                             │
echo  │  3. Click "stockbot" tunnel  ^>  "Configure"                  │
echo  │  4. Click "Public Hostname" tab  ^>  "Add a public hostname"  │
echo  │  5. Fill in:                                                  │
echo  │       Subdomain : dashboard                                   │
echo  │       Domain    : (pick a domain from the dropdown)          │
echo  │       Type      : HTTP    URL: localhost:5000                 │
echo  │  6. Click Save                                                │
echo  │                                                               │
echo  │  Your URL:  https://dashboard.YOUR-DOMAIN                    │
echo  │  (if you have no domain in Cloudflare, go to OPTION B first) │
echo  └───────────────────────────────────────────────────────────────┘
echo.
echo  ┌─ OPTION B  (Free domain via Cloudflare Registrar) ───────────┐
echo  │                                                               │
echo  │  1. Go to cloudflare.com/products/registrar                  │
echo  │  2. Search for a cheap domain (many .com under $10/yr)       │
echo  │  3. Register it — it's automatically added to Cloudflare     │
echo  │  4. Come back here and choose Option A above                  │
echo  └───────────────────────────────────────────────────────────────┘
echo.
echo  Do steps above now (leave this window open), then come back
echo  and paste your permanent URL below.
echo.
set /p PERM_URL="  Paste your permanent https://... URL here: "

if "!PERM_URL!"=="" (
    echo.
    echo [INFO] No URL entered — you can set this later.
    echo        Edit docs\config.js and tunnel_config.yml manually,
    echo        or re-run this script.
    echo.
    set "PERM_URL=https://YOUR-PERMANENT-URL-HERE"
    set "HOSTNAME=YOUR-PERMANENT-URL-HERE"
    goto :save_config
)

:: Basic validation
echo !PERM_URL! | findstr /r "^https://" >nul 2>&1
if errorlevel 1 (
    echo [WARN] URL should start with https:// -- saving anyway.
)

:: Extract hostname
set "HOSTNAME="
for /f %%h in ('powershell -NonInteractive -Command "try { ([System.Uri]'!PERM_URL!').Host } catch { 'unknown-host' }" 2^>nul') do set "HOSTNAME=%%h"
if "!HOSTNAME!"=="" set "HOSTNAME=unknown-host"

echo [OK] Permanent URL: !PERM_URL!
echo [OK] Hostname:      !HOSTNAME!
echo.

:: ─────────────────────────────────────────────────────────────────────────────
:: STEP 4/4 — Write tunnel_config.yml + update docs/config.js
:: ─────────────────────────────────────────────────────────────────────────────
:save_config
echo  ─────────────────────────────────────────────────────────
echo  STEP 4/4  --  Saving configuration files
echo  ─────────────────────────────────────────────────────────
echo.

:: Write tunnel_config.yml
(
echo # Stock Bot Tracker -- Named Tunnel Configuration
echo # Generated by setup_named_tunnel.bat
echo # DO NOT commit this file to git (it contains a local credentials path).
echo # It is already in .gitignore.
echo #
echo # public_url: !PERM_URL!
echo #
echo tunnel: stockbot
echo credentials-file: !CREDS_FILE!
echo.
echo ingress:
echo   - hostname: !HOSTNAME!
echo     service: http://localhost:5000
echo   - service: http_status:404
) > "!CONFIG_FILE!"

echo [OK] Wrote tunnel_config.yml

:: Update docs/config.js with permanent URL
if exist "!DOCS_CONFIG!" (
    powershell -NonInteractive -Command ^
        "$url = '!PERM_URL!'; $c = Get-Content '!DOCS_CONFIG!' -Raw; $c = [regex]::Replace($c, 'https://[^\"'']+', $url); Set-Content '!DOCS_CONFIG!' $c -Encoding utf8"
    echo [OK] Updated docs\config.js with permanent URL
) else (
    echo [WARN] docs\config.js not found -- skipping auto-update
)

:: Add tunnel_config.yml to .gitignore if missing
findstr /i "tunnel_config.yml" "%DIR%.gitignore" >nul 2>&1
if errorlevel 1 (
    (
    echo.
    echo # Named tunnel config (local paths — do not commit)
    echo tunnel_config.yml
    ) >> "%DIR%.gitignore"
    echo [OK] Added tunnel_config.yml to .gitignore
)

:: ─────────────────────────────────────────────────────────────────────────────
:: Summary
:: ─────────────────────────────────────────────────────────────────────────────
echo.
echo  ============================================================
echo   Named Tunnel setup complete!
echo  ============================================================
echo.

if "!PERM_URL!" == "https://YOUR-PERMANENT-URL-HERE" (
    echo  [ACTION NEEDED]
    echo  You haven't set a public hostname yet.
    echo  Follow Option A in Step 3, then either:
    echo    a) Re-run this script and paste your URL, OR
    echo    b) Edit tunnel_config.yml and docs\config.js manually
    echo.
) else (
    echo   Permanent URL: !PERM_URL!
    echo.
    echo   This URL never changes, even after PC restarts.
    echo   Bookmark it on your phone!
    echo.
    echo   To update GitHub Pages remote dashboard, run:
    echo     git add docs\config.js
    echo     git commit -m "Set permanent tunnel URL"
    echo     git push
    echo.
)

echo   Next time the bot starts, it uses the named tunnel automatically.
echo   No more random URLs!
echo.
pause
