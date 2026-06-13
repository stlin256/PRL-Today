from __future__ import annotations

import copy
import locale
import math
import os
import sys
import threading
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from PyQt6.QtCore import QObject, QEasingCurve, QPoint, QPropertyAnimation, QSize, QThread, QTimer, Qt, QUrl, pyqtSignal, pyqtSlot
    from PyQt6.QtGui import QAction, QDesktopServices, QIcon, QPixmap
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
    from PyQt5.QtCore import QObject, QEasingCurve, QPoint, QPropertyAnimation, QSize, QThread, QTimer, Qt, QUrl, pyqtSignal, pyqtSlot
    from PyQt5.QtGui import QDesktopServices, QIcon, QPixmap
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

from .api import SOURCE_FIELDS, ApiError, DataSnapshot, HttpClient, apply_proxy_env, fetch_snapshot, merge_snapshot, normalize_http_url
from .config import (
    BUNDLE_ROOT,
    CONFIG_PATH,
    market_source_names,
    miner_address_error,
    mining_software_names,
    pool_names,
    refresh_seconds,
    save_config,
)
from .model import ProfitEstimate, SmoothValue, compute_estimate, seconds_today


FONT_UI = "'Urbanist', 'Inter', 'Segoe UI'"
FONT_MONO = "'Source Code Pro', 'Cascadia Mono', 'Consolas'"
FONT_SERIF = "'Source Serif 4', 'Georgia'"
BG = "#111111"
PANEL = "#1F1F1F"
PANEL_SOFT = "#2A2926"
PEARL = "#F0EFEA"
SHELL = "#D8D0C5"
SHELL_DARK = "#8E867A"
ACCENT = "#E6D1AD"
ACCENT_LIGHT = "#FFF7E6"
TEXT_MUTED = "#AFA79C"
INPUT_BG = "#171717"
INPUT_BORDER = "#5C564E"
LOADING_ACCENT = "#E4B7FF"
REPOSITORY_FALLBACK_URL = "https://github.com/stlin256/prl-today"
TRUSTED_REPOSITORY_HOSTS = {"github.com", "www.github.com"}
DPI_BASE = 96.0
MIN_UI_SCALE = 0.85
MAX_UI_SCALE = 1.8

if QT_API == "PyQt6":
    FRAMELESS_FLAGS = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
    TRANSLUCENT_BACKGROUND = Qt.WidgetAttribute.WA_TranslucentBackground
    NO_FRAME = QFrame.Shape.NoFrame
    SCROLLBAR_OFF = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    ALIGN_LEFT = Qt.AlignmentFlag.AlignLeft
    ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
    HORIZONTAL = Qt.Orientation.Horizontal
    COMPUTER_ICON = QStyle.StandardPixmap.SP_ComputerIcon
    LEFT_BUTTON = Qt.MouseButton.LeftButton
    TRAY_TRIGGER = QSystemTrayIcon.ActivationReason.Trigger
    TRAY_DOUBLE_CLICK = QSystemTrayIcon.ActivationReason.DoubleClick
    KEEP_ASPECT = Qt.AspectRatioMode.KeepAspectRatio
    SMOOTH_TRANSFORM = Qt.TransformationMode.SmoothTransformation
else:
    FRAMELESS_FLAGS = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    TRANSLUCENT_BACKGROUND = Qt.WA_TranslucentBackground
    NO_FRAME = QFrame.NoFrame
    SCROLLBAR_OFF = Qt.ScrollBarAlwaysOff
    ALIGN_LEFT = Qt.AlignLeft
    ALIGN_CENTER = Qt.AlignCenter
    HORIZONTAL = Qt.Horizontal
    COMPUTER_ICON = QStyle.SP_ComputerIcon
    LEFT_BUTTON = Qt.LeftButton
    TRAY_TRIGGER = QSystemTrayIcon.Trigger
    TRAY_DOUBLE_CLICK = QSystemTrayIcon.DoubleClick
    KEEP_ASPECT = Qt.KeepAspectRatio
    SMOOTH_TRANSFORM = Qt.SmoothTransformation


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


def asset_path(*parts: str) -> Path:
    return BUNDLE_ROOT.joinpath(*parts)


def system_prefers_cny() -> bool:
    values = [
        locale.getlocale()[0] or "",
        locale.getlocale(locale.LC_CTYPE)[0] or "",
        os.environ.get("LANG", ""),
        os.environ.get("LANGUAGE", ""),
    ]
    text = " ".join(values).lower()
    return text.startswith("zh") or "chinese" in text


def display_currency(config: dict[str, Any]) -> str:
    requested = str((config.get("display") or {}).get("currency", "auto")).strip().lower()
    if requested in {"usd", "cny"}:
        return requested
    return "cny" if system_prefers_cny() else "usd"


def scaled_int(value: float, scale: float, minimum: int = 1) -> int:
    return max(minimum, int(round(value * scale)))


def bounded_ui_scale(value: Any, default: float = 1.0) -> float:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        parsed = default
    if not math.isfinite(parsed):
        parsed = default
    return min(max(parsed, MIN_UI_SCALE), MAX_UI_SCALE)


def screen_ui_scale(screen: Any | None = None) -> float:
    override = os.environ.get("PRL_TODAY_UI_SCALE")
    if override:
        return bounded_ui_scale(override)
    if screen is None:
        try:
            screen = QApplication.primaryScreen()
        except RuntimeError:
            screen = None
    if screen is None:
        return 1.0
    try:
        dpi = float(screen.logicalDotsPerInch())
    except (TypeError, ValueError, AttributeError):
        return 1.0
    if not math.isfinite(dpi) or dpi <= 0:
        return 1.0
    return bounded_ui_scale(max(dpi / DPI_BASE, 1.0), default=1.0)


def qt_application_attribute(name: str) -> Any:
    container = getattr(Qt, "ApplicationAttribute", None)
    return getattr(container, name, None) or getattr(Qt, name, None)


def configure_high_dpi() -> None:
    if QT_API == "PyQt5":
        os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    for name in ("AA_EnableHighDpiScaling", "AA_UseHighDpiPixmaps"):
        attribute = qt_application_attribute(name)
        if attribute is not None:
            QApplication.setAttribute(attribute, True)
    policy_container = getattr(Qt, "HighDpiScaleFactorRoundingPolicy", None)
    policy = getattr(policy_container, "PassThrough", None)
    if policy is not None and hasattr(QApplication, "setHighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(policy)


class SlotNumber(QWidget):
    def __init__(self, scale: float = 1.0) -> None:
        super().__init__()
        self.scale = scale
        self.labels: list[QLabel] = []
        self.current = ""
        self.target = ""
        self.phase = 0
        self.digit_layout = QHBoxLayout(self)
        self.digit_layout.setContentsMargins(0, 0, 0, 0)
        self.digit_layout.setSpacing(0)
        self.setMinimumHeight(self.dp(30))

    def dp(self, value: float, minimum: int = 1) -> int:
        return scaled_int(value, self.scale, minimum)

    def digit_style(self) -> str:
        return (
            f"font-family: {FONT_MONO}; font-size: {self.dp(23)}px; font-weight: 800; color: {PEARL}; "
            "background: transparent; letter-spacing: 0px;"
        )

    def set_target(self, value: str) -> None:
        if value == self.target:
            return
        self.target = value
        width = len(self.target)
        if len(self.current) < width:
            self.current = self.current.rjust(width)
        elif len(self.current) > width:
            self.current = self.current[-width:]
        self.ensure_labels(width)

    def ensure_labels(self, width: int) -> None:
        while len(self.labels) < width:
            label = QLabel(" ")
            label.setAlignment(ALIGN_CENTER)
            label.setMinimumWidth(self.dp(13))
            label.setStyleSheet(self.digit_style())
            self.labels.append(label)
            self.digit_layout.addWidget(label)
        while len(self.labels) > width:
            label = self.labels.pop()
            self.digit_layout.removeWidget(label)
            label.deleteLater()

    def step(self) -> None:
        if not self.target:
            return
        self.phase = (self.phase + 1) % 10
        chars = list(self.current.rjust(len(self.target)))
        target = self.target
        changed = False
        for idx, goal in enumerate(target):
            current = chars[idx]
            if current == goal:
                continue
            if current.isdigit() and goal.isdigit():
                chars[idx] = str((int(current) + 1) % 10)
                if chars[idx] == goal:
                    changed = True
            else:
                chars[idx] = goal
                changed = True
        self.current = "".join(chars)
        if self.current == target:
            changed = True
        self.render(changed)

    def render(self, settled: bool = False) -> None:
        if not self.labels:
            return
        text = self.current or self.target
        self.ensure_labels(len(text))
        for idx, char in enumerate(text):
            label = self.labels[idx]
            label.setText(char)
            label.setStyleSheet(self.digit_style())


class ProfitWorker(QObject):
    data_updated = pyqtSignal(object)
    MAX_BACKOFF_SECONDS = 300

    def __init__(self, config: dict[str, Any]):
        super().__init__()
        self.config = copy.deepcopy(config)
        self.snapshot = DataSnapshot()
        self.last_updates: dict[str, datetime | None] = {source: None for source in SOURCE_FIELDS}
        self.next_due: dict[str, float] = {source: 0.0 for source in SOURCE_FIELDS}
        self.failure_counts: dict[str, int] = {source: 0 for source in SOURCE_FIELDS}
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
                self.data_updated.emit(
                    {
                        "loading": True,
                        "last_updates": dict(self.last_updates),
                        "intervals": self.intervals(),
                        "sources": list(due_sources),
                    }
                )
                try:
                    update = fetch_snapshot(self.config, self.client, due_sources)
                except Exception as exc:
                    update = DataSnapshot(errors=[f"worker: unexpected {type(exc).__name__}: {exc}"])
                merge_snapshot(self.snapshot, update)
                now = datetime.now().astimezone()
                for source in due_sources:
                    field_name = SOURCE_FIELDS[source]
                    success = getattr(update, field_name) is not None
                    if success:
                        self.last_updates[source] = now
                    self.next_due[source] = time.monotonic() + self.next_delay(source, success)
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

    def next_delay(self, source: str, success: bool) -> int:
        interval = refresh_seconds(self.config, f"{source}_seconds")
        if success:
            self.failure_counts[source] = 0
            return interval
        failures = self.failure_counts.get(source, 0) + 1
        self.failure_counts[source] = failures
        return min(interval * (2 ** min(failures, 4)), self.MAX_BACKOFF_SECONDS)

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
        self.failure_counts = {source: 0 for source in SOURCE_FIELDS}

    def stop(self) -> None:
        self._running = False


class PRLTodayWindow(QWidget):
    def __init__(self, config: dict[str, Any]):
        super().__init__()
        self.ui_scale = screen_ui_scale()
        self.config = copy.deepcopy(config)
        self.display_level = clean_level((self.config.get("display") or {}).get("level"))
        self.currency = display_currency(self.config)
        self.bg_opacity = self.opacity_to_int((self.config.get("window") or {}).get("alpha", 0.96))
        self.last_estimate: ProfitEstimate | None = None
        self.last_updates: dict[str, datetime | None] = {source: None for source in SOURCE_FIELDS}
        self.intervals: dict[str, int] = {source: refresh_seconds(self.config, f"{source}_seconds") for source in SOURCE_FIELDS}
        self.loading = True
        self.loading_phase = 0
        self.loading_sources: list[str] = ["miner", "pool", "market"]
        self.smoother = SmoothValue()
        self.thread: QThread | None = None
        self.worker: ProfitWorker | None = None
        self._is_config = False
        self._first_run = not bool((self.config.get("display") or {}).get("configured", False))
        self._dragging = False
        self._suppress_geometry_persist = True
        self._monitor_geometry: tuple[int, int, int, int] | None = None
        self._header_target_x: int | None = None
        self._progress_loading: bool | None = None
        self.old_pos = QPoint()
        self.geometry_save_timer = QTimer(self)
        self.geometry_save_timer.setSingleShot(True)
        self.geometry_save_timer.timeout.connect(self.persist_geometry)

        self.init_ui()
        self.init_tray()
        self.start_worker()
        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.update_tick)
        self.tick_timer.start(refresh_seconds(self.config, "ui_tick_seconds") * 1000)
        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self.animate_loading)
        self.loading_timer.start(180)
        self.restore_geometry()
        self._suppress_geometry_persist = False
        if self._first_run:
            QTimer.singleShot(350, self.show_first_run_config)

    def dp(self, value: float, minimum: int = 1) -> int:
        return scaled_int(value, self.ui_scale, minimum)

    def init_ui(self) -> None:
        self.setWindowTitle("PRL-Today")
        self.setWindowIcon(QIcon(str(asset_path("assets", "app_icon.png"))))
        self.setWindowFlags(FRAMELESS_FLAGS)
        self.setAttribute(TRANSLUCENT_BACKGROUND)
        self.setMouseTracking(True)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.container = QFrame()
        self.container.setObjectName("MainContainer")
        self.main_layout.addWidget(self.container)

        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(self.dp(10), self.dp(6), self.dp(10), self.dp(6))
        self.container_layout.setSpacing(0)

        self.header = QWidget()
        self.header.setFixedHeight(self.dp(24))
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(self.dp(2))
        self.logo_label = QLabel()
        self.logo_label.setObjectName("LogoLabel")
        self.logo_label.setFixedSize(self.dp(40), self.dp(13))
        self.load_logo()
        header_layout.addWidget(self.logo_label)
        self.title_label = QLabel("Today")
        self.title_label.setStyleSheet(
            f"font-family: {FONT_UI}; font-size: {self.dp(10)}px; font-weight: 700; color: {PEARL};"
        )
        header_layout.addWidget(self.title_label)
        self.right_container = QWidget()
        header_layout.addWidget(self.right_container, 1)

        self.status_label = QLabel("starting", self.right_container)
        self.status_label.setStyleSheet(f"font-size: {self.dp(9)}px; color: {TEXT_MUTED}; font-weight: bold;")
        self.status_label.setFixedHeight(self.dp(24))

        self.btn_settings = QPushButton("...", self.right_container)
        self.btn_settings.setObjectName("HeaderBtn")
        self.btn_settings.setFixedSize(self.dp(18), self.dp(18))
        self.btn_settings.clicked.connect(self.toggle_config)
        self.btn_settings.setVisible(False)

        self.btn_close = QPushButton("x", self.right_container)
        self.btn_close.setObjectName("HeaderBtn")
        self.btn_close.setFixedSize(self.dp(18), self.dp(18))
        self.btn_close.clicked.connect(self.hide)
        self.btn_close.setVisible(False)

        self.header_anim = QPropertyAnimation(self.status_label, b"pos")
        self.header_anim.setDuration(180)
        self.header_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.container_layout.addWidget(self.header)

        self.view_stack = QStackedWidget()
        self.monitor_view = self.build_monitor_view()
        self.config_view = self.build_config_view()
        self.view_stack.addWidget(self.monitor_view)
        self.view_stack.addWidget(self.config_view)
        self.container_layout.addWidget(self.view_stack)

        self.sizegrip = QSizeGrip(self)
        self.sizegrip.setFixedSize(self.dp(12), self.dp(12))
        self.sizegrip.setVisible(False)
        self.update_style(False)
        self.apply_display_level(force_resize=True)

    def load_logo(self) -> None:
        pixmap = QPixmap(str(asset_path("assets", "prl_logo.png")))
        if pixmap.isNull():
            self.logo_label.setText("PRL")
            self.logo_label.setStyleSheet(f"font-family: {FONT_UI}; color: {PEARL}; font-size: {self.dp(10)}px; font-weight: 800;")
            return
        self.logo_label.setPixmap(pixmap.scaled(self.logo_label.size(), KEEP_ASPECT, SMOOTH_TRANSFORM))

    def build_monitor_view(self) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.dp(2))

        self.amount_label = SlotNumber(self.ui_scale)
        self.amount_label.set_target(self.loading_text())
        self.amount_label.step()

        self.sub_label = QLabel("")
        self.sub_label.setMinimumWidth(self.dp(180))
        self.sub_label.setStyleSheet(
            f"font-family: {FONT_MONO}; font-size: {self.dp(10)}px; color: {SHELL}; font-weight: 700; letter-spacing: 0px;"
        )

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(self.dp(2))
        self.progress_bar.setRange(0, 86400)
        self.progress_bar.setTextVisible(False)
        self.update_progress_style()

        self.metric_row = QWidget()
        metric_layout = QHBoxLayout(self.metric_row)
        metric_layout.setContentsMargins(0, 0, 0, 0)
        metric_layout.setSpacing(self.dp(8))
        self.left_metric = QLabel("hash --")
        self.right_metric = QLabel("price --")
        for label in (self.left_metric, self.right_metric):
            label.setStyleSheet(f"font-family: {FONT_UI}; font-size: {self.dp(10)}px; color: {SHELL};")
        metric_layout.addWidget(self.left_metric)
        metric_layout.addStretch()
        metric_layout.addWidget(self.right_metric)

        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        self.detail_label.setStyleSheet(f"font-family: {FONT_UI}; font-size: {self.dp(9)}px; color: {TEXT_MUTED}; line-height: 120%;")

        layout.addWidget(self.amount_label)
        layout.addWidget(self.sub_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.metric_row)
        layout.addWidget(self.detail_label)
        return view

    def build_config_view(self) -> QWidget:
        view = QWidget()
        view.setObjectName("ConfigView")
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, self.dp(4), 0, self.dp(4))
        layout.setSpacing(self.dp(5))

        scroll = QScrollArea()
        scroll.setObjectName("ConfigScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(NO_FRAME)
        scroll.setHorizontalScrollBarPolicy(SCROLLBAR_OFF)
        form_host = QWidget()
        form_host.setObjectName("ConfigForm")
        form = QFormLayout(form_host)
        form.setContentsMargins(0, 0, self.dp(4), 0)
        form.setSpacing(self.dp(5))
        form.setLabelAlignment(ALIGN_LEFT)

        self.input_miner = QLineEdit(str(self.config.get("miner_address", "")))
        self.combo_pool = QComboBox()
        self.combo_pool.addItems(pool_names(self.config) or ["AlphaPool PRL"])
        self.combo_pool.setCurrentText(str(self.config.get("selected_pool", "AlphaPool PRL")))
        self.combo_level = QComboBox()
        self.combo_level.addItems(["lite", "standard", "detail"])
        self.combo_level.setCurrentText(self.display_level)
        self.combo_currency = QComboBox()
        self.combo_currency.addItems(["auto", "usd", "cny"])
        self.combo_currency.setCurrentText(str((self.config.get("display") or {}).get("currency", "auto")).lower())
        self.combo_hashrate = QComboBox()
        self.combo_hashrate.addItems(["fit", "miner_1h", "miner_24h", "worker_live"])
        self.combo_hashrate.setCurrentText(str((self.config.get("calculation") or {}).get("hashrate_mode", "fit")))
        self.combo_mining_software = QComboBox()
        self.combo_mining_software.addItems(mining_software_names(self.config) or ["AlphaMiner"])
        self.combo_mining_software.setCurrentText(str(self.config.get("selected_mining_software", "AlphaMiner")))
        self.combo_mining_software.currentTextChanged.connect(self.sync_tool_fee_from_software)

        calc = self.config.get("calculation") or {}
        self.combo_fee_mode = QComboBox()
        self.combo_fee_mode.addItems(["auto", "manual"])
        self.combo_fee_mode.setCurrentText(str(calc.get("fee_mode", "auto")))
        self.input_fee = QLineEdit(str(calc.get("fee_override_percent", 3.0)))
        self.combo_tool_fee_mode = QComboBox()
        self.combo_tool_fee_mode.addItems(["auto", "manual"])
        self.combo_tool_fee_mode.setCurrentText(str(calc.get("tool_fee_mode", "auto")))
        self.combo_tool_fee_mode.currentTextChanged.connect(self.sync_tool_fee_from_software)
        self.input_tool_fee = QLineEdit(str(calc.get("tool_fee_percent", 0.0)))
        self.combo_market_source = QComboBox()
        self.combo_market_source.addItems(market_source_names(self.config) or ["PRLScan"])
        self.combo_market_source.setCurrentText(str(self.config.get("selected_market_source", "PRLScan")))
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

        self.repo_url = str(self.config.get("repository_url") or "https://github.com/stlin256/prl-today")
        self.repo_button = QPushButton("stlin256/PRL-Today")
        self.repo_button.setObjectName("RepoButton")
        self.repo_button.setFixedHeight(self.dp(24))
        self.repo_button.setIcon(QIcon(str(asset_path("assets", "github_mark.png"))))
        self.repo_button.setIconSize(QSize(self.dp(15), self.dp(15)))
        self.repo_button.clicked.connect(self.open_repository)

        self.configure_inputs()
        self.sync_tool_fee_from_software()
        form.addRow(self.form_label("Wallet"), self.input_miner)
        form.addRow(self.form_label("Pool"), self.combo_pool)
        form.addRow(self.form_label("Level"), self.combo_level)
        form.addRow(self.form_label("Currency"), self.combo_currency)
        form.addRow(self.form_label("Hashrate"), self.combo_hashrate)
        form.addRow(self.form_label("Miner soft"), self.combo_mining_software)
        form.addRow(self.form_label("Pool fee"), self.row_widget(self.combo_fee_mode, self.input_fee))
        form.addRow(self.form_label("Tool fee"), self.row_widget(self.combo_tool_fee_mode, self.input_tool_fee))
        form.addRow(self.form_label("Price src"), self.combo_market_source)
        form.addRow(self.form_label("PRL/USD"), self.row_widget(self.combo_price_mode, self.input_price))
        form.addRow(self.form_label("USD/CNY"), self.row_widget(self.combo_fx_mode, self.input_fx))
        form.addRow(self.form_label("Proxy"), self.row_widget(self.combo_proxy, self.input_proxy))
        form.addRow(self.form_label("Refresh"), self.row_widget(self.input_miner_refresh, self.input_pool_refresh, self.input_market_refresh))
        form.addRow(self.form_label("Chain/FX"), self.row_widget(self.input_chain_refresh, self.input_fx_refresh))
        form.addRow(self.form_label("Opacity"), self.slider_opacity)
        form.addRow(self.form_label("Repo"), self.repo_button)
        scroll.setWidget(form_host)

        self.config_msg = QLabel("")
        self.config_msg.setStyleSheet(f"font-size: {self.dp(9)}px; color: #FF6B6B; font-weight: bold;")
        save_button = QPushButton("Save && Apply")
        save_button.setObjectName("SaveBtn")
        save_button.clicked.connect(self.save_config_action)

        layout.addWidget(scroll)
        layout.addWidget(self.config_msg)
        layout.addWidget(save_button)
        return view

    def form_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FormLabel")
        label.setMinimumWidth(self.dp(66))
        label.setStyleSheet(f"color: {SHELL}; font-family: {FONT_UI}; font-size: {self.dp(9)}px; font-weight: 700;")
        return label

    def row_widget(self, *widgets: QWidget) -> QWidget:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.dp(4))
        for widget in widgets:
            layout.addWidget(widget)
        return host

    def open_repository(self) -> None:
        QDesktopServices.openUrl(QUrl(self.safe_repository_url(self.repo_url)))

    @staticmethod
    def safe_repository_url(url: str) -> str:
        try:
            normalized = normalize_http_url(url)
        except ApiError:
            return REPOSITORY_FALLBACK_URL
        parsed = urllib.parse.urlparse(normalized)
        if parsed.scheme == "https" and parsed.netloc.lower() in TRUSTED_REPOSITORY_HOSTS:
            return normalized
        return REPOSITORY_FALLBACK_URL

    def configure_inputs(self) -> None:
        input_style = (
            f"background: {INPUT_BG}; color: {PEARL}; border: 1px solid {INPUT_BORDER}; "
            f"border-radius: {self.dp(4)}px; padding: {self.dp(3)}px {self.dp(6)}px; font-family: {FONT_UI}; font-size: {self.dp(9)}px; "
            f"selection-background-color: {ACCENT}; selection-color: #111111;"
        )
        combo_style = (
            f"QComboBox {{ {input_style} }}"
            f"QComboBox QAbstractItemView {{ background-color: {PANEL}; color: {PEARL}; "
            f"selection-background-color: {ACCENT}; selection-color: #111111; outline: none; border: 1px solid {ACCENT}; }}"
        )
        text_inputs = [
            self.input_miner,
            self.input_fee,
            self.input_tool_fee,
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
            widget.setMinimumHeight(self.dp(22))
            widget.setStyleSheet(input_style)
        for widget in (
            self.combo_pool,
            self.combo_level,
            self.combo_currency,
            self.combo_hashrate,
            self.combo_mining_software,
            self.combo_fee_mode,
            self.combo_tool_fee_mode,
            self.combo_market_source,
            self.combo_price_mode,
            self.combo_fx_mode,
            self.combo_proxy,
        ):
            widget.setMinimumHeight(self.dp(22))
            widget.setStyleSheet(combo_style)
        for widget in (self.input_miner_refresh, self.input_pool_refresh, self.input_market_refresh, self.input_chain_refresh, self.input_fx_refresh):
            widget.setMaximumWidth(self.dp(54))

    def sync_tool_fee_from_software(self) -> None:
        if not hasattr(self, "combo_tool_fee_mode") or not hasattr(self, "input_tool_fee"):
            return
        auto = self.combo_tool_fee_mode.currentText() == "auto"
        self.input_tool_fee.setEnabled(not auto)
        if not auto:
            return
        selected = self.combo_mining_software.currentText()
        for item in self.config.get("mining_software", []):
            if item.get("name") == selected:
                self.input_tool_fee.setText(str(item.get("dev_fee_percent", 0.0)))
                return

    def init_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        icon = QIcon(str(asset_path("assets", "app_icon.png")))
        if icon.isNull():
            icon = QApplication.style().standardIcon(COMPUTER_ICON)
        self.tray_icon.setIcon(icon)
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
                background-color: rgba(17, 17, 17, {self.bg_opacity});
                border: {self.dp(2)}px solid {border};
                border-radius: {self.dp(12)}px;
            }}
            #LogoLabel {{
                background-color: transparent;
            }}
            #HeaderBtn {{
                background-color: transparent;
                color: {PEARL};
                border: none;
                font-family: {FONT_UI};
                font-size: {self.dp(13)}px;
                font-weight: 700;
            }}
            QPushButton#HeaderBtn:hover {{ color: {ACCENT_LIGHT}; }}
            QPushButton#SaveBtn {{
                background: {ACCENT};
                color: #111111;
                border: none;
                border-radius: {self.dp(4)}px;
                min-height: {self.dp(24)}px;
                font-family: {FONT_UI};
                font-weight: 800;
            }}
            QPushButton#SaveBtn:hover {{
                background: {ACCENT_LIGHT};
            }}
            QLineEdit, QComboBox {{
                background: {INPUT_BG};
                color: {PEARL};
                border: 1px solid {INPUT_BORDER};
                border-radius: {self.dp(4)}px;
                padding: {self.dp(3)}px {self.dp(6)}px;
                font-family: {FONT_UI};
                font-size: {self.dp(9)}px;
                selection-background-color: {ACCENT};
                selection-color: #111111;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {ACCENT};
            }}
            QLineEdit:disabled, QComboBox:disabled {{
                color: {SHELL};
                background: {PANEL};
            }}
            QComboBox QAbstractItemView {{
                background-color: {PANEL};
                color: {PEARL};
                selection-background-color: {ACCENT};
                selection-color: #111111;
                outline: none;
                border: 1px solid {ACCENT};
            }}
            QLabel#FormLabel {{
                color: {SHELL};
                font-family: {FONT_UI};
                font-size: {self.dp(9)}px;
                font-weight: 700;
            }}
            QLabel#RepoLink {{
                color: {ACCENT};
                font-family: {FONT_UI};
                font-size: {self.dp(9)}px;
            }}
            QLabel#RepoLink a {{
                color: {ACCENT};
                text-decoration: none;
            }}
            QPushButton#RepoButton {{
                background: transparent;
                border: 1px solid {INPUT_BORDER};
                border-radius: {self.dp(4)}px;
                color: {PEARL};
                font-family: {FONT_UI};
                font-size: {self.dp(10)}px;
                font-weight: 700;
                padding: {self.dp(2)}px {self.dp(7)}px;
                text-align: left;
            }}
            QPushButton#RepoButton:hover {{
                border: 1px solid {ACCENT};
                background: {PANEL_SOFT};
            }}
            QWidget#ConfigView, QWidget#ConfigForm {{
                background: transparent;
            }}
            QScrollArea#ConfigScroll {{
                background: transparent;
                border: none;
            }}
            QScrollArea#ConfigScroll > QWidget > QWidget {{
                background: transparent;
            }}
            QSlider::groove:horizontal {{
                height: {self.dp(3)}px;
                background: {INPUT_BORDER};
                border-radius: 1px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT};
                width: {self.dp(12)}px;
                border-radius: {self.dp(6)}px;
                margin: -{self.dp(5)}px 0;
            }}
            """
        )

    def update_progress_style(self, loading: bool = False) -> None:
        if self._progress_loading == loading:
            return
        self._progress_loading = loading
        chunk = LOADING_ACCENT if loading else ACCENT
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: {PANEL_SOFT};
                border: none;
                border-radius: 1px;
                margin: {self.dp(3)}px 0;
            }}
            QProgressBar::chunk {{
                background-color: {chunk};
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
            "lite": (214, 76),
            "standard": (246, 106),
            "detail": (342, 184),
        }
        min_sizes = {
            "lite": (196, 72),
            "standard": (228, 98),
            "detail": (316, 166),
        }
        min_w, min_h = min_sizes[level]
        self.setMinimumSize(self.dp(min_w), self.dp(min_h))
        if force_resize:
            width, height = sizes[level]
            self.resize_without_geometry_persist(self.dp(width), self.dp(height))

    def restore_geometry(self) -> None:
        window = self.config.get("window") or {}
        x = safe_int(window.get("x", 80), 80, 0)
        y = safe_int(window.get("y", 80), 80, 0)
        width = safe_int(window.get("width", self.width()), self.width(), self.minimumWidth())
        height = safe_int(window.get("height", self.height()), self.height(), self.minimumHeight())
        x, y, width, height = self.clamp_geometry(x, y, width, height)
        self.setGeometry(x, y, width, height)

    def resize_without_geometry_persist(self, width: int, height: int) -> None:
        x, y, width, height = self.clamp_geometry(self.x(), self.y(), width, height)
        old_state = self._suppress_geometry_persist
        self._suppress_geometry_persist = True
        try:
            self.setGeometry(x, y, width, height)
        finally:
            self._suppress_geometry_persist = old_state

    def clamp_geometry(self, x: int, y: int, width: int, height: int) -> tuple[int, int, int, int]:
        screen = self.available_geometry(QPoint(x, y))
        if screen is None:
            return x, y, width, height
        width = max(self.minimumWidth(), min(width, screen.width()))
        height = max(self.minimumHeight(), min(height, screen.height()))
        max_x = screen.left() + max(screen.width() - width, 0)
        max_y = screen.top() + max(screen.height() - height, 0)
        return (
            max(screen.left(), min(x, max_x)),
            max(screen.top(), min(y, max_y)),
            width,
            height,
        )

    def available_geometry(self, point: QPoint | None = None) -> Any:
        screen_obj = None
        if point is not None and hasattr(QApplication, "screenAt"):
            screen_obj = QApplication.screenAt(point)
        if screen_obj is None and hasattr(self, "screen"):
            screen_obj = self.screen()
        if screen_obj is None:
            screen_obj = QApplication.primaryScreen()
        if screen_obj is None:
            return None
        return screen_obj.availableGeometry()

    def on_opacity_changed(self, value: int) -> None:
        self.bg_opacity = value
        self.update_style(self.underMouse())

    def update_header_positions(self, hovered: bool) -> None:
        width = self.right_container.width()
        self.btn_settings.move(max(width - self.dp(40), 0), self.dp(3))
        self.btn_close.move(max(width - self.dp(18), 0), self.dp(3))
        self.btn_settings.setVisible(hovered)
        self.btn_close.setVisible(hovered)
        self.status_label.adjustSize()
        reserved = self.dp(45) if hovered else 0
        target_x = max(width - reserved - self.status_label.width(), 0)
        if self._header_target_x == target_x:
            return
        self._header_target_x = target_x
        self.header_anim.stop()
        self.header_anim.setStartValue(self.status_label.pos())
        self.header_anim.setEndValue(QPoint(int(target_x), 0))
        if abs(self.status_label.x() - target_x) <= 1:
            self.status_label.move(int(target_x), 0)
        else:
            self.header_anim.start()

    def toggle_config(self) -> None:
        if self._is_config:
            self.view_stack.setCurrentIndex(0)
            self.btn_settings.setText("...")
            self._is_config = False
            self.apply_display_level(force_resize=False)
            self.restore_monitor_geometry()
        else:
            self.show_config()

    def restore_monitor_geometry(self) -> None:
        if self._monitor_geometry:
            x, y, width, height = self._monitor_geometry
            x, y, width, height = self.clamp_geometry(x, y, width, height)
            old_state = self._suppress_geometry_persist
            self._suppress_geometry_persist = True
            try:
                self.setGeometry(x, y, width, height)
            finally:
                self._suppress_geometry_persist = old_state
        else:
            self.apply_display_level(force_resize=True)

    def show_config(self) -> None:
        if not self._is_config:
            geom = self.geometry()
            self._monitor_geometry = (geom.x(), geom.y(), geom.width(), geom.height())
        self._is_config = True
        self.view_stack.setCurrentIndex(1)
        self.btn_settings.setText("<")
        self.setMinimumSize(self.dp(380), self.dp(410))
        self.resize_without_geometry_persist(max(self.width(), self.dp(430)), max(self.height(), self.dp(520)))
        self.show_window()

    def show_first_run_config(self) -> None:
        self.show_config()
        self.config_msg.setStyleSheet(f"font-size: {self.dp(9)}px; color: {ACCENT}; font-weight: 700;")
        self.config_msg.setText("Set wallet, pool, miner and price source, then save.")

    def show_window(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def save_config_action(self) -> None:
        miner = self.input_miner.text().strip()
        error = miner_address_error(miner)
        if error:
            self.config_msg.setText(error)
            return
        proxy_enabled = self.combo_proxy.currentText() == "enabled"
        proxy_url = self.input_proxy.text().strip()
        if proxy_enabled and proxy_url:
            try:
                proxy_url = normalize_http_url(proxy_url)
            except ApiError:
                self.config_msg.setText("Proxy must be an http(s) URL")
                return

        cfg = copy.deepcopy(self.config)
        cfg["miner_address"] = miner
        cfg["selected_pool"] = self.combo_pool.currentText()
        cfg["selected_mining_software"] = self.combo_mining_software.currentText()
        cfg["selected_market_source"] = self.combo_market_source.currentText()
        cfg.setdefault("display", {})["level"] = self.combo_level.currentText()
        cfg["display"]["currency"] = self.combo_currency.currentText()
        cfg["display"]["configured"] = True
        cfg.setdefault("proxy", {})["enabled"] = proxy_enabled
        cfg["proxy"]["url"] = proxy_url
        cfg["proxy"]["use_env"] = True

        calc = cfg.setdefault("calculation", {})
        calc["hashrate_mode"] = self.combo_hashrate.currentText()
        calc["fee_mode"] = self.combo_fee_mode.currentText()
        calc["fee_override_percent"] = safe_float(self.input_fee.text(), float(calc.get("fee_override_percent", 3.0)))
        calc["tool_fee_mode"] = self.combo_tool_fee_mode.currentText()
        calc["tool_fee_percent"] = safe_float(self.input_tool_fee.text(), float(calc.get("tool_fee_percent", 0.0)))
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
        self._first_run = False
        self.display_level = clean_level((cfg.get("display") or {}).get("level"))
        self.currency = display_currency(cfg)
        self.intervals = {source: refresh_seconds(cfg, f"{source}_seconds") for source in SOURCE_FIELDS}
        self.loading = True
        self.loading_sources = ["miner", "pool", "market"]
        self.tick_timer.start(refresh_seconds(cfg, "ui_tick_seconds") * 1000)
        if self.worker:
            self.worker.update_config(copy.deepcopy(cfg))
        self.config_msg.setText("")
        self.toggle_config()

    def capture_geometry(self, cfg: dict[str, Any] | None = None) -> None:
        target = cfg if cfg is not None else self.config
        if self._is_config and self._monitor_geometry:
            x, y, width, height = self._monitor_geometry
        else:
            geom = self.geometry()
            x, y, width, height = geom.x(), geom.y(), geom.width(), geom.height()
        window = target.setdefault("window", {})
        window["x"] = x
        window["y"] = y
        window["width"] = width
        window["height"] = height
        window["alpha"] = self.bg_opacity / 255.0

    def persist_geometry(self) -> None:
        self.capture_geometry(self.config)
        save_config(self.config, CONFIG_PATH)

    def schedule_geometry_persist(self) -> None:
        if self._suppress_geometry_persist or self._is_config or not self.isVisible():
            return
        self.geometry_save_timer.start(350)

    @pyqtSlot(object)
    def on_data_updated(self, data: dict[str, Any]) -> None:
        if data.get("loading"):
            self.loading = True
            self.loading_sources = [str(source) for source in data.get("sources", [])]
            self.last_updates = data.get("last_updates") or self.last_updates
            self.intervals = data.get("intervals") or self.intervals
            self.animate_loading()
            return
        estimate = data.get("estimate")
        if not isinstance(estimate, ProfitEstimate):
            return
        self.loading = False
        self.update_progress_style(False)
        self.progress_bar.setRange(0, 86400)
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
        self.amount_label.set_target(self.primary_amount(usd, cny))
        self.amount_label.step()
        self.sub_label.setText(self.secondary_amount(usd, cny, prl))
        elapsed, _ = seconds_today()
        self.progress_bar.setValue(int(elapsed))
        self.left_metric.setText(format_hps(estimate.hashrate_hps))
        self.right_metric.setText(
            f"${estimate.price_usd:.6f} {estimate.price_source}  pool {estimate.fee_percent:.2f}%  tool {estimate.tool_fee_percent:.2f}%"
        )
        status = "ERR" if estimate.errors else estimate.computed_at.strftime("%H:%M:%S")
        if self.loading:
            status = self.loading_status()
        self.status_label.setText(status)
        self.status_label.adjustSize()
        self.update_header_positions(self.underMouse())
        self.update_detail_text(estimate)

    def animate_loading(self) -> None:
        if not self.loading:
            return
        self.loading_phase = (self.loading_phase + 1) % 100
        text = self.loading_text()
        if self.last_estimate is None:
            self.amount_label.set_target(text)
            self.amount_label.step()
            self.sub_label.setText("")
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(self.loading_phase)
            self.update_progress_style(True)
        self.status_label.setText(text)
        self.status_label.adjustSize()
        self.update_header_positions(self.underMouse())

    def loading_status(self) -> str:
        return self.loading_text()

    def loading_text(self) -> str:
        dots = "." * ((self.loading_phase // 8) % 4)
        return f"syncing {dots:<3}"

    def primary_amount(self, usd: float, cny: float) -> str:
        if self.currency == "cny":
            return f"CNY {cny:.6f}"
        return f"${usd:.6f}"

    def secondary_amount(self, usd: float, cny: float, prl: float) -> str:
        if self.currency == "cny":
            return f"${usd:.6f} | {prl:.6f} PRL"
        return f"CNY {cny:.6f} | {prl:.6f} PRL"

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
            f"fees pool {estimate.fee_percent:.2f}% | tool {estimate.tool_fee_percent:.2f}%\n"
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
            self._dragging = True

    def mouseMoveEvent(self, event: Any) -> None:
        if event.buttons() == LEFT_BUTTON and self._dragging:
            current = self.event_global_pos(event)
            delta = current - self.old_pos
            new_pos = self.pos() + delta
            screen = self.available_geometry(current)
            if screen is not None:
                new_pos.setX(max(screen.left(), min(new_pos.x(), screen.right() - self.width())))
                new_pos.setY(max(screen.top(), min(new_pos.y(), screen.bottom() - self.height())))
            self.move(new_pos)
            self.old_pos = current

    def mouseReleaseEvent(self, event: Any) -> None:
        if event.button() == LEFT_BUTTON and self._dragging:
            self._dragging = False
            self.schedule_geometry_persist()
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        self.sizegrip.move(self.width() - self.dp(14), self.height() - self.dp(14))
        self.update_header_positions(self.underMouse())
        self.schedule_geometry_persist()

    def on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (TRAY_TRIGGER, TRAY_DOUBLE_CLICK):
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

    def shutdown(self) -> None:
        self.geometry_save_timer.stop()
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
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
    if QApplication.instance() is None:
        configure_high_dpi()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = PRLTodayWindow(config)
    app.aboutToQuit.connect(window.shutdown)
    window.show()
    if hasattr(app, "exec"):
        sys.exit(app.exec())
    sys.exit(app.exec_())
