# Test accounts (local development only)

Each password is the same as the username. Choose the matching role in
"Sign in as" on the login page.

| Sign in as | Username | Password | Lands on |
|---|---|---|---|
| Admin | `admintest` | `admintest` | `/admin` (BAC Secretariat) |
| End User | `endusertest` | `endusertest` | `/enduser` |
| Supplier | `suppliertest` | `suppliertest` | `/supplier` |

The supplier account was called `emailtest` before. Running the seed command
renames an existing `emailtest` account to `suppliertest`, keeping its linked
supplier, and sets its password to `suppliertest`.

Create the accounts, or reset their passwords, with:

```
cd backend
python manage.py seed_test_accounts
```

The command is safe to re-run. It only resets these three accounts'
passwords and reactivates them. If no supplier is linked to `suppliertest`, it
creates an approved demo supplier with verified documents. It refuses to run
when `DEBUG` is off.

Do not create these accounts on the deployed (Render) database: anyone who
reads this file could sign in.
