# Menu Service

A Quarkus-based RESTful service for managing restaurant menu items.

## Project Overview

- **Purpose:** Provides a REST API for CRUD operations on restaurant menu items.
- **Technology Stack:**
  - **Language:** Java 11
  - **Framework:** Quarkus 3.8.3
  - **Persistence:** Hibernate ORM with Panache, PostgreSQL (Production), H2 (Development/Test)
  - **API:** JAX-RS (RESTEasy) with Jackson for JSON processing
  - **Containerization:** Jib (Google Cloud Tools)
- **Architecture:** Layered architecture consisting of:
  - `MenuResource`: JAX-RS resource defining API endpoints.
  - `MenuRepository`: Panache repository for data access.
  - `Menu`: Panache entity representing the menu item data model.
  - `Status`: Enum representing the lifecycle status of a menu item (Processing, Ready, Failed).

## Building and Running

### Prerequisites
- JDK 11 or higher
- Maven (or use the provided `./mvnw` wrapper)

### Common Commands

| Task | Command |
| :--- | :--- |
| **Run in Dev Mode** | `./mvnw quarkus:dev` |
| **Run Tests** | `./mvnw test` |
| **Package Application** | `./mvnw package` |
| **Run Native Build** | `./mvnw package -Pnative` |
| **Build Container Image** | `./mvnw package -Dquarkus.container-image.build=true` |
| **Clean Project** | `./mvnw clean` |

## API Endpoints

The API is exposed at the `/menu` base path.

- `GET /menu`: List all menu items (sorted by name).
- `GET /menu/{id}`: Get a specific menu item by ID.
- `GET /menu/ready`: List all items with `Ready` status.
- `GET /menu/failed`: List all items with `Failed` status.
- `GET /menu/processing`: List all items with `Processing` status.
- `POST /menu`: Create a new menu item.
- `PUT /menu/{id}`: Update an existing menu item.
- `DELETE /menu/{id}`: Delete a menu item.

## Development Conventions

- **Data Access:** Always use Panache for database operations. Prefer `PanacheRepository` for better testability (mocking).
- **Testing:** 
  - Use `@QuarkusTest` for integration tests.
  - Use `RestAssured` for API-level assertions.
  - Use `@InjectMock` to mock repositories in resource tests.
- **Error Handling:** Use `WebApplicationException` with appropriate HTTP status codes for API errors.
- **Configuration:** Main configuration is in `src/main/resources/application.properties`.

## Directory Structure

- `src/main/java/org/google/demo/`: Core application logic (Entities, Repositories, Resources).
- `src/main/resources/`: Configuration and static assets.
- `src/test/java/org/google/demo/`: Unit and integration tests.
