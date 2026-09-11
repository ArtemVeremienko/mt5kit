"""
Broker commission calculation and multi-asset conversion engine.

Converts round-turn broker commissions ($/lot) into native spread units (pips/cents/pts)
and basis points (bps) based on asset class and quote currency dynamics.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

logger = logging.getLogger("spread_commissions")

AssetClass = Literal["forex", "metals", "indices", "commodities", "crypto", "other"]

FX_CURRENCIES = {
    "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD",
    "SEK", "NOK", "TRY", "ZAR", "MXN", "PLN", "SGD", "HKD",
    "CNH", "CZK", "HUF", "ILS", "DKK", "THB",
}


@dataclass
class CommissionImpact:
    commission_rt_usd: float
    commission_spread: float
    commission_bps: float
    effective_spread: float
    effective_spread_bps: float
    asset_class: str


@dataclass
class CommissionProfile:
    default_rates: Dict[str, float] = field(default_factory=lambda: {
        "forex": 7.0,
        "metals": 7.0,
        "indices": 0.0,
        "commodities": 0.0,
        "crypto": 0.0,
        "other": 0.0,
    })
    broker_rates: Dict[str, Dict[str, float]] = field(default_factory=dict)
    symbol_overrides: Dict[str, float] = field(default_factory=dict)

    def get_rate(self, broker_tag: str, symbol: str, asset_class: str) -> float:
        """Resolves applicable round-turn USD commission per standard lot."""
        s_upper = symbol.strip().upper()
        if s_upper in self.symbol_overrides:
            return float(self.symbol_overrides[s_upper])

        # Match broker_tag case-insensitively and substring-insensitively
        b_clean = broker_tag.strip().upper()
        for b_name, rates in self.broker_rates.items():
            b_cand = b_name.strip().upper()
            if b_cand in b_clean or b_clean in b_cand:
                if asset_class in rates:
                    return float(rates[asset_class])
                if "default" in rates:
                    return float(rates["default"])

        return float(self.default_rates.get(asset_class, 0.0))


def classify_asset_class(symbol: str) -> Tuple[AssetClass, str]:
    """
    Classifies a financial instrument into its asset class and sub-type.

    Returns:
        (asset_class, subtype):
        - asset_class: 'forex' | 'metals' | 'indices' | 'commodities' | 'crypto' | 'other'
        - subtype: e.g. 'usd_quote', 'usd_base', 'cross', 'gold', 'silver', etc.
    """
    s = symbol.strip().upper().lstrip("#.")

    # Strip standard broker suffixes
    for suffix in (".RAW", ".PRO", ".A", ".CASH", "CASH", "_SPOT", "SPOT", ".M", "M"):
        if s.endswith(suffix):
            s = s[:-len(suffix)]
            break

    # 1. Metals
    if any(k in s for k in ("XAU", "GOLD")):
        return "metals", "gold"
    if any(k in s for k in ("XAG", "SILVER")):
        return "metals", "silver"
    if any(k in s for k in ("XPT", "PLATINUM", "XPD", "PALLADIUM")):
        return "metals", "other_metal"

    # 2. Crypto
    crypto_coins = ("BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "BNB", "ADA", "DOT", "AVAX")
    if any(s.startswith(c) or s.endswith(c) for c in crypto_coins) or "CRYPTO" in s:
        return "crypto", "crypto"

    # 3. Indices
    index_keywords = (
        "500", "100", "30", "40", "225", "200", "50",
        "DAX", "SPX", "NDX", "WS30", "US500", "US100", "US30",
        "GER40", "JP225", "UK100", "AUS200", "EU50", "NIKKEI",
    )
    if any(k in s for k in index_keywords):
        return "indices", "index"

    # 4. Commodities & Energies
    commodity_keywords = (
        "WTI", "BRENT", "OIL", "USOIL", "UKOIL", "NATGAS", "NGAS", "GAS",
        "CORN", "WHEAT", "SOY", "COPPER", "COFFEE", "SUGAR",
    )
    if any(k in s for k in commodity_keywords):
        return "commodities", "commodity"

    # 5. Forex Currency Pairs
    if len(s) == 6 and s[:3] in FX_CURRENCIES and s[3:6] in FX_CURRENCIES:
        base, quote = s[:3], s[3:6]
        if quote == "USD":
            return "forex", "usd_quote"
        elif base == "USD":
            return "forex", "usd_base"
        else:
            return "forex", "cross"

    return "other", "unknown"


def calculate_commission_impact(
    symbol: str,
    broker_tag: str,
    unit: str,
    median_spread: float,
    spread_bps: float,
    mean_price: float,
    profile: CommissionProfile,
    enable_commission: bool = True,
) -> CommissionImpact:
    """
    Computes commission add-on in spread units and basis points.

    Formula breakdown:
    - Forex USD-Quoted (EURUSD): 1 pip = $10/lot -> comm_pips = comm / 10.0
    - Forex USD-Base (USDJPY): Notional = $100,000 -> comm_bps = comm / 10.0
    - Metals (XAUUSD): 1 lot = 100 oz -> comm / 100 oz = comm in cents
    - Indices / Commodities: default $0.0 commission
    """
    asset_class, subtype = classify_asset_class(symbol)

    if not enable_commission:
        return CommissionImpact(
            commission_rt_usd=0.0,
            commission_spread=0.0,
            commission_bps=0.0,
            effective_spread=round(median_spread, 4),
            effective_spread_bps=round(spread_bps, 4),
            asset_class=asset_class,
        )

    comm_rt = profile.get_rate(broker_tag, symbol, asset_class)
    if comm_rt <= 0.0:
        return CommissionImpact(
            commission_rt_usd=0.0,
            commission_spread=0.0,
            commission_bps=0.0,
            effective_spread=round(median_spread, 4),
            effective_spread_bps=round(spread_bps, 4),
            asset_class=asset_class,
        )

    # Asset-specific conversion
    if asset_class == "forex":
        if subtype == "usd_quote":
            # 1 standard lot = 100,000 base currency. 1 pip (0.0001) = $10.00 USD.
            comm_spread = comm_rt / 10.0
            comm_bps = (comm_rt / (100000.0 * mean_price) * 10000.0) if mean_price > 0.0 else 0.0
        elif subtype == "usd_base":
            # 1 standard lot = $100,000 USD notional. comm_bps is fixed at (comm / 100k) * 10000 = comm / 10.0
            comm_bps = comm_rt / 10.0
            # Convert bps to pips: pip_scale = 0.01 for JPY (3-digit), 0.0001 for others
            pip_scale = 0.01 if "JPY" in symbol.upper() else 0.0001
            comm_spread = (comm_bps / 10000.0 * mean_price / pip_scale) if pip_scale > 0.0 else 0.0
        else:
            # Cross pair (e.g. EURGBP, EURJPY)
            comm_spread = comm_rt / 10.0
            comm_bps = (comm_rt / (100000.0 * mean_price) * 10000.0) if mean_price > 0.0 else 0.0

    elif asset_class == "metals":
        # 1 standard lot = 100 troy ounces
        # Dollar fee per oz = comm_rt / 100.0
        # If quoted in cents (0.01 / oz), 1 cent = $1.00/lot -> comm in cents = comm_rt
        if unit == "cents":
            comm_spread = comm_rt
        elif unit == "pips":
            # 1 pip = $0.10 / oz -> comm in pips = comm_rt / 10.0
            comm_spread = comm_rt / 10.0
        else:
            comm_spread = comm_rt / 100.0

        notional = 100.0 * mean_price if mean_price > 0.0 else 250000.0
        comm_bps = (comm_rt / notional * 10000.0) if notional > 0.0 else 0.0

    elif asset_class == "indices":
        # CFD indices typically zero commission; if configured, comm_spread added in points
        comm_spread = 0.0
        comm_bps = (comm_rt / mean_price * 10000.0) if mean_price > 0.0 else 0.0

    else:
        comm_spread = 0.0
        comm_bps = 0.0

    eff_spread = median_spread + comm_spread
    eff_bps = spread_bps + comm_bps

    return CommissionImpact(
        commission_rt_usd=round(comm_rt, 2),
        commission_spread=round(comm_spread, 4),
        commission_bps=round(comm_bps, 4),
        effective_spread=round(eff_spread, 4),
        effective_spread_bps=round(eff_bps, 4),
        asset_class=asset_class,
    )


def load_commission_profile(
    config_path: Optional[Path] = None,
    cli_overrides: Optional[str] = None,
) -> CommissionProfile:
    """Loads commission profile from JSON file and merges optional CLI overrides."""
    profile = CommissionProfile()

    # Look for config_path or default broker_commissions.json in spread_analyzer
    if config_path is None:
        default_cfg = Path(__file__).parent / "broker_commissions.json"
        if default_cfg.exists():
            config_path = default_cfg

    if config_path and config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "default" in data:
                profile.default_rates.update(data["default"])
            if "brokers" in data:
                for b_name, b_rates in data["brokers"].items():
                    if isinstance(b_rates, dict):
                        profile.broker_rates[b_name] = b_rates
                    elif isinstance(b_rates, (int, float)):
                        profile.broker_rates[b_name] = {"forex": float(b_rates), "metals": float(b_rates)}
            if "symbols" in data:
                profile.symbol_overrides.update(data["symbols"])
            logger.info(f"Loaded broker commission config from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load commission configuration {config_path}: {e}")

    # Parse CLI overrides: e.g. "Pepperstone:7.0,RoboForex:4.0,FxPro:0"
    if cli_overrides:
        for item in cli_overrides.split(","):
            if ":" in item:
                b_tag, val_str = item.split(":", 1)
                b_tag = b_tag.strip()
                try:
                    val = float(val_str.strip())
                    profile.broker_rates[b_tag] = {"forex": val, "metals": val}
                    logger.info(f"Applied CLI commission override: [{b_tag}] = ${val}/lot RT")
                except ValueError:
                    logger.warning(f"Invalid CLI commission value: '{item}'")

    return profile
