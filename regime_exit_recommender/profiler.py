"""
Asset Behavior Profiler & Historical Exit Calibration Engine.
Decomposes 1-year historical days into Range, Semi-Trend, and Strong Trend regimes,
computes empirical distributions, and generates actionable exit playbooks.
"""
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from .models import (
    AssetBehaviorProfile,
    DayClassification,
    DayRegimeType,
    ExitStrategyType,
    RegimeDayStatistics,
    SymbolInfo,
)
from .mt5_data import fetch_rates_days, get_symbol_info

logger = logging.getLogger("regime_exit_recommender")


class AssetBehaviorProfiler:
    """
    Analyzes multi-month historical price dynamics to profile asset behavior,
    measure regime probabilities, and calibrate empirical exit parameters.
    """

    def __init__(self):
        pass

    def profile_asset(self, symbol: str, days: int = 365) -> Optional[AssetBehaviorProfile]:
        """
        Profiles a single symbol over the specified lookback horizon (default: 365 calendar days).
        """
        sym_clean = symbol.strip().upper()
        sym_info = get_symbol_info(sym_clean)
        if sym_info is None:
            logger.error(f"Could not retrieve symbol info for {sym_clean}")
            return None

        # Fetch Daily (D1) bars for daily categorization
        df_d1 = fetch_rates_days(sym_clean, "D1", days=days)
        if df_d1 is None or len(df_d1) < 20:
            logger.error(f"Insufficient D1 rates for {sym_clean} over {days} days")
            return None

        # Fetch Hourly (H1) bars for intraday swing decomposition
        df_h1 = fetch_rates_days(sym_clean, "H1", days=days)
        if df_h1 is None or len(df_h1) < 100:
            logger.warning(f"Hourly rates limited for {sym_clean}; falling back to daily-only stats.")
            df_h1 = pd.DataFrame()

        pip_size = sym_info.pip_size

        # Compute 20-day rolling Average Daily Range (ADR)
        df_d1["range_pips"] = (df_d1["high"] - df_d1["low"]) / pip_size
        df_d1["adr_20"] = df_d1["range_pips"].rolling(20).mean().bfill()

        # Classify each historical trading day
        daily_list: List[DayClassification] = []
        for idx, row in df_d1.iterrows():
            day_ts = idx
            date_str = day_ts.strftime("%Y-%m-%d")
            open_p = float(row["open"])
            high_p = float(row["high"])
            low_p = float(row["low"])
            close_p = float(row["close"])
            range_pips = float(row["range_pips"])
            body_pips = abs(close_p - open_p) / pip_size
            adr = float(row["adr_20"]) if row["adr_20"] > 0 else range_pips
            adr_mult = range_pips / adr if adr > 0 else 1.0

            # Retracement ratio: 0.0 = pure trend expansion, 1.0 = doji/full round-trip
            retrace_ratio = 1.0 - (body_pips / range_pips) if range_pips > 0 else 1.0
            retrace_ratio = float(np.clip(retrace_ratio, 0.0, 1.0))

            # Intraday H1 decomposition for this specific day
            ker_daily = 0.50
            first_leg_pips = body_pips
            max_pullback_pips = (range_pips - body_pips) / 2.0
            path_adr_mult = 1.0

            if not df_h1.empty:
                # Filter H1 bars for the current day
                day_start = day_ts.replace(hour=0, minute=0, second=0)
                day_end = day_ts.replace(hour=23, minute=59, second=59)
                day_h1 = df_h1.loc[(df_h1.index >= day_start) & (df_h1.index <= day_end)]

                if len(day_h1) >= 4:
                    h1_closes = day_h1["close"]
                    net_disp = abs(h1_closes.iloc[-1] - h1_closes.iloc[0])
                    path_len = h1_closes.diff().abs().sum()
                    ker_daily = float(net_disp / path_len) if path_len > 0 else 0.0
                    path_pips = path_len / pip_size
                    path_adr_mult = path_pips / adr if adr > 0 else 1.0

                    # Estimate largest intraday leg & pullback
                    h1_highs = day_h1["high"]
                    h1_lows = day_h1["low"]
                    cum_max = h1_highs.cummax()
                    drawdowns = (cum_max - h1_lows) / pip_size
                    max_pullback_pips = float(drawdowns.max()) if len(drawdowns) > 0 else 0.0
                    first_leg_pips = max(body_pips, range_pips - max_pullback_pips)

            # Classify Day Regime (4-Regime Taxonomy):
            # 1. Strong Trend Day: Solid directional body, high intraday velocity, and range expansion (<30% pullback)
            if retrace_ratio <= 0.35 and ker_daily >= 0.45 and adr_mult >= 0.75:
                regime = DayRegimeType.STRONG_TREND_DAY
            # 2. V-Shape Reversal Day: Deep EOD retracement (looks flat/small body on D1) BUT large daily range (>=0.80 ADR), large first leg (>=0.50 ADR), and high kinetic path / large adverse swing
            elif retrace_ratio >= 0.60 and adr_mult >= 0.80 and (first_leg_pips >= 0.50 * adr or range_pips >= 1.0 * adr) and (path_adr_mult >= 1.5 or max_pullback_pips >= 0.50 * adr):
                regime = DayRegimeType.V_SHAPE_REVERSAL_DAY
            # 3. Range Day: High retracement (body < 35% of range) OR low intraday efficiency with normal/small range
            elif retrace_ratio >= 0.65 or (ker_daily < 0.22 and retrace_ratio >= 0.50):
                regime = DayRegimeType.RANGE_DAY
            # 4. Semi-Trending Day: Moderate pullbacks, ascending/descending compression channels (e.g. Aug 4-5)
            else:
                regime = DayRegimeType.SEMI_TREND_DAY

            day_obj = DayClassification(
                date_str=date_str,
                timestamp=day_ts,
                regime=regime,
                open_price=open_p,
                high_price=high_p,
                low_price=low_p,
                close_price=close_p,
                range_pips=round(range_pips, 1),
                body_pips=round(body_pips, 1),
                retracement_ratio=round(retrace_ratio, 3),
                ker_daily=round(ker_daily, 3),
                adr_multiple=round(adr_mult, 2),
                first_leg_pips=round(first_leg_pips, 1),
                max_pullback_pips=round(max_pullback_pips, 1),
            )
            daily_list.append(day_obj)

        total_days = len(daily_list)
        if total_days == 0:
            return None

        # 2. Compute Aggregated Regime Statistics
        regime_stats = self._calculate_regime_statistics(daily_list, sym_info)
        avg_adr = float(np.mean([d.range_pips for d in daily_list]))

        profile = AssetBehaviorProfile(
            symbol=sym_clean,
            symbol_info=sym_info,
            lookback_days=days,
            total_trading_days=total_days,
            avg_daily_range_pips=round(avg_adr, 1),
            regime_stats=regime_stats,
            daily_classifications=daily_list,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            df_h1=df_h1,
        )
        return profile

    def _calculate_regime_statistics(
        self, daily_list: List[DayClassification], sym_info: SymbolInfo
    ) -> Dict[DayRegimeType, RegimeDayStatistics]:
        """Calculates quantile distributions and empirical exit rules for each regime."""
        total = len(daily_list)
        stats_dict: Dict[DayRegimeType, RegimeDayStatistics] = {}

        spread_pips = sym_info.spread_pips

        for reg in DayRegimeType:
            sub = [d for d in daily_list if d.regime == reg]
            count = len(sub)
            freq_pct = (count / total) * 100.0 if total > 0 else 0.0

            if count == 0:
                # Empty placeholder
                stats_dict[reg] = RegimeDayStatistics(
                    regime=reg,
                    days_count=0,
                    frequency_pct=0.0,
                    median_range_pips=0.0,
                    p25_range_pips=0.0,
                    p75_range_pips=0.0,
                    p90_range_pips=0.0,
                    avg_range_pips=0.0,
                    median_body_pips=0.0,
                    median_retracement_pct=50.0,
                    recommended_strategy=ExitStrategyType.NO_TRADE_FILTER,
                    recommended_tp1_pips=0.0,
                    recommended_tp2_pips=None,
                    recommended_be_buffer_pips=None,
                    recommended_trail_pips=None,
                    max_adverse_pullback_pips=0.0,
                    suggested_time_stop="N/A",
                )
                continue

            ranges = [d.range_pips for d in sub]
            bodies = [d.body_pips for d in sub]
            retraces = [d.retracement_ratio * 100.0 for d in sub]
            legs = [d.first_leg_pips for d in sub]
            pullbacks = [d.max_pullback_pips for d in sub]

            med_range = float(np.median(ranges))
            p25_range = float(np.percentile(ranges, 25))
            p75_range = float(np.percentile(ranges, 75))
            p90_range = float(np.percentile(ranges, 90))
            avg_range = float(np.mean(ranges))
            med_body = float(np.median(bodies))
            med_retrace = float(np.median(retraces))
            med_leg = float(np.median(legs))
            p75_pullback = float(np.percentile(pullbacks, 75))

            if reg == DayRegimeType.RANGE_DAY:
                tp1 = round(0.70 * med_range, 1)
                stats_dict[reg] = RegimeDayStatistics(
                    regime=reg,
                    days_count=count,
                    frequency_pct=round(freq_pct, 1),
                    median_range_pips=round(med_range, 1),
                    p25_range_pips=round(p25_range, 1),
                    p75_range_pips=round(p75_range, 1),
                    p90_range_pips=round(p90_range, 1),
                    avg_range_pips=round(avg_range, 1),
                    median_body_pips=round(med_body, 1),
                    median_retracement_pct=round(med_retrace, 1),
                    recommended_strategy=ExitStrategyType.FIXED_TARGET_1,
                    recommended_tp1_pips=tp1,
                    recommended_tp2_pips=None,
                    recommended_be_buffer_pips=None,
                    recommended_trail_pips=None,
                    max_adverse_pullback_pips=round(float(np.median(pullbacks)), 1),
                    suggested_time_stop="Liquidate at Session End / NY Close (No Overnight Holding)",
                )

            elif reg == DayRegimeType.SEMI_TREND_DAY:
                tp1 = round(max(med_leg * 0.85, med_range * 0.45), 1)
                tp2 = round(med_range * 0.90, 1)
                be_buffer = round(spread_pips + (0.15 * med_range * 0.20), 1)
                stats_dict[reg] = RegimeDayStatistics(
                    regime=reg,
                    days_count=count,
                    frequency_pct=round(freq_pct, 1),
                    median_range_pips=round(med_range, 1),
                    p25_range_pips=round(p25_range, 1),
                    p75_range_pips=round(p75_range, 1),
                    p90_range_pips=round(p90_range, 1),
                    avg_range_pips=round(avg_range, 1),
                    median_body_pips=round(med_body, 1),
                    median_retracement_pct=round(med_retrace, 1),
                    recommended_strategy=ExitStrategyType.SPLIT_EXIT_RUNNER,
                    recommended_tp1_pips=tp1,
                    recommended_tp2_pips=tp2,
                    recommended_be_buffer_pips=be_buffer,
                    recommended_trail_pips=round(med_range * 0.35, 1),
                    max_adverse_pullback_pips=round(float(np.median(pullbacks)), 1),
                    suggested_time_stop="Hold through 1-2 day swing cycle (Exit if stagnant > 36 bars)",
                )

            elif reg == DayRegimeType.V_SHAPE_REVERSAL_DAY:
                tp1 = round(max(med_leg * 0.75, med_range * 0.50), 1)  # Locks initial expansion wave
                tp2 = round(med_range * 0.95, 1)                        # Reversal swing target
                be_buffer = round(spread_pips + 2.0, 1)
                trail_pips = round(med_leg * 0.35, 1)
                stats_dict[reg] = RegimeDayStatistics(
                    regime=reg,
                    days_count=count,
                    frequency_pct=round(freq_pct, 1),
                    median_range_pips=round(med_range, 1),
                    p25_range_pips=round(p25_range, 1),
                    p75_range_pips=round(p75_range, 1),
                    p90_range_pips=round(p90_range, 1),
                    avg_range_pips=round(avg_range, 1),
                    median_body_pips=round(med_body, 1),
                    median_retracement_pct=round(med_retrace, 1),
                    recommended_strategy=ExitStrategyType.SPLIT_EXIT_RUNNER,
                    recommended_tp1_pips=tp1,
                    recommended_tp2_pips=tp2,
                    recommended_be_buffer_pips=be_buffer,
                    recommended_trail_pips=trail_pips,
                    max_adverse_pullback_pips=round(p75_pullback, 1),
                    suggested_time_stop="Lock TP1 before Session Climax (Fade reversal or tighten trail to 2-bar low/high)",
                )

            else:  # STRONG_TREND_DAY
                tp1 = round(med_range * 0.35, 1)  # Scalp 20% tranche
                tp2 = round(med_range, 1)         # Median full trend expansion
                trail_pips = round(p75_pullback + spread_pips + 2.0, 1)
                stats_dict[reg] = RegimeDayStatistics(
                    regime=reg,
                    days_count=count,
                    frequency_pct=round(freq_pct, 1),
                    median_range_pips=round(med_range, 1),
                    p25_range_pips=round(p25_range, 1),
                    p75_range_pips=round(p75_range, 1),
                    p90_range_pips=round(p90_range, 1),
                    avg_range_pips=round(avg_range, 1),
                    median_body_pips=round(med_body, 1),
                    median_retracement_pct=round(med_retrace, 1),
                    recommended_strategy=ExitStrategyType.DYNAMIC_TRAILING_STOP,
                    recommended_tp1_pips=tp1,
                    recommended_tp2_pips=tp2,
                    recommended_be_buffer_pips=round(spread_pips + 2.0, 1),
                    recommended_trail_pips=trail_pips,
                    max_adverse_pullback_pips=round(p75_pullback, 1),
                    suggested_time_stop="Ride until Chandelier stop hit (Never exit on fixed TP)",
                )

        return stats_dict

    @staticmethod
    def print_playbook_card(profile: AssetBehaviorProfile):
        """Prints a clean ASCII Playbook Card to the console."""
        sym = profile.symbol
        s_range = profile.regime_stats[DayRegimeType.RANGE_DAY]
        s_semi = profile.regime_stats[DayRegimeType.SEMI_TREND_DAY]
        s_vshape = profile.regime_stats.get(DayRegimeType.V_SHAPE_REVERSAL_DAY)
        s_trend = profile.regime_stats[DayRegimeType.STRONG_TREND_DAY]

        print("\n" + "=" * 105)
        print(f"ASSET BEHAVIOR PROFILE & EMPIRICAL EXIT PLAYBOOK: {sym}")
        print(f"Lookback: {profile.lookback_days} Calendar Days ({profile.total_trading_days} Trading Days) | Average Daily Range: {profile.avg_daily_range_pips:.1f} pips")
        print("=" * 105)
        print("HISTORICAL REGIME FREQUENCY CENSUS:")
        print(f"  [#] Range Days:          {s_range.days_count:>3} days ({s_range.frequency_pct:>5.1f}%) -- Median Range: {s_range.median_range_pips:>5.1f}p | 75th %: {s_range.p75_range_pips:>5.1f}p | Retracement: {s_range.median_retracement_pct:.0f}%")
        print(f"  [#] Semi-Trending Days:   {s_semi.days_count:>3} days ({s_semi.frequency_pct:>5.1f}%) -- Median Range: {s_semi.median_range_pips:>5.1f}p | 1st Leg: {s_semi.recommended_tp1_pips:>5.1f}p | Retracement: {s_semi.median_retracement_pct:.0f}%")
        if s_vshape and s_vshape.days_count > 0:
            print(f"  [#] V-Shape Reversal:    {s_vshape.days_count:>3} days ({s_vshape.frequency_pct:>5.1f}%) -- Median Range: {s_vshape.median_range_pips:>5.1f}p | 1st Leg: {s_vshape.recommended_tp1_pips:>5.1f}p | Retracement: {s_vshape.median_retracement_pct:.0f}%")
        print(f"  [#] Strong Trend Days:    {s_trend.days_count:>3} days ({s_trend.frequency_pct:>5.1f}%) -- Median Run:   {s_trend.median_range_pips:>5.1f}p | 90th %: {s_trend.p90_range_pips:>5.1f}p | Max Pullback: {s_trend.max_adverse_pullback_pips:>4.1f}p")
        print("-" * 105)
        print(f"ACTIONABLE EXIT RULES FOR TRADING {sym}:")
        print()
        print(f"1. IF TODAY IS IDENTIFIED AS A RANGE DAY ({s_range.frequency_pct:.0f}% Probability):")
        print(f"   - Position Strategy:  Single Fixed Target (100% at TP1)")
        print(f"   - Recommended TP1:    +{s_range.recommended_tp1_pips:.1f} pips (70% of Median Range Height)")
        print(f"   - Stop Loss Buffer:   12.0 pips beyond range extreme")
        print(f"   - Time Management:    {s_range.suggested_time_stop}")
        print()
        print(f"2. IF TODAY IS IDENTIFIED AS A SEMI-TRENDING / SWING DAY ({s_semi.frequency_pct:.0f}% Probability):")
        print(f"   - Position Strategy:  50/50 Split Exit (TP1 Cash Lock + TP2 Swing Runner)")
        print(f"   - Tranche 1 (TP1):    +{s_semi.recommended_tp1_pips:.1f} pips (Locks profit before the {s_semi.median_retracement_pct:.0f}% pullback)")
        print(f"   - Breakeven Trigger:  Move SL to Entry + {s_semi.recommended_be_buffer_pips:.1f} pips buffer upon TP1 fill")
        print(f"   - Tranche 2 (TP2):    +{s_semi.recommended_tp2_pips:.1f} pips (Captures second swing extension)")
        print(f"   - Time Management:    {s_semi.suggested_time_stop}")
        if s_vshape and s_vshape.days_count > 0:
            print()
            print(f"3. IF TODAY IS IDENTIFIED AS A V-SHAPE REVERSAL DAY ({s_vshape.frequency_pct:.0f}% Probability):")
            print(f"   - Position Strategy:  Split Exit with Milestone Profit Lock (Two-Way Expansion)")
            print(f"   - Tranche 1 (TP1):    +{s_vshape.recommended_tp1_pips:.1f} pips (Locks initial trend wave before reversal)")
            print(f"   - Breakeven Trigger:  Move SL to Entry + {s_vshape.recommended_be_buffer_pips:.1f} pips buffer upon TP1 fill")
            print(f"   - Tranche 2 (TP2):    +{s_vshape.recommended_tp2_pips:.1f} pips (Or reverse trade on session climax)")
            print(f"   - Time Management:    {s_vshape.suggested_time_stop}")
        print()
        print(f"4. IF TODAY IS IDENTIFIED AS A STRONG TRENDING DAY ({s_trend.frequency_pct:.0f}% Probability):")
        print(f"   - Position Strategy:  Dynamic Trailing Stop (20% Scalp / 80% Chandelier Runner)")
        print(f"   - Tranche 1 (Scalp):  +{s_trend.recommended_tp1_pips:.1f} pips (Secures initial equity)")
        print(f"   - Trailing Distance:  Maintain {s_trend.recommended_trail_pips:.1f} pips trailing buffer to survive normal intraday pullbacks")
        print(f"   - Median Potential:   +{s_trend.median_range_pips:.1f} pips (90th percentile: +{s_trend.p90_range_pips:.1f} pips)")
        print(f"   - Time Management:    {s_trend.suggested_time_stop}")
        print("=" * 105 + "\n")
