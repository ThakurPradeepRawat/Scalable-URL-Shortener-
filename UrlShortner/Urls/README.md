# URL Shortener

FastAPI URL shortener backed by PostgreSQL and Redis. PostgreSQL stores URL records; Redis `INCR` allocates globally unique numeric IDs, which are encoded with the `[0-9a-zA-Z]` Base62 alphabet. The ID counter is reconciled against the database maximum at application startup.

## Run locally

Requires Python 3.10+, PostgreSQL, and Redis. Keep Redis persistence enabled so counter values survive restarts; startup reconciliation also repairs a counter that is missing or behind the database.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` for your database credentials and public hostname, then create the PostgreSQL database named in `DATABASE_URL` and start Redis. Apply migrations and start the API:

```bash
python -m alembic upgrade head
uvicorn main:app --reload
```

The application checks both services at startup and expects migrations to have been applied. Interactive API documentation is available at `/docs`.

## API

Create a short URL:

```bash
curl -X POST http://localhost:8000/urls/v1/ \
  -H 'Content-Type: application/json' \
  -d '{"long_url":"https://example.com/path","expires_at":null}'
```

The response contains `short_code` and a browser-ready `short_url` such as `http://localhost:8000/r/1`.

- `GET /urls/v1/{short_code}` returns URL details as JSON.
- `GET /r/{short_code}` redirects with HTTP 307.
- `DELETE /urls/v1/{short_code}` deactivates the short URL.
- `GET /health` reports API process health.

`long_url` must be an HTTP or HTTPS URL. `expires_at` is optional and accepts an ISO 8601 timestamp; timestamps without a timezone are interpreted as UTC. Expired and deactivated links return 404.

Run unit tests with `pytest`.