"""
core.streaming package
Real-time High-Frequency WebSocket & NATS Stream Management.
"""

from core.streaming.websocket_manager import WebSocketStreamManager, get_stream_manager

__all__ = [
    "WebSocketStreamManager",
    "get_stream_manager"
]
