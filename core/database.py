"""
core/database.py
Institutional SQLite Storage & Concurrency Engine (WAL Mode).
Eliminates JSON file concurrency conflicts and Windows PermissionErrors between
Streamlit web UI, background alert daemons, and automated trading runners.
"""

import os
import time
import json
import sqlite3
import threading
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("QuantDatabase")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "quant_engine.db")

_local = threading.local()


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Returns a thread-local SQLite connection with WAL mode and generous busy timeout."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(db_path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Enable Write-Ahead Logging (WAL) for high concurrency (readers do not block writers)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        _local.conn = conn
    return conn


class QuantDatabaseManager:
    """
    ACID Transactional Storage Manager.
    Safely stores and synchronizes active trade states, sequential trade states,
    daily signals, shadow signals, trade journals, and daemon heartbeats.
    """

    _initialized = False
    _init_lock = threading.Lock()

    @classmethod
    def initialize_schema(cls, db_path: str = DB_PATH) -> None:
        """Initializes tables and performs one-time data migration from JSON files."""
        with cls._init_lock:
            if cls._initialized:
                return
            conn = get_db_connection(db_path)
            with conn:
                conn.executescript("""
                CREATE TABLE IF NOT EXISTS active_trade_state (
                    symbol TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sequential_trade_state (
                    symbol TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS daily_signals_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    date_str TEXT,
                    signal_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_signals_symbol_ts ON daily_signals_log(symbol, timestamp);

                CREATE TABLE IF NOT EXISTS shadow_signals_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    date_str TEXT,
                    signal_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_shadow_symbol_ts ON shadow_signals_log(symbol, timestamp);

                CREATE TABLE IF NOT EXISTS daily_trade_journal (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    journal_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS daemon_heartbeat (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    pid INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    status TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS key_value_store (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                """)
            cls._initialized = True
            cls._migrate_legacy_json_files(conn)

    @classmethod
    def _migrate_legacy_json_files(cls, conn: sqlite3.Connection) -> None:
        """Automatically imports existing legacy JSON files if tables are empty."""
        try:
            # 1. Active trade states (NIFTY, SENSEX)
            for sym in ["NIFTY", "SENSEX"]:
                json_path = os.path.join(BASE_DIR, f"active_trade_state_{sym}.json")
                if os.path.exists(json_path):
                    cur = conn.execute("SELECT COUNT(*) FROM active_trade_state WHERE symbol = ?", (sym,))
                    if cur.fetchone()[0] == 0:
                        try:
                            with open(json_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            conn.execute(
                                "INSERT OR REPLACE INTO active_trade_state (symbol, state_json, updated_at) VALUES (?, ?, ?)",
                                (sym, json.dumps(data), time.time())
                            )
                        except Exception as e:
                            logger.warning(f"Failed migrating {json_path}: {e}")

            # 2. Sequential trade states (NIFTY, SENSEX)
            for sym in ["NIFTY", "SENSEX"]:
                json_path = os.path.join(BASE_DIR, f"sequential_trade_state_{sym}.json")
                if os.path.exists(json_path):
                    cur = conn.execute("SELECT COUNT(*) FROM sequential_trade_state WHERE symbol = ?", (sym,))
                    if cur.fetchone()[0] == 0:
                        try:
                            with open(json_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            conn.execute(
                                "INSERT OR REPLACE INTO sequential_trade_state (symbol, state_json, updated_at) VALUES (?, ?, ?)",
                                (sym, json.dumps(data), time.time())
                            )
                        except Exception as e:
                            logger.warning(f"Failed migrating {json_path}: {e}")

            # 3. Daily trade journal
            journal_path = os.path.join(BASE_DIR, "daily_trade_journal.json")
            if os.path.exists(journal_path):
                cur = conn.execute("SELECT COUNT(*) FROM daily_trade_journal WHERE id = 1")
                if cur.fetchone()[0] == 0:
                    try:
                        with open(journal_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        conn.execute(
                            "INSERT OR REPLACE INTO daily_trade_journal (id, journal_json, updated_at) VALUES (1, ?, ?)",
                            (json.dumps(data), time.time())
                        )
                    except Exception as e:
                        logger.warning(f"Failed migrating {journal_path}: {e}")

            # 4. Daily signals log
            signals_path = os.path.join(BASE_DIR, "daily_signals_log.json")
            if os.path.exists(signals_path):
                cur = conn.execute("SELECT COUNT(*) FROM daily_signals_log")
                if cur.fetchone()[0] == 0:
                    try:
                        with open(signals_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, list):
                            for sig in data:
                                sym = sig.get("symbol", sig.get("scrip", "NIFTY"))
                                ts = float(sig.get("timestamp", time.time()))
                                dt = sig.get("date", sig.get("time", ""))
                                conn.execute(
                                    "INSERT INTO daily_signals_log (symbol, timestamp, date_str, signal_json) VALUES (?, ?, ?, ?)",
                                    (sym, ts, dt, json.dumps(sig))
                                )
                    except Exception as e:
                        logger.warning(f"Failed migrating {signals_path}: {e}")

            conn.commit()
        except Exception as e:
            logger.error(f"Error during legacy JSON migration: {e}")

    # =========================================================================
    # ACTIVE TRADE STATE CRUD
    # =========================================================================
    @classmethod
    def get_active_trade_state(cls, symbol: str) -> Dict[str, Any]:
        """Fetches active trade state for given symbol."""
        cls.initialize_schema()
        conn = get_db_connection()
        norm_sym = symbol.upper().replace(" ", "")
        row = conn.execute("SELECT state_json FROM active_trade_state WHERE symbol = ?", (norm_sym,)).fetchone()
        if row and row["state_json"]:
            try:
                return json.loads(row["state_json"])
            except Exception:
                pass
        return {}

    @classmethod
    def set_active_trade_state(cls, symbol: str, state: Dict[str, Any], sync_json: bool = True) -> bool:
        """Saves active trade state with immediate commit and optional legacy JSON mirror."""
        cls.initialize_schema()
        conn = get_db_connection()
        norm_sym = symbol.upper().replace(" ", "")
        raw_json = json.dumps(state, indent=2)
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO active_trade_state (symbol, state_json, updated_at) VALUES (?, ?, ?)",
                    (norm_sym, raw_json, time.time())
                )
            if sync_json:
                try:
                    fpath = os.path.join(BASE_DIR, f"active_trade_state_{norm_sym}.json")
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(raw_json)
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.error(f"Error saving active trade state for {symbol}: {e}")
            return False

    # =========================================================================
    # SEQUENTIAL TRADE STATE CRUD
    # =========================================================================
    @classmethod
    def get_sequential_trade_state(cls, symbol: str) -> Dict[str, Any]:
        """Fetches sequential trade state for symbol."""
        cls.initialize_schema()
        conn = get_db_connection()
        norm_sym = symbol.upper().replace(" ", "")
        row = conn.execute("SELECT state_json FROM sequential_trade_state WHERE symbol = ?", (norm_sym,)).fetchone()
        if row and row["state_json"]:
            try:
                return json.loads(row["state_json"])
            except Exception:
                pass
        return {}

    @classmethod
    def set_sequential_trade_state(cls, symbol: str, state: Dict[str, Any], sync_json: bool = True) -> bool:
        """Saves sequential trade state with optional legacy JSON mirror."""
        cls.initialize_schema()
        conn = get_db_connection()
        norm_sym = symbol.upper().replace(" ", "")
        raw_json = json.dumps(state, indent=2)
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO sequential_trade_state (symbol, state_json, updated_at) VALUES (?, ?, ?)",
                    (norm_sym, raw_json, time.time())
                )
            if sync_json:
                try:
                    fpath = os.path.join(BASE_DIR, f"sequential_trade_state_{norm_sym}.json")
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(raw_json)
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.error(f"Error saving sequential trade state for {symbol}: {e}")
            return False

    # =========================================================================
    # DAILY SIGNALS & SHADOW SIGNALS LOGGING
    # =========================================================================
    @classmethod
    def log_daily_signal(cls, symbol: str, signal_data: Dict[str, Any]) -> bool:
        """Logs an evaluated quantitative trading signal."""
        cls.initialize_schema()
        conn = get_db_connection()
        norm_sym = symbol.upper().replace(" ", "")
        ts = float(signal_data.get("timestamp", time.time()))
        dt_str = signal_data.get("date_str", signal_data.get("timestamp_str", ""))
        try:
            with conn:
                conn.execute(
                    "INSERT INTO daily_signals_log (symbol, timestamp, date_str, signal_json) VALUES (?, ?, ?, ?)",
                    (norm_sym, ts, dt_str, json.dumps(signal_data))
                )
            return True
        except Exception as e:
            logger.error(f"Error logging daily signal: {e}")
            return False

    @classmethod
    def get_recent_daily_signals(cls, symbol: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent evaluated signals."""
        cls.initialize_schema()
        conn = get_db_connection()
        if symbol:
            norm_sym = symbol.upper().replace(" ", "")
            rows = conn.execute(
                "SELECT signal_json FROM daily_signals_log WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
                (norm_sym, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT signal_json FROM daily_signals_log ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        signals = []
        for r in rows:
            try:
                signals.append(json.loads(r["signal_json"]))
            except Exception:
                pass
        return signals

    @classmethod
    def log_shadow_signal(cls, symbol: str, signal_data: Dict[str, Any]) -> bool:
        """Logs a shadow (hypothetical) trade tracking signal."""
        cls.initialize_schema()
        conn = get_db_connection()
        norm_sym = symbol.upper().replace(" ", "")
        ts = float(signal_data.get("timestamp", time.time()))
        dt_str = signal_data.get("date_str", signal_data.get("timestamp_str", ""))
        try:
            with conn:
                conn.execute(
                    "INSERT INTO shadow_signals_log (symbol, timestamp, date_str, signal_json) VALUES (?, ?, ?, ?)",
                    (norm_sym, ts, dt_str, json.dumps(signal_data))
                )
            return True
        except Exception as e:
            logger.error(f"Error logging shadow signal: {e}")
            return False

    @classmethod
    def get_recent_shadow_signals(cls, symbol: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent shadow signals."""
        cls.initialize_schema()
        conn = get_db_connection()
        if symbol:
            norm_sym = symbol.upper().replace(" ", "")
            rows = conn.execute(
                "SELECT signal_json FROM shadow_signals_log WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
                (norm_sym, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT signal_json FROM shadow_signals_log ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        signals = []
        for r in rows:
            try:
                signals.append(json.loads(r["signal_json"]))
            except Exception:
                pass
        return signals

    # =========================================================================
    # DAILY TRADE JOURNAL CRUD
    # =========================================================================
    @classmethod
    def get_trade_journal(cls) -> Dict[str, Any]:
        """Fetches complete multi-day trade journal."""
        cls.initialize_schema()
        conn = get_db_connection()
        row = conn.execute("SELECT journal_json FROM daily_trade_journal WHERE id = 1").fetchone()
        if row and row["journal_json"]:
            try:
                return json.loads(row["journal_json"])
            except Exception:
                pass
        return {}

    @classmethod
    def save_trade_journal(cls, journal_data: Dict[str, Any], sync_json: bool = True) -> bool:
        """Saves trade journal and mirrors to daily_trade_journal.json."""
        cls.initialize_schema()
        conn = get_db_connection()
        raw_json = json.dumps(journal_data, indent=2)
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO daily_trade_journal (id, journal_json, updated_at) VALUES (1, ?, ?)",
                    (raw_json, time.time())
                )
            if sync_json:
                try:
                    fpath = os.path.join(BASE_DIR, "daily_trade_journal.json")
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(raw_json)
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.error(f"Error saving trade journal: {e}")
            return False

    # =========================================================================
    # DAEMON HEARTBEAT TELEMETRY
    # =========================================================================
    @classmethod
    def record_daemon_heartbeat(cls, pid: int, status: str = "ALIVE") -> bool:
        """Records daemon process heartbeat timestamp."""
        cls.initialize_schema()
        conn = get_db_connection()
        now_ts = time.time()
        last_seen = time.strftime("%Y-%m-%d %I:%M:%S %p IST")
        try:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO daemon_heartbeat (id, pid, timestamp, status, last_seen) VALUES (1, ?, ?, ?, ?)",
                    (pid, now_ts, status, last_seen)
                )
            # Sync to daemon_heartbeat.json
            try:
                hb_path = os.path.join(BASE_DIR, "daemon_heartbeat.json")
                with open(hb_path, "w", encoding="utf-8") as f:
                    json.dump({"pid": pid, "timestamp": now_ts, "status": status, "last_seen": last_seen}, f, indent=2)
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"Error recording daemon heartbeat: {e}")
            return False

    @classmethod
    def is_daemon_heartbeat_alive(cls, max_age_secs: float = 45.0) -> Tuple[bool, Optional[int]]:
        """Checks if daemon heartbeat in SQLite is fresh and PID is running."""
        cls.initialize_schema()
        conn = get_db_connection()
        row = conn.execute("SELECT pid, timestamp, status FROM daemon_heartbeat WHERE id = 1").fetchone()
        if not row:
            return False, None
        age = time.time() - float(row["timestamp"])
        pid = int(row["pid"])
        if age <= max_age_secs and cls._is_pid_alive(pid):
            return True, pid
        return False, pid

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        """Validates if given PID is alive on the OS."""
        if pid <= 0:
            return False
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, int(pid))
            if h:
                kernel32.CloseHandle(h)
                return True
            return False
        except Exception:
            try:
                os.kill(pid, 0)
                return True
            except (OSError, PermissionError):
                return False
