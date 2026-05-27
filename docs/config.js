// ─────────────────────────────────────────────────────────────────────────────
// Stock Bot Remote Dashboard — Configuration
// ─────────────────────────────────────────────────────────────────────────────

// URL of your ngrok static domain (set by setup_ngrok.bat)
window.STOCKBOT_API_URL = "https://defeat-cataract-movable.ngrok-free.dev";

// Optional bearer token — matches DASHBOARD_SECRET in .env
window.STOCKBOT_TOKEN   = "";

// ── Wake on LAN relay ─────────────────────────────────────────────────────────
// Set WAKE_RELAY_URL after deploying wol_relay/ to Render.com (see README).
// Leave blank to hide the Wake PC button (you can still use a WoL phone app).
window.WAKE_RELAY_URL   = "";   // e.g. "https://stockbot-wol.onrender.com"

// Optional secret — must match WAKE_SECRET env var on Render.
window.WAKE_TOKEN       = "";

// Your PC's MAC address — shown on the offline screen so you can copy it into
// a WoL app. Not required if you use the relay. Safe to commit (it's local-only).
window.PC_MAC           = "BC-F4-D4-A9-18-D1";
