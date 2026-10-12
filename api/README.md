# PlanStride API

The PlanStride backend: a multi-tenant FastAPI service with organizations, teams,
weekly plans, two Pydantic AI agents, and a separate staff API. Built on the
Launchbase template (async SQLAlchemy, Postgres, Alembic, JWT auth, pytest).

## Requirements

- Python 3.12
- Postgres 16
- [uv](https://docs.astral.sh/uv/)
- Docker (the test suite starts its own Postgres)

## Quick start

Instructions assume Ubuntu 24.04 or macOS.

From the repo root:

```bash
cd api
uv sync                                  # create venv + install deps (incl. dev group)
cp .env.example .env                     # then edit values (see below)
createdb planstride                      # or use psql / pgAdmin
uv run alembic upgrade head              # apply migrations
uv run manage.py seed                    # demo data (see SUBMISSION.md for logins)
uv run fastapi dev                       # http://localhost:8000
```

`.env` needs at least `SQLALCHEMY_DATABASE_URI` and a random `SECRET_KEY`
(`openssl rand -hex 32`). The example URI uses the `postgres` role that
Ubuntu's Postgres creates; Homebrew's Postgres on macOS has no such role, so
use your own user there:
`postgresql+asyncpg://<your-username>@localhost:5432/planstride`.
`GOOGLE_API_KEY` is optional: without it the AI endpoints answer "not configured"
and everything else works. Get a free key at
[Google AI Studio](https://aistudio.google.com/apikey); it is read from `.env`
only and never leaves the server.

Git hooks are managed at the repo root — see the [root README](../README.md#git-hooks).

API docs (not served in production):

- Customer API: <http://localhost:8000/app/docs>
- Staff API: <http://localhost:8000/internal/docs>
- Every endpoint, with examples: [`requests.org`](requests.org)

## How it's organized

```
app/domain.py            roles, statuses, week helpers: the shared vocabulary
app/models.py            ORM models and the database-level guarantees
app/tenancy.py           OrgAccess: who is calling, in which organization, with what role
app/api/app/access.py    authentication, deactivation check, organization access
app/api/app/routers/     customer endpoints (all under /organizations/{organization_id})
app/api/internal/        staff endpoints (platform staff only)
app/services/            business rules; services flush, routers commit
app/ai/                  Pydantic AI agents, typed outputs, failure handling, usage log
app/cli/                 manage.py commands: create-user, seed
```

The design and its rules are in [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).

## Common workflows

### Run the dev server
```bash
uv run fastapi dev
```

### Run tests
```bash
uv run pytest
uv run pytest --cov=app        # with coverage
```
Tests spin up Postgres in a container via `testcontainers`, so Docker must be
running. They never call Gemini: `pydantic_ai.models.ALLOW_MODEL_REQUESTS` is off
and the agents run on `TestModel` / `FunctionModel`, so no key or network access
to Google is needed.

### Create a migration
```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
uv run alembic check           # confirms models and migrations agree
```

### Load the demo
```bash
uv run manage.py seed          # on an empty database
uv run manage.py seed --reset  # wipe everything and reseed (refused in production)
```

### Create platform staff
```bash
uv run manage.py create-user \
  --first-name Admin \
  --last-name User \
  --email admin@example.com \
  --admin
```
`--admin` makes the user PlanStride platform staff, able to sign in to the
internal console. It is not an organization role, and it is the only way staff
accounts are made. The login password is generated and printed unless you pass
`--password`.

### Run a custom management command
```bash
uv run manage.py --help
```

### Lint & type-check
From the repo root:
```bash
uv run --project api pre-commit run --all-files
```
