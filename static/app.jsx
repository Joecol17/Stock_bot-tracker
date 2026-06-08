/* App shell — sidebar, top bar, page router */
const { useState: useStateA, useEffect: useEffectA } = React;

/* ── Error boundary (class component — catches crashes in any page) ─────── */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error("[ErrorBoundary] Page crashed:", error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="page" style={{ alignItems: "center", justifyContent: "center" }}>
          <div className="card" style={{ maxWidth: 480, textAlign: "center", padding: 40 }}>
            <div style={{ fontSize: 36, marginBottom: 16 }}>⚠️</div>
            <div style={{ fontFamily: "var(--display)", fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
              This page crashed
            </div>
            <div className="mono dim" style={{ fontSize: 11, marginBottom: 20, wordBreak: "break-word" }}>
              {this.state.error?.message || "Unknown error"}
            </div>
            <button
              className="btn primary"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
window.ErrorBoundary = ErrorBoundary;

const DEFAULT_TWEAKS = /*EDITMODE-BEGIN*/{
  "accent": "amber",
  "density": "default",
  "showActivity": true
}/*EDITMODE-END*/;

const ACCENTS = {
  amber:  { name:"Amber",  color:"oklch(78% 0.14 70)"  },
  cyan:   { name:"Cyan",   color:"oklch(78% 0.13 200)" },
  violet: { name:"Violet", color:"oklch(72% 0.16 295)" },
  rose:   { name:"Rose",   color:"oklch(74% 0.16 10)"  },
};

const App = () => {
  const [page, setPage]       = useStateA("overview");
  const [tweaks, setTweak]    = useTweaks(DEFAULT_TWEAKS);
  const [tick, setTick]       = useStateA(0);
  const [paused, setPaused]   = useStateA(false);
  const [cycling, setCycling] = useStateA(false);

  // Re-render all pages when live data refreshes; sync pause state from server
  useEffectA(() => {
    const handler = () => {
      setTick(t => t + 1);
      if (window.BotData.paused !== undefined) setPaused(window.BotData.paused);
    };
    window.addEventListener('botdatarefreshed', handler);
    return () => window.removeEventListener('botdatarefreshed', handler);
  }, []);

  useEffectA(() => {
    document.documentElement.style.setProperty("--accent", ACCENTS[tweaks.accent]?.color || ACCENTS.amber.color);
    const c = ACCENTS[tweaks.accent]?.color || ACCENTS.amber.color;
    document.documentElement.style.setProperty("--accent-soft", c.replace(/\)$/, " / .15)"));
  }, [tweaks.accent]);

  // Keyboard shortcuts 1-7
  useEffectA(() => {
    const PAGES = { "1": "overview", "2": "sources", "3": "trades", "4": "ai-engine", "5": "broker", "6": "risk", "7": "predictions", "8": "logs", "9": "watchlist" };
    const handler = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
      if (PAGES[e.key]) setPage(PAGES[e.key]);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Pause toggle
  const togglePause = async () => {
    const next = !paused;
    setPaused(next);
    try {
      await fetch("/api/bot/pause", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paused: next }),
      });
    } catch (e) {
      setPaused(!next); // revert on error
    }
  };

  // Run cycle now
  const runCycleNow = async () => {
    setCycling(true);
    setPaused(false);
    try {
      await fetch("/api/bot/run_cycle", { method: "POST" });
    } catch (e) { /* ignore */ }
    setTimeout(() => setCycling(false), 2000);
  };

  const D = window.BotData;
  const isLive    = D.mode === "LIVE";
  const model     = D.model || "llama2";
  const botStatus = D.bot_status || "idle";

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">⌬</div>
          <div className="brand-text">
            <b>Mission Control</b>
            <span>stock_bot · v0.4</span>
          </div>
        </div>

        <div className="nav-section">Workspace</div>
        <NavItem icon={<I.Dashboard/>}  active={page === "overview"}   onClick={() => setPage("overview")}   kbd="1">Overview</NavItem>
        <NavItem icon={<I.Globe/>}      active={page === "sources"}    onClick={() => setPage("sources")}    kbd="2">Data sources</NavItem>
        <NavItem icon={<I.Trades/>}     active={page === "trades"}     onClick={() => setPage("trades")}     kbd="3">Trades</NavItem>

        <div className="nav-section">Setup</div>
        <NavItem icon={<I.Cpu/>}        active={page === "ai-engine"}  onClick={() => setPage("ai-engine")}  kbd="4">AI engine</NavItem>
        <NavItem icon={<I.Server/>}     active={page === "broker"}     onClick={() => setPage("broker")}     kbd="5">Broker</NavItem>
        <NavItem icon={<I.Settings/>}   active={page === "risk"}       onClick={() => setPage("risk")}       kbd="6">Risk & config</NavItem>

        <div className="nav-section">Insight</div>
        <NavItem icon={<I.Chart/>}      active={page === "predictions"} onClick={() => setPage("predictions")} kbd="7">Predictions</NavItem>

        <div className="nav-section">Debug</div>
        <NavItem icon={<I.Refresh/>}    active={page === "logs"}       onClick={() => setPage("logs")}       kbd="8">Live logs</NavItem>

        <div className="nav-section">Trading</div>
        <NavItem icon={<I.Globe/>}      active={page === "watchlist"}  onClick={() => setPage("watchlist")}  kbd="9">Watchlist</NavItem>

        <div className="side-foot">
          <div className="bot-status">
            <span className="dot" style={{
              background: botStatus === "running"  ? "var(--pos)"      :
                          botStatus === "paused"   ? "var(--warn)"     :
                          botStatus === "standby"  ? "var(--info)"     : "var(--text-dim)",
              boxShadow:  botStatus === "running"  ? "0 0 0 3px oklch(74% 0.16 148 / .18)" :
                          botStatus === "paused"   ? "0 0 0 3px oklch(78% 0.14 70 / .18)"  :
                          botStatus === "standby"  ? "0 0 0 3px oklch(72% 0.13 230 / .18)" : "none",
              animation:  (botStatus === "running" || botStatus === "standby") ? undefined : "none",
            }}/>
            <span>Bot <b style={{
              color: botStatus === "running"  ? "var(--pos)"  :
                     botStatus === "paused"   ? "var(--warn)" :
                     botStatus === "standby"  ? "var(--info)" : "var(--text-mute)"
            }}>{botStatus === "standby" ? "STANDBY" : botStatus.toUpperCase()}</b></span>
          </div>
          {/* Schedule: next run time or out-of-hours notice */}
          {D.schedule_enabled && (
            <div className="bot-status" style={{ fontSize:10, color:"var(--text-dim)" }}>
              {D.in_trading_window
                ? <span><span style={{ color:"var(--accent)" }}>⏱</span> Next run <b style={{ color:"var(--text)" }}>{D.next_run || "—"}</b></span>
                : <span><span style={{ color:"var(--warn)" }}>⏸</span> Market closed · next <b style={{ color:"var(--text)" }}>{D.next_run || "—"}</b></span>
              }
            </div>
          )}
          <div className="bot-status">
            <span className="dot" style={{ background: "var(--info)", boxShadow: "0 0 0 3px oklch(72% 0.13 230 / .18)" }}/>
            <span>{model} · t={D.temperature || 0.2}</span>
          </div>
          <div className="bot-status">
            <span className="dot" style={{ background: isLive ? "var(--pos)" : "var(--accent)", boxShadow: isLive ? "0 0 0 3px oklch(74% 0.16 148 / .18)" : "0 0 0 3px oklch(78% 0.14 70 / .18)" }}/>
            <span>T212 · <b style={{ color: isLive ? "var(--pos)" : "var(--warn)" }}>{D.mode || "DEMO"}</b></span>
          </div>

          {/* Remote tunnel URL */}
          {D.tunnel_url && (
            <div style={{ marginTop: 6, borderTop: "1px solid var(--border-soft)", paddingTop: 8 }}>
              <div style={{ fontSize: 9, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>
                🌐 Remote URL
              </div>
              <a
                href={D.tunnel_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  fontSize: 10, color: "var(--accent)", fontFamily: "var(--mono)",
                  wordBreak: "break-all", textDecoration: "none",
                  display: "block",
                }}
                title="Open dashboard remotely"
              >
                {D.tunnel_url.replace("https://", "")}
              </a>
              <button
                className="btn ghost"
                style={{ marginTop: 4, fontSize: 10, padding: "3px 8px", width: "100%" }}
                onClick={() => navigator.clipboard?.writeText(D.tunnel_url)}
              >
                Copy URL
              </button>
            </div>
          )}

          {/* PC power controls (only useful in remote/headless mode) */}
          <PCPowerControls/>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="crumb">
            STOCK_BOT  <span style={{ margin:"0 8px", color:"var(--text-dim)" }}>›</span>  <b>{pageTitle(page)}</b>
          </div>
          <div className="topbar-right">
            <span className="topbar-chip">
              <span className="dot" style={{
                background: botStatus === "running" ? "var(--pos)" :
                            botStatus === "paused"  ? "var(--warn)" :
                            botStatus === "standby" ? "var(--info)" : "var(--text-dim)"
              }}/>
              Bot {botStatus === "standby" ? "standby" : botStatus}
            </span>
            <span className="topbar-chip"><span className="dot dot-blue"/>T212 API</span>
            <span className="topbar-chip"><span className="dot dot-amber"/>Ollama {model}</span>
            {isLive
              ? <span className="topbar-chip" style={{ borderColor: "var(--pos)",  color: "var(--pos)"  }}>LIVE MODE</span>
              : <span className="topbar-chip" style={{ borderColor: "var(--warn)", color: "var(--warn)" }}>DEMO MODE</span>
            }
            <button
              className={`btn ghost ${paused ? "active" : ""}`}
              title={paused ? "Resume bot" : "Pause bot"}
              onClick={togglePause}
              style={paused ? { borderColor: "var(--warn)", color: "var(--warn)" } : {}}
            >
              <I.Pause className="ico"/>{paused ? "Resume" : "Pause"}
            </button>
            <button
              className="btn primary"
              onClick={runCycleNow}
              disabled={cycling}
              style={cycling ? { opacity: 0.6 } : {}}
            >
              <I.Bolt className="ico"/>{cycling ? "Triggered…" : "Run cycle"}
            </button>
          </div>
        </div>

        {page === "overview"  && <ErrorBoundary key={`ov-${tick}`}><OverviewPage tweaks={tweaks}/></ErrorBoundary>}
        {page === "sources"   && <ErrorBoundary key={`sr-${tick}`}><SourcesPage/></ErrorBoundary>}
        {page === "trades"    && <ErrorBoundary key={`tr-${tick}`}><TradesPage/></ErrorBoundary>}
        {page === "ai-engine" && <ErrorBoundary key="ai-engine"><AiEnginePage/></ErrorBoundary>}
        {page === "broker"    && <ErrorBoundary key="broker"><BrokerPage/></ErrorBoundary>}
        {page === "risk"      && <ErrorBoundary key="risk"><RiskConfigPage/></ErrorBoundary>}
        {page === "predictions" && <ErrorBoundary key={`pred-${tick}`}><PredictionsPage/></ErrorBoundary>}
        {page === "logs"      && <ErrorBoundary key="logs"><LogsPage/></ErrorBoundary>}
        {page === "watchlist" && <ErrorBoundary key="watchlist"><WatchlistPage/></ErrorBoundary>}
      </main>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Accent">
          <TweakColor
            label="Accent color"
            options={Object.values(ACCENTS).map(v => v.color)}
            value={ACCENTS[tweaks.accent].color}
            onChange={(c) => {
              const key = Object.entries(ACCENTS).find(([k, v]) => v.color === c)?.[0] || "amber";
              setTweak("accent", key);
            }}
          />
        </TweakSection>
        <TweakSection label="Layout">
          <TweakRadio
            label="Density"
            options={["default", "compact"]}
            value={tweaks.density}
            onChange={(v) => setTweak("density", v)}
          />
          <TweakToggle label="Show activity feed" value={tweaks.showActivity} onChange={(v) => setTweak("showActivity", v)}/>
        </TweakSection>
      </TweaksPanel>
    </div>
  );
};

const NavItem = ({ icon, children, active, onClick, kbd }) => (
  <button className={`nav-item ${active ? "active" : ""}`} onClick={onClick}>
    {icon}
    <span>{children}</span>
    {kbd && <span className="kbd">{kbd}</span>}
  </button>
);

/* ── PC Power Controls (remote shutdown / sleep) ─────────────────────── */
const { useState: useStatePwr } = React;

const PCPowerControls = () => {
  const [open, setOpen]         = useStatePwr(false);
  const [pending, setPending]   = useStatePwr(null);
  const [message, setMessage]   = useStatePwr(null);

  const send = async (endpoint, body = {}) => {
    setPending(endpoint);
    setMessage(null);
    try {
      const r = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await r.json();
      setMessage(d.message || (d.ok ? "Done" : "Failed"));
    } catch (e) {
      setMessage("Request failed");
    } finally {
      setPending(null);
    }
  };

  return (
    <div style={{ marginTop: 8, borderTop: "1px solid var(--border-soft)", paddingTop: 8 }}>
      <button
        className="btn ghost"
        style={{ width: "100%", fontSize: 10, padding: "3px 8px", color: "var(--text-dim)" }}
        onClick={() => { setOpen(o => !o); setMessage(null); }}
      >
        {open ? "▲" : "▼"} PC power controls
      </button>
      {open && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 6 }}>
          <button
            className="btn ghost"
            style={{ fontSize: 10, padding: "4px 8px" }}
            onClick={() => send("/api/pc/sleep")}
            disabled={pending !== null}
          >
            💤 Sleep PC
          </button>
          <button
            className="btn ghost"
            style={{ fontSize: 10, padding: "4px 8px", color: "var(--warn)" }}
            onClick={() => { if (window.confirm("Shut down PC in 2 minutes?")) send("/api/pc/shutdown", { delay_seconds: 120 }); }}
            disabled={pending !== null}
          >
            ⏻ Shutdown (2 min)
          </button>
          {message && (
            <div style={{ fontSize: 10, color: "var(--text-dim)", fontFamily: "var(--mono)", padding: "4px 0" }}>
              {message}
              {message.includes("shut down") && (
                <button
                  className="btn ghost"
                  style={{ marginLeft: 6, fontSize: 9, padding: "2px 6px", color: "var(--neg)" }}
                  onClick={() => send("/api/pc/cancel_shutdown")}
                >
                  Cancel
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const pageTitle = (p) => ({
  overview:   "Overview",
  sources:    "Data sources",
  trades:     "Trades & decisions",
  "ai-engine":"AI engine",
  broker:     "Broker",
  risk:       "Risk & config",
  predictions:"Predictions",
  logs:       "Live logs",
  watchlist:  "Watchlist",
}[p] || "Overview");

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
