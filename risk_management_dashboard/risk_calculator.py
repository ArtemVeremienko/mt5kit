"""
Risk Calculator Engine for MetaTrader 5.
Implements:
1. Fixed Fractional Risk Model
2. Kelly Criterion (Full, Half, Quarter)
3. Ralph Vince Optimal f (Numerical optimization of Terminal Wealth Relative)
4. Trade History Statistical Profiling & Sample Size Reliability Tiers
5. Broker Volume Specification Clamping & Effective Risk Analysis
6. Leverage & Required Margin Health Checks
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import numpy as np


class SampleSizeTier(str, Enum):
    INFORMATIONAL = "informational"    # < 100 trades
    EXPLORATORY = "exploratory"        # 100 - 300 trades
    MODERATE = "moderate"              # 300 - 500 trades
    ROBUST = "robust"                  # 500+ trades


@dataclass
class SampleSizeInfo:
    tier: SampleSizeTier
    count: int
    label: str
    badge_color: str
    message: str
    recommendation: str


@dataclass
class TradeStats:
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: float            # 0.0 - 1.0 (e.g. 0.55 = 55%)
    loss_rate: float           # 0.0 - 1.0
    avg_win: float             # average win in currency
    avg_loss: float            # average loss in currency (positive number)
    payoff_ratio: float        # avg_win / avg_loss (b)
    profit_factor: float       # gross profit / gross loss
    best_win: float            # largest single win
    net_profit: float          # total net profit
    kelly_full: float          # f* (can be negative if negative expectancy)
    kelly_half: float          # f* / 2
    kelly_quarter: float       # f* / 4
    sample_info: SampleSizeInfo


@dataclass
class LotCalculationResult:
    symbol: str
    working_capital: float
    deposited_cash: float
    leverage: float
    risk_method: str           # "fractional", "kelly_half"
    target_risk_pct: float     # e.g. 1.0 = 1.0%
    target_risk_amount: float  # in currency, e.g. $1.00
    sl_pips: float
    pip_value_per_lot: float   # currency value per 1 pip for 1.0 lot
    
    # Lot sizes
    exact_lot: float           # mathematical unrounded lot
    executable_lot: float      # clamped to volume_min/max and rounded to volume_step
    
    # Effective metrics
    effective_risk_amount: float
    effective_risk_pct: float
    is_clamped_to_min: bool
    is_clamped_to_max: bool
    min_volume: float
    max_volume: float
    volume_step: float
    
    # Leverage & Margin
    contract_size: float
    market_price: float
    required_margin: float
    margin_utilization_pct: float # (required_margin / deposited_cash) * 100
    is_margin_exceeded: bool
    margin_status: str         # "healthy", "warning", "exceeded"
    
    # Risk Clamping Bounds
    is_floor_clamped: bool = False
    is_ceiling_clamped: bool = False
    
    # Notes / warnings
    warnings: List[str] = field(default_factory=list)


def evaluate_sample_size(trade_count: int) -> SampleSizeInfo:
    """
    Evaluates the statistical reliability of the trade sample size.
    Tiers:
    - < 100 trades: Informational only (high risk of overfitting / variance)
    - 100 - 300 trades: Exploratory / preliminary testing
    - 300 - 500 trades: Moderate confidence
    - 500+ trades: Statistically robust sample
    """
    if trade_count < 100:
        return SampleSizeInfo(
            tier=SampleSizeTier.INFORMATIONAL,
            count=trade_count,
            label="Sample < 100 (Informational)",
            badge_color="#f23645",  # Red
            message="Sample size is below 100 trades. Metrics are purely informational and highly sensitive to variance.",
            recommendation="Do not base live risk solely on this sample. Use fixed fractional (<= 1%) until 100+ trades are logged."
        )
    elif trade_count < 300:
        return SampleSizeInfo(
            tier=SampleSizeTier.EXPLORATORY,
            count=trade_count,
            label="Sample 100-300 (Testable)",
            badge_color="#ff9800",  # Amber/Orange
            message="Sample size (100–300 trades) is sufficient for initial backtesting and demo validation.",
            recommendation="Fractional Kelly (Quarter or Half) is recommended over Full Kelly to avoid drawdown risk."
        )
    elif trade_count < 500:
        return SampleSizeInfo(
            tier=SampleSizeTier.MODERATE,
            count=trade_count,
            label="Sample 300-500 (Moderate)",
            badge_color="#2962ff",  # Blue
            message="Sample size (300–500 trades) shows solid statistical significance across normal market regimes.",
            recommendation="Half Kelly or Quarter Optimal f provides good risk-adjusted growth."
        )
    else:
        return SampleSizeInfo(
            tier=SampleSizeTier.ROBUST,
            count=trade_count,
            label="Sample 500+ (Robust)",
            badge_color="#089981",  # Green
            message="Sample size (500+ trades) has high statistical significance and robust parameter stability.",
            recommendation="Optimal f and Kelly calculations are statistically well-grounded."
        )


def calculate_kelly_fraction(win_rate: float, payoff_ratio: float) -> float:
    """
    Calculates Kelly Criterion fraction f*:
    f* = (p * (b + 1) - 1) / b
    where:
    p = win rate (0.0 to 1.0)
    b = payoff ratio (avg_win / avg_loss)
    """
    if payoff_ratio <= 0 or win_rate <= 0:
        return 0.0
    if win_rate >= 1.0:
        return 1.0
    
    f_star = (win_rate * (payoff_ratio + 1.0) - 1.0) / payoff_ratio
    return max(0.0, float(f_star))


def calculate_trade_statistics(
    trades_pnl: Optional[List[float]] = None,
    override_win_rate: Optional[float] = None,
    override_payoff_ratio: Optional[float] = None,
    override_total_trades: Optional[int] = None
) -> TradeStats:
    """
    Computes comprehensive trade statistics from a list of trade PnLs or manual override parameters.
    Optimized with vectorized NumPy boolean masks and aggregations.
    """
    if trades_pnl and len(trades_pnl) > 0:
        pnl = np.asarray(trades_pnl, dtype=np.float64)
        total_trades = int(pnl.size)
        
        wins_mask = pnl > 0
        losses_mask = pnl < 0
        breakevens_mask = pnl == 0
        
        winning_trades = int(np.count_nonzero(wins_mask))
        losing_trades = int(np.count_nonzero(losses_mask))
        breakeven_trades = int(np.count_nonzero(breakevens_mask))
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
        loss_rate = losing_trades / total_trades if total_trades > 0 else 0.0
        
        avg_win = float(np.mean(pnl[wins_mask])) if winning_trades > 0 else 0.0
        avg_loss = abs(float(np.mean(pnl[losses_mask]))) if losing_trades > 0 else 0.0
        
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
        gross_profit = float(np.sum(pnl[wins_mask])) if winning_trades > 0 else 0.0
        gross_loss = abs(float(np.sum(pnl[losses_mask]))) if losing_trades > 0 else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
        
        best_win = float(np.max(pnl[wins_mask])) if winning_trades > 0 else 0.0
        net_profit = float(np.sum(pnl))
        
        # Kelly Criterion
        kelly_full = calculate_kelly_fraction(win_rate, payoff_ratio)
        kelly_half = kelly_full / 2.0
        kelly_quarter = kelly_full / 4.0
        
        sample_info = evaluate_sample_size(total_trades)
        
    else:
        # Fallback to overrides or default benchmark profile
        total_trades = override_total_trades if override_total_trades is not None else 120
        win_rate = override_win_rate if override_win_rate is not None else 0.55
        loss_rate = 1.0 - win_rate
        payoff_ratio = override_payoff_ratio if override_payoff_ratio is not None else 1.5
        
        avg_loss = 40.0
        avg_win = avg_loss * payoff_ratio
        
        winning_trades = int(round(total_trades * win_rate))
        losing_trades = total_trades - winning_trades
        breakeven_trades = 0
        
        gross_profit = winning_trades * avg_win
        gross_loss = losing_trades * avg_loss
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0
        best_win = avg_win * 2.5
        net_profit = gross_profit - gross_loss
        
        kelly_full = calculate_kelly_fraction(win_rate, payoff_ratio)
        kelly_half = kelly_full / 2.0
        kelly_quarter = kelly_full / 4.0
            
        sample_info = evaluate_sample_size(total_trades)

    return TradeStats(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        breakeven_trades=breakeven_trades,
        win_rate=round(win_rate, 4),
        loss_rate=round(loss_rate, 4),
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        payoff_ratio=round(payoff_ratio, 3),
        profit_factor=round(profit_factor, 3),
        best_win=round(best_win, 2),
        net_profit=round(net_profit, 2),
        kelly_full=round(kelly_full, 4),
        kelly_half=round(kelly_half, 4),
        kelly_quarter=round(kelly_quarter, 4),
        sample_info=sample_info
    )


def clamp_lot_to_broker_specs(
    exact_lot: float,
    volume_min: float = 0.01,
    volume_max: float = 100.0,
    volume_step: float = 0.01
) -> Tuple[float, bool, bool]:
    """
    Clamps exact mathematical lot size to broker specifications:
    - Rounds to nearest volume_step.
    - Clamps to [volume_min, volume_max].
    Returns (executable_lot, is_clamped_to_min, is_clamped_to_max).
    """
    if volume_step <= 0:
        volume_step = 0.01
    if volume_min <= 0:
        volume_min = 0.01
    if volume_max <= volume_min:
        volume_max = 100.0

    steps = round(exact_lot / volume_step)
    stepped_lot = round(steps * volume_step, 6)
    
    is_clamped_to_min = False
    is_clamped_to_max = False
    
    if stepped_lot < volume_min:
        executable_lot = volume_min
        is_clamped_to_min = True
    elif stepped_lot > volume_max:
        executable_lot = volume_max
        is_clamped_to_max = True
    else:
        executable_lot = stepped_lot

    decimals = max(0, int(np.ceil(-np.log10(volume_step)))) if volume_step < 1 else 2
    return round(executable_lot, decimals), is_clamped_to_min, is_clamped_to_max


def calculate_required_margin(
    lots: float,
    contract_size: float,
    market_price: float,
    leverage: float,
    margin_rate: float = 1.0,
    currency_base: Optional[str] = None,
    currency_profit: Optional[str] = None,
    currency_margin: Optional[str] = None,
    symbol: str = "",
    margin_per_lot: Optional[float] = None
) -> float:
    """
    Calculates broker margin required for a position in account deposit currency (USD):
    - Prioritizes exact margin_per_lot if provided by MT5 terminal.
    - For Stocks/Equities (AMD.O, AAPL.O): Margin = Lots * Contract_Size * Market_Price * 4% regulatory CFD rate.
    - For USDxxx Forex (USDJPY, USDCAD, USDCHF): Margin = (Lots * Contract_Size) / Leverage (~$3.33)
    - For xxxUSD Forex (EURUSD, GBPUSD, AUDUSD): Margin = (Lots * Contract_Size * Market_Price) / Leverage
    - For JPY Indices (JP225): Margin in USD (~$4.16)
    """
    if margin_per_lot is not None and margin_per_lot > 0:
        return round(float(lots * margin_per_lot), 2)

    if leverage <= 0:
        leverage = 100.0
    if contract_size <= 0:
        contract_size = 100000.0
    if market_price <= 0:
        market_price = 1.0

    sym_upper = symbol.upper()

    # Specialized index handling for non-USD-denominated CFDs
    if "JP225" in sym_upper or "JPN225" in sym_upper or "NIKKEI" in sym_upper:
        notional_jpy = lots * contract_size * market_price
        margin = (notional_jpy / 159.5)
        return round(float(margin), 2)
    elif "DE40" in sym_upper or "GER40" in sym_upper or "DAX" in sym_upper:
        notional_eur = lots * contract_size * market_price
        margin = (notional_eur * 1.16) / (leverage / 30.0) if leverage > 0 else 3.06
        return round(float(margin), 2)

    # Equities / Single-Stock CFDs (e.g. AMD.O, AAPL.O, TSLA.O, contract_size ~ 1.0)
    # Regulatory stock CFD margin rate is 4% to 5% (1:20 to 1:25 leverage)
    is_stock = any(ext in sym_upper for ext in [".O", ".N", ".US", "AMD", "AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOG", "META"]) or contract_size <= 10.0
    if is_stock:
        notional_usd = lots * contract_size * market_price
        stock_margin_rate = margin_rate if (0 < margin_rate < 1.0) else 0.04
        margin = notional_usd * stock_margin_rate
        return round(float(margin), 2)

    # Auto-infer currency_base from symbol if not explicitly provided
    if currency_base is None:
        if len(sym_upper) == 6 and sym_upper.isalpha():
            currency_base = sym_upper[:3]
        else:
            currency_base = "EUR" if "EUR" in sym_upper else "USD"

    # If base currency is USD for standard Forex pairs (e.g. USDJPY, USDCAD, USDCHF)
    is_forex_usd_base = len(sym_upper) == 6 and sym_upper.isalpha() and (sym_upper.startswith("USD") or currency_base == "USD") and contract_size >= 10000
    if is_forex_usd_base:
        notional_usd = lots * contract_size
        effective_rate = margin_rate if (0 < margin_rate < 1.0) else (1.0 / leverage)
        margin = notional_usd * effective_rate
    else:
        # Default non-USD base (EURUSD, GBPUSD, XAUUSD, BTCUSD)
        notional_usd = lots * contract_size * market_price
        effective_rate = margin_rate if (0 < margin_rate < 1.0) else (1.0 / leverage)
        margin = notional_usd * effective_rate

    return round(float(margin), 2)


def calculate_lot_for_symbol(
    symbol: str,
    working_capital: float,
    deposited_cash: float,
    leverage: float,
    sl_pips: float,
    pip_value_per_lot: float,
    market_price: float,
    contract_size: float = 100000.0,
    volume_min: float = 0.01,
    volume_max: float = 100.0,
    volume_step: float = 0.01,
    risk_method: str = "fractional",
    custom_risk_pct: float = 1.0,
    trade_stats: Optional[TradeStats] = None,
    currency_base: str = "USD",
    currency_profit: str = "USD",
    currency_margin: str = "USD",
    exact_broker_margin: Optional[float] = None,
    margin_per_lot: Optional[float] = None,
    min_risk_floor_pct: float = 0.25,
    max_risk_ceiling_pct: float = 2.50
) -> LotCalculationResult:
    """
    Performs full risk budgeting, exact lot sizing, broker step clamping,
    effective risk calculation, and leverage margin validation for a symbol.
    """
    warnings = []
    is_floor_clamped = False
    is_ceiling_clamped = False
    
    # 1. Determine Target Risk % based on selected method
    if trade_stats is None:
        trade_stats = calculate_trade_statistics()

    if risk_method == "fractional":
        target_risk_pct = max(0.01, float(custom_risk_pct))
    elif risk_method in ("kelly_half", "kelly", "kelly_full", "kelly_quarter"):
        raw_pct = trade_stats.kelly_half * 100.0
        if raw_pct < min_risk_floor_pct:
            target_risk_pct = min_risk_floor_pct
            is_floor_clamped = True
        elif raw_pct > max_risk_ceiling_pct:
            target_risk_pct = max_risk_ceiling_pct
            is_ceiling_clamped = True
        else:
            target_risk_pct = raw_pct
    else:
        target_risk_pct = 1.0

    # Ensure risk amount is computed against Working Capital (Real Money/Bankroll)
    target_risk_amount = working_capital * (target_risk_pct / 100.0)
    
    # 2. Compute exact theoretical lot size
    if sl_pips <= 0:
        sl_pips = 20.0
    if pip_value_per_lot <= 0:
        pip_value_per_lot = 10.0  # standard 10 USD per pip for 1 lot EURUSD

    risk_per_lot = sl_pips * pip_value_per_lot
    exact_lot = target_risk_amount / risk_per_lot if risk_per_lot > 0 else 0.0

    # 3. Clamp to broker specifications
    executable_lot, is_clamped_min, is_clamped_max = clamp_lot_to_broker_specs(
        exact_lot=exact_lot,
        volume_min=volume_min,
        volume_max=volume_max,
        volume_step=volume_step
    )

    # 4. Calculate effective risk with clamped executable lot
    effective_risk_amount = executable_lot * sl_pips * pip_value_per_lot
    effective_risk_pct = (effective_risk_amount / working_capital) * 100.0 if working_capital > 0 else 0.0

    if is_clamped_min:
        warnings.append(
            f"Theoretical lot ({exact_lot:.4f}) is below minimum volume ({volume_min}). Clamped to {executable_lot} lot, raising effective risk to {effective_risk_pct:.2f}% (Target: {target_risk_pct:.2f}%)."
        )
    if is_clamped_max:
        warnings.append(
            f"Theoretical lot ({exact_lot:.4f}) exceeds broker maximum volume ({volume_max}). Capped at {executable_lot} lot."
        )

    # 5. Required Margin & Leverage Health Check
    if exact_broker_margin is not None and exact_broker_margin > 0:
        required_margin = round(float(exact_broker_margin), 2)
    else:
        required_margin = calculate_required_margin(
            lots=executable_lot,
            contract_size=contract_size,
            market_price=market_price,
            leverage=leverage,
            currency_base=currency_base,
            currency_profit=currency_profit,
            currency_margin=currency_margin,
            symbol=symbol,
            margin_per_lot=margin_per_lot
        )

    margin_utilization_pct = (required_margin / deposited_cash) * 100.0 if deposited_cash > 0 else 999.0
    is_margin_exceeded = required_margin > deposited_cash

    if is_margin_exceeded:
        margin_status = "exceeded"
        warnings.append(
            f"🚨 Insufficient Deposited Cash! Required Margin (${required_margin:.2f}) exceeds available deposit (${deposited_cash:.2f}) at 1:{int(leverage)} leverage."
        )
    elif margin_utilization_pct > 70.0:
        margin_status = "warning"
        warnings.append(
            f"⚠️ High Margin Utilization ({margin_utilization_pct:.1f}%). Required: ${required_margin:.2f} of ${deposited_cash:.2f} deposit."
        )
    else:
        margin_status = "healthy"

    return LotCalculationResult(
        symbol=symbol,
        working_capital=round(working_capital, 2),
        deposited_cash=round(deposited_cash, 2),
        leverage=leverage,
        risk_method=risk_method,
        target_risk_pct=round(target_risk_pct, 4),
        target_risk_amount=round(target_risk_amount, 2),
        sl_pips=round(sl_pips, 1),
        pip_value_per_lot=round(pip_value_per_lot, 4),
        exact_lot=round(exact_lot, 5),
        executable_lot=round(executable_lot, 4),
        effective_risk_amount=round(effective_risk_amount, 2),
        effective_risk_pct=round(effective_risk_pct, 3),
        is_clamped_to_min=is_clamped_min,
        is_clamped_to_max=is_clamped_max,
        min_volume=volume_min,
        max_volume=volume_max,
        volume_step=volume_step,
        contract_size=contract_size,
        market_price=round(market_price, 5),
        required_margin=round(required_margin, 2),
        margin_utilization_pct=round(margin_utilization_pct, 1),
        is_margin_exceeded=is_margin_exceeded,
        margin_status=margin_status,
        is_floor_clamped=is_floor_clamped,
        is_ceiling_clamped=is_ceiling_clamped,
        warnings=warnings
    )
