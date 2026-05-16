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
        max_tokens: int = 256,
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
            "model": result.model,
            "prompt": result.prompt,
            "raw_text": result.raw_text,
            "decision": result.parsed or {"text": result.raw_text},
        }

    @staticmethod
    def _build_prompt(context: Dict[str, Any], question: str) -> str:
        context_json = json.dumps(context, indent=2)
        return (
            "You are a stock trading decision agent. Analyse the context and answer the question.\n"
            "The context may include technical indicators — use them as follows:\n"
            "  - rsi_14: RSI(14). Below 30 = oversold (bullish signal), above 70 = overbought (bearish signal).\n"
            "  - macd_crossover: 'bullish' means MACD crossed above signal line (buy signal), 'bearish' means below (sell signal).\n"
            "  - macd_histogram: positive and rising = strengthening uptrend; negative and falling = strengthening downtrend.\n"
            "  - price_vs_sma20_pct / price_vs_sma50_pct: % above/below the moving average. Negative = price below MA (bearish).\n"
            "  - bb_position: 0 = price at lower Bollinger Band (potential reversal up), 1 = at upper band (potential reversal down).\n"
            'Respond with a JSON object containing exactly these keys: "action" (one of BUY, SELL, HOLD), '
            '"reasoning" (brief explanation referencing the indicators), "details" (any extra notes).\n\n'
            f"Context:\n{context_json}\n\n"
            f"Question: {question}\n\n"
            "Answer in valid JSON only. Example: "
            '{"action": "HOLD", "reasoning": "RSI at 65 approaching overbought, MACD bearish crossover", "details": ""}'
        )
