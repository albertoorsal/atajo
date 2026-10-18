# Atajo backend

URL shortener with click analytics — FastAPI + Azure Cosmos DB for MongoDB (vCore).

## Requirements

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- An Azure Cosmos DB for MongoDB (vCore) cluster, with your IP allowed in its networking/firewall settings

## Getting started

All commands run from the `backend/` folder.

**1. Install dependencies**

```bash
uv sync
```

**2. Configure environment**

```bash
cp .env.example .env
```

Fill in `.env`:

| Variable                | Required | Default                 | Description                                   |
| ----------------------- | -------- | ----------------------- | --------------------------------------------- |
| `MONGO_URL`             | yes      | —                       | Cosmos DB connection string                   |
| `API_KEYS`              | yes      | (empty)                 | Comma-separated keys for the `/links` routes  |
| `MONGO_DB`              | no       | `atajo_db`              | Database name                                 |
| `BASE_URL`              | no       | `http://localhost:8000` | Prefix used to build `short_url`              |
| `CLICKS_RETENTION_DAYS` | no       | `90`                    | Click events older than this are auto-deleted |

Generate an API key:

```bash
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**3. Run the server**

```bash
uv run fastapi dev   # development, auto-reload
uv run fastapi run   # production mode
```

The API runs at http://localhost:8000. Interactive docs are at http://localhost:8000/docs (click **Authorize** and paste your API key).

**4. Try it**

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/links \
  -H "X-API-Key: <your key>" -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "alias": "test"}'

curl -i http://localhost:8000/test   # 307 redirect, records a click

curl -H "X-API-Key: <your key>" http://localhost:8000/links/test/stats
```

**5. Run the tests**

```bash
uv run pytest   # uses an in-memory fake DB, no Cosmos connection needed
```

## Authentication

The API has two kinds of routes:

- **Public:** `GET /{code}` (the redirect) and `GET /health`. Anyone who has a short link must be able to open it.
- **Protected by API key:** everything under `/links` (create, stats, deactivate).

The API key exists because the protected routes are not safe to leave open:

- **Creating links:** without a key, anyone could use the service to mass-produce short links to phishing or malware sites, which hides the real destination behind your domain and can get it blacklisted.
- **Stats:** click counts and referrers are private analytics data.
- **Deactivating:** without a key, anyone could disable other people's links.

Send the key in the `X-API-Key` header. `API_KEYS` accepts several comma-separated values, so each client (for example the frontend and an admin script) can have its own key, and you can rotate one without breaking the others. If `API_KEYS` is empty, every protected call is rejected with 401.

Keep the keys in `.env` (already ignored by git) and never commit them.

## API

| Method | Path                  | Auth        | Description                         |
| ------ | --------------------- | ----------- | ----------------------------------- |
| GET    | `/health`             | —           | DB ping                             |
| POST   | `/links`              | `X-API-Key` | Create `{url, alias?, expires_at?}` |
| GET    | `/links/{code}/stats` | `X-API-Key` | Clicks per day + top referrers      |
| DELETE | `/links/{code}`       | `X-API-Key` | Deactivate a link                   |
| GET    | `/{code}`             | —           | 307 redirect, records a click       |

## Layout

```
app/
  main.py          lifespan (indexes, Mongo) + router wiring
  config.py        Settings from .env
  dependencies.py  get_db, require_api_key
  models/          Link document + request/response schemas
  services/        URL validation, link logic
  routers/         links (API) and redirect (catch-all, included last)
  utils/           code generation + reserved codes
```
