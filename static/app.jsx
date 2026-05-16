/* App shell — sidebar, top bar, page router */
const { useState: useStateA, useEffect: useEffectA } = React;

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
  const [page, setPage] = useStateA("overview");
  const [tweaks, setTweak] = useTweaks(DEFAULT_TWEAKS);
  const [tick, setTick] = useStateA(0);

  // Re-render all pages when live data refreshes
  useEffectA(() => {
    const handler = () => setTick(t => t + 1);
    window.addEventListener('botdatarefreshed', handler);
    return () => window.removeEventListener('botdatarefreshed', handler);
  }, []);

  useEffectA(() => {
    document.documentElement.style.setProperty("--accent", ACCENTS[tweaks.accent]?.color || ACCENTS.amber.color);
    const c = ACCENTS[tweaks.accent]?.color || ACCENTS.amber.color;
    document.documentElement.style.setProperty("--accent-soft", c.replace(/\)$/, " / .15)"));
  }, [tweaks.accent]);

  // Keyboard shortcuts 1-6
  useEffectA(() => {
    const PAGES = { "1": "overview", "2": "sources", "3": "trades", "4": "ai-engine", "5": "broker", "6": "risk" };
    const handler = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
      if (PAGES[e.key]) setPage(PAGES[e.key]);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const D = window.BotData;
  const isLive = D.mode === "LIVE";
  const model = D.model || "llama2";

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

        <div className="side-foot">
          <div className="bot-status">
            <span className="dot" style={{ background: D.bot_status === "running" ? "var(--pos)" : "var(--text-dim)", boxShadow: D.bot_status === "running" ? "0 0 0 3px oklch(74% 0.16 148 / .18)" : "none", animation: D.bot_status === "running" ? undefined : "none" }}/>
            <span>Bot <b style={{ color: D.bot_status === "running" ? "var(--pos)" : "var(--text-mute)" }}>{(D.bot_status || "idle").toUpperCase()}</b></span>
          </div>
          <div className="bot-status">
            <span className="dot" style={{ background: "var(--info)", boxShadow: "0 0 0 3px oklch(72% 0.13 230 / .18)" }}/>
            <span>{model} · t={D.temperature || 0.2}</span>
          </div>
          <div className="bot-status">
            <span className="dot" style={{ background: isLive ? "var(--pos)" : "var(--accent)", boxShadow: isLive ? "0 0 0 3px oklch(74% 0.16 148 / .18)" : "0 0 0 3px oklch(78% 0.14 70 / .18)" }}/>
            <span>T212 · <b style={{ color: isLive ? "var(--pos)" : "var(--warn)" }}>{D.mode || "DEMO"}</b></span>
          </div>
        </div>
      </aside>

      <main className="main">
        <div className="topbar">
          <div className="crumb">
            STOCK_BOT  <span style={{ margin:"0 8px", color:"var(--text-dim)" }}>›</span>  <b>{pageTitle(page)}</b>
          </div>
          <div className="topbar-right">
            <span className="topbar-chip"><span className="dot dot-green"/>Bot live</span>
            <span className="topbar-chip"><span className="dot dot-blue"/>T212 API</span>
            <span className="topbar-chip"><span className="dot dot-amber"/>Ollama {model}</span>
            {isLive
              ? <span className="topbar-chip" style={{ borderColor: "var(--pos)", color: "var(--pos)" }}>LIVE MODE</span>
              : <span className="topbar-chip" style={{ borderColor: "var(--warn)", color: "var(--warn)" }}>DEMO MODE</span>
            }
            <button className="btn ghost" title="Pause bot"><I.Pause className="ico"/>Pause</button>
            <button className="btn primary"><I.Bolt className="ico"/>Run cycle</button>
          </div>
        </div>

        {page === "overview"  && <OverviewPage tweaks={tweaks} key={`ov-${tick}`}/>}
        {page === "sources"   && <SourcesPage key={`sr-${tick}`}/>}
        {page === "trades"    && <TradesPage key={`tr-${tick}`}/>}
        {page === "ai-engine" && <AiEnginePage key="ai-engine"/>}
        {page === "broker"    && <BrokerPage key="broker"/>}
        {page === "risk"      && <RiskConfigPage key="risk"/>}
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

const pageTitle = (p) => ({
  overview: "Overview",
  sources: "Data sources",
  trades: "Trades & decisions",
  "ai-engine": "AI engine",
  broker: "Broker",
  risk: "Risk & config",
}[p] || "Overview");

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
