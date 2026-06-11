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
            "base_url": "https://pearl.alphapool.tech",
            "stats_path": "/api/stats",
            "miner_path_template": "/api/miner/{address}",
            "default_fee_percent": 3.0,
            "default_payout_min_prl": 1.0,
        }
    ],
    "market_url": "https://api.prlscan.com/v1/market/prl",
    "chain_summary_url": "https://api.prlscan.com/v1/analytics/summary",
    "fx_url": "https://open.er-api.com/v6/latest/USD",
    "exchange_url": "https://safetrade.com/exchange/PRL-USDT?type=basic",
    "hashrate_info_url": "https://hashrate.no/coins/PRL/",
    "proxy": {
        "enabled": True,
        "use_env": True,
        "url": "http://127.0.0.1:7897",
    },
    "calculation": {
        "fee_mode": "auto",
        "fee_override_percent": 3.0,
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
    },
    "window": {
        "x": 80,
        "y": 80,
        "width": 282,
        "height": 132,
        "alpha": 0.96,
        "compact": False,
    },
}


def deep_merge(default: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(default)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


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
