from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.package_release import normalized_arch, normalized_platform, package_artifact


class ReleasePackagingTest(unittest.TestCase):
    def test_normalizes_platform_and_arch_labels(self) -> None:
        self.assertEqual(normalized_platform("win32"), "windows")
        self.assertEqual(normalized_platform("darwin"), "macos")
        self.assertEqual(normalized_platform("linux"), "linux")
        self.assertEqual(normalized_arch("x86_64"), "x64")
        self.assertEqual(normalized_arch("aarch64"), "arm64")

    def test_packages_windows_exe_as_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "dist"
            output = root / "release"
            dist.mkdir()
            exe = dist / "PRL-Today.exe"
            exe.write_bytes(b"fake exe")

            archive = package_artifact(dist, output, "windows", "x64")

            self.assertEqual(archive.name, "PRL-Today-windows-x64.zip")
            self.assertTrue(archive.exists())
            with zipfile.ZipFile(archive) as zf:
                self.assertEqual(zf.namelist(), ["PRL-Today.exe"])


if __name__ == "__main__":
    unittest.main()
