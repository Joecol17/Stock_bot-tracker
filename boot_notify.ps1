# boot_notify.ps1
# Posts a reminder to the Discord #alerts channel ~1 min after the PC powers on,
# so you remember to log in (via AnyDesk) and start the trading bot.
# Runs as a SYSTEM "At startup" scheduled task, so it fires at the lock screen
# BEFORE anyone logs in. Reads the webhook from .env (never hard-coded here).
#
#   Test it:  powershell -ExecutionPolicy Bypass -File boot_notify.ps1 -Test

param([switch]$Test)

$proj    = "C:\Users\josep\OneDrive\Documents\GitHub\Stock_bot-tracker"
$envFile = Join-Path $proj ".env"

# Weekdays only (Mon-Fri) — skip on weekends unless testing.
if (-not $Test) {
    $dow = (Get-Date).DayOfWeek
    if ($dow -eq 'Saturday' -or $dow -eq 'Sunday') { return }
}

# Pull the alerts webhook (fall back to the generic one) from .env.
$url = $null
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        if ($line -match '^\s*DISCORD_WEBHOOK_ALERTS\s*=\s*(\S.*)$') { $url = $matches[1].Trim(); break }
    }
    if (-not $url) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*DISCORD_WEBHOOK_URL\s*=\s*(\S.*)$') { $url = $matches[1].Trim(); break }
        }
    }
}
if (-not $url) { return }

$msg = if ($Test) {
    "Test: boot reminder is set up correctly. (You'll get this ~1 min after the PC turns on, Mon-Fri.)"
} else {
    "PC is ON - log in via AnyDesk to start the trading bot."
}
$payload = @{ content = $msg } | ConvertTo-Json -Compress
$bytes   = [Text.Encoding]::UTF8.GetBytes($payload)

# Retry for up to ~90s to let the network come up after boot.
for ($i = 0; $i -lt 6; $i++) {
    try {
        Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json; charset=utf-8" -Body $bytes -TimeoutSec 15 | Out-Null
        break
    } catch {
        Start-Sleep -Seconds 15
    }
}
