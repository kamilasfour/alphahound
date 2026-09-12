# AH2 Database Migrations

How the `alphahound2` migration framework works, and how to run/roll back migrations. See `docs/AH2/docs/DATA_ARCHITECTURE.md` for what the schema actually contains.

---

## Framework

**Alembic** (the standard Python SQL migration tool), living under `docs/AH2/db/`:

```
docs/AH2/db/
  requirements.txt          # alembic, sqlalchemy, psycopg2-binary, python-dotenv
  alembic.ini               # config — no connection string committed here
  create_database.py        # one-off: creates the alphahound2 database itself
  verify_schema.py           # confirms tables exist + current migration version
  verify_audit_append_only.py  # confirms the audit_events trigger actually blocks UPDATE/DELETE
  migrations/
    env.py                  # reads AH2_DATABASE_URL from .env; supports online + offline mode
    script.py.mako           # template for future migrations (`alembic revision`)
    versions/
      ah2_0001_initial_ah2_schema.py   # the STEP 6 foundation migration
```

Why Alembic and not raw numbered `.sql` files: proper `upgrade()`/`downgrade()` pairing per revision, a tracked version stamp (the `alembic_version` table, created automatically), and it's the standard tool for a Python codebase — no custom versioning logic to maintain ourselves.

---

## Credentials — how the password never touches Claude or git

- `C:\alphahound_project\.env` (already gitignored) holds `DATABASE_URL` — AH1's existing admin connection string.
- `create_database.py` reads that, derives an `AH2_DATABASE_URL` (same host/user/password/`sslmode`, database name swapped to `alphahound2`), and appends it to the same `.env` file. It never prints the password.
- `migrations/env.py` reads `AH2_DATABASE_URL` from `.env` at runtime. `alembic.ini` itself contains no connection string.
- Claude has no network path to the Postgres server from its sandbox and never sees or handles the password at any point — every command in this document is meant to be run by a human with access to `.env`, not passed through chat.

---

## One-time setup (already done for STEP 6, kept here for future reference / a fresh environment)

```powershell
cd C:\alphahound_project\docs\AH2
.\.venv\Scripts\Activate.ps1
pip install -r db\requirements.txt
python db\create_database.py
```

`create_database.py` is idempotent — safe to re-run; it checks whether `alphahound2` already exists before doing anything, and checks whether `AH2_DATABASE_URL` is already in `.env` before appending it again.

## Applying migrations

```powershell
cd C:\alphahound_project\docs\AH2\db
alembic upgrade head
```

Applies every migration not yet applied, in order, up to the latest (`head`). For STEP 6 this is just `ah2_0001`.

## Rolling back

```powershell
cd C:\alphahound_project\docs\AH2\db
alembic downgrade -1
```

Rolls back exactly one migration. To roll back everything (drops all 18 tables, the append-only trigger, and the trigger function):

```powershell
alembic downgrade base
```

Every migration's `downgrade()` drops what its `upgrade()` created, in reverse dependency order (children before parents; trigger/function before the table they're attached to).

## Checking current state

```powershell
cd C:\alphahound_project\docs\AH2\db
python verify_schema.py
```

Lists every table in `alphahound2` and the current Alembic version stamp. Useful after any upgrade/downgrade to confirm it did what you expected.

## Writing a new migration (future steps)

```powershell
cd C:\alphahound_project\docs\AH2\db
alembic revision -m "short description"
```

Creates a new file in `migrations/versions/` from `script.py.mako`, stamped to apply after the current `head`. Fill in `upgrade()`/`downgrade()` — following the same style as `ah2_0001` (raw `op.execute()` SQL, since this schema's use of Postgres-specific features like `GENERATED ALWAYS AS IDENTITY`, `JSONB`, `GIN` indexes, and triggers is more directly expressed as SQL than through Alembic's portable `op.create_table()` API).

---

## Testing without a live database

Claude's sandbox has no network path to the real Postgres server, so `tests/test_db_migrations.py` verifies migrations via **Alembic's offline SQL-generation mode** (`alembic upgrade head --sql` / `alembic downgrade head:base --sql`), which renders the exact DDL Alembic would execute without connecting to anything. This confirms structural completeness (every expected table is created/dropped, the append-only trigger exists, no AH1 references) but is not a substitute for actually running the migration against a real database.

The real, live verification for STEP 6 was done manually (see `DATA_ARCHITECTURE.md` §6): `alembic upgrade head` was run for real against `alphahound2`, then `verify_schema.py` and `verify_audit_append_only.py` confirmed the actual database state, including that the append-only trigger genuinely rejects `UPDATE`/`DELETE`.

Run the full suite (offline tests included) the same way as always:

```powershell
cd C:\alphahound_project\docs\AH2
.\.venv\Scripts\Activate.ps1
pytest tests\ -v
```
