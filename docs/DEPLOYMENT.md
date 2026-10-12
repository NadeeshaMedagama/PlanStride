# Deployment and releases

PlanStride runs on Vercel with its data in a Neon Postgres database. The API is a
Python function; the app, the internal console and the landing page are static
sites. Every release also publishes Docker images to Docker Hub for anyone who
would rather host it themselves.

Each front end calls the API through its own address: a request to
`https://planstride-app.vercel.app/api/app/auth` is forwarded by Vercel to
`https://planstride-api.vercel.app/app/auth` (the rewrite in `app/vercel.json`).
To the browser, the API is part of the site it is on, so the session cookie is a
first-party cookie and sign-in works on the free `*.vercel.app` addresses. No
custom domain is needed.

```
browser ──> planstride-app.vercel.app ──/api/*──> planstride-api.vercel.app ──> Neon Postgres
            static app (app/)             rewrite   FastAPI function (api/)
```

## Deploy the product: database, API and app

This is everything customers use. It takes about twenty minutes, all of it in the
Neon and Vercel dashboards except one command that creates the tables.

### 1. Create the database on Neon

1. Sign up at [neon.com](https://neon.com) and create a project. Pick the region
   **AWS US East 1 (N. Virginia)**: Vercel runs functions in Washington, D.C.
   (`iad1`) unless you change it, and every API request makes several database
   round trips, so the two must be close. (To serve Asia faster, choose
   Singapore for both instead: Neon `aws-ap-southeast-1`, and in the Vercel API
   project, Settings → Functions → Function Region → `sin1`.)
2. Postgres 16 or newer; Neon's default is fine.
3. On the project dashboard choose **Connect**, turn **Connection pooling off**,
   and copy the connection string. It looks like this:

   ```
   postgresql://neondb_owner:npg_…@ep-…-….us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   ```

   Use it exactly as given, everywhere this guide asks for the database URL. The
   API translates it for its driver (asyncpg). The pooled string (with `-pooler`
   in the host) isn't needed: on Vercel the API opens one connection per
   request and closes it straight after, and migrations need the direct one.

Prefer to add Neon from Vercel's Marketplace instead? It creates
`DATABASE_URL` and `DATABASE_URL_UNPOOLED` variables in the project you connect
it to. Copy the `DATABASE_URL_UNPOOLED` value: that is the database URL.

### 2. Create the tables

From your machine, in the repository:

```bash
cd api
SQLALCHEMY_DATABASE_URI='postgresql://neondb_owner:…' uv run alembic upgrade head
```

Keep the single quotes: the URL contains `?` and `&`. The URL on the command line
takes precedence over the one in `api/.env`, which still supplies everything else.
(Without an `api/.env`, also put `SECRET_KEY=unused` in front of the command;
migrations don't use it.) It should finish with
`Running upgrade 9e87ebf2de15 -> 8f715f441ff1`.

Run the same command whenever a release adds a migration, before deploying the
API. The release workflow does this for you.

### 3. Deploy the API

In Vercel: **Add New → Project**, import this GitHub repository, and set:

| Setting | Value |
| --- | --- |
| Project Name | `planstride-api` |
| Root Directory | `api` (Vercel then detects FastAPI) |

Open **Environment Variables** on the same screen and add:

| Name | Value |
| --- | --- |
| `ENVIRONMENT` | `production` (also turns off the interactive API docs) |
| `SECRET_KEY` | The output of `openssl rand -hex 32`. Signs the session tokens; changing it signs everyone out. |
| `SQLALCHEMY_DATABASE_URI` | The Neon connection string from step 1 |
| `GOOGLE_API_KEY` | Optional. A Gemini key from [Google AI Studio](https://aistudio.google.com/apikey); without it the AI buttons explain that AI isn't set up, and everything else works. |
| `LOG_LEVEL` | `INFO` |

Then **Deploy**. (If no deployment starts, open **Deployments → Create
Deployment** and enter `main`: `vercel.json` switches off deploys on push, see
[Shipping changes](#shipping-changes).) When it's done, open
`https://planstride-api.vercel.app/app/health`. It should say
`{"status":"healthy"}`.

Check the project's address under **Settings → Domains**. If it isn't
`planstride-api.vercel.app` (Vercel adds a suffix when a name is taken), put
yours in the `destination` of the `/api/:path*` rewrite in `app/vercel.json`, and
in `internal/vercel.json` if you deploy the console, then commit and push. Use
that production address, not a deployment URL such as
`planstride-api-git-main-….vercel.app`: Vercel puts a login page in front of
deployment URLs, so forwarded requests would get that page instead of the API.

### 4. Deploy the app

**Add New → Project** again, the same repository:

| Setting | Value |
| --- | --- |
| Project Name | `planstride-app` |
| Root Directory | `app` |

It needs no environment variables: `app/.env.production` points it at `/api`.
**Deploy**.

### 5. Try it

1. Open `https://planstride-app.vercel.app/api/app/health`. Seeing
   `{"status":"healthy"}` here proves the app's rewrite reaches the API.
2. Open `https://planstride-app.vercel.app` and sign up. That creates your
   organization, with you as its owner; invite the rest of the team from
   **Members**.

Production starts empty. Don't run `manage.py seed` against it: every demo
account, a staff account among them, uses a password that is in this
repository.

## Optional: the internal console and the landing page

### The internal console

The staff back office deploys like the app: a project named
`planstride-internal` with Root Directory `internal` and no environment
variables. Its own `vercel.json` forwards `/api` to the API in the same way.

Staff accounts are created only from the command line. Create the first one
against the production database; it prints a generated password:

```bash
cd api
SQLALCHEMY_DATABASE_URI='postgresql://neondb_owner:…' \
  uv run manage.py create-user --first-name Ada --last-name Ops --email ada@example.com --admin
```

### The landing page

A project named `planstride-site` with Root Directory `site`, and two
environment variables, both read at build time:

| Name | Value |
| --- | --- |
| `VITE_SITE_URL` | The landing page's own address, such as `https://planstride-site.vercel.app`, for its canonical link and social card |
| `VITE_APP_URL` | The app's address, such as `https://planstride-app.vercel.app`, for the sign-up and sign-in buttons |

## Shipping changes

The `vercel.json` in each folder turns off Vercel's deploy-on-push, so a push to
`main` changes nothing in production. There are two ways to deploy:

- **A release** (below): runs the checks, migrates the database, deploys every
  configured project, and waits for your approval first.
- **By hand:** in each project you changed, open **Deployments → Create
  Deployment** and enter `main`. Deploy the API before the front ends, and if
  the changes add a migration, run the migration command (step 2) first.

Changes to a project's environment variables only reach new deployments, so
redeploy after editing them (**Deployments → ⋯ → Redeploy**). Front-end
variables are read at build time, the API's when it starts.

Would you rather Vercel deployed every push to `main`? Remove the `git` line
from that folder's `vercel.json`. Migrations then become a step you run by
hand before you merge a change that adds one.

## Releases

Five GitHub Actions workflows build, check and ship PlanStride:

| Workflow | File | Runs on | What it does |
| --- | --- | --- | --- |
| CI/CD Pipeline | `ci-cd.yaml` | Pull requests, pushes to `main` | Every pre-commit hook, the API tests, the three front-end builds, and a build and smoke test of each Docker image. On `main`, then publishes `edge` images. |
| CodeQL Security Analysis | `codeql.yaml` | Pull requests, `main`, every Monday | Scans the Python, the TypeScript and the workflows themselves. Results: Security → Code scanning. |
| Release | `release.yaml` | A `v1.2.3` tag, or a manual run | Runs the pipeline on that commit, publishes versioned images, creates the GitHub Release, then deploys to production after approval. |
| Publish Images to Docker Hub | `docker-publish.yaml` | Called by the two above, or by hand | Builds `api`, `app`, `internal` and `site` for linux/amd64 and linux/arm64, with SBOM and provenance attestations. |
| Deploy Production | `deploy-production.yaml` | Called by Release, or by hand | Runs database migrations, deploys the API and the app, then the internal console and the landing page if they have projects, and checks each one answers. |

```
pull request -> CI/CD Pipeline
push to main -> CI/CD Pipeline -> Publish Images (edge)
tag v1.2.3   -> Release -> CI/CD Pipeline -> Publish Images (1.2.3, 1.2, 1, latest)
                        -> GitHub Release -> [you approve] -> Deploy Production -> Vercel
```

Nothing has to be configured for the checks to run. Publishing starts once
Docker Hub is set up, and deploying once Vercel is; until then those steps are
skipped, not failed.

### Setting up deploys from GitHub

Do the Vercel setup above first, then:

1. Create the environment under Settings → Environments → New environment →
   `production`:
   - **Required reviewers:** add yourself. This is the approval step before
     every deploy. Without a reviewer, deploys go out unapproved. GitHub offers
     this on public repositories, and on private ones with a Pro, Team or
     Enterprise plan.
   - **Deployment branches and tags:** selected branches and tags, `main` and
     `v*`.
   - **Environment secrets:**

   | Secret | Value |
   | --- | --- |
   | `VERCEL_TOKEN` | A token from vercel.com/account/tokens, scoped to your team |
   | `PRODUCTION_DATABASE_URL` | The Neon connection string; the workflow runs migrations with it |

2. Add these repository variables (Settings → Secrets and variables → Actions →
   Variables):

   | Variable | Value |
   | --- | --- |
   | `VERCEL_ORG_ID` | Your team ID (Vercel → Team Settings → General) |
   | `VERCEL_PROJECT_ID_API`, `VERCEL_PROJECT_ID_APP` | Each project's ID (project Settings → General) |
   | `VERCEL_PROJECT_ID_INTERNAL`, `VERCEL_PROJECT_ID_SITE` | Optional: the console's and the landing page's, once you have those projects |
   | `PRODUCTION_API_URL`, `PRODUCTION_APP_URL`, `PRODUCTION_INTERNAL_URL`, `PRODUCTION_SITE_URL` | The `https://` addresses, without a trailing slash |

   The `PRODUCTION_*_URL` variables drive the checks after each deploy
   (including the app's `/api` rewrite) and the link on each deployment, and
   they're baked into the front-end Docker images.

### Docker Hub (optional)

1. Create a personal access token with read and write access (Docker Hub →
   Account settings → Personal access tokens).
2. In GitHub, under Settings → Secrets and variables → Actions:

| Kind | Name | Value |
| --- | --- | --- |
| Variable | `DOCKERHUB_USERNAME` | Your Docker Hub username |
| Secret | `DOCKERHUB_TOKEN` | The token |
| Variable | `DOCKERHUB_NAMESPACE` | Optional: an organization to publish under instead of your username |

Images go to `docker.io/<namespace>/planstride-api`, `-app`, `-internal` and
`-site`.

### CodeQL

Code scanning is free for public repositories; private ones need GitHub Code
Security. Leave CodeQL's "default setup" off (Settings → Code security), since
this workflow is the advanced setup and GitHub rejects running both.

### Releasing

```bash
git tag v1.0.0
git push origin v1.0.0
```

Or run Actions → Release → Run workflow from `main` and type `1.0.0`; it
creates the tag. When the pipeline and the images are done, the run waits on
the `production` environment: open it, choose Review deployments, and approve.

A pre-release such as `v1.1.0-rc.1` publishes images and a GitHub pre-release,
and never deploys.

### Rolling back

Run Actions → Deploy Production with the earlier tag, for example `v1.0.0`.
Migrations only move forward: when the database is already on a newer
migration than that release knows, the workflow leaves the schema alone and
deploys the older code. Write migrations the previous release can live with
(add a column before using it, drop it a release later). For a quick revert of
one project, Vercel's Instant Rollback also works (project → Deployments).

## Custom domains

Add your own domain to any project under Settings → Domains. The front ends
work on any domain, because they reach the API through their own `/api` path.
If you give the API a domain of its own, point the rewrites in
`app/vercel.json` and `internal/vercel.json` at it.

## Running the images yourself

```bash
docker run --rm --env-file prod.env docker.io/<namespace>/planstride-api:1.0.0 alembic upgrade head
docker run -d -p 8000:8000 --env-file prod.env docker.io/<namespace>/planstride-api:1.0.0
docker run -d -p 8080:8080 docker.io/<namespace>/planstride-app:1.0.0
```

`prod.env` holds the same settings as the API project above. The API image
runs as production on port 8000 and expects a proxy or load balancer in front
for HTTPS. The front-end images serve on port 8080 with the API's address baked
in at build time: `PRODUCTION_API_URL` when the workflow builds them, otherwise
`/api` on their own host, which needs a proxy in front that forwards `/api/` to
the API. When the app calls the API's own address, the two must share a domain
(`app.example.com` and `api.example.com`), and the app's address must be in the
API's `CORS_ORIGINS`. Each folder's `Dockerfile` shows the `--build-arg`s.

## Troubleshooting

| What you see | Why, and the fix |
| --- | --- |
| The API's `/app/health` says `unhealthy` | The API can't reach the database. Check `SQLALCHEMY_DATABASE_URI`, then the project's **Logs** in Vercel. |
| Sign-up fails, and the API's logs say `relation "users" does not exist` | The tables don't exist yet: run step 2. |
| The app's `/api/app/health` answers 404 `DEPLOYMENT_NOT_FOUND` | The rewrite in `app/vercel.json` points at a host that isn't the API's production address (step 3). Fix it, push, then deploy the app again from `main` (Create Deployment). |
| The app's `/api/app/health` shows a Vercel login page | The rewrite points at a deployment URL. Use the production address. |
| Sign-in says "Network error", or you're signed out again on the next page load | The app was built to call the API's own address instead of `/api`: delete any `VITE_API_URL` variable from the app's Vercel project and redeploy it. |
| The AI buttons say AI isn't set up | Add `GOOGLE_API_KEY` to the API project and redeploy it. |
| The first request after a quiet spell is slow | Neon pauses an idle database and takes a moment to wake it. Later requests are quick. |
| Every API request answers 500, and the API's logs say `SECRET_KEY cannot be empty` or `SQLALCHEMY_DATABASE_URI cannot be empty` | That variable isn't set for the Production environment in the API project. Add it and redeploy. |

## Notes

- The older API Tests, Frontend Build and Code Quality workflows still run on
  their own and overlap with the CI/CD Pipeline. The pipeline is the one
  releases and publishing depend on.
- Deploys never overlap: a second one waits for the first to finish.
