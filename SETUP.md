# Trading 212 API Integration - Setup Guide

## Overview

This trading system combines Ollama AI decision-making with the Trading 212 API to automatically analyze markets and execute trades on a practice account.

**Key Features:**
- ✓ AI-powered trading decisions using Ollama (llama2, etc.)
- ✓ Practice/Demo account support (safe trading)
- ✓ Full order management (buy, sell, cancel)
- ✓ Real-time position tracking
- ✓ Trade logging and history

## Prerequisites

1. **Ollama** - for local AI model
   - Download from: https://ollama.ai
   - Install and run: `ollama run llama2`

2. **Trading 212 API Key**
   - Create a Trading 212 account: https://trading212.com
   - Get API key from account settings
   - For practice/demo trading: Use demo mode flag

3. **Python 3.8+**

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Trading 212 API key** (Windows):
   ```powershell
   $env:TRADING212_API_KEY = "your_api_key_here"
   ```

   Or permanently set in System Environment Variables:
   - Right-click "This PC" → Properties → Advanced system settings
   - Environment Variables → New User variable
   - Name: `TRADING212_API_KEY`
   - Value: `your_api_key_here`

3. **Verify Ollama is running:**
   ```bash
   ollama list
   ```

## Configuration

Edit environment variables in your shell or system settings:

```bash
# Trading 212 Settings
set TRADING212_API_KEY=your_api_key_here
set TRADING212_DEMO_MODE=true              # Use demo/practice (true/false)

# Ollama Settings
set OLLAMA_MODEL=llama2                     # Model name
set OLLAMA_TEMPERATURE=0.2                  # 0.0-1.0 (lower = more deterministic)
set OLLAMA_MAX_TOKENS=256                   # Max response length

# Trading Parameters
set DEFAULT_TRADE_QUANTITY=1                # Fallback shares per trade
set MAX_DAILY_TRADES=0                      # 0 = unlimited (no daily cap)
set MIN_ACCOUNT_VALUE=100                   # Minimum account value
```

## Quick Start

### 1. Run the demo:
```bash
python main.py
```

This will:
- Check your account status
- Analyze Apple (AAPL) stock
- Make a trading decision
- Display positions and orders
- Show trade history

### 2. Interactive trading (interactive.py):
```bash
python interactive.py
```

Allows you to:
- Analyze specific stocks
- Execute trades manually
- Monitor positions
- Cancel orders

### 3. Automated trading loop (auto_trader.py):
```bash
python auto_trader.py
```

Continuously monitors and trades based on:
- Real-time market data
- AI decision engine
- Risk management rules

## File Structure

```
Stock_bot-tracker/
├── main.py                 # Main entry point with demo
├── interactive.py          # Interactive trading CLI
├── auto_trader.py         # Automated trading loop
├── trading_system.py      # Core trading system
├── trading212_client.py   # Trading 212 API wrapper
├── order_executor.py      # Order execution logic
├── decision_system.py     # Ollama decision engine
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── SETUP.md              # This file
└── README.md             # Project overview
```

## Usage Examples

### Basic Trade Analysis
```python
from trading_system import TradingSystem

system = TradingSystem(is_demo=True)

context = {
    "symbol": "AAPL",
    "price": 178.23,
    "trend": "uptrend",
    "news": "Strong earnings reported",
}

result = system.analyze_and_trade("AAPL", context, quantity=1)
print(result['execution'])
```

### Account Status
```python
system = TradingSystem(is_demo=True)
system.print_status()
```

### Cancel Order
```python
success = system.cancel_order("order_id_123")
```

## API Endpoints Used

### Account
- `GET /account` - Get account info
- `GET /positions` - Get open positions
- `GET /orders` - Get open orders

### Orders
- `POST /orders` - Place new order
- `DELETE /orders/{id}` - Cancel order

### Instruments
- `GET /instruments/{symbol}` - Get instrument details
- `GET /instruments/search` - Search instruments

## Risk Management

**Safety Features:**
1. ✓ Demo mode enabled by default
2. ✓ Insufficient funds check before trades
3. ✓ Position availability check for sells
4. ✓ Trade history logging
5. ✓ Risk-based position sizing with ATR & trailing stops
6. ✓ Minimum account value threshold

**Recommended Settings for Learning:**
- Demo Mode: **ON**
- Trade Quantity: **1 share**
- Risk Per Trade: **1%** of portfolio
- Ollama Temperature: **0.2** (consistent decisions)

## Troubleshooting

### "API key not found"
- Check `TRADING212_API_KEY` environment variable is set
- Restart terminal after setting environment variable

### "Ollama query failed"
- Make sure Ollama is running: `ollama serve`
- Check model is installed: `ollama list`
- Pull model: `ollama pull llama2`

### "Insufficient funds"
- Check account balance: `system.get_account_status()`
- Demo accounts start with virtual funds
- Reset account if needed in Trading 212 settings

### Connection timeout
- Check internet connection
- Verify Trading 212 API is up: https://status.trading212.com
- Increase timeout in `trading212_client.py`

## Demo vs Live Trading

**DEMO MODE (Recommended for testing):**
```
TRADING212_DEMO_MODE=true
```
- Uses practice account
- Virtual funds only
- No real money at risk
- Same API interface as live

**LIVE MODE (Use with caution):**
```
TRADING212_DEMO_MODE=false
```
- Real money trades
- Real positions
- Binding orders
- **Use only after extensive testing**

## Next Steps

1. **Test in demo mode** with the main.py script
2. **Explore interactive.py** to manually trade
3. **Review decision_system.py** to understand AI decisions
4. **Configure risk parameters** in config.py
5. **Start automated trading** once confident

## Support & Resources

- Trading 212 API Docs: https://trading212.com/api
- Ollama Docs: https://github.com/ollama/ollama
- Project Repository: Stock_bot-tracker
