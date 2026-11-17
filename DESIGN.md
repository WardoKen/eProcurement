# eProcure design system

This is the visual system for eProcure, the procurement portal of the Bids
and Awards Committee (BAC) at CTU Tuburan. It covers the Admin (BAC
Secretariat), Supplier and End User portals and the public pages. The tokens
below are implemented in `src/styles/tokens.css`. Shared components live in
`src/styles/components.css` and the portal shell in `src/styles/shell.css`.

## Direction: the docket

A Purchase Request at a BAC is a paper file. It arrives signed, gets
stamped and numbered, travels in a folder from desk to desk, and is checked
line by line against the government PR form. eProcure should feel like a
well-kept version of that file, not like a startup dashboard.

- **Records are paper, the app is the desk.** White surfaces carry records,
  tables and documents. They sit on a stone-grey workspace, so the eye can
  always tell content from chrome.
- **Ruled, not rounded.** Structure comes from 1px rules and aligned columns,
  as on a government form. Corners are 2 to 4px. Panels have no shadows; only
  dialogs float.
- **One institutional color, one accent.** Docket navy carries the identity
  and every primary action. Manila (the folder) marks where you are and what
  is waiting on you, and nothing else. Status colors are reserved for status.
- **Serif for the record, sans for the tool.** Headings use Literata, a
  serif with the authority of a printed form. Everything you read or operate
  uses Public Sans, a typeface designed for government services, with
  tabular figures for peso amounts and PR numbers.
- **Plain procurement language.** Say PR, RFQ, PO and BAC, the terms staff
  already use. Labels are sentence case and name what a button does
  ("Assign PR number", not "Submit").

**Why this suits a state university.** Staff, suppliers and auditors judge a
government system by whether it looks accountable: legible, orderly,
consistent, and unlikely to change from month to month. A restrained palette,
a printed-form structure and strict status colors read as institutional and
age well. They also meet the accessibility standard (WCAG 2.1 AA) that public
institutions are expected to meet.

**Ruled out:** purple or any gradient, glassmorphism and blur, emoji or text
glyphs as icons, oversized rounded cards, pill-shaped inputs, all-caps eyebrow
labels, monospace badges, decorative background patterns.

## Color

### Base palette

| Token | Hex | Use |
|---|---|---|
| `--navy` | `#1B3A5C` | Masthead, primary buttons, headings, links, focus ring |
| `--navy-hover` | `#142C47` | Primary button hover and pressed |
| `--navy-tint` | `#E4EAF1` | Selected rows, active nav background |
| `--manila` | `#D9B872` | Accent on navy grounds (masthead, dark surfaces) |
| `--manila-deep` | `#8A6722` | Accent on light grounds: active nav bar, "waiting on you" markers |
| `--manila-tint` | `#F6EEDC` | Background behind items that need action |
| `--workspace` | `#E9E7E1` | Page background (the desk) |
| `--sidebar` | `#F5F4F0` | Sidebar background |
| `--paper` | `#FFFFFF` | Panels, tables, forms, documents |
| `--paper-sunken` | `#F2F0EB` | Table headers, read-only fields, inset areas |
| `--ink` | `#1C2430` | Body text and headings on light grounds |
| `--ink-2` | `#4D5664` | Secondary text, labels, table headers |
| `--ink-3` | `#5C6470` | Hints and timestamps (not below 12px) |
| `--rule` | `#D3CFC6` | Panel borders, table row rules, dividers |
| `--rule-strong` | `#B9B4A8` | Section dividers, form-cell grids |
| `--input-border` | `#7D8590` | Input and select borders (3:1 non-text contrast) |

### Status colors

Every status renders as text on a tinted fill, with a small shape before
the label, so status never depends on color alone.

| Tone | Text | Fill | Shape | Statuses |
|---|---|---|---|---|
| Neutral | `#4F5866` | `#E9ECF0` | hollow circle | Submitted (uploaded), Draft, No RFQs |
| Review | `#7A4F00` | `#FAEBCB` | half-filled circle | In Review, Pending Review, Awaiting responses, For Compliance |
| Progress | `#1A5296` | `#E2ECF8` | filled circle | Matched, RFQ sent, Responses in progress |
| Success | `#1D6136` | `#DCEFE1` | check | Completed, Approved, Verified, Response received |
| Danger | `#9B2318` | `#F9E1DD` | cross | Rejected, Returned |

Alerts and toasts use the same five tones, with a 3px left rule in the text
color.

### Measured contrast (WCAG 2.1)

| Pair | Ratio | Needs |
|---|---|---|
| ink on workspace / on paper | 12.5 / 15.6 | 4.5 |
| ink-2 on workspace / sidebar / paper-sunken | 6.0 / 6.7 / 6.5 | 4.5 |
| white on navy | 11.6 | 4.5 |
| navy on sidebar | 10.6 | 4.5 |
| manila on navy | 6.1 | 4.5 |
| manila-deep on sidebar | 4.7 | 3 (marker) |
| input border on paper / workspace | 3.7 / 3.0 | 3 |
| each status text on its fill | 6.0 to 6.5 | 4.5 |

## Typography

| Role | Face | Size / line height | Weight |
|---|---|---|---|
| Page title (h1) | Literata | 26 / 32 | 600 |
| Section title (h2) | Literata | 20 / 26 | 600 |
| Panel title (h3) | Public Sans | 16 / 22 | 650 |
| Body, controls | Public Sans | 14 / 21 | 400, 600 for buttons and labels |
| Table body | Public Sans | 13.5 / 20 | 400 |
| Small, hints, table headers | Public Sans | 12.5 / 18 | 600 for headers, 400 otherwise |

- Figures are tabular (`font-variant-numeric: tabular-nums`) in tables,
  amounts, PR numbers and dates. There is no monospace face.
- Text is left-aligned. Numbers are right-aligned in table columns.
- Sentence case everywhere: headings, buttons, table headers, nav. The only
  capitals are acronyms (PR, RFQ, BAC, TIN).
- Running text is capped at 72 characters per line (`--measure`).

## Spacing, size and shape

- **Spacing scale (4px base):** 4, 8, 12, 16, 20, 24, 32, 48. Panels pad 20px.
  Sections are 24px apart.
- **Control heights:** 36px default, 32px compact (table row actions), 40px
  for login and registration fields. Touch targets are at least 24px.
- **Table density:** 40px rows, 8px by 12px cell padding.
- **Radius:** 2px for controls and badges, 4px for panels and cards, 6px for
  dialogs. Nothing is fully rounded except avatar-style circles.
- **Elevation:** panels have none and use a 1px `--rule` border instead.
  Dialogs and toasts use `--shadow-overlay`.
- **Focus:** a 2px solid navy outline at 2px offset on light grounds, and
  manila on navy. It is always visible on keyboard focus and never removed.
- **Motion:** 120 to 200ms ease-out for state changes only (opening a row,
  showing a toast). All motion is turned off under `prefers-reduced-motion`.

## Layout

```
+--------------------------------------------------------------------------+
| eProcure  Bids and Awards Committee, CTU Tuburan        Name, role  Log out| masthead, navy, 52px
+--------------+-----------------------------------------------------------+
| Overview     | Admin portal / PR review                                  |
|  Dashboard   | Page title                                     [actions]  |
| Procurement  | One-line description                                      |
| |PR review 2 | +-------------------------------------------------------+ |
|  RFQs        | | panel: white, 1px rule, 4px radius                     | |
|  Manual RFQs | +-------------------------------------------------------+ |
| Accounts     |                                                           |
|  Suppliers   |                       workspace, stone                    |
| Settings     |                                                           |
+--------------+-----------------------------------------------------------+
```

- **Masthead:** navy, full width. It names the system and the office it
  belongs to, and holds the signed-in user and Log out.
- **Sidebar:** light, 240px, grouped by task in sentence case. The active
  item has a 3px manila-deep bar and a navy-tint background. It collapses to
  icons, and on phones it becomes a drawer behind a menu button.
- **Content:** max 1320px wide, 32px side padding on desktop, 16px on
  phones. Each page has a breadcrumb, a Literata title, a one-line
  description and its actions on the right.
- **Breakpoints:** 1200px (tables tighten), 960px (sidebar collapses to
  icons), 720px (sidebar becomes a drawer, tables become labelled rows),
  480px (single column, full-width actions).

## Components

- **Buttons:** Primary is solid navy with white text, one per view, for the
  main action. Secondary is white with a navy text and an `--input-border`
  border. Quiet is navy text with no border, for low-emphasis and table
  actions. Danger is red text with a red border, and solid red only inside
  a delete confirmation. All buttons are sentence case, 600 weight and 2px
  radius, with a lucide icon only where it adds meaning.
- **Tables:** paper background, `--paper-sunken` header row with 12.5px
  sentence-case labels, 1px row rules, no zebra stripes, a navy-tint row
  hover. Sort buttons show their direction. Below 720px, tables marked
  responsive turn into labelled rows.
- **Forms:** labels sit above fields (no floating labels), 14px, weight 600.
  Required fields are marked with a red asterisk and a legend. Hints are
  12.5px `--ink-2`. Errors are red text with an icon under the field, plus an
  error summary at the top of long forms. Read-only fields use
  `--paper-sunken` with a solid border.
- **Status badges:** 2px radius, 12px text weight 600, tone shape first.
  The same status has the same label and tone in every portal.
- **Panels:** white, 1px `--rule`, 4px radius. The header row holds a 16px
  title, an optional count and actions, separated by a rule.
- **Dialogs:** 6px radius, overlay shadow, a header with a title and Close,
  a footer with actions aligned right (primary last). Large review tasks
  such as PR review open as a full-height sheet, not a small dialog.
- **Empty, loading and error states:** empty states say what is missing and
  give the next action in one line, left-aligned in the panel, with no large
  illustration. Loading uses skeleton rows the shape of the content. Errors
  use a danger alert that says what failed and offers "Try again".
- **Alerts and toasts:** tinted fill, 3px left rule in the tone color, an
  icon, a one-sentence message.

## Status vocabulary

| Stored value | Label shown | Tone |
|---|---|---|
| `uploaded` | Submitted | Neutral |
| `in_review` | In Review | Review |
| `matched` | Matched | Progress |
| `approved` | Completed | Success |
| `rejected` | Rejected | Danger |

Supplier registration: Pending Review and For Compliance use Review, Approved
uses Success, Rejected uses Danger. Documents: Pending uses Review, Verified
uses Success, Rejected uses Danger.

## Tokens

The canonical copy is `src/styles/tokens.css`. If the two ever disagree, the
CSS file wins and this table should be updated.

```css
:root {
  /* Color */
  --navy: #1B3A5C;
  --navy-hover: #142C47;
  --navy-tint: #E4EAF1;
  --manila: #D9B872;
  --manila-deep: #8A6722;
  --manila-tint: #F6EEDC;
  --workspace: #E9E7E1;
  --sidebar: #F5F4F0;
  --paper: #FFFFFF;
  --paper-sunken: #F2F0EB;
  --ink: #1C2430;
  --ink-2: #4D5664;
  --ink-3: #5C6470;
  --rule: #D3CFC6;
  --rule-strong: #B9B4A8;
  --input-border: #7D8590;

  --tone-neutral: #4F5866;   --tone-neutral-fill: #E9ECF0;
  --tone-review: #7A4F00;    --tone-review-fill: #FAEBCB;
  --tone-progress: #1A5296;  --tone-progress-fill: #E2ECF8;
  --tone-success: #1D6136;   --tone-success-fill: #DCEFE1;
  --tone-danger: #9B2318;    --tone-danger-fill: #F9E1DD;

  /* Type */
  --font-serif: 'Literata', 'Iowan Old Style', Georgia, serif;
  --font-sans: 'Public Sans', 'Segoe UI', system-ui, sans-serif;
  --text-xs: 12px;
  --text-sm: 12.5px;
  --text-table: 13.5px;
  --text-md: 14px;
  --text-lg: 16px;
  --text-xl: 20px;
  --text-2xl: 26px;
  --leading-tight: 1.25;
  --leading-body: 1.5;
  --measure: 72ch;

  /* Space */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-7: 32px;
  --space-8: 48px;

  /* Size and shape */
  --control-h: 36px;
  --control-h-sm: 32px;
  --control-h-lg: 40px;
  --row-h: 40px;
  --radius-control: 2px;
  --radius-panel: 4px;
  --radius-dialog: 6px;
  --shadow-overlay: 0 12px 32px rgba(28, 36, 48, 0.18), 0 2px 6px rgba(28, 36, 48, 0.08);
  --masthead-h: 52px;
  --sidebar-w: 240px;
  --content-max: 1320px;

  /* Focus and motion */
  --focus: 2px solid var(--navy);
  --focus-on-dark: 2px solid var(--manila);
  --focus-offset: 2px;
  --ease: cubic-bezier(0.2, 0, 0, 1);
  --duration: 160ms;
}
```
