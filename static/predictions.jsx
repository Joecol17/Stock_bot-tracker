/* Predictions — full-page profit forecast from recorded equity history */
const { useState: useStateP, useEffect: useEffectP } = React;

const _money  = (n) => "$" + Math.abs(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const _signed = (n) => (n >= 0 ? "+" : "−") + _money(n);
const _tone   = (n) => (n >= 0 ? "var(--pos)" : "var(--neg)");

const PredictionsPage = () => {
  const D = window.BotData;
  // Pull a fresh projection on mount (botdata also keeps D.projections current)
  const [p, setP] = useStateP(D.projections || { ready: false, days_tracked: 0 });

  useEffectP(() => {
    let alive = true;
    fetch("/api/predictions")
      .then(r => r.json())
      .then(d => { if (alive && d) setP(d); })
      .catch(() => {});
    return () => { alive = false; };
  }, [D.projections]);

  const ready = !!p.ready;
  const confChip = p.confidence === "high" ? "pos" : p.confidence === "medium" ? "warn" : "neg";
  const confVal  = p.confidence === "high" ? 0.95 : p.confidence === "medium" ? 0.6 : 0.3;

  // Real recorded equity curve (falls back to the live equity series)
  const curve = (Array.isArray(p.history) && p.history.length > 1)
    ? p.history.map((h, i) => ({ i, v: h.v }))
    : D.equity;
  const vals = curve.map(c => c.v);

  const horizons = [
    { lbl: "Per day",   prof: p.proj_day,   val: p.proj_day_value,   sub: "1 trading day"   },
    { lbl: "Per month", prof: p.proj_month, val: p.proj_month_value, sub: "21 trading days" },
    { lbl: "Per year",  prof: p.proj_year,  val: p.proj_year_value,  sub: "252 trading days"},
  ];

  return (
    <div className="page">
      {/* Forecast banner */}
      <div style={{
        display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap",
        padding: "10px 16px", background: "var(--bg-elev)",
        border: "1px solid var(--border-soft)", borderRadius: "var(--radius)",
        fontFamily: "var(--mono)", fontSize: 12,
      }}>
        <span style={{ color: "var(--text-dim)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em" }}>
          Profit forecast
        </span>
        {ready
          ? <span className={`chip ${confChip}`}>{p.confidence} confidence</span>
          : <span className="chip">building</span>}
        <span className="dim">
          {ready ? `${p.days_tracked} day${p.days_tracked === 1 ? "" : "s"} of equity tracked` : "needs 2+ days of data"}
        </span>
        <span style={{ marginLeft: "auto", color: "var(--text-dim)" }}>
          Linear least-squares fit · {D.mode || "DEMO"}
        </span>
      </div>

      {!ready ? (
        <div className="card">
          <div className="card-body" style={{ padding: "48px 24px", textAlign: "center" }}>
            <div style={{ fontSize: 38, marginBottom: 14 }}>📊</div>
            <div style={{ fontFamily: "var(--display)", fontSize: 18, fontWeight: 500, marginBottom: 6 }}>
              Building your forecast
            </div>
            <div className="dim mono" style={{ fontSize: 12 }}>
              {p.days_tracked || 0} day{p.days_tracked === 1 ? "" : "s"} of equity recorded so far.<br/>
              Projections appear once there are 2+ days of history — the bot records one
              snapshot per day it runs.
            </div>
          </div>
        </div>
      ) : (
        <React.Fragment>
          {/* Projection KPIs */}
          <div className="kpi-grid" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
            {horizons.map(h => (
              <div className="kpi" key={h.lbl}>
                <span className="kpi-label">Projected profit · {h.lbl.toLowerCase()}</span>
                <span className="kpi-value mono" style={{ color: _tone(h.prof) }}>{_signed(h.prof)}</span>
                <span className="kpi-delta muted">→ {_money(h.val)} total</span>
                <span className="kpi-foot">{h.sub}</span>
              </div>
            ))}
          </div>

          {/* Recorded equity curve */}
          <div className="card">
            <div className="card-head">
              <h3>Recorded equity · {p.days_tracked} days</h3>
              <span className="meta">USD · {D.mode || "DEMO"}</span>
            </div>
            <div className="card-body">
              <AreaChart data={curve} height={260}/>
              <div style={{ display:"flex", gap:18, marginTop:10, fontFamily:"var(--mono)", fontSize:11, color:"var(--text-mute)" }}>
                <span>START ${(p.start_value||vals[0]||0).toLocaleString("en-US",{maximumFractionDigits:0})}</span>
                <span style={{marginLeft:"auto"}}>HIGH ${Math.max(...vals).toLocaleString("en-US",{maximumFractionDigits:0})}</span>
                <span>LOW ${Math.min(...vals).toLocaleString("en-US",{maximumFractionDigits:0})}</span>
                <span>NOW <b style={{color:"var(--text)"}}>${(p.current_value||vals[vals.length-1]||0).toLocaleString("en-US",{maximumFractionDigits:0})}</b></span>
              </div>
            </div>
          </div>

          {/* Outlook + trend statistics */}
          <div className="row row-2">
            {/* 1-year outlook */}
            <div className="card">
              <div className="card-head">
                <h3>One-year outlook</h3>
                <span className={`chip ${confChip}`}>{p.confidence}</span>
              </div>
              <div className="card-body" style={{ display:"flex", alignItems:"center", gap: 20 }}>
                <Donut value={confVal} label={p.confidence} color="var(--accent)" size={104} stroke={11}/>
                <div style={{ display:"flex", flexDirection:"column", gap: 4 }}>
                  <span className="muted mono" style={{ fontSize:10, letterSpacing:"0.1em", textTransform:"uppercase" }}>
                    Projected value in 1 year
                  </span>
                  <span className="mono" style={{ fontFamily:"var(--display)", fontSize:30, fontWeight:600, color: _tone(p.proj_year) }}>
                    {_money(p.proj_year_value)}
                  </span>
                  <span className="dim mono" style={{ fontSize:11 }}>
                    {_signed(p.proj_year)} ({p.total_profit_pct >= 0 ? "+" : ""}
                    {(p.avg_daily_pct * 252).toFixed(0)}% projected)
                  </span>
                  <span className="dim" style={{ fontSize:11, marginTop:6 }}>
                    Extrapolated from {p.days_tracked} days at {p.avg_daily_pct >= 0 ? "+" : ""}{p.avg_daily_pct}%/day.
                  </span>
                </div>
              </div>
            </div>

            {/* Trend statistics */}
            <div className="card">
              <div className="card-head">
                <h3>Trend statistics</h3>
                <span className="meta">since tracking began</span>
              </div>
              <div className="card-body" style={{ display:"flex", flexDirection:"column", gap: 12 }}>
                <div className="kv"><span className="k">Starting equity</span><span className="v mono">{_money(p.start_value)}</span></div>
                <div className="kv"><span className="k">Current equity</span><span className="v mono">{_money(p.current_value)}</span></div>
                <div className="kv">
                  <span className="k">Total profit</span>
                  <span className="v mono" style={{ color: _tone(p.total_profit) }}>
                    {_signed(p.total_profit)} ({p.total_profit_pct >= 0 ? "+" : ""}{p.total_profit_pct}%)
                  </span>
                </div>
                <div className="kv">
                  <span className="k">Avg profit / day</span>
                  <span className="v mono" style={{ color: _tone(p.avg_daily_profit) }}>{_signed(p.avg_daily_profit)}</span>
                </div>
                <div className="kv">
                  <span className="k">Avg return / day</span>
                  <span className="v mono" style={{ color: _tone(p.avg_daily_pct) }}>
                    {p.avg_daily_pct >= 0 ? "+" : ""}{p.avg_daily_pct}%
                  </span>
                </div>
                <div className="divider"/>
                <div className="dim" style={{ fontSize:11, lineHeight:1.5 }}>
                  Projections are a straight-line estimate of the recorded equity curve —
                  not a guarantee. They reflect how the account has trended so far, not
                  future market moves.
                </div>
              </div>
            </div>
          </div>
        </React.Fragment>
      )}
    </div>
  );
};

window.PredictionsPage = PredictionsPage;
