# PlanStride: submission notes (SE-INT-04)

## The name

**PlanStride**

> **PlanStride helps engineering team leads turn every engineer's Monday plan into
> a Friday result: one thing to ship, checked by AI before you approve it, tracked
> through the week.**

**Why this name:** a stride is one confident step at a steady pace, the weekly
rhythm the product builds. "Plan" says what it is and "Stride" says what it
promises, a step forward every week. It's two everyday words, so it's easy to
say and easy to spell when you hear it, and no well-known planning product uses
it.

**Who it's for:** engineering team leads at product companies with roughly 5–50
engineers, who already run a weekly planning ritual in a doc or a spreadsheet.

**Why they'd switch:** Linear tracks tickets and Notion holds notes, but neither
makes each engineer commit to one checkable result for the week, pushes back on
vague plans before the lead reads them, or shows on Friday whether it shipped.

**The logo** (`branding/`): a check mark split where it bends into two strides.
The short mint step stands for the sub-goals; the long white stride is the one
thing that ships. The green tile carries its own colors, so the favicon reads
at 16px on light and dark tabs alike (checked at 16, 32, 64 and 128px on four
backgrounds). The wordmark is Geist SemiBold, outlined, so it renders the same
everywhere.

## How to run it

Every command, in order, is in the root README's
[Run it locally](README.md#run-it-locally), with fixes for common setup errors
under [Troubleshooting](README.md#troubleshooting). Beyond the Launchbase
READMEs:

1. **Database:** `createdb planstride`, then `uv run alembic upgrade head` in
   `api/`. On macOS with Homebrew's Postgres, connect as your own user (the
   README shows the `SQLALCHEMY_DATABASE_URI`).
2. **Seed:** `uv run manage.py seed` (in `api/`). Re-running on a database that
   has data needs `--reset`, which wipes it first (refused in production).
3. **AI key (optional):** put your Google AI Studio key in `api/.env` as
   `GOOGLE_API_KEY=…`. Without it every AI button explains that AI isn't set
   up, and planning works as normal. The model defaults to
   `gemini-3.5-flash-lite` and can be changed with `AI_MODEL`.
4. **Tests:** `uv run pytest` in `api/`. Docker must be running, because
   testcontainers starts Postgres 16. No key and no network access to Google
   are needed.
5. **Front ends:** `npm install` then `make run` in `site/` (port 3000), `app/`
   (3001) and `internal/` (3002).

### Demo logins

Every account's password is **`planstride-demo`**.

| Who | Email | Where to look |
| --- | --- | --- |
| Member | `aisha@northwind.example` | My week: a plan waiting for approval; history of shipped weeks |
| Member with a vague draft | `lena@northwind.example` | Click **Review with AI**: "Implement checkout", no "why", no go-to-market, and checkout work carried over from last week |
| Team lead | `marcus@northwind.example` | **Reviews** (Aisha's plan); **Teams → Payments** for the week at a glance and history; his own plan waits for Priya |
| Organization owner | `priya@northwind.example` | **Members** (roles, invite links); leads the "Engineering Leads" team, so she reviews Marcus and Sofia |
| Organization admin, not a lead | `jordan@northwind.example` | Can manage teams and members, but can't approve plans |
| Member on two teams | `tom@northwind.example` | Payments and Platform; an approved week in progress |
| Owner of another organization | `elena@lumen.example` | For trying cross-organization access |
| Member of a suspended org | `mia@brightline.example` | Sees the suspended screen |
| Deactivated account | `ben@northwind.example` | Sign-in is refused, with a message that says why |
| **Platform staff** | `staff@planstride.example` | The internal console at http://localhost:3002 |

Invite link into Northwind Labs, for trying sign-up through an invite:
http://localhost:3001/join/demo-join-northwind

**Tenancy, the way you said you'd review it:** sign in as Elena (Lumen Health),
copy a Northwind URL from Marcus's session (a plan, a team, the members page),
and open it. The API answers 404 for every one of them. `api/requests.org` has
every endpoint, and `api/tests/api/app/test_tenancy.py` automates the same
check across all 32 organization-scoped endpoints.

## What I built, briefly

- **Product:** sign-up (start an organization or join through an invite),
  owner/admin/member roles, teams with leads (people can be on several), weekly
  plans with a main task, sub-goals and go-to-market goals, the draft →
  submitted → approved → done lifecycle, return with a comment, ticking tasks,
  closing the week (shipped or not), the team's week, history, a review queue.
- **AI:** plan review with findings shown next to their tasks and applied in one
  click, and drafting a plan from a brain dump into the form. Both use Pydantic
  AI with Pydantic `output_type`s, handle every failure in plain words, and log
  each call against the organization. Optional feature: **look back before
  planning**, a tool that reads the member's two previous plans so the reviewer
  can flag work that keeps carrying over. The server checks the model's claims
  before the member sees them: a carry-over the history can't back goes back
  to the model, and a suggestion can never duplicate a task.
- **Internal console:** organizations (suspend/reinstate), users (search,
  memberships, deactivate, password reset), AI usage (calls, failures, rate
  limits, tokens, latency by organization, feature and day). Staff never see
  plan content, by design.
- **Landing page:** hero, how it works, a live AI review example, a section for
  leads, privacy, FAQ. Responsive, with full meta and an Open Graph image.

The design and its reasoning: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
The plan, revised against the brief: [docs/ROADMAP.md](docs/ROADMAP.md).

## Decisions worth explaining

- **Staff and plan text.** Staff don't need customers' plans to run the
  product, and the safest data is data the back office can't reach. So staff
  see counts by status, never content, and a test enforces it on every internal
  endpoint.
- **Who approves a lead's plan.** The lead of another team they're on (the seed
  uses an "Engineering Leads" team run by the CTO). Nobody approves their own
  plan, and an owner or admin role grants no approval rights by itself.
- **Plan visibility.** "Every engineer publishes a plan" suggested openness, so
  submitted plans are visible to teammates and leads. Drafts stay private.
- **404 versus 403.** Another organization's resources return 404, so they look
  like they don't exist. Inside your own organization, 403 says what's missing.
- **`is_admin`.** The column keeps its name for the documented CLI, but in code
  it's `is_platform_staff`, so it can't be confused with an organization's
  `admin` role.
- **Defense in depth in Postgres.** Monday-only weeks, one plan per member per
  week, one main task per plan, and team seats only for members of the same
  organization are database constraints, not just API checks.

## Your hours

**18 hours**, against the brief's estimate of about 12. The timebox note in
[docs/ROADMAP.md](docs/ROADMAP.md#1-what-changed-from-revision-1-and-why) says
where the work grew past it.

## What isn't done

**Cut on purpose (out of scope in the brief):** email (so no email invites,
verification or password-reset mail), billing, SSO, notifications, deployment.
Staff can set a new password for a locked-out user as the support path.

**Not right yet, or not verified:**

- **The AI is tuned by hand, not measured.** The prompts were built against
  Pydantic AI's test models, then run live against `gemini-3.5-flash-lite` on
  the seeded plans and tuned until each came out right: the first live run
  leaked internal task keys into findings, invented figures and missed
  carry-overs, and the fixes are in
  [docs/ROADMAP.md](docs/ROADMAP.md#4-the-live-run-and-whats-open). It's
  still a small model: about one review in three of a strong plan still
  nitpicks a task that's already checkable, and a rewrite is a starting point
  the member edits. There's no scored evaluation set yet, so a prompt change
  is checked by rerunning those plans and reading the results.
- **Front ends have no automated tests.** The API has 187 tests (96% coverage);
  the UI was verified by driving every role's main flows in a real browser.
- **Team history counts the team's current members.** Team membership isn't
  versioned, so someone who left a team drops out of its past weeks.
- **Time zones.** The browser decides "this week" in local time, while the API's
  planning window uses UTC. A one-week tolerance absorbs the difference, but an
  organization-level time zone would be cleaner.
- **No sign-in rate limiting** and no per-organization AI budget; only a
  per-user throttle protects the free-tier quota.
- **Updates aren't live.** A lead sees new submissions on navigation or refetch,
  not instantly.
- Leaving an organization, deleting an organization, and transferring
  ownership in one step aren't built.

**With another day:** a scored set of real plans to measure every prompt
change against; Playwright end-to-end tests for the main flows in CI; a per-organization AI budget with an
alert in the internal console; an organization time zone; and the end-of-week
AI summary, which reuses the look-back tool.
