"""
NSE India Official Holiday & Expiry Shift Calendar Engine
=========================================================
Single Source of Truth for National Stock Exchange of India (NSE)
Trading Holidays, Clearing Holidays, and Derivatives Expiry Shifts.

Features:
- Live synchronization with official NSE Holiday Master endpoint
  (https://www.nseindia.com/api/holiday-master?type=trading)
- Automatic local disk caching (data_cache/nse_holidays.json) with auto-refresh
- Comprehensive offline embedded baseline holidays (2024, 2025, 2026, 2027)
  guaranteeing 100% continuous uptime even during network outages
- Dynamic Expiry Shift Resolution: Detects when NIFTY weekly (Thursday),
  SENSEX weekly (Friday), or Equity monthly (Last Tuesday) expiries coincide
  with exchange holidays and automatically prepones to the preceding active trading day
- Precise trading day calculations and countdowns
"""

import os
import json
import time
import calendar
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
import pytz

IST = pytz.timezone("Asia/Kolkata")

# Path to persistent local cache
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_cache")
CACHE_FILE = os.path.join(CACHE_DIR, "nse_holidays.json")


# ==============================================================================
# EMBEDDED OFFICIAL NSE TRADING HOLIDAYS (OFFLINE SHIELD)
# Verified against official NSE circulars & master repository
# ==============================================================================
EMBEDDED_NSE_FO_HOLIDAYS = [
    # 2024
    {"tradingDate": "22-Jan-2024", "weekDay": "Monday", "description": "Special Holiday (Ayodhya Ram Mandir)", "year": 2024},
    {"tradingDate": "26-Jan-2024", "weekDay": "Friday", "description": "Republic Day", "year": 2024},
    {"tradingDate": "08-Mar-2024", "weekDay": "Friday", "description": "Mahashivratri", "year": 2024},
    {"tradingDate": "25-Mar-2024", "weekDay": "Monday", "description": "Holi", "year": 2024},
    {"tradingDate": "29-Mar-2024", "weekDay": "Friday", "description": "Good Friday", "year": 2024},
    {"tradingDate": "11-Apr-2024", "weekDay": "Thursday", "description": "Id-Ul-Fitr (Ramadan Eid)", "year": 2024},
    {"tradingDate": "17-Apr-2024", "weekDay": "Wednesday", "description": "Shri Ram Navami", "year": 2024},
    {"tradingDate": "01-May-2024", "weekDay": "Wednesday", "description": "Maharashtra Day", "year": 2024},
    {"tradingDate": "20-May-2024", "weekDay": "Monday", "description": "General Parliamentary Elections", "year": 2024},
    {"tradingDate": "17-Jun-2024", "weekDay": "Monday", "description": "Bakri Id", "year": 2024},
    {"tradingDate": "17-Jul-2024", "weekDay": "Wednesday", "description": "Muharram", "year": 2024},
    {"tradingDate": "15-Aug-2024", "weekDay": "Thursday", "description": "Independence Day", "year": 2024},
    {"tradingDate": "02-Oct-2024", "weekDay": "Wednesday", "description": "Mahatma Gandhi Jayanti", "year": 2024},
    {"tradingDate": "01-Nov-2024", "weekDay": "Friday", "description": "Diwali Laxmi Pujan (Muhurat Trading)", "year": 2024},
    {"tradingDate": "15-Nov-2024", "weekDay": "Friday", "description": "Prakash Gurpurb Sri Guru Nanak Dev", "year": 2024},
    {"tradingDate": "20-Nov-2024", "weekDay": "Wednesday", "description": "Maharashtra Assembly Election", "year": 2024},
    {"tradingDate": "25-Dec-2024", "weekDay": "Wednesday", "description": "Christmas", "year": 2024},

    # 2025
    {"tradingDate": "26-Jan-2025", "weekDay": "Sunday", "description": "Republic Day", "year": 2025},
    {"tradingDate": "26-Feb-2025", "weekDay": "Wednesday", "description": "Mahashivratri", "year": 2025},
    {"tradingDate": "14-Mar-2025", "weekDay": "Friday", "description": "Holi", "year": 2025},
    {"tradingDate": "31-Mar-2025", "weekDay": "Monday", "description": "Id-Ul-Fitr (Ramadan Eid)", "year": 2025},
    {"tradingDate": "10-Apr-2025", "weekDay": "Thursday", "description": "Shri Mahavir Jayanti", "year": 2025},
    {"tradingDate": "14-Apr-2025", "weekDay": "Monday", "description": "Dr. Baba Saheb Ambedkar Jayanti", "year": 2025},
    {"tradingDate": "18-Apr-2025", "weekDay": "Friday", "description": "Good Friday", "year": 2025},
    {"tradingDate": "01-May-2025", "weekDay": "Thursday", "description": "Maharashtra Day", "year": 2025},
    {"tradingDate": "07-Jun-2025", "weekDay": "Saturday", "description": "Bakri Id", "year": 2025},
    {"tradingDate": "06-Jul-2025", "weekDay": "Sunday", "description": "Muharram", "year": 2025},
    {"tradingDate": "15-Aug-2025", "weekDay": "Friday", "description": "Independence Day", "year": 2025},
    {"tradingDate": "27-Aug-2025", "weekDay": "Wednesday", "description": "Ganesh Chaturthi", "year": 2025},
    {"tradingDate": "02-Oct-2025", "weekDay": "Thursday", "description": "Mahatma Gandhi Jayanti / Dussehra", "year": 2025},
    {"tradingDate": "21-Oct-2025", "weekDay": "Tuesday", "description": "Diwali Laxmi Pujan (Muhurat Trading)", "year": 2025},
    {"tradingDate": "22-Oct-2025", "weekDay": "Wednesday", "description": "Diwali-Balipratipada", "year": 2025},
    {"tradingDate": "05-Nov-2025", "weekDay": "Wednesday", "description": "Prakash Gurpurb Sri Guru Nanak Dev", "year": 2025},
    {"tradingDate": "25-Dec-2025", "weekDay": "Thursday", "description": "Christmas", "year": 2025},

    # 2026 (Live verified from official NSE API)
    {"tradingDate": "15-Jan-2026", "weekDay": "Thursday", "description": "Municipal Corporation Election - Maharashtra", "year": 2026},
    {"tradingDate": "26-Jan-2026", "weekDay": "Monday", "description": "Republic Day", "year": 2026},
    {"tradingDate": "15-Feb-2026", "weekDay": "Sunday", "description": "Mahashivratri", "year": 2026},
    {"tradingDate": "03-Mar-2026", "weekDay": "Tuesday", "description": "Holi", "year": 2026},
    {"tradingDate": "21-Mar-2026", "weekDay": "Saturday", "description": "Id-Ul-Fitr (Ramadan Eid)", "year": 2026},
    {"tradingDate": "26-Mar-2026", "weekDay": "Thursday", "description": "Shri Ram Navami", "year": 2026},
    {"tradingDate": "31-Mar-2026", "weekDay": "Tuesday", "description": "Shri Mahavir Jayanti", "year": 2026},
    {"tradingDate": "03-Apr-2026", "weekDay": "Friday", "description": "Good Friday", "year": 2026},
    {"tradingDate": "14-Apr-2026", "weekDay": "Tuesday", "description": "Dr. Baba Saheb Ambedkar Jayanti", "year": 2026},
    {"tradingDate": "01-May-2026", "weekDay": "Friday", "description": "Maharashtra Day", "year": 2026},
    {"tradingDate": "28-May-2026", "weekDay": "Thursday", "description": "Bakri Id", "year": 2026},
    {"tradingDate": "26-Jun-2026", "weekDay": "Friday", "description": "Muharram", "year": 2026},
    {"tradingDate": "15-Aug-2026", "weekDay": "Saturday", "description": "Independence Day", "year": 2026},
    {"tradingDate": "14-Sep-2026", "weekDay": "Monday", "description": "Ganesh Chaturthi", "year": 2026},
    {"tradingDate": "02-Oct-2026", "weekDay": "Friday", "description": "Mahatma Gandhi Jayanti", "year": 2026},
    {"tradingDate": "20-Oct-2026", "weekDay": "Tuesday", "description": "Dussehra", "year": 2026},
    {"tradingDate": "08-Nov-2026", "weekDay": "Sunday", "description": "Diwali Laxmi Pujan (Muhurat Trading)", "year": 2026},
    {"tradingDate": "10-Nov-2026", "weekDay": "Tuesday", "description": "Diwali-Balipratipada", "year": 2026},
    {"tradingDate": "24-Nov-2026", "weekDay": "Tuesday", "description": "Prakash Gurpurb Sri Guru Nanak Dev", "year": 2026},
    {"tradingDate": "25-Dec-2026", "weekDay": "Friday", "description": "Christmas", "year": 2026},

    # 2027 (Projected Baseline)
    {"tradingDate": "26-Jan-2027", "weekDay": "Tuesday", "description": "Republic Day", "year": 2027},
    {"tradingDate": "05-Mar-2027", "weekDay": "Friday", "description": "Mahashivratri", "year": 2027},
    {"tradingDate": "23-Mar-2027", "weekDay": "Tuesday", "description": "Holi", "year": 2027},
    {"tradingDate": "26-Mar-2027", "weekDay": "Friday", "description": "Good Friday", "year": 2027},
    {"tradingDate": "14-Apr-2027", "weekDay": "Wednesday", "description": "Dr. Baba Saheb Ambedkar Jayanti", "year": 2027},
    {"tradingDate": "01-May-2027", "weekDay": "Saturday", "description": "Maharashtra Day", "year": 2027},
    {"tradingDate": "15-Aug-2027", "weekDay": "Sunday", "description": "Independence Day", "year": 2027},
    {"tradingDate": "02-Oct-2027", "weekDay": "Saturday", "description": "Mahatma Gandhi Jayanti", "year": 2027},
    {"tradingDate": "25-Dec-2027", "weekDay": "Saturday", "description": "Christmas", "year": 2027},
]


class NSECalendar:
    """
    Central Quantitative NSE Holiday & Expiry Shift Intelligence System.
    """
    _instance = None
    _holidays_raw = None
    _holidays_by_date = {}      # 'YYYY-MM-DD' -> holiday dict
    _holiday_strings_set = set() # multiple formats for O(1) matching
    _last_sync_time = 0
    _sync_source = "UNINITIALIZED"
    _sync_error = None
    SYNC_TTL = 86400.0  # 24 hours live cache TTL

    @classmethod
    def get_instance(cls) -> "NSECalendar":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._initialize()
        return cls._instance

    def __init__(self):
        self._initialize()

    def _initialize(self):
        """Loads holidays from disk cache or embedded baseline, then attempts background sync."""
        loaded = self._load_disk_cache()
        if not loaded:
            self._load_embedded()
        
        # Check if cache is stale and needs background refresh
        now = time.time()
        if now - self._last_sync_time > self.SYNC_TTL:
            try:
                self.sync_with_nse(force=False)
            except Exception:
                pass

    def _load_embedded(self):
        """Populates state with comprehensive embedded official holiday dataset."""
        self._holidays_raw = {"FO": EMBEDDED_NSE_FO_HOLIDAYS, "CM": EMBEDDED_NSE_FO_HOLIDAYS}
        self._index_holidays(self._holidays_raw.get("FO", []))
        self._sync_source = "EMBEDDED_OFFLINE_SHIELD"

    def _load_disk_cache(self) -> bool:
        """Loads holiday data from data_cache/nse_holidays.json if present and valid."""
        if not os.path.exists(CACHE_FILE):
            # Check for live file created earlier
            live_candidate = os.path.join(CACHE_DIR, "nse_holidays_live.json")
            if os.path.exists(live_candidate):
                try:
                    with open(live_candidate, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data and isinstance(data, dict):
                        self._holidays_raw = data
                        fo_list = data.get("FO", []) or data.get("CM", [])
                        self._index_holidays(fo_list)
                        self._sync_source = "DISK_CACHE"
                        self._last_sync_time = os.path.getmtime(live_candidate)
                        return True
                except Exception:
                    pass
            return False

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data and isinstance(data, dict):
                self._holidays_raw = data
                fo_list = data.get("FO", []) or data.get("CM", [])
                self._index_holidays(fo_list)
                self._sync_source = "DISK_CACHE"
                self._last_sync_time = os.path.getmtime(CACHE_FILE)
                return True
        except Exception as e:
            self._sync_error = str(e)
        return False

    def _index_holidays(self, holidays_list: List[Dict[str, Any]]):
        """Indexes holiday entries into fast lookup structures."""
        self._holidays_by_date = {}
        self._holiday_strings_set = set()

        # Combine embedded baseline with any live data to ensure multiple years are always covered
        combined = list(EMBEDDED_NSE_FO_HOLIDAYS)
        for h in holidays_list:
            if h not in combined:
                combined.append(h)

        for item in combined:
            raw_date = item.get("tradingDate") or item.get("date") or ""
            raw_date = str(raw_date).strip()
            if not raw_date:
                continue

            dt_parsed = None
            for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%b-%y", "%d/%m/%Y"):
                try:
                    dt_parsed = datetime.strptime(raw_date, fmt)
                    break
                except ValueError:
                    continue

            if dt_parsed:
                iso_str = dt_parsed.strftime("%Y-%m-%d")
                d_mon_y = dt_parsed.strftime("%d-%b-%Y")
                d_mon_yy = dt_parsed.strftime("%d-%b-%y")
                
                # Add to set in all common string variants
                self._holiday_strings_set.add(iso_str)
                self._holiday_strings_set.add(d_mon_y)
                self._holiday_strings_set.add(d_mon_y.upper())
                self._holiday_strings_set.add(d_mon_yy)
                self._holiday_strings_set.add(d_mon_yy.upper())

                entry = {
                    "tradingDate": d_mon_y,
                    "date_iso": iso_str,
                    "datetime": dt_parsed,
                    "date": dt_parsed.date(),
                    "weekDay": item.get("weekDay") or dt_parsed.strftime("%A"),
                    "description": item.get("description", "Exchange Holiday"),
                    "is_muhurat": "muhurat" in str(item.get("description", "")).lower() or "laxmi pujan" in str(item.get("description", "")).lower(),
                    "year": dt_parsed.year
                }
                self._holidays_by_date[iso_str] = entry

    def sync_with_nse(self, force: bool = False) -> Dict[str, Any]:
        """
        Connects directly to www.nseindia.com official holiday master endpoint:
        https://www.nseindia.com/api/holiday-master?type=trading
        Saves downloaded dataset to disk cache and updates live memory index.
        """
        now = time.time()
        if not force and (now - self._last_sync_time < self.SYNC_TTL) and self._sync_source == "LIVE_NSE_API_SYNCED":
            return {
                "success": True,
                "source": self._sync_source,
                "message": "NSE Calendar cache is up-to-date",
                "holiday_count": len(self._holidays_by_date)
            }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
        }

        data = None
        # Try curl_cffi first for TLS impersonation bypass
        try:
            from curl_cffi import requests as c_requests
            sess = c_requests.Session(impersonate="chrome120")
            # Handshake with home page to initialize cookies
            sess.get("https://www.nseindia.com", headers=headers, timeout=8)
            resp = sess.get("https://www.nseindia.com/api/holiday-master?type=trading", headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
        except Exception:
            pass

        # Fallback to standard requests if curl_cffi failed or unavailable
        if not data:
            try:
                import requests
                sess = requests.Session()
                sess.get("https://www.nseindia.com", headers=headers, timeout=8)
                resp = sess.get("https://www.nseindia.com/api/holiday-master?type=trading", headers=headers, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
            except Exception as e:
                self._sync_error = str(e)

        if data and isinstance(data, dict):
            self._holidays_raw = data
            fo_list = data.get("FO", []) or data.get("CM", [])
            self._index_holidays(fo_list)
            self._sync_source = "LIVE_NSE_API_SYNCED"
            self._last_sync_time = now
            self._sync_error = None

            # Persist to disk
            try:
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass

            return {
                "success": True,
                "source": "LIVE_NSE_API_SYNCED",
                "message": "Successfully synchronized live official NSE Trading Calendar",
                "holiday_count": len(self._holidays_by_date),
                "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
            }
        else:
            return {
                "success": False,
                "source": self._sync_source,
                "message": f"Could not reach NSE live endpoint ({self._sync_error or 'Network Timeout'}). Protected by {self._sync_source}.",
                "holiday_count": len(self._holidays_by_date),
                "timestamp": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
            }

    # ==========================================================================
    # CORE CALENDAR QUERY APIS
    # ==========================================================================
    def get_fo_holiday_strings(self) -> List[str]:
        """Returns flat list of holiday date strings recognized by NSEIndiaFetcher."""
        return list(self._holiday_strings_set)

    def get_all_holidays(self, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Returns sorted list of all registered NSE trading holidays."""
        holidays = list(self._holidays_by_date.values())
        if year:
            holidays = [h for h in holidays if h.get("year") == year]
        holidays.sort(key=lambda x: x["datetime"])
        return holidays

    def is_trading_holiday(self, dt_val: Any) -> bool:
        """
        Determines whether a date (datetime, date, or date string) is an official NSE trading holiday.
        """
        if dt_val is None:
            return False

        if isinstance(dt_val, str):
            s = dt_val.strip()
            # Fast set lookup
            if s in self._holiday_strings_set or s.upper() in self._holiday_strings_set:
                return True
            # Attempt parsing
            for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%b-%y"):
                try:
                    dt_val = datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
            if isinstance(dt_val, str):
                return False

        if isinstance(dt_val, datetime):
            iso_key = dt_val.strftime("%Y-%m-%d")
        elif isinstance(dt_val, date):
            iso_key = dt_val.strftime("%Y-%m-%d")
        else:
            return False

        return iso_key in self._holidays_by_date

    def get_holiday_details(self, dt_val: Any) -> Optional[Dict[str, Any]]:
        """Returns holiday metadata dictionary if date is a holiday, else None."""
        if dt_val is None:
            return None
        if isinstance(dt_val, (datetime, date)):
            iso_key = dt_val.strftime("%Y-%m-%d")
        elif isinstance(dt_val, str):
            iso_key = None
            for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%b-%y"):
                try:
                    iso_key = datetime.strptime(dt_val.strip(), fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue
            if not iso_key:
                iso_key = dt_val.strip()
        else:
            return None

        return self._holidays_by_date.get(iso_key)

    def is_market_open_today(self, now_dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Computes real-time market operational status taking into account:
        - Weekends (Saturday / Sunday)
        - Official NSE Trading Holidays
        - Muhurat Trading special sessions
        - Trading hours (09:15 - 15:30 IST)
        """
        if now_dt is None:
            now_dt = datetime.now(IST)
        elif getattr(now_dt, "tzinfo", None) is None:
            now_dt = IST.localize(now_dt)

        weekday = now_dt.weekday() # 0=Mon ... 6=Sun
        is_weekend = (weekday in (5, 6))
        holiday_info = self.get_holiday_details(now_dt)
        is_holiday = (holiday_info is not None)

        time_curr = now_dt.time()
        from datetime import time as dtime
        total_mins = time_curr.hour * 60 + time_curr.minute

        # Case 1: Official NSE Trading Holiday
        if is_holiday:
            is_muhurat = holiday_info.get("is_muhurat", False)
            desc = holiday_info.get("description", "Trading Holiday")
            if is_muhurat:
                # Muhurat trading usually 18:15 to 19:15 in the evening
                if 18 * 60 + 15 <= total_mins <= 19 * 60 + 15:
                    return {
                        "is_open": True,
                        "status": "MUHURAT_SESSION_LIVE",
                        "status_label": "🪔 LIVE MUHURAT TRADING SESSION",
                        "badge_color": "#F59E0B",
                        "is_holiday": True,
                        "is_weekend": is_weekend,
                        "holiday_name": desc,
                        "message": f"Special Diwali Muhurat Trading Active ({desc})"
                    }
                else:
                    return {
                        "is_open": False,
                        "status": "HOLIDAY_MUHURAT_SCHEDULED",
                        "status_label": "🪔 DIWALI MUHURAT (EVENING SESSION)",
                        "badge_color": "#F59E0B",
                        "is_holiday": True,
                        "is_weekend": is_weekend,
                        "holiday_name": desc,
                        "message": f"Market Closed for Regular Hours ({desc}). Special Muhurat Session opens in evening."
                    }
            return {
                "is_open": False,
                "status": "HOLIDAY_CLOSED",
                "status_label": f"🔴 TRADING HOLIDAY • CLOSED",
                "badge_color": "#EF4444",
                "is_holiday": True,
                "is_weekend": is_weekend,
                "holiday_name": desc,
                "message": f"NSE Market Closed today for {desc}."
            }

        # Case 2: Weekend
        if is_weekend:
            return {
                "is_open": False,
                "status": "WEEKEND_CLOSED",
                "status_label": "🛑 WEEKEND • CLOSED",
                "badge_color": "#64748B",
                "is_holiday": False,
                "is_weekend": True,
                "holiday_name": None,
                "message": "Standard Weekend closure (Saturday/Sunday). Next regular session: Monday 09:15 AM."
            }

        # Case 3: Weekday Session progression
        if total_mins < 9 * 60:
            return {
                "is_open": False,
                "status": "PRE_DAWN",
                "status_label": "🌙 PRE-DAWN • OPENS 09:15 AM",
                "badge_color": "#94A3B8",
                "is_holiday": False,
                "is_weekend": False,
                "holiday_name": None,
                "message": "Market opens at 09:15 AM IST (Pre-market auction begins 09:00 AM)."
            }
        elif total_mins < 9 * 60 + 15:
            return {
                "is_open": False,
                "status": "PRE_MARKET",
                "status_label": "🟡 PRE-MARKET • AUCTION (09:00 - 09:15)",
                "badge_color": "#FBBF24",
                "is_holiday": False,
                "is_weekend": False,
                "holiday_name": None,
                "message": "Pre-market discovery auction session. Normal trading commences at 09:15 AM."
            }
        elif total_mins <= 15 * 60 + 30:
            return {
                "is_open": True,
                "status": "LIVE_MARKET",
                "status_label": "🟢 LIVE SESSION • INTRADAY ACTIVE",
                "badge_color": "#10B981",
                "is_holiday": False,
                "is_weekend": False,
                "holiday_name": None,
                "message": "Official NSE Cash & Derivatives trading session active (09:15 - 15:30 IST)."
            }
        else:
            return {
                "is_open": False,
                "status": "POST_MARKET",
                "status_label": "⚪ POST-MARKET • CLOSED",
                "badge_color": "#64748B",
                "is_holiday": False,
                "is_weekend": False,
                "holiday_name": None,
                "message": "Official trading closed for the day. Post-market reporting active."
            }

    def get_next_holiday(self, ref_dt: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Returns the immediately upcoming NSE trading holiday after ref_dt."""
        if ref_dt is None:
            ref_dt = datetime.now(IST)
        elif getattr(ref_dt, "tzinfo", None) is not None:
            ref_dt = ref_dt.astimezone(IST)

        today_d = ref_dt.date()
        upcoming = []
        for h in self.get_all_holidays():
            h_date = h["date"]
            if h_date >= today_d:
                days_left = (h_date - today_d).days
                h_copy = h.copy()
                h_copy["days_left"] = days_left
                h_copy["is_today"] = (days_left == 0)
                upcoming.append(h_copy)

        upcoming.sort(key=lambda x: x["date"])
        return upcoming[0] if upcoming else None

    def get_upcoming_holidays(self, limit: int = 5, ref_dt: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Returns list of next N upcoming holidays."""
        if ref_dt is None:
            ref_dt = datetime.now(IST)
        today_d = ref_dt.date()
        upcoming = []
        for h in self.get_all_holidays():
            if h["date"] >= today_d:
                days_left = (h["date"] - today_d).days
                h_copy = h.copy()
                h_copy["days_left"] = days_left
                h_copy["is_today"] = (days_left == 0)
                upcoming.append(h_copy)
        upcoming.sort(key=lambda x: x["date"])
        return upcoming[:limit]

    def get_previous_trading_day(self, ref_dt: Optional[datetime] = None) -> datetime:
        """Finds the most recent active trading day preceding ref_dt (skipping weekends & holidays)."""
        if ref_dt is None:
            ref_dt = datetime.now(IST)
        cand = ref_dt - timedelta(days=1)
        while cand.weekday() in (5, 6) or self.is_trading_holiday(cand):
            cand -= timedelta(days=1)
        return cand

    def get_next_trading_day(self, ref_dt: Optional[datetime] = None) -> datetime:
        """Finds the next active trading day following ref_dt (skipping weekends & holidays)."""
        if ref_dt is None:
            ref_dt = datetime.now(IST)
        cand = ref_dt + timedelta(days=1)
        while cand.weekday() in (5, 6) or self.is_trading_holiday(cand):
            cand += timedelta(days=1)
        return cand

    def get_trading_days_between(self, start_dt: datetime, end_dt: datetime) -> Tuple[int, List[datetime]]:
        """
        Calculates exact count of active trading days between two dates,
        excluding weekends (Saturday/Sunday) and all official NSE holidays.
        """
        if getattr(start_dt, "tzinfo", None) is not None:
            start_dt = start_dt.replace(tzinfo=None)
        if getattr(end_dt, "tzinfo", None) is not None:
            end_dt = end_dt.replace(tzinfo=None)

        cur = start_dt
        days = []
        while cur.date() <= end_dt.date():
            if cur.weekday() < 5 and not self.is_trading_holiday(cur):
                days.append(cur)
            cur += timedelta(days=1)
        return len(days), days

    # ==========================================================================
    # EXPIRY SHIFT INTELLIGENCE (NSE / BSE MANDATE)
    # ==========================================================================
    def resolve_expiry_shift(
        self,
        nominal_dt: datetime,
        symbol: str = "NIFTY"
    ) -> Dict[str, Any]:
        """
        Takes nominal contract expiry date (e.g. Tuesday for NIFTY, Thursday for SENSEX,
        or Last Tuesday for Equities).
        Checks if that date is an NSE trading holiday or weekend.
        If it IS a holiday:
        Automatically shifts backward to the preceding active trading day (SEBI / NSE Rule).
        Returns full audit trail of the shift.
        """
        nominal_clean = datetime(nominal_dt.year, nominal_dt.month, nominal_dt.day)
        actual_dt = nominal_clean
        holiday_triggers = []

        is_shifted = False
        while actual_dt.weekday() in (5, 6) or self.is_trading_holiday(actual_dt):
            is_shifted = True
            h_info = self.get_holiday_details(actual_dt)
            if h_info:
                holiday_triggers.append(f"{actual_dt.strftime('%d-%b-%Y')} ({h_info.get('description', 'Holiday')})")
            elif actual_dt.weekday() in (5, 6):
                holiday_triggers.append(f"{actual_dt.strftime('%d-%b-%Y')} (Weekend)")
            actual_dt -= timedelta(days=1)

        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        shift_days = (nominal_clean - actual_dt).days

        if is_shifted:
            shift_reason = f"Preponed by {shift_days}d from {nominal_clean.strftime('%a, %d-%b-%Y')} to {actual_dt.strftime('%a, %d-%b-%Y')} due to exchange holiday: {', '.join(holiday_triggers)}"
            badge_label = f"⚠️ SHIFTED EXPIRY ({actual_dt.strftime('%d-%b-%Y').upper()})"
        else:
            shift_reason = "Standard scheduled expiry on regular active trading day (No holiday collision)."
            badge_label = f"🟢 STANDARD EXPIRY ({actual_dt.strftime('%d-%b-%Y').upper()})"

        return {
            "symbol": symbol.upper(),
            "nominal_dt": nominal_clean,
            "nominal_str": nominal_clean.strftime("%d-%b-%Y").upper(),
            "nominal_weekday": weekday_names[nominal_clean.weekday()],
            "actual_dt": actual_dt,
            "actual_str": actual_dt.strftime("%d-%b-%Y").upper(),
            "actual_weekday": weekday_names[actual_dt.weekday()],
            "is_shifted": is_shifted,
            "shift_days": shift_days,
            "holiday_triggers": holiday_triggers,
            "shift_reason": shift_reason,
            "badge_label": badge_label
        }

    def get_weekly_expiry(
        self,
        today_dt: Optional[datetime] = None,
        target_weekday: int = 3,
        symbol: str = "NIFTY"
    ) -> Dict[str, Any]:
        """
        Determines current week's expiry date for index derivatives:
        - target_weekday: 3 for Thursday (NIFTY 50), 4 for Friday (BSE SENSEX).
        - If today is past 15:30 on expiry day, rolls to next week.
        - Checks against NSE Calendar and prepones if holiday!
        """
        if today_dt is None:
            today_dt = datetime.now(IST)
        if getattr(today_dt, "tzinfo", None) is not None:
            today_dt = today_dt.astimezone(IST).replace(tzinfo=None)

        from datetime import time as dtime
        cur_weekday = today_dt.weekday()
        if cur_weekday < target_weekday:
            days_ahead = target_weekday - cur_weekday
        elif cur_weekday == target_weekday:
            if today_dt.time() <= dtime(15, 30):
                days_ahead = 0
            else:
                days_ahead = 7
        else:
            days_ahead = 7 - (cur_weekday - target_weekday)

        nominal_cand = today_dt + timedelta(days=days_ahead)
        return self.resolve_expiry_shift(nominal_cand, symbol=symbol)

    def get_monthly_stock_expiry(
        self,
        year: int,
        month: int,
        symbol: str = "RELIANCE"
    ) -> Dict[str, Any]:
        """
        Determines official NSE Monthly Stock Derivatives Expiry date (Last Tuesday of Month).
        If Last Tuesday is a trading holiday, rolls back to preceding active trading day.
        """
        last_d = calendar.monthrange(year, month)[1]
        tuesdays = [
            datetime(year, month, d)
            for d in range(1, last_d + 1)
            if datetime(year, month, d).weekday() == 1
        ]
        nominal_cand = tuesdays[-1] if tuesdays else datetime(year, month, 27)
        return self.resolve_expiry_shift(nominal_cand, symbol=symbol)

    def scan_all_expiry_shifts_for_year(self, year: int = 2026) -> Dict[str, List[Dict[str, Any]]]:
        """
        Audits all weekly index expiries and monthly stock expiries for a given year,
        identifying every single shifted expiry event!
        Returns dictionary with 'NIFTY', 'SENSEX', and 'EQUITIES_MONTHLY'.
        """
        results = {
            "NIFTY_WEEKLY_SHIFTS": [],
            "SENSEX_WEEKLY_SHIFTS": [],
            "MONTHLY_STOCK_SHIFTS": []
        }

        # 1. NIFTY Weekly Expiries (Nominal Thursday)
        start_d = datetime(year, 1, 1)
        cur_d = start_d
        while cur_d.year == year:
            if cur_d.weekday() == 3: # Thursday
                shift_audit = self.resolve_expiry_shift(cur_d, symbol="NIFTY")
                if shift_audit["is_shifted"]:
                    results["NIFTY_WEEKLY_SHIFTS"].append(shift_audit)
            cur_d += timedelta(days=1)

        # 2. SENSEX Weekly Expiries (Nominal Friday)
        cur_d = start_d
        while cur_d.year == year:
            if cur_d.weekday() == 4: # Friday
                shift_audit = self.resolve_expiry_shift(cur_d, symbol="SENSEX")
                if shift_audit["is_shifted"]:
                    results["SENSEX_WEEKLY_SHIFTS"].append(shift_audit)
            cur_d += timedelta(days=1)

        # 3. Monthly Stock Expiries (Nominal Last Tuesday)
        for m in range(1, 13):
            shift_audit = self.get_monthly_stock_expiry(year, m, symbol="STOCKS")
            if shift_audit["is_shifted"]:
                results["MONTHLY_STOCK_SHIFTS"].append(shift_audit)

        return results

    def get_calendar_status_telemetry(self) -> Dict[str, Any]:
        """
        Returns comprehensive UI telemetry for dashboard headers and calendar badges.
        """
        now = datetime.now(IST)
        market_status = self.is_market_open_today(now)
        next_holiday = self.get_next_holiday(now)
        nifty_exp = self.get_weekly_expiry(now, target_weekday=3, symbol="NIFTY")
        sensex_exp = self.get_weekly_expiry(now, target_weekday=4, symbol="SENSEX")

        return {
            "calendar_linked": True,
            "sync_source": self._sync_source,
            "sync_error": self._sync_error,
            "total_holidays": len(self._holidays_by_date),
            "today_iso": now.strftime("%Y-%m-%d"),
            "today_str": now.strftime("%d-%b-%Y"),
            "today_weekday": now.strftime("%A"),
            "market_status": market_status,
            "next_holiday": next_holiday,
            "active_nifty_expiry": nifty_exp,
            "active_sensex_expiry": sensex_exp,
            "is_nifty_expiry_shifted": nifty_exp["is_shifted"],
            "is_sensex_expiry_shifted": sensex_exp["is_shifted"],
        }


# Global singleton instance for immediate project-wide access
nse_calendar = NSECalendar.get_instance()
