"""
Interactive trading CLI for the Stock Bot Tracker system.
Allows manual analysis and execution of trades with Ollama decision engine.
"""

import sys
from trading_system import TradingSystem
from config import Config


def print_menu():
    """Display interactive menu."""
    print("\n" + "=" * 60)
    print("TRADING SYSTEM - INTERACTIVE MODE")
    print("=" * 60)
    print("1. Analyze and trade a stock")
    print("2. View account status")
    print("3. View open positions")
    print("4. View open orders")
    print("5. Cancel an order")
    print("6. View trade history")
    print("7. Manual decision input")
    print("0. Exit")
    print("=" * 60)


def get_stock_context():
    """Get market context from user input."""
    print("\nEnter market context for the stock analysis:")
    
    symbol = input("Stock symbol (e.g., AAPL): ").strip().upper()
    price = float(input("Current price: $"))
    trend = input("Trend (uptrend/downtrend/neutral): ").strip().lower()
    news = input("Recent news/headline: ").strip()
    volume = input("Volume (low/normal/high): ").strip().lower()
    risk = input("Risk tolerance (low/medium/high): ").strip().lower()
    
    return {
        "symbol": symbol,
        "price": price,
        "trend": trend,
        "news_headline": news,
        "volume": volume,
        "risk_tolerance": risk,
    }


def analyze_and_trade(system: TradingSystem):
    """Analyze stock and execute trade."""
    try:
        context = get_stock_context()
        quantity = float(input(f"Quantity to trade (default 1): ") or "1")
        
        print(f"\nAnalyzing {context['symbol']}...")
        result = system.analyze_and_trade(
            symbol=context["symbol"],
            context=context,
            quantity=quantity,
        )
        
        print("\n" + "-" * 60)
        print("DECISION ENGINE ANALYSIS")
        print("-" * 60)
        decision = result['decision']
        print(f"Raw Output: {decision.get('raw_text', 'N/A')}")
        
        print("\n" + "-" * 60)
        print("EXECUTION RESULT")
        print("-" * 60)
        exec_result = result['execution']
        print(f"Status: {'✓ SUCCESS' if exec_result['success'] else '✗ FAILED'}")
        print(f"Action: {exec_result['action']}")
        print(f"Message: {exec_result['message']}")
        if exec_result['order_id']:
            print(f"Order ID: {exec_result['order_id']}")
        if exec_result['error']:
            print(f"Error Details: {exec_result['error']}")
    
    except Exception as e:
        print(f"\nError: {e}")


def view_account_status(system: TradingSystem):
    """Display account status."""
    try:
        account = system.get_account_status()
        if "error" in account:
            print(f"Error: {account['error']}")
            return
        
        print("\n" + "-" * 60)
        print("ACCOUNT STATUS")
        print("-" * 60)
        print(f"Account ID: {account.get('account_id', 'N/A')}")
        print(f"Mode: {'DEMO' if system.is_demo else 'LIVE'}")
        print(f"Cash Balance: ${account.get('cash', 0):.2f}")
        print(f"Portfolio Value: ${account.get('portfolio_value', 0):.2f}")
        print(f"Free Funds: ${account.get('free_funds', 0):.2f}")
        print(f"Total Value: ${(account.get('cash', 0) + account.get('portfolio_value', 0)):.2f}")
    
    except Exception as e:
        print(f"Error: {e}")


def view_positions(system: TradingSystem):
    """Display open positions."""
    try:
        positions = system.get_open_positions()
        
        print("\n" + "-" * 60)
        print("OPEN POSITIONS")
        print("-" * 60)
        
        if not positions:
            print("No open positions")
            return
        
        print(f"{'Symbol':<10} {'Qty':<8} {'Price':<12} {'Value':<12} {'P/L':<12}")
        print("-" * 60)
        
        total_value = 0
        total_pl = 0
        
        for pos in positions:
            print(f"{pos['symbol']:<10} {pos['quantity']:<8.2f} ${pos['average_price']:<11.2f} "
                  f"${pos['value']:<11.2f} ${pos['profit_loss']:<11.2f}")
            total_value += pos['value']
            total_pl += pos['profit_loss']
        
        print("-" * 60)
        print(f"{'TOTAL':<10} {'':<8} {'':<12} ${total_value:<11.2f} ${total_pl:<11.2f}")
    
    except Exception as e:
        print(f"Error: {e}")


def view_orders(system: TradingSystem):
    """Display open orders."""
    try:
        orders = system.get_open_orders()
        
        print("\n" + "-" * 60)
        print("OPEN ORDERS")
        print("-" * 60)
        
        if not orders:
            print("No open orders")
            return
        
        print(f"{'Order ID':<15} {'Symbol':<10} {'Type':<6} {'Qty':<8} {'Price':<12} {'Status':<10}")
        print("-" * 60)
        
        for order in orders:
            print(f"{order['order_id']:<15} {order['symbol']:<10} {order['side']:<6} "
                  f"{order['quantity']:<8.2f} ${order['price']:<11.2f} {order['status']:<10}")
    
    except Exception as e:
        print(f"Error: {e}")


def cancel_order(system: TradingSystem):
    """Cancel an order."""
    try:
        order_id = input("\nEnter Order ID to cancel: ").strip()
        
        if system.cancel_order(order_id):
            print(f"✓ Order {order_id} cancelled successfully")
        else:
            print(f"✗ Failed to cancel order {order_id}")
    
    except Exception as e:
        print(f"Error: {e}")


def view_trade_history(system: TradingSystem):
    """Display trade history."""
    try:
        history = system.get_trade_history()
        
        print("\n" + "-" * 60)
        print("TRADE HISTORY")
        print("-" * 60)
        
        if not history:
            print("No trades executed yet")
            return
        
        for i, trade in enumerate(history, 1):
            exec_result = trade['execution']
            print(f"\nTrade #{i}")
            print(f"  Symbol: {trade['symbol']}")
            print(f"  Decision: {trade['decision'].get('raw_text', 'N/A')[:150]}...")
            print(f"  Action: {exec_result['action']}")
            print(f"  Result: {exec_result['message']}")
            if exec_result['error']:
                print(f"  Error: {exec_result['error']}")
    
    except Exception as e:
        print(f"Error: {e}")


def manual_decision(system: TradingSystem):
    """Allow user to provide custom decision context."""
    try:
        print("\nManual Decision Mode - Provide custom analysis context")
        print("(This lets you test the order executor with custom inputs)")
        
        symbol = input("Stock symbol: ").strip().upper()
        action = input("Desired action (BUY/SELL/HOLD): ").strip().upper()
        
        if action not in ["BUY", "SELL", "HOLD"]:
            print("Invalid action. Use BUY, SELL, or HOLD")
            return
        
        quantity = float(input("Quantity: ") or "1")
        
        # Create a simulated decision
        decision = {
            "action": action,
            "raw_text": f"Manual decision: {action} {quantity} shares of {symbol}",
        }
        
        from order_executor import OrderExecutor
        executor = system.executor
        
        result = executor.execute_decision(decision, symbol, quantity)
        
        print("\n" + "-" * 60)
        print("EXECUTION RESULT")
        print("-" * 60)
        print(f"Status: {'✓ SUCCESS' if result.success else '✗ FAILED'}")
        print(f"Action: {result.action}")
        print(f"Message: {result.message}")
        if result.order_id:
            print(f"Order ID: {result.order_id}")
        if result.error:
            print(f"Error: {result.error}")
    
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Main interactive loop."""
    print("\n" + "=" * 60)
    print("STOCK BOT TRACKER - INTERACTIVE TRADING")
    print("=" * 60)
    
    # Validate configuration
    if not Config.TRADING212_API_KEY:
        print("\nERROR: TRADING212_API_KEY environment variable is required!")
        print("Set it in Windows PowerShell:")
        print('  $env:TRADING212_API_KEY = "your_api_key"')
        return
    
    try:
        print(f"\nInitializing system...")
        system = TradingSystem(
            api_key=Config.TRADING212_API_KEY,
            ollama_model=Config.OLLAMA_MODEL,
            is_demo=Config.TRADING212_DEMO_MODE,
        )
        print(f"✓ Connected to Trading 212 ({'DEMO' if Config.TRADING212_DEMO_MODE else 'LIVE'} mode)")
        print(f"✓ Ollama model: {Config.OLLAMA_MODEL}")
        
        while True:
            print_menu()
            choice = input("Select option: ").strip()
            
            if choice == "1":
                analyze_and_trade(system)
            elif choice == "2":
                view_account_status(system)
            elif choice == "3":
                view_positions(system)
            elif choice == "4":
                view_orders(system)
            elif choice == "5":
                cancel_order(system)
            elif choice == "6":
                view_trade_history(system)
            elif choice == "7":
                manual_decision(system)
            elif choice == "0":
                print("\nExiting...")
                break
            else:
                print("Invalid option. Please try again.")
    
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
