from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .api import apply_proxy_env, fetch_snapshot
from .config import CONFIG_PATH, PROJECT_ROOT, load_config
from .model import compute_estimate


QT_CHECK = (
    "import importlib\n"
    "for name in ('PyQt6.QtWidgets', 'PyQt5.QtWidgets'):\n"
    "    try:\n"
    "        importlib.import_module(name)\n"
    "        raise SystemExit(0)\n"
    "    except ImportError:\n"
    "        pass\n"
    "raise SystemExit(1)\n"
)


def print_check(config: dict[str, Any]) -> None:
    snapshot = fetch_snapshot(config)
    estimate = compute_estimate(config, snapshot)
    print(f"errors={len(estimate.errors)}")
    for error in estimate.errors[:5]:
        print(f"error={error}")
    print(f"today_prl={estimate.today_prl:.6f}")
    print(f"today_usd={estimate.today_usd:.6f}")
    print(f"today_cny={estimate.today_cny:.6f}")
    print(f"projected_24h_prl={estimate.projected_24h_prl:.6f}")
    print(f"projected_24h_usd={estimate.projected_24h_usd:.6f}")
    print(f"projected_24h_cny={estimate.projected_24h_cny:.6f}")
    print(f"fee_percent={estimate.fee_percent:.2f}")
    print(f"tool_fee_percent={estimate.tool_fee_percent:.2f}")
    print(f"price_usd={estimate.price_usd:.6f}")
    print(f"price_source={estimate.price_source}")
    print(f"usd_cny={estimate.usd_cny:.6f}")
    print(f"hashrate_th={estimate.hashrate_hps / 1e12:.2f}")
    print(f"network_hashrate_eh={estimate.network_hashrate_hps / 1e18:.2f}")
    print(f"source={estimate.source_summary}")


def has_qt(python_exe: Path) -> bool:
    try:
        result = subprocess.run(
            [str(python_exe), "-c", QT_CHECK],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def qt_python_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_python = os.environ.get("PRL_TODAY_PYTHON")
    if env_python:
        candidates.append(Path(env_python))
    candidates.append(Path(r"C:\ProgramData\anaconda3\python.exe"))

    for raw in os.environ.get("PATH", "").split(os.pathsep):
        if not raw:
            continue
        path = Path(raw) / "python.exe"
        if path.exists():
            candidates.append(path)

    current = Path(sys.executable).resolve()
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen or resolved == current or not resolved.exists():
            continue
        seen.add(key)
        unique.append(resolved)
    return unique


def reexec_with_qt(argv: list[str]) -> None:
    if getattr(sys, "frozen", False):
        return
    if os.environ.get("PRL_TODAY_NO_REEXEC") == "1":
        return
    if has_qt(Path(sys.executable)):
        return

    for candidate in qt_python_candidates():
        if has_qt(candidate):
            env = os.environ.copy()
            env["PRL_TODAY_NO_REEXEC"] = "1"
            script = PROJECT_ROOT / "run.py"
            os.execve(str(candidate), [str(candidate), str(script), *argv], env)


def run_gui(config: dict[str, Any]) -> None:
    reexec_with_qt(sys.argv[1:])
    from .qt_app import run

    run(config)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="PRL-Today mining profit floating window")
    parser.add_argument("--check", action="store_true", help="fetch live data and print one estimate without opening the GUI")
    args = parser.parse_args(argv)
    config = load_config(CONFIG_PATH)
    apply_proxy_env(config)
    if args.check:
        print_check(config)
        return
    run_gui(config)


if __name__ == "__main__":
    main()
