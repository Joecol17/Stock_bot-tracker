# Stock Bot Tracker - Ollama Decision System Base

This repository contains a minimal base system for using a locally downloaded Ollama model to make decisions.

## What is included

- `decision_system.py` - Ollama client and decision engine scaffold.
- `main.py` - example usage of the local model.
- `requirements.txt` - placeholder for Python dependencies.

## Setup

1. Install Ollama and download a model locally.
2. Ensure `ollama` is available on your PATH.
3. Set the model name with `OLLAMA_MODEL` or update `model_name` in `main.py`.

## Run

```bash
python main.py
```

## Customization

- Extend `DecisionEngine._build_prompt` for domain-specific decision templates.
- Add model-specific stop tokens, temperature, and token limits in `OllamaClient`.
- Use the output structure in `decision_system.py` as a base for pipelines and risk filters.
