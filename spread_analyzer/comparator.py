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
    spread_to_vol_pct: float
    avg_daily_volatility_pct: float
    avg_daily_volatility: float
    total_ticks: int
    sampled_minutes: int
    composite_score: float = 0.0
    rank: int = 0
    savings_vs_worst_bps: float = 0.0


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
    2. Tier 2: Suffix/Prefix stripping (e.g. 'Cash', '.raw', '#', etc.) checked against reverse_map.
    3. Tier 3: Longest alias substring matching (checks if any known alias with length >= 4
       is contained within the symbol, or if the symbol is contained within an alias).
    4. Fallback: Generic noise stripping.
    """
    s_upper = symbol.strip().upper()

    # Tier 1: Exact match
    if s_upper in reverse_map:
        return reverse_map[s_upper]

    # Tier 2: Common broker suffix & prefix stripping checked against reverse_map
    s_clean = s_upper
    for suffix in (".RAW", ".PRO", ".A", ".CASH", "CASH", "SPOT", ".M", "M"):
        if s_clean.endswith(suffix):
            cand = s_clean[:-len(suffix)]
            if cand in reverse_map:
                return reverse_map[cand]

    if s_clean.startswith("#") or s_clean.startswith("."):
        cand = s_clean[1:]
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

    # Tier 4: Fallback generic noise stripping
    for suffix in (".RAW", ".PRO", ".A", ".CASH", "CASH"):
        if s_clean.endswith(suffix):
            return s_clean[:-len(suffix)]

    if s_clean.startswith("#") or s_clean.startswith("."):
        return s_clean[1:]

    return s_upper


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
    w_bps: float = 0.5,
    w_vol: float = 0.5,
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
            composite = (w_bps * spread_bps) + (w_vol * spread_to_vol_pct)

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
                composite_score=composite,
            )
            records.append(record)

    return records


def run_cross_broker_comparison(
    output_dir: Path,
    mappings_file: Path,
    w_bps: float = 0.5,
    w_vol: float = 0.5,
) -> Tuple[List[CanonicalComparisonGroup], Dict[str, BrokerLeaderboardStats]]:
    reverse_map = load_symbol_mappings(mappings_file)
    files = discover_summary_files(output_dir)

    if not files:
        logger.warning(f"No spread_summary.csv files found in {output_dir}")
        return [], {}

    all_records: List[BrokerSymbolRecord] = []
    broker_tags: set = set()
    for broker_tag, csv_path in files:
        recs = parse_summary_csv(broker_tag, csv_path, reverse_map, w_bps=w_bps, w_vol=w_vol)
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
        recs_sorted = sorted(recs, key=lambda x: (x.composite_score, x.spread_bps, x.median_spread))

        worst_bps = max((r.spread_bps for r in recs_sorted), default=0.0)
        is_contested = (len(recs_sorted) > 1)

        for rank_idx, r in enumerate(recs_sorted, start=1):
            r.rank = rank_idx
            r.savings_vs_worst_bps = max(0.0, worst_bps - r.spread_bps)

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

        winner = recs_sorted[0] if recs_sorted else None
        runner_up = recs_sorted[1] if len(recs_sorted) > 1 else None
        bps_diff = (runner_up.spread_bps - winner.spread_bps) if (winner and runner_up) else 0.0

        group = CanonicalComparisonGroup(
            canonical_symbol=canonical,
            records=recs_sorted,
            winner=winner,
            runner_up=runner_up,
            bps_difference=bps_diff,
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
    w_bps: float = 0.5,
    w_vol: float = 0.5,
) -> None:
    print(f"\n{BOLD}{CYAN}=== CROSS-BROKER SPREAD COMPARISON SUMMARY ==={RESET}")
    print(f"{GRAY}Scoring Formula : {BOLD}{int(w_bps*100)}% Spread(bps) + {int(w_vol*100)}% Spread/Vol(%){RESET} (Lower Score = Better Execution)")
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
    h_med, h_avg, h_bps, h_vol, h_scr, h_svg = "MEDIAN", "AVG", "BPS", "VOL%", "SCORE", "SAVINGS"
    print(f"\n{BOLD}{h_sym:<10}  {h_rnk:<5}  {h_brk:<35}  {h_unt:<6}  {h_med:<8}  {h_avg:<8}  {h_bps:<8}  {h_vol:<8}  {h_scr:<8}  {h_svg:<10}{RESET}")
    print(f"{GRAY}{'-'*115}{RESET}")

    for g in groups:
        is_contested = len(g.records) > 1
        for r in g.records:
            if r.rank == 1:
                rank_str = f"{GREEN}{BOLD}#1 [BEST]{RESET}"
                broker_str = f"{GREEN}{BOLD}{r.broker_tag:<35}{RESET}"
            elif r.rank == 2:
                rank_str = f"{ORANGE}#2{RESET}"
                broker_str = f"{r.broker_tag:<35}"
            else:
                rank_str = f"{GRAY}#{r.rank}{RESET}"
                broker_str = f"{GRAY}{r.broker_tag:<35}{RESET}"

            savings_str = f"{GREEN}+{r.savings_vs_worst_bps:.2f} bps{RESET}" if (r.rank == 1 and is_contested) else "-"

            print(
                f"{BOLD}{g.canonical_symbol:<10}{RESET}  "
                f"{rank_str:<5}  "
                f"{broker_str}  "
                f"{r.unit:<6}  "
                f"{r.median_spread:<8.2f}  "
                f"{r.avg_spread:<8.2f}  "
                f"{r.spread_bps:<8.2f}  "
                f"{r.spread_to_vol_pct:<8.2f}  "
                f"{BOLD}{r.composite_score:<8.2f}{RESET}  "
                f"{savings_str:<10}"
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
        "spread_to_vol_pct",
        "avg_daily_volatility_pct",
        "avg_daily_volatility",
        "composite_score",
        "savings_vs_worst_bps",
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
                    "spread_to_vol_pct": round(r.spread_to_vol_pct, 4),
                    "avg_daily_volatility_pct": round(r.avg_daily_volatility_pct, 4),
                    "avg_daily_volatility": round(r.avg_daily_volatility, 4),
                    "composite_score": round(r.composite_score, 4),
                    "savings_vs_worst_bps": round(r.savings_vs_worst_bps, 4),
                    "total_ticks": r.total_ticks,
                    "sampled_minutes": r.sampled_minutes,
                })
    return csv_path


def generate_comparison_html(
    groups: List[CanonicalComparisonGroup],
    leaderboard: Dict[str, BrokerLeaderboardStats],
    output_path: Path,
    w_bps: float = 0.5,
    w_vol: float = 0.5,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    leaderboard_html = []
    sorted_leaderboard = sorted(
        leaderboard.values(),
        key=lambda x: (x.avg_points, x.total_points, x.first_places),
        reverse=True
    )
    for idx, s in enumerate(sorted_leaderboard, start=1):
        is_first = (idx == 1)
        border_cls = "border-amber-500/50 bg-gray-900/90 shadow-lg shadow-amber-500/5" if is_first else "border-gray-800 bg-gray-900/60"
        score_badge_cls = "bg-amber-500/20 text-amber-400 border-amber-500/40" if is_first else "bg-gray-800 text-gray-300 border-gray-700"
        trophy = "🏆 " if is_first else ""

        card = f"""
        <div class="p-4 rounded-xl border {border_cls} flex flex-col justify-between space-y-3">
            <div class="flex items-center justify-between">
                <div>
                    <span class="text-[11px] text-gray-500 font-mono block">RANK #{idx}</span>
                    <span class="text-sm font-bold text-white tracking-tight">{trophy}{s.broker_tag}</span>
                </div>
                <div class="text-right">
                    <span class="px-2.5 py-1 rounded text-xs font-bold font-mono border {score_badge_cls}">
                        {s.avg_points:.2f} PTS/SYM
                    </span>
                </div>
            </div>

            <!-- Medals & Places Breakdown -->
            <div class="grid grid-cols-4 gap-1.5 pt-2 border-t border-gray-800/80 text-center font-mono text-xs">
                <div class="bg-gray-950/60 py-1.5 rounded border border-gray-800/50">
                    <span class="text-gray-500 block text-[10px]">🥇 1ST</span>
                    <span class="text-emerald-400 font-bold">{s.first_places}</span>
                </div>
                <div class="bg-gray-950/60 py-1.5 rounded border border-gray-800/50">
                    <span class="text-gray-500 block text-[10px]">🥈 2ND</span>
                    <span class="text-amber-400 font-bold">{s.second_places}</span>
                </div>
                <div class="bg-gray-950/60 py-1.5 rounded border border-gray-800/50">
                    <span class="text-gray-500 block text-[10px]">🥉 3RD</span>
                    <span class="text-orange-400 font-bold">{s.third_places}</span>
                </div>
                <div class="bg-gray-950/60 py-1.5 rounded border border-gray-800/50">
                    <span class="text-gray-500 block text-[10px]">TOTAL</span>
                    <span class="text-white font-bold">{s.total_points:.0f}</span>
                </div>
            </div>

            <div class="text-[11px] text-gray-400 font-mono flex justify-between">
                <span>Contested symbols: <strong class="text-gray-200">{s.contested_symbols}</strong></span>
                <span>Total offered: <strong class="text-gray-400">{s.total_symbols}</strong></span>
            </div>
        </div>
        """
        leaderboard_html.append(card)

    rows_html = []
    for g in groups:
        is_contested = len(g.records) > 1
        for r in g.records:
            is_win = (r.rank == 1)
            rank_badge = '<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 font-mono font-bold whitespace-nowrap">#1 🏆</span>' if is_win else f'<span class="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-800 text-gray-400 font-mono whitespace-nowrap">#{r.rank}</span>'
            row_bg = "bg-emerald-950/10" if is_win else ""
            broker_name = f"<span class='font-semibold text-white'>{r.broker_tag}</span>" if is_win else f"<span class='text-gray-400'>{r.broker_tag}</span>"

            savings_cell = f"<span class='text-emerald-400 font-mono font-bold whitespace-nowrap'>+{r.savings_vs_worst_bps:.2f} bps</span>" if (is_win and is_contested) else "<span class='text-gray-600 font-mono'>-</span>"

            row = f"""
            <tr class="hover:bg-gray-800/60 transition {row_bg}">
                <td class="px-4 py-3 font-bold text-blue-400 font-mono whitespace-nowrap" data-val="{g.canonical_symbol}">{g.canonical_symbol}</td>
                <td class="px-4 py-3 whitespace-nowrap" data-val="{r.rank}">{rank_badge}</td>
                <td class="px-4 py-3 whitespace-nowrap" data-val="{r.broker_tag}">{broker_name} <span class="text-xs text-gray-500 ml-1 font-mono">({r.symbol})</span></td>
                <td class="px-4 py-3 text-gray-400" data-val="{r.unit}">{r.unit}</td>
                <td class="px-4 py-3 text-green-400 font-mono" data-val="{r.min_spread}">{r.min_spread:.2f}</td>
                <td class="px-4 py-3 text-gray-300 font-mono" data-val="{r.median_spread}">{r.median_spread:.2f}</td>
                <td class="px-4 py-3 text-amber-400 font-mono" data-val="{r.avg_spread}">{r.avg_spread:.2f}</td>
                <td class="px-4 py-3 text-gray-300 font-mono" data-val="{r.p95_spread}">{r.p95_spread:.2f}</td>
                <td class="px-4 py-3 text-red-400 font-mono" data-val="{r.max_spread}">{r.max_spread:.2f}</td>
                <td class="px-4 py-3 text-cyan-400 font-mono font-bold" data-val="{r.spread_bps}">{r.spread_bps:.2f} bps</td>
                <td class="px-4 py-3 text-cyan-400 font-mono" data-val="{r.spread_to_vol_pct}">{r.spread_to_vol_pct:.2f}%</td>
                <td class="px-4 py-3 text-gray-300 font-mono cursor-help" title="{r.avg_daily_volatility:.1f} {r.unit}" data-val="{r.avg_daily_volatility_pct}">{r.avg_daily_volatility_pct:.2f}%</td>
                <td class="px-4 py-3 font-mono font-bold text-amber-300" data-val="{r.composite_score}">{r.composite_score:.2f}</td>
                <td class="px-4 py-3" data-val="{r.savings_vs_worst_bps}">{savings_cell}</td>
            </tr>
            """
            rows_html.append(row)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MetaTrader 5 Cross-Broker Spread Comparison</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #0B0F19;
        }}
        .font-mono {{
            font-family: 'JetBrains Mono', monospace;
        }}
        .sort-th {{
            cursor: pointer;
            user-select: none;
            transition: color 0.15s ease;
        }}
        .sort-th:hover {{
            color: #FFFFFF !important;
        }}
    </style>
</head>
<body class="text-gray-200 min-h-screen p-4 md:p-8">
    <div class="max-w-7xl mx-auto space-y-6">
        <div class="flex flex-col md:flex-row md:items-center justify-between border-b border-gray-800 pb-5 gap-4">
            <div>
                <div class="flex items-center gap-3">
                    <h1 class="text-2xl md:text-3xl font-bold tracking-tight text-white">Cross-Broker Spread Comparison</h1>
                    <span class="px-2.5 py-0.5 rounded text-xs font-semibold bg-emerald-900/60 text-emerald-400 border border-emerald-700/50">Multi-Broker Benchmarking</span>
                </div>
                <p class="text-sm text-gray-400 mt-1">Evaluating execution friction across MetaTrader 5 accounts</p>
            </div>
            <div class="text-xs font-mono bg-gray-900/80 px-4 py-2.5 rounded-lg border border-gray-800 space-y-1">
                <div><span class="text-gray-500">SCORING FORMULA:</span> <span class="text-cyan-400 font-bold">{int(w_bps*100)}% bps + {int(w_vol*100)}% vol_ratio</span></div>
                <div><span class="text-gray-500">CRITERION:</span> <span class="text-gray-300">Lowest Composite Score Wins (Rank #1 🏆)</span></div>
            </div>
        </div>

        <div>
            <h2 class="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3">Broker Win Leaderboard</h2>
            <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                {''.join(leaderboard_html)}
            </div>
        </div>

        <div class="flex flex-col sm:flex-row items-center justify-between gap-3 bg-gray-900/60 p-4 rounded-xl border border-gray-800">
            <div class="relative w-full sm:w-80">
                <input type="text" id="symbolSearch" onkeyup="filterTable()" placeholder="Search symbol (e.g. EURUSD, GOLD)..." class="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 font-mono">
            </div>
            <div class="text-xs text-gray-400">
                <span class="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 mr-1"></span>Winner (Rank #1)
                <span class="inline-block w-2.5 h-2.5 rounded-full bg-amber-500 ml-3 mr-1"></span>Runner-up
            </div>
        </div>

        <div class="bg-gray-900/60 rounded-xl border border-gray-800 overflow-hidden shadow-xl">
            <div class="p-4 border-b border-gray-800 flex items-center justify-between">
                <h2 class="text-base font-semibold text-white">Grouped Head-to-Head Comparisons</h2>
                <p class="text-xs text-gray-400">Click any column header to sort</p>
            </div>
            <div class="overflow-x-auto">
                <table id="comparisonTable" class="w-full text-left text-sm border-collapse">
                    <thead class="bg-gray-950/80 text-xs uppercase text-gray-400 font-semibold border-b border-gray-800">
                        <tr>
                            <th onclick="sortTable(0)" class="sort-th px-4 py-3 whitespace-nowrap"><span class="flex items-center gap-1">Canonical <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(1)" class="sort-th px-4 py-3 whitespace-nowrap min-w-[85px]"><span class="flex items-center gap-1">Rank <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(2)" class="sort-th px-4 py-3 whitespace-nowrap"><span class="flex items-center gap-1">Broker Account <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(3)" class="sort-th px-4 py-3"><span class="flex items-center gap-1">Unit <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(4)" class="sort-th px-4 py-3 text-green-400"><span class="flex items-center gap-1">Min <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(5)" class="sort-th px-4 py-3 text-gray-300"><span class="flex items-center gap-1">Median <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(6)" class="sort-th px-4 py-3 text-amber-400"><span class="flex items-center gap-1">Avg <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(7)" class="sort-th px-4 py-3 text-gray-300"><span class="flex items-center gap-1">P95 <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(8)" class="sort-th px-4 py-3 text-red-400"><span class="flex items-center gap-1">Max <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(9)" class="sort-th px-4 py-3 text-cyan-400"><span class="flex items-center gap-1">Spread (bps) <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(10)" class="sort-th px-4 py-3 text-cyan-400"><span class="flex items-center gap-1">Spread / Vol <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(11)" class="sort-th px-4 py-3"><span class="flex items-center gap-1">Daily Vol (%) <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(12)" class="sort-th px-4 py-3 text-amber-300"><span class="flex items-center gap-1">Score <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                            <th onclick="sortTable(13)" class="sort-th px-4 py-3 text-emerald-400"><span class="flex items-center gap-1">Savings <span class="sort-icon text-gray-600 text-[10px]">↕</span></span></th>
                        </tr>
                    </thead>
                    <tbody id="comparisonTableBody" class="divide-y divide-gray-800/60">
                        {''.join(rows_html)}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="text-center text-xs text-gray-500 pt-4 pb-6">
            Generated with MetaTrader 5 Cross-Broker Comparator • High-frequency quantitative analytics
        </div>
    </div>

    <script>
        let currentSortCol = null;
        let currentSortAsc = true;

        function sortTable(colIndex) {{
            const table = document.getElementById('comparisonTable');
            const tbody = document.getElementById('comparisonTableBody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const headers = table.querySelectorAll('.sort-th');

            if (currentSortCol === colIndex) {{
                currentSortAsc = !currentSortAsc;
            }} else {{
                currentSortCol = colIndex;
                currentSortAsc = true;
            }}

            headers.forEach((th, idx) => {{
                const icon = th.querySelector('.sort-icon');
                if (idx === colIndex) {{
                    icon.textContent = currentSortAsc ? '▲' : '▼';
                    icon.classList.remove('text-gray-600');
                    icon.classList.add('text-blue-400');
                }} else {{
                    icon.textContent = '↕';
                    icon.classList.remove('text-blue-400');
                    icon.classList.add('text-gray-600');
                }}
            }});

            rows.sort((a, b) => {{
                const cellA = a.children[colIndex];
                const cellB = b.children[colIndex];

                const valA = cellA.getAttribute('data-val') !== null ? cellA.getAttribute('data-val') : cellA.innerText.trim();
                const valB = cellB.getAttribute('data-val') !== null ? cellB.getAttribute('data-val') : cellB.innerText.trim();

                const numA = parseFloat(valA);
                const numB = parseFloat(valB);

                if (!isNaN(numA) && !isNaN(numB)) {{
                    return currentSortAsc ? numA - numB : numB - numA;
                }}
                return currentSortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
            }});

            rows.forEach(r => tbody.appendChild(r));
        }}

        function filterTable() {{
            const query = document.getElementById('symbolSearch').value.toUpperCase();
            const rows = document.querySelectorAll('#comparisonTableBody tr');
            rows.forEach(row => {{
                const canonical = row.children[0].innerText.toUpperCase();
                const broker = row.children[2].innerText.toUpperCase();
                if (canonical.includes(query) || broker.includes(query)) {{
                    row.style.display = '';
                }} else {{
                    row.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>
"""
    output_path.write_text(html_content, encoding="utf-8")
    return output_path

