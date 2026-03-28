# ─── Stage 1: Dependencies ──────────────────────────────────────────────────
FROM python:3.12-slim AS deps

WORKDIR /app

# Install system deps needed for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 2: Application ──────────────────────────────────────────────────
FROM python:3.12-slim AS runner

WORKDIR /app

# Install runtime deps only (curl for healthcheck, libpq for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from deps stage
COPY --from=deps /install /usr/local

# Copy application code
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Health check against the liveness endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run as non-root
RUN useradd -m -r appuser
USER appuser

EXPOSE 8000

CMD ["./start.sh"]
