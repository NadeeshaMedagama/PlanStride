# Deployment and releases

PlanStride ships through five GitHub Actions workflows. Production runs on
Vercel (the API as a Python function, the three front ends as static sites),
and every release also publishes Docker images to Docker Hub for anyone who
would rather host it themselves.

| Workflow | File | Runs on | What it does |
| --- | --- | --- | --- |
| CI/CD Pipeline | `ci-cd.yaml` | Pull requests, pushes to `main` | Every pre-commit hook, the API tests, the three front-end builds, and a build and smoke test of each Docker image. On `main`, then publishes `edge` images. |
| CodeQL Security Analysis | `codeql.yaml` | Pull requests, `main`, every Monday | Scans the Python, the TypeScript and the workflows themselves. Results: Security → Code scanning. |
| Release | `release.yaml` | A `v1.2.3` tag, or a manual run | Runs the pipeline on that commit, publishes versioned images, creates the GitHub Release, then deploys to production after approval. |
| Publish Images to Docker Hub | `docker-publish.yaml` | Called by the two above, or by hand | Builds `api`, `app`, `internal` and `site` for linux/amd64 and linux/arm64, with SBOM and provenance attestations. |
| Deploy Production | `deploy-production.yaml` | Called by Release, or by hand | Runs database migrations, then deploys the API, the app, the internal console and the landing page to Vercel. |

```
pull request -> CI/CD Pipeline
push to main -> CI/CD Pipeline -> Publish Images (edge)
tag v1.2.3   -> Release -> CI/CD Pipeline -> Publish Images (1.2.3, 1.2, 1, latest)
                        -> GitHub Release -> [you approve] -> Deploy Production -> Vercel
```

Nothing has to be configured for the checks to run. Publishing starts once
Docker Hub is set up, and deploying once Vercel is; until then those steps are
skipped, not failed.

## One-time setup

### 1. Docker Hub

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

### 2. A domain

Sign-in relies on the API's session cookie (`HttpOnly`, `SameSite=Lax`), which
browsers only send when the app and the API are on the same site. Give all four
projects hostnames under one domain you own:

| Project | Example hostname |
| --- | --- |
| Landing page | `www.example.com` |
| App | `app.example.com` |
| Internal console | `internal.example.com` |
| API | `api.example.com` |

Vercel's default `*.vercel.app` addresses are each a separate site to the
browser, so sign-in can't work on them.

### 3. A Postgres database

Vercel doesn't run Postgres itself. Use any managed Postgres 16 or newer, for
example Neon from the Vercel Marketplace, in the same region as your Vercel
functions (Washington, D.C., `iad1`, unless you change it). The API connects
with asyncpg, so write the URL like this:

```
postgresql+asyncpg://USER:PASSWORD@HOST/DATABASE?ssl=require
```

With Neon, take the direct (not pooled) connection string, change
`postgresql://` to `postgresql+asyncpg://`, replace `sslmode=require` with
`ssl=require`, and drop `channel_binding`.

### 4. Four Vercel projects

Create one project per folder: Add New → Project → import this repository →
set the Root Directory. Each folder's `vercel.json` sets the build and switches
off Vercel's own deploy-on-push, so from then on only Deploy Production
deploys. If Vercel starts a first deployment during the import, let it fail or
cancel it.

| Project | Root Directory | Production environment variables |
| --- | --- | --- |
| `planstride-api` | `api` | `ENVIRONMENT=production`, `SECRET_KEY` (`openssl rand -hex 32`), `SQLALCHEMY_DATABASE_URI` (step 3), `CORS_ORIGINS=https://app.example.com,https://internal.example.com`, `GOOGLE_API_KEY` (optional), `LOG_LEVEL=INFO` |
| `planstride-app` | `app` | `VITE_API_URL=https://api.example.com` |
| `planstride-internal` | `internal` | `VITE_API_URL=https://api.example.com` |
| `planstride-site` | `site` | `VITE_SITE_URL=https://www.example.com`, `VITE_APP_URL=https://app.example.com` |

Vercel detects the API as FastAPI (`app/main.py`). Then add each hostname under
the project's Settings → Domains.

### 5. GitHub: the production environment and the Vercel settings

Create the environment under Settings → Environments → New environment →
`production`:

- **Required reviewers:** add yourself. This is the approval step before every
  deploy. Without a reviewer, deploys go out unapproved. GitHub offers this on
  public repositories, and on private ones with a Pro, Team or Enterprise plan.
- **Deployment branches and tags:** selected branches and tags, `main` and `v*`.
- **Environment secrets:**

| Secret | Value |
| --- | --- |
| `VERCEL_TOKEN` | A token from vercel.com/account/tokens, scoped to your team |
| `PRODUCTION_DATABASE_URL` | The same URL as the API's `SQLALCHEMY_DATABASE_URI`; the workflow runs migrations with it |

Then add these repository variables (Settings → Secrets and variables →
Actions → Variables):

| Variable | Value |
| --- | --- |
| `VERCEL_ORG_ID` | Your team ID (Vercel → Team Settings → General) |
| `VERCEL_PROJECT_ID_API`, `VERCEL_PROJECT_ID_APP`, `VERCEL_PROJECT_ID_INTERNAL`, `VERCEL_PROJECT_ID_SITE` | Each project's ID (project Settings → General) |
| `PRODUCTION_SITE_URL`, `PRODUCTION_APP_URL`, `PRODUCTION_INTERNAL_URL`, `PRODUCTION_API_URL` | The four `https://` addresses, without a trailing slash |

The four `PRODUCTION_*_URL` variables drive the post-deploy health checks and
the link on each deployment, and they're baked into the front-end Docker
images.

### 6. The first staff account

Production starts empty (the seed command refuses to run there). Create the
first platform staff account from your machine; it prints a generated
password:

```bash
cd api
SQLALCHEMY_DATABASE_URI='postgresql+asyncpg://…' SECRET_KEY=unused \
  uv run manage.py create-user --first-name Ada --last-name Ops --email ada@example.com --admin
```

Customers sign up in the app as usual.

### 7. CodeQL

Code scanning is free for public repositories; private ones need GitHub Code
Security. Leave CodeQL's "default setup" off (Settings → Code security), since
this workflow is the advanced setup and GitHub rejects running both.

## Releasing

```bash
git tag v1.0.0
git push origin v1.0.0
```

Or run Actions → Release → Run workflow from `main` and type `1.0.0`; it
creates the tag. When the pipeline and the images are done, the run waits on
the `production` environment: open it, choose Review deployments, and approve.

A pre-release such as `v1.1.0-rc.1` publishes images and a GitHub pre-release,
and never deploys.

## Rolling back

Run Actions → Deploy Production with the earlier tag, for example `v1.0.0`.
Migrations only move forward: when the database is already on a newer
migration than that release knows, the workflow leaves the schema alone and
deploys the older code. Write migrations the previous release can live with
(add a column before using it, drop it a release later). For a quick revert of
one project, Vercel's Instant Rollback also works (project → Deployments).

## Running the images yourself

```bash
docker run --rm --env-file prod.env docker.io/<namespace>/planstride-api:1.0.0 alembic upgrade head
docker run -d -p 8000:8000 --env-file prod.env docker.io/<namespace>/planstride-api:1.0.0
docker run -d -p 8080:8080 docker.io/<namespace>/planstride-app:1.0.0
```

`prod.env` holds the same settings as the API project above. The API image
runs as production on port 8000 and expects a proxy or load balancer in front
for HTTPS. The front-end images serve on port 8080, with the URLs from the
`PRODUCTION_*_URL` variables baked in at build time, so build your own for a
different domain (each folder's `Dockerfile` shows the `--build-arg`s).

## Notes

- The older API Tests, Frontend Build and Code Quality workflows still run on
  their own and overlap with the CI/CD Pipeline. The pipeline is the one
  releases and publishing depend on.
- Deploys never overlap: a second one waits for the first to finish.
