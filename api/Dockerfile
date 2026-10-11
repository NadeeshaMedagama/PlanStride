# syntax=docker/dockerfile:1

# PlanStride API: FastAPI on Uvicorn, with the dependencies uv.lock pins.
#   docker build -t planstride-api api
#   docker run --rm planstride-api alembic upgrade head    # with the settings below
#   docker run -p 8000:8000 -e SECRET_KEY=... -e SQLALCHEMY_DATABASE_URI=... \
#     -e CORS_ORIGINS=https://app.example.com planstride-api
# The image runs as production (no /docs, seeding refused). WEB_CONCURRENCY sets
# the number of workers. Publishing: .github/workflows/docker-publish.yaml.

FROM python:3.12-slim-trixie AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /srv/api
# Dependencies only, from the lockfile, so this layer is reused until uv.lock changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim-trixie
RUN groupadd --system --gid 10001 planstride \
    && useradd --system --uid 10001 --gid planstride --no-create-home planstride
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO
WORKDIR /srv/api
COPY --from=build /opt/venv /opt/venv
COPY alembic.ini manage.py ./
COPY migrations ./migrations
COPY app ./app
# Numeric, so platforms can verify the container doesn't run as root.
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/app/health', timeout=4)"]
# Meant to run behind a proxy or load balancer, so trust its X-Forwarded-* headers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
