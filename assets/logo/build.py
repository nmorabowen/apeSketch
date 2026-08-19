"""Build the apeSketch logo kit from the Archivo Narrow lockup."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "logo-fonts" / "lockup-archivo-narrow.png"
FONT = ROOT / "assets" / "logo-fonts" / "_fonts" / "ArchivoNarrow-Bold.ttf"
OUT = Path(__file__).resolve().parent
STATIC = ROOT / "src" / "apeSketch" / "host" / "static"

PAPER = (244, 240, 230)
INK = (16, 24, 32)
TERRACOTTA = (198, 74, 26)
NAVY = (11, 37, 64)
CREAM = (244, 238, 225)


def _is_paper(c: tuple[int, ...], tol: int = 22) -> bool:
    return all(abs(int(c[i]) - PAPER[i]) < tol for i in range(3))


def _content_bbox(im: Image.Image, *, sample: int = 4, pad: int = 24) -> tuple[int, int, int, int]:
    px = im.load()
    w, h = im.size
    xs, ys = [], []
    for y in range(0, h, sample):
        for x in range(0, w, sample):
            if not _is_paper(px[x, y]):
                xs.append(x)
                ys.append(y)
    if not xs:
        return (0, 0, w, h)
    return (
        max(0, min(xs) - pad),
        max(0, min(ys) - pad),
        min(w, max(xs) + pad),
        min(h, max(ys) + pad),
    )


def crop_mark(lockup: Image.Image) -> Image.Image:
    """Square crop around the terracotta construction circle — no wordmark."""
    px = lockup.load()
    w, h = lockup.size
    xs: list[int] = []
    ys: list[int] = []
    for y in range(0, int(h * 0.55), 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y][:3]
            if r > 140 and r > g + 40 and r > b + 40 and g < 140 and b < 110:
                xs.append(x)
                ys.append(y)
    if len(xs) < 80:
        plate = lockup.crop((0, 0, w, int(h * 0.52)))
        return plate.crop(_content_bbox(plate, pad=20))
    pad = 18
    x0, y0 = max(0, min(xs) - pad), max(0, min(ys) - pad)
    x1, y1 = min(w, max(xs) + pad), min(h, max(ys) + pad)
    side = max(x1 - x0, y1 - y0)
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    x0 = max(0, cx - side // 2)
    y0 = max(0, cy - side // 2)
    x1 = min(w, x0 + side)
    y1 = min(h, y0 + side)
    return lockup.crop((x0, y0, x1, y1))


def to_transparent(im: Image.Image, *, tol: int = 18) -> Image.Image:
    rgba = im.convert("RGBA")
    pix = list(rgba.getdata())
    out = []
    for r, g, b, a in pix:
        if _is_paper((r, g, b), tol=tol):
            dist = max(abs(r - PAPER[0]), abs(g - PAPER[1]), abs(b - PAPER[2]))
            alpha = 0 if dist < tol - 6 else int(a * (dist - (tol - 6)) / 6)
            out.append((r, g, b, max(0, min(255, alpha))))
        else:
            out.append((r, g, b, a))
    rgba.putdata(out)
    return rgba


def to_dark(im: Image.Image) -> Image.Image:
    rgb = im.convert("RGB")
    px = rgb.load()
    w, h = rgb.size
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if _is_paper((r, g, b), tol=28):
                px[x, y] = NAVY
            elif r < 55 and g < 55 and b < 62:
                px[x, y] = CREAM
    return rgb.convert("RGBA")


def fit_square(im: Image.Image, size: int, *, bg: tuple[int, int, int] | None) -> Image.Image:
    src = im.convert("RGBA")
    scale = min(size / src.width, size / src.height)
    nw, nh = max(1, int(src.width * scale)), max(1, int(src.height * scale))
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    if bg is None:
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    else:
        canvas = Image.new("RGBA", (size, size), bg + (255,))
    canvas.alpha_composite(resized, ((size - nw) // 2, (size - nh) // 2))
    return canvas


def circular_icon(mark: Image.Image, size: int, *, bg: tuple[int, int, int]) -> Image.Image:
    square = fit_square(mark, size, bg=bg)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((1, 1, size - 2, size - 2), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(square, mask=mask)
    return out


def save_rgb(im: Image.Image, path: Path) -> None:
    im.convert("RGB").save(path, "PNG", optimize=True)


def save_rgba(im: Image.Image, path: Path) -> None:
    im.save(path, "PNG", optimize=True)


def tracked(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill, tracking: int) -> int:
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        box = draw.textbbox((x, y), ch, font=font)
        x = box[2] + tracking
    return x


def horizontal_lockup(mark: Image.Image, *, dark: bool) -> Image.Image:
    bg = NAVY if dark else PAPER
    ink = CREAM if dark else INK
    W, H = 1600, 520
    canvas = Image.new("RGBA", (W, H), bg + (255,))
    mark_h = 380
    m = mark.copy()
    scale = mark_h / m.height
    m = m.resize((int(m.width * scale), mark_h), Image.Resampling.LANCZOS)
    canvas.alpha_composite(m, (48, (H - m.height) // 2))
    draw = ImageDraw.Draw(canvas)
    word = ImageFont.truetype(str(FONT), 118)
    tag = ImageFont.truetype(str(FONT), 22)
    tx = 48 + m.width + 36
    ty = (H - 118) // 2 - 12
    draw.text((tx, ty), "apeSketch", font=word, fill=ink)
    tracked(draw, (tx, ty + 132), "INK BRIDGE", tag, TERRACOTTA, 10)
    return canvas


def og_image(mark: Image.Image) -> Image.Image:
    W, H = 1200, 630
    canvas = Image.new("RGBA", (W, H), PAPER + (255,))
    m = mark.copy()
    scale = 420 / m.height
    m = m.resize((int(m.width * scale), 420), Image.Resampling.LANCZOS)
    canvas.alpha_composite(m, (64, (H - m.height) // 2))
    draw = ImageDraw.Draw(canvas)
    word = ImageFont.truetype(str(FONT), 96)
    tag = ImageFont.truetype(str(FONT), 22)
    sub = ImageFont.truetype(str(FONT), 28)
    tx = 64 + m.width + 28
    draw.text((tx, 210), "apeSketch", font=word, fill=INK)
    tracked(draw, (tx, 330), "INK BRIDGE", tag, TERRACOTTA, 10)
    draw.text((tx, 380), "Hand-ink bridge for the ape* toolchain", font=sub, fill=(80, 84, 88))
    return canvas


def wordmark_png(*, dark: bool) -> Image.Image:
    bg = NAVY if dark else PAPER
    ink = CREAM if dark else INK
    font = ImageFont.truetype(str(FONT), 160)
    tmp = Image.new("RGB", (8, 8))
    d = ImageDraw.Draw(tmp)
    box = d.textbbox((0, 0), "apeSketch", font=font)
    w, h = box[2] - box[0] + 48, box[3] - box[1] + 48
    im = Image.new("RGBA", (w, h), bg + (255,))
    ImageDraw.Draw(im).text((24 - box[0], 24 - box[1]), "apeSketch", font=font, fill=ink)
    return im


def write_tokens_css(path: Path) -> None:
    path.write_text(
        """/* apeSketch brand tokens — from assets/logo */\n"""
        """:root {\n"""
        """  --ape-paper: #f4f0e6;\n"""
        """  --ape-paper-alt: #ede7d6;\n"""
        """  --ape-ink: #101820;\n"""
        """  --ape-cream: #f4eee1;\n"""
        """  --ape-navy: #0b2540;\n"""
        """  --ape-accent: #c64a1a;\n"""
        """  --ape-muted: rgba(16, 24, 32, 0.55);\n"""
        """  --ape-hair: rgba(16, 24, 32, 0.18);\n"""
        """}\n""",
        encoding="utf-8",
    )


def write_wordmark_svg(path: Path) -> None:
    path.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 120" role="img" aria-label="apeSketch">
  <title>apeSketch</title>
  <text x="0" y="86" fill="#101820"
        font-family="Archivo Narrow, Arial Narrow, sans-serif"
        font-weight="700" font-size="92" letter-spacing="-1.5">apeSketch</text>
</svg>
""",
        encoding="utf-8",
    )


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing lockup: {SRC}")
    if not FONT.exists():
        raise SystemExit(f"missing Archivo Narrow: {FONT}")
    OUT.mkdir(parents=True, exist_ok=True)

    lockup = Image.open(SRC).convert("RGBA")
    mark = crop_mark(lockup)
    lockup_trim = lockup.crop(_content_bbox(lockup, pad=40))
    mark_t = to_transparent(mark)
    lockup_t = to_transparent(lockup_trim)
    mark_dark = to_dark(mark)
    lockup_dark = to_dark(lockup_trim)

    shutil.copyfile(SRC, OUT / "lockup-stacked.png")
    save_rgba(fit_square(lockup_t, 1600, bg=None), OUT / "lockup-stacked-transparent.png")
    save_rgb(fit_square(lockup_dark, 1600, bg=NAVY), OUT / "lockup-stacked-dark.png")

    save_rgb(fit_square(mark, 1024, bg=PAPER), OUT / "mark.png")
    save_rgba(fit_square(mark_t, 1024, bg=None), OUT / "mark-transparent.png")
    save_rgb(fit_square(mark_dark, 1024, bg=NAVY), OUT / "mark-dark.png")

    save_rgb(horizontal_lockup(mark, dark=False), OUT / "lockup-horizontal.png")
    save_rgb(horizontal_lockup(mark_dark, dark=True), OUT / "lockup-horizontal-dark.png")

    save_rgb(wordmark_png(dark=False), OUT / "wordmark.png")
    save_rgb(wordmark_png(dark=True), OUT / "wordmark-dark.png")
    write_wordmark_svg(OUT / "wordmark.svg")

    # Icons
    for size, name in ((16, "favicon-16.png"), (32, "favicon-32.png"), (48, "favicon-48.png")):
        save_rgb(fit_square(mark, size, bg=PAPER), OUT / name)
    apple = fit_square(mark, 180, bg=PAPER)
    save_rgb(apple, OUT / "apple-touch-icon.png")
    save_rgb(fit_square(mark, 192, bg=PAPER), OUT / "icon-192.png")
    save_rgb(fit_square(mark, 512, bg=PAPER), OUT / "icon-512.png")
    save_rgba(circular_icon(mark, 512, bg=PAPER), OUT / "icon-maskable-512.png")

    fit_square(mark, 256, bg=PAPER).save(
        OUT / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )

    save_rgb(og_image(mark), OUT / "og.png")
    save_rgb(fit_square(lockup, 1080, bg=PAPER), OUT / "social-square.png")

    write_tokens_css(OUT / "tokens.css")
    (OUT / "fonts").mkdir(exist_ok=True)
    shutil.copyfile(FONT, OUT / "fonts" / "ArchivoNarrow-Bold.ttf")

    # Host static copies
    STATIC.mkdir(parents=True, exist_ok=True)
    for name in (
        "favicon.ico",
        "favicon-32.png",
        "apple-touch-icon.png",
        "icon-192.png",
        "icon-512.png",
        "mark.png",
        "mark-dark.png",
        "lockup-horizontal.png",
        "og.png",
        "tokens.css",
        "wordmark.svg",
    ):
        shutil.copyfile(OUT / name, STATIC / name)
    (STATIC / "fonts").mkdir(exist_ok=True)
    shutil.copyfile(FONT, STATIC / "fonts" / "ArchivoNarrow-Bold.ttf")
    # Header mark at UI size
    save_rgb(fit_square(mark, 80, bg=PAPER), STATIC / "logo-mark.png")
    save_rgba(fit_square(mark_t, 80, bg=None), STATIC / "logo-mark-transparent.png")
    save_rgb(fit_square(mark, 336, bg=PAPER), STATIC / "mark.png")

    print("wrote", OUT)
    print("copied into", STATIC)


if __name__ == "__main__":
    main()
