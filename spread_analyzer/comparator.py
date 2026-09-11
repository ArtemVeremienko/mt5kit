"""
Cross-Broker Spread Comparator Engine.

Gathers all spread_summary.csv files across broker output folders,
normalizes cross-broker symbol aliases using a configurable JSON map,
evaluates a 50/50 composite score of Spread (bps) and Spread / Vol (%),
ranks brokers per symbol, and outputs:
- Aligned color-coded terminal comparison table
- Interactive multi-broker HTML dashboard
- Structured cross-broker comparison CSV
"""

import csv
import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from spread_analyzer.commissions import (
    CommissionProfile,
    calculate_commission_impact,
    load_commission_profile,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("spread_comparator")

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
ORANGE = "\033[33m"
CYAN = "\033[36m"
GRAY = "\033[90m"
YELLOW = "\033[93m"
WHITE = "\033[97m"


@dataclass
class BrokerSymbolRecord:
    broker_tag: str
    symbol: str
    canonical_symbol: str
    unit: str
    min_spread: float
    median_spread: float
    avg_spread: float
    p95_spread: float
    max_spread: float
    metric_basis: str
    spread_bps: float
    spread_to_vol_pct: float = 0.0
    avg_daily_volatility_pct: float = 0.0
    avg_daily_volatility: float = 0.0
    total_ticks: int = 0
    sampled_minutes: int = 0
    # Advanced Quote Quality & Widening Metrics
    stability_ratio: float = 1.0
    widening_pct_15x_time: float = 0.0
    widening_pct_20x_time: float = 0.0
    widening_pct_15x_tick: float = 0.0
    time_weighted_bps: float = 0.0
    core_spread_bps: float = 0.0
    rollover_multiplier: float = 1.0
    max_quote_gap_sec: float = 0.0
    # Extreme Tail Risk & Blowout Metrics
    p99_spread: float = 0.0
    p999_spread: float = 0.0
    tail_blowout_ratio: float = 1.0
    max_to_median_ratio: float = 1.0
    mean_price: float = 0.0
    # Commission & All-In Friction Metrics
    asset_class: str = "other"
    commission_rt_usd: float = 0.0
    commission_spread: float = 0.0
    commission_bps: float = 0.0
    effective_median_spread: float = 0.0
    effective_avg_spread: float = 0.0
    effective_spread_bps: float = 0.0
    effective_quality_score: float = 0.0
    # Scoring & Ranking
    quality_score: float = 0.0
    composite_score: float = 0.0
    rank: int = 0
    savings_vs_worst_bps: float = 0.0
    delta_vs_winner_bps: float = 0.0
    winner_lead_bps: float = 0.0


@dataclass
class BrokerLeaderboardStats:
    broker_tag: str
    total_points: float = 0.0
    contested_symbols: int = 0
    avg_points: float = 0.0
    first_places: int = 0
    second_places: int = 0
    third_places: int = 0
    other_places: int = 0
    total_symbols: int = 0


@dataclass
class CanonicalComparisonGroup:
    canonical_symbol: str
    records: List[BrokerSymbolRecord] = field(default_factory=list)
    winner: Optional[BrokerSymbolRecord] = None
    runner_up: Optional[BrokerSymbolRecord] = None
    bps_difference: float = 0.0
    winner_lead_bps: float = 0.0


def load_symbol_mappings(mapping_file: Path) -> Dict[str, str]:
    if not mapping_file.exists():
        logger.warning(f"Mapping file not found at {mapping_file}, using exact symbol matching.")
        return {}

    try:
        with open(mapping_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to parse {mapping_file}: {e}")
        return {}

    reverse_map = {}
    for canonical, aliases in data.items():
        canonical_clean = canonical.strip().upper()
        reverse_map[canonical_clean] = canonical_clean
        for alias in aliases:
            reverse_map[alias.strip().upper()] = canonical_clean

    return reverse_map


def normalize_symbol(symbol: str, reverse_map: Dict[str, str]) -> str:
    """
    Resolves a broker's symbol into its canonical symbol using multi-tier matching:
    1. Tier 1: Exact uppercase match in reverse_map.
    2. Tier 2: Suffix/Prefix stripping checked against reverse_map.
    3. Tier 3: Longest alias substring matching (aliases with length >= 4).
    4. Tier 4: Fallback as-is: strips common broker noise (#, ., .raw, .pro, etc.)
       and returns the clean symbol directly if not present in reverse_map.
    """
    s_upper = symbol.strip().upper()

    # Tier 1: Exact match
    if s_upper in reverse_map:
        return reverse_map[s_upper]

    # Strip prefix noise (#, .)
    s_clean = s_upper.lstrip("#.")
    if s_clean in reverse_map:
        return reverse_map[s_clean]

    # Tier 2: Common broker suffix stripping checked against reverse_map
    for suffix in (".RAW", ".PRO", ".A", ".CASH", "CASH", "_SPOT", "SPOT", ".M", "M"):
        if s_clean.endswith(suffix):
            cand = s_clean[:-len(suffix)]
            if cand in reverse_map:
                return reverse_map[cand]

    # Tier 3: Substring matching against reverse_map aliases
    # Sort aliases by length descending so longer, more specific matches win (e.g. 'USNDAQ100' before 'US100')
    candidate_matches: List[Tuple[int, str]] = []
    for alias, canonical in reverse_map.items():
        if len(alias) >= 4:
            if alias in s_clean:
                candidate_matches.append((len(alias), canonical))

    if candidate_matches:
        candidate_matches.sort(key=lambda x: x[0], reverse=True)
        return candidate_matches[0][1]

    # Tier 4: Fallback as-is: strip standard broker noise and return clean symbol directly
    for suffix in (".RAW", ".PRO", ".A", ".CASH", "CASH", "_SPOT", "SPOT", ".M"):
        if s_clean.endswith(suffix):
            return s_clean[:-len(suffix)]

    # Forex micro/mini suffix 'm' on standard 6-char currency pairs (e.g. EURUSDm -> EURUSD)
    if len(s_clean) == 7 and s_clean.endswith("M") and s_clean[:6].isalpha():
        return s_clean[:-1]

    return s_clean


def discover_summary_files(base_dir: Path) -> List[Tuple[str, Path]]:
    found = []
    if not base_dir.exists():
        return found

    for item in sorted(base_dir.iterdir()):
        if item.is_dir():
            csv_path = item / "spread_summary.csv"
            if csv_path.exists():
                found.append((item.name, csv_path))
    return found


REQUIRED_SUMMARY_COLUMNS = {
    "symbol",
    "unit",
    "min_spread",
    "median_spread",
    "avg_spread",
    "p95_spread",
    "p99_spread",
    "p999_spread",
    "max_spread",
    "metric_basis",
    "spread_bps",
    "time_weighted_bps",
    "core_spread_bps",
    "rollover_multiplier",
    "stability_ratio",
    "tail_blowout_ratio",
    "max_to_median_ratio",
    "widening_pct_15x_time",
    "widening_pct_20x_time",
    "widening_pct_15x_tick",
    "max_quote_gap_sec",
    "spread_to_vol_pct",
    "avg_daily_volatility_pct",
    "avg_daily_volatility",
    "total_ticks",
    "sampled_minutes",
    "mean_price",
}


def parse_summary_csv(
    broker_tag: str,
    csv_path: Path,
    reverse_map: Dict[str, str],
) -> List[BrokerSymbolRecord]:
    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Spread summary CSV {csv_path} is empty or has no header.")

        missing_cols = sorted(REQUIRED_SUMMARY_COLUMNS - set(reader.fieldnames))
        if missing_cols:
            raise ValueError(
                f"Invalid spread summary CSV {csv_path}: missing required column(s): {missing_cols}. "
                "Please re-run spread analysis to generate up-to-date summary data."
            )

        for row in reader:
            sym = row["symbol"].strip()
            if not sym:
                continue

            unit = row["unit"]
            min_s = float(row["min_spread"])
            med_s = float(row["median_spread"])
            avg_s = float(row["avg_spread"])
            p95_s = float(row["p95_spread"])
            p99_s = float(row["p99_spread"])
            p999_s = float(row["p999_spread"])
            max_s = float(row["max_spread"])
            basis = row["metric_basis"]

            spread_bps = float(row["spread_bps"])
            spread_to_vol_pct = float(row["spread_to_vol_pct"])
            daily_vol_pct = float(row["avg_daily_volatility_pct"])
            daily_vol = float(row["avg_daily_volatility"])
            ticks = int(float(row["total_ticks"]))
            m1_bars = int(float(row["sampled_minutes"]))

            canonical = normalize_symbol(sym, reverse_map)

            # Advanced Quote Quality & Widening Metrics
            stab = float(row["stability_ratio"])
            widen_15_time = float(row["widening_pct_15x_time"])
            widen_20_time = float(row["widening_pct_20x_time"])
            widen_15_tick = float(row["widening_pct_15x_tick"])
            tw_bps = float(row["time_weighted_bps"])
            core_bps = float(row["core_spread_bps"])
            roll_mult = float(row["rollover_multiplier"])
            blowout_r = float(row["tail_blowout_ratio"])
            max_med_r = float(row["max_to_median_ratio"])
            max_gap = float(row["max_quote_gap_sec"])
            mean_p = float(row["mean_price"])

            record = BrokerSymbolRecord(
                broker_tag=broker_tag,
                symbol=sym,
                canonical_symbol=canonical,
                unit=unit,
                min_spread=min_s,
                median_spread=med_s,
                avg_spread=avg_s,
                p95_spread=p95_s,
                max_spread=max_s,
                metric_basis=basis,
                spread_bps=spread_bps,
                spread_to_vol_pct=spread_to_vol_pct,
                avg_daily_volatility_pct=daily_vol_pct,
                avg_daily_volatility=daily_vol,
                total_ticks=ticks,
                sampled_minutes=m1_bars,
                stability_ratio=stab,
                widening_pct_15x_time=widen_15_time,
                widening_pct_20x_time=widen_20_time,
                widening_pct_15x_tick=widen_15_tick,
                time_weighted_bps=tw_bps,
                core_spread_bps=core_bps,
                rollover_multiplier=roll_mult,
                p99_spread=p99_s,
                p999_spread=p999_s,
                tail_blowout_ratio=blowout_r,
                max_to_median_ratio=max_med_r,
                max_quote_gap_sec=max_gap,
                mean_price=mean_p,
                composite_score=spread_bps,
            )
            records.append(record)

    return records


def run_cross_broker_comparison(
    output_dir: Path,
    mappings_file: Path,
    commissions_file: Optional[Path] = None,
    broker_comm_overrides: Optional[str] = None,
    enable_commission: bool = True,
) -> Tuple[List[CanonicalComparisonGroup], Dict[str, BrokerLeaderboardStats]]:
    reverse_map = load_symbol_mappings(mappings_file)
    comm_profile = load_commission_profile(commissions_file, broker_comm_overrides)
    files = discover_summary_files(output_dir)

    if not files:
        logger.warning(f"No spread_summary.csv files found in {output_dir}")
        return [], {}

    all_records: List[BrokerSymbolRecord] = []
    broker_tags: set = set()
    for broker_tag, csv_path in files:
        recs = parse_summary_csv(broker_tag, csv_path, reverse_map)
        all_records.extend(recs)
        broker_tags.add(broker_tag)
        logger.info(f"Loaded {len(recs)} symbols from [{broker_tag}]")

    grouped: Dict[str, List[BrokerSymbolRecord]] = {}
    for r in all_records:
        grouped.setdefault(r.canonical_symbol, []).append(r)

    comparison_groups: List[CanonicalComparisonGroup] = []
    
    # Points scheme for contested symbols (Olympic / Grand Prix style):
    # 1st: 10 pts, 2nd: 6 pts, 3rd: 4 pts, 4th: 2 pts, 5th: 1 pt
    POINTS_TABLE = {1: 10.0, 2: 6.0, 3: 4.0, 4: 2.0, 5: 1.0}

    leaderboard: Dict[str, BrokerLeaderboardStats] = {
        b: BrokerLeaderboardStats(broker_tag=b) for b in broker_tags
    }

    for canonical, recs in sorted(grouped.items()):
        # Institutional Additive Execution Quality Score (Friction in basis points):
        # Quality Score = TWAS (bps) + 0.4 * TailRisk (bps) + 0.2 * BlowoutRisk (bps) + 1.0 * WideningFriction (bps)
        # All-In Quality Score = (TWAS + Comm_bps) + 0.4 * TailRisk + 0.2 * BlowoutRisk + 1.0 * WideningFriction
        # Note: Quote quality microstructure (tail risk, blowout, widening) is preserved strictly on raw spreads!
        for r in recs:
            impact = calculate_commission_impact(
                symbol=r.symbol,
                broker_tag=r.broker_tag,
                unit=r.unit,
                median_spread=r.median_spread,
                spread_bps=r.spread_bps,
                mean_price=r.mean_price,
                profile=comm_profile,
                enable_commission=enable_commission,
            )
            r.asset_class = impact.asset_class
            r.commission_rt_usd = impact.commission_rt_usd
            r.commission_spread = impact.commission_spread
            r.commission_bps = impact.commission_bps
            r.effective_median_spread = impact.effective_spread
            r.effective_avg_spread = round(r.avg_spread + impact.commission_spread, 4)
            r.effective_spread_bps = impact.effective_spread_bps

            base_bps = r.time_weighted_bps if r.time_weighted_bps > 0.0 else r.spread_bps
            # 1. Normal right-tail risk (P95 - Median)
            tail_scaled = max(r.p95_spread - r.median_spread, 0.0)
            tail_bps = (tail_scaled / r.median_spread * base_bps) if r.median_spread > 0.0 else (r.stability_ratio - 1.0) * base_bps
            tail_bps = max(tail_bps, 0.0)

            # 2. Extreme tail blowout risk (P99.9 - P95)
            p999_s = getattr(r, "p999_spread", r.max_spread)
            blowout_scaled = max(p999_s - r.p95_spread, 0.0)
            blowout_bps = (blowout_scaled / r.median_spread * base_bps) if r.median_spread > 0.0 else 0.0
            blowout_bps = max(blowout_bps, 0.0)

            # 3. Widening duration friction
            widen_friction = base_bps * (r.widening_pct_15x_time / 100.0)

            # Raw Quality Score
            r.quality_score = round(base_bps + 0.4 * tail_bps + 0.2 * blowout_bps + 1.0 * widen_friction, 4)

            # Effective All-In Quality Score with commission
            eff_base_bps = base_bps + r.commission_bps
            r.effective_quality_score = round(eff_base_bps + 0.4 * tail_bps + 0.2 * blowout_bps + 1.0 * widen_friction, 4)

            # Composite score used for ranking
            r.composite_score = r.effective_quality_score if enable_commission else r.quality_score

        # Rank by composite score, tie-break with spread_bps then median_spread
        recs_sorted = sorted(
            recs,
            key=lambda x: (
                x.composite_score,
                x.effective_spread_bps if enable_commission else x.spread_bps,
                x.effective_median_spread if enable_commission else x.median_spread,
            ),
        )

        is_contested = (len(recs_sorted) > 1)
        winner = recs_sorted[0] if recs_sorted else None
        runner_up = recs_sorted[1] if len(recs_sorted) > 1 else None
        winner_lead = round(runner_up.composite_score - winner.composite_score, 4) if (winner and runner_up) else 0.0

        for rank_idx, r in enumerate(recs_sorted, start=1):
            r.rank = rank_idx
            r.winner_lead_bps = winner_lead

            if rank_idx == 1:
                r.delta_vs_winner_bps = 0.0
                r.savings_vs_worst_bps = winner_lead  # preserve for backwards compatibility
            else:
                # Negative delta representing deficit vs winner in execution quality score
                r.delta_vs_winner_bps = round(winner.composite_score - r.composite_score, 4)
                r.savings_vs_worst_bps = 0.0

            stats = leaderboard[r.broker_tag]
            stats.total_symbols += 1

            if is_contested:
                stats.contested_symbols += 1
                pts = POINTS_TABLE.get(rank_idx, 0.0)
                stats.total_points += pts

                if rank_idx == 1:
                    stats.first_places += 1
                elif rank_idx == 2:
                    stats.second_places += 1
                elif rank_idx == 3:
                    stats.third_places += 1
                else:
                    stats.other_places += 1

        group = CanonicalComparisonGroup(
            canonical_symbol=canonical,
            records=recs_sorted,
            winner=winner,
            runner_up=runner_up,
            bps_difference=winner_lead,
            winner_lead_bps=winner_lead,
        )
        comparison_groups.append(group)

    # Compute normalized average points per contested symbol
    for stats in leaderboard.values():
        if stats.contested_symbols > 0:
            stats.avg_points = stats.total_points / stats.contested_symbols
        else:
            stats.avg_points = 0.0

    return comparison_groups, leaderboard


def print_comparison_terminal(
    groups: List[CanonicalComparisonGroup],
    leaderboard: Dict[str, BrokerLeaderboardStats],
) -> None:
    print(f"\n{BOLD}{CYAN}=== CROSS-BROKER SPREAD & EXECUTION QUALITY COMPARISON ==={RESET}")
    metric_desc = "Institutional Execution Quality Score [TWAS + 0.5*Tail + Widen] (bps)"
    print(f"{GRAY}Execution Metric: {BOLD}{metric_desc}{RESET} (Lower = Better Execution; Lowest Wins Rank #1 [BEST])")
    print(f"{GRAY}Points Formula  : {BOLD}1st: 10 pts, 2nd: 6 pts, 3rd: 4 pts, 4th: 2 pts, 5th: 1 pt{RESET} (Ranked by Avg Points/Symbol)")

    # Win & Points Leaderboard
    # To prevent cherry-picking where 1 symbol wins #1 over 50 symbols,
    # Leaderboard ranks by (avg_points, total_points, first_places)
    print(f"\n{BOLD}=== BROKER PERFORMANCE LEADERBOARD ==={RESET}")
    max_contested = max((s.contested_symbols for s in leaderboard.values()), default=0)
    # Require at least min(3, max_contested) contested symbols to qualify for the #1 Leader title
    min_required_for_leader = min(3, max_contested) if max_contested > 0 else 1

    sorted_leaderboard = sorted(
        leaderboard.values(),
        key=lambda x: (
            1 if x.contested_symbols >= min_required_for_leader else 0,
            x.avg_points,
            x.total_points,
            x.first_places,
        ),
        reverse=True
    )
    for idx, s in enumerate(sorted_leaderboard, start=1):
        trophy = f"{GREEN}{BOLD}[#1 LEADER]{RESET}" if idx == 1 else f"#{idx}       "
        print(
            f"  {trophy} {s.broker_tag:<35} : "
            f"{BOLD}{s.avg_points:.2f} pts/sym{RESET} "
            f"({s.total_points:.0f} pts | 1st: {s.first_places}, 2nd: {s.second_places}, 3rd: {s.third_places} over {s.contested_symbols} contested symbols)"
        )

    h_sym, h_rnk, h_brk, h_unt = "CANONICAL", "RANK", "BROKER ACCOUNT", "UNIT"
    h_med, h_comm, h_eff_med = "RAW MED", "COMM($)", "ALL-IN"
    h_p95, h_bps, h_eff_bps = "P95", "RAW(BPS)", "ALL-IN(BPS)"
    h_stab, h_score, h_dlt = "STABILITY", "SCORE", "DELTA VS #1"
    print(f"\n{BOLD}{h_sym:<10}  {h_rnk:<5}  {h_brk:<32}  {h_unt:<6}  {h_med:<8}  {h_comm:<8}  {h_eff_med:<8}  {h_p95:<8}  {h_bps:<10}  {h_eff_bps:<11}  {h_stab:<10}  {h_score:<8}  {h_dlt:<20}{RESET}")
    print(f"{GRAY}{'-'*155}{RESET}")

    for g in groups:
        is_contested = len(g.records) > 1
        for r in g.records:
            if r.rank == 1:
                rank_str = f"{GREEN}{BOLD}#1 [BEST]{RESET}"
                broker_str = f"{GREEN}{BOLD}{r.broker_tag:<32}{RESET}"
                delta_str = f"{GREEN}+ {r.winner_lead_bps:.2f} bps lead{RESET}" if is_contested else f"{GREEN}[Best]{RESET}"
            elif r.rank == 2:
                rank_str = f"{ORANGE}#2{RESET}"
                broker_str = f"{r.broker_tag:<32}"
                delta_str = f"{ORANGE}{r.delta_vs_winner_bps:.2f} bps{RESET}"
            else:
                rank_str = f"{GRAY}#{r.rank}{RESET}"
                broker_str = f"{GRAY}{r.broker_tag:<32}{RESET}"
                delta_str = f"{RED}{r.delta_vs_winner_bps:.2f} bps{RESET}"

            stab_color = GREEN if r.stability_ratio < 1.3 else (ORANGE if r.stability_ratio <= 2.0 else RED)
            comm_str = f"${r.commission_rt_usd:.2f}" if r.commission_rt_usd > 0 else "-"

            print(
                f"{BOLD}{g.canonical_symbol:<10}{RESET}  "
                f"{rank_str:<5}  "
                f"{broker_str}  "
                f"{r.unit:<6}  "
                f"{r.median_spread:<8.2f}  "
                f"{comm_str:<8}  "
                f"{BOLD}{r.effective_median_spread:<8.2f}{RESET}  "
                f"{r.p95_spread:<8.2f}  "
                f"{r.spread_bps:<10.2f}  "
                f"{BOLD}{r.effective_spread_bps:<11.2f}{RESET}  "
                f"{stab_color}{f'{r.stability_ratio:.2f}x':<10}{RESET}  "
                f"{r.composite_score:<8.3f}  "
                f"{delta_str:<20}"
            )
        print(f"{GRAY}{'.' * 155}{RESET}")
    print()


def export_comparison_csv(groups: List[CanonicalComparisonGroup], csv_path: Path) -> Path:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "canonical_symbol",
        "rank",
        "is_winner",
        "broker_tag",
        "broker_symbol",
        "unit",
        "min_spread",
        "median_spread",
        "avg_spread",
        "p95_spread",
        "max_spread",
        "spread_bps",
        "mean_price",
        "asset_class",
        "commission_rt_usd",
        "commission_spread",
        "commission_bps",
        "effective_median_spread",
        "effective_avg_spread",
        "effective_spread_bps",
        "effective_quality_score",
        "stability_ratio",
        "widening_pct_15x_time",
        "widening_pct_20x_time",
        "widening_pct_15x_tick",
        "core_spread_bps",
        "rollover_multiplier",
        "quality_score",
        "composite_score",
        "delta_vs_winner_bps",
        "winner_lead_bps",
        "total_ticks",
        "sampled_minutes",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for g in groups:
            for r in g.records:
                writer.writerow({
                    "canonical_symbol": g.canonical_symbol,
                    "rank": r.rank,
                    "is_winner": 1 if r.rank == 1 else 0,
                    "broker_tag": r.broker_tag,
                    "broker_symbol": r.symbol,
                    "unit": r.unit,
                    "min_spread": r.min_spread,
                    "median_spread": r.median_spread,
                    "avg_spread": r.avg_spread,
                    "p95_spread": r.p95_spread,
                    "max_spread": r.max_spread,
                    "spread_bps": round(r.spread_bps, 4),
                    "mean_price": round(r.mean_price, 5),
                    "asset_class": r.asset_class,
                    "commission_rt_usd": round(r.commission_rt_usd, 2),
                    "commission_spread": round(r.commission_spread, 4),
                    "commission_bps": round(r.commission_bps, 4),
                    "effective_median_spread": round(r.effective_median_spread, 4),
                    "effective_avg_spread": round(r.effective_avg_spread, 4),
                    "effective_spread_bps": round(r.effective_spread_bps, 4),
                    "effective_quality_score": round(r.effective_quality_score, 4),
                    "stability_ratio": round(r.stability_ratio, 4),
                    "widening_pct_15x_time": round(r.widening_pct_15x_time, 4),
                    "widening_pct_20x_time": round(r.widening_pct_20x_time, 4),
                    "widening_pct_15x_tick": round(r.widening_pct_15x_tick, 4),
                    "core_spread_bps": round(r.core_spread_bps, 4),
                    "rollover_multiplier": round(r.rollover_multiplier, 4),
                    "quality_score": round(r.quality_score, 4),
                    "composite_score": round(r.composite_score, 4),
                    "delta_vs_winner_bps": round(r.delta_vs_winner_bps, 4),
                    "winner_lead_bps": round(r.winner_lead_bps, 4),
                    "total_ticks": r.total_ticks,
                    "sampled_minutes": r.sampled_minutes,
                })
    return csv_path


def generate_comparison_html(
    groups: List[CanonicalComparisonGroup],
    leaderboard: Dict[str, BrokerLeaderboardStats],
    output_path: Path,
    enable_commission: bool = True,
) -> Path:
    """
    Generates a decoupled cross-broker comparison package:
    - report_data.json: Structured JSON comparison data (leaderboard + groups)
    - report_data.js: Script shim assigning window.__REPORT_DATA__ for local file:// viewing
    - index.html (or specified output_path): Static Alpine.js comparison dashboard copied from templates
    """
    if output_path.suffix.lower() == ".html":
        output_dir = output_path.parent
        html_file = output_path
    else:
        output_dir = output_path
        html_file = output_dir / "index.html"

    output_dir.mkdir(parents=True, exist_ok=True)

    leaderboard_data = []
    sorted_leaderboard = sorted(
        leaderboard.values(),
        key=lambda x: (x.avg_points, x.total_points, x.first_places),
        reverse=True
    )
    for s in sorted_leaderboard:
        leaderboard_data.append({
            "broker_tag": s.broker_tag,
            "total_points": round(float(s.total_points), 2),
            "contested_symbols": int(s.contested_symbols),
            "avg_points": round(float(s.avg_points), 4),
            "first_places": int(s.first_places),
            "second_places": int(s.second_places),
            "third_places": int(s.third_places),
            "other_places": int(s.other_places),
            "total_symbols": int(s.total_symbols),
        })

    groups_data = []
    for g in groups:
        records_data = []
        for r in g.records:
            records_data.append({
                "broker_tag": r.broker_tag,
                "symbol": r.symbol,
                "canonical_symbol": r.canonical_symbol,
                "unit": r.unit,
                "min_spread": round(float(r.min_spread), 4),
                "median_spread": round(float(r.median_spread), 4),
                "avg_spread": round(float(r.avg_spread), 4),
                "p95_spread": round(float(r.p95_spread), 4),
                "p99_spread": round(float(getattr(r, "p99_spread", r.p95_spread)), 4),
                "p999_spread": round(float(getattr(r, "p999_spread", r.max_spread)), 4),
                "max_spread": round(float(r.max_spread), 4),
                "metric_basis": r.metric_basis,
                "spread_bps": round(float(r.spread_bps), 4),
                "mean_price": round(float(r.mean_price), 5),
                "asset_class": r.asset_class,
                "commission_rt_usd": round(float(r.commission_rt_usd), 2),
                "commission_spread": round(float(r.commission_spread), 4),
                "commission_bps": round(float(r.commission_bps), 4),
                "effective_median_spread": round(float(r.effective_median_spread), 4),
                "effective_avg_spread": round(float(r.effective_avg_spread), 4),
                "effective_spread_bps": round(float(r.effective_spread_bps), 4),
                "effective_quality_score": round(float(r.effective_quality_score), 4),
                "stability_ratio": round(float(r.stability_ratio), 4),
                "tail_blowout_ratio": round(float(getattr(r, "tail_blowout_ratio", 1.0)), 4),
                "max_to_median_ratio": round(float(getattr(r, "max_to_median_ratio", 1.0)), 4),
                "widening_pct_15x_time": round(float(r.widening_pct_15x_time), 4),
                "widening_pct_20x_time": round(float(r.widening_pct_20x_time), 4),
                "widening_pct_15x_tick": round(float(r.widening_pct_15x_tick), 4),
                "core_spread_bps": round(float(r.core_spread_bps), 4),
                "rollover_multiplier": round(float(r.rollover_multiplier), 4),
                "quality_score": round(float(r.quality_score), 4),
                "composite_score": round(float(r.composite_score), 4),
                "rank": int(r.rank),
                "delta_vs_winner_bps": round(float(r.delta_vs_winner_bps), 4),
                "winner_lead_bps": round(float(r.winner_lead_bps), 4),
                "total_ticks": int(r.total_ticks),
                "sampled_minutes": int(r.sampled_minutes),
            })
        groups_data.append({
            "canonical_symbol": g.canonical_symbol,
            "records": records_data,
            "winner_lead_bps": round(float(g.winner_lead_bps), 4),
        })

    metric_title = "Execution Quality Score (bps: TWAS + 0.4·Tail + 0.2·Blowout + 1.0·Widening)"
    report_data = {
        "metric": metric_title,
        "rank_by": "quality",
        "enable_commission": enable_commission,
        "leaderboard": leaderboard_data,
        "groups": groups_data,
    }

    # 1. Write report_data.json
    json_path = output_dir / "report_data.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    # 2. Write report_data.js for offline file:// double-click compatibility
    js_path = output_dir / "report_data.js"
    json_str = json.dumps(report_data)
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(f"window.__REPORT_DATA__ = {json_str};\n")

    # 3. Copy static Alpine.js template
    template_path = Path(__file__).parent / "templates" / "broker_comparison.html"
    if template_path.exists():
        shutil.copy2(template_path, html_file)
    else:
        raise FileNotFoundError(f"Template not found at: {template_path}")

    return html_file


