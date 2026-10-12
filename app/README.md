# PlanStride App

The product PlanStride's customers use — a [TanStack Start](https://tanstack.com/start)
single-page app: sign-up and invites, my week with AI review and drafting,
approvals, teams, members and settings.

## Architecture

The app runs in TanStack Start's **SPA mode**: routes are never rendered on
the server. The build prerenders the document shell once to
`dist/client/_shell.html`; the host serves that file for every path (see
`public/_redirects`) and the router takes over on the client. That keeps
deployment to static files on a CDN, with no server runtime, while every
screen stays behind the session check in `AuthGuard`.

### Routing

Routes are files under `src/routes/`, and the route tree
(`src/routeTree.gen.ts`) is generated from them — by the Vite plugin during
`dev`/`build`, or on demand with `npm run routes`. It is generated output and
is not committed.

```
src/routes/__root.tsx                         document shell + query/user providers
src/routes/login.tsx                          /login                 (public)
src/routes/signup.tsx                         /signup                (public; ?invite=<token>)
src/routes/join.$token.tsx                    /join/:token           (public invite landing)
src/routes/_main.tsx                          auth guard (pathless)
src/routes/_main/index.tsx                    /  -> your last organization, or /welcome
src/routes/_main/welcome.tsx                  /welcome               (no organization yet)
src/routes/_main/orgs/$orgId.tsx              organization layout: app shell, suspended / not-found states
src/routes/_main/orgs/$orgId/week.tsx         /orgs/:id/week         my week (?week=YYYY-MM-DD)
src/routes/_main/orgs/$orgId/history.tsx      /orgs/:id/history
src/routes/_main/orgs/$orgId/plans/$planId.tsx  a plan (where leads approve)
src/routes/_main/orgs/$orgId/reviews.tsx      plans waiting for my review
src/routes/_main/orgs/$orgId/teams/index.tsx  teams
src/routes/_main/orgs/$orgId/teams/$teamId.tsx  the team's week, history, members
src/routes/_main/orgs/$orgId/members.tsx      members, roles, invite links
src/routes/_main/orgs/$orgId/settings.tsx     organization settings
```

`_main` is a **pathless layout route**: it does not appear in the URL, but
everything nested under it renders behind the auth guard. Organization pages
nest under `orgs/$orgId`, whose layout loads the organization and the caller's
role from the API (`src/contexts/org-context.tsx`) and renders the sidebar
(`src/components/app-shell.tsx`). Add an organization page by dropping a file in
`src/routes/_main/orgs/$orgId/` and a nav entry in the app shell. Public pages go
next to `login.tsx` and get listed in `src/lib/routes.ts`.

The organization lives in the URL rather than in local state, so links to a
plan or a team work for anyone in that organization.

## Getting Started

**Requires Node.js 24+** (current Active LTS). Use `nvm use` to pick up the version from `.nvmrc`.

Install dependencies and run the development server:

```bash
npm install
make run                                  # http://localhost:3001
```

## API SDK

The typed API client in `src/api/` is generated with
[orval](https://orval.dev) from the FastAPI OpenAPI spec:

- `src/api/endpoints/` — TanStack Query hooks (split per OpenAPI tag), calling
  the shared fetch client in `src/lib/api-client.ts`
- `src/api/model/` — TypeScript models
- `src/api/zod/` — standalone zod schemas for request/response/params,
  composable with react-hook-form via `@hookform/resolvers`

Regenerate after changing the API (requires the API dev server running at
`http://localhost:8000`):

```bash
npm run generate
```

Generated files are committed; don't edit them by hand.

### Forms

Forms use [react-hook-form](https://react-hook-form.com) with `zodResolver`.
Extend the generated zod schema with UI-facing validation messages while
staying anchored to the API contract:

```tsx
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AuthBody } from "@/api/zod/auth/auth.zod";

const loginSchema = AuthBody.extend({
  email: z.string().email("Invalid email address"),
});

const form = useForm<z.infer<typeof loginSchema>>({
  resolver: zodResolver(loginSchema),
});
```

## Code Quality

Git hooks for the whole monorepo are managed by
[pre-commit](https://pre-commit.com) at the repo root — oxfmt, oxlint, and
`tsc` run automatically on staged `app/` files before each commit. See the
[root README](../README.md#git-hooks) for setup.

Linting and formatting use the [oxc](https://oxc.rs) toolchain (same org as
Vite and Rolldown) rather than ESLint and Prettier: `oxlint` reads
`.oxlintrc.json`, `oxfmt` reads `.oxfmtrc.json`. Both are Rust binaries with no
plugin dependencies. The oxfmt config was migrated from the old `.prettierrc`
and produces byte-identical output, so nothing was reformatted in the switch.

The generated API client under `src/api/` is excluded from linting but is still
formatted — `npm run generate` runs `oxfmt` over orval's output.

### Manual Commands

You can also run these commands manually:

```bash
# Lint and fix issues
npm run lint:fix

# Format all files
npm run format

# Check formatting without changes
npm run format:check

# Type check
npm run type-check
```

### TypeScript Strict Mode

This project uses **maximum strictness** TypeScript configuration for enhanced
type safety, on TypeScript 7 — the native (Go) compiler, which type-checks this
app roughly 3-6x faster than the 6.x JavaScript one.

## Production

```bash
make build             # -> dist/client/
```

### Vercel

PlanStride deploys this folder as a Vercel project
([docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md)). `vercel.json` publishes
`dist/client/` with two rewrites: `/api/*` goes to the API project, so the app
calls the API through its own address (`VITE_API_URL=/api` in
`.env.production`) and its session cookie is first-party; every other path gets
`_shell.html`, so deep links like `/orgs/…/week` resolve in the router.

On another static host, serve `_shell.html` for unknown paths
(`public/_redirects` does this on Cloudflare Pages and Netlify) and forward
`/api/` to the API.
