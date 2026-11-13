# UI Refactor Safety Net and Baseline

This records how each critical flow behaves **before** the UI refactor and how
to check it again after every commit.

## How to run

```bash
npm run build                 # production build
npx eslint src                # lint (baseline: 32 problems, 31 errors / 1 warning, all pre-existing)
npm test                      # frontend contract tests (Vitest + Testing Library)
node tools/ui-walkthrough.mjs . tools/ui-walkthrough-out   # real-browser a11y/overflow check (see the file header)
# backend API suite (Django). Tests have no __init__.py, so pass module labels:
cd backend && python manage.py test api.tests.test_authorization api.tests.test_category_grouped_matching \
  api.tests.test_ocr_unavailable api.tests.test_password_reset api.tests.test_pr_number_format \
  api.tests.test_pr_status_notifications api.tests.test_rfq_abc api.tests.test_supplier_registration
```

## Baseline results (commit `c44c4e3`, before any UI change)

| Check | Result |
| --- | --- |
| `npm run build` | Pass (JS 509 kB / CSS 130 kB, existing >500 kB chunk warning) |
| `npx eslint src` | 32 problems (31 errors, 1 warning), all pre-existing |
| `npm test` | 38 / 38 pass |
| Django API tests | 283 / 283 pass |

## Final results (end of the overhaul)

| Check | Result |
| --- | --- |
| `npm run build` | Pass (JS 544 kB / CSS 145 kB) |
| `npx eslint src` | 31 problems (30 errors, 1 warning), all pre-existing; none added |
| `npm test` | 78 / 78 pass (the 38 baseline tests plus 40 new) |
| Django API tests | 283 / 283 pass |
| Snapshot files changed since baseline | 0 |
| `tools/ui-walkthrough.mjs` (Chrome + axe-core, 27 screens at 1280 px and 360 px) | 54 / 54 checks clean: no WCAG A/AA violations, no horizontal overflow, no runtime errors |

## How the contract tests work

`src/test/harness.js` renders the real `<App />` at a route, with a fake API
standing in for `fetch` and `XMLHttpRequest`. It records the method, path and
body of every request. Each flow test drives the UI the way a user would and
asserts the exact requests it sends, either with explicit `toEqual` or with a
committed snapshot in `src/test/flows/__snapshots__/`.

Rules for the refactor:
- A snapshot or payload assertion may **never** be updated to make a refactor
  pass. A diff there is a functional change and must be fixed in the UI.
- Selectors may change when visible text or markup changes (e.g. a new label).
  Those edits must not touch the expected requests.
- `acceptConfirmation()` clicks through an in-app confirmation dialog when an
  irreversible action shows one, so the same payload assertion holds with or
  without the new confirmation step.

## Automated coverage per flow

| Flow (process #) | Test | What is pinned |
| --- | --- | --- |
| Login: Admin, End User, Supplier | `auth.test.jsx` | `POST /api/login/` body, landing route, sessionStorage keys; bad credentials stay on `/login`; empty fields send nothing |
| Forgot / reset password | `auth.test.jsx` | `POST /api/forgot-password/`, `POST /api/reset-password/` bodies; mismatch sends nothing |
| Vendor registration (1) | `supplier.test.jsx` | Full multipart body of `POST /api/suppliers/register` (snapshot); missing fields block Continue |
| Document verification (2) | `admin-suppliers.test.jsx` | `PATCH /api/suppliers/:id/status/` for approve, reject (remarks required), For Compliance, apply document changes; delete needs confirmation |
| PR scan and extraction (3) | `pr-upload.test.jsx` | `POST /api/upload/` body; **no `POST /api/pr/` before the user confirms**; save blocked until the declaration is acknowledged; saved body (snapshot); signature rejection keeps input |
| PR number generation (4) | `admin-pr.test.jsx`, `admin-misc.test.jsx` | `PATCH /api/pr/:id/edit/` for Save Corrections vs Assign PR Number (automatic and custom); `PATCH /api/admin/pr-number-format/` |
| Procurement posting (5) | `admin-pr.test.jsx` | No explicit posting action exists. Covered via numbering and status (`PATCH /api/pr/:id/status/`). |
| Category matching (6) | `admin-rfq.test.jsx` | Matching view loads, then Request Quotation |
| RFQ generation and email (7) | `admin-rfq.test.jsx` | Save body and send body (snapshots); cancelling send sends nothing; manual RFQ body |
| Quotation submission (8) | `supplier.test.jsx` | `POST /api/suppliers/:id/rfqs/:rfq/response/` body; non-PDF is rejected client-side; unapproved supplier never loads RFQs |
| Vendor evaluation (9) | none | **Not implemented** in the app |
| PO issuance (10) | none | **Not implemented** in the app |
| Reporting dashboard (11) | `admin-misc.test.jsx`, `supplier.test.jsx` | Admin dashboard requests exactly the summary, PR list and supplier list, with no writes; empty states; supplier dashboard requests |
| Other Admin forms | `admin-misc.test.jsx` | End User account create / mismatch / delete; PR notification settings |
| End User Live Status | `admin-misc.test.jsx` | `GET /api/pr/list/?submitted_by=<username>` |

## Manual checklist (things jsdom can't verify)

Run against `npm run dev` + `npm run start-backend` with a seeded database.
Tick each item for the baseline and again in the final walkthrough.

**All roles**
- [ ] Each role logs in and lands on its portal; Log Out returns to `/login`.
- [ ] Reload inside a portal keeps the session (sessionStorage) and returns to Dashboard.
- [ ] Layout at 360 px, 768 px and 1280 px: no horizontal page scroll; the sidebar becomes a top bar on phones.

**End User**
- [ ] Upload a real signed PR PDF: OCR fields populate, the document preview renders, signature chips show.
- [ ] Save stays disabled until the declaration is ticked; after Save, the success modal shows and the form resets.
- [ ] Live Status shows the new PR, and the timeline advances after BAC actions.

**Admin**
- [ ] Dashboard panels and numbers match the database; auto-refresh doesn't flicker.
- [ ] PR review modal: the original document iframe loads; Recheck Signatures works; Assign PR Number assigns the next number from PR Numbering.
- [ ] Assign Categories → Supplier Matching → Request Quotation → Save RFQ shows the PDF preview → Send emails the supplier (check the mail backend / console).
- [ ] Manual RFQ: Create, then Download PDF; upload the completed PDF from Manual RFQs.
- [ ] Supplier Management: document preview (PDF and image), approve/reject; the supplier's portal access changes.
- [ ] CSV exports download for suppliers and purchase requests.

**Supplier**
- [ ] Unapproved: Opportunities, RFQs and Quotations show the access-status page.
- [ ] Approved: the RFQ list, then detail with the PDF iframe, then upload completed PDF, then the confirmation; Replace Submission while open.
- [ ] Profile edit saves; For Compliance shows Resubmit Documents and the status returns to Pending Review.
- [ ] Notifications: View RFQ opens the RFQ detail.
