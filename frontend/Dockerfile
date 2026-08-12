# ---- build stage: compile the static bundle ----
FROM node:20-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite bakes every VITE_* variable into the compiled JS at build time — a
# docker-compose `environment:` entry on the final container would be too
# late (the bundle is already static by then), so this has to come in as a
# build ARG instead. Defaults to the local dev backend so a plain
# `docker build` still works without any arg.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---- production stage: serve the static build ----
# nginx:alpine idles at a few MB of RAM, vs. hundreds of MB for the Vite dev
# server this replaces — the difference that actually matters on a small VPS.
FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# The self-signed TLS cert (nginx.conf's ssl_certificate/ssl_certificate_key)
# is generated once on the VM by scripts/setup-vm.sh and bind-mounted in at
# /etc/nginx/ssl via docker-compose.prod.yml — not baked into the image here.
# That's both faster to build (no apk install + keygen on every deploy) and
# keeps the cert's fingerprint stable across deploys, so browsers don't make
# you re-accept the untrusted-cert warning after every single push.

EXPOSE 5173 8443
