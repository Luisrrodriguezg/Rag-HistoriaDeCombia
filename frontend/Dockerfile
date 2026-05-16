# syntax=docker/dockerfile:1.7

# ────────────────────────────────────────────────────────────
# Stage 1: build the React app.
# ────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY tsconfig.json vite.config.ts tailwind.config.js postcss.config.js components.json index.html ./
COPY src ./src

ARG VITE_API_URL=http://localhost:8000
ARG VITE_KEYCLOAK_URL=http://localhost:8080
ARG VITE_KEYCLOAK_REALM=rag
ARG VITE_KEYCLOAK_CLIENT_ID=rag-frontend
ENV VITE_API_URL=$VITE_API_URL \
    VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL \
    VITE_KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM \
    VITE_KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID

RUN npm run build

# ────────────────────────────────────────────────────────────
# Stage 2: serve the static bundle with nginx.
# ────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
