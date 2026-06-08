/* Risk & Config setup page */
const { useState: useStateRC, useEffect: useEffectRC } = React;

const RiskConfigPage = () => {
  const D = window.BotData;

  const [vals, setVals] = useStateRC({
    // Position exits (fallback % stops — ATR/trailing manage exits primarily)
    STOP_LOSS_PCT:            "6",
    TAKE_PROFIT_PCT:          "12",
    // Account guardrails
    MIN_ACCOUNT_VALUE:        String(D.min_account_value || 100),
    DEFAULT_TRADE_QUANTITY:   "1",
    // Swing position sizing
    RISK_PER_TRADE_PCT:       String(((D.risk_per_trade_pct || 0.01) * 100)),
    ATR_STOP_MULTIPLIER:      String(D.atr_stop_multiplier || 1.5),
    MIN_RISK_REWARD:          String(D.min_risk_reward || 2),
    MAX_POSITION_PCT:         "10",
    MAX_HOLD_DAYS:            String(D.max_hold_days || 10),
    // Pre-trade filters
    MIN_FILTER_SCORE:         String(D.min_filter_score || 2),
    EARNINGS_BUFFER_DAYS:     String(D.earnings_buffer_days || 5),
    MIN_RELATIVE_STRENGTH:    "0.95",
    MARKET_REGIME_SYMBOL:     "SPY",
    REGIME_STRICT:            false,
    // Screener & discovery
    MAX_SYMBOLS_PER_CYCLE:    "5",
    DISCOVERY_INTERVAL_CYCLES: "7",
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
        const pct = (v, fallback) => (v !== "" && v != null ? String(parseFloat(v) * 100) : fallback);
        const num = (v, fallback) => (v !== "" && v != null ? String(v) : fallback);
        setVals(prev => ({
          ...prev,
          STOP_LOSS_PCT:            pct(d.STOP_LOSS_PCT,        prev.STOP_LOSS_PCT),
          TAKE_PROFIT_PCT:          pct(d.TAKE_PROFIT_PCT,      prev.TAKE_PROFIT_PCT),
          MIN_ACCOUNT_VALUE:        num(d.MIN_ACCOUNT_VALUE,    prev.MIN_ACCOUNT_VALUE),
          DEFAULT_TRADE_QUANTITY:   num(d.DEFAULT_TRADE_QUANTITY, prev.DEFAULT_TRADE_QUANTITY),
          RISK_PER_TRADE_PCT:       pct(d.RISK_PER_TRADE_PCT,   prev.RISK_PER_TRADE_PCT),
          ATR_STOP_MULTIPLIER:      num(d.ATR_STOP_MULTIPLIER,  prev.ATR_STOP_MULTIPLIER),
          MIN_RISK_REWARD:          num(d.MIN_RISK_REWARD,      prev.MIN_RISK_REWARD),
          MAX_POSITION_PCT:         pct(d.MAX_POSITION_PCT,     prev.MAX_POSITION_PCT),
          MAX_HOLD_DAYS:            num(d.MAX_HOLD_DAYS,         prev.MAX_HOLD_DAYS),
          MIN_FILTER_SCORE:         num(d.MIN_FILTER_SCORE,      prev.MIN_FILTER_SCORE),
          EARNINGS_BUFFER_DAYS:     num(d.EARNINGS_BUFFER_DAYS,  prev.EARNINGS_BUFFER_DAYS),
          MIN_RELATIVE_STRENGTH:    num(d.MIN_RELATIVE_STRENGTH, prev.MIN_RELATIVE_STRENGTH),
          MARKET_REGIME_SYMBOL:     (d.MARKET_REGIME_SYMBOL || prev.MARKET_REGIME_SYMBOL),
          REGIME_STRICT:            d.REGIME_STRICT != null && d.REGIME_STRICT !== ""
                                      ? String(d.REGIME_STRICT).toLowerCase() === "true"
                                      : prev.REGIME_STRICT,
          MAX_SYMBOLS_PER_CYCLE:    num(d.MAX_SYMBOLS_PER_CYCLE, prev.MAX_SYMBOLS_PER_CYCLE),
          DISCOVERY_INTERVAL_CYCLES: num(d.DISCOVERY_INTERVAL_CYCLES, prev.DISCOVERY_INTERVAL_CYCLES),
          DISCOVERY_TOP_N:          num(d.DISCOVERY_TOP_N,       prev.DISCOVERY_TOP_N),
          MAX_WATCHLIST_SIZE:       num(d.MAX_WATCHLIST_SIZE,    prev.MAX_WATCHLIST_SIZE),
        }));
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  const set = (key, value) => setVals(prev => ({ ...prev, [key]: value }));

  const save = async () => {
    setSaving(true); setErr(""); setSaved(false);
    const payload = { ...vals };
    // Convert percentage displays back to decimals for storage
    payload.STOP_LOSS_PCT      = String(parseFloat(vals.STOP_LOSS_PCT)      / 100 || 0.06);
    payload.TAKE_PROFIT_PCT    = String(parseFloat(vals.TAKE_PROFIT_PCT)    / 100 || 0.12);
    payload.RISK_PER_TRADE_PCT = String(parseFloat(vals.RISK_PER_TRADE_PCT) / 100 || 0.01);
    payload.MAX_POSITION_PCT   = String(parseFloat(vals.MAX_POSITION_PCT)   / 100 || 0.10);
    payload.REGIME_STRICT      = vals.REGIME_STRICT ? "true" : "false";
    payload.MARKET_REGIME_SYMBOL = String(vals.MARKET_REGIME_SYMBOL || "SPY").toUpperCase();
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

  const TextInput = ({ k, placeholder }) => (
    <input
      className="setup-input setup-input-sm"
      type="text" placeholder={placeholder}
      value={vals[k]}
      onChange={e => set(k, e.target.value.toUpperCase())}
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

  const ToggleField = ({ k, label, hint }) => (
    <Field label={label} hint={hint}>
      <button
        type="button"
        className={`btn ${vals[k] ? "primary" : "ghost"}`}
        style={{ width: "fit-content", padding: "5px 16px" }}
        onClick={() => set(k, !vals[k])}
      >
        {vals[k] ? "● Strict — block all buys in bear" : "○ Lenient — allow in bear"}
      </button>
    </Field>
  );

  if (!loaded) return <div className="setup-page"><p style={{ color: "var(--text-dim)" }}>Loading config…</p></div>;

  return (
    <div className="setup-page">
      <div className="setup-header">
        <div>
          <h2 className="setup-title">Risk & Config</h2>
          <p className="setup-sub">Position sizing, stops, pre-trade filters, and discovery settings for the swing system.</p>
        </div>
        <div className="setup-status-badge" style={{ color: "var(--info)", borderColor: "var(--info)" }}>
          <span className="dot" style={{ background: "var(--info)", animation: "none" }}/>
          Local config
        </div>
      </div>

      <div className="setup-grid">
        {/* Swing position sizing */}
        <div className="setup-card">
          <div className="setup-card-label">Position sizing</div>
          <p className="setup-card-desc">
            Risk-based sizing: each trade risks a fixed slice of the portfolio, with the
            stop placed a multiple of ATR below entry.
          </p>
          <SliderField k="RISK_PER_TRADE_PCT" label="Risk per trade" min={0.25} max={5} step={0.25} unit="%" hint="Portfolio % put at risk per position (distance from entry to stop)." />
          <SliderField k="ATR_STOP_MULTIPLIER" label="ATR stop multiplier" min={0.5} max={4} step={0.1} unit="×" hint="Stop loss sits this many ATRs below entry." />
          <SliderField k="MIN_RISK_REWARD" label="Min risk : reward" min={1} max={5} step={0.5} unit=":1" hint="Skip the trade unless the target is at least this many times the risk." />
          <SliderField k="MAX_POSITION_PCT" label="Max position size" min={2} max={50} step={1} unit="%" hint="A single position can never exceed this share of the portfolio." />
          <SliderField k="MAX_HOLD_DAYS" label="Max hold days" min={1} max={60} step={1} hint="Positions held longer than this are flagged for review." />
        </div>

        {/* Pre-trade filters */}
        <div className="setup-card">
          <div className="setup-card-label">Pre-trade filters</div>
          <p className="setup-card-desc">
            Quality gates a candidate must clear before the AI is asked to decide.
          </p>
          <SliderField k="MIN_FILTER_SCORE" label="Min filter score" min={0} max={4} step={1} unit="/4" hint="Minimum passing filters (trend, RS, volume, earnings) to proceed." />
          <SliderField k="EARNINGS_BUFFER_DAYS" label="Earnings buffer" min={0} max={21} step={1} unit="d" hint="Skip the symbol if earnings fall within this many days." />
          <SliderField k="MIN_RELATIVE_STRENGTH" label="Min relative strength" min={0.7} max={1.5} step={0.01} unit="×" hint="Strength vs the benchmark (1.0 = parity). Higher = only leaders." />
          <Field label="Regime benchmark" hint="Index used to read the market regime (bull / bear / neutral).">
            <TextInput k="MARKET_REGIME_SYMBOL" placeholder="SPY" />
          </Field>
          <ToggleField k="REGIME_STRICT" label="Bear-market policy" hint="Strict blocks every buy while the regime is bearish." />
        </div>

        {/* Position exits (fallback %) */}
        <div className="setup-card">
          <div className="setup-card-label">Position exits</div>
          <p className="setup-card-desc">
            ATR stops and the trailing stop manage exits. These percentages are the
            fallback used only when an ATR-based level can't be calculated.
          </p>
          <SliderField k="STOP_LOSS_PCT"   label="Stop loss (fallback)"   min={0.5} max={20}  step={0.5} unit="%" hint="Exit if price falls this % below entry when no ATR stop is available." />
          <SliderField k="TAKE_PROFIT_PCT" label="Take profit (fallback)" min={1}   max={50}  step={0.5} unit="%" hint="Exit at this % gain when the trailing stop isn't active." />
        </div>

        {/* Account guardrails */}
        <div className="setup-card">
          <div className="setup-card-label">Account guardrails</div>
          <p className="setup-card-desc">
            Minimum equity floor and the fallback order quantity.
          </p>
          <Field label="Min account value ($)" hint="Bot halts new entries if total account value drops below this.">
            <NumInput k="MIN_ACCOUNT_VALUE" min={0} max={100000} step={10} />
          </Field>
          <Field label="Fallback trade quantity (shares)" hint="Used only if risk-based sizing can't compute a quantity.">
            <NumInput k="DEFAULT_TRADE_QUANTITY" min={0.01} max={1000} step={0.01} />
          </Field>
        </div>

        {/* Screener & discovery */}
        <div className="setup-card">
          <div className="setup-card-label">Screener & discovery</div>
          <p className="setup-card-desc">
            How many symbols are analysed each cycle and how often discovery adds new ones.
          </p>
          <SliderField k="MAX_SYMBOLS_PER_CYCLE" label="Symbols per cycle" min={1} max={20} step={1} hint="Symbols pulled from the watchlist and sent to the AI each cycle." />
          <SliderField k="DISCOVERY_INTERVAL_CYCLES" label="Discovery every N cycles" min={1} max={20} step={1} hint="How often the screener searches for new watchlist candidates." />
          <SliderField k="DISCOVERY_TOP_N"    label="Discovery top-N" min={1} max={30} step={1} hint="Max new symbols added to the watchlist per discovery run." />
          <SliderField k="MAX_WATCHLIST_SIZE" label="Max watchlist size" min={5} max={100} step={5} hint="Watchlist is pruned to this length after each discovery run." />
        </div>

        {/* Summary */}
        <div className="setup-card setup-card-wide">
          <div className="setup-card-label">Current settings summary</div>
          <div className="setup-summary-grid">
            {[
              ["Risk / trade",       `${vals.RISK_PER_TRADE_PCT}%`],
              ["ATR stop",           `${vals.ATR_STOP_MULTIPLIER}×`],
              ["Min R:R",            `${vals.MIN_RISK_REWARD}:1`],
              ["Max position",       `${vals.MAX_POSITION_PCT}%`],
              ["Max hold",           `${vals.MAX_HOLD_DAYS} days`],
              ["Filter gate",        `${vals.MIN_FILTER_SCORE}/4`],
              ["Earnings buffer",    `${vals.EARNINGS_BUFFER_DAYS} days`],
              ["Min rel. strength",  `${vals.MIN_RELATIVE_STRENGTH}×`],
              ["Regime benchmark",   vals.MARKET_REGIME_SYMBOL],
              ["Bear policy",        vals.REGIME_STRICT ? "strict" : "lenient"],
              ["Stop / TP fallback", `${vals.STOP_LOSS_PCT}% / ${vals.TAKE_PROFIT_PCT}%`],
              ["Min account value",  `$${vals.MIN_ACCOUNT_VALUE}`],
              ["Symbols / cycle",    vals.MAX_SYMBOLS_PER_CYCLE],
              ["Discovery every",    `${vals.DISCOVERY_INTERVAL_CYCLES} cycles`],
              ["Discovery top-N",    vals.DISCOVERY_TOP_N],
              ["Max watchlist",      vals.MAX_WATCHLIST_SIZE],
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
