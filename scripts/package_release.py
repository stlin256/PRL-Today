from __future__ import annotations

import argparse
import platform
import shutil
import sys
import tarfile
from pathlib import Path


PROJECT_NAME = "PRL-Today"


def normalized_platform(value: str | None = None) -> str:
    raw = (value or sys.platform).lower()
    if raw.startswith("win"):
        return "windows"
    if raw.startswith("darwin") or raw.startswith("mac"):
        return "macos"
    if raw.startswith("linux"):
        return "linux"
    return raw.replace(" ", "-")


def normalized_arch(value: str | None = None) -> str:
    raw = (value or platform.machine() or "unknown").lower()
    aliases = {
        "amd64": "x64",
        "x86_64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    return aliases.get(raw, raw.replace(" ", "-"))


def find_build_artifact(dist_dir: Path, platform_name: str) -> Path:
    candidates: list[Path]
    if platform_name == "windows":
        candidates = [dist_dir / f"{PROJECT_NAME}.exe"]
    elif platform_name == "macos":
        candidates = [dist_dir / f"{PROJECT_NAME}.app", dist_dir / PROJECT_NAME]
    else:
        candidates = [dist_dir / PROJECT_NAME, dist_dir / f"{PROJECT_NAME}.exe"]

    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit(f"Build artifact not found in {dist_dir}")


def zip_artifact(source: Path, target_base: Path) -> Path:
    archive = shutil.make_archive(str(target_base), "zip", source.parent, source.name)
    return Path(archive)


def targz_artifact(source: Path, target: Path) -> Path:
    with tarfile.open(target, "w:gz") as tar:
        tar.add(source, arcname=source.name)
    return target


def package_artifact(dist_dir: Path, output_dir: Path, platform_name: str, arch: str) -> Path:
    artifact = find_build_artifact(dist_dir, platform_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    target_base = output_dir / f"{PROJECT_NAME}-{platform_name}-{arch}"
    if platform_name == "windows":
        return zip_artifact(artifact, target_base)
    return targz_artifact(artifact, target_base.with_suffix(".tar.gz"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Package PyInstaller output for release upload.")
    parser.add_argument("--dist", default="dist", type=Path, help="PyInstaller dist directory.")
    parser.add_argument("--output", default="release", type=Path, help="Directory for packaged release archives.")
    parser.add_argument("--platform", default=None, help="Override platform label: windows, macos, or linux.")
    parser.add_argument("--arch", default=None, help="Override architecture label.")
    args = parser.parse_args()

    platform_name = normalized_platform(args.platform)
    arch = normalized_arch(args.arch)
    archive = package_artifact(args.dist, args.output, platform_name, arch)
    print(archive)


if __name__ == "__main__":
    main()
