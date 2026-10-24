"""
core.brokers.groww_broker
Groww Broker Gateway Implementation for the Manoj Quant Engine.
Leverages the user's verified Groww API Subscription, JWT access tokens, and TOTP automation.
"""

import logging
from typing import Dict, Any, List, Optional
from core.brokers.base_broker import BaseBrokerGateway

logger = logging.getLogger(__name__)


class GrowwBrokerGateway(BaseBrokerGateway):
    """
    Production-grade Groww Broker Gateway adapter.
    Implements BaseBrokerGateway interface using GrowwMarketFeed and GrowwAPI SDK.
    """

    def __init__(self):
        self._feed = None
        self._name = "GROWW"

    def _get_feed(self):
        if self._feed is None:
            from groww_market_feed import GrowwMarketFeed
            self._feed = GrowwMarketFeed.get_instance()
        return self._feed

    def get_broker_name(self) -> str:
        return self._name

    def connect(self) -> bool:
        feed = self._get_feed()
        return getattr(feed, "is_connected", False)

    def disconnect(self) -> bool:
        feed = self._get_feed()
        if hasattr(feed, "disconnect"):
            feed.disconnect()
        return True

    @property
    def is_connected(self) -> bool:
        feed = self._get_feed()
        return getattr(feed, "is_connected", False)

    def get_profile(self) -> Dict[str, Any]:
        feed = self._get_feed()
        prof = getattr(feed, "user_profile", None)
        if callable(prof):
            return prof() or {}
        return prof or {}

    def get_wallet(self) -> Dict[str, Any]:
        feed = self._get_feed()
        if hasattr(feed, "get_wallet_balance"):
            return feed.get_wallet_balance() or {}
        return {}

    def get_ltp(self, symbol: str, exchange: str = "NSE", segment: str = "CASH") -> float:
        feed = self._get_feed()
        spot = feed.get_live_spot_data(symbol) if hasattr(feed, "get_live_spot_data") else feed.get_spot_price(symbol)
        if spot and isinstance(spot, dict):
            return float(spot.get("price") or spot.get("ltp") or 0.0)
        return float(spot or 0.0)

    def get_option_chain(self, underlying_symbol: str, expiry_date: str = "") -> Dict[str, Any]:
        feed = self._get_feed()
        if hasattr(feed, "get_live_option_chain"):
            return feed.get_live_option_chain(underlying_symbol) or {}
        return {}

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
        feed = self._get_feed()
        return feed.place_broker_order(
            trading_symbol=trading_symbol,
            quantity=quantity,
            transaction_type=transaction_type,
            order_type=order_type,
            price=price,
            trigger_price=trigger_price,
            product=product,
            exchange=exchange,
            segment=segment,
            validity=validity
        )

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        feed = self._get_feed()
        return feed.cancel_broker_order(order_id)

    def get_positions(self) -> List[Dict[str, Any]]:
        feed = self._get_feed()
        if hasattr(feed, "get_live_positions"):
            return feed.get_live_positions() or []
        return []

    def get_orders(self) -> List[Dict[str, Any]]:
        feed = self._get_feed()
        if hasattr(feed, "get_executed_trades_today"):
            return feed.get_executed_trades_today() or []
        if hasattr(feed, "get_today_orders"):
            return feed.get_today_orders() or []
        return []

    def get_underlying_feed_instance(self):
        """Returns direct GrowwMarketFeed singleton for legacy component access."""
        return self._get_feed()
