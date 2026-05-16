/* AI Engine setup page */
const { useState: useStateAI, useEffect: useEffectAI } = React;

const AiEnginePage = () => {
  const D = window.BotData;

  const [models, setModels]         = useStateAI([]);
  const [ollamaOk, setOllamaOk]     = useStateAI(null); // null=loading, true/false
  const [model, setModel]           = useStateAI(D.model || "");
  const [temperature, setTemperature] = useStateAI(D.temperature ?? 0.2);
  const [maxTokens, setMaxTokens]   = useStateAI(D.max_tokens ?? 256);
  const [saving, setSaving]         = useStateAI(false);
  const [saved, setSaved]           = useStateAI(false);
  const [err, setErr]               = useStateAI("");

  useEffectAI(() => {
    fetch("/api/ollama/models")
      .then(r => r.json())
      .then(d => {
        setOllamaOk(d.ok);
        setModels(d.models || []);
        if (d.ok && !model && d.models.length > 0) setModel(d.models[0]);
      })
      .catch(() => setOllamaOk(false));
  }, []);

  // Sync from live data refresh
  useEffectAI(() => {
    const h = () => {
      const D2 = window.BotData;
      setModel(m => m || D2.model || "");
      setTemperature(D2.temperature ?? 0.2);
      setMaxTokens(D2.max_tokens ?? 256);
    };
    window.addEventListener("botdatarefreshed", h);
    return () => window.removeEventListener("botdatarefreshed", h);
  }, []);

  const save = async () => {
    setSaving(true); setErr(""); setSaved(false);
    try {
      const r = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          OLLAMA_MODEL: model,
          OLLAMA_TEMPERATURE: String(temperature),
          OLLAMA_MAX_TOKENS: String(maxTokens),
        }),
      });
      const d = await r.json();
      if (d.ok) { setSaved(true); setTimeout(() => setSaved(false), 3000); }
      else setErr(d.error || "Save failed");
    } catch (e) { setErr(String(e)); }
    setSaving(false);
  };

  const statusColor = ollamaOk === null ? "var(--text-dim)" : ollamaOk ? "var(--pos)" : "var(--neg)";
  const statusLabel = ollamaOk === null ? "checking…" : ollamaOk ? "connected" : "unreachable";

  return (
    <div className="setup-page">
      <div className="setup-header">
        <div>
          <h2 className="setup-title">AI Engine</h2>
          <p className="setup-sub">Configure the local Ollama LLM used for trade decisions.</p>
        </div>
        <div className="setup-status-badge" style={{ color: statusColor, borderColor: statusColor }}>
          <span className="dot" style={{ background: statusColor, animation: ollamaOk ? undefined : "none" }}/>
          Ollama {statusLabel}
        </div>
      </div>

      <div className="setup-grid">
        {/* Model picker */}
        <div className="setup-card">
          <div className="setup-card-label">Model</div>
          <p className="setup-card-desc">
            The Ollama model that analyses market context and makes BUY / SELL / HOLD decisions.
            Run <code>ollama pull &lt;name&gt;</code> to add more.
          </p>
          {ollamaOk === false && (
            <div className="setup-warn">
              Ollama is not running. Start it with <code>ollama serve</code> then refresh.
            </div>
          )}
          <div className="setup-field">
            <label>Active model</label>
            {models.length > 0 ? (
              <select className="setup-select" value={model} onChange={e => setModel(e.target.value)}>
                {models.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            ) : (
              <input
                className="setup-input"
                value={model}
                onChange={e => setModel(e.target.value)}
                placeholder="e.g. llama3.2:latest"
              />
            )}
          </div>
          <div className="setup-field">
            <label>Current in .env</label>
            <div className="setup-readonly">{D.model || "—"}</div>
          </div>
        </div>

        {/* Sampling */}
        <div className="setup-card">
          <div className="setup-card-label">Sampling</div>
          <p className="setup-card-desc">
            Controls how deterministic or creative the model's responses are.
            Lower temperature = more consistent decisions.
          </p>
          <div className="setup-field">
            <label>Temperature — <b>{temperature}</b></label>
            <div className="setup-slider-row">
              <span>0.0</span>
              <input
                type="range" min="0" max="1" step="0.05"
                value={temperature}
                onChange={e => setTemperature(parseFloat(e.target.value))}
                className="setup-slider"
              />
              <span>1.0</span>
            </div>
            <div className="setup-hint">
              {temperature <= 0.2 ? "Very deterministic — good for consistent risk management."
                : temperature <= 0.5 ? "Balanced — slight variability in outputs."
                : "High variance — decisions may be unpredictable."}
            </div>
          </div>
          <div className="setup-field">
            <label>Max tokens — <b>{maxTokens}</b></label>
            <div className="setup-slider-row">
              <span>64</span>
              <input
                type="range" min="64" max="1024" step="32"
                value={maxTokens}
                onChange={e => setMaxTokens(parseInt(e.target.value))}
                className="setup-slider"
              />
              <span>1024</span>
            </div>
            <div className="setup-hint">
              Longer outputs give more reasoning but cost more inference time.
            </div>
          </div>
        </div>

        {/* Preview */}
        <div className="setup-card setup-card-wide">
          <div className="setup-card-label">Prompt preview</div>
          <p className="setup-card-desc">
            A simplified view of what the bot sends to the model for each symbol.
          </p>
          <pre className="setup-pre">{`[System] You are a trading assistant. Respond with valid JSON only.

[User] Analyse AAPL:
- RSI 14: 52.3  |  MACD signal: bullish
- 20d price change: +4.1%
- Current price: $211.45  |  Portfolio value: $12,450

Respond:
{"action":"BUY|SELL|HOLD","confidence":0-1,"reason":"...","quantity":N}

Model: ${model || D.model || "llama3.2:latest"}  |  temperature: ${temperature}  |  max_tokens: ${maxTokens}`}
          </pre>
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
