# Stage 1: Builder
FROM python:3.11-slim AS builder

# Copy the 'uv' binary directly from the official image
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

WORKDIR /app

# Install system dependencies required for compilation and cloning
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install poetry globally in the builder stage, not in the venv
# In order that it's not included in the final image
RUN pip install --no-cache-dir poetry==2.2.1 poetry-plugin-export==1.9.0 && \
    python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Clone and install TimesFM
WORKDIR /lib/timesfm
RUN git clone https://github.com/google-research/timesfm.git

WORKDIR /lib/timesfm/timesfm
RUN git checkout bf88c5dc88f6275b7071ebcd9051406c11435c0c && \
    rm -rf .git
ARG USE_JAX=false
RUN if [ "$USE_JAX" = "true" ]; then \
        # 1. Install TimesFM with Flax (this brings in the unwanted CUDA plugins)
        uv pip install --no-cache-dir .[flax]; \
        # 2. CRITICAL FIX: Explicitly remove the CUDA plugins that step 1 installed
        # If we don't do this, JAX will try to initialize CUDA on the TPU and crash.
        pip uninstall -y jax-cuda12-plugin jax-cuda12-pjrt; \
        # 3. Install the correct TPU support
        uv pip install --no-cache-dir "jax[tpu]>=0.4.35" -f https://storage.googleapis.com/jax-releases/libtpu_releases.html; \
    else \
        uv pip install --no-cache-dir .[torch]; \
    fi

# Copy configuration and install project dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt --output requirements.txt && \
    pip install --no-cache-dir -r requirements.txt


# Stage 2: Final image
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

ARG USE_JAX=false
ENV USE_JAX=${USE_JAX}

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY main.py utils.py ./

# Vertex AI requires listening on specific ports, usually 8080
ENV PORT=8080
EXPOSE $PORT

# Run the application
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT --log-level info"]
