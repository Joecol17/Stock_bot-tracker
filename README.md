# Stock Bot Tracker - AI-Powered Trading System

A comprehensive trading system that combines Ollama AI decision-making with the Trading 212 API to automatically analyze markets and execute trades on a practice account.

## Overview

This system provides:
- **AI Decision Engine**: Uses Ollama (llama2, etc.) to analyze market context and make trading decisions
- **Trading 212 Integration**: Full API integration for order execution, position tracking, and account management
- **Practice Account Support**: Safe testing with demo/virtual funds
- **Multiple Trading Modes**: Demo analysis, interactive trading, or fully automated bot

## Features

✓ **AI-Powered Analysis** - Ollama decision engine analyzes market context  
✓ **Practice Trading** - Demo account support (no real money risk)  
✓ **Full Order Management** - Buy, sell, limit, stop orders  
✓ **Position Tracking** - Real-time position and P/L monitoring  
✓ **Trade History** - Complete logging of all trades  
✓ **Risk Management** - Insufficient funds checks, position validation  
✓ **Multiple Interfaces** - CLI, interactive, and automated modes  

## Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Trading 212 API key (Windows PowerShell)
$env:TRADING212_API_KEY = "your_api_key"

# Make sure Ollama is running
ollama serve
```

### 2. Run Demo

```bash
python main.py
```

This will:
- Check your account status
- Analyze Apple stock
- Make a trading decision
- Display positions and execution results

### 3. Interactive Mode

```bash
python interactive.py
```

Interactive menu with options to:
- Analyze and trade specific stocks
- View account status and positions
- Manage orders
- View trade history

### 4. Automated Trading

```bash
python auto_trader.py
```

Continuously monitors symbols and executes trades based on AI analysis.

## Configuration

Set environment variables to customize behavior:

```powershell
# Trading 212
$env:TRADING212_API_KEY = "your_api_key"          # Required
$env:TRADING212_DEMO_MODE = "true"                # Use demo account (default: true)

# Ollama
$env:OLLAMA_MODEL = "llama2"                       # Model name (default: llama2)
$env:OLLAMA_TEMPERATURE = "0.2"                    # 0.0-1.0, lower = more consistent
$env:OLLAMA_MAX_TOKENS = "256"                     # Max response length

# Trading Parameters
$env:DEFAULT_TRADE_QUANTITY = "1"                  # Shares per trade
$env:MAX_DAILY_TRADES = "10"                       # Safety limit
$env:MIN_ACCOUNT_VALUE = "100"                     # Minimum account value
```

## Architecture

### Core Components

```
trading_system.py          - Main orchestrator
├── decision_system.py     - Ollama decision engine
├── trading212_client.py   - API client
└── order_executor.py      - Order execution
```

### File Structure

```
Stock_bot-tracker/
├── main.py                # Demo entry point
├── interactive.py         # Interactive CLI
├── auto_trader.py         # Automated trading bot
├── trading_system.py      # Core trading system
├── trading212_client.py   # Trading 212 API wrapper
├── order_executor.py      # Order execution engine
├── decision_system.py     # Ollama decision engine
├── config.py              # Configuration management
├── requirements.txt       # Dependencies
├── SETUP.md              # Detailed setup guide
└── README.md             # This file
```

## Usage Examples

### Basic Analysis
```python
from trading_system import TradingSystem

system = TradingSystem(is_demo=True)

context = {
    "symbol": "AAPL",
    "price": 178.23,
    "trend": "uptrend",
    "news": "Strong earnings",
}

result = system.analyze_and_trade("AAPL", context, quantity=1)
```

### Check Account
```python
system = TradingSystem(is_demo=True)
status = system.get_account_status()
print(f"Cash: ${status['cash']:.2f}")
print(f"Portfolio Value: ${status['portfolio_value']:.2f}")
```

### View Positions
```python
positions = system.get_open_positions()
for pos in positions:
    print(f"{pos['symbol']}: {pos['quantity']} shares, P/L: ${pos['profit_loss']:.2f}")
```

### Cancel Order
```python
system.cancel_order("order_id_123")
```

## API Endpoints

### Account
- `GET /account` - Account information
- `GET /positions` - Open positions
- `GET /orders` - Open orders

### Orders
- `POST /orders` - Place new order
- `DELETE /orders/{id}` - Cancel order

### Instruments
- `GET /instruments/{symbol}` - Instrument details
- `GET /instruments/search` - Search instruments

## Safety & Risk Management

**Built-in Safety Features:**
- Demo mode enabled by default (virtual funds)
- Insufficient funds check before trades
- Position validation for sell orders
- Daily trade limit enforcement
- Minimum account value threshold
- Complete trade logging

**Recommended Settings for Learning:**
- Demo Mode: **ON**
- Trade Quantity: **1 share**
- Max Daily Trades: **5**
- Temperature: **0.2** (consistent decisions)

## Trading Decision Flow

```
Market Context
    ↓
Ollama Decision Engine
    ├─ Analyzes context
    ├─ Generates decision
    └─ Returns BUY/SELL/HOLD
    ↓
Order Executor
    ├─ Validates account/position
    ├─ Places order via API
    └─ Returns execution result
    ↓
Trade Logger
    └─ Records trade history
```

## Troubleshooting

### "API key not found"
```powershell
$env:TRADING212_API_KEY = "your_api_key"
```

### "Ollama query failed"
```bash
# Make sure Ollama is running
ollama serve

# Check model is installed
ollama list

# Download model if needed
ollama pull llama2
```

### "Insufficient funds"
- Check account balance in `system.get_account_status()`
- Demo accounts may need reset in Trading 212 settings
- Ensure Demo Mode is ON: `$env:TRADING212_DEMO_MODE = "true"`

## Demo vs Live Mode

**Demo Mode (Recommended)**
```
TRADING212_DEMO_MODE=true
```
- Practice/demo account
- Virtual funds only
- No real money at risk
- Perfect for testing

**Live Mode (Caution)**
```
TRADING212_DEMO_MODE=false
```
- Real money trades
- Real positions and P/L
- Binding orders
- Use only after extensive testing

## Next Steps

1. **Follow SETUP.md** for detailed configuration
2. **Run main.py** to test the system
3. **Use interactive.py** for manual trading
4. **Review decision_system.py** to understand AI decisions
5. **Customize config.py** for your risk parameters
6. **Start auto_trader.py** once confident

## Learning Resources

- **Trading 212 API**: https://trading212.com/api
- **Ollama Documentation**: https://github.com/ollama/ollama
- **Trading Concepts**: https://www.investopedia.com

## Disclaimer

This system is provided for educational purposes. Trading involves risk:
- Always test thoroughly in demo mode first
- Never use live mode without understanding the risks
- AI decisions may be wrong; always verify before trading
- Past performance does not guarantee future results

## License

This project is provided as-is for educational purposes.

