# UI audit before the redesign (Phase 1)

Walked through on 18 Nov 2026 in Chrome at 1536 x 639 (a 1920 x 1080 laptop
at 125% scaling), logged in as the Admin, Supplier and End User test
accounts. Screenshots are kept locally in `design-screenshots/phase1-before/`
(not committed).

## Generic or templated

1. **Purple gradient banner** on supplier registration (indigo `#3730a3` to
   `#4f46e5`). It is left over from the first indigo theme and clashes with
   every other screen.
2. **Default Vite favicon** (purple lightning bolt) and a generic `eP`
   monogram in mustard yellow as the only brand mark.
3. **Graph-paper grid** drawn over a cream `#f6f4ee` page background. It is
   decoration with no meaning, and the cream-plus-serif combination is the
   most common AI-generated look.
4. **All-caps eyebrow labels everywhere**: above every dashboard panel
   ("SUPPLIER NETWORK"), in sidebar sections (MAIN / PROCUREMENT / ACCOUNTS),
   in table headers, on the login card ("EPROCURE ACCESS").
5. **Monospace status badges** (IBM Plex Mono, 10px), and PR numbers in a
   monospace face on End User status cards.
6. **SaaS dashboard kit** on the Admin dashboard: six identical KPI tiles,
   then six identical panels with bar lists. RFQs sent and the response rate
   appear twice.
7. **Emoji and text glyphs as icons**: `✓` and `⏳` in RFQ response counts,
   `🔍` in the Manual RFQs search box, `✓ CATEGORY MATCH` in supplier
   matching.
8. **Oversized rounded pills**: search fields are fully rounded, as are the
   supplier registration step tabs and the "STEP 1" chip.

## Inconsistent

1. **Five layered themes in `index.css`** (9,299 lines, five `:root`
   blocks). `.btn-primary` is defined 18 times and `.status-badge` 7 times,
   so the same component looks different from screen to screen.
2. **Four fonts**: DM Sans in the portals, a heavy display serif on public
   pages, IBM Plex Mono for badges, with Inter and Aptos still in the stack.
3. **Gold is both the brand color and the primary button color.** Gold
   buttons sit beside navy, teal and white buttons. RFQ Management alone has
   four button styles in one row.
4. **The same status has different names.** The Admin sees "Matched" and
   "Approved" or "Completed" (two different labels for `approved`), while the
   End User sees "Supplier Response". The CSS class for Rejected is
   `status-merged`, which is GitHub vocabulary.
5. **Page titles don't match the nav.** "Supplier Management" opens
   "Supplier Verification & Approval". "PR Review & Monitoring" is the only
   nav label with an ampersand-joined pair.
6. **Settings pages** (PR Numbering, PR Notifications) put a narrow card in
   the left third with a large grey header block, leaving the rest of the
   page empty.
7. **The supplier list is cards, while every other list is a table.**
8. **Copy defects**: "2 opportunitys"; "Welcome back, End User." (the role,
   not the person's name); hardcoded `admin@ctu.edu.ph` under
   "Administrator"; developer notes in the "Monitoring Notes" panel; a
   "Purchase Request submitted" banner that stays on the End User dashboard
   indefinitely once any PR has been submitted.

## Usability problems in the main BAC task

- **PR review is a modal.** The original document preview is about 200px
  wide and unreadable, and the line items table needs a horizontal scroll
  inside the dialog. The title says "Edit Purchase Request", while the button
  that opens it says "Open Review".
- **The PR monitoring table overflows at 1536px.** The Next Step and Actions
  columns are cut off behind a horizontal scrollbar.
- **The empty review queue takes a full panel** with a single centered
  sentence.

## Not presentation (noted, not changed)

- Supplier "My Quotations" shows 0 quotations, although the RFQs page shows
  RFQ-2026-0004 as "Quotation Submitted". This may be intended (an uploaded
  RFQ may not count as a quotation record), but it reads as a contradiction.
