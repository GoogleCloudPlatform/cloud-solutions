
# Menu Service

This project is a Quarkus-based microservice for managing restaurant menu items. It provides a RESTful API to perform CRUD operations on menu items, storing them in a database.

## Technologies

- **Java 11**
- **Quarkus 3.8.3**
- **Hibernate ORM with Panache:** Simplifies JPA entities and repositories.
- **PostgreSQL:** Production database (H2 in-memory is used for development/testing by default).
- **RESTeasy Jackson:** For JAX-RS and JSON support.
- **Jib:** For building optimized Docker and OCI container images.
- **JUnit 5 & REST Assured:** For testing.

## Project Structure

- `src/main/java/org/google/demo/`:
    - `Menu.java`: The JPA entity representing a menu item.
    - `MenuResource.java`: The REST API controller (endpoints at `/menu`).
    - `MenuRepository.java`: Repository for database operations.
    - `Status.java`: Enum for tracking the processing state of menu items.
- `src/main/resources/application.properties`: Configuration for the Quarkus application, including datasource settings.
- `pom.xml`: Maven configuration with dependencies and build plugins.

## REST API Endpoints

The service exposes the following endpoints under `/menu`:

- `GET /menu`: Returns all menu items sorted by name.
- `GET /menu/{id}`: Returns a specific menu item by ID.
- `GET /menu/ready`: Returns items with status `Ready`.
- `GET /menu/failed`: Returns items with status `Failed`.
- `GET /menu/processing`: Returns items with status `Processing`.
- `POST /menu`: Creates a new menu item (sets status to `Processing`).
- `PUT /menu/{id}`: Updates an existing menu item.
- `DELETE /menu/{id}`: Deletes a menu item.

## Building and Running

### Development Mode

To run the application in development mode (with live coding enabled):

```bash
./mvnw quarkus:dev
```

### Running Tests

To execute the unit and integration tests:

```bash
./mvnw test
```

### Packaging

To build a runnable JAR:

```bash
./mvnw package
```

### Building Container Image

To build a container image locally using Jib:

```bash
./mvnw compile jib:dockerBuild
```

To push to a remote registry:

```bash
./mvnw compile jib:build -Dimage=<your-image-name>
```

## Development Conventions

- **Panache Pattern:** Use Panache entities and repositories for data access.
- **Standard JAX-RS:** Use standard annotations (`@GET`, `@POST`, etc.) for REST endpoints.
- **Transactional:** Use `@Transactional` on methods that modify database state.
- **Testing:** New features should include corresponding tests in `src/test/java/org/google/demo/MenuResourceTest.java` using REST Assured.
