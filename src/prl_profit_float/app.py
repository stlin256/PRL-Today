from __future__ import annotations

import argparse
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Any

from .api import DataSnapshot, apply_proxy_env, fetch_snapshot
from .config import CONFIG_PATH, load_config, pool_names, save_config
from .model import ProfitEstimate, SmoothValue, compute_estimate, number


class ProfitApp:
    def __init__(self, root: tk.Tk, config: dict[str, Any]):
        self.root = root
        self.config = config
        self.queue: queue.Queue[DataSnapshot | Exception] = queue.Queue()
        self.estimate: ProfitEstimate | None = None
        self.smoother = SmoothValue()
        self.fetching = False
        self.drag_offset = (0, 0)

        self.usd_var = tk.StringVar(value="$0.000000")
        self.cny_var = tk.StringVar(value="RMB 0.000000")
        self.prl_var = tk.StringVar(value="0.000000 PRL today")
        self.projection_var = tk.StringVar(value="24h projection: waiting for data")
        self.status_var = tk.StringVar(value="Starting...")
        self.error_var = tk.StringVar(value="")

        self.build_window()
        self.apply_window_config()
        self.refresh()
        self.root.after(250, self.poll_queue)
        self.root.after(1000, self.tick)

    def build_window(self) -> None:
        self.root.title("PRL Profit Float")
        self.root.configure(bg="#111418")
        self.root.attributes("-topmost", True)

        self.frame = tk.Frame(self.root, bg="#111418", bd=1, relief="solid", highlightthickness=1, highlightbackground="#2b343c")
        self.frame.pack(fill="both", expand=True)
        self.frame.bind("<ButtonPress-1>", self.start_drag)
        self.frame.bind("<B1-Motion>", self.drag)

        header = tk.Frame(self.frame, bg="#111418")
        header.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(header, text="PRL Today", bg="#111418", fg="#d9faff", font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(header, text="Refresh", command=self.refresh, bg="#1b242b", fg="#d9faff", bd=0, padx=8).pack(side="right", padx=(4, 0))
        tk.Button(header, text="Set", command=self.open_settings, bg="#1b242b", fg="#d9faff", bd=0, padx=8).pack(side="right", padx=(4, 0))
        tk.Button(header, text="X", command=self.on_close, bg="#2b1c1c", fg="#ffd0d0", bd=0, padx=8).pack(side="right")

        tk.Label(self.frame, textvariable=self.usd_var, bg="#111418", fg="#f6d36a", font=("Consolas", 24, "bold")).pack(anchor="w", padx=10)
        tk.Label(self.frame, textvariable=self.cny_var, bg="#111418", fg="#7ee0d1", font=("Consolas", 19, "bold")).pack(anchor="w", padx=10)
        tk.Label(self.frame, textvariable=self.prl_var, bg="#111418", fg="#c8d3dc", font=("Consolas", 10)).pack(anchor="w", padx=12, pady=(2, 0))
        tk.Label(self.frame, textvariable=self.projection_var, bg="#111418", fg="#8ea1ad", font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(2, 0))
        tk.Label(self.frame, textvariable=self.status_var, bg="#111418", fg="#8ea1ad", font=("Segoe UI", 8), wraplength=360, justify="left").pack(anchor="w", padx=12, pady=(6, 0))
        tk.Label(self.frame, textvariable=self.error_var, bg="#111418", fg="#ff8d8d", font=("Segoe UI", 8), wraplength=360, justify="left").pack(anchor="w", padx=12, pady=(2, 10))

    def apply_window_config(self) -> None:
        window = self.config.get("window") or {}
        x = int(number(window.get("x"), 80))
        y = int(number(window.get("y"), 80))
        alpha = min(max(number(window.get("alpha"), 0.96), 0.35), 1.0)
        self.root.geometry(f"390x214+{x}+{y}")
        self.root.attributes("-alpha", alpha)

    def start_drag(self, event: tk.Event) -> None:
        self.drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def drag(self, event: tk.Event) -> None:
        x = event.x_root - self.drag_offset[0]
        y = event.y_root - self.drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def refresh(self) -> None:
        if self.fetching:
            return
        self.fetching = True
        self.status_var.set("Refreshing live pool, miner, market and FX data...")
        apply_proxy_env(self.config)
        threading.Thread(target=self.fetch_worker, daemon=True).start()

    def fetch_worker(self) -> None:
        try:
            self.queue.put(fetch_snapshot(self.config))
        except Exception as exc:  # defensive boundary for the GUI thread
            self.queue.put(exc)

    def poll_queue(self) -> None:
        try:
            item = self.queue.get_nowait()
        except queue.Empty:
            self.root.after(250, self.poll_queue)
            return
        self.fetching = False
        if isinstance(item, Exception):
            self.error_var.set(str(item))
        else:
            self.estimate = compute_estimate(self.config, item)
            self.smoother.reset(self.estimate)
            self.render_static()
        self.root.after(250, self.poll_queue)

    def tick(self) -> None:
        if self.estimate:
            prl = self.smoother.value()
            usd = prl * self.estimate.price_usd
            cny = usd * self.estimate.usd_cny
            self.usd_var.set(f"${usd:.6f}")
            self.cny_var.set(f"RMB {cny:.6f}")
            self.prl_var.set(f"{prl:.6f} PRL today")
        refresh_seconds = max(int(number(self.config.get("refresh_seconds"), 30)), 5)
        if self.estimate:
            age = (datetime.now().astimezone() - self.estimate.computed_at).total_seconds()
            if age >= refresh_seconds:
                self.refresh()
        self.root.after(1000, self.tick)

    def render_static(self) -> None:
        if not self.estimate:
            return
        e = self.estimate
        self.projection_var.set(
            f"24h projection: {e.projected_24h_prl:.6f} PRL / ${e.projected_24h_usd:.6f} / RMB {e.projected_24h_cny:.6f}"
        )
        h_th = e.hashrate_hps / 1e12
        net_eh = e.network_hashrate_hps / 1e18
        self.status_var.set(
            f"{h_th:.2f} TH/s | net {net_eh:.2f} EH/s | reward {e.block_reward_prl:.2f} PRL | {e.source_summary}"
        )
        if e.errors:
            self.error_var.set("Fallback active: " + " | ".join(e.errors[:2]))
        else:
            self.error_var.set("")

    def open_settings(self) -> None:
        SettingsWindow(self, self.root)

    def update_config(self, config: dict[str, Any]) -> None:
        self.config = config
        save_config(self.config)
        self.apply_window_config()
        self.refresh()

    def on_close(self) -> None:
        window = self.config.setdefault("window", {})
        window["x"] = self.root.winfo_x()
        window["y"] = self.root.winfo_y()
        save_config(self.config)
        self.root.destroy()


class SettingsWindow:
    def __init__(self, app: ProfitApp, parent: tk.Tk):
        self.app = app
        self.config = {**app.config}
        self.top = tk.Toplevel(parent)
        self.top.title("PRL Profit Settings")
        self.top.configure(bg="#15191d")
        self.top.transient(parent)
        self.top.attributes("-topmost", True)
        self.vars: dict[str, tk.Variable] = {}
        self.build()

    def build(self) -> None:
        body = ttk.Frame(self.top, padding=12)
        body.pack(fill="both", expand=True)

        self.vars["miner_address"] = tk.StringVar(value=str(self.app.config.get("miner_address", "")))
        self.vars["selected_pool"] = tk.StringVar(value=str(self.app.config.get("selected_pool", "")))
        self.vars["proxy_enabled"] = tk.BooleanVar(value=bool((self.app.config.get("proxy") or {}).get("enabled", True)))
        self.vars["proxy_url"] = tk.StringVar(value=str((self.app.config.get("proxy") or {}).get("url", "")))
        calc = self.app.config.get("calculation") or {}
        self.vars["fee_mode"] = tk.StringVar(value=str(calc.get("fee_mode", "auto")))
        self.vars["fee_override_percent"] = tk.StringVar(value=str(calc.get("fee_override_percent", 3.0)))
        self.vars["price_mode"] = tk.StringVar(value=str(calc.get("price_mode", "auto")))
        self.vars["manual_price_usd"] = tk.StringVar(value=str(calc.get("manual_price_usd", 0.52)))
        self.vars["fx_mode"] = tk.StringVar(value=str(calc.get("fx_mode", "auto")))
        self.vars["manual_usd_cny"] = tk.StringVar(value=str(calc.get("manual_usd_cny", 6.78)))
        self.vars["hashrate_mode"] = tk.StringVar(value=str(calc.get("hashrate_mode", "fit")))
        self.vars["refresh_seconds"] = tk.StringVar(value=str(self.app.config.get("refresh_seconds", 30)))
        self.vars["alpha"] = tk.StringVar(value=str((self.app.config.get("window") or {}).get("alpha", 0.96)))

        row = 0
        row = self.entry(body, row, "Wallet", "miner_address")
        pools = pool_names(self.app.config) or ["AlphaPool PRL"]
        row = self.option(body, row, "Pool", "selected_pool", pools)
        row = self.check(body, row, "Proxy enabled", "proxy_enabled")
        row = self.entry(body, row, "Proxy URL", "proxy_url")
        row = self.option(body, row, "Fee mode", "fee_mode", ["auto", "manual"])
        row = self.entry(body, row, "Manual fee %", "fee_override_percent")
        row = self.option(body, row, "Price mode", "price_mode", ["auto", "manual"])
        row = self.entry(body, row, "Manual PRL USD", "manual_price_usd")
        row = self.option(body, row, "FX mode", "fx_mode", ["auto", "manual"])
        row = self.entry(body, row, "Manual USD/CNY", "manual_usd_cny")
        row = self.option(body, row, "Hashrate", "hashrate_mode", ["fit", "miner_1h", "miner_24h", "worker_live"])
        row = self.entry(body, row, "Refresh seconds", "refresh_seconds")
        row = self.entry(body, row, "Window alpha", "alpha")

        buttons = ttk.Frame(body)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=self.top.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Save", command=self.save).pack(side="right")

    def entry(self, parent: ttk.Frame, row: int, label: str, key: str) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=self.vars[key], width=62).grid(row=row, column=1, sticky="ew", pady=3)
        return row + 1

    def option(self, parent: ttk.Frame, row: int, label: str, key: str, values: list[str]) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.OptionMenu(parent, self.vars[key], self.vars[key].get(), *values).grid(row=row, column=1, sticky="w", pady=3)
        return row + 1

    def check(self, parent: ttk.Frame, row: int, label: str, key: str) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Checkbutton(parent, variable=self.vars[key]).grid(row=row, column=1, sticky="w", pady=3)
        return row + 1

    def save(self) -> None:
        try:
            config = self.app.config
            config["miner_address"] = str(self.vars["miner_address"].get()).strip()
            config["selected_pool"] = str(self.vars["selected_pool"].get()).strip()
            proxy = config.setdefault("proxy", {})
            proxy["enabled"] = bool(self.vars["proxy_enabled"].get())
            proxy["url"] = str(self.vars["proxy_url"].get()).strip()
            proxy["use_env"] = True
            calc = config.setdefault("calculation", {})
            calc["fee_mode"] = str(self.vars["fee_mode"].get())
            calc["fee_override_percent"] = float(self.vars["fee_override_percent"].get())
            calc["price_mode"] = str(self.vars["price_mode"].get())
            calc["manual_price_usd"] = float(self.vars["manual_price_usd"].get())
            calc["fx_mode"] = str(self.vars["fx_mode"].get())
            calc["manual_usd_cny"] = float(self.vars["manual_usd_cny"].get())
            calc["hashrate_mode"] = str(self.vars["hashrate_mode"].get())
            config["refresh_seconds"] = int(float(self.vars["refresh_seconds"].get()))
            window = config.setdefault("window", {})
            window["alpha"] = float(self.vars["alpha"].get())
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc), parent=self.top)
            return
        self.app.update_config(config)
        self.top.destroy()


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
    print(f"price_usd={estimate.price_usd:.6f}")
    print(f"usd_cny={estimate.usd_cny:.6f}")
    print(f"hashrate_th={estimate.hashrate_hps / 1e12:.2f}")
    print(f"network_hashrate_eh={estimate.network_hashrate_hps / 1e18:.2f}")
    print(f"source={estimate.source_summary}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="PRL mining profit floating window")
    parser.add_argument("--check", action="store_true", help="fetch live data and print one estimate without opening the GUI")
    args = parser.parse_args(argv)
    config = load_config(CONFIG_PATH)
    apply_proxy_env(config)
    if args.check:
        print_check(config)
        return
    root = tk.Tk()
    ProfitApp(root, config)
    root.mainloop()


if __name__ == "__main__":
    main()
