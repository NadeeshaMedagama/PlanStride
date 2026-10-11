## Development

You can assume that all servers are already running on their ports via
`.tmuxp.yaml`: api 8000, site 3000, app 3001, internal 3002.

Read `docs/ARCHITECTURE.md` before changing anything that touches organizations,
roles, plans, the AI features or the internal console.

## Product rules every change must respect

- **Tenancy is enforced in the API, never by hiding UI.** Customer endpoints live
  under `/organizations/{organization_id}/...` and depend on `OrgMember` or
  `OrgManager`; services filter every query by `access.organization_id`.
  Another organization's ids answer 404; a missing role inside your own
  organization answers 403.
- **Staff versus customer admin.** `User.is_platform_staff` (database column
  `is_admin`) means PlanStride staff. In code, "admin" only ever means the
  organization role. Staff are created only with
  `manage.py create-user --admin`.
- **Staff never see plan content.** Nothing under `api/app/api/internal/` or
  `api/app/services/backoffice.py` may select plan or task text, review comments
  or outcome notes, and the AI usage log stores no content.
- **AI output is typed data.** Agents return Pydantic `output_type`s; never ask
  for JSON in a prompt and parse it. Every call goes through `AIService._run`
  (throttle, timeout, failure mapping, usage logging), and the UI only calls the
  AI on an explicit click.
- **Tests are required**, overriding the "MVP" note this template's
  `api/AGENTS.md` used to carry. Tenancy, roles and AI paths especially.

## Lessons from building this (keep adding)

When the agent gets something wrong, record the fix here or in the folder's
`AGENTS.md` so it doesn't happen twice.

- The template never checked `is_active`. Deactivation is enforced in
  `get_current_user`, on every request; keep it there.
- Login paths must do equal Argon2 work whether or not the account exists
  (`burn_password_check`), on both surfaces.
- Front-end grids that contain `truncate` text need `grid-cols-1`
  (`minmax(0, 1fr)`) on mobile, or the implicit column grows past the
  viewport.
- Front-end ports are fixed (`strictPort` in each `vite.config.ts`). The API's
  `CORS_ORIGINS` and the links between surfaces assume 3000/3001/3002; a dev
  server that drifted to 3004 turned every sign-in into a "Network error".
- If you start servers yourself (no tmux session running), stop them before
  handing back, or the developer's own `make run` finds the ports taken.
