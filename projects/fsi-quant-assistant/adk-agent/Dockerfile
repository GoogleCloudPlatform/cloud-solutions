FROM python:3.11-slim
WORKDIR /app

# Prevent Poetry from creating a virtual environment within the container
# This is a best practice for Docker, as the container itself provides isolation.
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Install build-essential using apt-get
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Set strict env variables for the installer
ENV POETRY_VERSION=2.2.1
ENV POETRY_HOME=/opt/poetry

# Set shell to bash with pipefail for safe piping
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install using the official script
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add poetry to your PATH
ENV PATH="$POETRY_HOME/bin:$PATH"

# Copy only the dependency file first to leverage Docker's layer caching
# This layer will only be rebuilt if these files change.
#COPY pyproject.toml poetry.lock* ./
COPY pyproject.toml ./

# Install project dependencies as root
# This will prevent permission errors when installing system-level dependencies
RUN poetry install --only main --no-root

# Create the application user and set the work directory ownership.
RUN adduser --disabled-password --gecos "" myuser && \
    chown -R myuser:myuser /app

# Switch to the new application user.
# All subsequent commands will run as 'myuser' by default.
USER myuser

# Set the PATH for the new user
ENV PATH="/home/myuser/.local/bin:$PATH" \
    PORT=8080

# Copy the rest of your application code
COPY --chown=myuser:myuser . .

# Expose the port for the application (optional, but good practice)
EXPOSE $PORT

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
