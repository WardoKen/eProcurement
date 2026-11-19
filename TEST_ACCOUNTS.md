# Test accounts (local development only)

Each password is the same as the username. Choose the matching role in
"Sign in as" on the login page.

| Sign in as | Username | Password | Lands on |
|---|---|---|---|
| Admin | `admintest` | `admintest` | `/admin` (BAC Secretariat) |
| End User | `endusertest` | `endusertest` | `/enduser` |
| Supplier | `emailtest` | `emailtest` | `/supplier` |

Create the accounts, or reset their passwords, with:

```
cd backend
python manage.py seed_test_accounts
```

The command is safe to re-run. It only resets these three accounts'
passwords and reactivates them. If no supplier is linked to `emailtest`, it
creates an approved demo supplier with verified documents. It refuses to run
when `DEBUG` is off.

Do not create these accounts on the deployed (Render) database: anyone who
reads this file could sign in.
