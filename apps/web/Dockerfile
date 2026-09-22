# Stage 1: Build Frontend Assets
FROM node:22-alpine AS builder

WORKDIR /app

# Copy dependency specifications
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source code and build
COPY . .
RUN npm run build

# Stage 2: Serve with Production Nginx
FROM nginx:1.27-alpine

# Copy built static assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy optimized intranet reverse proxy configuration
COPY nginx.conf /etc/nginx/nginx.conf
COPY security-headers.conf /etc/nginx/security-headers.conf

# Expose HTTPS port
EXPOSE 443

# Healthcheck for zero-downtime deployment verification
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
