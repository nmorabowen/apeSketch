# Logo kit

Canonical brand assets for apeSketch. Source lockup: Archivo Narrow stacked plate.

Rebuild from `assets/logo-fonts/lockup-archivo-narrow.png`:

```bash
python assets/logo/build.py
```

## Palette

| Token | Hex |
|---|---|
| Paper | `#f4f0e6` |
| Ink | `#101820` |
| Navy | `#0b2540` |
| Cream | `#f4eee1` |
| Accent | `#c64a1a` |

CSS: [`tokens.css`](tokens.css). Typeface: Archivo Narrow Bold in [`fonts/`](fonts/).

## Files

| File | Use |
|---|---|
| `lockup-stacked.png` | README, splash, print |
| `lockup-stacked-dark.png` | Dark splash |
| `lockup-stacked-transparent.png` | Overlay on paper |
| `lockup-horizontal.png` | Headers, GitHub social |
| `lockup-horizontal-dark.png` | Dark headers |
| `mark.png` | App icon, avatar |
| `mark-dark.png` | Dark icon |
| `mark-transparent.png` | Overlay mark |
| `wordmark.png` / `wordmark.svg` | Text-only |
| `favicon.ico` | Browser tab (16/32/48) |
| `favicon-16.png` / `32` / `48` | PNG favicons |
| `apple-touch-icon.png` | iOS 180 |
| `icon-192.png` / `icon-512.png` | PWA / Android |
| `icon-maskable-512.png` | Maskable PWA |
| `og.png` | Open Graph 1200×630 |
| `social-square.png` | Square share 1080 |

Host copies live in `src/apeSketch/host/static/` and are served as `/favicon.ico`, `/apple-touch-icon.png`, and `/brand/<file>`.
