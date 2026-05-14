# Use a slim Python base image
FROM python:3.11-slim

# Install uv from the official image
COPY --from=ghcr.io/astral-sh/uv:0.5.15 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# Set the working directory inside the container
WORKDIR /workspace

# Copy dependency files first to take advantage of Docker layer caching
COPY pyproject.toml uv.lock README.md ./

# Install the dependencies (excluding development dependencies).
# We omit --frozen here to allow uv to self-update the lockfile in the build environment
# since the project was recently renamed from bidi-demo to tech-assistant.
RUN uv sync --frozen --no-dev

# Copy the application source code
COPY app ./app

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Expose the port Cloud Run expects
# EXPOSE 8080

# Change working directory to the app folder to ensure relative imports resolve correctly
WORKDIR /workspace/app

# Start the FastAPI application using uvicorn under uv run
# CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
CMD ["sh", "-c", "uv run --project .. uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
