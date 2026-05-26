import json
import os
import requests
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama2"


@dataclass
class OllamaResult:
    model: str
    prompt: str
    raw_text: str
    parsed: Optional[Dict[str, Any]]
    error: Optional[str]


class OllamaClient:
    """Client for a locally running Ollama instance via REST API."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 512,
        base_url: str = OLLAMA_BASE_URL,
    ) -> None:
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        self.temperature = max(0.0, min(1.0, temperature))
        self.max_tokens = max(1, max_tokens)
        self.base_url = base_url.rstrip("/")

    def query(self, prompt: str, stop: Optional[Sequence[str]] = None) -> OllamaResult:
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        if stop:
            payload["options"]["stop"] = list(stop)

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            raw_text = data.get("response", "").strip()
            parsed = self._parse_json(raw_text)
            return OllamaResult(
                model=self.model_name,
                prompt=prompt,
                raw_text=raw_text,
                parsed=parsed,
                error=None,
            )
        except requests.exceptions.ConnectionError:
            error = (
                f"Cannot connect to Ollama at {self.base_url}. "
                "Make sure Ollama is running: `ollama serve`"
            )
            return OllamaResult(model=self.model_name, prompt=prompt, raw_text="", parsed=None, error=error)
        except requests.exceptions.RequestException as e:
            return OllamaResult(model=self.model_name, prompt=prompt, raw_text="", parsed=None, error=str(e))

    @staticmethod
    def _parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
        if not raw_text:
            return None

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            # Try to find a JSON object embedded in the response text.
            for line in raw_text.splitlines():
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
            return None


class DecisionEngine:
    """Build trading decisions from market context using a local LLM."""

    def __init__(self, client: OllamaClient) -> None:
        self.client = client

    def make_decision(self, context: Dict[str, Any], question: str) -> Dict[str, Any]:
        prompt = self._build_prompt(context, question)
        result = self.client.query(prompt, stop=["\n\n"])

        if result.error:
            raise RuntimeError(f"Ollama request failed: {result.error}")

        return {
            "model":    result.model,
            "prompt":   result.prompt,
            "raw_text": result.raw_text,
            "decision": result.parsed or {"text": result.raw_text},
        }

    @staticmethod
    def _build_prompt(context: Dict[str, Any], question: str) -> str:
        context_json = json.dumps(context, indent=2)
        return (
            "You are an expert swing trader making decisions based on daily-bar technical analysis.\n"
            "Swing trades are typically held for 1–10 days. Prioritise high-conviction, low-risk setups.\n\n"

            "INDICATOR GUIDE (all on daily bars):\n"
            "  rsi_14          — below 35: oversold/reversal zone; 35-60: healthy momentum; above 70: overbought\n"
            "  macd_crossover  — 'bullish': MACD just crossed above signal (buy signal); 'bearish': crossed below (sell signal)\n"
            "  macd_hist_rising— true = momentum building; false = momentum weakening\n"
            "  price_vs_sma20_pct / sma50_pct / sma200_pct — % above/below moving averages\n"
            "                    Price above all three MAs = strong uptrend; below all three = downtrend\n"
            "  bb_position     — 0.0 = at lower Bollinger Band (oversold/bounce); 1.0 = at upper band (overbought/fade)\n"
            "  atr_14          — average daily range in dollars; used to size positions and set stops\n"
            "  52w_range_pct   — 0 = at 52-week low, 100 = at 52-week high\n"
            "  volume          — 'high': above 1.5× 20-day avg (confirms breakouts/breakdowns)\n"
            "  pre_trade_filters.regime   — broad market trend: 'bull', 'neutral', or 'bear'\n"
            "  pre_trade_filters.setup_grade — A/B/C/D composite technical quality score\n\n"

            "SWING TRADE SETUP TYPES (use exactly one):\n"
            "  breakout      — price breaking above resistance with volume\n"
            "  pullback      — healthy dip to support in an uptrend (buy the dip)\n"
            "  reversal      — oversold bounce from significant low / support\n"
            "  trend_follow  — entering mid-trend after consolidation\n"
            "  breakdown_short — price failing at resistance, momentum turning down\n"
            "  none          — no clear setup; use with HOLD\n\n"

            "DECISION RULES:\n"
            "  - HOLD if: setup_grade is C or D, bear regime with no hedge rationale, RSI > 72, OR\n"
            "             earnings within 5 days (check pre_trade_filters.days_to_earnings)\n"
            "  - BUY  if: at least 3 of 4 filters pass, clear bullish setup, RSI not overbought\n"
            "  - SELL if: existing position has hit target, stop risk, or setup has broken down\n"
            "  - Use the suggested_stop_price and suggested_target_price as your anchors\n"
            "    but adjust based on key support/resistance levels you observe\n\n"

            f"Context:\n{context_json}\n\n"
            f"Question: {question}\n\n"

            "Respond ONLY with a JSON object — no extra text. Required keys:\n"
            '  "action"             — "BUY", "SELL", or "HOLD"\n'
            '  "confidence"         — float 0.0–1.0 (your conviction in this decision)\n'
            '  "setup_type"         — one of the setup types listed above\n'
            '  "expected_hold_days" — integer: how many days you expect to hold (1–10)\n'
            '  "stop_loss_price"    — exact dollar price for the stop loss (not a percentage)\n'
            '  "take_profit_price"  — exact dollar price for the take profit target\n'
            '  "reasoning"          — 1–3 sentences citing specific indicators\n'
            '  "risk_notes"         — any concerns that lowered your confidence\n\n'

            "Example: "
            '{"action":"BUY","confidence":0.78,"setup_type":"pullback","expected_hold_days":4,'
            '"stop_loss_price":148.50,"take_profit_price":162.00,'
            '"reasoning":"RSI 42 recovering from oversold, price at SMA50 support, MACD histogram turning positive.",'
            '"risk_notes":"Broad market neutral, earnings in 12 days so hold short."}'
        )
