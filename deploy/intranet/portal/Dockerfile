# syntax=docker/dockerfile:1
# SaintVision Intranet Portal Container (Card 156)
# Hardened, non-root, read-only rootfs compatible Nginx serving the apps/web SPA
# Pinned with exact verified multi-arch OCI index SHA256 digests from Docker Hub registry:
# - node:22-alpine: sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402
# - nginx:1.27-alpine: sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10

# Stage 1: Build Frontend Assets
FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS builder
WORKDIR /workspace

# Install web dependencies
COPY apps/web/package*.json ./apps/web/
WORKDIR /workspace/apps/web
RUN npm ci

# Copy web source and build production bundle
COPY apps/web/ ./
RUN npm run build

# Stage 2: Hardened Non-Root Nginx Runtime
FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10 AS runner

# Install curl and openssl for internal verified preflight probes (L1)
RUN apk add --no-cache curl openssl

# Configure non-root directories and temp paths for read-only rootfs compatibility
RUN mkdir -p /tmp/client_temp \
             /tmp/proxy_temp_path \
             /tmp/fastcgi_temp \
             /tmp/uwsgi_temp \
             /tmp/scgi_temp \
             /etc/nginx/certs \
             /etc/nginx/conf.d \
             /var/cache/nginx \
             /var/run \
             /usr/share/nginx/html \
    && chmod -R 1777 /tmp /var/cache/nginx /var/run

# Copy hardened nginx configuration and security headers snippet
COPY deploy/intranet/portal/nginx.conf /etc/nginx/nginx.conf
COPY deploy/intranet/portal/security-headers.conf /etc/nginx/security-headers.conf
COPY deploy/intranet/portal/conf.d/upstream.conf /etc/nginx/conf.d/upstream.conf

# Copy compiled static assets from builder
COPY --from=builder /workspace/apps/web/dist /usr/share/nginx/html

# Deploy intranet portal OIDC configuration
COPY deploy/intranet/portal/auth-config.js /usr/share/nginx/html/auth-config.js

# Coordinator Decision B2/Codex3: Static HTML assets are public/non-secret, owned by root:root
# Directories: 0555 (r-x), Files: 0444 (r--)
RUN chown -R root:root /usr/share/nginx/html \
    && find /usr/share/nginx/html -type d -exec chmod 0555 {} + \
    && find /usr/share/nginx/html -type f -exec chmod 0444 {} +

# Standard owner label tuple
LABEL ai.saintvision.service="portal"
LABEL ai.saintvision.workload="intranet-portal"
LABEL ai.saintvision.node="node2"
LABEL ai.saintvision.role="web-portal"

# Expose HTTP (80 -> redirect) and HTTPS (443)
EXPOSE 80 443

# Non-root default user (runtime --user overrides, M2)
USER 101:101

# Start Nginx in foreground (single source of daemon off)
CMD ["nginx", "-g", "daemon off;"]
