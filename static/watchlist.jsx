/* Watchlist Manager — view, add, remove, enable/disable + AI reasoning */
const {
  useState: useStateW,
  useEffect: useEffectW,
  useCallback: useCallbackW,
  useRef: useRefW,
} = React;

/* ── status metadata ─────────────────────────────────────── */
const STATUS_META = {
  queued:       { label: "Queued",       color: "var(--text-dim)",  icon: "○" },
  filtering:    { label: "Filtering…",   color: "var(--accent)",    icon: "⟳" },
  filtered_out: { label: "Filtered out", color: "var(--warn)",      icon: "✕" },
  thinking:     { label: "Ollama…",      color: "var(--accent)",    icon: "⌛" },
  hold:         { label: "HOLD",         color: "var(--text-dim)",  icon: "—" },
  traded:       { label: "TRADED",       color: "var(--pos)",       icon: "✓" },
  skipped:      { label: "Skipped",      color: "var(--warn)",      icon: "⤻" },
  error:        { label: "Error",        color: "var(--neg)",       icon: "!" },
  disabled:     { label: "Disabled",     color: "var(--text-mute)", icon: "⊘" },
  not_queued:   { label: "Not queued",   color: "var(--text-dim)",  icon: "·" },
};

const StatusBadge = ({ status, detail }) => {
  const m = STATUS_META[status] || { label: status, color: "var(--text-dim)", icon: "?" };
  const pulse = status === "thinking" || status === "filtering";
  return (
    <span title={detail || m.label} style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontSize: 10, fontFamily: "var(--mono)", color: m.color,
      padding: "2px 7px", borderRadius: 4,
      background: m.color.replace(")", " / .12)").replace("var(", "color-mix(in srgb,").replace(")", ",transparent 88%)") || m.color + "18",
      border: `1px solid ${m.color}44`,
      animation: pulse ? "pulse-opacity 1.4s ease-in-out infinite" : "none",
    }}>
      <span>{m.icon}</span>
      {m.label}
    </span>
  );
};

/* ── small helpers ─────────────────────────────────────── */
const ScoreBadge = ({ score, max = 4 }) => {
  const pct = Math.max(0, Math.min(score / max, 1));
  const col = pct >= 0.75 ? "var(--pos)" : pct >= 0.5 ? "var(--accent)" : "var(--neg)";
  return (
    <span style={{ display:"inline-flex", alignItems:"center", gap:4, fontSize:10, fontFamily:"var(--mono)", color:col }}>
      <span style={{ display:"inline-block", width:32, height:4, borderRadius:2, background:"var(--border-soft)", overflow:"hidden" }}>
        <span style={{ display:"block", height:"100%", width:`${pct*100}%`, background:col, borderRadius:2 }}/>
      </span>
      {score}/{max}
    </span>
  );
};

const Chip = ({ children, color }) => (
  <span style={{
    display:"inline-block", padding:"2px 7px", borderRadius:4,
    fontSize:10, fontFamily:"var(--mono)",
    background: (color || "var(--accent)") + "22",
    color: color || "var(--accent)",
    border:`1px solid ${color || "var(--accent)"}44`,
  }}>{children}</span>
);

/* ── toggle switch ─────────────────────────────────────── */
const Toggle = ({ value, onChange, disabled: dis }) => (
  <button
    onClick={() => !dis && onChange(!value)}
    title={value ? "Click to disable this symbol" : "Click to enable this symbol"}
    style={{
      position: "relative", width: 32, height: 18, borderRadius: 9,
      border: "none", cursor: dis ? "default" : "pointer",
      background: value ? "var(--pos)" : "var(--border-soft)",
      transition: "background 0.2s", flexShrink: 0, padding: 0,
    }}
  >
    <span style={{
      position:"absolute", top:2, left: value ? 16 : 2,
      width:14, height:14, borderRadius:"50%",
      background:"var(--text)", transition:"left 0.2s",
    }}/>
  </button>
);

/* ── single symbol card ─────────────────────────────────── */
const SymbolCard = ({ symbol, cycleStatus, enabled, onToggle, onRemove, onAnalyze, analysis, loading }) => {
  const [expanded, setExpanded] = useStateW(false);

  const a = analysis || {};
  const hasData = a.price != null;
  const priceColor = a.change_pct >= 0 ? "var(--pos)" : "var(--neg)";
  const regimeColor = a.regime === "bull" ? "var(--pos)" : a.regime === "bear" ? "var(--neg)" : "var(--warn)";

  const isActive = cycleStatus && !["not_queued", "disabled", undefined].includes(cycleStatus.status);

  return (
    <div className="card" style={{
      padding: "14px 16px", display:"flex", flexDirection:"column", gap:10,
      border: isActive ? "1px solid var(--accent)44" : "1px solid var(--border-soft)",
      opacity: enabled ? 1 : 0.55,
      transition: "border-color 0.2s, opacity 0.2s",
    }}>
      {/* ── header ── */}
      <div style={{ display:"flex", alignItems:"flex-start", gap:8 }}>
        {/* enable/disable toggle */}
        <div style={{ paddingTop:2 }}>
          <Toggle value={enabled} onChange={(v) => onToggle(symbol, v)}/>
        </div>

        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:2, flexWrap:"wrap" }}>
            <span className="sym" style={{ fontSize:15, fontWeight:700 }}>{symbol}</span>
            {hasData && (
              <span style={{ fontSize:11, color:priceColor, fontFamily:"var(--mono)" }}>
                ${a.price?.toFixed(2)}
                <span style={{ marginLeft:4 }}>{a.change_pct >= 0 ? "▲" : "▼"}{Math.abs(a.change_pct||0).toFixed(2)}%</span>
              </span>
            )}
            {a.regime && <Chip color={regimeColor}>{a.regime}</Chip>}
            {cycleStatus && <StatusBadge status={cycleStatus.status} detail={cycleStatus.detail}/>}
          </div>
          {a.name && <div style={{ fontSize:11, color:"var(--text-dim)", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{a.name}</div>}
        </div>

        <div style={{ display:"flex", gap:5, alignItems:"center", flexShrink:0 }}>
          <button className="btn ghost" style={{ fontSize:10, padding:"3px 10px" }}
            onClick={() => onAnalyze(symbol)} disabled={loading || !enabled} title="Get AI analysis">
            {loading ? "…" : "Analyse"}
          </button>
          <button className="btn ghost" style={{ fontSize:10, padding:"3px 8px", color:"var(--neg)", borderColor:"var(--neg)44" }}
            onClick={() => { if(window.confirm(`Remove ${symbol} from watchlist?`)) onRemove(symbol); }}
            title="Remove from watchlist">✕</button>
        </div>
      </div>

      {/* ── why: this cycle's reason (filter / hold / trade), shown inline ── */}
      {cycleStatus && cycleStatus.detail && (
        <div style={{
          fontSize:10.5, fontFamily:"var(--mono)", lineHeight:1.55,
          color:"var(--text-mute)", background:"var(--bg)",
          border:"1px solid var(--border-soft)", borderRadius:5, padding:"6px 9px",
        }}>
          <span style={{ color:(STATUS_META[cycleStatus.status]||{}).color || "var(--text-dim)" }}>
            {(STATUS_META[cycleStatus.status]||{}).icon || "·"} {(STATUS_META[cycleStatus.status]||{}).label || cycleStatus.status}
          </span>
          {" — "}{cycleStatus.detail}
        </div>
      )}

      {/* ── metrics row ── */}
      {hasData && (
        <div style={{ display:"flex", gap:14, flexWrap:"wrap" }}>
          {a.rsi != null && (
            <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
              <span style={{ fontSize:9, color:"var(--text-dim)", textTransform:"uppercase", letterSpacing:"0.08em" }}>RSI</span>
              <span style={{ fontSize:12, fontFamily:"var(--mono)", color: a.rsi > 70 ? "var(--neg)" : a.rsi < 30 ? "var(--pos)" : "var(--text)" }}>{a.rsi?.toFixed(1)}</span>
            </div>
          )}
          {a.filter_score != null && (
            <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
              <span style={{ fontSize:9, color:"var(--text-dim)", textTransform:"uppercase", letterSpacing:"0.08em" }}>Filters</span>
              <ScoreBadge score={a.filter_score} max={4}/>
            </div>
          )}
          {a.rs != null && (
            <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
              <span style={{ fontSize:9, color:"var(--text-dim)", textTransform:"uppercase", letterSpacing:"0.08em" }}>RS vs SPY</span>
              <span style={{ fontSize:12, fontFamily:"var(--mono)", color: a.rs >= 1 ? "var(--pos)" : "var(--neg)" }}>{a.rs?.toFixed(3)}</span>
            </div>
          )}
          {a.volume_m != null && (
            <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
              <span style={{ fontSize:9, color:"var(--text-dim)", textTransform:"uppercase", letterSpacing:"0.08em" }}>Volume</span>
              <span style={{ fontSize:12, fontFamily:"var(--mono)", color:"var(--text)" }}>{a.volume_m?.toFixed(1)}M</span>
            </div>
          )}
          {a.earnings_ok != null && (
            <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
              <span style={{ fontSize:9, color:"var(--text-dim)", textTransform:"uppercase", letterSpacing:"0.08em" }}>Earnings safe</span>
              <span style={{ fontSize:12, fontFamily:"var(--mono)", color: a.earnings_ok ? "var(--pos)" : "var(--neg)" }}>{a.earnings_ok ? "YES" : "NO"}</span>
            </div>
          )}
        </div>
      )}

      {/* ── AI reasoning (collapsible) ── */}
      {a.reasoning && (
        <div>
          <button className="btn ghost" style={{ fontSize:10, padding:"2px 8px", marginBottom:6, width:"100%", textAlign:"left" }}
            onClick={() => setExpanded(e => !e)}>
            <span style={{ marginRight:6 }}>{expanded ? "▲" : "▼"}</span>
            AI reasoning
            {a.action && (
              <span style={{
                marginLeft:8, padding:"1px 7px", borderRadius:4, fontWeight:700, fontSize:10,
                background: a.action==="BUY" ? "var(--pos)22" : a.action==="SELL" ? "var(--neg)22" : "var(--border-soft)",
                color: a.action==="BUY" ? "var(--pos)" : a.action==="SELL" ? "var(--neg)" : "var(--text-dim)",
              }}>{a.action}</span>
            )}
          </button>
          {expanded && (
            <div style={{
              background:"var(--bg)", border:"1px solid var(--border-soft)", borderRadius:6,
              padding:"10px 12px", fontSize:11, lineHeight:1.65, color:"var(--text)",
              fontFamily:"var(--mono)", whiteSpace:"pre-wrap", maxHeight:200, overflowY:"auto",
            }}>
              {a.reasoning}
            </div>
          )}
        </div>
      )}

      {/* ── loading / empty states ── */}
      {loading && !a.reasoning && (
        <div style={{ fontSize:11, color:"var(--accent)", fontFamily:"var(--mono)" }}>⌛ Asking AI…</div>
      )}
      {!loading && !a.reasoning && !hasData && enabled && (
        <div style={{ fontSize:11, color:"var(--text-dim)", fontFamily:"var(--mono)" }}>Click "Analyse" for AI reasoning</div>
      )}
      {!enabled && (
        <div style={{ fontSize:11, color:"var(--text-mute)", fontFamily:"var(--mono)" }}>Symbol disabled — bot will skip it</div>
      )}
    </div>
  );
};

/* ── add symbol form ── */
const AddSymbolForm = ({ onAdd, loading }) => {
  const [val, setVal] = useStateW("");
  const [err, setErr] = useStateW("");
  const submit = async (e) => {
    e.preventDefault();
    const sym = val.trim().toUpperCase();
    if (!sym) return;
    setErr("");
    const ok = await onAdd(sym);
    if (ok) setVal(""); else setErr(`Could not add ${sym}`);
  };
  return (
    <form onSubmit={submit} style={{ display:"flex", gap:8, alignItems:"center", flexWrap:"wrap" }}>
      <input className="input" style={{ width:120, fontFamily:"var(--mono)", textTransform:"uppercase", fontSize:13 }}
        placeholder="AAPL" value={val} onChange={e => setVal(e.target.value.toUpperCase())}
        maxLength={10} disabled={loading}/>
      <button className="btn primary" type="submit" disabled={!val.trim() || loading}>
        {loading ? "Adding…" : "+ Add symbol"}
      </button>
      {err && <span style={{ fontSize:11, color:"var(--neg)", fontFamily:"var(--mono)" }}>{err}</span>}
    </form>
  );
};

/* ── main page ── */
const WatchlistPage = () => {
  const [symbols,    setSymbols]    = useStateW([]);
  const [prefs,      setPrefs]      = useStateW({});   // { AAPL: {enabled:true}, ... }
  const [queue,      setQueue]      = useStateW({});   // { AAPL: {status,detail}, ... }
  const [analyses,   setAnalyses]   = useStateW({});
  const [loadingAll, setLoadingAll] = useStateW(false);
  const [loadingSym, setLoadingSym] = useStateW({});
  const [addLoading, setAddLoading] = useStateW(false);
  const [search,     setSearch]     = useStateW("");
  const [lastCycle,  setLastCycle]  = useStateW(null);
  const queuePollRef = useRefW(null);

  /* ── fetch watchlist ── */
  const fetchAll = useCallbackW(async () => {
    const [wlRes, prefsRes] = await Promise.all([
      fetch("/api/watchlist").then(r => r.json()).catch(() => []),
      fetch("/api/watchlist/prefs").then(r => r.json()).catch(() => ({})),
    ]);
    setSymbols(Array.isArray(wlRes) ? wlRes : (wlRes.symbols || []));
    setPrefs(prefsRes || {});
  }, []);

  /* ── poll symbol queue every 2s while bot is running ── */
  const fetchQueue = useCallbackW(async () => {
    try {
      const d = await fetch("/api/watchlist/queue").then(r => r.json());
      if (d.symbols) {
        setQueue(d.symbols);
        setLastCycle(d.cycle || null);
      }
    } catch(e) {}
  }, []);

  useEffectW(() => {
    fetchAll();
    fetchQueue();
    queuePollRef.current = setInterval(fetchQueue, 2000);
    return () => clearInterval(queuePollRef.current);
  }, []);

  /* ── enable / disable symbol ── */
  const toggleSymbol = useCallbackW(async (symbol, enabled) => {
    setPrefs(p => ({ ...p, [symbol]: { ...(p[symbol]||{}), enabled } }));
    try {
      await fetch("/api/watchlist/prefs", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ [symbol]: enabled }),
      });
    } catch(e) {}
  }, []);

  /* ── analyse one symbol ── */
  const analyseSymbol = useCallbackW(async (symbol) => {
    setLoadingSym(l => ({ ...l, [symbol]: true }));
    try {
      const r = await fetch("/api/watchlist/analyze", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ symbol }),
      });
      const d = await r.json();
      if (!d.error) setAnalyses(a => ({ ...a, [symbol]: d }));
    } catch(e) {}
    setLoadingSym(l => ({ ...l, [symbol]: false }));
  }, []);

  /* ── analyse all enabled symbols ── */
  const analyseAll = useCallbackW(async () => {
    setLoadingAll(true);
    const enabled = symbols.filter(s => prefs[s]?.enabled !== false);
    for (const sym of enabled) await analyseSymbol(sym);
    setLoadingAll(false);
  }, [symbols, prefs, analyseSymbol]);

  /* ── add symbol ── */
  const addSymbol = useCallbackW(async (symbol) => {
    setAddLoading(true);
    try {
      const r = await fetch("/api/watchlist/add", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ symbol }),
      });
      const d = await r.json();
      if (d.symbols) {
        setSymbols(d.symbols);
        analyseSymbol(symbol);
        setAddLoading(false);
        return true;
      }
    } catch(e) {}
    setAddLoading(false);
    return false;
  }, [analyseSymbol]);

  /* ── remove symbol ── */
  const removeSymbol = useCallbackW(async (symbol) => {
    try {
      const r = await fetch("/api/watchlist/remove", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ symbol }),
      });
      const d = await r.json();
      if (d.symbols) {
        setSymbols(d.symbols);
        setAnalyses(a => { const n={...a}; delete n[symbol]; return n; });
        setQueue(q => { const n={...q}; delete n[symbol]; return n; });
      }
    } catch(e) {}
  }, []);

  /* ── derived ── */
  const filtered = symbols.filter(s =>
    !search ||
    s.toLowerCase().includes(search.toLowerCase()) ||
    (analyses[s]?.name||"").toLowerCase().includes(search.toLowerCase())
  );

  const totalAnalysed = Object.keys(analyses).length;
  const bullish  = Object.values(analyses).filter(a => a.action === "BUY").length;
  const bearish  = Object.values(analyses).filter(a => a.action === "SELL").length;
  const disabled = symbols.filter(s => prefs[s]?.enabled === false).length;

  // Active symbols (currently being processed this cycle)
  const activeNow = Object.entries(queue)
    .filter(([,v]) => v.status === "thinking" || v.status === "filtering")
    .map(([k]) => k);

  return (
    <div className="page">
      {/* ── header ── */}
      <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:18, flexWrap:"wrap" }}>
        <div>
          <h2 style={{ fontFamily:"var(--display)", fontSize:16, fontWeight:600, margin:0 }}>Watchlist</h2>
          <div className="mono dim" style={{ fontSize:11, marginTop:2 }}>
            {symbols.length} symbols
            {disabled > 0 && ` · ${disabled} disabled`}
            {lastCycle != null && ` · cycle ${lastCycle}`}
            {activeNow.length > 0 && (
              <span style={{ color:"var(--accent)", marginLeft:6 }}>
                ⌛ {activeNow.join(", ")} running…
              </span>
            )}
          </div>
        </div>

        {totalAnalysed > 0 && (
          <div style={{ display:"flex", gap:6 }}>
            <Chip color="var(--pos)">▲ {bullish} BUY</Chip>
            <Chip color="var(--neg)">▼ {bearish} SELL</Chip>
            <Chip color="var(--text-dim)">○ {totalAnalysed - bullish - bearish} HOLD</Chip>
          </div>
        )}

        <div style={{ marginLeft:"auto", display:"flex", gap:8, alignItems:"center", flexWrap:"wrap" }}>
          <input className="input" style={{ width:130, fontSize:11, fontFamily:"var(--mono)" }}
            placeholder="Search…" value={search} onChange={e => setSearch(e.target.value)}/>
          <button className="btn ghost" onClick={analyseAll} disabled={loadingAll || symbols.length === 0}
            title="Run AI analysis on all enabled symbols">
            {loadingAll ? "Analysing…" : "Analyse all"}
          </button>
        </div>
      </div>

      {/* ── legend ── */}
      <div className="card" style={{ padding:"10px 14px", marginBottom:14, display:"flex", gap:14, flexWrap:"wrap", alignItems:"center" }}>
        <span style={{ fontSize:10, color:"var(--text-dim)", fontFamily:"var(--mono)", textTransform:"uppercase", letterSpacing:"0.08em" }}>Bot status this cycle:</span>
        {Object.entries(STATUS_META).map(([k, m]) => (
          <span key={k} style={{ display:"inline-flex", alignItems:"center", gap:4, fontSize:10, fontFamily:"var(--mono)", color:m.color }}>
            <span>{m.icon}</span>{m.label}
          </span>
        ))}
      </div>

      {/* ── add form ── */}
      <div className="card" style={{ padding:"14px 16px", marginBottom:16 }}>
        <div style={{ fontSize:11, color:"var(--text-dim)", marginBottom:8 }}>
          Add a stock ticker — the bot will start analysing it on the next cycle
        </div>
        <AddSymbolForm onAdd={addSymbol} loading={addLoading}/>
      </div>

      {/* ── grid ── */}
      {filtered.length === 0 && (
        <div className="card" style={{ padding:"40px 16px", textAlign:"center", color:"var(--text-dim)", fontFamily:"var(--mono)", fontSize:12 }}>
          {symbols.length === 0 ? "Watchlist is empty — add a symbol above" : "No symbols match your search"}
        </div>
      )}

      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(300px, 1fr))", gap:12 }}>
        {filtered.map(sym => (
          <SymbolCard
            key={sym}
            symbol={sym}
            cycleStatus={queue[sym]}
            enabled={prefs[sym]?.enabled !== false}
            onToggle={toggleSymbol}
            onRemove={removeSymbol}
            onAnalyze={analyseSymbol}
            analysis={analyses[sym]}
            loading={!!loadingSym[sym]}
          />
        ))}
      </div>
    </div>
  );
};

window.WatchlistPage = WatchlistPage;
