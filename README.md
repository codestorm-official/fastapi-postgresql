# FastAPI with PostgreSQL and Redis

Simple, production-ready FastAPI service with async PostgreSQL (SQLAlchemy 2 + asyncpg),
Redis cache-aside, and structured JSON logging with per-request correlation IDs.

## Deploy on Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/fastapi-postgres-redis?referralCode=asepsp)

1. Click the button above (or deploy this repo into a new Railway project).
2. Add the **PostgreSQL** and **Redis** plugins — Railway injects `DATABASE_URL`
   and `REDIS_URL` automatically; no extra config needed.
3. The app reads `$PORT` and those URLs on boot. Health check path is `/ready`
   (see `railway.json`), so deploys wait until Postgres and Redis are reachable.

## Features

- **Async stack**: FastAPI + SQLAlchemy 2.0 async + asyncpg.
- **Redis cache-aside** on item reads; a Redis outage degrades gracefully (falls back to DB).
- **JSON logging** to stdout with `request_id`, method, path, status, and duration.
- **Health probes**: `/health` (liveness) and `/ready` (checks Postgres + Redis).
- **Railway-friendly**: reads `DATABASE_URL` / `REDIS_URL`, binds to `$PORT`, normalizes `postgres://` URLs.

## Endpoints

| Method | Path          | Description                          |
|--------|---------------|--------------------------------------|
| GET    | `/health`     | Liveness (process up)                |
| GET    | `/ready`      | Readiness (Postgres + Redis up)      |
| POST   | `/items`      | Create item                          |
| GET    | `/items`      | List items (`limit`, `offset`)       |
| GET    | `/items/{id}` | Get item (cached)                    |
| DELETE | `/items/{id}` | Delete item (invalidates cache)      |

Interactive docs at `/docs`.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # adjust DATABASE_URL / REDIS_URL
uvicorn app.main:app --reload
```

Requires a reachable PostgreSQL and Redis (set their URLs in `.env`).

## Quick test

```bash
curl -X POST localhost:8000/items -H 'content-type: application/json' \
  -d '{"name":"hello","description":"world"}'

curl localhost:8000/items/1   # second call is served from Redis
curl localhost:8000/ready
```

## Tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Tests use in-memory SQLite and a fake Redis, so no live Postgres/Redis is needed.

## Notes

- `init_db()` runs `create_all` on startup for convenience. For real schema changes,
  use Alembic migrations instead of relying on auto-create.
- Logs are single-line JSON on stdout; pass structured fields via
  `logger.info("msg", extra={...})`.
