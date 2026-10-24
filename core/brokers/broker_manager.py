"""
core.brokers.broker_manager
Broker Gateway Manager & Registry.
Provides multi-broker factory, dynamic gateway switching, and unified broker resolution.
Defaults to 'GROWW' using the user's active Groww API subscription.
"""

import logging
from typing import Dict, List, Optional
from core.brokers.base_broker import BaseBrokerGateway
from core.brokers.groww_broker import GrowwBrokerGateway

logger = logging.getLogger(__name__)


class BrokerManager:
    """Singleton registry and manager for trading broker gateways."""
    _instance: Optional["BrokerManager"] = None
    _gateways: Dict[str, BaseBrokerGateway] = {}
    _active_broker_name: str = "GROWW"

    def __init__(self):
        # Register default Groww Broker Gateway
        self.register_gateway("GROWW", GrowwBrokerGateway())

    @classmethod
    def get_instance(cls) -> "BrokerManager":
        if cls._instance is None:
            cls._instance = BrokerManager()
        return cls._instance

    def register_gateway(self, name: str, gateway: BaseBrokerGateway):
        """Registers a broker gateway implementation."""
        key = str(name).strip().upper()
        self._gateways[key] = gateway
        logger.info(f"[BrokerManager] Registered broker gateway: {key}")

    def set_active_broker(self, name: str) -> bool:
        """Switches the active broker for order routing."""
        key = str(name).strip().upper()
        if key in self._gateways:
            self._active_broker_name = key
            logger.info(f"[BrokerManager] Switched active broker to: {key}")
            return True
        logger.warning(f"[BrokerManager] Unknown broker '{key}'. Available: {list(self._gateways.keys())}")
        return False

    def get_active_broker_name(self) -> str:
        """Returns uppercase name of currently active broker."""
        return self._active_broker_name

    def get_active_broker(self) -> BaseBrokerGateway:
        """Returns the currently active BaseBrokerGateway implementation."""
        if self._active_broker_name not in self._gateways:
            # Fallback to Groww
            self._gateways["GROWW"] = GrowwBrokerGateway()
            self._active_broker_name = "GROWW"
        return self._gateways[self._active_broker_name]

    def list_available_brokers(self) -> List[str]:
        """Returns list of registered broker names."""
        return list(self._gateways.keys())

    def get_broker(self, name: str) -> Optional[BaseBrokerGateway]:
        """Retrieves a specific registered broker gateway."""
        return self._gateways.get(str(name).strip().upper())


# Convenience module-level getter
def get_active_broker() -> BaseBrokerGateway:
    """Convenience shortcut to access active broker gateway directly."""
    return BrokerManager.get_instance().get_active_broker()
