from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import selected_market_source, selected_pool


USER_AGENT = "PRL-Today/0.1"
SOURCE_FIELDS = {
    "pool": "pool_stats",
    "miner": "miner_stats",
    "market": "market",
    "chain": "chain",
    "fx": "fx",
}


class ApiError(RuntimeError):
    pass


@dataclass(slots=True)
class DataSnapshot:
    pool_stats: dict[str, Any] | None = None
    miner_stats: dict[str, Any] | None = None
    market: dict[str, Any] | None = None
    chain: dict[str, Any] | None = None
    fx: dict[str, Any] | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    errors: list[str] = field(default_factory=list)


class HttpClient:
    def __init__(self, config: dict[str, Any], timeout: float = 12.0):
        self.config = config
        self.timeout = timeout
        handlers: list[urllib.request.BaseHandler] = []
        proxy = config.get("proxy") or {}
        if proxy.get("enabled", True):
            proxy_url = str(proxy.get("url") or "").strip()
            if proxy_url:
                handlers.append(urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url}))
            elif proxy.get("use_env", True):
                handlers.append(urllib.request.ProxyHandler())
            else:
                handlers.append(urllib.request.ProxyHandler({}))
        else:
            handlers.append(urllib.request.ProxyHandler({}))
        self.opener = urllib.request.build_opener(*handlers)

    def get_json(self, url: str) -> dict[str, Any]:
        text = self.get_text(url, accept="application/json")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ApiError(f"{url}: invalid JSON") from exc
        if not isinstance(data, dict):
            raise ApiError(f"{url}: JSON root is not an object")
        return data

    def get_text(self, url: str, accept: str = "*/*") -> str:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": accept,
                "Referer": "https://safetrade.com/exchange/PRL-USDT?type=basic",
            },
        )
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                status = getattr(resp, "status", 200)
                body = resp.read()
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise ApiError(f"{url}: {exc}") from exc
        if status >= 400:
            raise ApiError(f"{url}: HTTP {status}")
        return body.decode("utf-8", errors="replace")


def join_url(base: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urllib.parse.urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def miner_url(config: dict[str, Any]) -> str:
    pool = selected_pool(config)
    if pool.get("api_enabled") is False:
        return ""
    template = str(pool.get("miner_path_template", "/api/miner/{address}"))
    address = urllib.parse.quote(str(config.get("miner_address", "")), safe="")
    return join_url(str(pool.get("base_url", "")), template.format(address=address))


def stats_url(config: dict[str, Any]) -> str:
    pool = selected_pool(config)
    if pool.get("api_enabled") is False:
        return ""
    return join_url(str(pool.get("base_url", "")), str(pool.get("stats_path", "/api/stats")))


def market_url(config: dict[str, Any]) -> str:
    source = selected_market_source(config)
    return str(source.get("url") or source.get("market_url") or config.get("market_url") or "")


def market_urls(config: dict[str, Any]) -> list[str]:
    source = selected_market_source(config)
    urls: list[str] = []
    for key in ("url", "market_url"):
        value = str(source.get(key) or "").strip()
        if value and value not in urls:
            urls.append(value)
    for value in source.get("api_urls") or []:
        url = str(value or "").strip()
        if url and url not in urls:
            urls.append(url)
    return urls


def parse_safetrade_page(text: str) -> dict[str, Any]:
    for pattern in (
        r'"(?:last|last_price|close|price)"\s*:\s*"?([0-9]+(?:\.[0-9]+)?)"?',
        r"'(?:last|last_price|close|price)'\s*:\s*'?([0-9]+(?:\.[0-9]+)?)'?",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return {"price_usd": float(match.group(1)), "parsed_from": "safetrade_page"}
    raise ApiError("SafeTrade page did not expose a parseable PRL/USDT price")


def fetch_market(config: dict[str, Any], client: HttpClient) -> dict[str, Any]:
    source = selected_market_source(config)
    kind = str(source.get("kind", "")).lower()
    errors: list[str] = []
    urls = market_urls(config)
    if kind == "safetrade":
        api_urls = [url for url in urls if "/api/" in url]
        page_urls = [url for url in urls if "/api/" not in url]
        for url in [*api_urls, *page_urls]:
            try:
                if "/api/" in url:
                    data = client.get_json(url)
                else:
                    data = parse_safetrade_page(client.get_text(url, accept="text/html,*/*"))
                data.setdefault("_source_name", source.get("name", "SafeTrade"))
                data.setdefault("_source_kind", source.get("kind", "safetrade"))
                data.setdefault("_source_url", url)
                return data
            except ApiError as exc:
                errors.append(str(exc))
        raise ApiError("; ".join(errors) if errors else "SafeTrade price unavailable")

    url = market_url(config)
    if not url:
        raise ApiError("market source URL is empty")
    data = client.get_json(url)
    data.setdefault("_source_name", source.get("name", "market"))
    data.setdefault("_source_kind", source.get("kind", "unknown"))
    data.setdefault("_source_url", url)
    return data


def source_url(config: dict[str, Any], source: str) -> str:
    if source == "pool":
        return stats_url(config)
    if source == "miner":
        return miner_url(config)
    if source == "market":
        return market_url(config)
    if source == "chain":
        return str(config.get("chain_summary_url", ""))
    if source == "fx":
        return str(config.get("fx_url", ""))
    raise KeyError(source)


def fetch_snapshot(
    config: dict[str, Any],
    client: HttpClient | None = None,
    sources: list[str] | tuple[str, ...] | None = None,
) -> DataSnapshot:
    client = client or HttpClient(config)
    snapshot = DataSnapshot()
    selected_sources = list(sources or SOURCE_FIELDS.keys())
    for source in selected_sources:
        field_name = SOURCE_FIELDS.get(source)
        if not field_name:
            snapshot.errors.append(f"unknown source: {source}")
            continue
        url = source_url(config, source)
        if not url:
            continue
        try:
            if source == "market":
                data = fetch_market(config, client)
            else:
                data = client.get_json(url)
            setattr(snapshot, field_name, data)
        except ApiError as exc:
            snapshot.errors.append(f"{source}: {exc}")
    return snapshot


def merge_snapshot(base: DataSnapshot, update: DataSnapshot) -> DataSnapshot:
    for field_name in SOURCE_FIELDS.values():
        value = getattr(update, field_name)
        if value is not None:
            setattr(base, field_name, value)
    base.fetched_at = update.fetched_at
    base.errors = list(update.errors)
    return base


def apply_proxy_env(config: dict[str, Any]) -> None:
    proxy = config.get("proxy") or {}
    if not proxy.get("enabled", True):
        return
    url = str(proxy.get("url") or "").strip()
    if not url:
        return
    os.environ["HTTP_PROXY"] = url
    os.environ["HTTPS_PROXY"] = url
