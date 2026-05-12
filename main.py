from decision_system import DecisionEngine, OllamaClient


def main() -> None:
    client = OllamaClient(model_name=None)
    engine = DecisionEngine(client)

    sample_context = {
        "symbol": "AAPL",
        "position": "long",
        "price": 178.23,
        "trend": "neutral",
        "news_headline": "Apple announces stronger than expected earnings",
        "risk_tolerance": "medium",
    }

    question = "Based on this context, should the system buy, sell, or hold?"
    decision = engine.make_decision(sample_context, question)

    print("Decision result:")
    print(decision)


if __name__ == "__main__":
    main()
