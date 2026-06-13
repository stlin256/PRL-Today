from __future__ import annotations

import html
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import PROJECT_ROOT


APP_NAME = "PRL-Today"
WINDOWS_STARTUP_FILE = "PRL-Today.bat"
MACOS_LAUNCH_AGENT = "com.stlin256.prltoday.plist"
LINUX_DESKTOP_FILE = "prl-today.desktop"


class StartupError(RuntimeError):
    pass


@dataclass(frozen=True)
class LaunchCommand:
    executable: Path
    args: tuple[str, ...]
    cwd: Path


def startup_supported(platform: str | None = None) -> bool:
    platform = platform or sys.platform
    return platform.startswith("win") or platform == "darwin" or platform.startswith("linux")


def startup_entry_path(platform: str | None = None) -> Path | None:
    platform = platform or sys.platform
    if platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            return None
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / WINDOWS_STARTUP_FILE
    if platform == "darwin":
        return Path.home() / "Library" / "LaunchAgents" / MACOS_LAUNCH_AGENT
    if platform.startswith("linux"):
        return Path.home() / ".config" / "autostart" / LINUX_DESKTOP_FILE
    return None


def launch_command(
    *,
    executable: Path | None = None,
    project_root: Path | None = None,
    frozen: bool | None = None,
    platform: str | None = None,
) -> LaunchCommand:
    executable = Path(executable or sys.executable).resolve()
    project_root = Path(project_root or PROJECT_ROOT).resolve()
    frozen = bool(getattr(sys, "frozen", False) if frozen is None else frozen)
    platform = platform or sys.platform
    if frozen:
        return LaunchCommand(executable=executable, args=(), cwd=executable.parent)
    if platform.startswith("win") and executable.name.lower() == "python.exe":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            executable = pythonw
    return LaunchCommand(executable=executable, args=(str(project_root / "run.py"),), cwd=project_root)


def is_startup_enabled(platform: str | None = None) -> bool:
    path = startup_entry_path(platform)
    return bool(path and path.exists())


def set_startup_enabled(enabled: bool, platform: str | None = None) -> None:
    platform = platform or sys.platform
    path = startup_entry_path(platform)
    if path is None or not startup_supported(platform):
        raise StartupError("Startup is not supported on this platform")
    if enabled:
        command = launch_command(platform=platform)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(startup_file_content(command, platform), encoding="utf-8")
        except OSError as exc:
            raise StartupError(f"Unable to create startup entry: {exc}") from exc
        return
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise StartupError(f"Unable to remove startup entry: {exc}") from exc


def startup_file_content(command: LaunchCommand, platform: str | None = None) -> str:
    platform = platform or sys.platform
    if platform.startswith("win"):
        return windows_batch_content(command)
    if platform == "darwin":
        return macos_plist_content(command)
    if platform.startswith("linux"):
        return linux_desktop_content(command)
    raise StartupError("Startup is not supported on this platform")


def windows_batch_content(command: LaunchCommand) -> str:
    args = " ".join(windows_quote(arg) for arg in command.args)
    command_line = f"start \"\" {windows_quote(str(command.executable))}"
    if args:
        command_line = f"{command_line} {args}"
    return f"@echo off\r\ncd /d {windows_quote(str(command.cwd))}\r\n{command_line}\r\n"


def windows_quote(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) + chr(34))}"'


def macos_plist_content(command: LaunchCommand) -> str:
    arguments = [str(command.executable), *command.args]
    argument_xml = "\n".join(f"    <string>{html.escape(arg, quote=True)}</string>" for arg in arguments)
    cwd = html.escape(str(command.cwd), quote=True)
    label = html.escape(MACOS_LAUNCH_AGENT.removesuffix(".plist"), quote=True)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "  <key>Label</key>\n"
        f"  <string>{label}</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array>\n"
        f"{argument_xml}\n"
        "  </array>\n"
        "  <key>WorkingDirectory</key>\n"
        f"  <string>{cwd}</string>\n"
        "  <key>RunAtLoad</key>\n"
        "  <true/>\n"
        "</dict>\n"
        "</plist>\n"
    )


def linux_desktop_content(command: LaunchCommand) -> str:
    exec_line = " ".join(shlex.quote(part) for part in [str(command.executable), *command.args])
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f"Exec={exec_line}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
