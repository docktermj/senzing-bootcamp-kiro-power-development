# Database backup procedure (shared by two callers)

⛔ **This file is the ONE implementation of "back up the resolved repository". Two callers cite it;
neither reimplements it.**

- `SKILL.md` Step 6a, writing the INV-094 revisit bundle at graduation.
- `../bootcamp-onboarding/packaging.md`, when the `transfer` profile is asked for and
  `backups/revisit/` does not exist yet — the flow runs at any point in the bootcamp, so it can be
  reached before graduation has ever run.

⚠️ **Why it was factored out rather than copied.** The indeterminate-`database_type` branch below is
subtle, and getting it wrong means either no backup at all or `pg_dump` aimed at a SQLite file. A
second copy is precisely the drift this repo writes tests to prevent, and the backup is the whole
point of the bundle: INV-094 requires exactly one of the two branches to have run.

## The procedure

Back up the resolved repository so it can be restored later. Read **`database_type`**
(`sqlite`/`postgresql`) from pre-checks and the connection from `config/engine_config.json`.

⛔ **When `database_type` is indeterminate, do not guess a branch** — determine the engine from
`config/engine_config.json`'s connection string instead (and note the missing key per pre-check 3).
Picking the wrong branch here means either no backup or `pg_dump` against a SQLite file.

- **SQLite:** copy the repository file into `backups/revisit/database/` (e.g.
  `cp database/G2C.db backups/revisit/database/G2C.db`).
- **PostgreSQL:** run `pg_dump` of the Senzing database to
  `backups/revisit/database/senzing.dump`. When the database runs in a Docker container, dump
  through the container (e.g.
  `docker exec <container> pg_dump -U <user> -d <db> -Fc > backups/revisit/database/senzing.dump`).
  Confirm the exact user / database / container from `config/engine_config.json` (and the recorded
  container, when container-lifecycle tracking is present); **never invent credentials.**

**If the backup cannot be produced** (tool missing, database unreachable), warn and continue — the
rest of the bundle still saves, and graduation is non-blocking (INV-048). The packaging flow reports
the same way: it says the archive carries no database and why, rather than refusing to package.

## Restore

Record the exact **restore** command wherever this backup is described — `SKILL.md` Step 6c's return
guide (`docs/REVISIT_BOOTCAMP.md`), which the `transfer` archive carries and its `OPEN_ME_FIRST.md`
points at:

- **SQLite** — copy the file back to `database/`.
- **PostgreSQL** — `pg_restore` (or `psql <` for a plain dump) into a fresh database.
