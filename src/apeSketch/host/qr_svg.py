"""QR helpers for LAN pairing (optional segno dependency)."""

from __future__ import annotations

from apeSketch.errors import DocumentError


def board_qr_svg(url: str, *, scale: int = 8, border: int = 2) -> str:
    """Return an SVG document for the board join URL."""
    try:
        import segno
    except ImportError as exc:
        raise DocumentError(
            "QR pairing requires segno. Install with: pip install apeSketch"
        ) from exc
    qr = segno.make(url, error="m")
    return qr.svg_inline(scale=scale, border=border, dark="#1a1a1a", light="#ffffff")
