"""
MT5 Feed & Market Data Interface for Risk Management Dashboard.
Handles:
1. MT5 Terminal initialization & account detection
2. Live Market Watch symbols & specifications (volume min/max/step, contract size, tick value)
3. Dynamic D1 ADR(14) & ATR(14) in pips calculation with 15-minute in-memory TTL cache
4. Account Trade History extraction (closed deals, PnL list)
5. Fast sub-second tick polling (<5ms latency) decoupled from daily volatility calculations
6. Thread-safe execution for MT5 C-extension calls
7. Robust fallback/mock mode when MT5 terminal is offline
"""

from datetime import datetime, timezone, timedelta
import logging
import threading
import time
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RiskFeed")


# Fallback / Mock Data for offline testing
MOCK_SYMBOLS_SPECS = [
    {
        "symbol": "EURUSD", "category": "Forex Majors", "bid": 1.08500, "ask": 1.08512, "digits": 5, "point": 0.00001,
        "pip_size": 0.0001, "trade_contract_size": 100000.0, "trade_tick_value": 1.0, "trade_tick_size": 0.00001,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "adr_14_pips": 68.4, "atr_14_pips": 72.1
    },
    {
        "symbol": "GBPUSD", "category": "Forex Majors", "bid": 1.29400, "ask": 1.29415, "digits": 5, "point": 0.00001,
        "pip_size": 0.0001, "trade_contract_size": 100000.0, "trade_tick_value": 1.0, "trade_tick_size": 0.00001,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "adr_14_pips": 94.2, "atr_14_pips": 98.0
    },
    {
        "symbol": "USDJPY", "category": "Forex Majors", "bid": 154.250, "ask": 154.265, "digits": 3, "point": 0.001,
        "pip_size": 0.01, "trade_contract_size": 100000.0, "trade_tick_value": 0.648, "trade_tick_size": 0.001,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "adr_14_pips": 112.5, "atr_14_pips": 118.0
    },
    {
        "symbol": "AUDUSD", "category": "Forex Majors", "bid": 0.65350, "ask": 0.65362, "digits": 5, "point": 0.00001,
        "pip_size": 0.0001, "trade_contract_size": 100000.0, "trade_tick_value": 1.0, "trade_tick_size": 0.00001,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "adr_14_pips": 58.0, "atr_14_pips": 61.3
    },
    {
        "symbol": "USDCAD", "category": "Forex Majors", "bid": 1.38120, "ask": 1.38135, "digits": 5, "point": 0.00001,
        "pip_size": 0.0001, "trade_contract_size": 100000.0, "trade_tick_value": 0.724, "trade_tick_size": 0.00001,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "adr_14_pips": 62.1, "atr_14_pips": 65.4
    },
    {
        "symbol": "USDCHF", "category": "Forex Majors", "bid": 0.88450, "ask": 0.88465, "digits": 5, "point": 0.00001,
        "pip_size": 0.0001, "trade_contract_size": 100000.0, "trade_tick_value": 1.13, "trade_tick_size": 0.00001,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "adr_14_pips": 52.8, "atr_14_pips": 55.0
    },
    {
        "symbol": "NZDUSD", "category": "Forex Majors", "bid": 0.59200, "ask": 0.59215, "digits": 5, "point": 0.00001,
        "pip_size": 0.0001, "trade_contract_size": 100000.0, "trade_tick_value": 1.0, "trade_tick_size": 0.00001,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "adr_14_pips": 51.5, "atr_14_pips": 54.2
    },
    {
        "symbol": "EURGBP", "category": "Forex Minors", "bid": 0.83850, "ask": 0.83864, "digits": 5, "point": 0.00001,
        "pip_size": 0.0001, "trade_contract_size": 100000.0, "trade_tick_value": 1.294, "trade_tick_size": 0.00001,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "adr_14_pips": 38.6, "atr_14_pips": 41.0
    },
    {
        "symbol": "EURJPY", "category": "Forex Minors", "bid": 167.350, "ask": 167.368, "digits": 3, "point": 0.001,
        "pip_size": 0.01, "trade_contract_size": 100000.0, "trade_tick_value": 0.648, "trade_tick_size": 0.001,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "adr_14_pips": 128.4, "atr_14_pips": 134.0
    },
    {
        "symbol": "GBPJPY", "category": "Forex Minors", "bid": 199.600, "ask": 199.622, "digits": 3, "point": 0.001,
        "pip_size": 0.01, "trade_contract_size": 100000.0, "trade_tick_value": 0.648, "trade_tick_size": 0.001,
        "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01, "adr_14_pips": 156.0, "atr_14_pips": 162.5
    },
    {
        "symbol": "XAUUSD", "category": "Metals", "bid": 2650.50, "ask": 2650.85, "digits": 2, "point": 0.01,
        "pip_size": 0.1, "trade_contract_size": 100.0, "trade_tick_value": 1.0, "trade_tick_size": 0.01,
        "volume_min": 0.01, "volume_max": 50.0, "volume_step": 0.01, "adr_14_pips": 310.0, "atr_14_pips": 325.0
    },
    {
        "symbol": "XAGUSD", "category": "Metals", "bid": 31.450, "ask": 31.475, "digits": 3, "point": 0.001,
        "pip_size": 0.01, "trade_contract_size": 5000.0, "trade_tick_value": 5.0, "trade_tick_size": 0.001,
        "volume_min": 0.01, "volume_max": 20.0, "volume_step": 0.01, "adr_14_pips": 85.0, "atr_14_pips": 90.0
    },
    {
        "symbol": "USOIL", "category": "Energies", "bid": 71.25, "ask": 71.29, "digits": 2, "point": 0.01,
        "pip_size": 0.01, "trade_contract_size": 1000.0, "trade_tick_value": 10.0, "trade_tick_size": 0.01,
        "volume_min": 0.01, "volume_max": 50.0, "volume_step": 0.01, "adr_14_pips": 180.0, "atr_14_pips": 192.0
    },
    {
        "symbol": "US500", "category": "Indices", "bid": 5820.5, "ask": 5821.1, "digits": 1, "point": 0.1,
        "pip_size": 1.0, "trade_contract_size": 10.0, "trade_tick_value": 1.0, "trade_tick_size": 0.1,
        "volume_min": 0.1, "volume_max": 100.0, "volume_step": 0.1, "adr_14_pips": 54.0, "atr_14_pips": 58.0
    },
    {
        "symbol": "USTECH", "category": "Indices", "bid": 20450.0, "ask": 20452.5, "digits": 1, "point": 0.1,
        "pip_size": 1.0, "trade_contract_size": 10.0, "trade_tick_value": 1.0, "trade_tick_size": 0.1,
        "volume_min": 0.1, "volume_max": 100.0, "volume_step": 0.1, "adr_14_pips": 240.0, "atr_14_pips": 255.0
    },
    {
        "symbol": "BTCUSD", "category": "Crypto", "bid": 92450.0, "ask": 92485.0, "digits": 2, "point": 0.01,
        "pip_size": 1.0, "trade_contract_size": 1.0, "trade_tick_value": 0.01, "trade_tick_size": 0.01,
        "volume_min": 0.01, "volume_max": 10.0, "volume_step": 0.01, "adr_14_pips": 3200.0, "atr_14_pips": 3450.0
    }
]


def generate_mock_trades_pnl(count: int = 185, win_rate: float = 0.56, payoff_ratio: float = 1.45) -> List[float]:
    """Generates synthetic closed trade PnLs for demo/fallback purposes."""
    np.random.seed(42)
    trades = []
    avg_win = 45.0
    avg_loss = avg_win / payoff_ratio
    
    for _ in range(count):
        is_win = np.random.rand() < win_rate
        if is_win:
            # lognormal distribution for wins
            val = float(np.random.exponential(scale=avg_win))
            trades.append(round(val, 2))
        else:
            # lognormal distribution for losses
            val = -float(np.random.exponential(scale=avg_loss))
            trades.append(round(val, 2))
    return trades


class MT5RiskFeed:
    """
    Manages MT5 live data retrieval, in-memory TTL caching, thread synchronization,
    and fast tick polling with sub-second responsiveness.
    """

    VOLATILITY_TTL_SECONDS = 900.0   # 15 minutes TTL for 14-day D1 ADR / ATR
    MARKET_WATCH_TTL_SECONDS = 5.0   # 5 seconds TTL for Market Watch symbol list discovery

    def __init__(self, mock_mode: bool = False):
        self._is_connected = False
        self._mock_mode = mock_mode
        self._cached_trades: List[float] = []
        self._mt5_lock = threading.RLock()
        
        # In-memory caches for high-speed sub-second polling
        self._specs_cache: Dict[str, Dict[str, Any]] = {}
        self._volatility_cache: Dict[str, Dict[str, Any]] = {}
        self._cached_symbol_names: List[str] = []
        self._last_symbol_sync_time: float = 0.0

        if not mock_mode:
            self._init_mt5()

    def _init_mt5(self) -> bool:
        if mt5 is None:
            logger.warning("MetaTrader5 python package not available. Running in Mock Data Mode.")
            self._mock_mode = True
            self._is_connected = False
            return False
        
        with self._mt5_lock:
            try:
                if not mt5.initialize():
                    err = mt5.last_error()
                    logger.warning(f"MT5 initialize() returned False (Error: {err}). Running in Mock Data Mode.")
                    self._mock_mode = True
                    self._is_connected = False
                    return False
                
                terminal_info = mt5.terminal_info()
                if terminal_info is None:
                    logger.warning("MT5 terminal info is None. Running in Mock Data Mode.")
                    self._mock_mode = True
                    self._is_connected = False
                    return False

                self._is_connected = True
                self._mock_mode = False
                logger.info("Successfully connected to live MT5 terminal.")
                # Pre-warm volatility cache on initialization
                self.refresh_volatility_cache()
                return True
            except Exception as e:
                logger.warning(f"Exception initializing MT5: {e}. Running in Mock Data Mode.")
                self._mock_mode = True
                self._is_connected = False
                return False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_live(self) -> bool:
        return self._is_connected and not self._mock_mode

    def get_account_summary(self) -> Dict[str, Any]:
        """Returns account equity, balance, leverage, currency, and margin stats."""
        if self.is_live:
            with self._mt5_lock:
                try:
                    acc = mt5.account_info()
                    if acc is not None:
                        margin_mode_raw = getattr(acc, "margin_mode", 2)
                        if margin_mode_raw == 2:
                            account_type = "Hedge"
                        elif margin_mode_raw in (0, 1):
                            account_type = "Netting"
                        else:
                            account_type = "Hedge"

                        return {
                            "is_live": True,
                            "login": acc.login,
                            "server": acc.server,
                            "currency": acc.currency,
                            "balance": float(acc.balance),
                            "equity": float(acc.equity),
                            "margin": float(acc.margin),
                            "margin_free": float(acc.margin_free),
                            "margin_level": float(acc.margin_level) if acc.margin_level else 0.0,
                            "leverage": float(acc.leverage) if acc.leverage > 0 else 300.0,
                            "account_type": account_type,
                            "name": acc.name
                        }
                except Exception as e:
                    logger.error(f"Error reading account info: {e}")

        # Fallback Mock Account
        return {
            "is_live": False,
            "login": 88812345,
            "server": "Demo-Server (Simulated)",
            "currency": "USD",
            "balance": 20.0,
            "equity": 20.0,
            "margin": 0.0,
            "margin_free": 20.0,
            "margin_level": 0.0,
            "leverage": 300.0,
            "account_type": "Hedge",
            "name": "Simulated MT5 User"
        }

    def _determine_category(self, symbol: str, path: str = "") -> str:
        s = symbol.upper()
        p = path.upper()
        
        # 1. Check Forex Majors first (including broker prefixes/suffixes)
        majors = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
        if any(m in s for m in majors):
            return "Forex Majors"

        # 2. Metals
        if any(m in s for m in ["XAU", "XAG", "GOLD", "SILVER", "PLATINUM", "PALLADIUM"]) or "METALS" in p:
            return "Metals"

        # 3. Energies
        if any(e in s for e in ["OIL", "BRENT", "WTI", "GAS", "CRUDE", "NGAS"]) or "ENERGY" in p or "ENERGIES" in p:
            return "Energies"

        # 4. Crypto
        if any(c in s for c in ["BTC", "ETH", "SOL", "XRP", "LTC", "DOGE", "ADA", "BNB"]) or "CRYPTO" in p:
            return "Crypto"

        # 5. Indices (avoid broad 2-letter matches like 'DJ' that match currency pairs)
        index_keywords = [
            "500", "TECH", "DOW", "DAX", "FTSE", "NIKKEI", "NAS", "NASDAQ", "NDAQ",
            "SPX", "DJ30", "DJIA", "US30", "JP225", "JAPAN", "DE40", "DE30", "GERMANY",
            "UK100", "US100", "US500", "HK50", "WS30", "CAC", "STOXX", "RUSSELL", "US2000"
        ]
        if any(idx in s for idx in index_keywords) or "INDEX" in p or "INDICES" in p:
            return "Indices"

        # 6. Equities / Stocks (e.g. AMD.O, AAPL.O, TSLA.O, NVDA.O, MSFT.O or STOCK/EQUITY paths)
        if any(ext in s for ext in [".O", ".N", ".US", ".UK", ".DE", "AMD", "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOG", "META"]) or any(k in p for k in ["STOCK", "EQUITY", "EQUITIES", "SHARES"]):
            return "Stocks"

        # 7. Forex Minors / Crosses
        if len(s) >= 6 and any(s.startswith(cur) or cur in s for cur in ["EUR", "GBP", "USD", "AUD", "CAD", "CHF", "NZD", "JPY"]):
            return "Forex Minors"

        return "Other"

    def compute_step_rule(self, symbol: str, category: str, digits: int, point: float, pip_size: float, stops_level: int = 0) -> Dict[str, Any]:
        """
        Computes exact institutional stepping rules, multiplier increments, and stops limits
        based on broker instrument metadata.
        """
        sym = symbol.upper()
        cat = (category or "").upper()

        # 1. Forex JPY Pairs (3 digits)
        if ("JPY" in sym or "JPY" in cat) and digits == 3:
            normal_step = 0.01
            fast_step = 0.10
            precision_step = 0.001
            unit_label = "pips"
        # 2. Forex Standard Pairs (5 digits or 4 digits non-metal)
        elif "FOREX" in cat or digits == 5 or (digits == 4 and "XAU" not in sym and "GOLD" not in sym):
            normal_step = pip_size if pip_size > 0 else 0.0001
            fast_step = normal_step * 10.0
            precision_step = point if point > 0 else 0.00001
            unit_label = "pips"
        # 3. Precious Metals (Gold - XAU, Silver - XAG)
        elif "METAL" in cat or any(m in sym for m in ["XAU", "GOLD", "XAG", "SILVER"]):
            if "XAU" in sym or "GOLD" in sym:
                normal_step = 0.50
                fast_step = 5.00
                precision_step = 0.05
            else:
                normal_step = 0.05
                fast_step = 0.50
                precision_step = 0.005
            unit_label = "pts"
        # 4. Indices
        elif "IND" in cat or any(k in sym for k in ["500", "SPX", "30", "NAS", "100", "DE40", "GER"]):
            if "500" in sym or "SPX" in sym:
                normal_step = 1.00
                fast_step = 10.00
                precision_step = 0.25
            else:
                normal_step = 5.00
                fast_step = 50.00
                precision_step = 1.00
            unit_label = "pts"
        # 5. Crypto
        elif "CRYPTO" in cat or any(c in sym for c in ["BTC", "ETH", "SOL"]):
            if "BTC" in sym:
                normal_step = 10.0
                fast_step = 100.0
                precision_step = 1.0
            else:
                normal_step = 1.0
                fast_step = 10.0
                precision_step = 0.1
            unit_label = "$"
        # 6. Energies
        elif "ENERGY" in cat or any(e in sym for e in ["OIL", "BRENT", "WTI"]):
            normal_step = 0.10
            fast_step = 1.00
            precision_step = 0.01
            unit_label = "pts"
        else:
            normal_step = pip_size if pip_size > 0 else (point * 10 if point > 0 else 0.0001)
            fast_step = normal_step * 10.0
            precision_step = point if point > 0 else (normal_step / 10.0)
            unit_label = "pips" if digits in (3, 5) else "pts"

        stops_level_pips = round((stops_level * point) / pip_size, 1) if (stops_level > 0 and pip_size > 0 and point > 0) else 0.0

        return {
            "pip_size": round(pip_size, digits) if pip_size > 0 else 0.0001,
            "digits": digits,
            "normal_step": round(normal_step, digits),
            "fast_step": round(fast_step, digits),
            "precision_step": round(precision_step, digits),
            "unit_label": unit_label,
            "stops_level_pips": stops_level_pips
        }

    def _calculate_adr_and_atr(self, symbol: str, point: float, digits: int, period: int = 14) -> Tuple[float, float, float]:
        """
        Calculates 14-day D1 ADR and ATR in pips.
        Leverages the 15-minute in-memory cache to prevent blocking IPC calls during fast ticks.
        Returns (adr_pips, atr_pips, pip_size).
        """
        pip_multiplier = 10.0 if digits in (3, 5) else 1.0
        pip_size = point * pip_multiplier if point > 0 else 0.0001
        now = time.time()

        # Check cache first
        cached = self._volatility_cache.get(symbol)
        if cached and (now - cached.get("timestamp", 0)) < self.VOLATILITY_TTL_SECONDS:
            return cached["adr_14_pips"], cached["atr_14_pips"], pip_size

        if self.is_live:
            with self._mt5_lock:
                try:
                    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 1, period)
                    if rates is not None and len(rates) >= 5:
                        highs = np.asarray(rates['high'], dtype=np.float64)
                        lows = np.asarray(rates['low'], dtype=np.float64)
                        closes = np.asarray(rates['close'], dtype=np.float64)
                        
                        ranges = highs - lows
                        adr_pips = float(np.mean(ranges) / pip_size)
                        
                        # Vectorized True Range (Wilder TR)
                        hl = highs[1:] - lows[1:]
                        hc = np.abs(highs[1:] - closes[:-1])
                        lc = np.abs(lows[1:] - closes[:-1])
                        tr = np.maximum.reduce([hl, hc, lc])
                        atr_pips = float(np.mean(tr) / pip_size) if len(tr) > 0 else adr_pips
                        
                        adr_val = round(adr_pips, 1)
                        atr_val = round(atr_pips, 1)
                        self._volatility_cache[symbol] = {
                            "adr_14_pips": adr_val,
                            "atr_14_pips": atr_val,
                            "timestamp": now
                        }
                        return adr_val, atr_val, pip_size
                except Exception as e:
                    logger.debug(f"Could not compute live ADR for {symbol}: {e}")

        # Fallback approximation for mock or missing data
        default_adr = 65.0
        for item in MOCK_SYMBOLS_SPECS:
            if item["symbol"] == symbol:
                adr_val = item["adr_14_pips"]
                atr_val = item["atr_14_pips"]
                self._volatility_cache[symbol] = {
                    "adr_14_pips": adr_val,
                    "atr_14_pips": atr_val,
                    "timestamp": now
                }
                return adr_val, atr_val, item["pip_size"]
        
        self._volatility_cache[symbol] = {
            "adr_14_pips": default_adr,
            "atr_14_pips": round(default_adr * 1.05, 1),
            "timestamp": now
        }
        return default_adr, round(default_adr * 1.05, 1), pip_size

    def refresh_volatility_cache(self, symbols: Optional[List[str]] = None, force: bool = False) -> None:
        """
        Proactively warms and refreshes the 15-minute ADR/ATR cache for Market Watch symbols.
        Called asynchronously in the background so sub-second tick polling never hits IPC bottlenecks.
        """
        now = time.time()
        sym_list = symbols
        if sym_list is None:
            if self.is_live:
                with self._mt5_lock:
                    try:
                        all_syms = mt5.symbols_get()
                        if all_syms:
                            mw_symbols = [s for s in all_syms if s.visible]
                            if not mw_symbols:
                                mw_symbols = [s for s in all_syms if s.select]
                            if not mw_symbols:
                                mw_symbols = all_syms[:30]
                            sym_list = [s.name for s in mw_symbols]
                    except Exception as e:
                        logger.error(f"Error fetching symbols in refresh_volatility_cache: {e}")
            
            if not sym_list:
                sym_list = [item["symbol"] for item in MOCK_SYMBOLS_SPECS]

        self._cached_symbol_names = sym_list

        for symbol in sym_list:
            cached = self._volatility_cache.get(symbol)
            if not force and cached and (now - cached.get("timestamp", 0)) < self.VOLATILITY_TTL_SECONDS:
                continue

            if self.is_live:
                with self._mt5_lock:
                    try:
                        info = mt5.symbol_info(symbol)
                        if info:
                            digits = info.digits
                            point = info.point
                            pip_multiplier = 10.0 if digits in (3, 5) else 1.0
                            pip_size = point * pip_multiplier if point > 0 else 0.0001
                            
                            category = self._determine_category(info.name, info.path)
                            acc = mt5.account_info() if self.is_live else None
                            lev = float(acc.leverage) if (acc and acc.leverage > 0) else 2000.0
                            default_rate = 0.04 if category == "Stocks" else (1.0 / lev)
                            base_margin_rate = default_rate
                            try:
                                tick = mt5.symbol_info_tick(symbol)
                                init_price = float(tick.ask) if tick and tick.ask else 1.0
                                raw_m = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, 1.0, init_price)
                                if raw_m is not None and raw_m > 0:
                                    n_1lot = float(info.trade_contract_size) * init_price
                                    if n_1lot > 0:
                                        base_margin_rate = round(float(raw_m) / n_1lot, 6)
                            except Exception:
                                pass

                            # Cache base static specs
                            self._specs_cache[symbol] = {
                                "symbol": info.name,
                                "category": category,
                                "digits": digits,
                                "point": point,
                                "pip_size": pip_size,
                                "trade_contract_size": float(info.trade_contract_size) if info.trade_contract_size > 0 else 100000.0,
                                "trade_tick_value": float(info.trade_tick_value) if info.trade_tick_value > 0 else 1.0,
                                "trade_tick_size": float(info.trade_tick_size) if info.trade_tick_size > 0 else point,
                                "trade_stops_level": int(info.trade_stops_level) if hasattr(info, "trade_stops_level") else 0,
                                "volume_min": float(info.volume_min) if info.volume_min > 0 else 0.01,
                                "volume_max": float(info.volume_max) if info.volume_max > 0 else 100.0,
                                "volume_step": float(info.volume_step) if info.volume_step > 0 else 0.01,
                                "currency_base": info.currency_base,
                                "currency_profit": info.currency_profit,
                                "currency_margin": info.currency_margin,
                                "margin_rate": base_margin_rate
                            }
                            # Calculate ADR/ATR
                            self._calculate_adr_and_atr(symbol, point, digits)
                    except Exception as e:
                        logger.error(f"Error refreshing volatility cache for {symbol}: {e}")
            else:
                # Mock mode cache populate
                for item in MOCK_SYMBOLS_SPECS:
                    if item["symbol"] == symbol:
                        self._specs_cache[symbol] = {
                            "symbol": item["symbol"],
                            "category": item["category"],
                            "digits": item["digits"],
                            "point": item["point"],
                            "pip_size": item["pip_size"],
                            "trade_contract_size": item["trade_contract_size"],
                            "trade_tick_value": item["trade_tick_value"],
                            "trade_tick_size": item["trade_tick_size"],
                            "trade_stops_level": 0,
                            "volume_min": item["volume_min"],
                            "volume_max": item["volume_max"],
                            "volume_step": item["volume_step"],
                            "currency_base": symbol[:3] if len(symbol) == 6 else "USD",
                            "currency_profit": symbol[3:6] if len(symbol) == 6 else "USD",
                            "currency_margin": symbol[:3] if len(symbol) == 6 else "USD",
                            "margin_rate": 0.04 if item["category"] == "Stocks" else 0.0005
                        }
                        self._volatility_cache[symbol] = {
                            "adr_14_pips": item["adr_14_pips"],
                            "atr_14_pips": item["atr_14_pips"],
                            "timestamp": now
                        }

    def get_symbol_specs(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves real-time symbol specifications, tick prices, spread, and ADR/ATR.
        Optimized with fast tick lookups and cached volatility/specifications.
        """
        if self.is_live:
            with self._mt5_lock:
                try:
                    # Fast tick lookup (< 0.05ms)
                    tick = mt5.symbol_info_tick(symbol)
                    base_spec = self._specs_cache.get(symbol)
                    
                    if base_spec is None:
                        info = mt5.symbol_info(symbol)
                        if info is not None:
                            digits = info.digits
                            point = info.point
                            pip_multiplier = 10.0 if digits in (3, 5) else 1.0
                            pip_size = point * pip_multiplier if point > 0 else 0.0001
                            category = self._determine_category(info.name, info.path)
                            acc = mt5.account_info() if self.is_live else None
                            lev = float(acc.leverage) if (acc and acc.leverage > 0) else 2000.0
                            default_rate = 0.04 if category == "Stocks" else (1.0 / lev)
                            base_margin_rate = default_rate
                            try:
                                init_price = float(tick.ask) if tick and tick.ask else 1.0
                                raw_m = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, 1.0, init_price)
                                if raw_m is not None and raw_m > 0:
                                    n_1lot = float(info.trade_contract_size) * init_price
                                    if n_1lot > 0:
                                        base_margin_rate = round(float(raw_m) / n_1lot, 6)
                            except Exception:
                                pass

                            base_spec = {
                                "symbol": info.name,
                                "category": category,
                                "digits": digits,
                                "point": point,
                                "pip_size": pip_size,
                                "trade_contract_size": float(info.trade_contract_size) if info.trade_contract_size > 0 else 100000.0,
                                "trade_tick_value": float(info.trade_tick_value) if info.trade_tick_value > 0 else 1.0,
                                "trade_tick_size": float(info.trade_tick_size) if info.trade_tick_size > 0 else point,
                                "trade_stops_level": int(info.trade_stops_level) if hasattr(info, "trade_stops_level") else 0,
                                "volume_min": float(info.volume_min) if info.volume_min > 0 else 0.01,
                                "volume_max": float(info.volume_max) if info.volume_max > 0 else 100.0,
                                "volume_step": float(info.volume_step) if info.volume_step > 0 else 0.01,
                                "currency_base": info.currency_base,
                                "currency_profit": info.currency_profit,
                                "currency_margin": info.currency_margin,
                                "margin_rate": base_margin_rate
                            }
                            self._specs_cache[symbol] = base_spec

                    if base_spec is not None:
                        digits = base_spec["digits"]
                        point = base_spec["point"]
                        pip_size = base_spec["pip_size"]
                        tick_size = base_spec["trade_tick_size"]
                        tick_value = base_spec["trade_tick_value"]
                        stops_level = int(base_spec.get("trade_stops_level", 0))
                        
                        adr_pips, atr_pips, _ = self._calculate_adr_and_atr(symbol, point, digits)
                        
                        bid = tick.bid if tick else 1.0
                        ask = tick.ask if tick else 1.0
                        spread_pips = round((ask - bid) / pip_size, 1) if (ask and bid and pip_size > 0) else 1.0
                        
                        pip_value_per_lot = (pip_size / tick_size) * tick_value if tick_size > 0 else 10.0
                        if pip_value_per_lot <= 0:
                            pip_value_per_lot = 10.0

                        step_rule = self.compute_step_rule(
                            symbol=symbol,
                            category=base_spec["category"],
                            digits=digits,
                            point=point,
                            pip_size=pip_size,
                            stops_level=stops_level
                        )

                        contract_size = base_spec["trade_contract_size"]
                        m_price = float(ask) if ask else 1.0
                        notional_1lot = contract_size * m_price
                        margin_rate = base_spec.get("margin_rate", 0.04 if base_spec["category"] == "Stocks" else 0.0005)
                        margin_per_lot = round(notional_1lot * margin_rate, 4)

                        return {
                            **base_spec,
                            "bid": float(bid) if bid else 1.0,
                            "ask": float(ask) if ask else 1.0,
                            "pip_value_per_lot": round(float(pip_value_per_lot), 4),
                            "spread_pips": spread_pips,
                            "adr_14_pips": adr_pips,
                            "atr_14_pips": atr_pips,
                            "step_rule": step_rule,
                            "margin_per_lot": margin_per_lot,
                            "margin_rate": margin_rate
                        }
                except Exception as e:
                    logger.error(f"Error fetching live symbol specs for {symbol}: {e}")

        # Fallback to mock dictionary
        for item in MOCK_SYMBOLS_SPECS:
            if item["symbol"] == symbol:
                pip_size = item["pip_size"]
                pip_val = (pip_size / item["trade_tick_size"]) * item["trade_tick_value"]
                
                # Check cached volatility if available
                vol = self._volatility_cache.get(symbol)
                adr_val = vol["adr_14_pips"] if vol else item["adr_14_pips"]
                atr_val = vol["atr_14_pips"] if vol else item["atr_14_pips"]

                step_rule = self.compute_step_rule(
                    symbol=item["symbol"],
                    category=item["category"],
                    digits=item["digits"],
                    point=item["point"],
                    pip_size=pip_size,
                    stops_level=0
                )

                contract_size = item["trade_contract_size"]
                m_price = item["ask"]
                notional_1lot = contract_size * m_price
                margin_per_lot = round(notional_1lot * 0.04 if item["category"] == "Stocks" else notional_1lot / 300.0, 4)
                margin_rate = round(margin_per_lot / notional_1lot, 6) if notional_1lot > 0 else 0.0033

                return {
                    **item,
                    "pip_value_per_lot": round(pip_val, 4),
                    "spread_pips": round((item["ask"] - item["bid"]) / pip_size, 1),
                    "adr_14_pips": adr_val,
                    "atr_14_pips": atr_val,
                    "currency_base": symbol[:3] if len(symbol) == 6 else "USD",
                    "currency_profit": symbol[3:6] if len(symbol) == 6 else "USD",
                    "currency_margin": symbol[:3] if len(symbol) == 6 else "USD",
                    "step_rule": step_rule,
                    "margin_per_lot": margin_per_lot,
                    "margin_rate": margin_rate
                }
        return None

    def get_market_symbols(self) -> List[Dict[str, Any]]:
        """
        Retrieves list of Market Watch symbols with fast tick prices.
        Executes in < 5ms by decoupling 14-day history calculations.
        """
        results = []
        if self.is_live:
            with self._mt5_lock:
                try:
                    now = time.time()
                    # Refresh symbol list every 5s to sync Market Watch without querying 2,000+ symbols on every 500ms tick
                    if not self._cached_symbol_names or (now - self._last_symbol_sync_time) > self.MARKET_WATCH_TTL_SECONDS:
                        symbols = mt5.symbols_get()
                        if symbols:
                            mw_symbols = [s for s in symbols if s.visible]
                            if not mw_symbols:
                                mw_symbols = [s for s in symbols if s.select]
                            if not mw_symbols:
                                mw_symbols = symbols[:30]
                            self._cached_symbol_names = [s.name for s in mw_symbols]
                            self._last_symbol_sync_time = now

                    for sym_name in self._cached_symbol_names:
                        spec = self.get_symbol_specs(sym_name)
                        if spec:
                            results.append(spec)
                    if results:
                        return results
                except Exception as e:
                    logger.error(f"Error fetching symbols_get: {e}")

        # Fallback to mock symbols
        for item in MOCK_SYMBOLS_SPECS:
            spec = self.get_symbol_specs(item["symbol"])
            if spec:
                results.append(spec)
        return results

    def calculate_margin(self, symbol: str, lots: float, price: float, leverage: float = 300.0) -> Optional[float]:
        """
        Calculates exact broker margin using mt5.order_calc_margin when live,
        scaled by custom leverage if selected by the user.
        """
        if self.is_live:
            with self._mt5_lock:
                try:
                    acc = mt5.account_info()
                    acc_leverage = float(acc.leverage) if (acc and acc.leverage > 0) else 300.0
                    raw_margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, lots, price)
                    if raw_margin is not None and raw_margin > 0:
                        info = mt5.symbol_info(symbol)
                        is_fixed_margin = info and (getattr(info, "trade_calc_mode", 0) in (2, 32) or info.trade_contract_size <= 10.0)
                        if is_fixed_margin:
                            return round(float(raw_margin), 2)
                        scale = (acc_leverage / leverage) if (leverage > 0 and abs(acc_leverage - leverage) > 0.1) else 1.0
                        return round(float(raw_margin) * scale, 2)
                except Exception as e:
                    logger.debug(f"order_calc_margin error for {symbol}: {e}")
        return None

    def fetch_closed_deals_history(
        self,
        days: Optional[int] = None,
        symbol: Optional[str] = None,
        magic: Optional[int] = None
    ) -> List[float]:
        """
        Fetches closed trade deal profits from MT5 terminal history.
        Loads ALL deals from account inception when days is None.
        """
        if self.is_live:
            with self._mt5_lock:
                try:
                    now = datetime.now(timezone.utc) + timedelta(days=1)
                    if days is not None:
                        from_dt = now - timedelta(days=days)
                    else:
                        from_dt = datetime(1970, 1, 1, tzinfo=timezone.utc)
                    
                    deals = mt5.history_deals_get(from_dt, now)
                    
                    if deals is not None and len(deals) > 0:
                        pnl_list = []
                        for d in deals:
                            # Exclude balance deposits/withdrawals (DEAL_TYPE_BALANCE = 2)
                            if getattr(d, 'type', 0) == 2:
                                continue
                            # Closed deals (ENTRY_OUT=1, ENTRY_INOUT=2, ENTRY_OUT_BY=3) or trading deals with profit != 0
                            if d.entry in (1, 2, 3) or (d.type in (0, 1) and d.profit != 0):
                                if symbol and d.symbol.upper() != symbol.upper():
                                    continue
                                if magic is not None and d.magic != magic:
                                    continue
                                
                                net_pnl = float(d.profit) + float(d.swap) + float(d.commission) + float(d.fee)
                                pnl_list.append(round(net_pnl, 2))
                        
                        if pnl_list:
                            logger.info(f"Loaded {len(pnl_list)} closed deals from MT5 history.")
                            self._cached_trades = pnl_list
                            return pnl_list
                except Exception as e:
                    logger.error(f"Error fetching history_deals_get: {e}")

        # Fallback mock trade history
        if not self._cached_trades:
            self._cached_trades = generate_mock_trades_pnl(count=185, win_rate=0.56, payoff_ratio=1.45)
        return self._cached_trades

    def set_custom_trades(self, pnl_list: List[float]):
        """Sets custom trade history (from CSV or manual upload)."""
        self._cached_trades = pnl_list

    def send_market_order(
        self,
        symbol: str,
        action: str,
        volume: float,
        sl_pips: float,
        rr_ratio: float = 1.0,
        comment: str = "RiskDashboard",
        magic: int = 900100,
        slippage: int = 20
    ) -> Dict[str, Any]:
        """
        Executes a direct market order in MT5 with computed SL and TP prices.
        Returns execution result status, ticket, price, volume, sl, and tp.
        """
        action_upper = action.upper().strip()
        if action_upper not in ("BUY", "SELL"):
            return {"success": False, "message": f"Invalid order action: {action}"}

        if not self.is_live or mt5 is None:
            # Simulated execution mode
            spec = self.get_symbol_specs(symbol)
            digits = spec["digits"] if spec else 5
            pip_size = spec["pip_size"] if spec else 0.0001
            base_price = (spec["ask"] if action_upper == "BUY" else spec["bid"]) if spec else 1.0850
            
            if action_upper == "BUY":
                sl_price = round(base_price - (sl_pips * pip_size), digits)
                tp_price = round(base_price + (sl_pips * rr_ratio * pip_size), digits) if rr_ratio > 0 else 0.0
            else:
                sl_price = round(base_price + (sl_pips * pip_size), digits)
                tp_price = round(base_price - (sl_pips * rr_ratio * pip_size), digits) if rr_ratio > 0 else 0.0

            mock_ticket = int(np.random.randint(10000000, 99999999))
            return {
                "success": True,
                "mock": True,
                "ticket": mock_ticket,
                "symbol": symbol,
                "action": action_upper,
                "volume": volume,
                "price": base_price,
                "sl": sl_price,
                "tp": tp_price,
                "retcode": 10009,
                "message": f"Simulated {action_upper} {volume} {symbol} @ {base_price} (SL: {sl_price}, TP: {tp_price})"
            }

        with self._mt5_lock:
            try:
                if not mt5.symbol_select(symbol, True):
                    return {"success": False, "message": f"Symbol {symbol} cannot be selected in MT5"}

                info = mt5.symbol_info(symbol)
                tick = mt5.symbol_info_tick(symbol)
                if not info or not tick:
                    return {"success": False, "message": f"Could not retrieve live price tick for {symbol}"}

                digits = info.digits
                point = info.point
                pip_multiplier = 10.0 if digits in (3, 5) else 1.0
                pip_size = point * pip_multiplier if point > 0 else 0.0001

                # Clamp volume
                vol_min = float(info.volume_min) if info.volume_min > 0 else 0.01
                vol_max = float(info.volume_max) if info.volume_max > 0 else 100.0
                vol_step = float(info.volume_step) if info.volume_step > 0 else 0.01
                
                steps = round(volume / vol_step)
                clamped_vol = max(vol_min, min(vol_max, round(steps * vol_step, 6)))

                if action_upper == "BUY":
                    order_type = mt5.ORDER_TYPE_BUY
                    price = float(tick.ask)
                    sl_price = round(price - (sl_pips * pip_size), digits)
                    tp_price = round(price + (sl_pips * rr_ratio * pip_size), digits) if rr_ratio > 0 else 0.0
                else:
                    order_type = mt5.ORDER_TYPE_SELL
                    price = float(tick.bid)
                    sl_price = round(price + (sl_pips * pip_size), digits)
                    tp_price = round(price - (sl_pips * rr_ratio * pip_size), digits) if rr_ratio > 0 else 0.0

                filling_mode = mt5.ORDER_FILLING_IOC
                if hasattr(info, "filling_mode"):
                    if info.filling_mode & 1:
                        filling_mode = mt5.ORDER_FILLING_FOK
                    elif info.filling_mode & 2:
                        filling_mode = mt5.ORDER_FILLING_IOC
                    else:
                        filling_mode = mt5.ORDER_FILLING_RETURN

                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": clamped_vol,
                    "type": order_type,
                    "price": price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "deviation": slippage,
                    "magic": magic,
                    "comment": comment,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": filling_mode,
                }

                result = mt5.order_send(request)
                if result is None:
                    err = mt5.last_error()
                    return {"success": False, "message": f"mt5.order_send failed: {err}"}

                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    return {
                        "success": False,
                        "retcode": result.retcode,
                        "message": f"Order rejected: [{result.retcode}] {result.comment}"
                    }

                return {
                    "success": True,
                    "ticket": result.order or result.deal,
                    "symbol": symbol,
                    "action": action_upper,
                    "volume": clamped_vol,
                    "price": result.price if result.price > 0 else price,
                    "sl": sl_price,
                    "tp": tp_price,
                    "retcode": result.retcode,
                    "comment": result.comment,
                    "message": f"Executed {action_upper} {clamped_vol} {symbol} @ {price:.{digits}f} (SL: {sl_price:.{digits}f}, TP: {tp_price:.{digits}f})"
                }
            except Exception as e:
                logger.error(f"Exception during send_market_order: {e}")
                return {"success": False, "message": f"Execution exception: {str(e)}"}

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """
        Retrieves all currently open positions from MT5 terminal with live floating P&L and R-multiples.
        """
        if not self._is_connected or mt5 is None or self._mock_mode:
            return []

        with self._mt5_lock:
            try:
                positions = mt5.positions_get()
                if positions is None:
                    return []

                res = []
                for p in positions:
                    pos_type_str = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                    digits = 5
                    pip_size = 0.0001
                    info = mt5.symbol_info(p.symbol)
                    if info:
                        digits = info.digits
                        point = info.point
                        pip_multiplier = 10.0 if digits in (3, 5) else 1.0
                        pip_size = point * pip_multiplier if point > 0 else 0.0001

                    # Compute PnL in pips
                    pnl_pips = 0.0
                    if pos_type_str == "BUY":
                        pnl_pips = (p.price_current - p.price_open) / pip_size
                    else:
                        pnl_pips = (p.price_open - p.price_current) / pip_size

                    # Compute R-Multiple if SL was defined
                    r_multiple = None
                    if p.sl and p.sl > 0:
                        risk_dist = abs(p.price_open - p.sl)
                        if risk_dist > 0:
                            gain_dist = (p.price_current - p.price_open) if pos_type_str == "BUY" else (p.price_open - p.price_current)
                            r_multiple = round(gain_dist / risk_dist, 2)

                    category = self._determine_category(p.symbol, info.path if info else "")
                    point = info.point if info else (0.00001 if digits == 5 else 0.001)
                    stops_level = info.trade_stops_level if info else 0

                    step_rule = self.compute_step_rule(
                        symbol=p.symbol,
                        category=category,
                        digits=digits,
                        point=point,
                        pip_size=pip_size,
                        stops_level=stops_level
                    )

                    res.append({
                        "ticket": int(p.ticket),
                        "symbol": p.symbol,
                        "type": pos_type_str,
                        "volume": float(p.volume),
                        "price_open": round(float(p.price_open), digits),
                        "price_current": round(float(p.price_current), digits),
                        "sl": round(float(p.sl), digits) if p.sl else 0.0,
                        "tp": round(float(p.tp), digits) if p.tp else 0.0,
                        "profit": round(float(p.profit), 2),
                        "swap": round(float(p.swap), 2),
                        "pnl_pips": round(float(pnl_pips), 1),
                        "r_multiple": r_multiple,
                        "comment": p.comment or "",
                        "magic": int(p.magic),
                        "time": int(p.time),
                        "digits": digits,
                        "pip_size": pip_size,
                        "step_rule": step_rule
                    })
                return res
            except Exception as e:
                logger.error(f"Error in get_open_positions: {e}")
                return []

    def modify_position_sltp(self, ticket: int, sl: Optional[float], tp: Optional[float]) -> Dict[str, Any]:
        """
        Modifies Stop-Loss and/or Take-Profit on an open position.
        """
        if not self._is_connected or mt5 is None or self._mock_mode:
            return {"success": False, "message": "MT5 Terminal not connected"}

        with self._mt5_lock:
            try:
                positions = mt5.positions_get(ticket=ticket)
                if not positions or len(positions) == 0:
                    return {"success": False, "message": f"Position #{ticket} not found"}

                pos = positions[0]
                info = mt5.symbol_info(pos.symbol)
                digits = info.digits if info else 5

                new_sl = round(float(sl), digits) if sl is not None and sl > 0 else float(pos.sl)
                new_tp = round(float(tp), digits) if tp is not None and tp > 0 else float(pos.tp)

                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": int(ticket),
                    "symbol": pos.symbol,
                    "sl": new_sl,
                    "tp": new_tp,
                }

                result = mt5.order_send(request)
                if result is None:
                    err = mt5.last_error()
                    return {"success": False, "message": f"mt5.order_send failed: {err}"}

                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    return {
                        "success": False,
                        "retcode": result.retcode,
                        "message": f"Modify SL/TP rejected: [{result.retcode}] {result.comment}"
                    }

                return {
                    "success": True,
                    "ticket": ticket,
                    "symbol": pos.symbol,
                    "sl": new_sl,
                    "tp": new_tp,
                    "message": f"Modified #{ticket} {pos.symbol} (SL: {new_sl}, TP: {new_tp})"
                }
            except Exception as e:
                logger.error(f"Error in modify_position_sltp: {e}")
                return {"success": False, "message": f"Modify exception: {str(e)}"}

    def close_position(self, ticket: int, volume: Optional[float] = None) -> Dict[str, Any]:
        """
        Closes an open position (full volume or partial volume liquidation).
        """
        if not self._is_connected or mt5 is None or self._mock_mode:
            return {"success": False, "message": "MT5 Terminal not connected"}

        with self._mt5_lock:
            try:
                positions = mt5.positions_get(ticket=ticket)
                if not positions or len(positions) == 0:
                    return {"success": False, "message": f"Position #{ticket} not found"}

                pos = positions[0]
                symbol = pos.symbol
                info = mt5.symbol_info(symbol)
                tick = mt5.symbol_info_tick(symbol)
                if not info or not tick:
                    return {"success": False, "message": f"Could not retrieve tick for {symbol}"}

                digits = info.digits
                vol_step = float(info.volume_step) if info.volume_step > 0 else 0.01
                vol_min = float(info.volume_min) if info.volume_min > 0 else 0.01

                close_vol = float(pos.volume)
                if volume is not None and volume > 0 and volume < pos.volume:
                    steps = round(volume / vol_step)
                    close_vol = max(vol_min, round(steps * vol_step, 6))

                # Opposite order type
                if pos.type == mt5.ORDER_TYPE_BUY:
                    order_type = mt5.ORDER_TYPE_SELL
                    price = float(tick.bid)
                else:
                    order_type = mt5.ORDER_TYPE_BUY
                    price = float(tick.ask)

                filling_mode = mt5.ORDER_FILLING_IOC
                if hasattr(info, "filling_mode"):
                    if info.filling_mode & 1:
                        filling_mode = mt5.ORDER_FILLING_FOK
                    elif info.filling_mode & 2:
                        filling_mode = mt5.ORDER_FILLING_IOC
                    else:
                        filling_mode = mt5.ORDER_FILLING_RETURN

                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "position": int(ticket),
                    "symbol": symbol,
                    "volume": close_vol,
                    "type": order_type,
                    "price": price,
                    "deviation": 20,
                    "comment": f"Close #{ticket}",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": filling_mode,
                }

                result = mt5.order_send(request)
                if result is None:
                    err = mt5.last_error()
                    return {"success": False, "message": f"mt5.order_send failed: {err}"}

                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    return {
                        "success": False,
                        "retcode": result.retcode,
                        "message": f"Close rejected: [{result.retcode}] {result.comment}"
                    }

                return {
                    "success": True,
                    "ticket": ticket,
                    "symbol": symbol,
                    "closed_volume": close_vol,
                    "remaining_volume": round(float(pos.volume) - close_vol, 6),
                    "price": price,
                    "message": f"Closed {close_vol} lots of #{ticket} {symbol} @ {price:.{digits}f}"
                }
            except Exception as e:
                logger.error(f"Error in close_position: {e}")
                return {"success": False, "message": f"Close exception: {str(e)}"}

    def close_all_positions(self) -> List[Dict[str, Any]]:
        """
        Closes all currently open positions.
        """
        positions = self.get_open_positions()
        results = []
        for p in positions:
            res = self.close_position(ticket=p["ticket"])
            results.append(res)
        return results


feed = MT5RiskFeed(mock_mode=False)



