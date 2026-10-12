## Python Development

- We are using uv in the project. So every command you run related to python start them with `uv run`

### Development guidelines

- Use `uv run alembic revision --autogenerate` create migration file. Only manual edit you are supposed to do is adding server_default to handle nullable situation. If you need some fancy data migration do it in seperate `uv run manage.py` custom command
- Tests are required for every API change (`uv run pytest`; Docker must be running). Cover the tenancy and role rules, not only the happy path: call new endpoints with another organization's ids and add them to `tests/api/app/test_tenancy.py`.
- Don't use enums in models due to issues in alembic migrations. Allowed values live in `app/domain.py`: use its `Literal` types on the `Mapped[...]` columns and its tuples for CHECK constraints.

### API Development Best Practices

- When you make any changes to APIs make sure to update requests.org file (it's emacs verb plugin file written in org mode)
- Use MUST use common REST API design guidelines
- Never session.commit() in services, only session.flush() in service and let router layer commit
- Customer routes take `OrgMember` or `OrgManager` from `app/api/app/access.py` and pass the `OrgAccess` to services; never accept an organization id or a user id from the request body as authority.
- After regenerating the OpenAPI schema, run `npm run generate` in `app/` and `internal/`.

### AI (Pydantic AI + Gemini)

- Agents live in `app/ai/agents.py` with typed outputs in `app/ai/schemas.py`; they are model-less, and the model is injected per run (`get_ai_model`).
- `pydantic-settings` loads `api/.env` into `settings` but not into `os.environ`, so pass `GOOGLE_API_KEY` to `GoogleProvider` explicitly (see `app/ai/provider.py`). Never log or return the key.
- Tests never call Gemini: `ALLOW_MODEL_REQUESTS = False` is set in `tests/conftest.py`. Use `TestModel` or `FunctionModel` and the `use_model` fixture.
- `TestModel` (and real models) invent task keys. Never trust a key from the model; resolve it against the plan (`normalize_review`).
- Pydantic AI 2.x: `result.usage` is a property, not a method.
- Offline tests prove the plumbing, not the prompts. Run a prompt change live on the seeded plans, a few times each since a small model varies between runs: Lena (every check plus two carry-overs), Ken (scope), Aisha (strong: "ready", no findings), Tom (no carry-over, though his last week didn't ship).
- Flash-lite writes the short task keys into its prose ("T1 is an activity") even when told not to. The member must never see a key: `unkey` turns them into words.
- When the app can check a claim, check it. Flash-lite invents carry-overs from unrelated unfinished work, so the reviewer's output validator sends unbacked ones back (`ModelRetry`) and `normalize_review` drops whatever is left on the last attempt.
- Seed data is prompt input: the look-back sends a member's outcome note to the reviewer, so a note that describes different work than its plan produces wrong findings.

### Lessons (keep adding)

- Relationships raise on lazy load (`app/database.py`). Eager-load with `selectinload`, or set the relationship object on new rows (`Invitation(created_by=user, accepted_by=None)`).
- After a write, re-read with `populate_existing` (see `PlanService.get_plan`) so the response reflects the flush.
- The surfaces are mounted sub-apps: set test `dependency_overrides` on `app_api` and `internal_api`, not only the root app.
- Coverage needs `concurrency = ["greenlet", "thread"]` (already in `pyproject.toml`), or lines after an `await` show as missed.
- Ruff 0.16 enables bugbear: give non-primitive query parameters FastAPI's `Annotated[..., Query()]` form instead of `= Query(...)` defaults.
- Hosted Postgres (Neon) hands out libpq URLs, and asyncpg rejects their `sslmode` and `channel_binding`. Settings pass `SQLALCHEMY_DATABASE_URI` through `asyncpg_url` (`app/config.py`), so the URL is pasted as given; keep every way in (the app, alembic, `manage.py`) on `settings`.
- On Vercel (`VERCEL=1`) the engine uses `NullPool` (`pool_options` in `app/database.py`): frozen serverless instances would otherwise hold idle connections against Neon's limit.
