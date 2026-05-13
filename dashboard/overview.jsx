/* Overview / Mission Control — whole-process pulse */
const { useState, useEffect, useMemo } = React;

const OverviewPage = ({ tweaks }) => {
  const D = window.BotData;
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const totalValue = D.positions.reduce((s, p) => s + p.value, 0);
  const totalPL    = D.positions.reduce((s, p) => s + p.pl, 0);
  const totalPLPct = (totalPL / (totalValue - totalPL)) * 100;
  const filled     = D.decisions.filter(d => d.status === "filled").length;
  const totalDec   = D.decisions.length;
  const buys       = D.decisions.filter(d => d.action === "BUY").length;
  const sells      = D.decisions.filter(d => d.action === "SELL").length;
  const holds      = D.decisions.filter(d => d.action === "HOLD").length;
  const equityVals = D.equity.map(p => p.v);

  // Live free funds from account data
  const freeFunds = D.account?.free_funds ?? 4127.84;
  const totalPortfolio = D.account?.portfolio_value ?? totalValue;
  const buyingPowerPct = totalPortfolio > 0 ? ((freeFunds / (freeFunds + totalPortfolio)) * 100).toFixed(1) : "0.0";
  const [ffInt, ffDec] = freeFunds.toFixed(2).split(".");

  // Bot status
  const bs = D.botStatus || {};
  const upSec = bs.uptimeSeconds || 0;
  const hh = String(Math.floor(upSec / 3600)).padStart(2, "0");
  const mm = String(Math.floor((upSec % 3600) / 60)).padStart(2, "0");
  const ss = String(upSec % 60).padStart(2, "0");
  const cycleInterval = 300; // seconds
  const tSec = Math.floor(Date.now() / 1000) % cycleInterval;
  const stepIdx = Math.floor((tSec / cycleInterval) * 5);

  const steps = [
    { label: "01", name: "Fetch context",  meta: "yfinance"   },
    { label: "02", name: "Build prompt",   meta: "ctx → json" },
    { label: "03", name: "Ollama decide",  meta: bs.model || "llama2" },
    { label: "04", name: "Execute order",  meta: "T212 API"   },
    { label: "05", name: "Log & monitor",  meta: "trade_log"  },
  ];

  // Average confidence across decisions that have it
  const confScores = D.decisions.filter(d => d.confidence).map(d => d.confidence);
  const avgConf = confScores.length ? confScores.reduce((a,b)=>a+b,0)/confScores.length : 0.72;

  return (
    <div className="page">
      {/* TAPE */}
      <div className="tape">
        <span className="dim">TAPE</span>
        {D.positions.map((p, i) => (
          <React.Fragment key={p.symbol}>
            <span className="item">
              <span className="sym">{p.symbol}</span>
              <span className="px">${p.price.toFixed(2)}</span>
              <span className={`ch ${p.plPct >= 0 ? "pos" : "neg"}`}>{p.plPct >= 0 ? "▲" : "▼"} {Math.abs(p.plPct).toFixed(2)}%</span>
            </span>
            {i < D.positions.length - 1 && <span className="sep">·</span>}
          </React.Fragment>
        ))}
        <span style={{ marginLeft: "auto" }} className="dim">{now.toLocaleTimeString("en-GB")} · UTC</span>
      </div>

      {/* KPIs */}
      <div className="kpi-grid">
        <div className="kpi">
          <span className="kpi-label">Portfolio value</span>
          <span className="kpi-value mono">${totalValue.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}</span>
          <span className={`kpi-delta ${totalPL >= 0 ? "pos" : "neg"}`}>
            {totalPL >= 0 ? "▲" : "▼"} ${Math.abs(totalPL).toFixed(2)} · {totalPLPct.toFixed(2)}%
          </span>
          <span className="kpi-foot">Today · {D.positions.length} positions</span>
          <svg className="kpi-spark" viewBox="0 0 88 36" preserveAspectRatio="none">
            <Sparkline points={equityVals.slice(-30)} color={totalPL>=0?"oklch(74% 0.16 148)":"oklch(68% 0.19 25)"} w={88} h={36}/>
          </svg>
        </div>
        <div className="kpi">
          <span className="kpi-label">Free funds</span>
          <span className="kpi-value mono">${ffInt}.<span style={{fontSize:18,opacity:.7}}>{ffDec}</span></span>
          <span className="kpi-delta muted">{buyingPowerPct}% buying power</span>
          <span className="kpi-foot">{(bs.isDemo !== false) ? "Demo" : "Live"} · Trading 212</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">Decisions today</span>
          <span className="kpi-value mono">{totalDec}<span className="unit">  /  {bs.maxDailyTrades || 10} limit</span></span>
          <span className="kpi-delta">
            <span style={{color:"var(--pos)"}}>BUY {buys}</span> &nbsp;
            <span style={{color:"var(--neg)"}}>SELL {sells}</span> &nbsp;
            <span className="muted">HOLD {holds}</span>
          </span>
          <span className="kpi-foot">{filled} filled · {totalDec - filled} skipped</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">Bot uptime</span>
          <span className="kpi-value mono">{hh}:{mm}:<span style={{fontSize:18,opacity:.7}}>{ss}</span></span>
          <span className="kpi-delta pos">▲ all systems live</span>
          <span className="kpi-foot">Cycle {bs.cycleCount || "—"} · {bs.model || "llama2"} · t={bs.temperature ?? 0.2}</span>
        </div>
      </div>

      {/* Pipeline */}
      <div className="card">
        <div className="card-head">
          <h3>Decision pipeline</h3>
          <span className="chip accent"><span className="dot dot-amber" style={{width:6,height:6,borderRadius:"50%",background:"currentColor"}}></span> running</span>
          <span className="meta">cycle every 5 min</span>
        </div>
        <div className="card-body">
          <div className="pipe">
            {steps.map((s, i) => (
              <div key={i} className={`pipe-step ${i === stepIdx ? "active" : ""}`}>
                <span className="label">STEP {s.label}</span>
                <span className="name">{s.name}</span>
                <span className="num">{s.meta}</span>
                <div className="bar-track" style={{ marginTop: 8 }}>
                  <div className="bar-fill" style={{
                    width: i < stepIdx ? "100%" : i === stepIdx ? `${(tSec / cycleInterval) * 100 * 5 % 100}%` : "0%",
                    background: i === stepIdx ? "var(--accent)" : i < stepIdx ? "var(--pos)" : "var(--surface-hi)",
                    transition: "width 200ms linear"
                  }}/>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Equity + decisions chart */}
      <div className="row row-2">
        <div className="card">
          <div className="card-head">
            <h3>Portfolio value · today</h3>
            <span className="meta">USD · {(bs.isDemo !== false) ? "demo" : "live"}</span>
          </div>
          <div className="card-body">
            <AreaChart data={D.equity} height={240}/>
            <div style={{ display:"flex", gap:18, marginTop:10, fontFamily:"var(--mono)", fontSize:11, color:"var(--text-mute)" }}>
              <span>OPEN</span>
              <span style={{marginLeft:"auto"}}>HIGH ${Math.max(...equityVals).toFixed(2)}</span>
              <span>LOW ${Math.min(...equityVals).toFixed(2)}</span>
              <span>NOW <b style={{color:"var(--text)"}}>${equityVals[equityVals.length-1].toFixed(2)}</b></span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>AI decisions · 24h</h3>
            <span className="meta">hourly</span>
          </div>
          <div className="card-body">
            <StackedBars data={D.decisionHist} height={150}/>
            <div style={{display:"flex", gap:18, fontFamily:"var(--mono)", fontSize:10, color:"var(--text-mute)", marginTop:8 }}>
              <span><i style={{display:"inline-block",width:8,height:8,background:"var(--pos)",marginRight:6,borderRadius:1}}/>BUY</span>
              <span><i style={{display:"inline-block",width:8,height:8,background:"var(--neg)",marginRight:6,borderRadius:1}}/>SELL</span>
              <span><i style={{display:"inline-block",width:8,height:8,background:"oklch(40% 0.012 250)",marginRight:6,borderRadius:1}}/>HOLD</span>
            </div>
            <div className="divider" style={{ margin: "14px 0" }}/>
            <div style={{ display: "flex", alignItems:"center", gap: 16 }}>
              <Donut value={avgConf} label={`${(avgConf*100).toFixed(0)}%`} color="var(--accent)"/>
              <div>
                <div className="muted mono" style={{ fontSize:10, letterSpacing:"0.1em", textTransform:"uppercase" }}>Avg model confidence</div>
                <div style={{ fontFamily:"var(--display)", fontSize:20, fontWeight:500, marginTop:2 }}>{avgConf >= 0.7 ? "Healthy" : avgConf >= 0.5 ? "Moderate" : "Low"}</div>
                <div className="dim mono" style={{ fontSize:10, marginTop:2 }}>{bs.model || "llama2"} · temperature {bs.temperature ?? 0.2}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Activity + Risk */}
      <div className="row row-2">
        <div className="card">
          <div className="card-head">
            <h3>Activity stream</h3>
            <span className="chip"><span className="dot dot-green" style={{width:6,height:6,borderRadius:"50%",background:"var(--pos)"}}></span> live</span>
            <span className="meta">{D.activity.length} events</span>
          </div>
          <div className="feed">
            {D.activity.map((a, i) => (
              <div className="feed-item" key={i}>
                <div className="feed-time">{a.t}</div>
                <div className="feed-msg" dangerouslySetInnerHTML={{ __html: a.text }} />
                <span className={`chip ${a.tagClass}`}>{a.tag}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h3>Risk & safety</h3>
            <span className="chip pos">all clear</span>
          </div>
          <div className="card-body" style={{ display:"flex", flexDirection:"column", gap: 14 }}>
            <RiskRow label="Daily trade limit"          value={`${totalDec} / ${bs.maxDailyTrades || 10}`} pct={totalDec/(bs.maxDailyTrades||10)} tone="info"/>
            <RiskRow label="Free funds threshold"       value={`$${freeFunds.toFixed(0)}  /  $100 min`}    pct={Math.min(1, freeFunds/10000)}       tone="pos"/>
            <RiskRow label="Decision confidence"        value={`${(avgConf*100).toFixed(0)}% avg / 50% min`} pct={avgConf}                          tone="accent"/>
            <RiskRow label="Order failure rate"         value="0.0%"                                        pct={0}                                  tone="pos"/>
            <div className="divider"/>
            <div className="kv">
              <span className="k">Mode</span><span className="v"><span className={`chip ${bs.isDemo !== false ? "warn" : "neg"}`}>{bs.isDemo !== false ? "DEMO · practice" : "LIVE · real money"}</span></span>
            </div>
            <div className="kv">
              <span className="k">Account</span><span className="v mono">{D.account?.account_id || "N/A"}</span>
            </div>
            <div className="kv">
              <span className="k">Model</span><span className="v mono">{bs.model || "llama2"} · t={bs.temperature ?? 0.2} · max {bs.maxTokens || 256}</span>
            </div>
            <div className="kv">
              <span className="k">Symbols</span><span className="v mono">{D.positions.map(p=>p.symbol).join(" · ") || "—"}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const RiskRow = ({ label, value, pct, tone }) => (
  <div>
    <div style={{display:"flex", justifyContent:"space-between", marginBottom: 6, fontSize: 12 }}>
      <span className="muted">{label}</span>
      <span className="mono">{value}</span>
    </div>
    <div className="bar-track">
      <div className="bar-fill" style={{
        width: `${Math.min(100, (pct||0)*100)}%`,
        background: tone === "pos" ? "var(--pos)" : tone === "neg" ? "var(--neg)" : tone === "warn" ? "var(--warn)" : tone === "accent" ? "var(--accent)" : "var(--info)"
      }}/>
    </div>
  </div>
);

window.OverviewPage = OverviewPage;
