/* App shell — sidebar, top bar, page router */
/* Subscribes to botdata:update events so the whole tree re-renders on live data */
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
  const [tick, setTick] = useStateA(0); // bumped every time live data arrives

  // Re-render the whole tree when the data layer fires an update event
  useEffectA(() => {
    const handler = () => setTick(t => t + 1);
    window.addEventListener('botdata:update', handler);
    return () => window.removeEventListener('botdata:update', handler);
  }, []);

  useEffectA(() => {
    document.documentElement.style.setProperty("--accent", ACCENTS[tweaks.accent]?.color || ACCENTS.amber.color);
    const c = ACCENTS[tweaks.accent]?.color || ACCENTS.amber.color;
    document.documentElement.style.setProperty("--accent-soft", c.replace(/\)$/, " / .15)"));
  }, [tweaks.accent]);

  // Keyboard shortcuts 1/2/3 to switch pages
  useEffectA(() => {
    const handler = (e) => {
      if (e.target.tagName === "INPUT") return;
      if (e.key === "1") setPage("overview");
      if (e.key === "2") setPage("sources");
      if (e.key === "3") setPage("trades");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const D = window.BotData;
  const bs = D.botStatus || {};
  const isDemo = bs.isDemo !== false;

  // Uptime display
  const upSec = bs.uptimeSeconds || 0;
  const hh = String(Math.floor(upSec / 3600)).padStart(2, "0");
  const mm = String(Math.floor((upSec % 3600) / 60)).padStart(2, "0");
  const ss = String(upSec % 60).padStart(2, "0");

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
        <NavItem icon={<I.Dashboard/>} active={page === "overview"} onClick={() => setPage("overview")} kbd="1">Overview</NavItem>
        <NavItem icon={<I.Globe/>}     active={page === "sources"}  onClick={() => setPage("sources")}  kbd="2">Data sources</NavItem>
        <NavItem icon={<I.Trades/>}    active={page === "trades"}   onClick={() => setPage("trades")}   kbd="3">Trades</NavItem>

        <div className="nav-section">Setup</div>
        <NavItem icon={<I.Cpu/>}      onClick={() => {}}>AI engine</NavItem>
        <NavItem icon={<I.Server/>}   onClick={() => {}}>Broker</NavItem>
        <NavItem icon={<I.Settings/>} onClick={() => {}}>Risk & config</NavItem>

        <div className="side-foot">
          <div className="bot-status">
            <span className="dot"/>
            <span>Bot <b style={{ color: "var(--text)" }}>RUNNING</b> · cycle {bs.cycleCount || "—"}</span>
          </div>
          <div className="bot-status">
            <span className="dot" style={{ background: "var(--info)", boxShadow: "0 0 0 3px oklch(72% 0.13 230 / .18)" }}/>
            <span>{bs.model || "llama2"} · {bs.temperature ?? 0.2} · max {bs.maxTokens || 256}</span>
          </div>
          <div className="bot-status">
            <span className="dot" style={{ background: "var(--accent)", boxShadow: "0 0 0 3px oklch(78% 0.14 70 / .18)" }}/>
            <span>T212 · <b style={{ color: isDemo ? "var(--warn)" : "var(--neg)" }}>{isDemo ? "DEMO" : "LIVE"}</b></span>
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
            <span className="topbar-chip"><span className="dot dot-blue"/>T212 {D.sources?.find(s=>s.id==="t212")?.latency ?? "—"}ms</span>
            <span className="topbar-chip"><span className="dot dot-amber"/>Ollama {D.sources?.find(s=>s.id==="ollama")?.latency ?? "—"}ms</span>
            {isDemo && <span className="topbar-chip" style={{ borderColor: "var(--warn)", color: "var(--warn)" }}>DEMO MODE</span>}
            <button className="btn ghost" title="Pause bot"><I.Pause className="ico"/>Pause</button>
            <button className="btn primary" onClick={() => fetch('/api/cycle', {method:'POST'}).catch(()=>{})}><I.Bolt className="ico"/>Run cycle</button>
          </div>
        </div>

        {page === "overview" && <OverviewPage tweaks={tweaks}/>}
        {page === "sources"  && <SourcesPage/>}
        {page === "trades"   && <TradesPage/>}
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

const pageTitle = (p) => p === "overview" ? "Overview" : p === "sources" ? "Data sources" : "Trades & decisions";

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
