"""
AI Controller — the system's "night shift" reviewer.

Runs AFTER market close (separate schedule from the trading cycle, so it never
slows a cycle down). Its sole job is to look at how the system is performing and
say how to make it better. It:

  • reads the daily dossiers + raw data (journal.db, trades, equity, swarm log),
  • reads the codebase READ-ONLY (a manifest of modules + the tunable config) so
    its advice is grounded in what actually exists,
  • thinks with the larger `plutus` finance model (no time pressure at night),
  • files a report: new features to build, features to improve, strategy ideas,
    and clamped parameter recommendations,
  • is ADVISORY by default. It never edits code. It can only *propose* parameter
    changes; it applies them solely when CONTROLLER_AUTO_APPLY=true, and even then
    only whitelisted keys clamped to safe ranges (live via Config.reload()).

Runnable standalone:  python controller.py [--apply] [YYYY-MM-DD]
"""

import glob
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from daily_report import collect_day, generate_daily_report

logger = logging.getLogger(__name__)

# Tunable .env keys the controller may RECOMMEND (and, if enabled, apply),
# each clamped to a safe [min, max] range. Nothing outside this list is touchable.
TUNABLES: Dict[str, Tuple[float, float, bool]] = {
    # key:                     (min,   max,   is_int)
    "MIN_FILTER_SCORE":        (1,     4,     True),
    "MIN_RISK_REWARD":         (1.0,   4.0,   False),
    "RISK_PER_TRADE_PCT":      (0.005, 0.03,  False),
    "ATR_STOP_MULTIPLIER":     (1.0,   3.0,   False),
    "MAX_POSITION_PCT":        (0.05,  0.25,  False),
    "TAKE_PROFIT_PCT":         (0.06,  0.30,  False),
    "STOP_LOSS_PCT":           (0.03,  0.12,  False),
    "MIN_RELATIVE_STRENGTH":   (0.80,  1.20,  False),
    "MAX_SYMBOLS_PER_CYCLE":   (5,     60,    True),
    "EXPLORE_SLOTS":           (10,    80,    True),
    "EARNINGS_BUFFER_DAYS":    (1,     10,    True),
}

CODE_EXTS = (".py",)


def _code_manifest(root: str = ".") -> List[Dict[str, str]]:
    """A read-only map of the codebase: each module + its one-line purpose."""
    out = []
    for path in sorted(glob.glob(os.path.join(root, "*.py"))):
        name = os.path.basename(path)
        purpose = ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(800)
            # First docstring line, else first comment line.
            for marker in ('"""', "'''"):
                if marker in head:
                    body = head.split(marker, 1)[1]
                    purpose = body.strip().splitlines()[0].strip() if body.strip() else ""
                    break
            if not purpose:
                for line in head.splitlines():
                    s = line.strip()
                    if s.startswith("#"):
                        purpose = s.lstrip("# ").strip()
                        break
        except Exception:
            pass
        try:
            lines = sum(1 for _ in open(path, "r", encoding="utf-8", errors="ignore"))
        except Exception:
            lines = 0
        out.append({"file": name, "lines": str(lines), "purpose": purpose[:120]})
    return out


def _current_tunables() -> Dict[str, Any]:
    return {k: getattr(Config, k, None) for k in TUNABLES}


def _clamp(key: str, value: Any) -> Optional[Any]:
    lo, hi, is_int = TUNABLES[key]
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    v = max(lo, min(hi, v))
    return int(round(v)) if is_int else round(v, 4)


def _recent_summaries(day: str, lookback: int) -> List[Dict[str, Any]]:
    """Compact summaries for the last `lookback` filed dossiers (+ today)."""
    reports_dir = getattr(Config, "REPORTS_DIR", "reports")
    summaries: List[Dict[str, Any]] = []
    for jf in sorted(glob.glob(os.path.join(reports_dir, "daily_*.json")), reverse=True)[:lookback]:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                s = json.load(f)
            summaries.append({k: s.get(k) for k in (
                "day", "cycles", "equity_delta", "n_trades", "n_buys", "n_sells",
                "avg_confidence", "action_counts", "top_block_reasons",
                "open_positions", "free_close", "swarm_added")})
        except Exception:
            pass
    return summaries


def _build_prompt(day: str, today: Dict[str, Any], history: List[Dict[str, Any]],
                  manifest: List[Dict[str, str]], tunables: Dict[str, Any]) -> str:
    manifest_txt = "\n".join(f"  {m['file']} ({m['lines']} ln) — {m['purpose']}" for m in manifest)
    tun_txt = "\n".join(
        f"  {k} = {tunables[k]}  (allowed {TUNABLES[k][0]}–{TUNABLES[k][1]})" for k in TUNABLES
    )
    return (
        "You are the AI CONTROLLER for a local automated swing-trading bot — its night-shift "
        "strategy reviewer. You run after market close and DO NOT trade. You CANNOT change code; "
        "you advise a human developer and may only propose parameter tweaks.\n\n"
        "Your job: study the performance data below and the codebase map, then suggest concrete "
        "ways to make the whole system better — new features worth building, existing features to "
        "improve, strategy ideas, and safe parameter adjustments grounded in the data.\n\n"
        f"=== TODAY ({day}) ===\n{json.dumps(today, indent=2)[:2500]}\n\n"
        f"=== LAST {len(history)} DAYS (most recent first) ===\n{json.dumps(history, indent=2)[:3000]}\n\n"
        f"=== CODEBASE MAP (read-only) ===\n{manifest_txt}\n\n"
        f"=== TUNABLE PARAMETERS (current → allowed range) ===\n{tun_txt}\n\n"
        "Think about: are we trading too little/much? Are filters too strict (lots of FILTERED with "
        "few trades)? Is confidence predictive of outcomes? Is the explore/discovery tier adding value? "
        "Is capital fully deployed with no room for new setups?\n\n"
        "Respond ONLY with a JSON object:\n"
        "{\n"
        '  "summary": "2-3 sentence read on how the system is doing",\n'
        '  "feature_ideas": ["new capability worth building", ...],\n'
        '  "improvements": ["existing thing to improve, and how", ...],\n'
        '  "strategy_notes": ["data-grounded strategy observation", ...],\n'
        '  "param_proposals": [{"key": "MIN_FILTER_SCORE", "proposed": 3, "rationale": "why, citing the data"}]\n'
        "}\n"
        "Only use parameter keys from the tunable list. Keep every list concise and specific."
    )


def _set_env_keys(changes: Dict[str, Any], env_path: str = ".env") -> None:
    """Update/append keys in .env (utf-8, no BOM), preserving other lines."""
    lines: List[str] = []
    try:
        with open(env_path, "r", encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except Exception:
        pass
    keys_left = dict(changes)
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in keys_left:
                out.append(f"{k}={keys_left.pop(k)}")
                continue
        out.append(line)
    for k, v in keys_left.items():
        out.append(f"{k}={v}")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def run_controller(day: Optional[str] = None, apply: Optional[bool] = None) -> Dict[str, Any]:
    """Generate today's dossier, run the nightly review, and file the report.
    Returns the structured recommendation dict."""
    day = day or datetime.now().strftime("%Y-%m-%d")
    if apply is None:
        apply = getattr(Config, "CONTROLLER_AUTO_APPLY", False)

    # Make sure today's dossier exists/refreshed.
    try:
        generate_daily_report(day)
    except Exception as e:
        logger.warning(f"Controller: dossier generation failed: {e}")

    today = collect_day(day)
    history = _recent_summaries(day, getattr(Config, "CONTROLLER_LOOKBACK_DAYS", 14))
    manifest = _code_manifest()
    tunables = _current_tunables()
    prompt = _build_prompt(day, today, history, manifest, tunables)

    # Think with the bigger finance model — fall back to the trading model.
    from decision_system import OllamaClient
    model = getattr(Config, "CONTROLLER_MODEL", None) or Config.OLLAMA_MODEL
    parsed, raw, used_model = None, "", model
    for m in (model, Config.OLLAMA_MODEL):
        try:
            client = OllamaClient(model_name=m, temperature=0.3, max_tokens=900)
            res = client.query(prompt)
            raw = res.raw_text or ""
            if res and not res.error and isinstance(res.parsed, dict):
                parsed, used_model = res.parsed, m
                break
            if res and res.error:
                logger.warning(f"Controller model {m} error: {res.error}")
        except Exception as e:
            logger.warning(f"Controller model {m} failed: {e}")
    if parsed is None:
        parsed = {"summary": raw[:500] or "Controller could not produce a structured review.",
                  "feature_ideas": [], "improvements": [], "strategy_notes": [], "param_proposals": []}

    # Clamp + validate parameter proposals against the whitelist.
    clean_props = []
    for p in (parsed.get("param_proposals") or []):
        if not isinstance(p, dict):
            continue
        key = str(p.get("key", "")).strip()
        if key not in TUNABLES:
            continue
        clamped = _clamp(key, p.get("proposed"))
        if clamped is None:
            continue
        current = tunables.get(key)
        clean_props.append({
            "key": key, "current": current, "proposed": clamped,
            "rationale": str(p.get("rationale", ""))[:300],
            "changed": str(clamped) != str(current),
        })

    applied: List[str] = []
    if apply and clean_props:
        changes = {p["key"]: p["proposed"] for p in clean_props if p["changed"]}
        if changes:
            try:
                _set_env_keys(changes)
                Config.reload()
                applied = list(changes.keys())
                logger.info(f"Controller applied params: {changes}")
            except Exception as e:
                logger.warning(f"Controller could not apply params: {e}")

    recommendation = {
        "generated": datetime.now().isoformat(),
        "day": day,
        "model": used_model,
        "summary": str(parsed.get("summary", ""))[:1000],
        "feature_ideas": [str(x)[:300] for x in (parsed.get("feature_ideas") or [])][:12],
        "improvements": [str(x)[:300] for x in (parsed.get("improvements") or [])][:12],
        "strategy_notes": [str(x)[:300] for x in (parsed.get("strategy_notes") or [])][:12],
        "param_proposals": clean_props,
        "applied": applied,
        "auto_apply_enabled": bool(apply),
    }

    _write_reports(day, recommendation)
    return recommendation


def _write_reports(day: str, rec: Dict[str, Any]) -> None:
    reports_dir = getattr(Config, "REPORTS_DIR", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    # Machine-readable (latest + dated)
    for path in (os.path.join(reports_dir, f"controller_{day}.json"),
                 os.path.join(reports_dir, "controller_latest.json")):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rec, f, indent=2)
        except Exception:
            pass
    # Human-readable
    L = [f"# AI Controller Review — {day}", "",
         f"_model: {rec['model']} · generated {rec['generated'][:19]} · "
         f"auto-apply {'ON' if rec['auto_apply_enabled'] else 'OFF (advisory)'}_", "",
         "## Read on the system", rec["summary"] or "—", ""]

    def section(title, items):
        L.append(f"## {title}")
        if items:
            L.extend(f"- {it}" for it in items)
        else:
            L.append("- (none)")
        L.append("")

    section("New feature ideas", rec["feature_ideas"])
    section("Improvements", rec["improvements"])
    section("Strategy notes", rec["strategy_notes"])

    L.append("## Parameter proposals")
    if rec["param_proposals"]:
        L.append("| key | current | proposed | applied? | rationale |")
        L.append("|-----|---------|----------|----------|-----------|")
        for p in rec["param_proposals"]:
            ap = "yes" if p["key"] in rec["applied"] else ("(advisory)" if p["changed"] else "no change")
            L.append(f"| {p['key']} | {p['current']} | {p['proposed']} | {ap} | {p['rationale'][:80].replace('|','/')} |")
    else:
        L.append("- (none)")
    L.append("")

    try:
        with open(os.path.join(reports_dir, f"controller_{day}.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(L))
        logger.info(f"Controller report written: controller_{day}.md")
    except Exception as e:
        logger.warning(f"Could not write controller report: {e}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = [a for a in sys.argv[1:]]
    apply_flag = "--apply" in args
    day_arg = next((a for a in args if not a.startswith("--")), None)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    rec = run_controller(day_arg, apply=apply_flag or None)
    print(json.dumps(rec, indent=2))
