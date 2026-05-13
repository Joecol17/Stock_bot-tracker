/* Data Sources — interactive world map with live packet flow */
const { useState: useStateS, useEffect: useEffectS, useRef: useRefS, useMemo: useMemoS } = React;

// ─── Hook: rolling latency history per source ─────────────────────────────
const useLiveLatency = (sources) => {
  const [history, setHistory] = useStateS(() => {
    const h = {};
    sources.forEach(s => {
      // seed with 24 points jittered around baseline
      h[s.id] = Array.from({length: 24}, () => s.latency + (Math.random() - 0.5) * s.latency * 0.4);
    });
    return h;
  });
  useEffectS(() => {
    const t = setInterval(() => {
      setHistory(prev => {
        const next = {};
        sources.forEach(s => {
          const buf = prev[s.id] || [];
          const last = buf[buf.length - 1] ?? s.latency;
          // small drift, occasional spikes
          let v = last + (Math.random() - 0.5) * s.latency * 0.18;
          if (Math.random() < 0.05) v += s.latency * 0.6;
          v = Math.max(s.latency * 0.3, Math.min(s.latency * 2.2, v));
          next[s.id] = [...buf.slice(-23), v];
        });
        return next;
      });
    }, 900);
    return () => clearInterval(t);
  }, [sources]);
  return history;
};

// ─── World map (interactive) ──────────────────────────────────────────────
const WorldMap = ({ sources, selectedId, onSelect, hoverId, onHover }) => {
  // Anchor the central hub to the Localhost source so SVG and HTML pins agree.
  // SVG viewBox is 100×50, HTML overlay uses lat_px / lng_px as percentages of container,
  // so the SVG hub coords = lng_px and lat_px / 2.
  const allSources = window.BotData.sources;
  const hub = allSources.find(s => s.kind === "ai") || { lat_px: 50, lng_px: 50 };
  const HUB_X = hub.lng_px;          // viewBox x (0–100) — matches lng_px %
  const HUB_Y = hub.lat_px / 2;      // viewBox y (0–50)  — matches lat_px %

  return (
    <div className="world world-tall">
      <svg className="dotmap" viewBox="0 0 100 50" preserveAspectRatio="none">
        <defs>
          <pattern id="dots-water-v2" width="1.2" height="1.2" patternUnits="userSpaceOnUse">
            <circle cx="0.6" cy="0.6" r="0.18" fill="oklch(36% 0.018 250)"/>
          </pattern>
          <pattern id="dots-land-v2" width="1.2" height="1.2" patternUnits="userSpaceOnUse">
            <circle cx="0.6" cy="0.6" r="0.32" fill="oklch(62% 0.013 250)"/>
          </pattern>
          <radialGradient id="hub-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="var(--accent)" stopOpacity="0.5"/>
            <stop offset="60%" stopColor="var(--accent)" stopOpacity="0.08"/>
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0"/>
          </radialGradient>
          <radialGradient id="vignette2" cx="50%" cy="50%" r="65%">
            <stop offset="55%" stopColor="black" stopOpacity="0"/>
            <stop offset="100%" stopColor="black" stopOpacity="0.55"/>
          </radialGradient>
        </defs>

        {/* water */}
        <rect width="100" height="50" fill="url(#dots-water-v2)" opacity="0.55"/>

        {/* continents */}
        <g fill="url(#dots-land-v2)" opacity="0.95">
          {/* North America */}
          <ellipse cx="22" cy="15" rx="13" ry="6.5"/>
          <ellipse cx="16" cy="20" rx="6"  ry="4"/>
          <ellipse cx="27" cy="22" rx="4"  ry="3"/>
          <ellipse cx="25" cy="27" rx="2.5" ry="3"/>
          {/* South America */}
          <ellipse cx="31" cy="34" rx="5" ry="8"/>
          <ellipse cx="29" cy="41" rx="2.5" ry="3"/>
          {/* Europe */}
          <ellipse cx="50" cy="14" rx="6" ry="3.5"/>
          <ellipse cx="48" cy="19" rx="4" ry="2.5"/>
          {/* Africa */}
          <ellipse cx="53" cy="27" rx="6" ry="6"/>
          <ellipse cx="55" cy="33" rx="3.5" ry="4"/>
          {/* Asia */}
          <ellipse cx="68" cy="14" rx="13" ry="5"/>
          <ellipse cx="76" cy="19" rx="9" ry="4.5"/>
          <ellipse cx="62" cy="20" rx="4" ry="3"/>
          <ellipse cx="72" cy="23" rx="4" ry="3"/>
          <ellipse cx="80" cy="24" rx="3" ry="2.5"/>
          <ellipse cx="86" cy="20" rx="3" ry="2"/>
          {/* Australia */}
          <ellipse cx="83" cy="36" rx="6" ry="3"/>
          {/* Greenland / Iceland */}
          <ellipse cx="38" cy="9" rx="4" ry="3"/>
        </g>

        {/* hub glow (under everything) */}
        <circle cx={HUB_X} cy={HUB_Y} r="14" fill="url(#hub-glow)"/>

        {/* parallels (subtle) */}
        <g stroke="oklch(28% 0.018 250)" strokeWidth="0.08" fill="none">
          {[10, 20, 30, 40].map((y) => <line key={"h"+y} x1="0" y1={y} x2="100" y2={y}/>)}
          {[20, 40, 60, 80].map((x) => <line key={"v"+x} x1={x} y1="0" x2={x} y2="50"/>)}
        </g>

        {/* Connection arcs + flowing packets */}
        {sources.filter(s => s.kind !== "ai" && s.kind !== "config").map((s, i) => {
          const x1 = s.lng_px, y1 = s.lat_px / 2;
          const x2 = HUB_X,    y2 = HUB_Y;
          const cx = (x1 + x2) / 2;
          const cy = Math.min(y1, y2) - 5;
          const d  = `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
          const isHot = selectedId === s.id || hoverId === s.id;
          const color = s.status === "live" ? "oklch(72% 0.13 230)" : "oklch(68% 0.19 25)";
          const dur = (s.latency / 80 + 1.6).toFixed(2) + "s";
          return (
            <g key={s.id}>
              <path id={`arc-${s.id}`} d={d}
                    stroke={color}
                    strokeWidth={isHot ? 0.5 : 0.32}
                    strokeOpacity={isHot ? 0.85 : 0.5}
                    fill="none"
                    style={{ transition: "all 200ms ease" }}/>
              {/* moving packet */}
              <circle r={isHot ? 0.9 : 0.65} fill={color} opacity={s.status === "live" ? 1 : 0.4}>
                <animateMotion dur={dur} repeatCount="indefinite" rotate="auto" begin={`${i * 0.4}s`}>
                  <mpath href={`#arc-${s.id}`}/>
                </animateMotion>
              </circle>
              {isHot && (
                <circle r="0.5" fill="white" opacity="0.95">
                  <animateMotion dur={dur} repeatCount="indefinite" begin={`${i * 0.4 + 0.15}s`}>
                    <mpath href={`#arc-${s.id}`}/>
                  </animateMotion>
                </circle>
              )}
            </g>
          );
        })}

        {/* hub (Ollama local) */}
        <g>
          <circle cx={HUB_X} cy={HUB_Y} r="1.6" fill="var(--accent)" opacity="0.18"/>
          <circle cx={HUB_X} cy={HUB_Y} r="0.9" fill="var(--accent)"/>
          <circle cx={HUB_X} cy={HUB_Y} r="1.3" fill="none" stroke="var(--accent)" strokeWidth="0.14" opacity="0.7">
            <animate attributeName="r" values="1.3;3;1.3" dur="2.4s" repeatCount="indefinite"/>
            <animate attributeName="opacity" values="0.8;0;0.8" dur="2.4s" repeatCount="indefinite"/>
          </circle>
        </g>

        <rect width="100" height="50" fill="url(#vignette2)"/>
      </svg>

      {/* pins (HTML overlay) */}
      {sources.map((s) => {
        const isHub = s.kind === "ai" || s.kind === "config";
        const color = s.kind === "broker" ? "var(--info)" :
                      s.kind === "market" ? "var(--accent)" :
                      s.kind === "news"   ? "var(--warn)" :
                      s.kind === "ai"     ? "var(--pos)" :
                      "var(--text-mute)";
        const isHot = selectedId === s.id || hoverId === s.id;
        return (
          <div key={s.id}
               className={`pin ${s.status === "live" && !isHub ? "pulse" : ""} ${isHot ? "active" : ""}`}
               style={{ left: `${s.lng_px}%`, top: `${s.lat_px}%`, color, zIndex: isHot ? 5 : 2 }}
               onClick={() => onSelect(s.id)}
               onMouseEnter={() => onHover(s.id)}
               onMouseLeave={() => onHover(null)}>
            <div className="ring"/>
            <div className="label">
              {s.city}
              {isHot && <span className="label-meta"> · {s.latency}ms</span>}
            </div>
          </div>
        );
      })}

      {/* legend chip overlay */}
      <div className="map-overlay">
        <span className="mono dim" style={{ fontSize: 10, letterSpacing: "0.1em", textTransform:"uppercase" }}>Live · {sources.filter(s => s.status==="live").length}/{sources.length} sources</span>
        <span className="map-overlay-sep"/>
        <LegendDot color="var(--info)"   label="Broker"/>
        <LegendDot color="var(--accent)" label="Market"/>
        <LegendDot color="var(--warn)"   label="News"/>
        <LegendDot color="var(--pos)"    label="AI hub"/>
      </div>
    </div>
  );
};

// ─── Detail rail (right side) ─────────────────────────────────────────────
const SourceDetail = ({ source, history }) => {
  const buf = history[source.id] || [];
  const curLat = buf[buf.length - 1] || source.latency;
  const avgLat = buf.length ? buf.reduce((a, b) => a + b, 0) / buf.length : source.latency;
  const minLat = buf.length ? Math.min(...buf) : source.latency;
  const maxLat = buf.length ? Math.max(...buf) : source.latency;

  return (
    <div className="detail-rail">
      <div style={{ display:"flex", alignItems:"center", gap: 10 }}>
        <SourceIcon kind={source.kind} size={32}/>
        <div>
          <div className="mono dim" style={{ fontSize:10, textTransform:"uppercase", letterSpacing:"0.1em" }}>{source.kind} source</div>
          <div style={{ fontFamily:"var(--display)", fontSize:16, fontWeight:500 }}>{source.label}</div>
        </div>
        <span className={`chip ${source.status === "live" ? "pos" : source.status === "degraded" ? "warn" : "neg"}`} style={{ marginLeft:"auto" }}>{source.status}</span>
      </div>

      <div className="divider"/>

      {/* Big live latency module */}
      <div>
        <div style={{ display:"flex", alignItems:"baseline", gap: 10, marginBottom: 8 }}>
          <span className="mono dim" style={{ fontSize:10, letterSpacing:"0.1em", textTransform:"uppercase" }}>Latency · live</span>
          <span style={{ marginLeft:"auto", fontFamily:"var(--display)", fontSize:22, fontWeight:500, color: curLat < 100 ? "var(--pos)" : curLat < 250 ? "var(--warn)" : "var(--neg)" }}>
            {curLat.toFixed(0)}<span className="dim" style={{ fontSize: 12, marginLeft: 2 }}>ms</span>
          </span>
        </div>
        <div style={{ background:"var(--bg-elev)", border:"1px solid var(--border-soft)", borderRadius:"var(--radius-sm)", padding:"10px 12px 8px" }}>
          <Sparkline points={buf} color={curLat < 100 ? "var(--pos)" : curLat < 250 ? "var(--warn)" : "var(--neg)"} w={300} h={48} full/>
          <div style={{ display:"flex", justifyContent:"space-between", marginTop: 6, fontFamily:"var(--mono)", fontSize: 10, color:"var(--text-dim)" }}>
            <span>min {minLat.toFixed(0)}</span>
            <span>avg {avgLat.toFixed(0)}</span>
            <span>max {maxLat.toFixed(0)}</span>
          </div>
        </div>
      </div>

      {/* Throughput */}
      <div>
        <div style={{ display:"flex", alignItems:"baseline", marginBottom: 6 }}>
          <span className="mono dim" style={{ fontSize:10, letterSpacing:"0.1em", textTransform:"uppercase" }}>Throughput</span>
          <span className="mono" style={{ marginLeft:"auto", fontSize: 12 }}>{source.throughput}</span>
        </div>
        <div className="throughput-bar">
          <div className="throughput-fill" style={{ width: source.throughput === "—" ? "5%" : "78%" }}>
            <div className="throughput-stripe"/>
          </div>
        </div>
      </div>

      <div className="kv"><span className="k">Region</span><span className="v">{source.city === "Localhost" ? "127.0.0.1" : `${source.city}, ${source.country}`}</span></div>
      <div className="kv"><span className="k">Role</span><span className="v">{source.description}</span></div>

      <div>
        <div className="mono dim" style={{ fontSize:10, letterSpacing:"0.1em", textTransform:"uppercase", marginBottom: 6 }}>Last packet</div>
        <div className="terminal">
          <SamplePacket kind={source.kind}/>
        </div>
      </div>
    </div>
  );
};

const SamplePacket = ({ kind }) => {
  if (kind === "ai") return (
    <>
      <span className="k-key">$</span> ollama query llama2 --temperature 0.2 \{"\n"}
      {"   "}<span className="k-str">"You are a decision-making agent..."</span>{"\n"}{"\n"}
      <span className="k-key">→ response</span> in <span className="k-num">847ms</span>{"\n"}
      {"{"}{"\n"}
      {"  "}<span className="k-key">"action"</span>: <span className="k-str">"BUY"</span>,{"\n"}
      {"  "}<span className="k-key">"reasoning"</span>: <span className="k-str">"uptrend confirmed"</span>,{"\n"}
      {"  "}<span className="k-key">"confidence"</span>: <span className="k-num">0.78</span>{"\n"}
      {"}"}
    </>
  );
  if (kind === "broker") return (
    <>
      <span className="k-key">GET</span> /api/v0/equity/account{"\n"}
      <span className="k-key">200 OK</span> · 38ms{"\n"}
      {"{"}{"\n"}
      {"  "}<span className="k-key">"id"</span>: <span className="k-num">88412</span>,{"\n"}
      {"  "}<span className="k-key">"cash"</span>: <span className="k-num">4127.84</span>,{"\n"}
      {"  "}<span className="k-key">"currency"</span>: <span className="k-str">"USD"</span>,{"\n"}
      {"  "}<span className="k-key">"demo"</span>: <span className="k-num">true</span>{"\n"}
      {"}"}
    </>
  );
  if (kind === "market") return (
    <>
      <span className="k-key">subscribe</span> AAPL,GOOGL,MSFT{"\n"}
      <span className="k-key">tick</span> AAPL <span className="k-num">178.23</span> ×<span className="k-num">1.2k</span>{"\n"}
      <span className="k-key">tick</span> GOOGL <span className="k-num">142.50</span> ×<span className="k-num">340</span>{"\n"}
      <span className="k-key">tick</span> MSFT <span className="k-num">380.00</span> ×<span className="k-num">820</span>
    </>
  );
  if (kind === "news") return (
    <>
      <span className="k-key">headline</span>{"\n"}
      <span className="k-str">"Apple reports strong services growth"</span>{"\n"}
      <span className="k-key">source</span> Reuters · <span className="k-key">time</span> 10:42:11{"\n"}
      <span className="k-key">tickers</span> [AAPL]{"\n"}
      <span className="k-key">sentiment</span> <span className="k-num">+0.42</span>
    </>
  );
  return (
    <>
      <span className="k-key">DEFAULT_TRADE_QUANTITY</span> = <span className="k-num">1</span>{"\n"}
      <span className="k-key">MAX_DAILY_TRADES</span> = <span className="k-num">10</span>{"\n"}
      <span className="k-key">MIN_ACCOUNT_VALUE</span> = <span className="k-num">100</span>{"\n"}
      <span className="k-key">TRADING212_DEMO_MODE</span> = <span className="k-num">true</span>
    </>
  );
};

// ─── Page ─────────────────────────────────────────────────────────────────
const SourcesPage = () => {
  const D = window.BotData;
  const [selectedId, setSelectedId] = useStateS(D.sources[2].id);
  const [hoverId, setHoverId] = useStateS(null);
  const [filter, setFilter] = useStateS("all");

  const filtered = filter === "all" ? D.sources : D.sources.filter(s => s.kind === filter);
  const selected = D.sources.find(s => s.id === selectedId) || D.sources[0];
  const history = useLiveLatency(D.sources);

  // aggregate stats
  const liveCount = D.sources.filter(s => s.status === "live").length;
  const avgLatency = Math.round(D.sources.reduce((sum, s) => {
    const buf = history[s.id] || [];
    return sum + (buf[buf.length-1] || s.latency);
  }, 0) / D.sources.length);
  const totalThroughput = "2.4k events/min";

  return (
    <div className="page">
      {/* TOP STATS STRIP */}
      <div className="kpi-grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <MiniStat label="Sources live"      value={`${liveCount}/${D.sources.length}`}   sub="all regions reporting" tone="pos" icon={<I.Server/>}/>
        <MiniStat label="Avg latency"       value={`${avgLatency}`} unit="ms" sub="rolling 60s" tone={avgLatency < 150 ? "pos" : "warn"} icon={<I.Bolt/>}/>
        <MiniStat label="Throughput"        value="2.4k"  unit="events/min"   sub="across 8 endpoints" tone="info" icon={<I.Chart/>}/>
        <MiniStat label="AI engine"         value="6"     unit="ms"           sub="llama2 · local"     tone="accent" icon={<I.Cpu/>}/>
      </div>

      {/* MAP + DETAIL */}
      <div className="row" style={{ gridTemplateColumns: "1.55fr 1fr", alignItems: "stretch" }}>
        <div style={{ display:"flex", flexDirection:"column", gap: 10 }}>
          <div style={{ display:"flex", alignItems:"center", gap: 12 }}>
            <div className="tabs">
              {["all","broker","market","news","ai","config"].map(k => (
                <span key={k} className={`tab ${filter===k?"active":""}`} onClick={()=>setFilter(k)}>{k}</span>
              ))}
            </div>
            <span className="mono dim" style={{ marginLeft:"auto", fontSize:11 }}>
              showing {filtered.length} of {D.sources.length} sources
            </span>
          </div>
          <WorldMap
            sources={filtered}
            selectedId={selectedId}
            onSelect={setSelectedId}
            hoverId={hoverId}
            onHover={setHoverId}
          />
        </div>

        <SourceDetail source={selected} history={history}/>
      </div>

      {/* SOURCES TABLE */}
      <div className="card">
        <div className="card-head">
          <h3>All data sources</h3>
          <span className="meta">click any row to focus on the map</span>
        </div>
        <table className="t">
          <thead>
            <tr>
              <th>Source</th>
              <th>Kind</th>
              <th>Region</th>
              <th className="r">Latency · live</th>
              <th>Trend</th>
              <th className="r">Throughput</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {D.sources.map(s => {
              const buf = history[s.id] || [];
              const cur = buf[buf.length-1] || s.latency;
              return (
                <tr key={s.id} className="row-hover"
                    onClick={()=>setSelectedId(s.id)}
                    onMouseEnter={()=>setHoverId(s.id)}
                    onMouseLeave={()=>setHoverId(null)}
                    style={{ cursor:"pointer", background: s.id === selectedId ? "var(--surface-hi)" : undefined }}>
                  <td>
                    <div style={{ display:"flex", alignItems:"center", gap: 10 }}>
                      <SourceIcon kind={s.kind} size={22}/>
                      <div>
                        <div><b>{s.label}</b></div>
                        <div className="dim mono" style={{ fontSize:10, marginTop:2 }}>{s.description}</div>
                      </div>
                    </div>
                  </td>
                  <td><span className={`chip ${s.kind === "ai" ? "pos" : s.kind === "broker" ? "info" : s.kind === "market" ? "accent" : s.kind === "news" ? "warn" : ""}`}>{s.kind}</span></td>
                  <td className="mono">{s.city === "Localhost" ? "127.0.0.1" : `${s.city}, ${s.country}`}</td>
                  <td className="r mono" style={{ color: cur < 100 ? "var(--pos)" : cur < 250 ? "var(--warn)" : "var(--neg)" }}>{cur.toFixed(0)} ms</td>
                  <td style={{ width: 110 }}>
                    <Sparkline points={buf.slice(-12)} color={cur < 100 ? "var(--pos)" : cur < 250 ? "var(--warn)" : "var(--neg)"} w={100} h={20} area={false}/>
                  </td>
                  <td className="r mono">{s.throughput}</td>
                  <td><span className={`chip ${s.status === "live" ? "pos" : s.status === "degraded" ? "warn" : "neg"}`}>{s.status}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const MiniStat = ({ label, value, unit, sub, tone, icon }) => {
  const color = tone === "pos" ? "var(--pos)" : tone === "warn" ? "var(--warn)" : tone === "neg" ? "var(--neg)" : tone === "accent" ? "var(--accent)" : "var(--info)";
  return (
    <div className="kpi" style={{ paddingBottom: 14 }}>
      <span className="kpi-label">
        <span style={{ color, display:"inline-flex", alignItems:"center", marginRight: 4 }}>
          {React.cloneElement(icon, { style: { width: 12, height: 12 } })}
        </span>
        {label}
      </span>
      <span className="kpi-value mono">{value}{unit && <span className="unit">{unit}</span>}</span>
      <span className="kpi-foot" style={{ color }}>{sub}</span>
    </div>
  );
};

const LegendDot = ({ color, label }) => (
  <span style={{ display:"inline-flex", alignItems:"center", gap: 6, fontFamily:"var(--mono)", fontSize: 10, color:"var(--text-mute)" }}>
    <i style={{ width: 7, height: 7, borderRadius: "50%", background: color, boxShadow: `0 0 6px ${color}` }}/>
    {label}
  </span>
);

const SourceIcon = ({ kind, size = 24 }) => {
  const color = kind === "broker" ? "var(--info)" : kind === "market" ? "var(--accent)" : kind === "news" ? "var(--warn)" : kind === "ai" ? "var(--pos)" : "var(--text-mute)";
  return (
    <div style={{
      width: size, height: size, borderRadius: 6,
      background: `oklch(from ${color} l c h / .15)`,
      border: `1px solid ${color}`,
      display: "grid", placeItems: "center", color, flexShrink: 0
    }}>
      {kind === "broker" && <I.Server   style={{ width: size*0.55, height: size*0.55 }}/>}
      {kind === "market" && <I.Chart    style={{ width: size*0.55, height: size*0.55 }}/>}
      {kind === "news"   && <I.News     style={{ width: size*0.55, height: size*0.55 }}/>}
      {kind === "ai"     && <I.Cpu      style={{ width: size*0.55, height: size*0.55 }}/>}
      {kind === "config" && <I.Settings style={{ width: size*0.55, height: size*0.55 }}/>}
    </div>
  );
};

window.SourcesPage = SourcesPage;
