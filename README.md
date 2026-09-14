# eProcure

eProcure is an intelligent decision-support and procurement system built for
a state university's Bids and Awards Committee (BAC). It digitizes the
Purchase Request (PR) workflow - from PR upload and data extraction, through
category-based supplier matching, to Request for Quotation (RFQ) generation
and supplier response - replacing a mostly paper-and-email process with a
single system BAC staff, requesting offices, and vendors all use.

**Stack:** Django + MySQL (backend/API), React + Vite (frontend).

**Roles.** The system has three user roles, matching the use case diagram in
the capstone proposal:

- **Admin (BAC Secretariat)** - reviews and manages Purchase Requests,
  verifies and approves suppliers, generates and sends RFQs, and configures
  system-wide settings (PR numbering format, status notification emails).
- **Supplier / Vendor** - registers with eligibility documents, sees
  procurement opportunities matched to their registered categories, and
  submits quotations against RFQs.
- **End User / Buyer** - staff in a requesting office who upload Purchase
  Requests and track their status through review, matching, and approval.

## Local setup - backend

> **There are two `requirements.txt` files in this repo.** The one at the
> project root is an orphaned stub left over from early setup and is
> missing most of what the app actually needs. The real one is
> **`backend/requirements.txt`** - always `cd backend` first, or you'll
> install the wrong dependency set and nothing will work.

1. Create and activate a virtual environment **at the repo root** (this
   matches where the `npm run start-backend*` scripts in `package.json`
   expect to find it), then `cd` into `backend/` before installing so you
   install from the right `requirements.txt`:

   ```bash
   python -m venv .venv

   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate

   cd backend
   pip install -r requirements.txt
   ```

2. Copy `backend/.env.example` to `backend/.env` and fill in the values you
   need (see [Environment variables](#environment-variables) below - for a
   quick start you can leave most of it at its defaults).

3. Apply database migrations:

   ```bash
   python manage.py migrate
   ```

   By default the app runs on **SQLite** with no extra setup - `manage.py
   migrate` creates `backend/db.sqlite3` automatically. This is controlled
   by `DJANGO_USE_SQLITE` in `backend/eprocure/settings.py`, which defaults
   to `1` (true). You do **not** need MySQL or Railway installed just to run
   the app locally; MySQL is only used in `DJANGO_USE_SQLITE=0` mode
   (typically for a closer-to-production setup, or deployment).

4. Start the backend:

   ```bash
   python manage.py runserver 8000
   ```

   (The project's `package.json` also exposes this as `npm run
   start-backend` from the repo root, if you'd rather not activate the venv
   manually - see `start-backend:win` / `start-backend:unix` for the exact
   commands it runs.)

5. **Get an admin account.** A fresh database has no users at all, and the
   `/api/register/` endpoint itself requires an admin session to call (it's
   how an admin creates other accounts) - so the very first admin has to be
   created directly, once, via the Django shell. The `admin`/`buyer`/
   `supplier` roles themselves are seeded automatically by migration
   `0012_seed_default_roles`, so once you've run `migrate`, this will work:

   ```bash
   python manage.py shell
   ```

   ```python
   from api.models import Role, User
   from api.views import hash_password

   User.objects.create(
       username='admin',
       password_hash=hash_password('changeme'),
       full_name='BAC Secretariat',
       role=Role.objects.get(name='admin'),
       is_active=True,
   )
   ```

   Log in with that username/password from the frontend's login screen
   (selecting the Admin role). From there, that account can create further
   admin/buyer/supplier accounts normally through the UI.

## Local setup - frontend

From the repo root (not `backend/`):

```bash
npm install
npm run dev
```

This starts the Vite dev server at `http://localhost:5173`. Check
`package.json` for the full script list (`build`, `preview`, `lint`, plus
the `start-backend*` helpers mentioned above).

The frontend needs the backend running to do anything useful. Out of the
box, the two are already configured to talk to each other: the frontend
defaults to calling the backend at `http://127.0.0.1:8000`, and the
backend's default `FRONTEND_ORIGIN` (see below) already allows
`http://localhost:5173`. If you run the backend on a different port or
host, set `VITE_API_BASE_URL` in a `.env` file at the repo root to match,
and add your frontend's origin to `FRONTEND_ORIGIN` in `backend/.env` - a
mismatch here is the most common cause of login/session requests silently
failing in the browser.

## Environment variables

All backend variables are documented with inline comments in
[`backend/.env.example`](backend/.env.example) - copy it to `backend/.env`
to get started. Summary:

| Variable | Purpose | If left unset |
|---|---|---|
| `DJANGO_SECRET_KEY` | Session/crypto signing key | Falls back to an insecure default - fine for local dev only |
| `DJANGO_DEBUG` | Enables Django's debug error pages | Defaults to `True` (on) |
| `DJANGO_ALLOWED_HOSTS` | Hostnames Django will serve | Defaults to `127.0.0.1,localhost` |
| `DJANGO_USE_SQLITE` | Use SQLite instead of MySQL | Defaults to `1` (SQLite, no DB setup needed) |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | MySQL connection details | Ignored entirely unless `DJANGO_USE_SQLITE=0` |
| `EMAIL_BACKEND` / `EMAIL_HOST` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `EMAIL_PORT` / `EMAIL_USE_TLS` / `DEFAULT_FROM_EMAIL` | SMTP settings for RFQ dispatch and PR status notification emails | Defaults to Django's console backend - emails print to the terminal instead of actually sending, nothing breaks |
| `FRONTEND_ORIGIN` | Origin(s) allowed to make credentialed (cookie) requests | Defaults to `http://localhost:5173,http://127.0.0.1:5173` |
| `SESSION_COOKIE_SAMESITE` / `SESSION_COOKIE_SECURE` | Cross-site session cookie behavior | Default to `None` / `true`, which is required for the frontend and backend on different hostnames (true even for `localhost` vs `127.0.0.1` locally) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` | Credentials for AWS Textract, which powers PR upload OCR extraction | **PR upload will fail without these.** Worse, on the main upload endpoint this currently surfaces as an unhandled server error rather than a clean message - see Known limitations |

## Key features

- **Vendor registration & eligibility verification.** Suppliers register
  with their business details, the categories of goods/services they
  offer, and required compliance documents. BAC Secretariat reviews each
  registration and its documents before the supplier is marked eligible to
  receive RFQs.
- **PR upload with OCR extraction.** Requesting-office staff upload a scanned
  or digital Purchase Request; the system extracts the header details, line
  items, and signatories automatically instead of requiring manual
  re-typing. PR numbers are generated using an **admin-configurable
  format** (prefix, date segments, running-sequence digits, and reset
  schedule) rather than a hardcoded scheme.
- **Category-based supplier matching.** Once a PR's line items are
  categorized, the system automatically groups them and matches each group
  against suppliers who are registered for that category, approved, and
  have every required compliance document verified - no manual searching
  required.
- **RFQ generation & email dispatch.** BAC can generate a Request for
  Quotation per matched supplier group directly from a PR and send it by
  email; suppliers respond with quotations through their own portal.
- **PR status email notifications.** Buyers are notified by email as their
  PR moves through review, matching, approval, or rejection. This is
  **admin-configurable per status** - each transition's email can be
  toggled independently, and there's a separate switch to mute the
  automatic status-change emails that fire while BAC is actively
  re-categorizing a PR's items (an explicit status change always still
  notifies, regardless of that switch).
- **Admin reporting dashboard.** A summary view of PR and RFQ activity -
  status breakdowns, monthly PR volume, RFQ response rates - with CSV
  export of suppliers and Purchase Requests, filterable by status,
  category, and date range.

## Admin settings

Two configuration panels live under **Settings** in the admin sidebar:

- **PR Numbering** - controls the PR number format described above
  (prefix, date granularity, digit count, reset schedule).
- **PR Notifications** - controls which PR status changes trigger an
  email, the master on/off switch, and the "mute automatic transitions"
  option described above.

Both exist so BAC Secretariat can adjust these behaviors themselves without
a code change - worth knowing about before testing the system, since they
change how the PR/RFQ flow behaves.

## Deployment notes

Based on what's actually in this repo (no deployment scripts or hosting
config are committed beyond the two files below, so treat the exact
dashboard settings as something you'll configure manually, not as
pre-verified steps):

- **Frontend - Vercel.** A standard Vite project; Vercel's framework
  auto-detection picks up `npm run build` (output directory `dist/`, per
  `package.json` and `vite.config.js`). Set `VITE_API_BASE_URL` as a Vercel
  project environment variable pointing at the deployed backend URL.
- **Backend - Render (or similar).** `backend/Procfile` defines the
  production start command (`web: gunicorn eprocure.wsgi`), and
  `backend/requirements.txt` is the dependency list to install. On a
  platform like Render, set the service's root/build directory to
  `backend/`, and set every variable from the table above in the service's
  environment settings (with `DJANGO_DEBUG=False` and `DJANGO_USE_SQLITE=0`
  in production).
- **Database - Railway or Render MySQL.** Point `DB_HOST` / `DB_NAME` /
  `DB_USER` / `DB_PASSWORD` / `DB_PORT` at a managed MySQL instance from
  either provider.

## Known limitations

- **No CSRF token protection beyond the session cookie.** State-changing
  API endpoints are decorated `@csrf_exempt` throughout `backend/api/views.py`;
  authentication and authorization rely on the session cookie and
  server-side role checks alone, not a CSRF token.
- **reCAPTCHA is not verified server-side.** The `verify-recaptcha`
  endpoint always returns success - the reCAPTCHA widget on supplier
  registration is currently a display element, not an enforced check.
- **Supplier matching is rule-based, not machine learning.** A supplier is
  "matched" to a PR category when it's registered for that category,
  approved, and has its required documents verified - deliberately, not as
  a placeholder for a future ML model.
- **No mobile app.** eProcure is a responsive web application only.
- **No payment or financial transaction processing.** The system covers
  the procurement workflow (PR → matching → RFQ → quotation → award); it
  does not handle actual payment or disbursement.
