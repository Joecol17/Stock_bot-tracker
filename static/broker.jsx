/* Broker setup page */
const { useState: useStateBR, useEffect: useEffectBR } = React;

const BrokerPage = () => {
  const D = window.BotData;

  const [apiKey, setApiKey]     = useStateBR("");
  const [keySet, setKeySet]     = useStateBR(false);
  const [showKey, setShowKey]   = useStateBR(false);
  const [demoMode, setDemoMode] = useStateBR(D.mode === "DEMO");
  const [testing, setTesting]   = useStateBR(false);
  const [testResult, setTestResult] = useStateBR(null); // null | {ok, msg}
  const [saving, setSaving]     = useStateBR(false);
  const [saved, setSaved]       = useStateBR(false);
  const [err, setErr]           = useStateBR("");

  useEffectBR(() => {
    fetch("/api/config")
      .then(r => r.json())
      .then(d => {
        setKeySet(d.api_key_set || false);
        setDemoMode((d.TRADING212_DEMO_MODE || "true").toLowerCase() === "true");
      })
      .catch(() => {});
  }, []);

  useEffectBR(() => {
    const h = () => setDemoMode(window.BotData.mode === "DEMO");
    window.addEventListener("botdatarefreshed", h);
    return () => window.removeEventListener("botdatarefreshed", h);
  }, []);

  const testConnection = async () => {
    setTesting(true); setTestResult(null);
    try {
      const r = await fetch("/api/status");
      if (r.ok) {
        const d = await r.json();
        if (d.error) setTestResult({ ok: false, msg: d.error });
        else setTestResult({ ok: true, msg: `Connected — account ${d.account_id}, ${d.mode} mode` });
      } else {
        setTestResult({ ok: false, msg: `HTTP ${r.status}` });
      }
    } catch (e) { setTestResult({ ok: false, msg: String(e) }); }
    setTesting(false);
  };

  const save = async () => {
    setSaving(true); setErr(""); setSaved(false);
    const body = { TRADING212_DEMO_MODE: demoMode ? "true" : "false" };
    if (apiKey && apiKey !== "***") body.TRADING212_API_KEY = apiKey;
    try {
      const r = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const d = await r.json();
      if (d.ok) {
        setSaved(true); setTimeout(() => setSaved(false), 3000);
        if (apiKey && apiKey !== "***") { setKeySet(true); setApiKey(""); }
      } else setErr(d.error || "Save failed");
    } catch (e) { setErr(String(e)); }
    setSaving(false);
  };

  const isLive = !demoMode;

  return (
    <div className="setup-page">
      <div className="setup-header">
        <div>
          <h2 className="setup-title">Broker</h2>
          <p className="setup-sub">Connect your Trading 212 account and choose demo or live trading.</p>
        </div>
        <div className="setup-status-badge"
          style={{ color: isLive ? "var(--pos)" : "var(--warn)", borderColor: isLive ? "var(--pos)" : "var(--warn)" }}>
          <span className="dot" style={{ background: isLive ? "var(--pos)" : "var(--warn)" }}/>
          {isLive ? "LIVE" : "DEMO"} mode
        </div>
      </div>

      <div className="setup-grid">
        {/* API key */}
        <div className="setup-card">
          <div className="setup-card-label">API key</div>
          <p className="setup-card-desc">
            Your Trading 212 API key from <b>Settings → API</b> in the app.
            The key is stored in <code>.env</code> and never sent to any external service.
          </p>
          <div className="setup-field">
            <label>
              Key status:&nbsp;
              <span style={{ color: keySet ? "var(--pos)" : "var(--neg)" }}>
                {keySet ? "set" : "not set"}
              </span>
            </label>
            <div className="setup-input-row">
              <input
                className="setup-input"
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder={keySet ? "Enter new key to replace…" : "Paste API key here…"}
              />
              <button className="btn ghost" style={{ flexShrink: 0 }} onClick={() => setShowKey(v => !v)}>
                {showKey ? "Hide" : "Show"}
              </button>
            </div>
            <div className="setup-hint">Leave blank to keep existing key.</div>
          </div>
        </div>

        {/* Mode toggle */}
        <div className="setup-card">
          <div className="setup-card-label">Trading mode</div>
          <p className="setup-card-desc">
            Demo mode uses a virtual account with no real money. Switch to Live only when you're confident
            the bot is operating correctly.
          </p>
          <div className="setup-mode-toggle">
            <button
              className={`setup-mode-btn ${demoMode ? "active" : ""}`}
              style={demoMode ? { borderColor: "var(--warn)", color: "var(--warn)" } : {}}
              onClick={() => setDemoMode(true)}
            >
              Demo
              <span>Virtual account</span>
            </button>
            <button
              className={`setup-mode-btn ${!demoMode ? "active" : ""}`}
              style={!demoMode ? { borderColor: "var(--pos)", color: "var(--pos)" } : {}}
              onClick={() => setDemoMode(false)}
            >
              Live
              <span>Real money</span>
            </button>
          </div>
          {!demoMode && (
            <div className="setup-warn" style={{ borderColor: "var(--neg)", color: "var(--neg)" }}>
              Live mode places real orders with real money. Confirm bot risk settings before enabling.
            </div>
          )}
        </div>

        {/* Account stats */}
        <div className="setup-card">
          <div className="setup-card-label">Account</div>
          <p className="setup-card-desc">Live figures from the last API poll.</p>
          <div className="setup-stats-grid">
            <div className="setup-stat">
              <span className="setup-stat-label">Cash</span>
              <span className="setup-stat-val">${(D.cash || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>
            <div className="setup-stat">
              <span className="setup-stat-label">Total value</span>
              <span className="setup-stat-val">${(D.total_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>
            <div className="setup-stat">
              <span className="setup-stat-label">Free funds</span>
              <span className="setup-stat-val">${(D.free_funds || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            </div>
            <div className="setup-stat">
              <span className="setup-stat-label">Positions</span>
              <span className="setup-stat-val">{(D.positions || []).length}</span>
            </div>
          </div>
          <div style={{ marginTop: "12px" }}>
            <button className="btn ghost" onClick={testConnection} disabled={testing}>
              {testing ? "Testing…" : "Test connection"}
            </button>
            {testResult && (
              <div className="setup-hint" style={{ marginTop: "8px", color: testResult.ok ? "var(--pos)" : "var(--neg)" }}>
                {testResult.ok ? "✓" : "✗"} {testResult.msg}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="setup-footer">
        {err && <span className="setup-err">{err}</span>}
        {saved && <span className="setup-ok">Saved — restart bot to apply.</span>}
        <button className="btn primary" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>
    </div>
  );
};

window.BrokerPage = BrokerPage;
