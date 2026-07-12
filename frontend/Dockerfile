# Veriprops frontend image — Next.js 16 (React 19) built with pnpm.
# Multi-stage: install deps -> build -> lean standalone runner.
FROM node:22-alpine AS base
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH
RUN corepack enable
WORKDIR /app

# --- deps: install from the committed lockfile (cached across source changes) --
FROM base AS deps
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# --- builder: compile the app -------------------------------------------------
FROM base AS builder
# NEXT_PUBLIC_* are inlined into the client bundle at build time, so they must be
# present here (passed as build args by compose). Server-only vars (API_BASE_URL,
# BACKEND_SECRET_KEY) are read at runtime and are NOT baked in.
ARG NEXT_PUBLIC_ENVIRONMENT=production
ARG NEXT_PUBLIC_APP_NAME=Veriprops
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ARG NEXT_PUBLIC_API_TIMEOUT=10000
ARG NEXT_PUBLIC_MICROSOFT_CLARITY_PROJECT_ID=
ARG NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=
ARG NEXT_PUBLIC_OAUTH_GOOGLE_DISABLED=false
ARG NEXT_PUBLIC_OAUTH_APPLE_DISABLED=true
ARG NEXT_PUBLIC_OAUTH_FACEBOOK_DISABLED=true
ENV NEXT_PUBLIC_ENVIRONMENT=$NEXT_PUBLIC_ENVIRONMENT \
    NEXT_PUBLIC_APP_NAME=$NEXT_PUBLIC_APP_NAME \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_API_TIMEOUT=$NEXT_PUBLIC_API_TIMEOUT \
    NEXT_PUBLIC_MICROSOFT_CLARITY_PROJECT_ID=$NEXT_PUBLIC_MICROSOFT_CLARITY_PROJECT_ID \
    NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=$NEXT_PUBLIC_GOOGLE_MAPS_API_KEY \
    NEXT_PUBLIC_OAUTH_GOOGLE_DISABLED=$NEXT_PUBLIC_OAUTH_GOOGLE_DISABLED \
    NEXT_PUBLIC_OAUTH_APPLE_DISABLED=$NEXT_PUBLIC_OAUTH_APPLE_DISABLED \
    NEXT_PUBLIC_OAUTH_FACEBOOK_DISABLED=$NEXT_PUBLIC_OAUTH_FACEBOOK_DISABLED
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# next.config.ts imports serverConfig, which reads API_BASE_URL/BACKEND_SECRET_KEY.
# Pass build-time placeholders inline (not ENV) so `next build` doesn't choke and
# nothing secret-shaped is baked into the image; real values are injected at
# runtime in the runner (server modules read process.env per request).
RUN API_BASE_URL=http://backend:8000 BACKEND_SECRET_KEY=build-time-placeholder pnpm build

# --- runner: minimal standalone server ----------------------------------------
# `output: "standalone"` (next.config.ts) emits a self-contained server bundling
# only the traced dependencies, so the runner never carries the full node_modules
# or a package manager.
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

# Run as an unprivileged user.
RUN addgroup -g 1001 -S nodejs && adduser -u 1001 -S nextjs -G nodejs

# server.js + its traced node_modules; static assets and public/ are not traced,
# so they are copied explicitly alongside.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000
# API_BASE_URL and BACKEND_SECRET_KEY are supplied by compose at runtime.
CMD ["node", "server.js"]
