---
trigger: model_decision
description: >-
  Python development standards covering prerequisites, virtual environment
  isolation, dependency pinning, PEP 8 style, modularity, documentation,
  runtime configuration, error handling, and container builds. Apply when
  generating or modifying Python application code.
---

# Development rules

## Prerequisites

- **Python version and system tools:** Require Python 3.11 or higher, `uv` or
  `pip-tools`, and document any required OS-level packages.
- **Virtual environment isolation:** Create and activate a local Python virtual
  environment (`venv`) for all tooling and command executions. Do not install
  packages globally.
- **Dependency specification and compilation:**
    - Define direct dependencies with major-version bounds in `requirements.in`.
    - Compile pinned lockfiles with hashes into `requirements.txt` using
      `pip-compile` or `uv pip compile` with `--generate-hashes` and
      `--output-file=requirements.txt requirements.in`.
    - Install dependencies strictly using
      `./venv/bin/pip install --require-hashes -r requirements.txt` or sync
      using `pip-sync` or `uv pip sync`. Do not run bare `pip install <pkg>`.
- **Workspace hygiene:** Exclude `venv/`, `.venv/`, `__pycache__/`, local `.db`
  and `.sqlite3` files, `.env` files, and `.agents/mcp_config.json` in
  `.gitignore`.

## Code architecture and style

- **Copyright headers:** Include the required copyright and license header at
  the top of source files.
- **PEP 8 and type annotations:** Follow the PEP 8 style guide and include type
  annotations on function signatures.
- **Modularity:** Decompose application logic into small, single-responsibility
  functions that can be independently unit tested.
- **Template separation:** Place HTML templates in a dedicated `templates/`
  directory rather than embedding large HTML strings in Python code.
- **Documentation:** Add descriptive module, class, and function docstrings, and
  include concise inline comments for non-obvious logic.

## Runtime rules and configuration

- **Environment variable resolution:** Retrieve runtime configurations, API
  keys, and project IDs strictly from environment variables, such as by using
  `pydantic-settings` or `python-dotenv`. Never hardcode secrets, and check in a
  template `.env.example` file.
- **Logging and output:** Use Python's standard `logging` module with explicit
  log levels (`INFO`, `WARNING`, `ERROR`). Do not use bare `print()` statements
  in application code.
- **Granular exception handling:** Catch explicit exception types rather than
  using bare `except:` blocks, and fail gracefully with structured error
  messages without exposing internal stack traces.

## Container build standards

Apply these rules when containerizing the application or when a `Dockerfile` is
present in the project:

- **Base image selection:** Use official, pinned slim or distroless base images,
  such as `python:3.11-slim` or `gcr.io/distroless/python3-debian12`, rather
  than full OS distributions or mutable tags like `:latest`.
- **Multi-stage builds:** Separate the build and compilation environment from
  the final runtime image:
    - Install compiler tools, build dependencies, and wheels in a `builder`
      stage.
    - Copy only installed packages and application source into the final runtime
      stage to keep image size small and minimize the attack surface.
- **Layer caching optimization:** Order `Dockerfile` instructions to leverage
  the build cache by copying dependency lockfiles (`requirements.txt`) and
  running `pip install --require-hashes -r requirements.txt` before copying
  application source code (`COPY . .`).
- **Non-root execution:** Create and switch to a dedicated non-root user
  (`USER nonroot` or `USER appuser`) before running the application. Never run
  container processes as `root`.
- **Reproducible build context:** When a `Dockerfile` is present, maintain a
  `.dockerignore` file mirroring `.gitignore` to exclude `.git`, `venv/`,
  `.venv/`, local caches, `.env` files, and build artifacts from the build
  context.
- **Signal handling and PID 1:** Use `exec` form for container entrypoints, such
  as `ENTRYPOINT ["python", "-m", "app.main"]`, so operating system signals
  (`SIGTERM`, `SIGINT`) propagate cleanly for graceful shutdowns.
