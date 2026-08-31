"""
MT5 Feed & Market Data Interface for Risk Management Dashboard.
Handles:
1. MT5 Terminal initialization & account detection
2. Live Market Watch symbols & specifications (volume min/max/step, contract size, tick value)
3. Dynamic D1 ADR(14) & ATR(14) in pips calculation
4. Account Trade History extraction (closed deals, PnL list)
5. Robust fallback/mock mode when MT5 terminal is offline
"""

from datetime import datetime, timezone, timedelta
import logging
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
    """Manages MT5 live data retrieval and fallback mock structures."""

    def __init__(self, mock_mode: bool = False):
        self._is_connected = False
        self._mock_mode = mock_mode
        self._cached_trades: List[float] = []
        if not mock_mode:
            self._init_mt5()

    def _init_mt5(self) -> bool:
        if mt5 is None:
            logger.warning("MetaTrader5 python package not available. Running in Mock Data Mode.")
            self._mock_mode = True
            self._is_connected = False
            return False
        
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
            return True
        except Exception as e:
            logger.warning(f"Exception initializing MT5: {e}. Running in Mock Data Mode.")
            self._mock_mode = True
            self._is_connected = False
            return False

    @property
    def is_live(self) -> bool:
        return self._is_connected and not self._mock_mode

    def get_account_summary(self) -> Dict[str, Any]:
        """Returns account equity, balance, leverage, currency, and margin stats."""
        if self.is_live:
            try:
                acc = mt5.account_info()
                if acc is not None:
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
        index_keywords = ["500", "TECH", "DOW", "DAX", "FTSE", "NIKKEI", "NAS", "SPX", "DJ30", "DJIA", "US30", "JP225", "DE40", "DE30", "UK100", "US100", "US500", "HK50", "WS30", "CAC", "STOXX"]
        if any(idx in s for idx in index_keywords) or "INDEX" in p or "INDICES" in p:
            return "Indices"

        # 6. Forex Minors / Crosses
        if len(s) >= 6 and any(s.startswith(cur) or cur in s for cur in ["EUR", "GBP", "USD", "AUD", "CAD", "CHF", "NZD", "JPY"]):
            return "Forex Minors"

        return "Other"

    def _calculate_adr_and_atr(self, symbol: str, point: float, digits: int, period: int = 14) -> Tuple[float, float, float]:
        """
        Calculates 14-day D1 ADR and ATR in pips.
        Returns (adr_pips, atr_pips, pip_size).
        """
        pip_multiplier = 10.0 if digits in (3, 5) else 1.0
        pip_size = point * pip_multiplier if point > 0 else 0.0001

        if self.is_live:
            try:
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 1, period)
                if rates is not None and len(rates) >= 5:
                    highs = rates['high']
                    lows = rates['low']
                    closes = rates['close']
                    
                    ranges = highs - lows
                    adr_pips = float(np.mean(ranges) / pip_size)
                    
                    # True Range
                    tr_list = []
                    for i in range(len(rates)):
                        hl = highs[i] - lows[i]
                        if i > 0:
                            hc = abs(highs[i] - closes[i - 1])
                            lc = abs(lows[i] - closes[i - 1])
                            tr = max(hl, hc, lc)
                        else:
                            tr = hl
                        tr_list.append(tr)
                    atr_pips = float(np.mean(tr_list) / pip_size)
                    return round(adr_pips, 1), round(atr_pips, 1), pip_size
            except Exception as e:
                logger.debug(f"Could not compute live ADR for {symbol}: {e}")

        # Fallback approximation
        default_adr = 65.0
        for item in MOCK_SYMBOLS_SPECS:
            if item["symbol"] == symbol:
                return item["adr_14_pips"], item["atr_14_pips"], item["pip_size"]
        return default_adr, default_adr * 1.05, pip_size

    def get_symbol_specs(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetches detailed specifications for a single symbol."""
        if self.is_live:
            try:
                info = mt5.symbol_info(symbol)
                tick = mt5.symbol_info_tick(symbol)
                if info is not None:
                    digits = info.digits
                    point = info.point
                    adr_pips, atr_pips, pip_size = self._calculate_adr_and_atr(symbol, point, digits)
                    
                    bid = tick.bid if tick else info.bid
                    ask = tick.ask if tick else info.ask
                    spread_pips = round((ask - bid) / pip_size, 1) if (ask and bid and pip_size > 0) else 1.0
                    
                    tick_value = info.trade_tick_value if info.trade_tick_value > 0 else 1.0
                    tick_size = info.trade_tick_size if info.trade_tick_size > 0 else point
                    
                    # Pip value for 1 lot in deposit currency
                    pip_value_per_lot = (pip_size / tick_size) * tick_value if tick_size > 0 else 10.0
                    if pip_value_per_lot <= 0:
                        pip_value_per_lot = 10.0

                    return {
                        "symbol": info.name,
                        "category": self._determine_category(info.name, info.path),
                        "bid": float(bid) if bid else 1.0,
                        "ask": float(ask) if ask else 1.0,
                        "digits": digits,
                        "point": point,
                        "pip_size": pip_size,
                        "pip_value_per_lot": round(float(pip_value_per_lot), 4),
                        "spread_pips": spread_pips,
                        "trade_contract_size": float(info.trade_contract_size) if info.trade_contract_size > 0 else 100000.0,
                        "trade_tick_value": float(tick_value),
                        "trade_tick_size": float(tick_size),
                        "volume_min": float(info.volume_min) if info.volume_min > 0 else 0.01,
                        "volume_max": float(info.volume_max) if info.volume_max > 0 else 100.0,
                        "volume_step": float(info.volume_step) if info.volume_step > 0 else 0.01,
                        "adr_14_pips": adr_pips,
                        "atr_14_pips": atr_pips,
                        "currency_base": info.currency_base,
                        "currency_profit": info.currency_profit,
                        "currency_margin": info.currency_margin
                    }
            except Exception as e:
                logger.error(f"Error fetching live symbol specs for {symbol}: {e}")

        # Fallback to mock dictionary
        for item in MOCK_SYMBOLS_SPECS:
            if item["symbol"] == symbol:
                pip_size = item["pip_size"]
                pip_val = (pip_size / item["trade_tick_size"]) * item["trade_tick_value"]
                return {
                    **item,
                    "pip_value_per_lot": round(pip_val, 4),
                    "spread_pips": round((item["ask"] - item["bid"]) / pip_size, 1),
                    "currency_base": symbol[:3] if len(symbol) == 6 else "USD",
                    "currency_profit": symbol[3:6] if len(symbol) == 6 else "USD",
                    "currency_margin": symbol[:3] if len(symbol) == 6 else "USD"
                }
        return None

    def get_market_symbols(self) -> List[Dict[str, Any]]:
        """Retrieves list of Market Watch symbols or standard major instruments."""
        results = []
        if self.is_live:
            try:
                symbols = mt5.symbols_get()
                if symbols:
                    # Filter for visible / select Market Watch symbols
                    mw_symbols = [s for s in symbols if s.visible or s.select]
                    if not mw_symbols:
                        mw_symbols = symbols[:30]  # First 30 if none marked
                    
                    for s in mw_symbols:
                        spec = self.get_symbol_specs(s.name)
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
            try:
                acc = mt5.account_info()
                acc_leverage = float(acc.leverage) if (acc and acc.leverage > 0) else 300.0
                raw_margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, lots, price)
                if raw_margin is not None and raw_margin > 0:
                    scale = (acc_leverage / leverage) if leverage > 0 else 1.0
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


feed = MT5RiskFeed(mock_mode=False)

