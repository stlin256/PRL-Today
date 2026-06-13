from __future__ import annotations

import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG file")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


class AssetTest(unittest.TestCase):
    def test_prl_logo_has_high_dpi_headroom(self) -> None:
        width, height = png_size(ROOT / "assets" / "prl_logo.png")
        self.assertGreaterEqual(width, 900)
        self.assertGreaterEqual(height, 280)


if __name__ == "__main__":
    unittest.main()
