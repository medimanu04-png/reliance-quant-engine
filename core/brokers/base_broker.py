"""
core.brokers.base_broker
Abstract Broker Gateway Interface for the Manoj Quant Engine.
Standardizes connectivity, telemetry, market quotes, order routing, and positions across all supported brokers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseBrokerGateway(ABC):
    """Abstract Base Class defining the Institutional Broker Gateway contract."""

    @abstractmethod
    def get_broker_name(self) -> str:
        """Returns uppercase broker identifier (e.g. 'GROWW', 'ZERODHA', 'DHAN')."""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """Establishes authenticated broker session and verifies permissions."""
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """Terminates active broker session."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Returns True if verified broker session is active."""
        pass

    @abstractmethod
    def get_profile(self) -> Dict[str, Any]:
        """Returns verified account profile (UCC, enabled segments, client ID)."""
        pass

    @abstractmethod
    def get_wallet(self) -> Dict[str, Any]:
        """Returns available trading capital, utilized margin, and collateral."""
        pass

    @abstractmethod
    def get_ltp(self, symbol: str, exchange: str = "NSE", segment: str = "CASH") -> float:
        """Retrieves real-time Last Traded Price for an instrument."""
        pass

    @abstractmethod
    def get_option_chain(self, underlying_symbol: str, expiry_date: str) -> Dict[str, Any]:
        """Retrieves complete option chain with Greeks, OI, and IV for specified expiry."""
        pass

    @abstractmethod
    def place_order(
        self,
        trading_symbol: str,
        quantity: int,
        transaction_type: str,
        order_type: str = "LIMIT",
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        product: str = "NRML",
        exchange: str = "AUTO",
        segment: str = "FNO",
        validity: str = "DAY"
    ) -> Dict[str, Any]:
        """Places live order on exchange with institutional tick rounding and risk gates."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancels active pending order."""
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Retrieves active intraday and overnight portfolio positions."""
        pass

    @abstractmethod
    def get_orders(self) -> List[Dict[str, Any]]:
        """Retrieves day's complete order book with execution timestamps and statuses."""
        pass
