# Redesign verification (Phase 4)

Checked on 18 Nov 2026 in Chrome against the local dev servers, logged in
as the Admin, Supplier and End User test accounts.

## Widths

Desktop was checked at 1536 x 639 (a 1920 x 1080 laptop at 125%). Tablet
(820px) and phone (390px) were checked in same-origin frames, because the
browser window was maximized and could not be resized.

| Width | Result |
|---|---|
| 1536 desktop | Full sidebar. The PR monitoring table fits without horizontal scroll. |
| 820 tablet | The sidebar collapses to an icon rail. No page-level horizontal overflow on any portal (page width equals viewport width). |
| 390 phone | The masthead keeps the brand, Log out and the menu button. Navigation opens as a drawer under the masthead. Tables become labelled cards. The PR review sheet stacks the document above the form. No page-level horizontal overflow. |

Fixed during this pass:
- the phone drawer opened with an unreadable navy background
- page headers were centred on phones
- the supplier figure row overflowed at tablet width
- RFQ numbers wrapped next to their status on phones

## Contrast (WCAG 2.1 AA)

A script checked every visible text element against its effective
background (4.5:1 for body text, 3:1 for large text). A deliberately
low-contrast probe was flagged (1.55:1), which confirms the check works.

| Screen | Elements checked | Below AA |
|---|---|---|
| Admin: 8 sidebar screens | 28 to 149 each | 0 |
| Admin: PR review sheet, supplier review dialog | 128 (dialog) | 0 |
| Supplier: 6 sidebar screens, RFQ detail | 25 to 81 each | 0 |
| End User: Submit a PR, Live Status | 53, 49 | 0 |
| Public: home, login, registration, FAQ | 27 to 59 each | 0 |

The only items the script flagged were the hidden "eP" text inside the
brand mark, which is transparent and zero-size (the mark is an image). The
FAQ intro failed at 3.9:1 and was fixed by mapping the legacy slate greys
to the text tokens.

## Focus and keyboard

- Every interactive element shows a solid 2px navy outline (manila on
  navy). A legacy 25% alpha focus ring on the sidebar toggle failed the
  3:1 minimum; the focus rule now sits above all legacy styles.
- Tab order runs skip link, masthead, sidebar, then page content.
- Escape closes the PR review sheet and the supplier review dialog. The
  automated tests also cover focus trapping and focus return.

## Console and flows

- No console errors across login, all three portals, the PR review sheet,
  the supplier review dialog, supplier RFQ detail and the public pages.
- Flows clicked through: login for each role; PR review (open the sheet,
  read the document, inspect signatories and line items, close without
  saving); RFQs and responses (expand a PR group); supplier RFQ detail and
  the quotation upload step; End User submission page and Live Status.
- Not done on purpose: uploading a new PR, saving corrections, assigning a
  PR number, sending an RFQ or uploading a quotation. These write to the
  local database, and the automated tests already cover these paths with
  mocked responses.

## Automated checks

- `npm test`: 94 tests pass (93 existing, 1 new for the dashboard work
  queue).
- `vite build`: succeeds.
- `eslint`: no new problems; the 25 pre-existing `react-hooks` findings in
  `App.jsx` are unchanged.
