# Design lab: three directions for the Admin dashboard

Static mockups of the same screen, the BAC Secretariat dashboard, using the
real local data (13 matched PRs, 327 approved suppliers, 14 RFQs). Open them
through the Vite dev server, for example
`http://localhost:5173/design-lab/a-line.html`.

| File | Direction | Type | Color | Structure |
|---|---|---|---|---|
| `a-line.html` | **Line** | Archivo, one variable family, width axis 62 to 125 | Jade and marigold on a cool paper | Pipeline drawn as a transit line across the page, then an 8/4 split: dense worklist and a shaded "waiting on you" column |
| `b-signal.html` | **Signal** | Big Shoulders Display and Atkinson Hyperlegible Next | Garnet slab with signal yellow | Fixed color slab with one giant number, pipeline as a departure board of rows |
| `c-board.html` | **Board** | Bricolage Grotesque, optical size and width axes | Dark umber with sea cyan | Headline written as a sentence, pipeline as six board columns of PR slips |

## Verdict: Line

**Line** wins because its signature works on every screen, not just this
one:

- The line can be the full-width dashboard band, a six-segment mini tracker
  in a table row, or a header on a PR record. Signal's departure board and
  Board's kanban columns only make sense on the dashboard.
- One variable family covers both ends of the type scale. Wide, heavy
  display numbers and condensed table text are both Archivo, so a dense
  table and a display headline still read as one product.
- Jade and marigold are calm enough for a state university office but are
  not the blue or indigo SaaS default. Signal's garnet and yellow felt like
  sports branding, and Board's dark-first UI is a poor fit for office
  monitors and printed screenshots.

Line also takes one idea from **Board**. The dashboard headline states what
needs doing in a sentence ("13 requests are matched and none are posted")
instead of showing the date at display size.
