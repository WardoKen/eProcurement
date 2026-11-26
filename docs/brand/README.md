# eProcure logo kit (Concept C, "Scan-line e")

> **Installed.** The favicons are in `public/`, `index.html` links them, and
> `BrandMark` in `src/components/Sidebar.jsx` is the new mark (top bar,
> sidebar and footer). This folder keeps the source SVGs and the PNGs for
> documents and slides. The steps under "Putting it in the repo" are done.

The colors and font come from the eProcure "Line" design system (`DESIGN.md`, `src/styles/tokens.css`):

| Part | Light | Dark |
|---|---|---|
| Mark ("e" and corners), "e" in the wordmark | jade `#006D4F` | jade `#4FC39C` |
| Scan line | marigold `#F9BC38` | marigold `#F9BC38` |
| "Procure" | ink `#13201B` | ink `#E6EDEA` |
| App icon / favicon ground | jade `#006D4F`, mark in paper `#F8FBF9` | same |

The wordmark uses Archivo at weight 820, width 118 and −0.03em tracking, the same as `.topbar-name`.
The text in the SVG logos is converted to outlines, so the font doesn't need to be installed.

## What's inside

| File | Use |
|---|---|
| `svg/eprocure-logo.svg` | Full logo on light backgrounds: login page, reports, RFQ/PDF header |
| `svg/eprocure-logo-dark.svg` | Full logo on dark-mode backgrounds |
| `svg/eprocure-mark.svg` / `-dark.svg` | Mark only, transparent background |
| `svg/eprocure-app-icon.svg` | Jade rounded-square icon |
| `png/logo/` | Full logo PNGs, 120 / 240 / 480 px tall (Word docs, slides, defense deck) |
| `png/mark/` | Mark PNGs, 16 to 1024 px, transparent |
| `png/app-icon/` | App icon PNGs, 64 to 1024 px |
| `favicon/` | Browser tab, phone home screen and PWA icons + `site.webmanifest` |
| `BrandMark.jsx` | Drop-in replacement for the `BrandMark` in `src/components/Sidebar.jsx` |

## Putting it in the repo

1. **Favicon.** Your `public/` currently holds the BSIT seal (`favicon.ico`, `favicon.png`, `favicon.svg`). Replace those with everything in `favicon/` (copy all nine files into `public/`). The root `favicon/` folder holds the same seal and can be deleted.
2. **`index.html`.** Replace the single `<link rel="icon" …>` line with:

```html
<link rel="icon" href="/favicon.ico" sizes="48x48" />
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
<link rel="manifest" href="/site.webmanifest" />
```

   Your `theme-color` is already `#006D4F`.

3. **Top bar.** Replace `BrandMark` in `src/components/Sidebar.jsx` with the one in `BrandMark.jsx`. It reads `--jade`, `--on-jade` and `--marigold`, so it follows the theme toggle.
4. **Anywhere else** (login split page, landing):

```jsx
import logo from "./assets/eprocure-logo.svg";
import logoDark from "./assets/eprocure-logo-dark.svg";
```

The favicon and `BrandMark` leave out the corner brackets so the "e" stays readable at 16 to 32 px. Every larger size keeps them.
