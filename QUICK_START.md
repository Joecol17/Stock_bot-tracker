# Quick Reference Guide

## Getting Started (5 Minutes)

### 1. Set API Key
```powershell
$env:TRADING212_API_KEY = "your_api_key_here"
```

### 2. Start Ollama
```bash
ollama serve
```
(In another terminal)

### 3. Run Demo
```bash
python main.py
```

## Commands

### Demo/Testing
```bash
python main.py              # Run demo analysis
```

### Interactive Trading
```bash
python interactive.py       # Menu-driven trading interface
```

### Automated Bot
```bash
python auto_trader.py       # Continuous automated trading
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `TRADING212_API_KEY` | *(required)* | Trading 212 API key |
| `TRADING212_DEMO_MODE` | `true` | Use demo account |
| `OLLAMA_MODEL` | `llama2` | Ollama model name |
| `OLLAMA_TEMPERATURE` | `0.2` | Decision consistency |
| `DEFAULT_TRADE_QUANTITY` | `1` | Fallback shares per trade |
| `RISK_PER_TRADE_PCT` | `0.01` | Portfolio risk per trade (1%) |

### Setting Variables (Windows PowerShell)
```powershell
$env:TRADING212_API_KEY = "your_key"
$env:TRADING212_DEMO_MODE = "true"
$env:DEFAULT_TRADE_QUANTITY = "1"
```

### Permanent Settings
1. Right-click "This PC" → Properties
2. Advanced system settings
3. Environment Variables
4. New User variable
5. Name: `TRADING212_API_KEY`
6. Value: `your_api_key`

## Common Tasks

### Check Account Balance
```python
from trading_system import TradingSystem
system = TradingSystem(is_demo=True)
account = system.get_account_status()
print(f"Cash: ${account['cash']}")
```

### View Positions
```python
positions = system.get_open_positions()
for pos in positions:
    print(f"{pos['symbol']}: {pos['quantity']} shares")
```

### Place Trade
```python
context = {
    "symbol": "AAPL",
    "price": 178.23,
    "trend": "uptrend",
}
result = system.analyze_and_trade("AAPL", context, quantity=1)
```

### Cancel Order
```python
system.cancel_order("order_id_123")
```

### View Trade History
```python
trades = system.get_trade_history()
for trade in trades:
    print(f"{trade['symbol']}: {trade['execution']['action']}")
```

## Troubleshooting

### API Key Error
```
ERROR: TRADING212_API_KEY environment variable is required!
```
**Solution:**
```powershell
$env:TRADING212_API_KEY = "your_api_key"
```

### Ollama Error
```
Error: Ollama query failed
```
**Solutions:**
1. Start Ollama: `ollama serve`
2. Check model: `ollama list`
3. Download model: `ollama pull llama2`

### Connection Error
```
API request failed: Connection refused
```
**Solutions:**
1. Check internet connection
2. Verify Trading 212 API is up
3. Check firewall settings

### Insufficient Funds
```
Message: "Insufficient free funds for trade"
```
**Solutions:**
1. Check account balance: `system.get_account_status()`
2. Use demo account: `TRADING212_DEMO_MODE=true`
3. Reset account in Trading 212 settings

## Key Classes

### TradingSystem
Main orchestrator for the trading system.
```python
system = TradingSystem(api_key, ollama_model, is_demo)
system.analyze_and_trade(symbol, context, quantity)
system.get_account_status()
system.get_open_positions()
system.get_open_orders()
system.cancel_order(order_id)
system.print_status()
```

### Trading212Client
API client for Trading 212.
```python
client = Trading212Client(api_key, is_demo)
client.get_account_info()
client.get_positions()
client.get_orders()
client.place_order(symbol, quantity, side, order_type)
client.cancel_order(order_id)
```

### OrderExecutor
Executes trading decisions.
```python
executor = OrderExecutor(trading_client)
result = executor.execute_decision(decision, symbol, quantity)
summary = executor.get_account_summary()
history = executor.get_trade_history()
```

### DecisionEngine
Makes trading decisions using Ollama.
```python
engine = DecisionEngine(ollama_client)
decision = engine.make_decision(context, question)
```

## File Reference

| File | Purpose |
|------|---------|
| `main.py` | Demo entry point |
| `interactive.py` | Interactive CLI menu |
| `auto_trader.py` | Automated trading bot |
| `trading_system.py` | Core orchestrator |
| `trading212_client.py` | API wrapper |
| `order_executor.py` | Trade execution |
| `decision_system.py` | Ollama decision engine |
| `config.py` | Configuration |
| `README.md` | Project overview |
| `SETUP.md` | Detailed setup |

## Important Notes

⚠️ **Always test in Demo Mode first**
- Set `TRADING212_DEMO_MODE=true`
- Uses virtual funds only
- No real money at risk

⚠️ **AI Decisions May Be Wrong**
- Verify decisions before executing
- Start with small quantities (1 share)
- Monitor trades closely

⚠️ **Risk Management**
- Check account balance before trading
- Validate positions before selling
- Let risk-based sizing and ATR/trailing stops manage exposure

## Support

- **API Issues**: Check Trading 212 API status
- **Model Issues**: Check Ollama installation
- **Bugs**: Review log files
- **Questions**: See SETUP.md for detailed guide

## Log Files

- `trading_bot.log` - Automated bot logs
- Console output - Real-time status

## Next Steps

1. ✓ Set API key
2. ✓ Start Ollama
3. ✓ Run `python main.py`
4. ✓ Try `python interactive.py`
5. ✓ Review decisions carefully
6. ✓ Start with small quantities
7. ✓ Run `python auto_trader.py` when confident
