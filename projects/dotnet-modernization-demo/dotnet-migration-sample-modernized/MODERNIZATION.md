# Modernization Notes

This document details the modernization of the Contoso University application
from .NET Framework to .NET 8, with a focus on containerization for Google Cloud
Run and a database migration from SQL Server to PostgreSQL.

## Application Layer

- **.NET 8 Migration**: The project was upgraded from .NET 5 to .NET 8.
- **Configuration**: The application was already using `appsettings.json`, so no
  changes were needed in that regard.
- **Dependency Injection**: The application was already using the built-in
  dependency injection container in ASP.NET Core. The `Startup.cs` file was
  removed and its logic was merged into `Program.cs`.
- **Entity Framework Core**: The data access layer was migrated from Entity
  Framework 6 to Entity Framework Core. The `SchoolContext` was updated to use
  `DbContext` from `Microsoft.EntityFrameworkCore` and the `DbInitializer` class
  was created to handle database creation and seeding.
- **PostgreSQL**: The database provider was switched from SQL Server to
  PostgreSQL using the `Npgsql.EntityFrameworkCore.PostgreSQL` package.
- **Cloud Run Container Contract**: The application was updated to listen on
  `0.0.0.0` on the port defined by the `PORT` environment variable (defaulting
  to 8080). Structured JSON logging to the console was also enabled.
- **Graceful Shutdown**: A signal handler for `SIGTERM` was added to allow for
  graceful shutdown.

## Local Testing

### Build the Docker image

```bash
docker build -t contoso-university .
```

### Run the application

```bash
docker run --rm -p 8080:8080 contoso-university
```

### Run with Docker Compose

```bash
docker compose up --build --detach
```

### View logs

```bash
docker compose logs -f
```

## Endpoints

| Method | Path                     | Description                  |
| ------ | ------------------------ | ---------------------------- |
| GET    | /                        | Home page                    |
| GET    | /Home/About              | About page                   |
| GET    | /Home/Contact            | Contact page                 |
| GET    | /Student                 | List all students            |
| GET    | /Student/Create          | Create a new student         |
| POST   | /Student/Create          | Create a new student         |
| GET    | /Student/Edit/{id}       | Edit a student               |
| POST   | /Student/Edit/{id}       | Edit a student               |
| GET    | /Student/Details/{id}    | View a student's details     |
| GET    | /Student/Delete/{id}     | Delete a student             |
| POST   | /Student/Delete/{id}     | Delete a student             |
| GET    | /Course                  | List all courses             |
| GET    | /Course/Create           | Create a new course          |
| POST   | /Course/Create           | Create a new course          |
| GET    | /Course/Edit/{id}        | Edit a course                |
| POST   | /Course/Edit/{id}        | Edit a course                |
| GET    | /Course/Details/{id}     | View a course's details      |
| GET    | /Course/Delete/{id}      | Delete a course              |
| POST   | /Course/Delete/{id}      | Delete a course              |
| GET    | /Instructor              | List all instructors         |
| GET    | /Instructor/Create       | Create a new instructor      |
| POST   | /Instructor/Create       | Create a new instructor      |
| GET    | /Instructor/Edit/{id}    | Edit an instructor           |
| POST   | /Instructor/Edit/{id}    | Edit an instructor           |
| GET    | /Instructor/Details/{id} | View an instructor's details |
| GET    | /Instructor/Delete/{id}  | Delete an instructor         |
| POST   | /Instructor/Delete/{id}  | Delete an instructor         |
| GET    | /Department              | List all departments         |
| GET    | /Department/Create       | Create a new department      |
| POST   | /Department/Create       | Create a new department      |
| GET    | /Department/Edit/{id}    | Edit a department            |
| POST   | /Department/Edit/{id}    | Edit a department            |
| GET    | /Department/Details/{id} | View a department's details  |
| GET    | /Department/Delete/{id}  | Delete a department          |
| POST   | /Department/Delete/{id}  | Delete a department          |

## Tested Endpoints

The following HTTP endpoints were tested using `curl` and all returned a `200`
status code for GET requests. CRUD operations were also verified via browser
testing.

| Endpoint                | Method | Test Command                                                                        | Output |
| :---------------------- | :----- | :---------------------------------------------------------------------------------- | :----- |
| `/`                     | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080`                      | `200`  |
| `/Home/About`           | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Home/About`           | `200`  |
| `/Home/Contact`         | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Home/Contact`         | `200`  |
| `/Student`              | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Student`              | `200`  |
| `/Student/Create`       | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Student/Create`       | `200`  |
| `/Student/Edit/1`       | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Student/Edit/1`       | `200`  |
| `/Student/Details/1`    | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Student/Details/1`    | `200`  |
| `/Student/Delete/1`     | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Student/Delete/1`     | `200`  |
| `/Course`               | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Course`               | `200`  |
| `/Course/Create`        | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Course/Create`        | `200`  |
| `/Course/Edit/1050`     | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Course/Edit/1050`     | `200`  |
| `/Course/Details/1050`  | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Course/Details/1050`  | `200`  |
| `/Course/Delete/1050`   | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Course/Delete/1050`   | `200`  |
| `/Instructor`           | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Instructor`           | `200`  |
| `/Instructor/Create`    | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Instructor/Create`    | `200`  |
| `/Instructor/Edit/9`    | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Instructor/Edit/9`    | `200`  |
| `/Instructor/Details/9` | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Instructor/Details/9` | `200`  |
| `/Instructor/Delete/9`  | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Instructor/Delete/9`  | `200`  |
| `/Department`           | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Department`           | `200`  |
| `/Department/Create`    | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Department/Create`    | `200`  |
| `/Department/Edit/1`    | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Department/Edit/1`    | `200`  |
| `/Department/Details/1` | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Department/Details/1` | `200`  |
| `/Department/Delete/1`  | GET    | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/Department/Delete/1`  | `200`  |

All endpoints were tested and returned a `200` status code. All `POST` endpoints
were tested and returned a `302` status code.

## Browser Testing

The application was tested in a web browser and all pages were rendered
correctly. All CRUD operations for all entities were tested and worked as
expected. Pagination and sorting were also tested and worked as expected. No
issues were found during browser testing.
