import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

DEFAULT_MODEL = "llama2"


@dataclass
class OllamaResult:
    model: str
    prompt: str
    raw_text: str
    parsed: Optional[Dict[str, Any]]
    exit_code: int
    stderr: str


class OllamaClient:
    """Simple client for a locally downloaded Ollama model."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 256,
    ) -> None:
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        self.temperature = temperature
        self.max_tokens = max_tokens

    def query(self, prompt: str, stop: Optional[Sequence[str]] = None) -> OllamaResult:
        command: List[str] = [
            "ollama",
            "query",
            self.model_name,
            prompt,
            "--temperature",
            str(self.temperature),
            "--max-tokens",
            str(self.max_tokens),
            "--json",
        ]

        if stop:
            # Ollama accepts multiple --stop options or a comma-separated list.
            command.extend(["--stop", ",".join(stop)])

        result = subprocess.run(command, capture_output=True, text=True)
        raw_text = result.stdout.strip()
        parsed = self._parse_json(raw_text)

        return OllamaResult(
            model=self.model_name,
            prompt=prompt,
            raw_text=raw_text,
            parsed=parsed,
            exit_code=result.returncode,
            stderr=result.stderr.strip(),
        )

    @staticmethod
    def _parse_json(raw_text: str) -> Optional[Dict[str, Any]]:
        if not raw_text:
            return None

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            # Try to locate JSON inside a longer text response.
            for line in raw_text.splitlines():
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
            return None


class DecisionEngine:
    """Build decisions from context and a task prompt."""

    def __init__(self, client: OllamaClient) -> None:
        self.client = client

    def make_decision(self, context: Dict[str, Any], question: str) -> Dict[str, Any]:
        prompt = self._build_prompt(context, question)
        result = self.client.query(prompt, stop=["\n\n"])

        if result.exit_code != 0:
            raise RuntimeError(
                f"Ollama query failed (exit code={result.exit_code}): {result.stderr}"
            )

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
            "You are a decision-making agent. Use the provided context to answer the question. "
            "Return a JSON object with keys: action, reasoning, and details.\n\n"
            f"Context:\n{context_json}\n\n"
            f"Question: {question}\n\n"
            "Answer in valid JSON only."
        )
