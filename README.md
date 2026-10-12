<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="branding/banner-dark.svg">
    <img src="branding/banner-light.svg" alt="PlanStride: Monday plans. Friday results." width="100%">
  </picture>
</p>

**PlanStride helps engineering team leads turn every engineer's Monday plan into a
Friday result: one thing to ship, checked by AI before you approve it, tracked
through the week.**

Each member writes a plan for the week: one main task and why it matters, a few
sub-goals that get it over the line, and go-to-market goals that put the work in
front of users. An AI reviewer (Pydantic AI + Gemini) flags tasks you couldn't
honestly tick off on Friday and suggests rewrites you apply in one click. The team
lead approves the plan or sends it back with a comment, everyone ticks tasks off
during the week, and on Friday the member records whether the main task shipped.

It is a multi-tenant SaaS: anyone can sign up, organizations are walled off from
each other in the API, and PlanStride's own staff run it from a separate internal
console that never shows customer plan content.

## What's in the box

| Folder      | What it is                                                                                         | Setup                                    |
| ----------- | -------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| `api/`      | FastAPI backend: organizations, teams, weekly plans, the AI agents, the staff API, the seed command | [api/README.md](api/README.md)           |
| `app/`      | The product customers use: sign-up, my week, AI review, approvals, teams, members                   | [app/README.md](app/README.md)           |
| `internal/` | PlanStride's staff console: organizations, users, suspension, AI usage                             | [internal/README.md](internal/README.md) |
| `site/`     | The landing page, statically generated                                                             | [site/README.md](site/README.md)         |
| `branding/` | Logo, wordmark, favicon, banners and the brand sheet                                               | [branding/README.md](branding/README.md) |
| `docs/`     | Architecture, tenancy rules, AI design, and the project roadmap                                    | see below                                |

PlanStride is built on [Launchbase](https://github.com/chamoda/launchbase) and
follows its conventions (see the `AGENTS.md` files).

## Run it locally

Everything runs with local commands. Docker is only needed for the API test
suite, which starts its own Postgres. (Each package also has a Dockerfile for
production images; see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).)
Linux (Ubuntu 24.04) and macOS are covered below; on Windows, use WSL 2.

### 1. Install the tools

- **[uv](https://docs.astral.sh/uv/)**, which also fetches Python if you don't
  have 3.12 or newer: `brew install uv` on macOS, or
  `curl -LsSf https://astral.sh/uv/install.sh | sh` on Ubuntu.
- **Node.js 24+**: with [nvm](https://github.com/nvm-sh/nvm), `nvm install 24`
  (each front end has an `.nvmrc`, so `nvm use` picks it up).
- **Postgres 16** (newer versions work too):
  `brew install postgresql@16 && brew services start postgresql@16` on macOS, or
  `sudo apt install postgresql` on Ubuntu (it starts by itself).
- **Docker**, only for running the API tests.
- **A Gemini API key** from [Google AI Studio](https://aistudio.google.com/apikey),
  for the AI features. Optional: everything else works without it.

### 2. Create the database

On Ubuntu, the API's example settings connect as `postgres` with the password
`postgres`, so give that user a password and create the database:

```bash
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
sudo -u postgres createdb planstride
```

On macOS, Homebrew's Postgres signs you in as your own user, with no password:

```bash
export PATH="$(brew --prefix postgresql@16)/bin:$PATH"   # Homebrew doesn't link postgresql@16
createdb planstride
```

### 3. Set up the API

```bash
cd api
uv sync                       # creates .venv and installs everything
cp .env.example .env
```

Then edit `api/.env`:

| Setting | Value |
| --- | --- |
| `SECRET_KEY` | Any long random string. Run `openssl rand -hex 32` and paste the output. |
| `SQLALCHEMY_DATABASE_URI` | Ubuntu: leave it as it is. macOS: `postgresql+asyncpg://YOUR_USERNAME@localhost:5432/planstride` (`whoami` prints your username). |
| `GOOGLE_API_KEY` | Optional: your Gemini key, for the AI buttons. It stays on the server. |

Create the tables and load the demo data, then go back to the repo root:

```bash
uv run alembic upgrade head   # create the tables
uv run manage.py seed         # 3 organizations, 18 people, six weeks of plans
cd ..
```

### 4. Install the front ends

```bash
cd site && npm install && cd ..
cd app && npm install && cd ..
cd internal && npm install && cd ..
```

### 5. Start everything

Use four terminals, each starting from the repo root:

```bash
cd api && uv run fastapi dev   # API            http://localhost:8000/app/docs
cd site && npm run dev         # landing page   http://localhost:3000
cd app && npm run dev          # the product    http://localhost:3001
cd internal && npm run dev     # staff console  http://localhost:3002
```

`make run` in each folder does the same, and with tmux and
[tmuxp](https://tmuxp.git-pull.com/) installed, `tmuxp load .` starts all four.

Open the apps at `http://localhost:…` exactly as above, not `127.0.0.1`:
sign-in uses cookies, and the API accepts requests only from the addresses in
`CORS_ORIGINS` in `api/.env`. Each front end keeps its port; if one is taken,
it stops with "Port … is already in use" (see [Troubleshooting](#troubleshooting)).

## Demo logins

Every demo account's password is **`planstride-demo`**. Customer accounts sign
in to the product at http://localhost:3001; the staff account signs in to the
internal console at http://localhost:3002.

| Who | Email | What to try |
| --- | --- | --- |
| Member | `aisha@northwind.example` | My week: a plan waiting for approval; a history of shipped weeks |
| Member with a vague draft | `lena@northwind.example` | Click **Review with AI** on "Implement checkout", then **Draft from notes** |
| Team lead | `marcus@northwind.example` | **Reviews** (Aisha's plan); **Teams → Payments** for the week at a glance and its history |
| Organization owner | `priya@northwind.example` | **Members** (roles, invite links); she reviews the team leads' plans |
| Organization admin, not a lead | `jordan@northwind.example` | Manages teams and members, but can't approve plans |
| Member on two teams | `tom@northwind.example` | Payments and Platform; an approved week in progress |
| Owner of another organization | `elena@lumen.example` | Open a Northwind link from another account: "Organization not found" |
| Member of a suspended organization | `mia@brightline.example` | The suspended screen |
| Deactivated account | `ben@northwind.example` | Sign-in is refused with a clear message |
| **Platform staff** | `staff@planstride.example` | The internal console: organizations, users, AI usage |

To try signing up through an invite, open
http://localhost:3001/join/demo-join-northwind. The link works once;
`uv run manage.py seed --reset` brings it back. More on what to look for:
[SUBMISSION.md](SUBMISSION.md#demo-logins).

## Everyday commands

```bash
cd api && uv run manage.py seed --reset   # wipe the database and reload the demo
cd api && uv run pytest                   # 187 tests; Docker must be running; no API key or network needed
uv run --project api pre-commit run --all-files   # ruff, pyright, oxfmt, oxlint, tsc (files tracked by git)
cd api && uv run manage.py create-user --first-name Ada --last-name Ops --email ada@example.com --admin
                                          # another staff account; prints a generated password
cd app && npm run generate                # after an API change, with the API running; same in internal/
```

## Troubleshooting

| What you see | Why, and the fix |
| --- | --- |
| `[Errno 48] Address already in use` from the API (`[Errno 98]` on Linux), or `Port 3001 is already in use` from a front end | That port is already taken, usually by an earlier server in another terminal. Stop it with Ctrl+C there, or find it with `lsof -nP -iTCP:8000 -sTCP:LISTEN` and stop it with `kill <PID>`. |
| Sign-in says "Network error" or "Can't reach the API" | The API isn't running, or the page isn't open at http://localhost:3001 (product) or http://localhost:3002 (staff). Use `localhost`, not `127.0.0.1`. |
| `createdb: command not found` on macOS | Homebrew doesn't put `postgresql@16` on your PATH: `export PATH="$(brew --prefix postgresql@16)/bin:$PATH"`. |
| `role "postgres" does not exist` | You're on Homebrew's Postgres: put your username in `SQLALCHEMY_DATABASE_URI` (step 3). |
| `password authentication failed for user "postgres"` | Ubuntu's `postgres` user has no password until you set one (step 2). |
| `seed` says the database already has data | `uv run manage.py seed --reset` |
| The AI buttons say AI isn't available | `GOOGLE_API_KEY` isn't set in `api/.env`. Add it and restart the API. |
| `uv run pytest` can't start Postgres | Start Docker. |

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the data model, tenancy and
  authorization rules, the plan lifecycle, how the AI features work and fail, and
  what staff can and can't see
- [docs/ROADMAP.md](docs/ROADMAP.md): the delivery plan, revised against the brief,
  with status
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md): putting it online with Vercel and a
  Neon database, releases, and the Docker images
- [SUBMISSION.md](SUBMISSION.md): how to run and review it, demo logins, the brand,
  and what isn't done

## Git hooks

[pre-commit](https://pre-commit.com) manages hooks for the whole monorepo via
`.pre-commit-config.yaml`. Install once after cloning:

```bash
uv run --project api pre-commit install
```
