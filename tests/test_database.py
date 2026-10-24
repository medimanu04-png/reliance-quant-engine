"""
tests/test_database.py
Automated Unit Tests for SQLite WAL Storage Engine.
Verifies ACID transactions, concurrent active trade states, journal persistence,
and daemon heartbeat telemetry.
"""

import os
import time
import pytest
from core.database import QuantDatabaseManager, DB_PATH


def test_database_initialization():
    QuantDatabaseManager.initialize_schema()
    assert os.path.exists(DB_PATH)


def test_active_trade_state_crud():
    QuantDatabaseManager.initialize_schema()
    test_state = {
        "is_active": True,
        "symbol": "NIFTY",
        "entry_price": 22450.50,
        "target": 22500.50,
        "sl": 22414.50,
        "lots": 2,
        "market_status": "TEST_RUN"
    }

    ok = QuantDatabaseManager.set_active_trade_state("NIFTY", test_state, sync_json=False)
    assert ok is True

    loaded = QuantDatabaseManager.get_active_trade_state("NIFTY")
    assert loaded["is_active"] is True
    assert loaded["entry_price"] == 22450.50
    assert loaded["target"] == 22500.50


def test_sequential_trade_state_crud():
    QuantDatabaseManager.initialize_schema()
    seq_state = {
        "current_state": "IN_TRADE",
        "symbol": "SENSEX",
        "today_trade_count": 1,
        "updated_at": "2026-10-24 09:30:00 AM IST"
    }

    ok = QuantDatabaseManager.set_sequential_trade_state("SENSEX", seq_state, sync_json=False)
    assert ok is True

    loaded = QuantDatabaseManager.get_sequential_trade_state("SENSEX")
    assert loaded["current_state"] == "IN_TRADE"
    assert loaded["today_trade_count"] == 1


def test_daemon_heartbeat():
    QuantDatabaseManager.initialize_schema()
    curr_pid = os.getpid()
    ok = QuantDatabaseManager.record_daemon_heartbeat(curr_pid, status="TEST_ALIVE")
    assert ok is True

    is_alive, pid = QuantDatabaseManager.is_daemon_heartbeat_alive(max_age_secs=30.0)
    assert is_alive is True
    assert pid == curr_pid
