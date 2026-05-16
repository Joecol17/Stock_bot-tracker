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
  const totalPLPct = totalValue - totalPL !== 0 ? (totalPL / (totalValue - totalPL)) * 100 : 0;
  const filled     = D.decisions.filter(d => d.status === "filled").length;
  const totalDec   = D.decisions.length;
  const buys       = D.decisions.filter(d => d.action === "BUY").length;
  const sells      = D.decisions.filter(d => d.action === "SELL").length;
  const holds      = D.decisions.filter(d => d.action === "HOLD").length;
  const equityVals = D.equity.map(p => p.v);

  // pipeline cycle indicator
  const cycleSec = 18;
  const tSec = Math.floor(Date.now() / 1000) % cycleSec;
  const stepIdx = Math.floor((tSec / cycleSec) * 5);

  const steps = [
    { label: "01", name: "Fetch context",  meta: "feeds × 4"  },
    { label: "02", name: "Build prompt",   meta: "ctx → json"   },
    { label: "03", name: "Ollama decide",  meta: "llama2"       },
    { label: "04", name: "Execute order",  meta: "T212 API"    },
    { label: "05", name: "Log & monitor",  meta: "trade_log"    },
  ];

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
          <span className="kpi-foot">Today · 6 positions</span>
          <svg className="kpi-spark" viewBox="0 0 88 36" preserveAspectRatio="none">
            <Sparkline points={equityVals.slice(-30)} color={totalPL>=0?"oklch(74% 0.16 148)":"oklch(68% 0.19 25)"} w={88} h={36}/>
          </svg>
        </div>
        <div className="kpi">
          <span className="kpi-label">Free funds</span>
          <span className="kpi-value mono">${(D.free_funds||D.cash||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}</span>
          <span className="kpi-delta muted">{D.total_value > 0 ? ((D.free_funds||D.cash||0)/D.total_value*100).toFixed(1)+'% buying power' : 'buying power'}</span>
          <span className="kpi-foot">{D.mode||'DEMO'} · Trading 212</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">Decisions today</span>
          <span className="kpi-value mono">{totalDec}<span className="unit">  /  10 limit</span></span>
          <span className="kpi-delta">
            <span style={{color:"var(--pos)"}}>BUY {buys}</span> &nbsp;
            <span style={{color:"var(--neg)"}}>SELL {sells}</span> &nbsp;
            <span className="muted">HOLD {holds}</span>
          </span>
          <span className="kpi-foot">{filled} filled · {totalDec - filled} skipped</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">Bot uptime</span>
          <span className="kpi-value mono">04:17:<span style={{fontSize:18,opacity:.7}}>22</span></span>
          <span className="kpi-delta pos">▲ all systems live</span>
          <span className="kpi-foot">Cycle {Math.floor((Date.now()/1000)%cycleSec)+1}/{cycleSec}s · llama2 · t=0.2</span>
        </div>
      </div>

      {/* Pipeline */}
      <div className="card">
        <div className="card-head">
          <h3>Decision pipeline</h3>
          <span className="chip accent"><span className="dot dot-amber" style={{width:6,height:6,borderRadius:"50%",background:"currentColor"}}></span> running</span>
          <span className="meta">cycle every 5 min · last @ 10:42:11</span>
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
                    width: i < stepIdx ? "100%" : i === stepIdx ? `${(tSec / cycleSec) * 100 * 5 % 100}%` : "0%",
                    background: i === stepIdx ? "var(--accent)" : i < stepIdx ? "var(--pos)" : "var(--surface-hi)",
                    transition: "width 200ms linear"
                  }}/>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Equity + side col */}
      <div className="row row-2">
        <div className="card">
          <div className="card-head">
            <h3>Portfolio value · today</h3>
            <div className="tabs" style={{ marginLeft: 12 }}>
              <span className="tab">1H</span>
              <span className="tab active">1D</span>
              <span className="tab">1W</span>
              <span className="tab">1M</span>
            </div>
            <span className="meta">USD · demo</span>
          </div>
          <div className="card-body">
            <AreaChart data={D.equity} height={240}/>
            <div style={{ display:"flex", gap:18, marginTop:10, fontFamily:"var(--mono)", fontSize:11, color:"var(--text-mute)" }}>
              <span>09:30 OPEN</span>
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
              <Donut value={0.72} label="72%" color="var(--accent)"/>
              <div>
                <div className="muted mono" style={{ fontSize:10, letterSpacing:"0.1em", textTransform:"uppercase" }}>Avg model confidence</div>
                <div style={{ fontFamily:"var(--display)", fontSize:20, fontWeight:500, marginTop:2 }}>Healthy</div>
                <div className="dim mono" style={{ fontSize:10, marginTop:2 }}>llama2 · temperature 0.2</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Risk + activity */}
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
            <RiskRow label="Daily trade limit"        value={`${totalDec} / 10`}      pct={totalDec/10} tone="info"/>
            <RiskRow label="Free funds threshold"     value="$4,127  /  $100 min"      pct={0.18}      tone="pos"/>
            <RiskRow label="Max position concentration" value="AAPL · 23.5%"            pct={0.235}     tone="warn"/>
            <RiskRow label="Decision confidence"      value="0.68 avg / 0.50 min"     pct={0.68}      tone="accent"/>
            <RiskRow label="Order failure rate"       value="0.0%"                    pct={0.0}       tone="pos"/>
            <div className="divider"/>
            <div className="kv">
              <span className="k">Mode</span><span className="v"><span className="chip warn">DEMO · practice</span></span>
            </div>
            <div className="kv">
              <span className="k">API key</span><span className="v mono">tk_•••••••••••3f9b</span>
            </div>
            <div className="kv">
              <span className="k">Model</span><span className="v mono">llama2 · t=0.2 · max 256</span>
            </div>
            <div className="kv">
              <span className="k">Symbols</span><span className="v mono">AAPL · GOOGL · MSFT · ASML · TSM · NVO</span>
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
        width: `${Math.min(100, pct*100)}%`,
        background: tone === "pos" ? "var(--pos)" : tone === "neg" ? "var(--neg)" : tone === "warn" ? "var(--warn)" : tone === "accent" ? "var(--accent)" : "var(--info)"
      }}/>
    </div>
  </div>
);

window.OverviewPage = OverviewPage;
