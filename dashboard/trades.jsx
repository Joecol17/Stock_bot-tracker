/* Trades — positions, decision log, orders, drill-in */
const { useState: useStateT, useMemo: useMemoT } = React;

const TradesPage = () => {
  const D = window.BotData;
  const [selectedId, setSelectedId] = useStateT(D.decisions[0].id);
  const [filter, setFilter] = useStateT("all");
  const [search, setSearch] = useStateT("");
  const selected = D.decisions.find(d => d.id === selectedId) || D.decisions[0];

  const filteredDec = D.decisions.filter(d => {
    const f = filter === "all" || d.action === filter.toUpperCase();
    const s = !search || d.symbol.toLowerCase().includes(search.toLowerCase());
    return f && s;
  });

  return (
    <div className="page">
      {/* POSITIONS GRID */}
      <div>
        <div style={{ display:"flex", alignItems:"center", marginBottom: 12 }}>
          <h3 style={{ fontFamily:"var(--display)", fontSize:14, fontWeight:500 }}>Open positions</h3>
          <span className="mono dim" style={{ marginLeft: 10, fontSize:11 }}>{D.positions.length} symbols · ${D.positions.reduce((s,p)=>s+p.value,0).toFixed(2)}</span>
          <div style={{ marginLeft:"auto", display:"flex", gap:8 }}>
            <button className="btn ghost"><I.Refresh className="ico"/>refresh</button>
            <button className="btn primary"><I.Bolt className="ico"/>Run cycle now</button>
          </div>
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(6, minmax(0, 1fr))", gap:10 }}>
          {D.positions.map(p => (
            <div key={p.symbol} className="symbol-tile" style={{ minWidth: 0 }}>
              <div className="top">
                <span className="sym">{p.symbol}</span>
                <span className="name">{p.flag}</span>
              </div>
              <div style={{ display:"flex", alignItems:"baseline", gap:8 }}>
                <span className="price">${p.price.toFixed(2)}</span>
                <span className={`change ${p.plPct >= 0 ? "pos" : "neg"}`}>
                  {p.plPct >= 0 ? "▲" : "▼"} {Math.abs(p.plPct).toFixed(2)}%
                </span>
              </div>
              <Sparkline points={sparks[p.symbol]} color={p.plPct >= 0 ? "var(--pos)" : "var(--neg)"} w={170} h={28} full/>
              <div className="mono dim" style={{ fontSize:10, display:"flex", justifyContent:"space-between" }}>
                <span>×{p.quantity} @ ${p.avg.toFixed(2)}</span>
                <span className={p.pl >= 0 ? "pos" : "neg"}>{p.pl >= 0 ? "+" : "−"}${Math.abs(p.pl).toFixed(2)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* DECISION LOG + DETAIL */}
      <div className="row" style={{ gridTemplateColumns:"1.45fr 1fr" }}>
        <div className="card">
          <div className="card-head">
            <h3>Decision log</h3>
            <div className="tabs" style={{ marginLeft: 10 }}>
              {["all","buy","sell","hold"].map(k => (
                <span key={k} className={`tab ${filter===k?"active":""}`} onClick={()=>setFilter(k)}>{k}</span>
              ))}
            </div>
            <div style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:6, padding:"4px 8px", border:"1px solid var(--border-soft)", borderRadius:"var(--radius-sm)", background:"var(--bg-elev)" }}>
              <I.Search style={{ width:12, height:12, color:"var(--text-dim)" }}/>
              <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Filter symbol…"
                     style={{ background:"transparent", border:"none", outline:"none", fontFamily:"var(--mono)", fontSize:11, width:100, color:"var(--text)" }}/>
            </div>
          </div>
          <table className="t">
            <thead>
              <tr>
                <th>Time</th>
                <th>Symbol</th>
                <th>Decision</th>
                <th className="r">Conf.</th>
                <th className="r">Qty</th>
                <th className="r">Price</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredDec.map(d => (
                <tr key={d.id} className="row-hover" onClick={()=>setSelectedId(d.id)}
                    style={{ background: d.id === selectedId ? "var(--surface-hi)" : undefined, cursor:"pointer" }}>
                  <td className="mono dim">{d.at}</td>
                  <td className="mono"><b>{d.symbol}</b></td>
                  <td><span className={`dpill ${d.action.toLowerCase()}`}>{d.action}</span></td>
                  <td className="r mono">
                    <div style={{ display:"flex", alignItems:"center", gap:6, justifyContent:"flex-end" }}>
                      <div className="bar-track" style={{ width: 48 }}>
                        <div className="bar-fill" style={{
                          width: `${d.confidence * 100}%`,
                          background: d.confidence >= 0.7 ? "var(--pos)" : d.confidence >= 0.55 ? "var(--accent)" : "var(--neg)"
                        }}/>
                      </div>
                      <span>{(d.confidence*100).toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="r mono">{d.qty || "—"}</td>
                  <td className="r mono">${d.price.toFixed(2)}</td>
                  <td><span className={`chip ${d.status === "filled" ? "pos" : d.status === "blocked" ? "neg" : ""}`}>{d.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="detail-rail">
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <span className={`dpill ${selected.action.toLowerCase()}`} style={{ fontSize:11, padding:"4px 10px" }}>{selected.action}</span>
            <div>
              <div style={{ fontFamily:"var(--display)", fontSize:18, fontWeight:500 }}>{selected.symbol} <span className="dim mono" style={{ fontSize:11, marginLeft:4 }}>{selected.id}</span></div>
              <div className="mono dim" style={{ fontSize:11 }}>at {selected.at} · llama2</div>
            </div>
            <span className={`chip ${selected.status === "filled" ? "pos" : selected.status === "blocked" ? "neg" : ""}`} style={{ marginLeft:"auto" }}>{selected.status}</span>
          </div>

          <div className="divider"/>

          <div>
            <div className="mono dim" style={{ fontSize:10, letterSpacing:"0.1em", textTransform:"uppercase", marginBottom: 6 }}>Reasoning</div>
            <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.55 }}>{selected.reason}</div>
          </div>

          <div>
            <div className="mono dim" style={{ fontSize:10, letterSpacing:"0.1em", textTransform:"uppercase", marginBottom: 6 }}>Model confidence</div>
            <div style={{ display:"flex", alignItems:"center", gap: 10 }}>
              <div className="bar-track" style={{ flex: 1 }}>
                <div className="bar-fill" style={{
                  width: `${selected.confidence * 100}%`,
                  background: selected.confidence >= 0.7 ? "var(--pos)" : selected.confidence >= 0.55 ? "var(--accent)" : "var(--neg)"
                }}/>
              </div>
              <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>{(selected.confidence*100).toFixed(0)}%</span>
            </div>
          </div>

          <div>
            <div className="mono dim" style={{ fontSize:10, letterSpacing:"0.1em", textTransform:"uppercase", marginBottom: 6 }}>Market context</div>
            <div className="terminal">
{JSON.stringify(selected.context, null, 2)}
            </div>
          </div>

          <div className="divider"/>

          <div style={{ display:"flex", gap: 8 }}>
            <button className="btn"><I.Refresh className="ico"/>Re-run</button>
            <button className="btn">View order</button>
            <button className="btn ghost" style={{ marginLeft:"auto" }}>Export JSON</button>
          </div>
        </div>
      </div>

      {/* OPEN ORDERS */}
      <div className="card">
        <div className="card-head">
          <h3>Orders</h3>
          <span className="meta">{D.orders.filter(o => o.status === "WORKING").length} working · {D.orders.filter(o => o.status === "FILLED").length} filled today</span>
        </div>
        <table className="t">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Placed</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Type</th>
              <th className="r">Qty</th>
              <th className="r">Price</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {D.orders.map(o => (
              <tr key={o.id} className="row-hover">
                <td className="mono dim">{o.id}</td>
                <td className="mono dim">{o.placed}</td>
                <td className="mono"><b>{o.symbol}</b></td>
                <td><span className={`dpill ${o.side.toLowerCase()}`}>{o.side}</span></td>
                <td className="mono dim">{o.type}</td>
                <td className="r mono">{o.qty}</td>
                <td className="r mono">${o.price.toFixed(2)}</td>
                <td><span className={`chip ${o.status === "WORKING" ? "info" : "pos"}`}>{o.status}</span></td>
                <td className="r">{o.status === "WORKING" && <button className="btn ghost" style={{ padding:"4px 8px", fontSize:11 }}>cancel</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

window.TradesPage = TradesPage;
