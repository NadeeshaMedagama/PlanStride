# syntax=docker/dockerfile:1

# PlanStride landing page: every page prerendered at build time and served by
# nginx on port 8080.
#   docker build -t planstride-site \
#     --build-arg VITE_SITE_URL=https://www.example.com \
#     --build-arg VITE_APP_URL=https://app.example.com site
# Both URLs are baked in at build time; without them, .env.production's apply.
# Publishing: .github/workflows/docker-publish.yaml.

# The built files are the same for every CPU, so build on the builder's own platform.
FROM --platform=$BUILDPLATFORM node:24-trixie-slim AS build
WORKDIR /src
# The build prerenders every page by starting a preview server on "localhost"
# and fetching from it. BuildKit maps localhost to ::1 as well as 127.0.0.1, and
# the two sides can disagree, so resolve to IPv4 first.
ENV NODE_OPTIONS=--dns-result-order=ipv4first
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY . .
ARG VITE_SITE_URL
ARG VITE_APP_URL
# An empty build arg would override .env.production with "", so drop it instead.
RUN if [ -z "$VITE_SITE_URL" ]; then unset VITE_SITE_URL; fi \
    && if [ -z "$VITE_APP_URL" ]; then unset VITE_APP_URL; fi \
    && npm run build

FROM nginxinc/nginx-unprivileged:1.30-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist/client /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD ["wget", "--quiet", "--output-document=/dev/null", "http://127.0.0.1:8080/healthz"]
