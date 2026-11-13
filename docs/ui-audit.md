# eProcure UI/UX Audit

Audit of the React + Vite frontend as of commit `d41dca8`, done before any UI
refactor. It maps every screen to its role and user tasks, then lists friction
points and accessibility issues and sets a prioritized plan.

**Rules that apply to every item below:** routes, API endpoints, request and
response shapes, model fields, validation rules, permissions, and workflow
state transitions do not change. Authentication, session and CSRF handling, and
build or deploy config are out of scope.

## 1. Codebase shape

| File | Lines | Notes |
| --- | --- | --- |
| `src/App.jsx` | 7,326 | Every portal, screen, modal and route in one module. |
| `src/index.css` | 9,005 | Five `:root` blocks (lines 3, 3834, 5864, 7348, 7880), each a later redesign overriding the one before. The last, a "canonical layer", already defines semantic colors, a 4–48 px spacing scale, radii and shadows. It has no type, motion, focus, layer or target-size tokens, and the file still holds 824 literal hex colors. 31 media queries, no `prefers-reduced-motion`. |
| `src/components/DragDropUpload.jsx` | 1,375 | PR upload, OCR review, signature check, declaration, save. |
| `src/components/SupplierRegistration.jsx` | 621 | 4-step supplier registration wizard. |
| `src/components/Sidebar.jsx` | 99 | Shared portal sidebar. |
| `src/lib/apiClient.js` | 31 | `apiFetch` wrapper (session cookie, 401 handling). Not touched by this pass. |

`App.jsx` also has **121 inline `style={{…}}` objects**, which are one-off
styles that bypass the tokens.

**Unreachable code:** `Opportunities` (exported but never routed), `Tracking`
and `UploadForm` are not mounted by any route. `/register` mounts an older
supplier form (`Register`) that posts to the same endpoint as the current
wizard at `/supplier/register`. These stay as they are, because removing a
route would be a functional change. See Open questions.

## 2. Roles and navigation

Routes are enforced client-side by `ProtectedRoute` (role read from
`sessionStorage`) and server-side by the session.

| Role (code value) | Route | Navigation |
| --- | --- | --- |
| Public | `/`, `/faq`, `/login`, `/forgot-password`, `/reset-password`, `/supplier/register`, `/register` | Top navbar: Home, Help & FAQ, Log In/Out |
| Admin / BAC Secretariat (`admin`) | `/admin` | Sidebar tabs: Dashboard · PR Review & Monitoring · RFQ Management · Manual RFQs · Supplier Management · End User Accounts · PR Numbering · PR Notifications. Hidden workflow tabs: Assign Categories, Supplier Matching. |
| End User (`buyer`) | `/buyer` | Sidebar: Dashboard (PR upload) · Live Status |
| Supplier (`supplier`) | `/supplier` | Sidebar: Dashboard · Opportunities · RFQs · Quotations · Profile · Notifications. Opportunities, RFQs and Quotations show an "access status" page unless the supplier is **Approved**. |

Portal tabs are component state, not URLs. Reloading always lands on the
Dashboard, and the browser Back button leaves the portal. Changing that would
alter routing, so it is out of scope (see Open questions).

## 3. Process coverage (the 11 in-scope processes)

| # | Process | Where it lives | Status |
| --- | --- | --- | --- |
| 1 | Vendor registration | `/supplier/register` wizard → `POST /api/suppliers/register` | Implemented |
| 2 | Document eligibility verification | Admin › Supplier Management review modal → `PATCH /api/suppliers/:id/status/` | Implemented |
| 3 | PR scanning and extraction | End User › Dashboard → `POST /api/upload/` → read-only review + declaration → `POST /api/pr/`; BAC corrects in Admin › PR Review modal → `PATCH /api/pr/:id/edit/` | Implemented. Human confirmation exists: End User **Save** plus declaration, then BAC **Save Corrections / Assign PR Number**. Nothing is persisted by `/api/upload/` alone. |
| 4 | Automated PR number generation | Admin › PR Numbering (`/api/admin/pr-number-format/`), **Assign PR Number** in the PR review modal | Implemented |
| 5 | Procurement posting | No explicit "post" action. A PR becomes a supplier-visible opportunity through its status / category match. | Partially implicit. See Open questions. |
| 6 | Category-based supplier matching | Assign Categories → Supplier Matching (`/api/pr/:id/supplier-match/`) | Implemented |
| 7 | RFQ generation and email distribution | RFQ Preparation (save/send `PATCH|POST /api/pr/:id/rfq/`), Manual RFQ (`POST /api/pr/:id/manual-rfq/`) | Implemented |
| 8 | Quotation submission | Supplier › RFQs › detail upload (`POST /api/suppliers/:id/rfqs/:rfq/response/`); Admin › Manual RFQs upload | Implemented |
| 9 | Vendor evaluation | **Not implemented.** Only "View Response". A code comment marks a future "Compare Quotations" step. | Missing; needs backend |
| 10 | PO issuance | **Not implemented.** No model, endpoint or screen. | Missing; needs backend |
| 11 | Reporting dashboard | Admin › Dashboard (`/api/admin/dashboard-summary/`), CSV exports; Supplier › Dashboard | Implemented |

Processes 9 and 10 cannot get UI in this pass without backend changes. They
are listed under Recommended backend changes in the final report. The
workflow stepper still shows **Evaluation** and **PO Issuance** as upcoming
stages, so users can see where the process ends today, without implying they
exist.

## 4. Screen-by-screen audit

Severity: **H** blocks or misleads a task, or is a WCAG A/AA failure. **M** is
real friction. **L** is polish.

### 4.1 Public

**Home `/`.** Tasks: understand the system, go to log in.
- L: Notices are hard-coded marketing copy. They can stay; just noting it.
- M: Footer contact items use icons with no text label for the icon's meaning (the text is present, so this is acceptable).

**FAQ `/faq`.** Tasks: self-help.
- L: `<details>` accordions are keyboard-accessible already. Focus style depends on the global `summary:focus-visible` rule.

**Login `/login`.** Tasks: choose a role, sign in, go to registration or reset.
- H: Role `<select>`, username and password have **no `<label>`** (placeholder only). This fails WCAG 1.3.1 / 3.3.2.
- H: All feedback uses `window.alert()`, including the "Login successful as buyer" success alert, which blocks the page and isn't announced in context.
- M: Submit is not disabled while the request is pending, so double submits are possible.
- M: Empty-field validation is a single alert, not field-level.

**Forgot password / Reset password.** Tasks: request a link, set a new password.
- H: Inputs have no `<label>` (placeholder only).
- M: Reset errors are form-level only. Mismatch and length errors aren't tied to fields (`aria-describedby`).
- L: All-caps headings ("FORGOT PASSWORD") read awkwardly and break heading conventions.

**Supplier registration wizard `/supplier/register`.** Tasks: enter company and account details, pick categories, upload documents, review, submit.
- M: Validation errors come back as one list at the bottom. Fields aren't marked `aria-invalid`, the list isn't focused or announced, and the user has to scroll to find it.
- M: The step indicator isn't announced (`aria-current` missing on the active step).
- M: The "Reference Number" is generated client-side (`Math.random`) and shown as if it were official. **Not changed** (the shown value is existing behavior); flagged in Open questions.
- L: Required markers are a literal `*` with no legend.

**Legacy register `/register`.** The same endpoint with a different field set. Placeholder-only inputs; errors in red text without `role="alert"`. Left alone apart from shared a11y fixes.

### 4.2 Admin (BAC Secretariat)

**Shell.** Sidebar, content.
- H: Active nav item has no `aria-current="page"`. Only color shows it.
- M: No breadcrumbs. Hidden workflow tabs (Assign Categories, Supplier Matching, RFQ Preparation) leave the user without a sense of place.
- M: No skip-to-content link.
- M: No error boundary. A render error blanks the whole portal.

**Dashboard.** Tasks: status overview, jump to recent records.
- M: KPIs are spread across panels as bar charts. There is no top-line tile row with labeled units (PRs, suppliers, RFQs, response %).
- M: "Recent Purchase Requests" rows open a `window.alert()` summary.
- L: Auto-refreshes every 30 s with no "last updated" indicator.

**PR Review & Monitoring.** Tasks: review unnumbered PRs, assign PR numbers, correct extracted data, change status, start matching, delete, export.
- H: "Assign PR Number" makes a numbered record (an irreversible allocation) with **no confirmation**.
- H: The monitoring "table" is CSS-grid `<div>`s with no table semantics. Screen readers get no headers.
- M: No sorting, filtering or pagination on the numbered list.
- M: The inline status edit (gear icon) commits a workflow status change with only icon buttons (Check/X) and no stated consequence.
- M: The "View" eye icon and PR-number link open a `window.alert()`.
- M: The "Matched Suppliers" section's **Select** button only raises an alert; it does nothing. Left functionally as is and noted.
- L: "Monitoring Notes" describes development intent ("upcoming supplier matching logic").

**PR review / edit modal.** Tasks: compare the original document to the extracted fields, fix them, verify signatures, assign a number.
- H: Modal has no focus trap, doesn't close on Escape, and doesn't return focus to the trigger.
- M: The only rule (Entity Name required) disables the buttons silently. No inline message.

**Assign Categories.** Tasks: assign a category per item.
- M: The combobox (`SearchableSelect`) lacks `aria-controls` / `aria-activedescendant`, and its listbox has no id.
- L: Table has no caption.

**Supplier Matching / RFQ Preparation.** Tasks: choose suppliers per category group, prepare and send an RFQ, issue a manual RFQ.
- H: **Send RFQ** (emails the supplier, locks the RFQ) uses `window.confirm()`. Not styled, not consistent, and the consequence wording is easy to miss.
- H: **Create RFQ** for unregistered suppliers issues a quotation number immediately, with no confirmation.
- M: Manual-RFQ modal has no focus management.
- M: The workflow stepper shows only the PR-side steps. It doesn't show where RFQ → quotation → evaluation → PO stands for the selected record.

**RFQ Management.** Tasks: monitor RFQs per PR, view responses and documents.
- M: Response indicators use emoji glyphs (⏳ ✓) as the only differentiator besides color.
- M: Document viewer modal has no focus management or accessible title link (`aria-labelledby` missing).
- L: No pagination when many PRs exist.

**Manual RFQs.** Tasks: find, re-download, upload completed RFQs.
- M: Upload errors use `window.alert()`.
- M: Modal has no focus management.

**Supplier Management.** Tasks: search, review documents, verify or reject documents, approve, reject, request compliance, delete.
- H: **Reject** confirmation doesn't state the consequence (the supplier loses portal access; remarks are sent to them).
- H: Review / action / preview modals have no focus trap or Escape handling. The action modal has no `aria-labelledby`.
- M: No status filter, sort or pagination.
- L: Loading state is a text row, not a skeleton.

**End User Accounts.** Tasks: create an account, search, delete.
- M: Password rules are only enforced on submit. There is no inline mismatch message.
- M: The two "Show" toggles control both fields with no `aria-pressed` / `aria-label`.
- L: No pagination.

**PR Numbering / PR Notifications.** Tasks: configure settings.
- L: Good structure already. Sequence digits (2–6) relies on native `min`/`max` only.

### 4.3 End User

**Dashboard (PR upload).** Tasks: upload a signed PR, review the extraction (read-only), acknowledge the declaration, submit.
- M: The dropzone is `role="button"` but handles no Enter/Space key (keyboard users can't open the file picker from it).
- M: The upload-success and delete-item modals have no focus management.
- M: Network failure on save uses `window.alert()`.
- L: The `WorkflowStepper` from the BAC flow isn't shown here. The End User has a separate timeline in Live Status (fine).

**Live Status.** Tasks: track submitted PRs.
- L: The timeline is good. Each record already has a "Current Status" block.
- L: No filter when an End User has many PRs.

### 4.4 Supplier

**Access gate.** Non-approved suppliers see Opportunities, RFQs and Quotations in the nav, but each opens a status page. The goal says users should never see menu items they can't use, while the constraint says role-based visibility stays identical. **Resolved in favor of existing behavior:** items stay, with a lock indicator and accessible description. Flagged in Open questions.

**Dashboard.** Tasks: status, KPIs.
- M: KPI values have no units or zero-state copy. Fetch errors are swallowed (`console.error` only) and show as zeros.

**Opportunities / Opportunity detail.** Tasks: browse matching PRs.
- M: No sort or pagination. Fetch errors are silent. The table isn't responsive at 360 px.

**RFQs / RFQ detail.** Tasks: download the RFQ, upload the completed RFQ, replace it while open.
- M: No visible step indicator for the RFQ record's lifecycle (Sent → Response Submitted → Completed).
- L: The "1–4" instructions list is good and stays.

**Quotations.** Tasks: track submissions.
- M: No sort or pagination. Status classes are built as `status-${status}` (some have no CSS).

**Profile.** Tasks: view and edit the profile, resubmit documents.
- M: The resubmit modal and confirm modal have no focus management.
- L: Success message disappears after 3 s with no live region.

**Notifications.** Tasks: read and jump to the RFQ.
- L: Notifications with no matching type render an empty icon slot.

## 5. Cross-cutting issues

1. **Design tokens.** Five stacked `:root` blocks. The last one has color, spacing, radius and shadow tokens but no type, motion, focus or layer tokens; 824 literal hex colors.
2. **Contrast (WCAG 1.4.3 / 1.4.11).** `--text-muted` is 2.99:1 on white and 2.72:1 on the page background. Warning badge text is 4.42:1. Input borders (`--border-strong`) are 1.69:1. The focus ring (teal at 25% alpha) is about 1.4:1.
3. **Modals.** 16 hand-rolled overlays, none with focus trap, Escape-to-close, or focus restore.
4. **Blocking dialogs.** `window.alert` / `window.confirm` are used in 14 places.
5. **Feedback.** No toast or live-region system; success and error messages are inconsistent.
6. **Errors.** No error boundary anywhere.
7. **Tables.** Sorting and pagination exist only on the unrouted `Opportunities` component.
8. **Motion.** Spinners and transitions ignore `prefers-reduced-motion`.
9. **Status.** Status badge classes are recomputed in about 8 places with slightly different maps.

## 6. Prioritized plan

Each step is one commit (or a small group). Build, lint and tests run after each.

| Priority | Step | Addresses |
| --- | --- | --- |
| P0 | Safety net: frontend contract tests that record every flow's request URL, method and payload; manual checklist | Verification for everything below |
| P0 | Complete the token set (type, motion, focus, layers, target size) in a final layer, fix failing contrast values, base a11y CSS: focus ring, reduced motion, `.sr-only`, skip link | §5.1, §5.2, §5.8 |
| P0 | Shared components: `Modal` (focus trap, Escape, restore), `ConfirmDialog` / `useConfirm`, `ToastProvider`, `ErrorBoundary`, `Breadcrumbs`, `ProcurementStepper`, `KpiTile`, `useTableControls` + `TableToolbar` + `SortableHeader` + `Pagination`, `FieldError` / `RequiredMark` | §5.3–5.7 |
| P1 | App shell: error boundary, toasts, skip link, `aria-current`, breadcrumbs per portal | Shell items |
| P1 | Irreversible-action confirmations: Send RFQ, Create manual RFQ, Assign PR Number, Reject supplier (consequence stated) | H items |
| P1 | Auth screens: labels, inline validation, pending state, no `alert()` | Login / Forgot / Reset |
| P1 | Migrate all modals to the shared `Modal` | §5.3 |
| P2 | Admin Dashboard KPI tiles with units and zero states | Dashboard |
| P2 | PR Monitoring: table semantics, sort, filter, pagination, mobile cards | PR Monitoring |
| P2 | Supplier Management: status filter, sort, pagination | Supplier Mgmt |
| P2 | RFQ stepper (RFQ → Quotation → Evaluation → PO) on RFQ Preparation, RFQ detail, supplier RFQ detail | Workflow |
| P2 | Supplier portal tables: sort, pagination, error states, lock indicators | Supplier |
| P3 | Form inline validation: End User accounts, supplier registration wizard, profile | Forms |
| P3 | Changelog + final walkthrough | Deliverables |

Deferred (too large to do safely in one pass): converting the 9,005-line
stylesheet to tokens throughout. New and touched components use tokens. The
legacy blocks are left in place and pinned by the final token layer, so the
look stays stable.

## 7. Open questions (existing behavior kept)

1. **Procurement posting.** There is no explicit "post" action. Should one exist (e.g. publish a numbered PR to matched suppliers)? That would need a backend state.
2. **Locked supplier menu items.** Hide them for non-approved suppliers, or keep them with a lock (current choice)?
3. **Client-generated registration reference number** (`SUP-YYYY-####`, random). It isn't stored anywhere. Should the backend issue it?
4. **Unrouted components** (`Opportunities`, `Tracking`, `UploadForm`) and the legacy `/register` form. Remove, or route them?
5. **"Matched Suppliers" Select button** in PR Monitoring only shows an alert. Remove, or wire it to Supplier Matching?
6. **Tab state in URLs.** Deep links and Back-button support would change routing. Do it in a later pass?
