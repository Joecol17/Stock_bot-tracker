import os
from trading_system import TradingSystem
from config import Config


def main() -> None:
    """Main entry point for the trading system."""
    
    # Validate configuration
    print("Initializing Trading System...")
    Config.print_config()
    
    if not Config.TRADING212_API_KEY:
        print("\nERROR: TRADING212_API_KEY environment variable is required!")
        print("Set it before running: set TRADING212_API_KEY=your_api_key")
        return
    
    try:
        # Initialize trading system (demo mode by default)
        trading_system = TradingSystem(
            api_key=Config.TRADING212_API_KEY,
            ollama_model=Config.OLLAMA_MODEL,
            is_demo=Config.TRADING212_DEMO_MODE,
        )
        
        print(f"\n✓ Trading System initialized in {'DEMO' if Config.TRADING212_DEMO_MODE else 'LIVE'} mode\n")
        
        # Example 1: Check account status
        print("=" * 60)
        print("Example 1: Checking Account Status")
        print("=" * 60)
        trading_system.print_status()
        
        # Example 2: Analyze and trade based on market context
        print("=" * 60)
        print("Example 2: Decision-Based Trading")
        print("=" * 60)
        
        sample_context = {
            "symbol": "AAPL",
            "position": "long",
            "price": 178.23,
            "trend": "uptrend",
            "news_headline": "Apple announces stronger than expected earnings",
            "risk_tolerance": "medium",
            "volume": "high",
            "support_level": 175.00,
            "resistance_level": 182.00,
        }
        
        print(f"\nAnalyzing {sample_context['symbol']} with context:")
        for key, value in sample_context.items():
            print(f"  {key}: {value}")
        
        result = trading_system.analyze_and_trade(
            symbol="AAPL",
            context=sample_context,
            quantity=1,
        )
        
        print("\nDecision Engine Result:")
        print(f"  Raw Decision: {result['decision'].get('raw_text', 'N/A')[:200]}...")
        
        print("\nExecution Result:")
        exec_result = result['execution']
        print(f"  Status: {'✓ SUCCESS' if exec_result['success'] else '✗ FAILED'}")
        print(f"  Action: {exec_result['action']}")
        print(f"  Message: {exec_result['message']}")
        if exec_result['order_id']:
            print(f"  Order ID: {exec_result['order_id']}")
        if exec_result['error']:
            print(f"  Error: {exec_result['error']}")
        
        # Example 3: View open positions
        print("\n" + "=" * 60)
        print("Example 3: Open Positions")
        print("=" * 60)
        positions = trading_system.get_open_positions()
        if positions:
            for pos in positions:
                print(f"\n{pos['symbol']}:")
                print(f"  Quantity: {pos['quantity']}")
                print(f"  Current Value: ${pos['value']:.2f}")
                print(f"  Profit/Loss: ${pos['profit_loss']:.2f}")
        else:
            print("No open positions")
        
        # Example 4: View open orders
        print("\n" + "=" * 60)
        print("Example 4: Open Orders")
        print("=" * 60)
        orders = trading_system.get_open_orders()
        if orders:
            for order in orders:
                print(f"\n{order['symbol']}:")
                print(f"  Type: {order['side']}")
                print(f"  Quantity: {order['quantity']}")
                print(f"  Status: {order['status']}")
        else:
            print("No open orders")
        
        # Example 5: Trade history
        print("\n" + "=" * 60)
        print("Example 5: Trade History")
        print("=" * 60)
        history = trading_system.get_trade_history()
        if history:
            for i, trade in enumerate(history, 1):
                print(f"\nTrade {i}: {trade['symbol']}")
                print(f"  Decision: {trade['decision'].get('raw_text', 'N/A')[:100]}...")
                print(f"  Execution: {trade['execution']['action']} - {trade['execution']['message']}")
        else:
            print("No trades executed yet")
        
        print("\n" + "=" * 60)
        print("Trading System Demo Complete")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
