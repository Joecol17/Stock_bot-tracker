/* Risk & Config setup page */
const { useState: useStateRC, useEffect: useEffectRC } = React;

const RiskConfigPage = () => {
  const D = window.BotData;

  const [vals, setVals] = useStateRC({
    STOP_LOSS_PCT:            "3",
    TAKE_PROFIT_PCT:          "5",
    MAX_DAILY_TRADES:         String(D.max_daily_trades || 10),
    DEFAULT_TRADE_QUANTITY:   "1",
    MIN_ACCOUNT_VALUE:        String(D.min_account_value || 100),
    MAX_SYMBOLS_PER_CYCLE:    "5",
    DISCOVERY_INTERVAL_CYCLES: "6",
    DISCOVERY_TOP_N:          "10",
    MAX_WATCHLIST_SIZE:       "20",
  });
  const [saving, setSaving]   = useStateRC(false);
  const [saved, setSaved]     = useStateRC(false);
  const [err, setErr]         = useStateRC("");
  const [loaded, setLoaded]   = useStateRC(false);

  useEffectRC(() => {
    fetch("/api/config")
      .then(r => r.json())
      .then(d => {
        setVals(prev => ({
          ...prev,
          STOP_LOSS_PCT:            d.STOP_LOSS_PCT   ? String(parseFloat(d.STOP_LOSS_PCT)   * 100) : prev.STOP_LOSS_PCT,
          TAKE_PROFIT_PCT:          d.TAKE_PROFIT_PCT ? String(parseFloat(d.TAKE_PROFIT_PCT) * 100) : prev.TAKE_PROFIT_PCT,
          MAX_DAILY_TRADES:         d.MAX_DAILY_TRADES         || prev.MAX_DAILY_TRADES,
          DEFAULT_TRADE_QUANTITY:   d.DEFAULT_TRADE_QUANTITY   || prev.DEFAULT_TRADE_QUANTITY,
          MIN_ACCOUNT_VALUE:        d.MIN_ACCOUNT_VALUE        || prev.MIN_ACCOUNT_VALUE,
          MAX_SYMBOLS_PER_CYCLE:    d.MAX_SYMBOLS_PER_CYCLE    || prev.MAX_SYMBOLS_PER_CYCLE,
          DISCOVERY_INTERVAL_CYCLES: d.DISCOVERY_INTERVAL_CYCLES || prev.DISCOVERY_INTERVAL_CYCLES,
          DISCOVERY_TOP_N:          d.DISCOVERY_TOP_N          || prev.DISCOVERY_TOP_N,
          MAX_WATCHLIST_SIZE:       d.MAX_WATCHLIST_SIZE        || prev.MAX_WATCHLIST_SIZE,
        }));
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  const set = (key, value) => setVals(prev => ({ ...prev, [key]: value }));

  const save = async () => {
    setSaving(true); setErr(""); setSaved(false);
    // Convert percentage display back to decimal for STOP_LOSS_PCT / TAKE_PROFIT_PCT
    const payload = { ...vals };
    payload.STOP_LOSS_PCT   = String(parseFloat(vals.STOP_LOSS_PCT)   / 100 || 0.03);
    payload.TAKE_PROFIT_PCT = String(parseFloat(vals.TAKE_PROFIT_PCT) / 100 || 0.05);
    try {
      const r = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const d = await r.json();
      if (d.ok) { setSaved(true); setTimeout(() => setSaved(false), 3000); }
      else setErr(d.error || "Save failed");
    } catch (e) { setErr(String(e)); }
    setSaving(false);
  };

  const Field = ({ label, hint, children }) => (
    <div className="setup-field">
      <label>{label}</label>
      {children}
      {hint && <div className="setup-hint">{hint}</div>}
    </div>
  );

  const NumInput = ({ k, min, max, step = 1 }) => (
    <input
      className="setup-input setup-input-sm"
      type="number" min={min} max={max} step={step}
      value={vals[k]}
      onChange={e => set(k, e.target.value)}
    />
  );

  const SliderField = ({ k, label, min, max, step = 1, unit = "", hint }) => (
    <Field label={`${label} — ${vals[k]}${unit}`} hint={hint}>
      <div className="setup-slider-row">
        <span>{min}{unit}</span>
        <input
          type="range" className="setup-slider"
          min={min} max={max} step={step}
          value={vals[k]}
          onChange={e => set(k, e.target.value)}
        />
        <span>{max}{unit}</span>
      </div>
    </Field>
  );

  if (!loaded) return <div className="setup-page"><p style={{ color: "var(--text-dim)" }}>Loading config…</p></div>;

  return (
    <div className="setup-page">
      <div className="setup-header">
        <div>
          <h2 className="setup-title">Risk & Config</h2>
          <p className="setup-sub">Trade limits, stop-loss / take-profit, and discovery settings.</p>
        </div>
        <div className="setup-status-badge" style={{ color: "var(--info)", borderColor: "var(--info)" }}>
          <span className="dot" style={{ background: "var(--info)", animation: "none" }}/>
          Local config
        </div>
      </div>

      <div className="setup-grid">
        {/* Position risk */}
        <div className="setup-card">
          <div className="setup-card-label">Position risk</div>
          <p className="setup-card-desc">
            Automatic stop-loss and take-profit thresholds applied to every position.
          </p>
          <SliderField k="STOP_LOSS_PCT"   label="Stop loss"   min={0.5} max={20}  step={0.5} unit="%" hint="Exit position if price falls this % below entry." />
          <SliderField k="TAKE_PROFIT_PCT" label="Take profit" min={1}   max={50}  step={0.5} unit="%" hint="Exit position when this % profit is reached." />
        </div>

        {/* Trade limits */}
        <div className="setup-card">
          <div className="setup-card-label">Trade limits</div>
          <p className="setup-card-desc">
            Daily caps and minimum account guardrails to prevent over-trading.
          </p>
          <SliderField k="MAX_DAILY_TRADES" label="Max daily trades" min={1} max={50} step={1} hint="Bot won't place more than this many orders today." />
          <Field label="Min account value ($)" hint="Bot halts if total account value drops below this.">
            <NumInput k="MIN_ACCOUNT_VALUE" min={0} max={100000} step={10} />
          </Field>
          <Field label="Default trade quantity (shares)" hint="Number of shares placed per order when not overridden.">
            <NumInput k="DEFAULT_TRADE_QUANTITY" min={0.01} max={1000} step={0.01} />
          </Field>
        </div>

        {/* Screener & discovery */}
        <div className="setup-card">
          <div className="setup-card-label">Screener & discovery</div>
          <p className="setup-card-desc">
            Controls how many symbols are analysed each cycle and how often discovery adds new ones.
          </p>
          <SliderField k="MAX_SYMBOLS_PER_CYCLE" label="Symbols per cycle" min={1} max={20} step={1} hint="Symbols pulled from watchlist and sent to the AI each cycle." />
          <SliderField k="DISCOVERY_INTERVAL_CYCLES" label="Discovery every N cycles" min={1} max={20} step={1} hint="How often the screener searches for new watchlist candidates." />
          <SliderField k="DISCOVERY_TOP_N"    label="Discovery top-N" min={1} max={30} step={1} hint="Max new symbols added to watchlist per discovery run." />
          <SliderField k="MAX_WATCHLIST_SIZE" label="Max watchlist size" min={5} max={100} step={5} hint="Watchlist is pruned to this length after each discovery run." />
        </div>

        {/* Summary */}
        <div className="setup-card setup-card-wide">
          <div className="setup-card-label">Current limits summary</div>
          <div className="setup-summary-grid">
            {[
              ["Stop loss",           `${vals.STOP_LOSS_PCT}%`],
              ["Take profit",         `${vals.TAKE_PROFIT_PCT}%`],
              ["Max daily trades",    vals.MAX_DAILY_TRADES],
              ["Trade quantity",      vals.DEFAULT_TRADE_QUANTITY],
              ["Min account value",   `$${vals.MIN_ACCOUNT_VALUE}`],
              ["Symbols / cycle",     vals.MAX_SYMBOLS_PER_CYCLE],
              ["Discovery every",     `${vals.DISCOVERY_INTERVAL_CYCLES} cycles`],
              ["Discovery top-N",     vals.DISCOVERY_TOP_N],
              ["Max watchlist",       vals.MAX_WATCHLIST_SIZE],
            ].map(([l, v]) => (
              <div key={l} className="setup-summary-row">
                <span>{l}</span><b>{v}</b>
              </div>
            ))}
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

window.RiskConfigPage = RiskConfigPage;
