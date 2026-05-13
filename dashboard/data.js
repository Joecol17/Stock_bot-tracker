// ─── Mission Control · Live Data Client ──────────────────────────────────────
// Initialises window.BotData with mock data so the UI renders immediately,
// then polls /api/all every 5 s and merges in real data from the Flask server.
// If the server is not running the UI stays on mock data gracefully.

window.BotData = (() => {

  // ── Mock / fallback data ────────────────────────────────────────────────
  const positions = [
    { symbol: "AAPL",  name: "Apple Inc.",         quantity: 12, avg: 172.18, price: 178.23, value: 2138.76, pl:  72.60, plPct:  3.51, trend: "uptrend",   flag: "🇺🇸" },
    { symbol: "GOOGL", name: "Alphabet Inc. Cl A", quantity:  8, avg: 145.30, price: 142.50, value: 1140.00, pl: -22.40, plPct: -1.93, trend: "neutral",   flag: "🇺🇸" },
    { symbol: "MSFT",  name: "Microsoft Corp.",    quantity:  4, avg: 388.40, price: 380.00, value: 1520.00, pl: -33.60, plPct: -2.16, trend: "downtrend", flag: "🇺🇸" },
    { symbol: "ASML",  name: "ASML Holding N.V.",  quantity:  2, avg: 902.10, price: 914.55, value: 1829.10, pl:  24.90, plPct:  1.38, trend: "uptrend",   flag: "🇳🇱" },
    { symbol: "TSM",   name: "Taiwan Semi. Mfg.",  quantity: 10, avg: 148.20, price: 152.95, value: 1529.50, pl:  47.50, plPct:  3.20, trend: "uptrend",   flag: "🇹🇼" },
    { symbol: "NVO",   name: "Novo Nordisk A/S",   quantity:  6, avg: 122.40, price: 119.80, value:  718.80, pl: -15.60, plPct: -2.12, trend: "neutral",   flag: "🇩🇰" },
  ];

  const decisions = [
    { id: "tr_0421", at: "10:42:18", symbol: "AAPL",  action: "BUY",  qty: 1, model: "llama2", confidence: 0.78, status: "filled",    price: 178.23, reason: "Uptrend confirmed; services growth narrative.", context: { price: 178.23, trend: "uptrend" } },
    { id: "tr_0420", at: "10:41:02", symbol: "GOOGL", action: "HOLD", qty: 0, model: "llama2", confidence: 0.61, status: "no-action", price: 142.50, reason: "Neutral trend, regulatory overhang.", context: { price: 142.50, trend: "neutral" } },
    { id: "tr_0419", at: "10:40:11", symbol: "MSFT",  action: "SELL", qty: 1, model: "llama2", confidence: 0.72, status: "filled",    price: 380.00, reason: "Downtrend persistent; AI capex concerns.", context: { price: 380.00, trend: "downtrend" } },
    { id: "tr_0418", at: "10:32:45", symbol: "TSM",   action: "BUY",  qty: 2, model: "llama2", confidence: 0.83, status: "filled",    price: 152.95, reason: "Foundry demand positive; support held.", context: { price: 152.95, trend: "uptrend" } },
    { id: "tr_0417", at: "10:28:09", symbol: "ASML",  action: "BUY",  qty: 1, model: "llama2", confidence: 0.69, status: "filled",    price: 914.55, reason: "EUV order book robust.", context: { price: 914.55, trend: "uptrend" } },
    { id: "tr_0416", at: "10:21:33", symbol: "NVO",   action: "HOLD", qty: 0, model: "llama2", confidence: 0.55, status: "no-action", price: 119.80, reason: "Mixed signals; competitor data pending.", context: { price: 119.80, trend: "neutral" } },
  ];

  const orders = [
    { id: "ord_882", symbol: "AAPL", side: "BUY",  qty: 1, type: "LIMIT",  price: 176.00, status: "WORKING", placed: "10:42:21" },
    { id: "ord_881", symbol: "TSM",  side: "BUY",  qty: 2, type: "MARKET", price: 152.95, status: "FILLED",  placed: "10:32:46" },
    { id: "ord_879", symbol: "MSFT", side: "SELL", qty: 1, type: "MARKET", price: 380.00, status: "FILLED",  placed: "10:40:13" },
  ];

  const sources = [
    { id: "t212",     kind: "broker", label: "Trading 212 — Demo",            city: "London",    country: "UK", lat_px: 30, lng_px: 49, status: "live",  latency: 38,  throughput: "live",     description: "Orders, positions, account state" },
    { id: "yfinance", kind: "market", label: "Market Data — yfinance",        city: "New York",  country: "US", lat_px: 39, lng_px: 28, status: "live",  latency: 120, throughput: "on-demand",description: "NYSE / NASDAQ prices" },
    { id: "ollama",   kind: "ai",     label: "Ollama (llama2) — local",       city: "Localhost", country: "—",  lat_px: 64, lng_px: 50, status: "live",  latency: 6,   throughput: "on-demand",description: "AI decision engine" },
    { id: "config",   kind: "config", label: "Risk & Config — local",         city: "Localhost", country: "—",  lat_px: 64, lng_px: 50, status: "live",  latency: 1,   throughput: "—",        description: "Daily limits, demo flag" },
  ];

  const activity = [
    { t: "10:42:18", kind: "decision", text: '<b>llama2</b> decided <span class="sym">AAPL</span> → <b>BUY</b> (conf 0.78)',  tag: "AI",   tagClass: "accent" },
    { t: "10:41:02", kind: "decision", text: '<b>llama2</b> decided <span class="sym">GOOGL</span> → <b>HOLD</b> (conf 0.61)', tag: "AI",   tagClass: "accent" },
    { t: "10:40:11", kind: "decision", text: '<b>llama2</b> decided <span class="sym">MSFT</span> → <b>SELL</b> (conf 0.72)',  tag: "AI",   tagClass: "accent" },
    { t: "10:32:45", kind: "decision", text: '<b>llama2</b> decided <span class="sym">TSM</span> → <b>BUY</b> (conf 0.83)',   tag: "AI",   tagClass: "accent" },
  ];

  const equity = (() => {
    const pts = []; let v = 9870;
    for (let i = 0; i < 72; i++) {
      v += (Math.sin(i / 6) * 5) + (Math.random() - 0.45) * 9 + (i > 30 ? 0.7 : 0);
      pts.push({ i, v: Math.round(v * 100) / 100 });
    }
    return pts;
  })();

  const decisionHist = Array.from({ length: 24 }, (_, h) => ({
    h, buy: Math.round(Math.random() * 4 + (h > 9 && h < 17 ? 3 : 0)),
    sell: Math.round(Math.random() * 3 + (h > 9 && h < 17 ? 2 : 0)),
    hold: Math.round(Math.random() * 5 + (h > 9 && h < 17 ? 4 : 1)),
  }));

  const account = { cash: 4127.84, portfolio_value: 9876.16, free_funds: 4127.84, account_id: "demo" };
  const botStatus = { isDemo: true, model: "llama2", temperature: 0.2, maxTokens: 256, maxDailyTrades: 10, cycleCount: 51, uptimeSeconds: 15442 };

  // ── Live polling ────────────────────────────────────────────────────────
  const POLL_MS = 5000;

  function applyLiveData(data) {
    if (data.positions && data.positions.length > 0 && !data.positions[0]?.error) {
      window.BotData.positions = data.positions;
    }
    if (data.decisions && data.decisions.length > 0) {
      window.BotData.decisions = data.decisions;
    }
    if (data.orders  && data.orders.length > 0)  window.BotData.orders  = data.orders;
    if (data.sources && data.sources.length > 0) window.BotData.sources = data.sources;
    if (data.activity)     window.BotData.activity     = data.activity;
    if (data.equity)       window.BotData.equity       = data.equity;
    if (data.decisionHist) window.BotData.decisionHist = data.decisionHist;
    if (data.account)      window.BotData.account      = data.account;
    if (data.botStatus)    window.BotData.botStatus    = data.botStatus;
    window.dispatchEvent(new CustomEvent('botdata:update'));
  }

  async function poll() {
    try {
      const res = await fetch('/api/all', { signal: AbortSignal.timeout(4000) });
      if (res.ok) applyLiveData(await res.json());
    } catch (_) {
      // Server not running — keep mock data, retry next interval
    }
  }

  // Small delay so React has time to mount before the first update fires
  setTimeout(() => { poll(); setInterval(poll, POLL_MS); }, 800);

  return { positions, decisions, orders, sources, activity, equity, decisionHist, account, botStatus };
})();
