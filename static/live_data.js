// Live data bridge: fetches /api/botdata and populates window.BotData,
// then dispatches 'botdatarefreshed' so React re-renders.

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
