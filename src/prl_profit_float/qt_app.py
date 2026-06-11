from __future__ import annotations

import copy
import math
import sys
import threading
import time
from datetime import datetime
from typing import Any

try:
    from PyQt6.QtCore import QObject, QEasingCurve, QPoint, QPropertyAnimation, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
    from PyQt6.QtGui import QAction
    from PyQt6.QtWidgets import (
        QApplication,
        QComboBox,
        QFrame,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMenu,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizeGrip,
        QSlider,
        QStackedWidget,
        QStyle,
        QSystemTrayIcon,
        QVBoxLayout,
        QWidget,
    )

    QT_API = "PyQt6"
except ImportError:
    from PyQt5.QtCore import QObject, QEasingCurve, QPoint, QPropertyAnimation, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
    from PyQt5.QtWidgets import (
        QAction,
        QApplication,
        QComboBox,
        QFrame,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMenu,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizeGrip,
        QSlider,
        QStackedWidget,
        QStyle,
        QSystemTrayIcon,
        QVBoxLayout,
        QWidget,
    )

    QT_API = "PyQt5"

from .api import SOURCE_FIELDS, DataSnapshot, HttpClient, apply_proxy_env, fetch_snapshot, merge_snapshot
from .config import CONFIG_PATH, pool_names, refresh_seconds, save_config
from .model import ProfitEstimate, SmoothValue, compute_estimate, seconds_today


ACCENT = "#D81B60"
ACCENT_LIGHT = "#F06292"
BG = "#141414"
TEXT_MUTED = "#9A9A9A"

if QT_API == "PyQt6":
    FRAMELESS_FLAGS = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
    TRANSLUCENT_BACKGROUND = Qt.WidgetAttribute.WA_TranslucentBackground
    NO_FRAME = QFrame.Shape.NoFrame
    SCROLLBAR_OFF = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    ALIGN_LEFT = Qt.AlignmentFlag.AlignLeft
    HORIZONTAL = Qt.Orientation.Horizontal
    COMPUTER_ICON = QStyle.StandardPixmap.SP_ComputerIcon
    LEFT_BUTTON = Qt.MouseButton.LeftButton
    TRAY_TRIGGER = QSystemTrayIcon.ActivationReason.Trigger
    TRAY_DOUBLE_CLICK = QSystemTrayIcon.ActivationReason.DoubleClick
else:
    FRAMELESS_FLAGS = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    TRANSLUCENT_BACKGROUND = Qt.WA_TranslucentBackground
    NO_FRAME = QFrame.NoFrame
    SCROLLBAR_OFF = Qt.ScrollBarAlwaysOff
    ALIGN_LEFT = Qt.AlignLeft
    HORIZONTAL = Qt.Horizontal
    COMPUTER_ICON = QStyle.SP_ComputerIcon
    LEFT_BUTTON = Qt.LeftButton
    TRAY_TRIGGER = QSystemTrayIcon.Trigger
    TRAY_DOUBLE_CLICK = QSystemTrayIcon.DoubleClick


def clean_level(value: Any) -> str:
    level = str(value or "standard").strip().lower()
    if level in {"lite", "standard", "detail"}:
        return level
    return "standard"


def safe_int(value: Any, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default
    return max(parsed, minimum)


def safe_float(value: Any, default: float, minimum: float = 0.0) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return max(parsed, minimum)


def format_hps(value: float) -> str:
    units = (("EH/s", 1e18), ("PH/s", 1e15), ("TH/s", 1e12), ("GH/s", 1e9), ("MH/s", 1e6))
    for label, scale in units:
        if abs(value) >= scale:
            return f"{value / scale:.2f} {label}"
    return f"{value:.0f} H/s"


class ProfitWorker(QObject):
    data_updated = pyqtSignal(object)

    def __init__(self, config: dict[str, Any]):
        super().__init__()
        self.config = copy.deepcopy(config)
        self.snapshot = DataSnapshot()
        self.last_updates: dict[str, datetime | None] = {source: None for source in SOURCE_FIELDS}
        self.next_due: dict[str, float] = {source: 0.0 for source in SOURCE_FIELDS}
        self._running = True
        self.client = HttpClient(self.config)
        self._lock = threading.Lock()
        self._pending_config: dict[str, Any] | None = None

    @pyqtSlot()
    def run(self) -> None:
        while self._running:
            self.apply_pending_config()
            due_sources = self.due_sources()
            if due_sources:
                update = fetch_snapshot(self.config, self.client, due_sources)
                merge_snapshot(self.snapshot, update)
                now = datetime.now().astimezone()
                for source in due_sources:
                    field_name = SOURCE_FIELDS[source]
                    if getattr(update, field_name) is not None:
                        self.last_updates[source] = now
                    self.next_due[source] = time.monotonic() + refresh_seconds(self.config, f"{source}_seconds")
                estimate = compute_estimate(self.config, self.snapshot)
                self.data_updated.emit(
                    {
                        "estimate": estimate,
                        "last_updates": dict(self.last_updates),
                        "intervals": self.intervals(),
                        "sources": list(due_sources),
                    }
                )
            self.sleep_slice()

    def due_sources(self) -> list[str]:
        now = time.monotonic()
        return [source for source, due_at in self.next_due.items() if now >= due_at]

    def intervals(self) -> dict[str, int]:
        return {source: refresh_seconds(self.config, f"{source}_seconds") for source in SOURCE_FIELDS}

    def sleep_slice(self) -> None:
        for _ in range(5):
            if not self._running:
                return
            time.sleep(0.1)

    @pyqtSlot(object)
    def update_config(self, config: dict[str, Any]) -> None:
        with self._lock:
            self._pending_config = copy.deepcopy(config)

    def apply_pending_config(self) -> None:
        with self._lock:
            pending = self._pending_config
            self._pending_config = None
        if pending is None:
            return
        self.config = pending
        apply_proxy_env(self.config)
        self.client = HttpClient(self.config)
        self.next_due = {source: 0.0 for source in SOURCE_FIELDS}

    def stop(self) -> None:
        self._running = False


class PRLTodayWindow(QWidget):
    def __init__(self, config: dict[str, Any]):
        super().__init__()
        self.config = copy.deepcopy(config)
        self.display_level = clean_level((self.config.get("display") or {}).get("level"))
        self.bg_opacity = self.opacity_to_int((self.config.get("window") or {}).get("alpha", 0.96))
        self.last_estimate: ProfitEstimate | None = None
        self.last_updates: dict[str, datetime | None] = {source: None for source in SOURCE_FIELDS}
        self.intervals: dict[str, int] = {source: refresh_seconds(self.config, f"{source}_seconds") for source in SOURCE_FIELDS}
        self.smoother = SmoothValue()
        self.thread: QThread | None = None
        self.worker: ProfitWorker | None = None
        self._is_config = False
        self.old_pos = QPoint()

        self.init_ui()
        self.init_tray()
        self.start_worker()
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.update_tick)
        self.tick_timer.start(refresh_seconds(self.config, "ui_tick_seconds") * 1000)
        self.restore_geometry()

    def init_ui(self) -> None:
        self.setWindowTitle("PRL-Today")
        self.setWindowFlags(FRAMELESS_FLAGS)
        self.setAttribute(TRANSLUCENT_BACKGROUND)
        self.setMouseTracking(True)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.container = QFrame()
        self.container.setObjectName("MainContainer")
        self.main_layout.addWidget(self.container)

        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(10, 6, 10, 6)
        self.container_layout.setSpacing(0)

        self.header = QWidget()
        self.header.setFixedHeight(24)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        self.title_label = QLabel("PRL-Today")
        self.title_label.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {ACCENT_LIGHT};")
        header_layout.addWidget(self.title_label)
        self.right_container = QWidget()
        header_layout.addWidget(self.right_container, 1)

        self.status_label = QLabel("starting", self.right_container)
        self.status_label.setStyleSheet(f"font-size: 9px; color: {TEXT_MUTED}; font-weight: bold;")
        self.status_label.setFixedHeight(24)

        self.btn_settings = QPushButton("...", self.right_container)
        self.btn_settings.setObjectName("HeaderBtn")
        self.btn_settings.setFixedSize(18, 18)
        self.btn_settings.clicked.connect(self.toggle_config)
        self.btn_settings.setVisible(False)

        self.btn_close = QPushButton("x", self.right_container)
        self.btn_close.setObjectName("HeaderBtn")
        self.btn_close.setFixedSize(18, 18)
        self.btn_close.clicked.connect(self.hide)
        self.btn_close.setVisible(False)

        self.header_anim = QPropertyAnimation(self.status_label, b"pos")
        self.header_anim.setDuration(250)
        self.header_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.container_layout.addWidget(self.header)

        self.view_stack = QStackedWidget()
        self.monitor_view = self.build_monitor_view()
        self.config_view = self.build_config_view()
        self.view_stack.addWidget(self.monitor_view)
        self.view_stack.addWidget(self.config_view)
        self.container_layout.addWidget(self.view_stack)

        self.sizegrip = QSizeGrip(self)
        self.sizegrip.setFixedSize(12, 12)
        self.sizegrip.setVisible(False)
        self.update_style(False)
        self.apply_display_level(force_resize=True)

    def build_monitor_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.amount_label = QLabel("CNY --")
        self.amount_label.setStyleSheet("font-size: 24px; font-weight: bold; color: white; letter-spacing: 0px;")
        self.amount_label.setMinimumHeight(30)

        self.sub_label = QLabel("$ --  |  -- PRL")
        self.sub_label.setStyleSheet(f"font-size: 10px; color: {ACCENT_LIGHT}; font-weight: bold;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(2)
        self.progress_bar.setRange(0, 86400)
        self.progress_bar.setTextVisible(False)
        self.update_progress_style()

        self.metric_row = QWidget()
        metric_layout = QHBoxLayout(self.metric_row)
        metric_layout.setContentsMargins(0, 0, 0, 0)
        metric_layout.setSpacing(8)
        self.left_metric = QLabel("hash --")
        self.right_metric = QLabel("price --")
        for label in (self.left_metric, self.right_metric):
            label.setStyleSheet("font-size: 10px; color: #DDD;")
        metric_layout.addWidget(self.left_metric)
        metric_layout.addStretch()
        metric_layout.addWidget(self.right_metric)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet(f"font-size: 9px; color: {TEXT_MUTED}; line-height: 120%;")

        layout.addWidget(self.amount_label)
        layout.addWidget(self.sub_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.metric_row)
        layout.addWidget(self.detail_label)
        layout.addStretch()
        return view

    def build_config_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(5)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(NO_FRAME)
        scroll.setHorizontalScrollBarPolicy(SCROLLBAR_OFF)
        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setContentsMargins(0, 0, 4, 0)
        form.setSpacing(5)
        form.setLabelAlignment(ALIGN_LEFT)

        self.input_miner = QLineEdit(str(self.config.get("miner_address", "")))
        self.combo_pool = QComboBox()
        self.combo_pool.addItems(pool_names(self.config) or ["AlphaPool PRL"])
        self.combo_pool.setCurrentText(str(self.config.get("selected_pool", "AlphaPool PRL")))
        self.combo_level = QComboBox()
        self.combo_level.addItems(["lite", "standard", "detail"])
        self.combo_level.setCurrentText(self.display_level)
        self.combo_hashrate = QComboBox()
        self.combo_hashrate.addItems(["fit", "miner_1h", "miner_24h", "worker_live"])
        self.combo_hashrate.setCurrentText(str((self.config.get("calculation") or {}).get("hashrate_mode", "fit")))

        calc = self.config.get("calculation") or {}
        self.combo_fee_mode = QComboBox()
        self.combo_fee_mode.addItems(["auto", "manual"])
        self.combo_fee_mode.setCurrentText(str(calc.get("fee_mode", "auto")))
        self.input_fee = QLineEdit(str(calc.get("fee_override_percent", 3.0)))
        self.combo_price_mode = QComboBox()
        self.combo_price_mode.addItems(["auto", "manual"])
        self.combo_price_mode.setCurrentText(str(calc.get("price_mode", "auto")))
        self.input_price = QLineEdit(str(calc.get("manual_price_usd", 0.52)))
        self.combo_fx_mode = QComboBox()
        self.combo_fx_mode.addItems(["auto", "manual"])
        self.combo_fx_mode.setCurrentText(str(calc.get("fx_mode", "auto")))
        self.input_fx = QLineEdit(str(calc.get("manual_usd_cny", 6.78)))

        proxy = self.config.get("proxy") or {}
        self.combo_proxy = QComboBox()
        self.combo_proxy.addItems(["enabled", "disabled"])
        self.combo_proxy.setCurrentText("enabled" if proxy.get("enabled", True) else "disabled")
        self.input_proxy = QLineEdit(str(proxy.get("url", "")))

        self.input_miner_refresh = QLineEdit(str(refresh_seconds(self.config, "miner_seconds")))
        self.input_pool_refresh = QLineEdit(str(refresh_seconds(self.config, "pool_seconds")))
        self.input_market_refresh = QLineEdit(str(refresh_seconds(self.config, "market_seconds")))
        self.input_chain_refresh = QLineEdit(str(refresh_seconds(self.config, "chain_seconds")))
        self.input_fx_refresh = QLineEdit(str(refresh_seconds(self.config, "fx_seconds")))

        self.slider_opacity = QSlider(HORIZONTAL)
        self.slider_opacity.setRange(40, 255)
        self.slider_opacity.setValue(self.bg_opacity)
        self.slider_opacity.valueChanged.connect(self.on_opacity_changed)

        self.configure_inputs()
        form.addRow("Wallet", self.input_miner)
        form.addRow("Pool", self.combo_pool)
        form.addRow("Level", self.combo_level)
        form.addRow("Hashrate", self.combo_hashrate)
        form.addRow("Fee", self.row_widget(self.combo_fee_mode, self.input_fee))
        form.addRow("PRL/USD", self.row_widget(self.combo_price_mode, self.input_price))
        form.addRow("USD/CNY", self.row_widget(self.combo_fx_mode, self.input_fx))
        form.addRow("Proxy", self.row_widget(self.combo_proxy, self.input_proxy))
        form.addRow("Refresh", self.row_widget(self.input_miner_refresh, self.input_pool_refresh, self.input_market_refresh))
        form.addRow("Chain/FX", self.row_widget(self.input_chain_refresh, self.input_fx_refresh))
        form.addRow("Opacity", self.slider_opacity)
        scroll.setWidget(form_host)

        self.config_msg = QLabel("")
        self.config_msg.setStyleSheet("font-size: 9px; color: #FF6B6B; font-weight: bold;")
        save_button = QPushButton("Save && Apply")
        save_button.setObjectName("SaveBtn")
        save_button.clicked.connect(self.save_config_action)

        layout.addWidget(scroll)
        layout.addWidget(self.config_msg)
        layout.addWidget(save_button)
        return view

    def row_widget(self, *widgets: QWidget) -> QWidget:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for widget in widgets:
            layout.addWidget(widget)
        return host

    def configure_inputs(self) -> None:
        text_inputs = [
            self.input_miner,
            self.input_fee,
            self.input_price,
            self.input_fx,
            self.input_proxy,
            self.input_miner_refresh,
            self.input_pool_refresh,
            self.input_market_refresh,
            self.input_chain_refresh,
            self.input_fx_refresh,
        ]
        for widget in text_inputs:
            widget.setMinimumHeight(22)
        for widget in (self.input_miner_refresh, self.input_pool_refresh, self.input_market_refresh, self.input_chain_refresh, self.input_fx_refresh):
            widget.setMaximumWidth(54)

    def init_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QApplication.style().standardIcon(COMPUTER_ICON))
        menu = QMenu()
        menu.addAction(QAction("Show", self, triggered=self.show_window))
        menu.addAction(QAction("Settings", self, triggered=self.show_config))
        menu.addAction(QAction("Quit", self, triggered=QApplication.instance().quit))
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def start_worker(self) -> None:
        self.thread = QThread(self)
        self.worker = ProfitWorker(self.config)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.data_updated.connect(self.on_data_updated)
        self.thread.start()

    def update_style(self, hovered: bool = False) -> None:
        border = ACCENT if hovered else "rgba(0,0,0,0)"
        self.container.setStyleSheet(
            f"""
            #MainContainer {{
                background-color: rgba(20, 20, 20, {self.bg_opacity});
                border: 2px solid {border};
                border-radius: 12px;
            }}
            #HeaderBtn {{
                background-color: transparent;
                color: white;
                border: none;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton#HeaderBtn:hover {{ color: {ACCENT_LIGHT}; }}
            QPushButton#SaveBtn {{
                background: {ACCENT};
                color: white;
                border: none;
                border-radius: 4px;
                min-height: 24px;
                font-weight: bold;
            }}
            QLineEdit, QComboBox {{
                background: rgba(255,255,255,22);
                color: white;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 2px 5px;
                font-size: 9px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #1A1A1A;
                color: white;
                selection-background-color: {ACCENT};
                outline: none;
                border: 1px solid {ACCENT};
            }}
            QFormLayout QLabel {{
                color: #AAA;
                font-size: 9px;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QSlider::groove:horizontal {{
                height: 3px;
                background: #444;
                border-radius: 1px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT};
                width: 12px;
                border-radius: 6px;
                margin: -5px 0;
            }}
            """
        )

    def update_progress_style(self) -> None:
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: #444;
                border: none;
                border-radius: 1px;
                margin: 3px 0;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT};
                border-radius: 1px;
            }}
            """
        )

    def apply_display_level(self, force_resize: bool = False) -> None:
        level = self.display_level
        self.metric_row.setVisible(level in {"standard", "detail"})
        self.detail_label.setVisible(level == "detail")
        if self._is_config:
            return
        sizes = {
            "lite": (218, 92),
            "standard": (282, 132),
            "detail": (382, 222),
        }
        min_sizes = {
            "lite": (180, 78),
            "standard": (230, 112),
            "detail": (320, 180),
        }
        min_w, min_h = min_sizes[level]
        self.setMinimumSize(min_w, min_h)
        if force_resize:
            width, height = sizes[level]
            self.resize(width, height)

    def restore_geometry(self) -> None:
        window = self.config.get("window") or {}
        x = safe_int(window.get("x", 80), 80, 0)
        y = safe_int(window.get("y", 80), 80, 0)
        width = safe_int(window.get("width", self.width()), self.width(), self.minimumWidth())
        height = safe_int(window.get("height", self.height()), self.height(), self.minimumHeight())
        self.setGeometry(x, y, width, height)

    def on_opacity_changed(self, value: int) -> None:
        self.bg_opacity = value
        self.update_style(self.underMouse())

    def update_header_positions(self, hovered: bool) -> None:
        width = self.right_container.width()
        self.btn_settings.move(max(width - 40, 0), 3)
        self.btn_close.move(max(width - 18, 0), 3)
        self.btn_settings.setVisible(hovered)
        self.btn_close.setVisible(hovered)
        self.status_label.adjustSize()
        reserved = 45 if hovered else 0
        target_x = max(width - reserved - self.status_label.width(), 0)
        self.header_anim.stop()
        self.header_anim.setEndValue(QPoint(int(target_x), 0))
        self.header_anim.start()

    def toggle_config(self) -> None:
        if self._is_config:
            self.view_stack.setCurrentIndex(0)
            self.btn_settings.setText("...")
            self._is_config = False
            self.apply_display_level(force_resize=True)
        else:
            self.show_config()

    def show_config(self) -> None:
        self._is_config = True
        self.view_stack.setCurrentIndex(1)
        self.btn_settings.setText("<")
        self.setMinimumSize(380, 390)
        self.resize(max(self.width(), 420), max(self.height(), 480))
        self.show_window()

    def show_window(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def save_config_action(self) -> None:
        miner = self.input_miner.text().strip()
        if not miner:
            self.config_msg.setText("Wallet is required")
            return

        cfg = copy.deepcopy(self.config)
        cfg["miner_address"] = miner
        cfg["selected_pool"] = self.combo_pool.currentText()
        cfg.setdefault("display", {})["level"] = self.combo_level.currentText()
        cfg.setdefault("proxy", {})["enabled"] = self.combo_proxy.currentText() == "enabled"
        cfg["proxy"]["url"] = self.input_proxy.text().strip()
        cfg["proxy"]["use_env"] = True

        calc = cfg.setdefault("calculation", {})
        calc["hashrate_mode"] = self.combo_hashrate.currentText()
        calc["fee_mode"] = self.combo_fee_mode.currentText()
        calc["fee_override_percent"] = safe_float(self.input_fee.text(), float(calc.get("fee_override_percent", 3.0)))
        calc["price_mode"] = self.combo_price_mode.currentText()
        calc["manual_price_usd"] = safe_float(self.input_price.text(), float(calc.get("manual_price_usd", 0.52)))
        calc["fx_mode"] = self.combo_fx_mode.currentText()
        calc["manual_usd_cny"] = safe_float(self.input_fx.text(), float(calc.get("manual_usd_cny", 6.78)))

        refresh = cfg.setdefault("refresh", {})
        refresh["miner_seconds"] = safe_int(self.input_miner_refresh.text(), 30, 5)
        refresh["pool_seconds"] = safe_int(self.input_pool_refresh.text(), 30, 5)
        refresh["market_seconds"] = safe_int(self.input_market_refresh.text(), 30, 5)
        refresh["chain_seconds"] = safe_int(self.input_chain_refresh.text(), 60, 5)
        refresh["fx_seconds"] = safe_int(self.input_fx_refresh.text(), 3600, 5)
        refresh["ui_tick_seconds"] = refresh_seconds(cfg, "ui_tick_seconds")

        window = cfg.setdefault("window", {})
        window["alpha"] = self.bg_opacity / 255.0
        self.capture_geometry(cfg)

        save_config(cfg, CONFIG_PATH)
        self.config = cfg
        self.display_level = clean_level((cfg.get("display") or {}).get("level"))
        self.intervals = {source: refresh_seconds(cfg, f"{source}_seconds") for source in SOURCE_FIELDS}
        self.tick_timer.start(refresh_seconds(cfg, "ui_tick_seconds") * 1000)
        if self.worker:
            self.worker.update_config(copy.deepcopy(cfg))
        self.config_msg.setText("")
        self.toggle_config()

    def capture_geometry(self, cfg: dict[str, Any] | None = None) -> None:
        target = cfg if cfg is not None else self.config
        geom = self.geometry()
        window = target.setdefault("window", {})
        window["x"] = geom.x()
        window["y"] = geom.y()
        window["width"] = geom.width()
        window["height"] = geom.height()
        window["alpha"] = self.bg_opacity / 255.0

    def persist_geometry(self) -> None:
        self.capture_geometry(self.config)
        save_config(self.config, CONFIG_PATH)

    @pyqtSlot(object)
    def on_data_updated(self, data: dict[str, Any]) -> None:
        estimate = data.get("estimate")
        if not isinstance(estimate, ProfitEstimate):
            return
        self.last_estimate = estimate
        self.last_updates = data.get("last_updates") or self.last_updates
        self.intervals = data.get("intervals") or self.intervals
        self.smoother.reset(estimate)
        self.update_tick()

    def update_tick(self) -> None:
        estimate = self.last_estimate
        if estimate is None:
            return
        prl = self.smoother.value()
        usd = prl * estimate.price_usd
        cny = usd * estimate.usd_cny
        self.amount_label.setText(f"CNY {cny:.6f}")
        self.sub_label.setText(f"${usd:.6f}  |  {prl:.6f} PRL")
        elapsed, _ = seconds_today()
        self.progress_bar.setValue(int(elapsed))
        self.left_metric.setText(format_hps(estimate.hashrate_hps))
        self.right_metric.setText(f"${estimate.price_usd:.6f}  fee {estimate.fee_percent:.2f}%")
        status = "ERR" if estimate.errors else estimate.computed_at.strftime("%H:%M:%S")
        self.status_label.setText(status)
        self.status_label.adjustSize()
        self.update_header_positions(self.underMouse())
        self.update_detail_text(estimate)

    def update_detail_text(self, estimate: ProfitEstimate) -> None:
        if self.display_level != "detail":
            return
        refresh_text = (
            f"refresh miner/pool/market {self.intervals.get('miner', 0)}/"
            f"{self.intervals.get('pool', 0)}/{self.intervals.get('market', 0)}s, "
            f"chain {self.intervals.get('chain', 0)}s, fx {self.intervals.get('fx', 0)}s"
        )
        latest = ", ".join(
            f"{source}:{stamp.strftime('%H:%M:%S') if stamp else '--'}" for source, stamp in self.last_updates.items()
        )
        errors = "; ".join(estimate.errors[:2]) if estimate.errors else "ok"
        self.detail_label.setText(
            f"24h CNY {estimate.projected_24h_cny:.6f} | USD {estimate.projected_24h_usd:.6f} | PRL {estimate.projected_24h_prl:.6f}\n"
            f"net {format_hps(estimate.network_hashrate_hps)} | block {estimate.block_time_seconds:.2f}s | reward {estimate.block_reward_prl:.4f}\n"
            f"{refresh_text}\n"
            f"last {latest}\n"
            f"{errors}"
        )

    def enterEvent(self, event: Any) -> None:
        self.update_style(True)
        self.sizegrip.setVisible(True)
        self.update_header_positions(True)
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:
        self.update_style(False)
        self.sizegrip.setVisible(False)
        self.update_header_positions(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == LEFT_BUTTON:
            self.old_pos = self.event_global_pos(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if event.buttons() == LEFT_BUTTON:
            current = self.event_global_pos(event)
            delta = current - self.old_pos
            new_pos = self.pos() + delta
            screen = QApplication.primaryScreen().availableGeometry()
            new_pos.setX(max(screen.left(), min(new_pos.x(), screen.right() - self.width())))
            new_pos.setY(max(screen.top(), min(new_pos.y(), screen.bottom() - self.height())))
            self.move(new_pos)
            self.old_pos = current
            self.persist_geometry()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        self.sizegrip.move(self.width() - 14, self.height() - 14)
        self.update_header_positions(self.underMouse())
        if self.isVisible():
            self.persist_geometry()

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (TRAY_TRIGGER, TRAY_DOUBLE_CLICK):
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

    def shutdown(self) -> None:
        if self.worker:
            self.worker.stop()
        if self.thread:
            self.thread.quit()
            self.thread.wait(3000)
        self.persist_geometry()

    @staticmethod
    def opacity_to_int(value: Any) -> int:
        alpha = safe_float(value, 0.96, 0.1)
        if alpha <= 1.0:
            return max(40, min(255, int(alpha * 255)))
        return max(40, min(255, int(alpha)))

    @staticmethod
    def event_global_pos(event: Any) -> QPoint:
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        return event.globalPos()


def run(config: dict[str, Any]) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = PRLTodayWindow(config)
    app.aboutToQuit.connect(window.shutdown)
    window.show()
    if hasattr(app, "exec"):
        sys.exit(app.exec())
    sys.exit(app.exec_())
