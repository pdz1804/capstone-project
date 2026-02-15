# Multi-stage build for React frontend
# Stage 1: Build
FROM node:20-alpine as builder

WORKDIR /app

LABEL stage=builder

# Install build dependencies
RUN apk add --no-cache \
    python3 \
    make \
    g++ \
    && echo "Build stage: Dependencies installed successfully"

# Copy package files
COPY package*.json ./
COPY vite.config.js ./
COPY tailwind.config.js ./
COPY postcss.config.js ./

# Install dependencies
RUN npm ci --frozen-lockfile && \
    echo "Build stage: npm dependencies installed ($(npm list --depth=0 | wc -l) total packages)" && \
    npm list --depth=0

# Copy source code
COPY src ./src
COPY index.html ./

# Accept build-time env vars for Vite
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Build the application with detailed output
RUN echo "===== FRONTEND BUILD LOG =====" && \
    echo "Node Version: $(node --version)" && \
    echo "npm Version: $(npm --version)" && \
    echo "Starting Vite build..." && \
    npm run build && \
    echo "Build completed successfully" && \
    echo "Build artifacts:" && ls -lh dist/

# Stage 2: Runtime (Nginx)
FROM nginx:alpine

LABEL maintainer="Your Team"

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf
COPY default.conf /etc/nginx/conf.d/

# Copy built assets from builder
COPY --from=builder /app/dist/ /usr/share/nginx/html/

# Create logs directory
RUN mkdir -p /var/log/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    echo "Runtime stage: nginx configured"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/health || exit 1

# Expose port
EXPOSE 3000

# Startup logging
RUN echo "=== Frontend Docker Image Build Complete ===" && \
    echo "Nginx Version: $(nginx -v 2>&1)" && \
    echo "Built assets:" && ls -la /usr/share/nginx/html/

# Start nginx with detailed logging
CMD ["sh", "-c", "\
    echo '===== FRONTEND STARTUP LOG =====' && \
    echo 'Timestamp:' $(date) && \
    echo 'Nginx Version:' $(nginx -v 2>&1) && \
    echo 'Available Assets:' && ls -lh /usr/share/nginx/html/ && \
    echo 'Starting nginx...' && \
    nginx -g 'daemon off;' \
    || (echo 'ERROR: Failed to start nginx' && exit 1)"]
