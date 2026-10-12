# PlanStride brand

Open [`index.html`](index.html) in a browser for the brand sheet: every asset
on light and dark, at every size.

## Name and promise

**PlanStride.** A stride is one confident step at a steady pace, the weekly
rhythm the product builds. "Plan" says what it is; "Stride" says what it
promises.

- **One line:** PlanStride helps engineering team leads turn every engineer's
  Monday plan into a Friday result: one thing to ship, checked by AI before you
  approve it, tracked through the week.
- **Tagline:** Monday plans. Friday results.
- **Voice:** concrete and plain. Say what will be true on Friday, the way a good
  plan does. Never "unlock", "supercharge" or "empower".

## The mark: two strides

A check mark split where it bends. The short mint step stands for the
sub-goals; the long white stride is the one thing that ships. It reads as a
plain check at 16px and as two strides from 32px up. The green tile carries its
own colors, so the mark works on light and dark backgrounds without a variant.

| File | Use |
| --- | --- |
| `logomark.svg` | The mark on its own (64×64) |
| `favicon.svg` | Browser tab icon (the same mark); `favicon.ico` (16/32/48) and `apple-touch-icon.png` (180) live in each app's `public/` |
| `wordmark.svg` | "PlanStride" outlined from Geist SemiBold, tracked -2% |
| `logo.svg` / `logo-dark.svg` | Lockup for light and dark backgrounds |
| `banner-light.svg` / `banner-dark.svg` | README banner |
| `og-image.html` | Source of `site/public/og-image.png` (1200×630) |

In the apps, `Logo` and `Logomark` (`src/components/Logo.tsx`) draw the same
geometry inline; the wordmark there follows `currentColor`.

Rules: keep the tile's colors and corner radius; give the lockup clear space
equal to the mark's stroke width (9 units at 64); don't recolor the strides,
add effects, or set the wordmark in a live font.

## Color

| Token | Hex | Use |
| --- | --- | --- |
| Stride green | `#059669` | The mark's tile; brand accents |
| Deep green | `#047857` | Primary buttons and links on light (white text, 5.5:1) |
| Bright green | `#34D399` | Primary on dark |
| Mint | `#A7F3D0` | The mark's short stride; tints |
| Ink | `#0F1B16` | Wordmark and text on light |
| Paper | `#F6F8F7` | Marketing backgrounds |

In the product, status colors carry meaning and nothing else: sky = awaiting
approval, emerald = approved / shipped, amber = returned or needs attention,
rose = didn't ship. They're always paired with a label. The internal console
adds amber as its "internal" marker.

## Type

Geist (variable, self-hosted via `@fontsource-variable/geist`) for everything,
including the wordmark. Geist Mono only for code and the INTERNAL tag.

## Regenerating assets

The SVGs are written from one set of geometry, so the mark and lockups never
drift. To re-render the social card after a copy change:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --hide-scrollbars --force-device-scale-factor=1 --window-size=1200,630 \
  --allow-file-access-from-files \
  --screenshot="$PWD/site/public/og-image.png" "file://$PWD/branding/og-image.html"
```
