from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any, Iterable

from .api import DataSnapshot
from .config import selected_mining_software, selected_pool


GRAIN = 100_000_000
HASH_UNITS = {
    "H": 1.0,
    "KH": 1e3,
    "MH": 1e6,
    "GH": 1e9,
    "TH": 1e12,
    "PH": 1e15,
    "EH": 1e18,
}


@dataclass(slots=True)
class ProfitEstimate:
    today_prl: float
    today_usd: float
    today_cny: float
    projected_24h_prl: float
    projected_24h_usd: float
    projected_24h_cny: float
    observed_today_prl: float
    prl_per_second: float
    price_usd: float
    price_source: str
    usd_cny: float
    fee_percent: float
    tool_fee_percent: float
    hashrate_hps: float
    network_hashrate_hps: float
    block_reward_prl: float
    block_time_seconds: float
    source_summary: str
    errors: list[str]
    computed_at: datetime


def number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        out = float(value)
        if math.isfinite(out):
            return out
    except (TypeError, ValueError):
        pass
    return default


def parse_hashrate(text: Any) -> float:
    if isinstance(text, (int, float)):
        return float(text)
    if not isinstance(text, str):
        return 0.0
    parts = text.strip().replace("/s", "").split()
    if not parts:
        return 0.0
    value = number(parts[0])
    unit = "H"
    if len(parts) > 1:
        unit = parts[1].upper()
    elif parts[0] and parts[0][-1].isalpha():
        raw = parts[0].upper()
        for suffix in ("EH", "PH", "TH", "GH", "MH", "KH", "H"):
            if raw.endswith(suffix):
                value = number(raw[: -len(suffix)])
                unit = suffix
                break
    return value * HASH_UNITS.get(unit, 1.0)


def grains_to_prl(value: Any) -> float:
    return number(value) / GRAIN


def local_day(dt: datetime | None = None) -> str:
    dt = dt or datetime.now().astimezone()
    return dt.strftime("%Y-%m-%d")


def seconds_today(now: datetime | None = None) -> tuple[float, float]:
    now = now or datetime.now().astimezone()
    start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
    elapsed = max((now - start).total_seconds(), 0.0)
    return elapsed, max(86_400.0 - elapsed, 0.0)


def today_observed_prl(miner: dict[str, Any] | None, now: datetime | None = None) -> float:
    if not miner:
        return 0.0
    now = now or datetime.now().astimezone()
    today = now.date()
    total = 0.0
    for item in miner.get("payments") or []:
        if item.get("status") == "orphaned":
            continue
        ts = number(item.get("ts"), -1)
        if ts < 0:
            continue
        item_dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
        if item_dt.date() == today:
            total += grains_to_prl(item.get("amount_grain"))
    if total > 0:
        return total
    for item in miner.get("payments_by_day") or []:
        if item.get("day") == local_day(now):
            return number(item.get("amount_prl"))
    return 0.0


def median(values: Iterable[float]) -> float:
    vals = [v for v in values if math.isfinite(v) and v > 0]
    if not vals:
        return 0.0
    return statistics.median(vals)


def fit_hashrate_hps(series: list[dict[str, Any]], now_ts: float | None = None) -> float:
    points: list[tuple[float, float]] = []
    for row in series[-72:]:
        ts = number(row.get("ts"))
        y = number(row.get("hashrate"))
        if ts > 0 and y > 0:
            points.append((ts, y))
    if len(points) < 3:
        return 0.0

    now_ts = now_ts or datetime.now(timezone.utc).timestamp()
    x0 = points[-1][0]
    xs = [(x - x0) / 3600.0 for x, _ in points]
    ys = [y for _, y in points]
    xbar = sum(xs) / len(xs)
    ybar = sum(ys) / len(ys)
    denom = sum((x - xbar) ** 2 for x in xs)
    if denom <= 0:
        prediction = ys[-1]
    else:
        slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / denom
        intercept = ybar - slope * xbar
        prediction = intercept + slope * ((now_ts - x0) / 3600.0)

    center = median(ys[-12:]) or median(ys)
    if center <= 0:
        return max(prediction, 0.0)
    return min(max(prediction, center * 0.55), center * 1.45)


def worker_live_hashrate(miner: dict[str, Any] | None) -> float:
    if not miner:
        return 0.0
    total = 0.0
    for worker in miner.get("workers") or []:
        total += parse_hashrate(worker.get("hashrate_live") or worker.get("hashrate_1h") or worker.get("hashrate"))
    return total


def choose_hashrate(config: dict[str, Any], miner: dict[str, Any] | None) -> tuple[float, str]:
    mode = ((config.get("calculation") or {}).get("hashrate_mode") or "fit").lower()
    if not miner:
        return 0.0, "no miner data"
    choices = {
        "miner_1h": (number(miner.get("estHash1hRaw")), "miner 1h"),
        "miner_24h": (number(miner.get("estHash24hRaw")), "miner 24h"),
        "worker_live": (worker_live_hashrate(miner), "worker live"),
        "fit": (fit_hashrate_hps(miner.get("hashrate_series") or []), "fitted hashrate"),
    }
    value, label = choices.get(mode, choices["fit"])
    if value <= 0 and mode == "fit":
        value, label = choices["miner_1h"]
    if value <= 0:
        value, label = choices["miner_24h"]
    return max(value, 0.0), label


def pool_fee(config: dict[str, Any], stats: dict[str, Any] | None) -> float:
    calc = config.get("calculation") or {}
    if calc.get("fee_mode") == "manual":
        return number(calc.get("fee_override_percent"), 0.0)
    if stats and stats.get("feePercent") is not None:
        return number(stats.get("feePercent"), 0.0)
    return number(selected_pool(config).get("default_fee_percent"), 0.0)


def tool_fee(config: dict[str, Any]) -> float:
    calc = config.get("calculation") or {}
    if calc.get("tool_fee_mode", "auto") == "manual":
        return number(calc.get("tool_fee_percent"), 1.0)
    return number(selected_mining_software(config).get("dev_fee_percent"), 1.0)


def price_usd(config: dict[str, Any], market: dict[str, Any] | None) -> float:
    calc = config.get("calculation") or {}
    if calc.get("price_mode") == "manual":
        return number(calc.get("manual_price_usd"), 0.0)
    if market:
        return extract_market_price(market)
    return number(calc.get("manual_price_usd"), 0.0)


def extract_market_price(market: dict[str, Any]) -> float:
    for key in ("price_usd", "usd", "last", "last_price", "close", "price", "ticker_price"):
        value = number(market.get(key), 0.0)
        if value > 0:
            return value
    for container_key in ("ticker", "data", "result", "market", "payload"):
        nested = market.get(container_key)
        if isinstance(nested, dict):
            value = extract_market_price(nested)
            if value > 0:
                return value
    return 0.0


def price_source(market: dict[str, Any] | None) -> str:
    if not market:
        return "manual"
    return str(market.get("_source_name") or market.get("source") or market.get("provider") or "market")


def usd_cny(config: dict[str, Any], fx: dict[str, Any] | None) -> float:
    calc = config.get("calculation") or {}
    if calc.get("fx_mode") == "manual":
        return number(calc.get("manual_usd_cny"), 0.0)
    if fx:
        rates = fx.get("rates") or {}
        return number(rates.get("CNY") or rates.get("CNH"), 0.0)
    return number(calc.get("manual_usd_cny"), 0.0)


def block_reward(stats: dict[str, Any] | None) -> float:
    if not stats:
        return 0.0
    coins = stats.get("coins") or []
    if coins:
        return number(coins[0].get("reward"), 0.0)
    return 0.0


def network_hashrate(stats: dict[str, Any] | None, chain: dict[str, Any] | None) -> float:
    if chain:
        hps = number(chain.get("estimated_hashrate_hps"), 0.0)
        if hps > 0:
            return hps
    if stats:
        coins = stats.get("coins") or []
        if coins:
            hps = parse_hashrate(coins[0].get("network_hash"))
            if hps > 0:
                return hps
    return 0.0


def block_time(chain: dict[str, Any] | None, default: float = 228.0) -> float:
    if chain:
        sec = number(chain.get("avg_block_time_seconds"), 0.0)
        if sec > 0:
            return sec
    return default


def compute_estimate(config: dict[str, Any], snapshot: DataSnapshot, now: datetime | None = None) -> ProfitEstimate:
    now = now or datetime.now().astimezone()
    stats = snapshot.pool_stats
    miner = snapshot.miner_stats
    chain = snapshot.chain
    fee = pool_fee(config, stats)
    dev_fee = tool_fee(config)
    price = price_usd(config, snapshot.market)
    p_source = "manual" if (config.get("calculation") or {}).get("price_mode") == "manual" else price_source(snapshot.market)
    cny = usd_cny(config, snapshot.fx)
    reward = block_reward(stats)
    net_hps = network_hashrate(stats, chain)
    miner_hps, h_source = choose_hashrate(config, miner)
    avg_block_time = block_time(chain)
    observed = today_observed_prl(miner, now)
    elapsed, _remaining = seconds_today(now)

    projected_prl = 0.0
    if miner_hps > 0 and net_hps > 0 and reward > 0 and avg_block_time > 0:
        share = miner_hps / net_hps
        pool_keep = max(0.0, 1.0 - fee / 100.0)
        tool_keep = max(0.0, 1.0 - dev_fee / 100.0)
        projected_prl = share * (86_400.0 / avg_block_time) * reward * pool_keep * tool_keep

    estimated_so_far = projected_prl * min(max(elapsed / 86_400.0, 0.0), 1.0)
    today_prl = max(observed, estimated_so_far)
    prl_per_second = projected_prl / 86_400.0 if projected_prl > 0 else 0.0
    today_usd = today_prl * price
    projected_usd = projected_prl * price
    source = f"{h_source}, pool {fee:.2f}%, tool {dev_fee:.2f}%, price ${price:.4f} ({p_source}), USD/CNY {cny:.4f}"
    return ProfitEstimate(
        today_prl=today_prl,
        today_usd=today_usd,
        today_cny=today_usd * cny,
        projected_24h_prl=projected_prl,
        projected_24h_usd=projected_usd,
        projected_24h_cny=projected_usd * cny,
        observed_today_prl=observed,
        prl_per_second=prl_per_second,
        price_usd=price,
        price_source=p_source,
        usd_cny=cny,
        fee_percent=fee,
        tool_fee_percent=dev_fee,
        hashrate_hps=miner_hps,
        network_hashrate_hps=net_hps,
        block_reward_prl=reward,
        block_time_seconds=avg_block_time,
        source_summary=source,
        errors=list(snapshot.errors),
        computed_at=now,
    )


class SmoothValue:
    def __init__(self) -> None:
        self.anchor_time = datetime.now().astimezone()
        self.anchor_prl = 0.0
        self.target_prl = 0.0
        self.slope = 0.0
        self.blend_seconds = 8.0

    def reset(self, estimate: ProfitEstimate) -> None:
        now = datetime.now().astimezone()
        current = self.value(now)
        self.anchor_time = now
        self.anchor_prl = current
        self.target_prl = estimate.today_prl
        self.slope = estimate.prl_per_second

    def value(self, now: datetime | None = None) -> float:
        now = now or datetime.now().astimezone()
        dt = max((now - self.anchor_time).total_seconds(), 0.0)
        raw_target = self.target_prl + self.slope * dt
        if self.blend_seconds <= 0:
            return raw_target
        t = min(dt / self.blend_seconds, 1.0)
        smooth = t * t * (3.0 - 2.0 * t)
        return self.anchor_prl + (raw_target - self.anchor_prl) * smooth
