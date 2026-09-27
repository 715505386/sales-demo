# 001 MySQL foundation

Status: implemented-needs-runtime-verification
Depends-on: none

## Goal

Replace the SQLite demo store with MySQL 8.x, Docker Compose initialization, seed data, and read-only query functions.

## Done when

- `docker-compose.yml` starts MySQL 8.x.
- `sql/init.sql` creates all required tables and seeds customers, orders, and follow-ups.
- Python database access uses configured MySQL connection settings.
- No business write functions remain in the v1 runtime path.

## Verification

- SQL schema and Python MySQL access are implemented.
- Docker runtime verification is pending because Docker Desktop Linux Engine was unavailable.
