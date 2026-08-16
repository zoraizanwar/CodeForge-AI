# Build Stage
FROM python:3.13-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production Stage
FROM python:3.13-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create Non-Root System User
RUN groupadd -g 1000 codeforge && \
    useradd -u 1000 -g codeforge -m -s /bin/bash codeforge

# Copy Python packages from builder
COPY --from=builder /root/.local /home/codeforge/.local
ENV PATH=/home/codeforge/.local/bin:$PATH

# Copy Backend Application Code
COPY --chown=codeforge:codeforge . .

# Create workspace directory with correct permissions
RUN mkdir -p workspaces && chown -R codeforge:codeforge /app

# Set Production Environment Variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENV=production \
    ENVIRONMENT=production

USER codeforge

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["sh", "./entrypoint.sh"]
