from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any


if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    BUNDLE_ROOT = PROJECT_ROOT
CONFIG_PATH = PROJECT_ROOT / "config.json"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config.example.json"
BUNDLED_EXAMPLE_CONFIG_PATH = BUNDLE_ROOT / "config.example.json"


DEFAULT_CONFIG: dict[str, Any] = {
    "miner_address": "prl1p2ka5l06wmq73kdsqec9k7fsv00jt76nfhk56e9nh82fn07qjualspfsxyp",
    "selected_pool": "AlphaPool PRL",
    "pools": [
        {
            "name": "AlphaPool PRL",
            "hashrate_name": "AlphaPool",
            "base_url": "https://pearl.alphapool.tech",
            "stats_path": "/api/stats",
            "miner_path_template": "/api/miner/{address}",
            "api_enabled": True,
            "default_fee_percent": 3.0,
            "default_payout_min_prl": 1.0,
            "payout_scheme": "PPLNS",
            "hashrate_no_hashrate": "2.3 Eh/s",
            "hashrate_no_share_percent": 8.4,
        },
        {
            "name": "Kryptex",
            "base_url": "https://pool.kryptex.com/prl",
            "api_enabled": False,
            "default_fee_percent": 1.0,
            "payout_scheme": "PROP",
            "hashrate_no_hashrate": "2.6 Eh/s",
            "hashrate_no_share_percent": 9.5,
        },
        {
            "name": "Pearlhash",
            "base_url": "https://pearlhash.xyz",
            "api_enabled": False,
            "default_fee_percent": 3.0,
            "payout_scheme": "PPLNS",
            "hashrate_no_hashrate": "6.9 Eh/s",
            "hashrate_no_share_percent": 24.8,
        },
        {
            "name": "Luckypool",
            "base_url": "https://pearl.luckypool.io",
            "api_enabled": False,
            "default_fee_percent": 1.0,
            "payout_scheme": "PPLNS",
            "hashrate_no_hashrate": "3.7 Eh/s",
            "hashrate_no_share_percent": 13.2,
        },
        {
            "name": "JETSKI",
            "base_url": "https://pearl.jetskipool.ai",
            "api_enabled": False,
            "default_fee_percent": 1.0,
            "payout_scheme": "PROP",
            "hashrate_no_hashrate": "242.4 Ph/s",
            "hashrate_no_share_percent": 0.9,
        },
        {
            "name": "BaikalMine",
            "base_url": "https://baikalmine.com/pools/pplns/pearl/dashboard",
            "api_enabled": False,
            "default_fee_percent": 0.5,
            "payout_scheme": "PPLNS",
            "hashrate_no_hashrate": "194.4 Ph/s",
            "hashrate_no_share_percent": 0.7,
        },
        {
            "name": "akoya",
            "base_url": "https://akoyapool.com",
            "api_enabled": False,
            "default_fee_percent": 2.0,
            "payout_scheme": "PPLTS",
            "hashrate_no_hashrate": "181.0 Ph/s",
            "hashrate_no_share_percent": 0.7,
        },
        {
            "name": "Himpool SOLO",
            "hashrate_name": "Himpool",
            "base_url": "https://himpool.com/pools/prl",
            "api_enabled": False,
            "default_fee_percent": 2.0,
            "payout_scheme": "SOLO",
            "hashrate_no_hashrate": "15.7 Ph/s",
            "hashrate_no_share_percent": 0.1,
        },
        {
            "name": "Himpool PPLNS",
            "hashrate_name": "Himpool",
            "base_url": "https://himpool.com/pools/prl",
            "api_enabled": False,
            "default_fee_percent": 1.0,
            "payout_scheme": "PPLNS",
            "hashrate_no_hashrate": "N/A",
        },
        {
            "name": "NushyPool PPS",
            "hashrate_name": "NushyPool",
            "base_url": "https://nushypool.com/prl/pool",
            "api_enabled": False,
            "default_fee_percent": 1.0,
            "payout_scheme": "PPS",
            "hashrate_no_hashrate": "1.3 Ph/s",
            "hashrate_no_share_percent": 0.0,
        },
        {
            "name": "NushyPool SOLO",
            "hashrate_name": "NushyPool",
            "base_url": "https://nushypool.com/prl/pool",
            "api_enabled": False,
            "default_fee_percent": 1.0,
            "payout_scheme": "SOLO",
            "hashrate_no_hashrate": "N/A",
        },
        {
            "name": "Mineprl",
            "base_url": "https://mineprl.com",
            "api_enabled": False,
            "default_fee_percent": 4.4,
            "payout_scheme": "PPLNS",
            "hashrate_no_hashrate": "929.8 Gh/s",
            "hashrate_no_share_percent": 0.0,
        },
        {
            "name": "HeroMiners",
            "base_url": "https://pearl.herominers.com",
            "api_enabled": False,
            "default_fee_percent": 0.0,
            "payout_scheme": "PROP",
            "hashrate_no_hashrate": "904.7 Mh/s",
            "hashrate_no_share_percent": 0.0,
        },
    ],
    "selected_mining_software": "AlphaMiner",
    "mining_software": [
        {
            "name": "AlphaMiner",
            "algorithm": "pearl",
            "dev_fee_percent": 1.0,
            "nvidia": True,
            "amd": False,
            "intel": False,
            "cpu": False,
            "source_url": "https://hashrate.no/miners/AlphaMiner",
        },
        {
            "name": "SRBMiner",
            "algorithm": "pearlhash",
            "dev_fee_percent": 3.0,
            "nvidia": True,
            "amd": False,
            "intel": False,
            "cpu": False,
            "source_url": "https://hashrate.no/miners/SRBMiner",
        },
    ],
    "selected_market_source": "PRLScan",
    "market_sources": [
        {
            "name": "PRLScan",
            "kind": "prlscan",
            "url": "https://api.prlscan.com/v1/market/prl",
        },
        {
            "name": "SafeTrade",
            "kind": "safetrade",
            "market_url": "https://safetrade.com/exchange/PRL-USDT?type=basic",
            "api_urls": [
                "https://safetrade.com/api/v2/trade/public/tickers/prlusdt",
                "https://safetrade.com/api/v2/trade/public/tickers/prl-usdt",
                "https://safetrade.com/api/v2/peatio/public/markets/prlusdt/tickers",
                "https://safetrade.com/api/v2/peatio/public/tickers/prlusdt",
            ],
        },
        {
            "name": "SafeTrade mirror",
            "kind": "safetrade",
            "market_url": "https://safetrade.com/exchange/PRL-USDT?type=basic",
            "api_urls": [
                "https://safe.trade/api/v2/trade/public/tickers/prlusdt",
                "https://safe.trade/api/v2/trade/public/tickers/prl-usdt",
                "https://safe.trade/api/v2/peatio/public/markets/prlusdt/tickers",
                "https://safe.trade/api/v2/peatio/public/tickers/prlusdt",
            ],
        },
    ],
    "market_url": "https://api.prlscan.com/v1/market/prl",
    "chain_summary_url": "https://api.prlscan.com/v1/analytics/summary",
    "fx_url": "https://open.er-api.com/v6/latest/USD",
    "exchange_url": "https://safetrade.com/exchange/PRL-USDT?type=basic",
    "hashrate_info_url": "https://hashrate.no/coins/PRL/",
    "repository_url": "https://github.com/stlin256/prl-today",
    "proxy": {
        "enabled": True,
        "use_env": True,
        "url": "http://127.0.0.1:7897",
    },
    "calculation": {
        "fee_mode": "auto",
        "fee_override_percent": 3.0,
        "tool_fee_mode": "auto",
        "tool_fee_percent": 1.0,
        "price_mode": "auto",
        "manual_price_usd": 0.52,
        "fx_mode": "auto",
        "manual_usd_cny": 6.78,
        "hashrate_mode": "fit",
    },
    "refresh": {
        "miner_seconds": 30,
        "pool_seconds": 30,
        "market_seconds": 30,
        "chain_seconds": 60,
        "fx_seconds": 3600,
        "ui_tick_seconds": 1,
    },
    "refresh_seconds": 30,
    "display": {
        "level": "standard",
        "currency": "auto",
        "configured": False,
    },
    "window": {
        "x": 80,
        "y": 80,
        "width": 246,
        "height": 106,
        "alpha": 0.96,
        "compact": False,
    },
}


def deep_merge(default: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(default)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        elif key in {"pools", "mining_software", "market_sources"} and isinstance(value, list) and isinstance(result.get(key), list):
            result[key] = merge_named_list(result[key], value)
        else:
            result[key] = value
    return result


def merge_named_list(default: list[Any], override: list[Any]) -> list[Any]:
    if not all(isinstance(item, dict) and "name" in item for item in [*default, *override]):
        return copy.deepcopy(override)
    merged = {str(item["name"]): copy.deepcopy(item) for item in default}
    order = [str(item["name"]) for item in default]
    for item in override:
        name = str(item["name"])
        if name in merged:
            merged[name] = deep_merge(merged[name], item)
        else:
            order.append(name)
            merged[name] = copy.deepcopy(item)
    return [merged[name] for name in order]


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return deep_merge(DEFAULT_CONFIG, json.load(f))

    example_path = EXAMPLE_CONFIG_PATH if EXAMPLE_CONFIG_PATH.exists() else BUNDLED_EXAMPLE_CONFIG_PATH
    if example_path.exists():
        with example_path.open("r", encoding="utf-8") as f:
            config = deep_merge(DEFAULT_CONFIG, json.load(f))
    else:
        config = copy.deepcopy(DEFAULT_CONFIG)
    save_config(config, path)
    return config


def save_config(config: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")


def selected_pool(config: dict[str, Any]) -> dict[str, Any]:
    name = config.get("selected_pool")
    pools = config.get("pools") or []
    for pool in pools:
        if pool.get("name") == name:
            return pool
    if pools:
        return pools[0]
    return DEFAULT_CONFIG["pools"][0]


def pool_names(config: dict[str, Any]) -> list[str]:
    return [str(pool.get("name", "Unnamed Pool")) for pool in config.get("pools", [])]


def selected_mining_software(config: dict[str, Any]) -> dict[str, Any]:
    name = config.get("selected_mining_software")
    software = config.get("mining_software") or []
    for item in software:
        if item.get("name") == name:
            return item
    if software:
        return software[0]
    return DEFAULT_CONFIG["mining_software"][0]


def mining_software_names(config: dict[str, Any]) -> list[str]:
    return [str(item.get("name", "Unnamed Miner")) for item in config.get("mining_software", [])]


def selected_market_source(config: dict[str, Any]) -> dict[str, Any]:
    name = config.get("selected_market_source")
    sources = config.get("market_sources") or []
    for source in sources:
        if source.get("name") == name:
            return source
    if sources:
        return sources[0]
    return {
        "name": "PRLScan",
        "kind": "prlscan",
        "url": str(config.get("market_url", DEFAULT_CONFIG["market_url"])),
    }


def market_source_names(config: dict[str, Any]) -> list[str]:
    return [str(source.get("name", "Unnamed Source")) for source in config.get("market_sources", [])]


def refresh_seconds(config: dict[str, Any], key: str) -> int:
    refresh = config.get("refresh") or {}
    legacy = int(config.get("refresh_seconds") or DEFAULT_CONFIG["refresh_seconds"])
    default = int((DEFAULT_CONFIG["refresh"] or {}).get(key, legacy))
    try:
        value = int(float(refresh.get(key, default)))
    except (TypeError, ValueError):
        value = default
    if key == "ui_tick_seconds":
        return max(value, 1)
    return max(value, 5)
