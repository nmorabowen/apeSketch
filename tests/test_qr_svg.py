"""QR SVG pairing helper tests."""

from __future__ import annotations

import pytest

from apeSketch.errors import DocumentError
from apeSketch.host.qr_svg import board_qr_svg


def test_board_qr_svg_contains_svg_root() -> None:
    try:
        svg = board_qr_svg("http://192.168.1.10:9968/")
    except DocumentError:
        pytest.skip("segno not installed")
    assert "<svg" in svg
    # QR payload is rendered as modules; the plaintext URL need not appear.
    assert len(svg) > 100
