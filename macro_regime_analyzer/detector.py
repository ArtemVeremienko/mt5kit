"""
Macro Regime Detection and Market Structure Segmentation Engine.
Combines multi-scale quantitative metrics (KER 10d, 50d, 100d, Overlap, Range Expansion)
with H4/D1 Swing Pivot structure to segment time series into macro periods.
Calculates Directional Asymmetry Index (DAI) and multi-period cumulative returns.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from .config import (
    CHOP_VOLATILITY_RATIO,
    CYCLE_SCALE_PRESETS,
    DEFAULT_CYCLE_SCALE,
    RANGE_KER_THRESHOLD,
    RANGE_OVERLAP_THRESHOLD,
    ROLLING_EFFICIENCY_WINDOW,
    SHORT_EFFICIENCY_WINDOW,
    SWING_PIVOT_BARS_D1,
    SWING_PIVOT_BARS_H4,
    TREND_KER_THRESHOLD,
)
from .models import (
    AsymmetryCharacter,
    DayMacroMetrics,
    MacroAssetProfile,
    MacroPeriod,
    MacroRegimeType,
    PivotType,
    SwingPivot,
    SymbolInfo,
)

logger = logging.getLogger("macro_regime_analyzer")


class MacroRegimeDetector:
    """
    Analyzes multi-year price data to identify temporal macro trend and range periods,
    measure Bull/Bear asymmetry, and evaluate multi-scale cycle persistence.
    """

    def __init__(
        self,
        cycle_scale: str = DEFAULT_CYCLE_SCALE,
        ker_window: Optional[int] = None,
        short_ker_window: Optional[int] = None,
        overlap_window: Optional[int] = None,
        trend_ker_thresh: Optional[float] = None,
        range_ker_thresh: Optional[float] = None,
    ):
        preset = CYCLE_SCALE_PRESETS.get(cycle_scale.lower(), CYCLE_SCALE_PRESETS["swing"])
        self.cycle_scale_name = cycle_scale.lower()
        self.ker_window = ker_window or preset["ker_window"]
        self.short_ker_window = short_ker_window or preset["short_ker_window"]
        self.overlap_window = overlap_window or preset["overlap_window"]
        self.trend_ker_thresh = trend_ker_thresh or preset["trend_ker_thresh"]
        self.range_ker_thresh = range_ker_thresh or preset["range_ker_thresh"]
        self.overlap_thresh = RANGE_OVERLAP_THRESHOLD

    def detect_swing_pivots(
        self, df: pd.DataFrame, left_bars: int = SWING_PIVOT_BARS_H4, right_bars: int = SWING_PIVOT_BARS_H4, tf_name: str = "H4"
    ) -> List[SwingPivot]:
        """
        Extracts verified swing highs and swing lows using a rolling extrema window.
        """
        if df.empty or len(df) < (left_bars + right_bars + 1):
            return []

        pivots: List[SwingPivot] = []
        highs = df["high"].values
        lows = df["low"].values
        times = df.index

        n = len(df)
        for i in range(left_bars, n - right_bars):
            curr_h = highs[i]
            curr_l = lows[i]

            # Check Swing High
            is_high = True
            for k in range(i - left_bars, i + right_bars + 1):
                if k != i and highs[k] >= curr_h:
                    is_high = False
                    break

            if is_high:
                pivots.append(
                    SwingPivot(
                        timestamp=times[i],
                        date_str=times[i].strftime("%Y-%m-%d %H:%M"),
                        price=float(curr_h),
                        pivot_type=PivotType.SWING_HIGH,
                        timeframe=tf_name,
                        confirmed_bar_index=i + right_bars,
                    )
                )

            # Check Swing Low
            is_low = True
            for k in range(i - left_bars, i + right_bars + 1):
                if k != i and lows[k] <= curr_l:
                    is_low = False
                    break

            if is_low:
                pivots.append(
                    SwingPivot(
                        timestamp=times[i],
                        date_str=times[i].strftime("%Y-%m-%d %H:%M"),
                        price=float(curr_l),
                        pivot_type=PivotType.SWING_LOW,
                        timeframe=tf_name,
                        confirmed_bar_index=i + right_bars,
                    )
                )

        pivots.sort(key=lambda p: p.timestamp)
        return pivots

    def compute_multi_period_returns(self, df_d1: pd.DataFrame) -> Dict[str, Optional[float]]:
        """
        Calculates cumulative percentage returns across standard financial periods (YTD, 1Y, 2Y, 3Y, 5Y, 10Y).
        """
        if df_d1.empty:
            return {}

        current_close = float(df_d1["close"].iloc[-1])
        current_date = df_d1.index[-1]
        returns: Dict[str, Optional[float]] = {}

        # 1. YTD
        df_ytd = df_d1[df_d1.index.year == current_date.year]
        if not df_ytd.empty:
            ytd_open = float(df_ytd["open"].iloc[0])
            returns["YTD"] = round(((current_close - ytd_open) / ytd_open) * 100.0, 2)
        else:
            returns["YTD"] = None

        # Multi-Year Horizons
        horizons = {
            "1Y": 365,
            "2Y": int(2 * 365.25),
            "3Y": int(3 * 365.25),
            "5Y": int(5 * 365.25),
            "10Y": int(10 * 365.25),
        }

        for label, days in horizons.items():
            cutoff = current_date - pd.Timedelta(days=days)
            df_sub = df_d1[df_d1.index >= cutoff]
            if not df_sub.empty and len(df_sub) >= min(20, days // 5):
                start_p = float(df_sub["open"].iloc[0])
                ret = ((current_close - start_p) / start_p) * 100.0
                returns[label] = round(ret, 2)
            else:
                returns[label] = None

        return returns

    def compute_daily_metrics(
        self, df_d1: pd.DataFrame, sym_info: SymbolInfo
    ) -> Tuple[pd.DataFrame, List[DayMacroMetrics]]:
        """
        Computes rolling multi-scale metrics on daily bars.
        """
        df = df_d1.copy()
        pip_size = sym_info.pip_size

        df["range_pips"] = (df["high"] - df["low"]) / pip_size
        df["body_pips"] = (df["close"] - df["open"]).abs() / pip_size
        df["adr_20"] = df["range_pips"].rolling(20, min_periods=1).mean()
        df["sma_20"] = df["close"].rolling(20, min_periods=1).mean()
        df["sma_50"] = df["close"].rolling(50, min_periods=1).mean()

        # Multi-Scale Kaufman Efficiency Ratios
        close_diff = df["close"].diff().abs()

        # 1. 10-Day KER (Swing Scale)
        net_disp_10 = (df["close"] - df["close"].shift(10)).abs()
        total_path_10 = close_diff.rolling(10, min_periods=1).sum()
        df["ker_10d"] = np.where(total_path_10 > 0, net_disp_10 / total_path_10, 0.0)

        # 2. 50-Day KER (Macro Scale)
        net_disp_50 = (df["close"] - df["close"].shift(50)).abs()
        total_path_50 = close_diff.rolling(50, min_periods=1).sum()
        df["ker_50d"] = np.where(total_path_50 > 0, net_disp_50 / total_path_50, 0.0)

        # 3. 100-Day KER (Secular Scale)
        net_disp_100 = (df["close"] - df["close"].shift(100)).abs()
        total_path_100 = close_diff.rolling(100, min_periods=1).sum()
        df["ker_100d"] = np.where(total_path_100 > 0, net_disp_100 / total_path_100, 0.0)

        # Active Primary KER based on configured scale
        net_disp_active = (df["close"] - df["close"].shift(self.ker_window)).abs()
        total_path_active = close_diff.rolling(self.ker_window, min_periods=1).sum()
        df["ker_active"] = np.where(total_path_active > 0, net_disp_active / total_path_active, 0.0)
        df["displacement_active_pips"] = (df["close"] - df["close"].shift(self.ker_window)) / pip_size

        # Short-term KER
        net_disp_short = (df["close"] - df["close"].shift(self.short_ker_window)).abs()
        total_path_short = close_diff.rolling(self.short_ker_window, min_periods=1).sum()
        df["ker_short"] = np.where(total_path_short > 0, net_disp_short / total_path_short, 0.0)
        df["displacement_short_pips"] = (df["close"] - df["close"].shift(self.short_ker_window)) / pip_size

        # Daily Bar Overlap Ratio (ROR)
        highs = df["high"].values
        lows = df["low"].values
        n = len(df)
        overlaps = np.zeros(n)
        for i in range(1, n):
            h_curr, l_curr = highs[i], lows[i]
            h_prev, l_prev = highs[i - 1], lows[i - 1]
            inter_h = min(h_curr, h_prev)
            inter_l = max(l_curr, l_prev)
            overlap_len = max(0.0, inter_h - inter_l)
            min_range = min(h_curr - l_curr, h_prev - l_prev)
            overlaps[i] = (overlap_len / min_range) if min_range > 0 else 0.0

        df["bar_overlap"] = overlaps
        df["overlap_ratio_active"] = df["bar_overlap"].rolling(self.overlap_window, min_periods=1).mean()
        df["overlap_ratio_5d"] = df["bar_overlap"].rolling(5, min_periods=1).mean()

        # Range Expansion Index (REI)
        roll_high_short = df["high"].rolling(self.short_ker_window, min_periods=1).max()
        roll_low_short = df["low"].rolling(self.short_ker_window, min_periods=1).min()
        span_short = roll_high_short - roll_low_short
        sum_range_short = (df["high"] - df["low"]).rolling(self.short_ker_window, min_periods=1).sum()
        df["range_expansion_index_5d"] = np.where(sum_range_short > 0, span_short / sum_range_short, 0.0)

        # Classify candidate regime for each day
        records: List[DayMacroMetrics] = []
        raw_regimes: List[MacroRegimeType] = []

        for idx, row in df.iterrows():
            ts = idx
            date_str = ts.strftime("%Y-%m-%d")
            ker_act = float(row["ker_active"])
            ker_sht = float(row["ker_short"])
            ker10 = float(row["ker_10d"])
            ker50 = float(row["ker_50d"])
            ker100 = float(row["ker_100d"])
            overlap_act = float(row["overlap_ratio_active"])
            overlap5 = float(row["overlap_ratio_5d"])
            rei = float(row["range_expansion_index_5d"])
            disp_act = float(row["displacement_active_pips"])
            disp_sht = float(row["displacement_short_pips"])
            close_p = float(row["close"])
            sma20 = float(row["sma_20"])
            range_pips = float(row["range_pips"])
            adr20 = float(row["adr_20"])

            # Classification logic
            is_bullish_momentum = (
                (ker_act >= self.trend_ker_thresh or (ker_sht >= 0.40 and rei >= 0.60))
                and disp_act > 0
                and (close_p >= sma20 or disp_sht > 0)
            )
            is_bearish_momentum = (
                (ker_act >= self.trend_ker_thresh or (ker_sht >= 0.40 and rei >= 0.60))
                and disp_act < 0
                and (close_p <= sma20 or disp_sht < 0)
            )

            if is_bullish_momentum:
                reg = MacroRegimeType.BULL_TREND
            elif is_bearish_momentum:
                reg = MacroRegimeType.BEAR_TREND
            elif ker_act < self.range_ker_thresh and ker_sht < 0.25 and (range_pips >= 0.90 * adr20 or rei < 0.38):
                reg = MacroRegimeType.VOLATILE_CHOP
            else:
                reg = MacroRegimeType.TRADING_RANGE

            raw_regimes.append(reg)
            rec = DayMacroMetrics(
                date_str=date_str,
                timestamp=ts,
                open_price=float(row["open"]),
                high_price=float(row["high"]),
                low_price=float(row["low"]),
                close_price=close_p,
                range_pips=round(range_pips, 1),
                body_pips=round(float(row["body_pips"]), 1),
                ker_5d=round(ker_sht, 3),
                ker_10d=round(ker10, 3),
                ker_50d=round(ker50, 3),
                ker_100d=round(ker100, 3),
                overlap_ratio_5d=round(overlap5, 3),
                range_expansion_index_5d=round(rei, 3),
                adr_20=round(adr20, 1),
                assigned_regime=reg,
                displacement_10d_pips=round(disp_act, 1),
            )
            records.append(rec)

        df["raw_regime"] = [r.value for r in raw_regimes]
        return df, records

    def segment_macro_periods(
        self, df_d1: pd.DataFrame, daily_records: List[DayMacroMetrics], sym_info: SymbolInfo
    ) -> List[MacroPeriod]:
        """
        Applies state-machine smoothing with hysteresis to group daily observations into contiguous MacroPeriods.
        """
        if not daily_records:
            return []

        # Smooth raw regimes: require 2-bar persistence to switch
        smoothed_regimes: List[MacroRegimeType] = []
        current_state = daily_records[0].assigned_regime
        smoothed_regimes.append(current_state)

        for i in range(1, len(daily_records)):
            candidate = daily_records[i].assigned_regime
            if candidate != current_state:
                if i + 1 < len(daily_records):
                    next_cand = daily_records[i + 1].assigned_regime
                    if next_cand == candidate:
                        current_state = candidate
                else:
                    current_state = candidate
            smoothed_regimes.append(current_state)

        for i, rec in enumerate(daily_records):
            rec.assigned_regime = smoothed_regimes[i]

        periods: List[MacroPeriod] = []
        period_id = 1
        p_start_idx = 0
        p_regime = smoothed_regimes[0]
        pip_size = sym_info.pip_size

        for i in range(1, len(daily_records) + 1):
            if i == len(daily_records) or smoothed_regimes[i] != p_regime:
                p_end_idx = i - 1
                start_rec = daily_records[p_start_idx]
                end_rec = daily_records[p_end_idx]

                sub_records = daily_records[p_start_idx : p_end_idx + 1]
                high_p = max(r.high_price for r in sub_records)
                low_p = min(r.low_price for r in sub_records)
                start_p = start_rec.open_price
                end_p = end_rec.close_price

                disp_pips = (end_p - start_p) / pip_size
                channel_pips = (high_p - low_p) / pip_size
                path_pips = sum(r.range_pips for r in sub_records)
                efficiency = abs(disp_pips) / path_pips if path_pips > 0 else 0.0
                duration_days = len(sub_records)

                period_obj = MacroPeriod(
                    period_id=period_id,
                    regime=p_regime,
                    start_date=start_rec.date_str,
                    end_date=end_rec.date_str,
                    start_timestamp=start_rec.timestamp,
                    end_timestamp=end_rec.timestamp,
                    duration_days=duration_days,
                    start_price=round(start_p, sym_info.digits),
                    end_price=round(end_p, sym_info.digits),
                    displacement_pips=round(disp_pips, 1),
                    high_price=round(high_p, sym_info.digits),
                    low_price=round(low_p, sym_info.digits),
                    channel_range_pips=round(channel_pips, 1),
                    total_path_pips=round(path_pips, 1),
                    efficiency=round(efficiency, 3),
                    support_level=round(low_p, sym_info.digits),
                    resistance_level=round(high_p, sym_info.digits),
                )
                periods.append(period_obj)
                period_id += 1

                if i < len(daily_records):
                    p_start_idx = i
                    p_regime = smoothed_regimes[i]

        return periods

    def build_profile(
        self,
        symbol: str,
        sym_info: SymbolInfo,
        df_d1: pd.DataFrame,
        df_h4: Optional[pd.DataFrame] = None,
        lookback_days: int = 730,
    ) -> Optional[MacroAssetProfile]:
        """
        Executes full macro analysis and constructs the MacroAssetProfile with Asymmetry metrics.
        """
        if df_d1.empty or len(df_d1) < 20:
            logger.error(f"Insufficient D1 data for {symbol}")
            return None

        # 1. Compute Daily Metrics
        df_d1_enriched, daily_records = self.compute_daily_metrics(df_d1, sym_info)

        # 2. Extract H4 / D1 Swing Pivots
        pivots: List[SwingPivot] = []
        if df_h4 is not None and not df_h4.empty:
            pivots = self.detect_swing_pivots(df_h4, left_bars=SWING_PIVOT_BARS_H4, right_bars=SWING_PIVOT_BARS_H4, tf_name="H4")
        else:
            pivots = self.detect_swing_pivots(df_d1_enriched, left_bars=SWING_PIVOT_BARS_D1, right_bars=SWING_PIVOT_BARS_D1, tf_name="D1")

        # 3. Segment into Contiguous Periods
        periods = self.segment_macro_periods(df_d1_enriched, daily_records, sym_info)
        total_days = len(daily_records)
        if total_days == 0 or not periods:
            return None

        # 4. Compute Aggregate Statistics
        bull_days = sum(p.duration_days for p in periods if p.regime == MacroRegimeType.BULL_TREND)
        bear_days = sum(p.duration_days for p in periods if p.regime == MacroRegimeType.BEAR_TREND)
        range_days = sum(p.duration_days for p in periods if p.regime == MacroRegimeType.TRADING_RANGE)
        chop_days = sum(p.duration_days for p in periods if p.regime == MacroRegimeType.VOLATILE_CHOP)

        bull_pct = (bull_days / total_days) * 100.0
        bear_pct = (bear_days / total_days) * 100.0
        range_pct = (range_days / total_days) * 100.0
        chop_pct = (chop_days / total_days) * 100.0

        # Calculate Directional Asymmetry Index (DAI) & Character
        if bear_pct > 0:
            dai = bull_pct / bear_pct
        else:
            dai = 10.0 if bull_pct > 0 else 1.0

        if dai >= 3.0:
            character = AsymmetryCharacter.SECULAR_BULL
        elif dai >= 1.5:
            character = AsymmetryCharacter.MODERATE_BULL
        elif dai <= 0.33:
            character = AsymmetryCharacter.SECULAR_BEAR
        elif dai <= 0.67:
            character = AsymmetryCharacter.MODERATE_BEAR
        else:
            character = AsymmetryCharacter.SYMMETRICAL_CHOP

        # Compute Multi-Period Returns
        multi_returns = self.compute_multi_period_returns(df_d1)

        # Multi-Scale latest efficiencies
        latest_rec = daily_records[-1]
        trend_periods = [p for p in periods if p.regime in (MacroRegimeType.BULL_TREND, MacroRegimeType.BEAR_TREND)]
        range_periods = [p for p in periods if p.regime == MacroRegimeType.TRADING_RANGE]

        avg_trend_dur = float(np.mean([p.duration_days for p in trend_periods])) if trend_periods else 0.0
        avg_range_dur = float(np.mean([p.duration_days for p in range_periods])) if range_periods else 0.0
        longest_trend = max([p.duration_days for p in trend_periods], default=0)
        longest_range = max([p.duration_days for p in range_periods], default=0)

        avg_adr = float(np.mean([r.range_pips for r in daily_records]))
        current_period = periods[-1]

        profile = MacroAssetProfile(
            symbol=sym_info.name,
            symbol_info=sym_info,
            lookback_days=lookback_days,
            total_trading_days=total_days,
            current_regime=current_period.regime,
            current_regime_age_days=current_period.duration_days,
            time_in_bull_trend_pct=round(bull_pct, 1),
            time_in_bear_trend_pct=round(bear_pct, 1),
            time_in_range_pct=round(range_pct, 1),
            time_in_chop_pct=round(chop_pct, 1),
            dai_ratio=round(dai, 2),
            character=character,
            cycle_scale_name=self.cycle_scale_name,
            returns_multi_period=multi_returns,
            latest_ker_10d=latest_rec.ker_10d,
            latest_ker_50d=latest_rec.ker_50d,
            latest_ker_100d=latest_rec.ker_100d,
            avg_trend_duration_days=round(avg_trend_dur, 1),
            avg_range_duration_days=round(avg_range_dur, 1),
            avg_daily_range_pips=round(avg_adr, 1),
            longest_trend_days=longest_trend,
            longest_range_days=longest_range,
            periods=periods,
            daily_records=daily_records,
            pivots_h4=pivots,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            df_d1=df_d1_enriched,
            df_h4=df_h4,
        )
        return profile
