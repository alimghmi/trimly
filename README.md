# Trimly

A small URL shortener. Give it a long URL, get back a short code. Visit the
short code, get redirected to the original URL.

Built with Django + Django REST Framework.

## What it does

- `POST /api/shorten` - send a URL, get back a 5-character code and a short link.
- `GET /<code>` - visiting the short link redirects to the original URL.
- `GET /api/health` - health check for uptime monitoring.
- Once a URL is shortened, that link is permanent.

## Running it locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups
uv run python manage.py migrate
uv run python manage.py runserver
```

The app runs at `http://localhost:8000`. No database or Redis setup needed,
it falls back to SQLite and an in-memory cache automatically.

## Running it with Docker

```bash
cp .env.example .env
docker compose up --build
```

This starts the app with Postgres and Redis. For production, use
`docker-compose.prod.yml` instead (it requires real secrets in `.env`, not
the dev defaults).

## Trying it out

```bash
curl -X POST http://localhost:8000/api/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/some/very/long/path"}'
```

You'll get back something like:

```json
{
  "code": "aB3xZ",
  "short_url": "http://localhost:8000/aB3xZ",
  "long_url": "https://example.com/some/very/long/path"
}
```

Visit `short_url` in a browser and you'll land on the original page.

## Design choices

Django and Django REST Framework provide URL validation, database migrations,
and an admin interface without much extra code.

Short codes contain five characters chosen from `0-9`, `a-z`, and `A-Z`. This
gives 916,132,832 possible codes. Codes are generated with Python's `secrets`
module, which makes them difficult to guess in sequence. The code is the
database primary key, so PostgreSQL prevents duplicates when several requests
arrive at the same time.

Another option was to encode an auto-incrementing database ID and decode it
when a short link is opened. That would avoid collisions, but the codes would
be predictable and easier to enumerate. Encrypting or permuting the ID could
hide the sequence, but it would add a permanent secret key and more complexity.
Losing or changing that key could break existing links, and encryption would
not increase the five-character keyspace. Random generation keeps the design
simple, does not reveal creation order, and lets PostgreSQL handle the rare
collision safely.

By default, code generation stops after 20 attempts to keep request time
bounded. If every attempt collides, the API returns `503` and the client can
try again. This does not mean that every possible code has been used.

PostgreSQL is the permanent source of truth. Redis caches successful lookups
and missing codes to reduce database work. If Redis is unavailable, redirects
fall back to PostgreSQL.

The web application does not store local state, so several web instances can
share the same PostgreSQL database and Redis cache. Database backups are needed
to keep shortened links permanently.

## Running tests

```bash
uv run python manage.py test
```

## Running a benchmark

Start the service, then run the redirect benchmark:

```bash
uv run python scripts/benchmark.py
```

Use `--operation shorten` or `--operation both` to include the write path. The
shorten endpoint is rate-limited. To measure write capacity with Docker, restart
the web service with an explicit higher limit:

```bash
TRIMLY_WRITE_RATE=10000/min docker compose up -d --force-recreate web
uv run python scripts/benchmark.py --operation both --requests 500 --concurrency 50
```

Restore the normal `60/min` limit afterward:

```bash
docker compose up -d --force-recreate web
```

Write benchmarks create permanent short links. Use a disposable database for
large runs. Run `uv run python scripts/benchmark.py --help` to see the
concurrency, request count, warmup, and target options.

## Configuration

All settings are read from environment variables. See `.env.example` for
the full list with explanations. Nothing needs to be set for local
development; the defaults just work.

## Project layout

```
core/
  models.py       the ShortURL table
  shortcodes.py   generates random 5-character codes
  services.py     the actual shorten/resolve logic
  serializers.py  validates incoming URLs
  views.py        the HTTP endpoints
```
