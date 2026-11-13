# UI/UX Overhaul: Final Report

Scope: the React + Vite frontend of eProcure, for all three roles (Admin / BAC
Secretariat, End User, Supplier). Companion documents:
[ui-audit.md](ui-audit.md) (audit and plan), [ui-baseline.md](ui-baseline.md)
(safety net, baseline and final results), [ui-changelog.md](ui-changelog.md)
(user-visible changes per screen).

## Summary

- **No functional differences were found.** Every request the UI sends (endpoint, method and payload) is identical to the baseline. 0 of the recorded payload snapshots changed, and no expected request in the baseline tests was edited.
- **Nothing outside the frontend changed.** The diff contains 0 changes to `backend/`, `vite.config.js`, deployment files, authentication/session/CSRF code (`src/lib/apiClient.js`), or the `sessionStorage` keys.
- **Two of the 11 processes have no implementation** to overhaul: vendor evaluation (#9) and PO issuance (#10). The UI now shows them as "not yet available in eProcure" in the RFQ step indicator. The backend work they need is listed below.

## Commits (one screen or component group each)

| Commit | Scope |
| --- | --- |
| `c44c4e3` | Audit (`docs/ui-audit.md`) |
| `0a1c18f` | Safety net: frontend contract tests, baseline and manual checklist |
| `b0b16a0` | Design tokens and the shared accessible component kit |
| `42586de` | App shell: skip link, breadcrumbs, error boundaries, toasts, sidebar semantics |
| `410fb1e` | Confirmations for irreversible actions, with stated consequences |
| `5f302f1` | Login / forgot / reset password |
| `b2e0870` | All remaining overlays moved onto the accessible Modal; alerts removed |
| `c9b09a0` | Dashboard KPI tiles (Admin and Supplier) |
| `c4024ad` | PR Review & Monitoring table |
| `44fc51b` | Supplier Management list |
| `c47cdb0` | RFQ → Quotation → Evaluation → PO step indicator on every RFQ |
| `06309bb` | Supplier portal lists (Opportunities, Quotations) |
| `d503184` | Field-level validation (supplier registration, End User accounts) |
| `7020981` | Accessibility polish (category picker, RFQ screens, notices) |
| `39d15fb` | Fixes from the real-browser axe walkthrough |
| *(this commit)* | Changelog, report, walkthrough tool |

## Files changed

The full list is `git diff --stat d41dca8 HEAD`, 44 files before this commit.

- **Modified:**
  - `src/App.jsx`
  - `src/components/DragDropUpload.jsx`
  - `src/components/SupplierRegistration.jsx`
  - `src/components/Sidebar.jsx`
  - `src/main.jsx` (imports the new stylesheet)
  - `package.json` and `package-lock.json` (dev dependencies `vitest`, `@testing-library/*`, `jsdom`, and a `test` script)
  - `package.json` also carries an unrelated local-dev change that was committed with the test tooling in `0a1c18f`: the `start-backend:win` script now uses the venv at `%USERPROFILE%\.venvs\eProcure` (moved out of OneDrive earlier in this session). It isn't build or deploy config.
  - `.gitignore`
- **Added, UI:**
  - `src/styles/design-system.css`
  - `src/components/ui/`: `Modal`, `ConfirmDialog`, `useConfirm`, `ToastProvider` + `toast-context`, `ErrorBoundary`, `Breadcrumbs`, `KpiTile`, `ProcurementStepper`, `useTableControls`, `TableParts`, `FormParts`, `formUtils`
- **Added, tests and tooling:**
  - `vitest.config.js`
  - `src/test/` (harness, fixtures, 13 test files, 4 snapshot files)
  - `src/components/ui/ui.test.jsx`
  - `tools/ui-walkthrough.mjs`
- **Added, docs:** `docs/ui-audit.md`, `docs/ui-baseline.md`, `docs/ui-changelog.md`, `docs/ui-report.md`

## Verification results

### Automated checks, before and after

| Check | Baseline (`d41dca8`) | Final |
| --- | --- | --- |
| `npm run build` | Pass. JS 509 kB, CSS 130 kB | Pass. JS 544 kB (+35 kB from the new components), CSS 145 kB. The existing >500 kB chunk warning remains. |
| `npx eslint src` | 32 problems (31 errors, 1 warning) | 31 problems (30 errors, 1 warning). All pre-existing; one was removed as a side effect; none were added. |
| Frontend tests (`npm test`) | 38 / 38 (baseline suite) | **78 / 78** (baseline suite plus 40 new tests) |
| Django API tests | 283 / 283 | **283 / 283** |
| Real-browser walkthrough (Chrome, axe-core WCAG 2.0–2.2 A/AA, 27 screens × 1280 px and 360 px) | Not run at baseline | **54 / 54 checks with 0 violations, 0 horizontal overflow, 0 runtime errors** (after fixing the 10 issue types it found) |

### Per flow

"Payload" means the method, path and body the test records are equal to the
baseline.

| Flow (process #) | Result |
| --- | --- |
| Login: Admin, End User, Supplier | ✅ Payload unchanged; same landing routes and storage keys. Errors are now inline. |
| Forgot / reset password | ✅ Payloads unchanged; mismatch and short passwords are still blocked client-side. |
| Vendor registration (1) | ✅ Multipart payload snapshot unchanged. The same rules and messages now also appear on each field. |
| Document eligibility verification (2) | ✅ Approve / reject / For Compliance / apply-documents payloads unchanged. Remarks are still required for reject and compliance. |
| PR scanning and extraction (3) | ✅ `POST /api/upload/` unchanged. **Still nothing is saved until the End User acknowledges the declaration and presses Save** (tested). The saved payload snapshot is unchanged. |
| PR number generation (4) | ✅ Save Corrections / Assign PR Number (automatic and custom) payloads unchanged. A confirmation step was added before assigning. |
| Procurement posting (5) | ✅ Status change payload unchanged; a confirmation step was added. *No explicit posting action exists* (see Open questions). |
| Category-based supplier matching (6) | ✅ Assign Categories payload recorded and unchanged (the save code is byte-identical to the baseline). The matching view loads the same endpoints. |
| RFQ generation and email (7) | ✅ Save and send payload snapshots unchanged. Cancelling the send still sends nothing. The manual RFQ payload is unchanged. |
| Quotation submission (8) | ✅ Completed-RFQ upload payload unchanged; non-PDF files are still rejected client-side; unapproved suppliers still never load RFQs. |
| Vendor evaluation (9) | ⛔ Not implemented in the app (no model, endpoint or screen). |
| PO issuance (10) | ⛔ Not implemented in the app (no model, endpoint or screen). |
| Reporting dashboard (11) | ✅ Admin dashboard requests exactly the same three endpoints with no writes. Refresh re-requests the same summary endpoint. The supplier dashboard loads the same endpoints. |
| Other Admin forms | ✅ End User account create/delete, PR numbering and notification settings payloads unchanged. |

### Not verified (needs a person with real data)

The manual checklist in [ui-baseline.md](ui-baseline.md#manual-checklist-things-jsdom-cant-verify)
covers what automation can't. It still needs to be ticked against a running
backend with real data:

- real OCR on a scanned PR;
- PDF iframes;
- an actual email on Send RFQ;
- CSV downloads;
- screen-reader listening (NVDA / VoiceOver).

The walkthrough used fixture API data, not the live database.

## Functional differences found

**None in data or workflow.** These interaction changes are intentional and
listed so a reviewer can confirm them:

1. **New confirmation steps** before: Assign PR Number, PR status change, Send RFQ (replacing `window.confirm`), and Create manual RFQ. Each sends the identical request after Confirm and sends nothing on Cancel or Escape.
2. **Escape closes dialogs** where it previously did nothing. It is disabled while a save or delete is in progress and for the "PR submitted" dialog, whose Continue button resets the form.
3. **Browser pop-ups are gone.** Login success is a toast. Failures show inline. PR "View" opens a summary dialog. The Matched-Suppliers **Select** button (which only ever displayed a message) shows a toast instead.
4. **Display-only list controls** (search, filter, sort, paging) were added to PR monitoring, Supplier Management, End User accounts, Opportunities and Quotations. The default order is still the API's order, and they never refetch.
5. **The Supplier Management row card** is no longer a single keyboard button. Its own buttons are the keyboard path (this fixed nested interactive controls).

## Backend changes recommended (not made)

| # | Change | Why |
| --- | --- | --- |
| 1 | **Vendor evaluation** (process 9): e.g. a quotation abstract / evaluation model, endpoints to record per-supplier evaluation and the BAC recommendation, and an evaluation status on the RFQ. | Needed before the "Evaluation" step can be anything but "not yet available". The data is already grouped per PR in `rfqs/responses/` (see the code comment in `PRResponsesView`). |
| 2 | **PO issuance** (process 10): PO model, numbering (it could reuse the PR numbering service), PDF generation, and status transitions from an awarded quotation. | Same reason, for the final step. |
| 3 | **An explicit "posted" state** for procurement posting (process 5), if RA 12009 posting must be recorded, e.g. `posted_at` / `posted_by` on a PR. | Today posting is implicit in status and category matching, so the UI can't show or confirm it. |
| 4 | **A server-issued registration reference number.** | The supplier wizard shows a client-generated random `SUP-YYYY-####` that isn't stored anywhere. Left unchanged as existing behavior. |
| 5 | **Add `backend/api/tests/__init__.py`.** | `python manage.py test api` currently finds 0 tests. The suite only runs with explicit module labels (documented in ui-baseline.md). |
| 6 | **Server-side pagination and filtering** for `pr/list/`, `suppliers/`, `buyer-accounts/`. | Paging is client-side today, which is fine at capstone scale but loads the whole list. |
| 7 | **`display_status` on supplier opportunity and quotation responses** (as `pr_list` already has for End Users). | The supplier lists currently format raw values like `in_review` on the client. |

## Open questions (existing behavior kept)

1. Should non-approved suppliers' Opportunities / RFQs / Quotations items be **hidden** rather than shown locked? They are shown locked now, since role visibility had to stay identical.
2. Is "procurement posting" the PR numbering step, a status, or a separate action (see recommendation 3)?
3. Should the unrouted components (`Opportunities`, `Tracking`, `UploadForm`) and the legacy `/register` form be removed or routed? They were left untouched.
4. Should the Matched-Suppliers **Select** button (PR monitoring) be removed or wired to Supplier Matching?
5. Should portal tabs get their own URLs (deep links, Back button)? That changes routing, so it's deferred.
6. The 9,005-line `index.css` still holds legacy literal colors under the new token layer. A follow-up pass can migrate it screen by screen and delete the dead `:root` blocks. New and refactored UI uses tokens only.
