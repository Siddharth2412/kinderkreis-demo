# ---- build stage: compile the static bundle ----
FROM node:20-slim AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---- production stage: serve the static build ----
# nginx:alpine idles at a few MB of RAM, vs. hundreds of MB for the Vite dev
# server this replaces — the difference that actually matters on a small VPS.
FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 5173
