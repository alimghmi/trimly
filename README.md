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

## Running tests

```bash
uv run python manage.py test
```

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
