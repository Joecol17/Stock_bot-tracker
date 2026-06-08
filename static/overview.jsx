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

  // Market regime
  const regime     = D.regime || {};
  const regimeLabel= regime.regime || "unknown";
  const regimeColor= regimeLabel === "bull" ? "var(--pos)" : regimeLabel === "bear" ? "var(--neg)" : "var(--warn)";
  const regimeIcon = regimeLabel === "bull" ? "▲" : regimeLabel === "bear" ? "▼" : "○";

  // Swing stats
  const avgHoldDays = useMemo(() => {
    const held = D.decisions.filter(d => d.expected_hold_days > 0);
    return held.length ? Math.round(held.reduce((s, d) => s + d.expected_hold_days, 0) / held.length) : null;
  }, [D.decisions]);
  const avgRR = useMemo(() => {
    const rr = D.decisions.filter(d => d.risk_reward > 0);
    return rr.length ? (rr.reduce((s, d) => s + d.risk_reward, 0) / rr.length).toFixed(1) : null;
  }, [D.decisions]);
  const longestHeld = D.positions.reduce((best, p) => {
    return (p.days_held != null && (best == null || p.days_held > best.days_held)) ? p : best;
  }, null);

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

      {/* Market Regime Banner */}
      <div style={{
        display: "flex", alignItems: "center", gap: 16,
        padding: "10px 16px",
        background: "var(--bg-elev)",
        border: "1px solid var(--border-soft)",
        borderRadius: "var(--radius)",
        fontFamily: "var(--mono)", fontSize: 12,
      }}>
        <span style={{ color: "var(--text-dim)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em" }}>Market Regime</span>
        <span style={{
          fontWeight: 700, fontSize: 13, color: regimeColor,
          display: "flex", alignItems: "center", gap: 5,
        }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: regimeColor, display: "inline-block" }}/>
          {regimeLabel.toUpperCase()}
        </span>
        {D.in_focus_period && (
          <span className="chip overdrive"
                title={`Focus period ${D.focus_window || ""} — faster scans, more symbols, larger sizing`}>
            ⚡ OVERDRIVE
          </span>
        )}
        {regime.benchmark && (
          <span className="dim">{regime.benchmark} · ${(regime.price||0).toFixed(2)}</span>
        )}
        {regime.sma50 > 0 && (
          <span style={{ color: regime.above_sma50 ? "var(--pos)" : "var(--neg)" }}>
            SMA50 ${(regime.sma50||0).toFixed(0)} {regime.above_sma50 ? "✓" : "✗"}
          </span>
        )}
        {regime.sma200 > 0 && (
          <span style={{ color: regime.above_sma200 ? "var(--pos)" : "var(--neg)" }}>
            SMA200 ${(regime.sma200||0).toFixed(0)} {regime.above_sma200 ? "✓" : "✗"}
          </span>
        )}
        <span style={{ marginLeft: "auto", color: "var(--text-dim)" }}>
          Risk/trade: <b style={{ color: "var(--text)" }}>{((D.risk_per_trade_pct||0.01)*100).toFixed(0)}%</b>
          &nbsp;·&nbsp;
          ATR stop: <b style={{ color: "var(--text)" }}>{D.atr_stop_multiplier||1.5}×</b>
          &nbsp;·&nbsp;
          Min R:R: <b style={{ color: "var(--text)" }}>{D.min_risk_reward||2}:1</b>
          &nbsp;·&nbsp;
          Filter gate: <b style={{ color: "var(--text)" }}>{D.min_filter_score||2}/4</b>
        </span>
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
          <span className={`chip ${D.bot_status === "running" ? "accent" : ""}`}
            style={D.bot_status === "running" ? { display:"flex", alignItems:"center", gap:6 } : {}}>
            {D.bot_status === "running" && (
              <span style={{ width:7, height:7, borderRadius:"50%", background:"var(--accent)", display:"inline-block",
                boxShadow:"0 0 0 3px oklch(78% 0.14 70 / .25)", animation:"pulse 1.4s ease infinite" }}/>
            )}
            {D.bot_status === "running"
              ? `${D.step_name || "running"}${D.current_symbol ? " · " + D.current_symbol : ""}`
              : `idle · cycle #${D.cycle || 0}`}
          </span>
          <span className="meta">
            {(D.cycle_interval||86400) >= 3600
              ? `every ${Math.round((D.cycle_interval||86400)/3600)}h`
              : `every ${Math.round((D.cycle_interval||86400)/60)} min`}
            {" · last @ "}{lastCycleTime}
          </span>
        </div>
        <div className="card-body">
          {/* Connected-dot progress track */}
          <div className="pipe-track">
            {steps.map((s, i) => {
              const isRunning = D.bot_status === "running";
              const done    = isRunning && i < stepIdx;
              const active  = isRunning && i === stepIdx;
              const pending = isRunning && i > stepIdx;
              const ready   = !isRunning;
              const nodeClass = done ? "done" : active ? "active" : pending ? "pending" : "ready";
              return (
                <React.Fragment key={i}>
                  <div className={`pipe-node ${nodeClass}`}>
                    <div className="pipe-dot">
                      {done   && <svg viewBox="0 0 10 10" width="10" height="10"><polyline points="2,5 4.5,7.5 8,2.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
                      {active && <span className="pipe-dot-inner"/>}
                      {(ready || pending) && <span style={{ width:6, height:6, borderRadius:"50%", background:"var(--border)", display:"block" }}/>}
                    </div>
                    <div className="pipe-node-body">
                      <span className="pipe-node-num">{s.label}</span>
                      <span className="pipe-node-name">{s.name}</span>
                      <span className="pipe-node-meta">{s.meta}</span>
                    </div>
                  </div>
                  {i < steps.length - 1 && (
                    <div className={`pipe-connector ${done ? "done" : ""}`}/>
                  )}
                </React.Fragment>
              );
            })}
          </div>
          {/* Status strip */}
          <div className="pipe-strip">
            {D.bot_status === "running"
              ? <span style={{ color:"var(--accent)" }}>▶ Step {D.step}/5 — <b>{D.step_name}</b>{D.current_symbol ? ` · ${D.current_symbol}` : ""}</span>
              : D.cycle > 0
                ? <span>Last cycle completed @ <b style={{ color:"var(--text)" }}>{lastCycleTime}</b> &nbsp;·&nbsp; {D.cycle} total cycle{D.cycle !== 1 ? "s" : ""} run</span>
                : <span>Bot not yet started &nbsp;·&nbsp; run <b style={{ color:"var(--text)" }}>start_bot.bat</b> to begin</span>
            }
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

      {/* Profit projections */}
      <ProjectionsCard />

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
            <h3>Risk & swing stats</h3>
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
              label="Free funds"
              value={`$${(D.free_funds||D.cash||0).toFixed(0)}  /  min $${D.min_account_value||100}`}
              pct={D.min_account_value > 0 ? Math.min(1, (D.free_funds||D.cash||0) / (D.min_account_value * 20)) : 1}
              tone="pos"
            />
            <RiskRow
              label="Largest position"
              value={maxPos ? `${maxPos.symbol} · ${(maxPosPct*100).toFixed(1)}% of portfolio` : "—"}
              pct={maxPosPct}
              tone={maxPosPct > 0.4 ? "warn" : maxPosPct > 0.25 ? "accent" : "pos"}
            />
            <RiskRow
              label="Avg model confidence"
              value={avgConf > 0 ? `${(avgConf*100).toFixed(0)}%` : "no data"}
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
            {/* Swing accountability rows */}
            <div className="kv">
              <span className="k">Avg hold target</span>
              <span className="v mono">{avgHoldDays != null ? `${avgHoldDays} day${avgHoldDays !== 1 ? "s" : ""}` : "—"}</span>
            </div>
            <div className="kv">
              <span className="k">Avg R:R (decisions)</span>
              <span className="v mono" style={{ color: avgRR >= D.min_risk_reward ? "var(--pos)" : "var(--warn)" }}>
                {avgRR != null ? `${avgRR}:1` : "—"}
                {D.min_risk_reward && avgRR != null && (
                  <span className="dim" style={{ fontSize:10, marginLeft: 5 }}>min {D.min_risk_reward}:1</span>
                )}
              </span>
            </div>
            <div className="kv">
              <span className="k">Longest held</span>
              <span className="v mono" style={{ color: longestHeld && longestHeld.days_held >= (D.max_hold_days||10) ? "var(--warn)" : "var(--text)" }}>
                {longestHeld ? `${longestHeld.symbol} · ${longestHeld.days_held}d` : "—"}
                {longestHeld && longestHeld.days_held >= (D.max_hold_days||10) && (
                  <span className="chip warn" style={{ marginLeft: 6, fontSize: 9 }}>review</span>
                )}
              </span>
            </div>
            <div className="divider"/>
            <div className="kv">
              <span className="k">Mode</span>
              <span className="v">
                <span className={`chip ${D.mode === "LIVE" ? "pos" : "warn"}`}>
                  {D.mode || "DEMO"} · {D.mode === "LIVE" ? "live" : "practice"}
                </span>
              </span>
            </div>
            <div className="kv">
              <span className="k">Model</span>
              <span className="v mono">{D.model || "llama2"} · t={D.temperature || 0.2}</span>
            </div>
            <div className="kv">
              <span className="k">Filter gate</span>
              <span className="v mono">{D.min_filter_score||2}/4 filters · earnings buffer {D.earnings_buffer_days||5}d</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const ProjectionsCard = () => {
  const D = window.BotData;
  const p = D.projections || {};
  const sfmt = (n) => (n >= 0 ? "+" : "−") + "$" +
    Math.abs(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const tone = (n) => (n >= 0 ? "var(--pos)" : "var(--neg)");
  const confChip = p.confidence === "high" ? "pos" : p.confidence === "medium" ? "warn" : "neg";

  const cells = [
    ["Per day",   p.proj_day],
    ["Per month", p.proj_month],
    ["Per year",  p.proj_year],
  ];

  return (
    <div className="card">
      <div className="card-head">
        <h3>Profit projections</h3>
        {p.ready
          ? <span className={`chip ${confChip}`}>{p.confidence} confidence</span>
          : <span className="chip">building</span>}
        <span className="meta">{p.ready ? `${p.days_tracked} days tracked` : "needs 2+ days of data"}</span>
      </div>
      <div className="card-body">
        {!p.ready ? (
          <div style={{ padding: "24px 16px", textAlign: "center", color: "var(--text-dim)", fontFamily: "var(--mono)", fontSize: 12 }}>
            📊 Building forecast — {p.days_tracked || 0} day{p.days_tracked === 1 ? "" : "s"} of equity recorded.<br/>
            <span style={{ fontSize: 11, color: "var(--text-mute)" }}>Projections appear after 2+ days of data.</span>
          </div>
        ) : (
          <React.Fragment>
            <div className="kpi-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
              {cells.map(([lbl, val]) => (
                <div className="kpi" key={lbl}>
                  <span className="kpi-label">{lbl}</span>
                  <span className="kpi-value mono" style={{ color: tone(val) }}>{sfmt(val)}</span>
                </div>
              ))}
            </div>
            <div className="divider" style={{ margin: "14px 0" }}/>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 18px", fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-mute)" }}>
              <span>Trend so far: <b style={{ color: tone(p.total_profit) }}>{sfmt(p.total_profit)}</b> ({p.total_profit_pct >= 0 ? "+" : ""}{p.total_profit_pct}%)</span>
              <span>Avg <b style={{ color: "var(--text)" }}>{p.avg_daily_pct >= 0 ? "+" : ""}{p.avg_daily_pct}%/day</b></span>
              <span>Proj. 1y value: <b style={{ color: "var(--text)" }}>${(p.proj_year_value || 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}</b></span>
              <span style={{ color: "var(--text-dim)" }}>Linear estimate from recorded equity — not a guarantee.</span>
            </div>
          </React.Fragment>
        )}
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
