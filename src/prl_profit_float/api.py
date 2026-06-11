from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import selected_pool


USER_AGENT = "PRL-Today/0.1 (+local desktop monitor)"
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
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                status = getattr(resp, "status", 200)
                body = resp.read()
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise ApiError(f"{url}: {exc}") from exc
        if status >= 400:
            raise ApiError(f"{url}: HTTP {status}")
        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ApiError(f"{url}: invalid JSON") from exc
        if not isinstance(data, dict):
            raise ApiError(f"{url}: JSON root is not an object")
        return data


def join_url(base: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return urllib.parse.urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def miner_url(config: dict[str, Any]) -> str:
    pool = selected_pool(config)
    template = str(pool.get("miner_path_template", "/api/miner/{address}"))
    address = urllib.parse.quote(str(config.get("miner_address", "")), safe="")
    return join_url(str(pool.get("base_url", "")), template.format(address=address))


def stats_url(config: dict[str, Any]) -> str:
    pool = selected_pool(config)
    return join_url(str(pool.get("base_url", "")), str(pool.get("stats_path", "/api/stats")))


def source_url(config: dict[str, Any], source: str) -> str:
    if source == "pool":
        return stats_url(config)
    if source == "miner":
        return miner_url(config)
    if source == "market":
        return str(config.get("market_url", ""))
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
            setattr(snapshot, field_name, client.get_json(url))
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
