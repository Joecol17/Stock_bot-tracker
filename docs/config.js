// ─────────────────────────────────────────────────────────────────────────────
// Stock Bot Remote Dashboard — Configuration
// ─────────────────────────────────────────────────────────────────────────────
//
// You have two ways to configure the remote dashboard:
//
//  A) Edit this file and commit it to GitHub (recommended for Named Tunnel).
//     Replace the placeholder URL below with your Cloudflare Named Tunnel URL.
//     Leave STOCKBOT_TOKEN blank if you have not set DASHBOARD_SECRET in .env.
//
//  B) Leave this file as-is. On first visit the dashboard shows a ⚙ Settings
//     panel where you can enter the URL and token directly. These are saved in
//     localStorage and persist across visits on that device.
//
// IMPORTANT — do NOT commit your Trading 212 API key here.
// ─────────────────────────────────────────────────────────────────────────────

window.STOCKBOT_API_URL = "https://defeat-cataract-movable.ngrok-free.dev";
window.STOCKBOT_TOKEN   = "";   // matches DASHBOARD_SECRET in .env (optional)
