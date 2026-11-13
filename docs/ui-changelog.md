# UI Changelog: UI/UX Overhaul

User-visible changes per screen, from commit `d41dca8` (before) to the end of
the overhaul. Nothing here changes a route, an API request or response, a
stored value, a validation rule, a permission or a workflow transition (see
[ui-report.md](ui-report.md) for how that was verified).

## Everywhere

- **Keyboard and screen readers.**
  - A "Skip to main content" link appears on the first Tab.
  - Every control has a visible focus ring that meets 3:1 contrast.
  - Icon-only buttons have descriptive names, e.g. "Delete 2026-11-001" instead of "Delete".
- **Dialogs.** Every dialog keeps focus inside while open, closes with Escape (except where closing would lose work), and returns focus to the button that opened it.
- **No more browser pop-ups.** All `alert()` and `confirm()` boxes are replaced by in-page messages, notifications (toasts) or in-app confirmation dialogs.
- **Notifications.** Successful saves, sends and deletions show a short toast in the corner. Errors stay until dismissed.
- **Recovery from errors.** If one screen fails to display, only that screen shows an error panel, with Try again / Reload. The navigation and session keep working.
- **Breadcrumbs** in all three portals show where you are, e.g. *Admin Portal / PR Review & Monitoring / Supplier Matching*.
- **Contrast.** Muted text, warning badges, input borders, workflow steps and timeline labels were darkened to meet WCAG AA.
- **Reduced motion.** Animations and spinners stop when the operating system asks for reduced motion.
- **Phones (360 px and up).** Tables turn into labelled cards, and no screen scrolls sideways.

## Public

| Screen | Changes |
| --- | --- |
| Login | Visible labels for role, username and password. Empty fields are flagged on the field itself, with focus moved there. Wrong credentials and network errors show inline instead of a pop-up, and what you typed is kept. Log In shows "Signing in…" and can't be pressed twice. The "Login successful" pop-up is now a toast. |
| Forgot password | Labelled field; sentence-case heading. |
| Reset password | Labelled fields with an "At least 8 characters" hint. Length and mismatch errors appear on the field they belong to. |
| Supplier registration | Every error is shown on its own field and in a summary at the bottom. The summary is announced, and each item jumps to the field, including fields on an earlier step. Errors clear as you fix them. The step indicator announces the current step; required fields have a legend; the upload bar is announced. |

## Admin (BAC Secretariat)

| Screen | Changes |
| --- | --- |
| Sidebar | Active item is announced as the current page; sections are grouped; the collapse button reports its state. |
| Dashboard | New top row of six labelled tiles with units and plain "nothing yet" hints: Purchase Requests, Awaiting PR number, Registered suppliers, Suppliers awaiting review, RFQs sent, RFQ response rate. Adds "Updated <time>", a Refresh button, and Try again when loading fails. Clicking a recent PR opens a summary dialog instead of a pop-up. |
| PR Review & Monitoring | Numbered PRs: search, status filter, sortable columns, pagination (10/25/50), result count, and a "no matches / Clear filters" state. Real table semantics for screen readers; rows become cards on phones. **Assign PR Number** now asks for confirmation and says the number is permanent. **Changing a status** asks for confirmation and says the End User may be emailed. **View** opens a summary dialog with an "Open Review" shortcut. The review dialog says why Save is disabled when Entity Name is empty. Delete confirmation names the PR and what is removed. |
| Assign Categories | Each category picker is labelled "Category for item N" and is fully usable with arrow keys and Enter; missing categories are announced. |
| Supplier Matching | **Create RFQ** for an unregistered supplier now asks for confirmation and says a quotation number is issued immediately. |
| RFQ Preparation | Shows "RFQ for <supplier> · <category>", the current status, and the RFQ → Quotation → Evaluation → PO step indicator. **Send RFQ** asks in an in-app dialog that names the recipient email and says the RFQ locks once sent. Mode of Procurement is marked required with a hint. Toasts confirm save and send. |
| RFQ Management | Breadcrumbs inside the response and RFQ-detail views; the RFQ detail shows the step indicator; the document viewer adds "Open in new tab". |
| Manual RFQs | The detail dialog shows the step indicator. Upload errors show inline instead of a pop-up, with "Uploading…" while it works. |
| Supplier Management | Status filter, sort (registration order, newest, oldest, name A–Z/Z–A, status), result count, pagination, and skeleton loading. **Approve / Reject / Request documents** each state what happens to the supplier (e.g. Reject: "loses access to opportunities, RFQs and quotations, and sees your remarks"), mark remarks as required with a hint, and use specific button labels ("Confirm Rejection"). The document preview title names the document. |
| End User Accounts | Required markers and legend. Password-length and mismatch errors sit on their own fields; labelled show/hide toggle; success toast; pagination and clearer empty states. |
| PR Numbering / PR Notifications | Inherit the global focus, contrast and dialog improvements. |

## End User

| Screen | Changes |
| --- | --- |
| Dashboard (PR upload) | Press Enter or Space on the drop area to browse for a file. "Uploading and extracting details…" is announced while OCR runs. A failed save shows inline and keeps your entries, instead of a pop-up. The extraction still needs your review, the declaration and **Save** before anything is stored. |
| Live Status | Breadcrumb; upcoming timeline steps are readable (contrast fix). |

## Supplier

| Screen | Changes |
| --- | --- |
| Sidebar | If your account isn't approved yet, Opportunities, RFQs and Quotations show a lock and "(available after BAC approval)". They still open the same status explanation as before. |
| Dashboard | Stats become labelled tiles with units and zero-state hints. If figures fail to load you now see a message and Try again, instead of zeros. |
| Opportunities | Search, sortable columns, pagination; statuses read "In Review" instead of "in_review"; cards on phones; a failed load shows Try again; a missing budget shows ₱0.00 instead of breaking the page. |
| Opportunity detail | Reports a failed load and falls back to the summary from the list. |
| RFQs / RFQ detail | Current status line and the step indicator (Evaluation and PO Issuance shown as "not yet available in eProcure"). The items table can be scrolled with the keyboard. |
| Quotations | Search, sortable columns, pagination, readable statuses, cards on phones, Try again on failure, clearer empty-state guidance. |
| Profile | The Resubmit Documents dialog keeps focus. The confirmation states that status returns to Pending Review. Save results are announced. |
| Notifications | Unknown notification types get a default icon; readable group labels. |
