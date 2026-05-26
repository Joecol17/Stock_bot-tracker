/* Live log tail — streams trading_bot.log via /api/logs (polled every 5 s) */
const { useState: useStateLog, useEffect: useEffectLog, useRef: useRefLog } = React;

const LEVEL_COLOR = (line) => {
  if (/- (ERROR|CRITICAL) -/.test(line))  return "var(--neg)";
  if (/- WARNING -/.test(line))            return "var(--warn)";
  if (/- INFO -/.test(line))              return "var(--text)";
  return "var(--text-dim)";
};

const LEVEL_TAG = (line) => {
  if (/- (ERROR|CRITICAL) -/.test(line))  return { label: "ERR",  cls: "neg" };
  if (/- WARNING -/.test(line))            return { label: "WARN", cls: "warn" };
  if (/- INFO -/.test(line))              return { label: "INFO", cls: "" };
  return { label: "LOG", cls: "" };
};

const LogsPage = () => {
  const [lines, setLines]           = useStateLog([]);
  const [loading, setLoading]       = useStateLog(true);
  const [error, setError]           = useStateLog(null);
  const [autoScroll, setAutoScroll] = useStateLog(true);
  const [filter, setFilter]         = useStateLog("all"); // all | err | warn | info
  const bottomRef                   = useRefLog(null);

  const fetchLogs = async () => {
    try {
      const res  = await fetch("/api/logs?lines=200");
      const data = await res.json();
      if (data.ok) {
        setLines(data.lines);
        setError(null);
      } else {
        setError(data.error || "Failed to load logs");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffectLog(() => {
    fetchLogs();
    const id = setInterval(fetchLogs, 5000);
    return () => clearInterval(id);
  }, []);

  useEffectLog(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [lines, autoScroll]);

  const filtered = lines.filter(line => {
    if (filter === "err")  return /- (ERROR|CRITICAL) -/.test(line);
    if (filter === "warn") return /- WARNING -/.test(line);
    if (filter === "info") return /- INFO -/.test(line);
    return true;
  });

  return (
    <div className="page">
      <div className="card" style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
        <div className="card-head" style={{ flexShrink: 0 }}>
          <h3>Live log</h3>
          <span className="mono dim" style={{ fontSize: 11, marginLeft: 6 }}>trading_bot.log · auto-refresh 5 s</span>

          {/* Level filter tabs */}
          <div className="tabs" style={{ marginLeft: 12 }}>
            {[["all","All"],["info","INFO"],["warn","WARN"],["err","ERR"]].map(([k, label]) => (
              <span key={k} className={`tab ${filter === k ? "active" : ""}`} onClick={() => setFilter(k)}>{label}</span>
            ))}
          </div>

          {/* Auto-scroll toggle */}
          <label style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer", userSelect: "none" }}>
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={e => setAutoScroll(e.target.checked)}
              style={{ accentColor: "var(--accent)" }}
            />
            Auto-scroll
          </label>

          <button className="btn ghost" onClick={fetchLogs} style={{ marginLeft: 8 }}>
            <I.Refresh className="ico"/>Refresh
          </button>
        </div>

        {/* Log body */}
        {loading ? (
          <div style={{ padding: "48px 16px", textAlign: "center", color: "var(--text-dim)", fontFamily: "var(--mono)", fontSize: 12 }}>
            Loading…
          </div>
        ) : error ? (
          <div style={{ padding: "48px 16px", textAlign: "center", color: "var(--neg)", fontFamily: "var(--mono)", fontSize: 12 }}>
            {error}
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: "48px 16px", textAlign: "center", color: "var(--text-dim)", fontFamily: "var(--mono)", fontSize: 12 }}>
            {lines.length === 0
              ? "Log file is empty — start the bot first (start_bot.bat)"
              : `No ${filter.toUpperCase()} lines in the last ${lines.length} entries`}
          </div>
        ) : (
          <div
            className="terminal"
            style={{
              flex: 1,
              overflowY: "auto",
              fontSize: 11,
              lineHeight: 1.65,
              padding: "12px 14px",
              borderRadius: "0 0 var(--radius) var(--radius)",
            }}
          >
            {filtered.map((line, i) => {
              const tag = LEVEL_TAG(line);
              // Split timestamp prefix (everything before " - LEVEL - ") for dimming
              const match = line.match(/^([\d\-,: ]+) - [A-Z]+ - (.*)$/);
              return (
                <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start", marginBottom: 1 }}>
                  <span className={`chip ${tag.cls}`} style={{ fontSize: 9, padding: "1px 5px", flexShrink: 0, marginTop: 1 }}>{tag.label}</span>
                  <span style={{ color: "var(--text-dim)", fontFamily: "var(--mono)", flexShrink: 0, fontSize: 10, marginTop: 2 }}>
                    {match ? match[1].trim() : ""}
                  </span>
                  <span style={{ color: LEVEL_COLOR(line), whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                    {match ? match[2] : line}
                  </span>
                </div>
              );
            })}
            <div ref={bottomRef}/>
          </div>
        )}
      </div>

      {/* Stats footer */}
      <div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--text-dim)", fontFamily: "var(--mono)", flexShrink: 0 }}>
        <span>{lines.length} lines loaded</span>
        <span>·</span>
        <span style={{ color: "var(--neg)" }}>{lines.filter(l => /- (ERROR|CRITICAL) -/.test(l)).length} errors</span>
        <span>·</span>
        <span style={{ color: "var(--warn)" }}>{lines.filter(l => /- WARNING -/.test(l)).length} warnings</span>
      </div>
    </div>
  );
};

window.LogsPage = LogsPage;
