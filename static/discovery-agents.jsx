/* Discovery Agents — live view of the 4-agent stock-finding swarm.
   Polls /api/agents/{state,activity,explore} every 3s. */
const {
  useState: useStateD,
  useEffect: useEffectD,
  useRef: useRefD,
} = React;

const AGENT_META = {
  "Scout":        { icon: "🛰️", color: "var(--info)"   },
  "Analyst":      { icon: "📊", color: "var(--accent)" },
  "Risk Officer": { icon: "🛡️", color: "var(--warn)"   },
  "Curator":      { icon: "🎯", color: "var(--pos)"    },
};

const ACTION_COLOR = {
  add: "var(--pos)", approve: "var(--pos)", scan: "var(--info)",
  grade: "var(--accent)", judge: "var(--accent)",
  evict: "var(--warn)", reject: "var(--neg)",
};

const hhmmss = (iso) => {
  if (!iso) return "—";
  const s = String(iso);
  return s.length >= 19 ? s.slice(11, 19) : s;
};

/* ── one agent card ── */
const AgentCard = ({ a }) => {
  const m = AGENT_META[a.agent] || { icon: "🤖", color: "var(--text-dim)" };
  const working = a.status === "working";
  return (
    <div className="card" style={{
      padding: "14px 16px", display: "flex", flexDirection: "column", gap: 8,
      border: working ? `1px solid ${m.color}` : "1px solid var(--border-soft)",
      transition: "border-color 0.2s",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 22, lineHeight: 1 }}>{m.icon}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: "var(--display)", fontWeight: 600, fontSize: 14 }}>{a.agent}</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--text-dim)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {a.role}
          </div>
        </div>
        <span style={{
          display: "inline-flex", alignItems: "center", gap: 5,
          fontFamily: "var(--mono)", fontSize: 10, color: working ? m.color : "var(--text-dim)",
          padding: "2px 8px", borderRadius: 999,
          border: `1px solid ${working ? m.color : "var(--border)"}`,
          animation: working ? "pulse-opacity 1.4s ease-in-out infinite" : "none",
        }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: working ? m.color : "var(--text-dim)", display: "inline-block" }}/>
          {working ? "WORKING" : "IDLE"}
        </span>
      </div>

      <div style={{ fontSize: 11.5, color: "var(--text)", fontFamily: "var(--mono)", lineHeight: 1.5 }}>
        {a.current_task || "—"}
      </div>
      {a.last_action && (
        <div style={{ fontSize: 10.5, color: "var(--text-mute)", fontFamily: "var(--mono)" }}>
          last: {a.last_action}
        </div>
      )}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text-dim)", fontFamily: "var(--mono)", marginTop: 2 }}>
        <span>processed {a.processed || 0}</span>
        <span>{a.updated ? "@ " + hhmmss(a.updated) + " UTC" : ""}</span>
      </div>
    </div>
  );
};

/* ── controller review list column ── */
const CtrlList = ({ title, items, color }) => (
  <div>
    <div style={{ fontSize: 11, fontWeight: 600, color: color || "var(--text)", marginBottom: 6 }}>{title}</div>
    {(items && items.length)
      ? <ul style={{ margin: 0, paddingLeft: 16, display: "flex", flexDirection: "column", gap: 5 }}>
          {items.map((it, i) => <li key={i} style={{ fontSize: 11.5, lineHeight: 1.5, color: "var(--text-mute)" }}>{it}</li>)}
        </ul>
      : <div style={{ fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--mono)" }}>—</div>}
  </div>
);

/* ── main page ── */
const DiscoveryAgentsPage = () => {
  const [states, setStates]   = useStateD([]);
  const [activity, setActivity] = useStateD([]);
  const [explore, setExplore] = useStateD({ explore: [], core_count: 0, explore_count: 0, explore_slots: 50, slots_free: 50, total: 0 });
  const [controller, setController] = useStateD(null);
  const pollRef = useRefD(null);

  const fetchAll = async () => {
    try {
      const [s, act, ex, ctrl] = await Promise.all([
        fetch("/api/agents/state").then(r => r.json()).catch(() => []),
        fetch("/api/agents/activity?limit=80").then(r => r.json()).catch(() => []),
        fetch("/api/agents/explore").then(r => r.json()).catch(() => ({})),
        fetch("/api/controller/report").then(r => r.json()).catch(() => null),
      ]);
      if (Array.isArray(s)) setStates(s);
      if (Array.isArray(act)) setActivity(act);
      if (ex && typeof ex === "object") setExplore(ex);
      if (ctrl && typeof ctrl === "object") setController(ctrl);
    } catch (e) { /* ignore */ }
  };

  useEffectD(() => {
    fetchAll();
    pollRef.current = setInterval(fetchAll, 3000);
    return () => clearInterval(pollRef.current);
  }, []);

  const anyWorking = states.some(a => a.status === "working");

  return (
    <div className="page">
      {/* header */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h2 style={{ fontFamily: "var(--display)", fontSize: 16, fontWeight: 600, margin: 0 }}>Discovery Agents</h2>
          <div className="mono dim" style={{ fontSize: 11, marginTop: 2 }}>
            {explore.core_count} core · {explore.explore_count}/{explore.explore_slots} explore · {explore.total} tracked
          </div>
        </div>
        <span className="chip" style={{ marginLeft: "auto" }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", display: "inline-block", marginRight: 5,
            background: anyWorking ? "var(--accent)" : "var(--pos)" }}/>
          {anyWorking ? "swarm running" : "swarm idle"}
        </span>
      </div>

      {/* agent cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
        {states.map(a => <AgentCard key={a.agent} a={a}/>)}
      </div>

      {/* night-shift controller review */}
      <div className="card">
        <div className="card-head">
          <h3>🌙 Night-shift Controller</h3>
          {controller && controller.model && <span className="chip">{controller.model}</span>}
          <span className="meta">
            {controller && controller.generated
              ? "reviewed " + controller.generated.slice(0, 16).replace("T", " ")
              : "runs after market close"}
          </span>
        </div>
        <div className="card-body">
          {(!controller || (!controller.summary && !(controller.feature_ideas||[]).length))
            ? <div style={{ padding: "18px 4px", color: "var(--text-dim)", fontFamily: "var(--mono)", fontSize: 12 }}>
                No review filed yet — the controller studies the day's data each night and proposes improvements here.
              </div>
            : <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {controller.summary && (
                  <div style={{ fontSize: 12.5, lineHeight: 1.6, color: "var(--text)" }}>{controller.summary}</div>
                )}
                <div className="row row-3">
                  <CtrlList title="💡 Feature ideas" items={controller.feature_ideas} color="var(--info)"/>
                  <CtrlList title="🔧 Improvements" items={controller.improvements} color="var(--accent)"/>
                  <CtrlList title="📈 Strategy notes" items={controller.strategy_notes} color="var(--pos)"/>
                </div>
                {(controller.param_proposals || []).length > 0 && (
                  <div>
                    <div style={{ fontSize: 10, color: "var(--text-dim)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 6 }}>
                      Parameter proposals {controller.auto_apply_enabled ? "(auto-apply ON)" : "(advisory)"}
                    </div>
                    <table className="t" style={{ fontSize: 11 }}>
                      <thead><tr><th>param</th><th className="r">current</th><th className="r">proposed</th><th>why</th></tr></thead>
                      <tbody>
                        {controller.param_proposals.map((p, i) => (
                          <tr key={i}>
                            <td className="mono">{p.key}</td>
                            <td className="r mono">{String(p.current)}</td>
                            <td className="r mono" style={{ color: p.changed ? "var(--accent)" : "var(--text-dim)" }}>{String(p.proposed)}</td>
                            <td style={{ color: "var(--text-mute)" }}>{p.rationale}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
          }
        </div>
      </div>

      {/* activity + explore */}
      <div className="row row-2">
        {/* activity timeline */}
        <div className="card">
          <div className="card-head">
            <h3>Agent activity</h3>
            <span className="chip"><span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--pos)", display: "inline-block", marginRight: 4 }}/>live</span>
            <span className="meta">{activity.length} events</span>
          </div>
          <div className="card-body">
            {activity.length === 0
              ? <div style={{ padding: "24px 16px", textAlign: "center", color: "var(--text-dim)", fontFamily: "var(--mono)", fontSize: 12 }}>
                  No agent activity yet — runs on the next discovery scan.
                </div>
              : <div className="feed" style={{ maxHeight: 420, overflowY: "auto" }}>
                  {activity.map((e, i) => {
                    const col = ACTION_COLOR[e.action] || "var(--text-dim)";
                    return (
                      <div className="feed-item" key={i} style={{ alignItems: "flex-start" }}>
                        <div className="feed-time" style={{ whiteSpace: "nowrap" }}>{hhmmss(e.ts)}</div>
                        <div className="feed-msg" style={{ fontSize: 11.5 }}>
                          <b style={{ color: (AGENT_META[e.agent] || {}).color || "var(--text)" }}>{e.agent}</b>
                          {" "}
                          <span style={{ color: col, fontFamily: "var(--mono)", fontSize: 10, textTransform: "uppercase" }}>{e.action}</span>
                          {e.symbols ? <span style={{ color: "var(--text)", fontFamily: "var(--mono)" }}> {e.symbols}</span> : null}
                          {e.reason ? <div style={{ color: "var(--text-mute)", fontSize: 10.5, marginTop: 2 }}>{e.reason}</div> : null}
                        </div>
                        {e.cycle != null && <span className="chip" style={{ fontSize: 9 }}>#{e.cycle}</span>}
                      </div>
                    );
                  })}
                </div>
            }
          </div>
        </div>

        {/* explore board */}
        <div className="card">
          <div className="card-head">
            <h3>Explore slots</h3>
            <span className="meta">{explore.explore_count}/{explore.explore_slots} used · {explore.slots_free} free</span>
          </div>
          <div className="card-body">
            {(!explore.explore || explore.explore.length === 0)
              ? <div style={{ padding: "24px 16px", textAlign: "center", color: "var(--text-dim)", fontFamily: "var(--mono)", fontSize: 12 }}>
                  No explore picks yet. The Curator fills these from the swarm's best finds.
                </div>
              : <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {explore.explore.map((e, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "flex-start", gap: 8,
                      padding: "8px 10px", borderRadius: 6,
                      background: "var(--bg)", border: "1px solid var(--border-soft)",
                    }}>
                      <span className="sym" style={{ fontWeight: 700, fontSize: 13, minWidth: 52 }}>{e.symbol}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 10.5, color: "var(--text-mute)", fontFamily: "var(--mono)", lineHeight: 1.45 }}>
                          {e.reason || "—"}
                        </div>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 3 }}>
                        {e.score != null && <span className="mono" style={{ fontSize: 11, color: "var(--accent)" }}>{Number(e.score).toFixed(0)}</span>}
                        {e.pinned && <span className="chip" style={{ fontSize: 8 }}>📌 pinned</span>}
                      </div>
                    </div>
                  ))}
                </div>
            }
          </div>
        </div>
      </div>
    </div>
  );
};

window.DiscoveryAgentsPage = DiscoveryAgentsPage;
