# eProcure design system: Line

eProcure is the procurement portal of the Bids and Awards Committee (BAC) at
CTU Tuburan: the BAC Secretariat (Admin), End Users who submit Purchase
Requests, suppliers, and the public. This document is the visual identity
and the rules every screen follows. It replaces the earlier "docket" system.
The direction was chosen from three mockups in [`design-lab/`](design-lab/README.md).

## The idea

Procurement is a journey with fixed stations: a Purchase Request is
submitted, posted as an opportunity, sent out as RFQs, and answered with
quotations. Evaluation, award and the purchase order follow, but they are
out of eProcure's scope and happen outside the system. Staff ask one
question of every record: *where is it on the line, and is it waiting on me?*

So the product is built around **the line**: the four stations drawn like a
transit line. It is the largest element on the dashboard, the header of a
record, and a segmented strip in a table row. Everything else stays quiet
so the line, and the numbers on it, carry the page.

Four rules follow from that:

1. **Type leads.** Hierarchy comes from size, weight and width, not from
   boxes. Display text is wide and heavy; data is condensed and dense.
2. **Bands, not cards.** Sections are separated by rules and by a change of
   ground (paper to sunk), never by a grid of identical rounded boxes with
   shadows. Only things that float (dialogs, menus, the command palette)
   have a shadow.
3. **Two colors with jobs.** Jade is the institution and every primary
   action. Marigold is *now*: the current station, what is waiting on you,
   the focus ring. Neither is decoration.
4. **Dense where you work, open where you decide.** Tables and forms are
   tight. The headline, the line and the queue get generous space.

## Color

All colors are OKLCH, defined in `src/styles/tokens.css`. Hex values are
the sRGB equivalents, for reference.

### Light

| Token | OKLCH | Hex | Use |
|---|---|---|---|
| `--paper` | 0.985 0.004 165 | `#F8FBF9` | Page ground |
| `--surface` | 1 0 0 | `#FFFFFF` | Inputs, dialogs, table body |
| `--sunk` | 0.955 0.009 165 | `#EBF2EF` | Secondary bands, side columns, table header |
| `--rule` | 0.885 0.012 165 | `#D2DCD7` | Hairlines between rows and sections |
| `--input-line` | 0.62 0.02 170 | `#7B8A84` | Input and checkbox borders (3.5:1) |
| `--ink` | 0.23 0.02 170 | `#13201B` | Text, strong rules |
| `--ink-2` | 0.44 0.02 170 | `#485651` | Secondary text |
| `--ink-3` | 0.53 0.018 170 | `#626F6A` | Hints, placeholders |
| `--jade` | 0.47 0.105 168 | `#006D4F` | **Primary.** Buttons, the travelled line, selected states |
| `--jade-deep` | 0.36 0.085 168 | `#004B34` | Links, record numbers, hover on primary |
| `--jade-wash` | 0.945 0.03 168 | `#DBF4E9` | Selected rows, active nav ground |
| `--marigold` | 0.83 0.155 82 | `#F9BC38` | **Accent.** Current station, counts waiting on you, focus ring |
| `--marigold-ink` | 0.47 0.1 70 | `#7E4F04` | Marigold as text, for warning statuses |
| `--marigold-wash` | 0.95 0.05 90 | `#FBEEC9` | Warning status fill |
| `--danger` | 0.52 0.19 27 | `#BE2323` | Errors, rejection |
| `--info` | 0.48 0.09 235 | `#1C6589` | In-progress statuses only |

### Dark

Dark mode follows the system setting and can be overridden from the top bar
(stored per browser). It is not an inversion: the ground is a deep green
black, so jade reads as light emitted rather than paint, and marigold stays
the same hue so the current station is recognisable in both modes.

| Token | OKLCH | Hex |
|---|---|---|
| `--paper` | 0.195 0.012 170 | `#101714` |
| `--surface` | 0.225 0.013 170 | `#161E1B` |
| `--sunk` | 0.235 0.014 170 | `#18201D` |
| `--rule` | 0.34 0.015 170 | `#313B37` |
| `--ink` | 0.94 0.008 165 | `#E6EDEA` |
| `--ink-2` | 0.76 0.015 165 | `#A9B4AF` |
| `--ink-3` | 0.66 0.015 165 | `#8A9590` |
| `--jade` | 0.74 0.12 168 | `#4FC39C` (text on it is `--paper`) |
| `--jade-deep` | 0.8 0.11 168 | `#6FD5B0` |
| `--marigold` | 0.83 0.155 82 | `#F9BC38` |
| `--danger` | 0.72 0.15 27 | `#F47C70` |

### Contrast (WCAG 2.1 AA)

| Pair | Light | Dark |
|---|---|---|
| ink on paper | 16.1 | 15.3 |
| ink-2 on paper | 7.4 | 8.6 |
| ink-3 on paper / sunk | 5.0 / 4.6 | 5.9 |
| Text on jade button | 6.4 | 8.3 |
| jade-deep link on paper | 9.8 | 10.2 |
| ink on marigold | 9.8 | 10.7 |
| marigold-ink on marigold-wash | 6.0 | n/a |
| danger on paper | 5.8 | 6.9 |
| input-line on paper (non-text, 3:1 needed) | 3.5 | n/a |

### Status

Status is always text first, color second, with a dot before the label. It
is never a filled pastel pill.

| Tone | Statuses |
|---|---|
| neutral (`ink-2`) | Submitted, Draft, Not posted |
| info (`info`) | In review, Matched, Sent, Pending review |
| success (`jade`) | Posted, Quotation received, Approved, Completed |
| warning (`marigold-ink`) | For compliance, Awaiting quotation |
| danger (`danger`) | Rejected |

## Type

One variable family: **Archivo** (Google Fonts, `wdth` 62 to 125,
`wght` 100 to 900). One family keeps a 64px headline and a 13px table cell
recognisably the same product. The scale contrast comes from the width axis:

| Role | Size / line height | Width | Weight | Tracking |
|---|---|---|---|---|
| Display (dashboard headline, landing) | `clamp(44px, 6vw, 84px)` / 0.92 | 112 | 820 | -0.035em |
| Page title (`h1`) | `clamp(32px, 3.4vw, 44px)` / 1 | 110 | 780 | -0.025em |
| Section (`h2`) | 22px / 1.15 | 106 | 720 | -0.015em |
| Sub-section (`h3`) | 16px / 1.3 | 100 | 650 | 0 |
| Body | 15px / 1.5 | 100 | 400 | 0 |
| Data (tables, forms, meta) | 13.5px / 1.4 | 88 | 420 | 0 |
| Small | 12.5px / 1.4 | 92 | 450 | 0.005em |
| Station number | 48px / 1 | 118 | 800 | -0.03em |
| Queue number | 44px / 1 | 70 | 300 | -0.02em |

- Peso amounts, PR numbers and counts use `font-variant-numeric:
  tabular-nums`, right-aligned in tables.
- Two numeral voices: **wide and heavy** for where things are (stations),
  **condensed and light** for what is waiting (queues). They never swap.
- No all-caps labels, no letter-spaced eyebrows, no monospace for data.
- Sentence case everywhere. Procurement terms keep their capitals: PR, RFQ,
  ABC, BAC, PO, PhilGEPS.

## Layout

### Shell

```
┌────────────────────────────────────────────────────────────────────────┐
│ eProcure  BAC · Admin   [ Jump to a PR or supplier…  Ctrl K ]  ◐  User ⎋ │  top bar, 56px, paper
├────────────────────────────────────────────────────────────────────────┤
│ Overview │ Purchase requests ⁷  RFQs  Manual RFQs │ Suppliers  End users │ … │  index bar, rules between groups
├────────────────────────────────────────────────────────────────────────┤
│ content, max 1440px, 40px side margin (16px on phones)                   │
```

- **No sidebar.** The portal navigation is a horizontal index under the top
  bar, grouped by task with a rule between groups. The active item has a
  jade underline and ink text; a count waiting on you is a marigold numeral.
  This returns the full width to tables.
- Below 960px the index collapses into a drawer opened from the top bar.
- The public site uses the same top bar with its own links (Home,
  Opportunities, Help and FAQ) and a log in button.

### Grids

- Pages use a 12-column grid with a 32px gutter, but content is placed
  asymmetrically: **8/4** (work and context), **5/7** (headline and queue)
  or full bleed (the line, wide tables).
- Side columns sit on `--sunk` and run to the edge of their band instead of
  floating in a box.
- Text is left-aligned. Numbers are right-aligned. Nothing in the app is
  centred except empty states.

### Spacing

4px base: 4, 8, 12, 16, 24, 32, 48, 72. Table rows are 36px (compact) or
44px (comfortable). Bands are separated by 48 to 72px; items inside a band
by 8 to 16px. That jump is the point.

### Shape

| Element | Radius |
|---|---|
| Panels, bands, tables | 0 |
| Buttons, inputs, selects | 6px |
| Index tabs, segmented controls, density toggle | 999px (pill) |
| Dialogs, menus, command palette | 12px, with the only shadow in the system |

## The line (signature component)

`src/components/ui/PipelineLine.jsx`. Four stations, always in this order:

1. Purchase request
2. Posting
3. RFQ
4. Quotation

A station is **done** (jade ring, travelled jade track), **now** (marigold
ring with a soft halo, track ends here), **later** (rule-colored ring and
track) or **stopped** (danger ring, for a rejected PR). The line ends at
Quotation: evaluation, award and the purchase order are out of scope, so
they are not drawn.

| Variant | Where | Content |
|---|---|---|
| `overview` | Admin dashboard | Each station with its count (station-number style) and a short note |
| `record` | PR details, RFQ screens | Each station named, the current one with its state in words |
| `mini` | Table rows | One 16x4px segment per station, with the stage named in text next to it |

The stage of a PR comes from data already on the record: rejected stops at
the request; uploaded or in review is at the request; matched and not
posted is at posting; posted is at RFQ; RFQs sent are at quotation; every
RFQ answered, or a completed PR, is past all four.

The RFQ progress indicator (`ProcurementStepper`) uses the same ring and
track drawing for its three RFQ steps.

## Data

- **Tables** have a sticky header on `--sunk` with a 2px ink rule beneath,
  hairline rows, and a hover in `--jade-wash`. No zebra stripes, no outer
  border, no rounded corners.
- **Status is inline**: dot and label, and on PR rows the mini line.
- **Row expansion**: PR rows open in place to show the record line, the
  items and the next action, without leaving the list.
- **Density toggle** (Comfortable / Compact) in every table toolbar,
  remembered per browser. Compact is the default for the BAC.
- **Command palette** (Ctrl K or Cmd K, also the top bar search field):
  jump to any page, PR (by number, office or purpose) or supplier (by name
  or email). Arrow keys move, Enter opens, Escape closes. In the Supplier
  and End User portals it lists that portal's pages and records.

## Motion

- **Page changes** use the View Transitions API: the content area
  cross-fades and rises 8px (220ms). The top bar and index stay still.
- **One orchestrated entrance**: on the dashboard the line draws from left
  to right and the stations appear in sequence (60ms apart). Nothing else
  staggers.
- **Skeletons** for anything loading longer than a moment: blocks in
  `--sunk` with a slow sheen, shaped like the content they replace.
- Feedback motion only: dialogs scale in from 98%, rows expand with a
  height transition, the palette fades in.
- `prefers-reduced-motion: reduce` removes the transitions, the line
  animation and the sheen. Everything still appears, immediately.

## Removed on purpose

These made the earlier designs read as a template. They do not come back.

- Rows of identical rounded stat cards with soft shadows. Key figures are
  stations on the line or numbers in the queue.
- Pastel circles behind icons. Icons are 16px, ink-2, inline with text, and
  only where they help recognition.
- Gradient heroes and gradient washes.
- A centred "Welcome back" login on a plain background. Sign-in is a split
  page: the line and what eProcure does on one side, the form on the other.
- Emoji as icons.
- The navy masthead with a light sidebar.

## Accessibility

- Scrollbars are hidden across the app; areas still scroll by wheel,
  touch, trackpad and keyboard.

- WCAG 2.1 AA contrast for all text and controls (table above).
- Focus is a 2px marigold outline with a 2px offset plus an ink inner
  outline, visible on paper, jade and dark grounds alike.
- The line is a list with `aria-current="step"` on the current station and
  each station's state written out, so it never relies on color.
- Targets are at least 36px tall (44px on touch widths).
- The layout works from 320px. Tables become labelled stacks below 720px.

## Files

| File | Contents |
|---|---|
| `src/styles/tokens.css` | Color (light and dark), type, space, shape, motion |
| `src/styles/base.css` | Element defaults, typography, focus, reduced motion, view transitions |
| `src/styles/components.css` | Buttons, forms, status, tables, dialogs, alerts, palette, the line |
| `src/styles/shell.css` | Top bar, index navigation, public navigation, footer |
| `src/styles/screens-*.css` | Screen-specific layout: public, admin, supplier, enduser |

## Implementation notes

- **Sticky headers** stick to the page only inside `.table-scroll` on wide
  screens. A table inside any other scrolling frame keeps its header at the
  top of that frame, because a sticky element cannot see past a scrolling
  ancestor.
- **View transitions** pair the content area across page changes. The
  `view-transition-name`s are set only while a transition runs
  (`.vt-active`, `:active-view-transition`), because a named element is a
  stacking context and would otherwise trap dialogs under the top bar.
- **Legacy CSS.** `src/index.css` and `design-system.css` still hold rules
  for screens outside the redesign (registration, profile, settings forms),
  inside `@layer legacy`. Their colours, shadows and radii are mapped to
  the tokens, so they follow the theme. Delete a rule there once its
  screen is rebuilt here. A layered `!important` beats an unlayered one,
  so a legacy `!important` must be deleted, not overridden.

## Verification and tools (`design-lab/`)

| Tool | Use |
|---|---|
| `preview.html?as=admin\|enduser\|supplier` | The real app with sample data, for screenshots of signed-in screens |
| `viewports.html?src=<url>` | One page at 820px and 390px side by side; `overflowReport()` in the console |
| `contrast-audit.js` | `await import('/design-lab/contrast-audit.js'); auditContrast(document)` lists text below AA |

Checked at 1536, 820 and 390px in light and dark: no horizontal overflow
on the redesigned screens, no AA contrast failures, a visible focus ring
on every control reached by Tab, and no console errors.
