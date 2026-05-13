import os
import time
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


@dataclass
class Account:
    account_id: str
    cash: float
    portfolio_value: float
    free_funds: float


@dataclass
class Position:
    instrument_code: str
    quantity: float
    average_price: float
    current_price: float
    value: float
    profit_loss: float


@dataclass
class Order:
    order_id: str
    instrument_code: str
    side: str
    quantity: float
    price: float
    status: str


class Trading212Client:
    """
    Client for the Trading 212 API v0.
    Supports both live and demo/practice accounts.

    API base URLs:
      Live:  https://live.trading212.com/api/v0
      Demo:  https://demo.trading212.com/api/v0
    """

    LIVE_BASE_URL = "https://live.trading212.com/api/v0"
    DEMO_BASE_URL = "https://demo.trading212.com/api/v0"

    # How many times to retry on rate-limit (HTTP 429) before giving up.
    _MAX_RETRIES = 3
    _RETRY_BACKOFF = 5  # seconds between retries

    def __init__(self, api_key: str, is_demo: bool = True):
        self.api_key = api_key
        self.is_demo = is_demo
        self.base_url = self.DEMO_BASE_URL if is_demo else self.LIVE_BASE_URL
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{endpoint}"

        for attempt in range(self._MAX_RETRIES):
            try:
                if method == "GET":
                    response = requests.get(url, headers=self.headers, params=params, timeout=15)
                elif method == "POST":
                    response = requests.post(url, headers=self.headers, json=data, timeout=15)
                elif method == "DELETE":
                    response = requests.delete(url, headers=self.headers, timeout=15)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                if response.status_code == 429:
                    wait = self._RETRY_BACKOFF * (attempt + 1)
                    if attempt < self._MAX_RETRIES - 1:
                        time.sleep(wait)
                        continue
                    raise Exception(f"Rate limited after {self._MAX_RETRIES} attempts")

                response.raise_for_status()
                return response.json() if response.text.strip() else {}

            except requests.exceptions.RequestException as e:
                if attempt < self._MAX_RETRIES - 1:
                    time.sleep(self._RETRY_BACKOFF)
                    continue
                raise Exception(f"API request failed: {e}")

    @staticmethod
    def _get(data: Dict, *keys: str, default: Any = None) -> Any:
        """Try multiple key names and return the first match."""
        for key in keys:
            if key in data:
                return data[key]
        return default

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_account_info(self) -> Account:
        """
        Fetch account cash details and metadata.

        Cash endpoint returns: blocked, free, invested, pieCash, result, total
        Info endpoint returns: currencyCode, id
        """
        cash_data = self._make_request("GET", "/equity/account/cash")

        # Attempt to get account ID from the info endpoint (non-fatal if it fails).
        account_id = "N/A"
        try:
            info_data = self._make_request("GET", "/equity/account/info")
            account_id = str(self._get(info_data, "id", "accountId", default="N/A"))
        except Exception:
            pass

        free_funds = float(self._get(cash_data, "free", "freeFunds", default=0))
        # "invested" reflects the current market value of holdings.
        portfolio_value = float(self._get(cash_data, "total", "portfolioValue", default=0))
        # "free" is uninvested cash; "blocked" is cash reserved for open orders.
        cash = float(self._get(cash_data, "free", "cash", default=0))

        return Account(
            account_id=account_id,
            cash=cash,
            portfolio_value=portfolio_value,
            free_funds=free_funds,
        )

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_positions(self) -> List[Position]:
        """
        Fetch all open positions from /equity/portfolio.

        Each item may use 'ticker' (API v0) or 'instrumentCode' (legacy).
        P/L field may be 'ppl' (API v0) or 'profitLoss' (legacy).
        """
        data = self._make_request("GET", "/equity/portfolio")
        items = data if isinstance(data, list) else data.get("positions", [])

        positions = []
        for pos in items:
            positions.append(
                Position(
                    instrument_code=self._get(pos, "ticker", "instrumentCode", default=""),
                    quantity=float(self._get(pos, "quantity", default=0)),
                    average_price=float(self._get(pos, "averagePrice", default=0)),
                    current_price=float(self._get(pos, "currentPrice", default=0)),
                    value=float(self._get(pos, "value", default=0)),
                    profit_loss=float(self._get(pos, "ppl", "profitLoss", "fxPpl", default=0)),
                )
            )
        return positions

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def get_orders(self) -> List[Order]:
        """Fetch historical / open orders from /equity/orders."""
        data = self._make_request("GET", "/equity/orders")
        items = data if isinstance(data, list) else data.get("orders", [])

        orders = []
        for order in items:
            orders.append(
                Order(
                    order_id=str(self._get(order, "id", "orderId", default="")),
                    instrument_code=self._get(order, "ticker", "instrumentCode", default=""),
                    side=self._get(order, "side", "type", default=""),
                    quantity=float(self._get(order, "orderedQuantity", "quantity", default=0)),
                    price=float(self._get(order, "fillPrice", "limitPrice", "price", default=0)),
                    status=self._get(order, "status", default=""),
                )
            )
        return orders

    def place_order(
        self,
        symbol: str,
        quantity: float,
        side: OrderSide,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Place a new order.

        Trading 212 API v0 uses separate endpoints per order type:
          Market: POST /equity/orders/market  — body: {ticker, quantity}
          Limit:  POST /equity/orders/limit   — body: {ticker, quantity, limitPrice, timeValidity}
          Stop:   POST /equity/orders/stop    — body: {ticker, quantity, stopPrice, timeValidity}
        """
        if order_type == OrderType.MARKET:
            endpoint = "/equity/orders/market"
            body: Dict[str, Any] = {"ticker": symbol, "quantity": quantity}

        elif order_type == OrderType.LIMIT:
            endpoint = "/equity/orders/limit"
            body = {
                "ticker": symbol,
                "quantity": quantity,
                "limitPrice": limit_price,
                "timeValidity": "DAY",
            }

        elif order_type == OrderType.STOP:
            endpoint = "/equity/orders/stop"
            body = {
                "ticker": symbol,
                "quantity": quantity,
                "stopPrice": stop_price,
                "timeValidity": "DAY",
            }
        else:
            raise ValueError(f"Unsupported order type: {order_type}")

        return self._make_request("POST", endpoint, body)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an open order."""
        return self._make_request("DELETE", f"/equity/orders/{order_id}")

    def get_instrument_details(self, symbol: str) -> Dict[str, Any]:
        """Get details about a specific instrument."""
        return self._make_request("GET", f"/equity/instruments/{symbol}")

    def search_instruments(self, query: str) -> List[Dict[str, Any]]:
        """Search for instruments by name or ticker symbol."""
        data = self._make_request("GET", "/equity/instruments", params={"search": query})
        return data if isinstance(data, list) else data.get("results", [])


def load_api_key_from_env(env_var: str = "TRADING212_API_KEY") -> str:
    """Load the Trading 212 API key from an environment variable."""
    api_key = os.getenv(env_var)
    if not api_key:
        raise ValueError(f"API key not found. Set the {env_var} environment variable.")
    return api_key
