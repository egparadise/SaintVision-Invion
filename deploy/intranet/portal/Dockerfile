# syntax=docker/dockerfile:1
# SaintVision Intranet Portal Container (Card 156)
# Hardened, non-root, read-only rootfs compatible Nginx serving the apps/web SPA

# Stage 1: Build Frontend Assets
FROM node:20-alpine AS builder
WORKDIR /workspace

# Install web dependencies
COPY apps/web/package*.json ./apps/web/
WORKDIR /workspace/apps/web
RUN npm ci

# Copy web source and build production bundle
COPY apps/web/ ./
RUN npm run build

# Stage 2: Hardened Non-Root Nginx Runtime
FROM nginx:1.27-alpine AS runner

# Configure non-root directories and temp paths for read-only rootfs compatibility
RUN mkdir -p /tmp/client_temp \
             /tmp/proxy_temp_path \
             /tmp/fastcgi_temp \
             /tmp/uwsgi_temp \
             /tmp/scgi_temp \
             /etc/nginx/certs \
             /var/cache/nginx \
             /var/run \
    && chown -R 101:101 /tmp /var/cache/nginx /var/run /etc/nginx /usr/share/nginx/html \
    && chmod -R 770 /tmp /var/cache/nginx /var/run

# Copy hardened nginx configuration
COPY deploy/intranet/portal/nginx.conf /etc/nginx/nginx.conf

# Copy compiled static assets from builder
COPY --from=builder /workspace/apps/web/dist /usr/share/nginx/html

# Deploy intranet portal OIDC configuration
COPY deploy/intranet/portal/auth-config.js /usr/share/nginx/html/auth-config.js

# Ensure non-root ownership and read-only static permissions
RUN chown -R 101:101 /usr/share/nginx/html \
    && chmod -R 550 /usr/share/nginx/html

# Owner labels for node container lifecycle management
LABEL ai.saintvision.service="portal"
LABEL ai.saintvision.role="web-portal"
LABEL ai.saintvision.node="node2"
LABEL ai.saintvision.workload="intranet-portal"

# Run as unprivileged nginx user (UID:GID 101:101)
USER 101:101

# Expose HTTP (80 -> redirect) and HTTPS (443)
EXPOSE 80 443

# Start Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
