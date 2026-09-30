# syntax=docker/dockerfile:1
# SaintVision Intranet Portal Container (Card 156)
# Hardened, non-root, read-only rootfs compatible Nginx serving the apps/web SPA
# Pinned with exact immutable base image SHA256 digests

# Stage 1: Build Frontend Assets
FROM node:22-alpine@sha256:d13e9a7863be2441a12a52bf874e892d92ee436057e4e4a706ae9958dbcf19f2 AS builder
WORKDIR /workspace

# Install web dependencies
COPY apps/web/package*.json ./apps/web/
WORKDIR /workspace/apps/web
RUN npm ci

# Copy web source and build production bundle
COPY apps/web/ ./
RUN npm run build

# Stage 2: Hardened Non-Root Nginx Runtime
FROM nginx:1.27-alpine@sha256:4ff2f67629aa393306db7e35db838dc86e2468bd8b9ad43e2e8e040ffc91b5ff AS runner

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
    && chown -R 101:101 /tmp /var/cache/nginx /var/run /etc/nginx /usr/share/nginx/html \
    && chmod -R 770 /tmp /var/cache/nginx /var/run

# Copy hardened nginx configuration and security headers snippet
COPY deploy/intranet/portal/nginx.conf /etc/nginx/nginx.conf
COPY deploy/intranet/portal/security-headers.conf /etc/nginx/security-headers.conf
COPY deploy/intranet/portal/conf.d/upstream.conf /etc/nginx/conf.d/upstream.conf

# Copy compiled static assets from builder
COPY --from=builder /workspace/apps/web/dist /usr/share/nginx/html

# Deploy intranet portal OIDC configuration
COPY deploy/intranet/portal/auth-config.js /usr/share/nginx/html/auth-config.js

# Ensure non-root ownership and read-only static permissions
RUN chown -R 101:101 /usr/share/nginx/html \
    && chmod -R 550 /usr/share/nginx/html

# Standard owner label tuple
LABEL ai.saintvision.service="portal"
LABEL ai.saintvision.workload="intranet-portal"
LABEL ai.saintvision.node="node2"
LABEL ai.saintvision.role="web-portal"

# Run as unprivileged nginx user (UID:GID 101:101)
USER 101:101

# Expose HTTP (80 -> redirect) and HTTPS (443)
EXPOSE 80 443

# Start Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
