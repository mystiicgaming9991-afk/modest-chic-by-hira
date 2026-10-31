# Modest Chic Backend — production Docker image
FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

# Application
COPY src/ src/
COPY migrations/ migrations/
COPY alembic.ini .

# Non-root user
RUN groupadd --gid 10001 modest \
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash modest \
    && chown -R modest:modest /app
USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD ["curl", "-fsS", "http://localhost:8000/health/ready"]

CMD ["uv", "run", "uvicorn", "modest_chic_backend.main:create_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8000"]
