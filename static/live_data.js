// Live data bridge: fetches /api/botdata and populates window.BotData,
// then dispatches 'botdatarefreshed' so React re-renders.

// ── Auth-token bridge ───────────────────────────────────────────────────────
// When the GitHub Pages gateway forwards here it may append "#token=<secret>".
// Capture it, persist it, strip it from the URL, and transparently attach it to
// every same-origin /api/* request so the full dashboard works remotely even
// when DASHBOARD_SECRET is configured. No token → completely inert.
(function () {
  try {
    const m = (location.hash || "").match(/token=([^&]+)/);
    if (m) {
      localStorage.setItem("stockbot_token", decodeURIComponent(m[1]));
      history.replaceState(null, "", location.pathname + location.search);
    }
  } catch (e) { /* ignore */ }

  const token = (() => { try { return localStorage.getItem("stockbot_token") || ""; } catch (e) { return ""; } })();
  if (token) {
    const _fetch = window.fetch;
    window.fetch = function (input, init = {}) {
      const url = typeof input === "string" ? input : (input && input.url) || "";
      const isApi = url.startsWith("/api/") || url.includes(location.host + "/api/");
      if (isApi) {
        init = { ...init };
        init.headers = { ...(init.headers || {}), "X-Auth-Token": token };
      }
      return _fetch.call(this, input, init);
    };
  }
})();

window.BotData = {
  positions: [],
  decisions: [],
  orders: [],
  sources: [
    { id: "t212-api",   kind: "broker",  label: "Trading 212",            city: "London",    country: "UK", lat_px: 30, lng_px: 49, status: "live",  latency: 38,  throughput: "—", description: "Orders, positions, account state" },
    { id: "yfinance",   kind: "market",  label: "yfinance (Yahoo)",        city: "New York",  country: "US", lat_px: 39, lng_px: 28, status: "live",  latency: 124, throughput: "—", description: "Market data & technical indicators" },
    { id: "ollama-loc", kind: "ai",      label: "Ollama — local",          city: "Localhost", country: "—",  lat_px: 64, lng_px: 50, status: "live",  latency: 6,   throughput: "—", description: "AI decision engine" },
    { id: "config-loc", kind: "config",  label: "Risk & Config — local",   city: "Localhost", country: "—",  lat_px: 64, lng_px: 50, status: "live",  latency: 1,   throughput: "—", description: "Daily limits, SL/TP, watchlist" },
  ],
  activity: [],
  equity: Array.from({ length: 72 }, (_, i) => ({ i, v: 10000 })),
  decisionHist: Array.from({ length: 24 }, (_, h) => ({ h, buy: 0, sell: 0, hold: 0 })),
  cash: 0,
  free_funds: 0,
  total_value: 0,
  mode: "DEMO",
  model: "llama2",
  temperature: 0.2,
  max_tokens: 256,
  min_account_value: 100,
  cycle_interval: 300,
  cycles_per_hour: 3,
  focus_cycles_per_hour: 12,
  schedule_enabled: true,
  in_trading_window: false,
  next_run: "",
  trading_hours: "",
  bot_status: "idle",
  cycle: 0,
  step: 0,
  step_name: "idle",
  current_symbol: "",
  uptime_seconds: 0,
  last_cycle_time: "",
  avg_confidence: 0,
  tunnel_url: null,      // set by tunnel_helper.py (Cloudflare public URL)
  paused: false,
  regime: { regime: "unknown" },
  in_focus_period: false,         // true during the 2:30–3:45pm overdrive window
  focus_window: "",
  projections: { ready: false, days_tracked: 0 },  // profit forecast (equity_tracker.py)
};

async function _fetchBotData() {
  try {
    const r = await fetch('/api/botdata');
    if (!r.ok) return;
    const d = await r.json();
    if (d.error) return;
    // Keep sources from live_data defaults if server returns none
    if (!d.sources || d.sources.length === 0) delete d.sources;
    Object.assign(window.BotData, d);
    window.dispatchEvent(new CustomEvent('botdatarefreshed'));
  } catch (e) {
    console.warn('BotData fetch failed', e);
  }
}

_fetchBotData();
setInterval(_fetchBotData, 30000);
