from __future__ import annotations

import unittest
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from prl_profit_float.api import ApiError, DataSnapshot, fetch_snapshot, normalize_http_url, parse_safetrade_page
from prl_profit_float.config import DEFAULT_CONFIG, miner_address_error
from prl_profit_float.model import compute_estimate, extract_market_price, fit_hashrate_hps, parse_hashrate, today_observed_prl


class ModelTest(unittest.TestCase):
    def test_parse_hashrate(self) -> None:
        self.assertEqual(parse_hashrate("130.57 TH/s"), 130.57e12)
        self.assertEqual(parse_hashrate("24.60 EH/s"), 24.60e18)

    def test_today_observed_prl_ignores_orphans(self) -> None:
        miner = {
            "payments": [
                {"ts": 1781089540, "amount_grain": 12640465, "status": "pending"},
                {"ts": 1781089540, "amount_grain": 99999999, "status": "orphaned"},
            ]
        }
        now = datetime.fromtimestamp(1781090000, tz=timezone.utc).astimezone()
        self.assertAlmostEqual(today_observed_prl(miner, now), 0.12640465)

    def test_fit_hashrate(self) -> None:
        series = [
            {"ts": 1000, "hashrate": 100.0},
            {"ts": 1600, "hashrate": 110.0},
            {"ts": 2200, "hashrate": 120.0},
            {"ts": 2800, "hashrate": 130.0},
        ]
        self.assertGreater(fit_hashrate_hps(series, now_ts=2800), 0)

    def test_compute_estimate_uses_auto_fee_price_and_fx(self) -> None:
        config = DEFAULT_CONFIG.copy()
        snapshot = DataSnapshot(
            pool_stats={
                "feePercent": 3,
                "coins": [{"reward": 2625.6, "network_hash": "24.60 EH/s"}],
            },
            miner_stats={
                "estHash1hRaw": 130.57e12,
                "estHash24hRaw": 137.53e12,
                "hashrate_series": [
                    {"ts": 1781089200, "hashrate": 128e12},
                    {"ts": 1781089800, "hashrate": 132e12},
                    {"ts": 1781090400, "hashrate": 130e12},
                ],
                "payments": [],
            },
            market={"price_usd": 0.5201},
            chain={"estimated_hashrate_hps": 20.799e18, "avg_block_time_seconds": 228.08},
            fx={"rates": {"CNY": 6.785295}},
        )
        estimate = compute_estimate(
            config,
            snapshot,
            now=datetime.fromtimestamp(1781090000, tz=timezone.utc).astimezone(),
        )
        self.assertGreater(estimate.projected_24h_prl, 0)
        self.assertAlmostEqual(estimate.fee_percent, 3.0)
        self.assertAlmostEqual(estimate.tool_fee_percent, 0.0)
        self.assertAlmostEqual(estimate.price_usd, 0.5201)
        self.assertEqual(estimate.price_source, "market")
        self.assertAlmostEqual(estimate.usd_cny, 6.785295)

    def test_extract_market_price_supports_safetrade_shapes(self) -> None:
        self.assertAlmostEqual(extract_market_price({"last": "0.6000"}), 0.6)
        self.assertAlmostEqual(extract_market_price({"ticker": {"last_price": "0.6100"}}), 0.61)

    def test_parse_safetrade_page_embedded_price(self) -> None:
        self.assertAlmostEqual(parse_safetrade_page('window.__DATA__={"last":"0.6200"}')["price_usd"], 0.62)

    def test_default_proxy_is_disabled(self) -> None:
        self.assertFalse(DEFAULT_CONFIG["proxy"]["enabled"])
        self.assertEqual(DEFAULT_CONFIG["proxy"]["url"], "")

    def test_miner_address_validation(self) -> None:
        self.assertIsNone(miner_address_error(DEFAULT_CONFIG["miner_address"]))
        self.assertIsNotNone(miner_address_error(""))
        self.assertIsNotNone(miner_address_error("https://example.com/wallet"))

    def test_rejects_non_http_urls(self) -> None:
        with self.assertRaises(ApiError):
            normalize_http_url("file:///C:/Users/example/config.json")

    def test_fetch_snapshot_reports_bad_url_as_error(self) -> None:
        config = {**DEFAULT_CONFIG, "chain_summary_url": "file:///C:/Users/example/config.json"}
        snapshot = fetch_snapshot(config, sources=["chain"])
        self.assertEqual(snapshot.chain, None)
        self.assertTrue(any("unsupported URL" in error for error in snapshot.errors))


if __name__ == "__main__":
    unittest.main()
