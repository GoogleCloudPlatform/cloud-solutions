<!-- Allow increasing ordered list prefixes to avoid confusing the LLM -->
<!-- markdownlint-disable MD029 -->
<!-- Start copying the prompt after this comment -->

# .NET application modernization

## Role

Act as a Senior Cloud Architect and .NET Developer. Your goal is to:

- Port a legacy .NET 5 application to .NET 8 (Core).
- Refactor an existing .NET application into a containerized application
  suitable for Google Cloud Run.
- Refactor the application's data layer from SQL Server to PostgreSQL.
- You MUST NOT add, remove, or change business logic. Create a faithful, 1:1
  replication of features, API contracts, and UI behavior.
- You MUST explain every action you take.

## Context

I will provide:

1.  The .NET source code for the application.

## Instructions

### 1. Code Refactoring (Application Layer)

Refactor the .NET logic into a production-ready web service.

- **.NET refactoring**:
    - Analyze the existing codebase to understand its structure and
      dependencies.
    - Convert the project SDK to .NET 8, convert `web.config` to
      `appsettings.json`, and handle the dependency injection changes
      (`Program.cs` and `Startup.cs`).
    - Convert the `.csproj` to the modern SDK-style format targeting .NET 8.
    - Refactor Global.asax.cs logic into the modern `Program.cs` middleware
      pipeline and DI container.
    - EF Migration: Replace `System.Data.Entity` (EF6) with
      `Microsoft.EntityFrameworkCore`.
    - Use Entity Framework Core, and not Dapper.
    - PostgreSQL Provider: Use `Npgsql.EntityFrameworkCore.PostgreSQL`.
    - Schema initialization:
        - Analyze existing `DropCreateDatabaseIfModelChanges` or
          `IDatabaseInitializer` classes.
        - Refactor these into a dedicated DbInitializer class that utilizes
          context.Database.EnsureCreated() or applies migrations at startup (if
          appropriate for a demo) or generates a SQL migration script.
        - Seeding: Refactor any Seed methods to work with the EF Core
          ModelBuilder or a custom seeding service ensuring data is populated if
          the DB is empty.
    - Do not delete DAL files unless absolutely necessary; refactor them to
      maintain class structure where possible to minimize logic drift.
    - To keep the structure of the application as close as possible to the
      application, you MUST refactor existing source code files, rather then
      deleting and creating new ones, whenever possible.
    - You MUST NOT delete any needed functional component when migrating to EF
      Core. If you encounter any issue due to using the old Entity framework
      (such as `System.Data.Entity` imports), you MUST refactor those classes,
      instead of deleting them, if possible.

- **Cloud Run Container Contract Compliance**
  (https://docs.cloud.google.com/run/docs/container-contract):
    - **Port Binding:** The application must listen on 0.0.0.0 on the port
      defined by the PORT environment variable (defaulting to 8080 if
      undefined).
    - **Logging:**
        - Remove any file-based logging (e.g., Log4Net file appenders).
        - Configure ILogger to write structured JSON logs to Console (stdout)
          for Cloud Logging ingestion.

- **Concurrency & Safety**:
    - Identify any usage of `HttpRuntime.Cache` or static lists. Replace them
      with `IMemoryCache` and add comments warning about scalability issues in a
      stateless serverless environment.
    - Implement a signal handler for `SIGTERM` to allow graceful shutdown.

- **Running tools**:
    - You MUST NOT run `dotnet` tools on the host. Run them in a Docker
      container, if necessary.
    - Whenever you run a Docker container, add the `--rm` option to the
      `docker run` command.

## 2. Dockerfile Generation

Write a `Dockerfile` following these best practices:

- **Base Image:**
    - Multi-Stage Build: Use the official `mcr.microsoft.com/dotnet/sdk:8.0` for
      building and `mcr.microsoft.com/dotnet/aspnet:8.0` for the runtime.
- **Optimization:** Clean up caches and apt-get lists to minimize image size.
- **Build checks**: Ensure that the Dockerfile passes all docker build checks.
  Read about Docker build checks
  (https://docs.docker.com/reference/build-checks/) and ensure that the
  Dockerfile passes all the checks. Here are the instructions to run Docker
  build checks without actually building the image:
  https://docs.docker.com/build/checks/#check-a-build-without-building. Run
  Docker build checks without building the image by running:
  `docker build --check .`

## 3. Docker Compose generation

Write a Docker Compose file named `compose.yaml` to test the refactored
application locally. The compose file should:

- Run a PostgreSQL instance for the application to use. Do not create the
  database, because the .NET application will create it.
- Run the .NET application
- Not include a `version` attribute because newer Compose Specs consider the
  `version` attribute as deprecated.
- Not include a definition for the `POSTGRES_DB` environment variable in the
  service definition that runs the PostgreSQL database container, so the .NET
  application will trigger the database initialization.
- Include a healthcheck for the PostgreSQL container to check if the database is
  ready before starting the .NET application container. You MUST NOT depend on
  the `contosouniversity` database being present when you build the healthcheck.
  Use the `pg_isready` command to build the healthcheck.
- Pass the connection string to the app service using environment variables.

## 4. Documentation

Create a modernization report in the MODERNIZATION.md file with:

- **Modernization Notes:** A summary of changes, specifically pointing out the
  `MockContext` implementation.
- **Local Testing:** Specific `docker build`, `docker run`, and `docker compose`
  commands.
    - Ensure that all `docker run` commands have the `--rm` flag.
    - Add the `--detach` and the `--build` options to the `docker compose up`
      command.
    - Explain how to run `docker compose logs` to get logs of the running
      application and database.
- **Endpoints**: A table containing all the HTTP endpoints that the application
  supports.

## 5. Build the container image

Try building the container image by running the `docker build` command you wrote
in the `MODERNIZATION.md` file.

Fix any error you encounter when building the container image.

## 6. Try running the .NET application container

Try running the .NET application container by doing the following:

1.  Run the Docker Compose application: `docker compose up --build --detach`
2.  Get Docker Compose logs:
    1.  Run the `docker compose logs` command.
    2.  If the output of the the `docker compose logs` command is the same as
        the last time you ran it, wait for 15 secondos.
    3.  Run the `docker compose logs` command again.
    4.  If the output of the the `docker compose logs` command is the same as
        the last time you ran it, stop the Docker Compose application by running
        `docker compose stop`

3.  If Docker Compose exits with an error, examine the error. Fix any error you
    encounter when running the application. If you see an error connecting to
    `contosouniversity` database, but the application starts successfully,
    ignore this error. This is a test that .NET uses to check if it needs to
    create the database or not.
4.  If you edit the `Dockerfile` or the .NET application source, rebuild the
    container image by running the `docker build` command you wrote in the
    `MODERNIZATION.md` file.
5.  After each run, either successful or unsuccessful, run the following
    commands:
    1.  Stop Docker Compose: `docker compose stop`
    2.  Remove containers: `docker compose rm --force`

Show the output of the commands you run.

## 7. Try sending HTTP requests

Test HTTP endpoints the .NET application:

1.  List all the HTTP endpoints not just the GET endpoints that the application
    supports and show me the output.
2.  Run the `docker compose up --build --detach` command.
3.  Wait for the .NET application to initialize the database.
4.  You MUST test ALL the HTTP endpoints (e.g. GET, POST, DELETE), not just the
    GET endpoints. For each HTTP endpoint, do the following:
    1.  Send a properly crafted request. Load anti-forgery tokens and cookies as
        if needed, and store them in text files.
    2.  Get Docker Compose logs by running the `docker compose logs` command.
    3.  If you encounter an error, stop the application and fix the error.
    4.  If you edit the Dockerfile or any file of the .NET application, rebuild
        the container image by running the `docker build` command you wrote in
        the `MODERNIZATION.md` file, and run the Docker Compose application
        again with the `docker compose up --build --detach` command.
    5.  Wait for the .NET application to initialize the database.
    6.  Test the endpoint again by sending a GET request

When you're done with testing, do the following:

1.  Stop Docker Compose: `docker compose stop`
2.  Remove containers: `docker compose rm --force`
3.  Add a section in `MODERNIZATION.md` that reports on which HTTP endpoints you
    tested. The section should have a table that lists the endpoint, the HTTP
    method, the command used to test the endpoint, and the command output. If
    the `MODERNIZATION.md` file already contains that section, update it with
    the latest test report.
4.  Delete the files you created to store cookies and anti-forgery tokens.

Show the output of the commands you run.

## 8. Test the .NET application in a browser

Perform an automated UI smoke test using the Chrome DevTools MCP tools
(new_page, click, take_screenshot, etc.) to validate the frontend:

- Follow all links to views
- Exexute CRUD tests in views
- Validate pagination and sorting functionality
- Make sure there are no missing resources that result in 404 errors, such as
  CSS files, JavaScript files, images, and any other media file.

1.  **Startup:** Ensure the application is running via `docker compose` using
    the `docker compose up --build --detach` command.
2.  **Asset Integrity Check:**
    1.  Navigate to the application root (e.g., `http://localhost:8080`).
    2.  Inspect the **Network** activity. Verify that all static resources (CSS,
        JavaScript, Images) load with `200 OK` status codes.
    3.  **Critical:** If you detect `404 Not Found` for assets (common in .NET
        migrations), fix the static file middleware configuration in
        `Program.cs` or adjust the `Dockerfile` copy paths.
3.  **Functional Crawl:** 4. **Navigation:** Identify and follow links to all
    major views. 5. **Data Grids:** If a table is present, test **Pagination**
    (next/prev pages) and **Sorting** (click column headers) to ensure EF Core
    translation is correct. 6. **CRUD Operations:** Perform a full Create, Read,
    Update, and Delete cycle on a main entity (e.g., Students/Courses) to verify
    the PostgreSQL data layer.
4.  **Console Health:** Check the Browser Console for any JavaScript errors and
    report or fix them.
