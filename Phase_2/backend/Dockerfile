# Multi-stage build for Python backend
# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Create wheels for all dependencies (faster installation in final stage)
RUN pip install --user --no-cache-dir --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt && \
    echo "Build stage: Python dependencies installed successfully"

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/ && \
    echo "Runtime stage: System dependencies installed successfully"

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Set environment variables
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app:/app/api

# Verify Python installation
RUN python --version && \
    echo "Python installation verified"

# Copy application code
COPY . .

# Create necessary directories for logs
RUN mkdir -p /app/logs && \
    echo "Logs directory created"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# Expose port
EXPOSE 5000

# Logging
RUN echo "=== Backend Docker Image Build Complete ===" && \
    echo "Python: $(python --version)" && \
    echo "Working Directory: $(pwd)" && \
    echo "Files:" && ls -la /app/

# Run FastAPI application with detailed logging
CMD ["sh", "-c", "\
    echo '===== BACKEND STARTUP LOG =====' && \
    echo 'Timestamp:' $(date) && \
    echo 'Python Version:' $(python --version) && \
    echo 'Current Directory:' $(pwd) && \
    echo 'Environment Variables:' && \
    env | grep -E '(AWS|BACKEND|DATABASE|LOG)' || echo 'No AWS/Backend env vars set' && \
    echo 'Starting FastAPI server...' && \
    python -m uvicorn api.main:app --host 0.0.0.0 --port 5000 --log-level info \
    || (echo 'ERROR: Failed to start FastAPI server' && exit 1)"]
