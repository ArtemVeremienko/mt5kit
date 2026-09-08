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


def parse_summary_csv(
    broker_tag: str,
    csv_path: Path,
    reverse_map: Dict[str, str],
) -> List[BrokerSymbolRecord]:
    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = row.get("symbol", "").strip()
            if not sym:
                continue

            unit = row.get("unit", "standard")
            min_s = float(row.get("min_spread", 0.0))
            med_s = float(row.get("median_spread", row.get("avg_spread", 0.0)))
            avg_s = float(row.get("avg_spread", 0.0))
            p95_s = float(row.get("p95_spread", avg_s))
            max_s = float(row.get("max_spread", avg_s))
            basis = row.get("metric_basis", "median")

            spread_bps = float(row.get("spread_bps", 0.0))
            spread_to_vol_pct = float(row.get("spread_to_vol_pct", 0.0))
            daily_vol_pct = float(row.get("avg_daily_volatility_pct", 0.0))
            daily_vol = float(row.get("avg_daily_volatility", 0.0))
            ticks = int(float(row.get("total_ticks", 0)))
            m1_bars = int(float(row.get("sampled_minutes", 0)))

            canonical = normalize_symbol(sym, reverse_map)

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
                composite_score=spread_bps,
            )
            records.append(record)

    return records


def run_cross_broker_comparison(
    output_dir: Path,
    mappings_file: Path,
) -> Tuple[List[CanonicalComparisonGroup], Dict[str, BrokerLeaderboardStats]]:
    reverse_map = load_symbol_mappings(mappings_file)
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
        # Sort purely by Spread in Basis Points (bps), then median spread as tie-breaker
        recs_sorted = sorted(recs, key=lambda x: (x.spread_bps, x.median_spread))

        is_contested = (len(recs_sorted) > 1)
        winner = recs_sorted[0] if recs_sorted else None
        runner_up = recs_sorted[1] if len(recs_sorted) > 1 else None
        winner_lead = (runner_up.spread_bps - winner.spread_bps) if (winner and runner_up) else 0.0

        for rank_idx, r in enumerate(recs_sorted, start=1):
            r.rank = rank_idx
            r.composite_score = r.spread_bps
            r.winner_lead_bps = winner_lead

            if rank_idx == 1:
                r.delta_vs_winner_bps = 0.0
                r.savings_vs_worst_bps = winner_lead  # preserve for backwards compatibility
            else:
                # Negative delta representing deficit vs winner
                r.delta_vs_winner_bps = winner.spread_bps - r.spread_bps
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
    print(f"\n{BOLD}{CYAN}=== CROSS-BROKER SPREAD COMPARISON SUMMARY ==={RESET}")
    print(f"{GRAY}Execution Metric: {BOLD}Spread (bps){RESET} (Lower = Better Execution; Lowest Wins Rank #1 🏆)")
    print(f"{GRAY}Points Formula  : {BOLD}1st: 10 pts, 2nd: 6 pts, 3rd: 4 pts, 4th: 2 pts, 5th: 1 pt{RESET} (Ranked by Avg Points/Symbol)")

    # Win & Points Leaderboard
    print(f"\n{BOLD}=== BROKER PERFORMANCE LEADERBOARD ==={RESET}")
    sorted_leaderboard = sorted(
        leaderboard.values(),
        key=lambda x: (x.avg_points, x.total_points, x.first_places),
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
    h_med, h_avg, h_p95, h_bps, h_dlt = "MEDIAN", "AVG", "P95", "SPREAD(BPS)", "DELTA VS #1"
    print(f"\n{BOLD}{h_sym:<10}  {h_rnk:<5}  {h_brk:<35}  {h_unt:<6}  {h_med:<8}  {h_avg:<8}  {h_p95:<8}  {h_bps:<12}  {h_dlt:<22}{RESET}")
    print(f"{GRAY}{'-'*115}{RESET}")

    for g in groups:
        is_contested = len(g.records) > 1
        for r in g.records:
            if r.rank == 1:
                rank_str = f"{GREEN}{BOLD}#1 [BEST]{RESET}"
                broker_str = f"{GREEN}{BOLD}{r.broker_tag:<35}{RESET}"
                delta_str = f"{GREEN}+ {r.winner_lead_bps:.2f} bps lead{RESET}" if is_contested else f"{GREEN}🏆 Best{RESET}"
            elif r.rank == 2:
                rank_str = f"{ORANGE}#2{RESET}"
                broker_str = f"{r.broker_tag:<35}"
                delta_str = f"{ORANGE}{r.delta_vs_winner_bps:.2f} bps{RESET}"
            else:
                rank_str = f"{GRAY}#{r.rank}{RESET}"
                broker_str = f"{GRAY}{r.broker_tag:<35}{RESET}"
                delta_str = f"{RED}{r.delta_vs_winner_bps:.2f} bps{RESET}"

            print(
                f"{BOLD}{g.canonical_symbol:<10}{RESET}  "
                f"{rank_str:<5}  "
                f"{broker_str}  "
                f"{r.unit:<6}  "
                f"{r.median_spread:<8.2f}  "
                f"{r.avg_spread:<8.2f}  "
                f"{r.p95_spread:<8.2f}  "
                f"{BOLD}{r.spread_bps:<12.2f}{RESET}  "
                f"{delta_str:<22}"
            )
        print(f"{GRAY}{'.' * 115}{RESET}")
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
                "max_spread": round(float(r.max_spread), 4),
                "metric_basis": r.metric_basis,
                "spread_bps": round(float(r.spread_bps), 4),
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

    report_data = {
        "metric": "Spread (bps)",
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


