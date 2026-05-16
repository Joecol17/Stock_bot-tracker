/* Overview / Mission Control — whole-process pulse */
const { useState, useEffect, useMemo } = React;

// Format seconds into hh:mm:ss
const fmtUptime = (s) => {
  if (!s) return "00:00:00";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
};

const OverviewPage = ({ tweaks }) => {
  const D = window.BotData;
  const [now, setNow] = useState(new Date());
  const [uptime, setUptime] = useState(D.uptime_seconds || 0);

  useEffect(() => {
    const t = setInterval(() => {
      setNow(new Date());
      setUptime(u => u + 1);
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // Sync uptime when BotData refreshes
  useEffect(() => {
    if (D.uptime_seconds > 0) setUptime(D.uptime_seconds);
  }, [D.uptime_seconds]);

  const totalValue = D.positions.reduce((s, p) => s + p.value, 0);
  const totalPL    = D.positions.reduce((s, p) => s + p.pl, 0);
  const totalPLPct = totalValue - totalPL !== 0 ? (totalPL / (totalValue - totalPL)) * 100 : 0;
  const filled     = D.decisions.filter(d => d.status === "filled").length;
  const totalDec   = D.decisions.length;
  const buys       = D.decisions.filter(d => d.action === "BUY").length;
  const sells      = D.decisions.filter(d => d.action === "SELL").length;
  const holds      = D.decisions.filter(d => d.action === "HOLD").length;
  const equityVals = D.equity.map(p => p.v);
  const maxDaily   = D.max_daily_trades || 10;

  // Max position concentration
  const maxPos    = D.positions.length ? D.positions.reduce((a, b) => b.value > a.value ? b : a) : null;
  const maxPosPct = totalValue > 0 && maxPos ? maxPos.value / totalValue : 0;

  // Order failure rate
  const failedDec  = D.decisions.filter(d => d.status === "blocked").length;
  const failRate   = totalDec > 0 ? failedDec / totalDec : 0;

  // Pipeline: real step from bot_state (0=idle, 1=risk, 2=screen, 3=fetch, 4=ollama, 5=execute)
  // Map to the 5 display steps (indices 0-4)
  const stepIdx = D.step > 0 ? D.step - 1 : -1;  // -1 = idle
  const lastCycleTime = D.last_cycle_time
    ? D.last_cycle_time.slice(11, 19)
    : "—";

  const steps = [
    { label: "01", name: "Risk exits",    meta: "SL / TP check"   },
    { label: "02", name: "Screener",      meta: "watchlist rank"  },
    { label: "03", name: "Fetch context", meta: "yfinance + ta"   },
    { label: "04", name: "Ollama decide", meta: D.model || "llama2" },
    { label: "05", name: "Execute order", meta: "T212 API"         },
  ];

  // Confidence
  const avgConf = D.avg_confidence || 0;
  const confLabel = avgConf >= 0.7 ? "Healthy" : avgConf >= 0.5 ? "Moderate" : avgConf > 0 ? "Low" : "No data";

  // Uptime display split
  const uptimeStr = fmtUptime(uptime);
  const [uptimeMain, uptimeSub] = [uptimeStr.slice(0, 5), uptimeStr.slice(5)];

  return (
    <div className="page">
      {/* TAPE */}
      <div className="tape">
        <span className="dim">TAPE</span>
        {D.positions.length === 0 && <span className="dim" style={{ fontSize:11 }}>No open positions</span>}
        {D.positions.map((p, i) => (
          <React.Fragment key={p.symbol}>
            <span className="item">
              <span className="sym">{p.symbol}</span>
              <span className="px">${(p.price||0).toFixed(2)}</span>
              <span className={`ch ${p.plPct >= 0 ? "pos" : "neg"}`}>{p.plPct >= 0 ? "▲" : "▼"} {Math.abs(p.plPct||0).toFixed(2)}%</span>
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
          <span className="kpi-foot">Today · {D.positions.length} position{D.positions.length !== 1 ? "s" : ""}</span>
          <svg className="kpi-spark" viewBox="0 0 88 36" preserveAspectRatio="none">
            <Sparkline points={equityVals.slice(-30)} color={totalPL>=0?"oklch(74% 0.16 148)":"oklch(68% 0.19 25)"} w={88} h={36}/>
          </svg>
        </div>
        <div className="kpi">
          <span className="kpi-label">Free funds</span>
          <span className="kpi-value mono">${(D.free_funds||D.cash||0).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}</span>
          <span className="kpi-delta muted">
            {D.total_value > 0 ? ((D.free_funds||D.cash||0)/D.total_value*100).toFixed(1)+'% buying power' : 'buying power'}
          </span>
          <span className="kpi-foot">{D.mode || 'DEMO'} · Trading 212</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">Decisions today</span>
          <span className="kpi-value mono">{totalDec}<span className="unit">  /  {maxDaily} limit</span></span>
          <span className="kpi-delta">
            <span style={{color:"var(--pos)"}}>BUY {buys}</span> &nbsp;
            <span style={{color:"var(--neg)"}}>SELL {sells}</span> &nbsp;
            <span className="muted">HOLD {holds}</span>
          </span>
          <span className="kpi-foot">{filled} filled · {totalDec - filled} skipped</span>
        </div>
        <div className="kpi">
          <span className="kpi-label">Bot uptime</span>
          <span className="kpi-value mono">{uptimeMain}<span style={{fontSize:18,opacity:.7}}>{uptimeSub}</span></span>
          <span className={`kpi-delta ${D.bot_status === "running" ? "pos" : ""}`}>
            {D.bot_status === "running" ? "▲ all systems live" : D.bot_status === "idle" ? "○ idle" : "● stopped"}
          </span>
          <span className="kpi-foot">
            Cycle {D.cycle || 0} · {D.model || "llama2"} · t={D.temperature || 0.2}
          </span>
        </div>
      </div>

      {/* Pipeline */}
      <div className="card">
        <div className="card-head">
          <h3>Decision pipeline</h3>
          {D.bot_status === "running"
            ? <span className="chip accent"><span style={{width:6,height:6,borderRadius:"50%",background:"currentColor",display:"inline-block",marginRight:4}}/>
                {D.step_name || "running"}{D.current_symbol ? ` — ${D.current_symbol}` : ""}
              </span>
            : <span className="chip">idle</span>
          }
          <span className="meta">every {Math.round((D.cycle_interval||300)/60)} min · last @ {lastCycleTime}</span>
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
                    width: i < stepIdx ? "100%" : i === stepIdx ? "60%" : "0%",
                    background: i === stepIdx ? "var(--accent)" : i < stepIdx ? "var(--pos)" : "var(--surface-hi)",
                    transition: "width 400ms ease"
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
            <span className="meta">USD · {D.mode || "DEMO"}</span>
          </div>
          <div className="card-body">
            <AreaChart data={D.equity} height={240}/>
            <div style={{ display:"flex", gap:18, marginTop:10, fontFamily:"var(--mono)", fontSize:11, color:"var(--text-mute)" }}>
              <span>START</span>
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
              <Donut value={avgConf || 0.1} label={avgConf > 0 ? `${(avgConf*100).toFixed(0)}%` : "—"} color="var(--accent)"/>
              <div>
                <div className="muted mono" style={{ fontSize:10, letterSpacing:"0.1em", textTransform:"uppercase" }}>Avg model confidence</div>
                <div style={{ fontFamily:"var(--display)", fontSize:20, fontWeight:500, marginTop:2 }}>{confLabel}</div>
                <div className="dim mono" style={{ fontSize:10, marginTop:2 }}>{D.model || "llama2"} · temperature {D.temperature || 0.2}</div>
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
            <span className="chip"><span style={{width:6,height:6,borderRadius:"50%",background:"var(--pos)",display:"inline-block",marginRight:4}}/>live</span>
            <span className="meta">{D.activity.length} events</span>
          </div>
          {D.activity.length === 0
            ? <div style={{padding:"24px 16px", textAlign:"center", color:"var(--text-dim)", fontFamily:"var(--mono)", fontSize:12}}>No activity yet</div>
            : <div className="feed">
                {D.activity.map((a, i) => (
                  <div className="feed-item" key={i}>
                    <div className="feed-time">{a.t}</div>
                    <div className="feed-msg" dangerouslySetInnerHTML={{ __html: a.text }} />
                    <span className={`chip ${a.tagClass}`}>{a.tag}</span>
                  </div>
                ))}
              </div>
          }
        </div>

        <div className="card">
          <div className="card-head">
            <h3>Risk & safety</h3>
            <span className={`chip ${failRate > 0.2 ? "neg" : "pos"}`}>{failRate > 0.2 ? "warning" : "all clear"}</span>
          </div>
          <div className="card-body" style={{ display:"flex", flexDirection:"column", gap: 14 }}>
            <RiskRow
              label="Daily trade limit"
              value={`${totalDec} / ${maxDaily}`}
              pct={totalDec / maxDaily}
              tone={totalDec / maxDaily > 0.8 ? "warn" : "info"}
            />
            <RiskRow
              label="Free funds threshold"
              value={`$${(D.free_funds||D.cash||0).toFixed(0)}  /  $${D.min_account_value||100} min`}
              pct={D.min_account_value > 0 ? Math.min(1, (D.free_funds||D.cash||0) / (D.min_account_value * 20)) : 1}
              tone="pos"
            />
            <RiskRow
              label="Max position concentration"
              value={maxPos ? `${maxPos.symbol} · ${(maxPosPct*100).toFixed(1)}%` : "—"}
              pct={maxPosPct}
              tone={maxPosPct > 0.4 ? "warn" : maxPosPct > 0.25 ? "accent" : "pos"}
            />
            <RiskRow
              label="Decision confidence"
              value={avgConf > 0 ? `${avgConf.toFixed(2)} avg` : "no data"}
              pct={avgConf}
              tone={avgConf >= 0.7 ? "pos" : avgConf >= 0.5 ? "accent" : "neg"}
            />
            <RiskRow
              label="Order failure rate"
              value={`${(failRate * 100).toFixed(1)}%`}
              pct={failRate}
              tone={failRate > 0.2 ? "neg" : "pos"}
            />
            <div className="divider"/>
            <div className="kv">
              <span className="k">Mode</span>
              <span className="v">
                <span className={`chip ${D.mode === "LIVE" ? "pos" : "warn"}`}>
                  {D.mode || "DEMO"} · {D.mode === "LIVE" ? "live trading" : "practice"}
                </span>
              </span>
            </div>
            <div className="kv">
              <span className="k">Model</span>
              <span className="v mono">{D.model || "llama2"} · t={D.temperature || 0.2} · max {D.max_tokens || 256}</span>
            </div>
            <div className="kv">
              <span className="k">Watchlist</span>
              <span className="v mono" style={{ fontSize:11, wordBreak:"break-all" }}>
                {D.positions.length > 0 ? D.positions.map(p => p.symbol).join(" · ") : "—"}
              </span>
            </div>
            <div className="kv">
              <span className="k">Cycle</span>
              <span className="v mono">#{D.cycle || 0} · {D.step_name || "idle"}{D.current_symbol ? ` (${D.current_symbol})` : ""}</span>
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
