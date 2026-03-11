# Agentic development with Antigravity

This guide shows you how to use Antigravity to build and deploy microservices.
You use Cloud SQL for PostgreSQL for the database and deploy the application to
Google Kubernetes Engine (GKE).

The guide includes the following steps:

1.  **Set up your environment and workspace:** Install Antigravity, configure a
    workspace, and review development mode settings.
1.  **Generate the domain model:** Use a Domain-Driven Design (DDD) approach to
    create functional specs, ubiquitous language, and bounded contexts.
1.  **Design database schemas and generate Data Definition Language (DDL)
    scripts:** Convert domain model entities into standalone DDL scripts for
    each specific domain while maintaining logical references across domains.
1.  **Design and implement the microservices:** Generate Spring Boot source code
    for all DDD layers, implement inter-service communication through OpenFeign,
    and define OpenAPI contracts.
1.  **Generate sample data:** Generate and initialize realistic sample data
    across all schemas and verify the results through the Swagger UI.
1.  **Generate unit and integration tests for microservices:** Develop a test
    suite to ensure service reliability and coverage of both success and error
    scenarios.
1.  **Generate project documentation:** Create essential README files and
    Unified Modeling Language (UML) diagrams (class and sequence) for the order
    creation workflow.
1.  **Run the application locally:** Execute and test the fully integrated
    microservices locally to validate all API endpoints.
1.  **Deploy the application:** Containerize services, generate deployment
    descriptors, and provision Google Cloud infrastructure for GKE deployment.

## Agent conversation strategy

To maximize efficiency and keep the conversation context focused, this guide
divides the workload across several modular conversations. This strategy
prevents context pollution and allows you to execute independent tasks in
parallel:

- **Conversation 1 (The Builder):** This foundational agent handles
  domain-driven abstractions, database schema creation, core microservices
  architecture, and project documentation.
- **Conversation 2 (Data Setup):** This dedicated conversation focuses on
  configuration and data seeding. It keeps bulk SQL generation out of the core
  application context.
- **Conversations 3, 4, and 5 (The Testers):** These parallel conversations
  generate unit and integration tests for each microservice. They demonstrate
  Antigravity's multitasking ability and reduce development time.
- **Conversation 6 (The DevOps Engineer):** This persona focuses on platform
  engineering and infrastructure. The agent handles your local orchestrations,
  Kubernetes configuration, and Terraform deployments.

## Requirements

To run this demo, you need the following:

- Java Development Kit (JDK): Version 21 or higher
- Apache Maven: Version 3.9.3 or higher
- Docker: Version 29.3.0 or higher
- For infrastructure provisioning and deployment:
    - A Google Cloud project with the `Owner` role.
    - Google Cloud SDK
    - Terraform >= 1.11.1
    - `kubectl` (configure this for your GKE cluster)
    - `jq` (for testing)

<!-- markdownlint-disable MD046 -->

!!! note "Gemini Pro model"

    This demo uses the latest Gemini Pro model.

<!-- markdownlint-enable MD046 -->

## Set up your environment and workspace

In this demo guide, you use [Google Antigravity](https://antigravity.google/),
an agentic development platform for building microservices.

1.  If you haven't already, download the installer for your operating system
    from the [downloads](https://antigravity.google/download) page.
1.  Launch the application installer and install it on your machine. After you
    complete the installation, launch the Antigravity application.
1.  Create a workspace folder on your machine called `e-commerce-workspace`.
    This folder acts as a shared context where Antigravity agents and developers
    collaborate on tasks.

### Configure `Review Driven Development` mode

1.  Open Antigravity.
1.  Click `Open Folder` to open the workspace directory.
1.  Switch to the `Agent Manager` window by clicking on `Open Agent Manager` on
    the top right corner.
    1.  Click the gear icon on the top right corner and select the `Agent` tab.
    1.  Change the dropdown under Artifact `Review Policy` to `Asks for Review`.
        The agent stops and waits for your approval after it generates an
        Implementation Plan before it writes code.
    1.  Change the setting under `Terminal Command Auto Execution` to
        `Request Review`. The agent no longer runs commands without your manual
        approval.

<!-- markdownlint-disable MD046 -->

!!! note "Review Driven Development"

    Throughout this demo, you must manually approve or reject every command the
    agent suggests by selecting either the Run or Reject option.

<!-- markdownlint-enable MD046 -->

## Generate the domain model

In this section, you use Domain-Driven Design (DDD) to model the e-commerce
order management system. This architectural step is key to defining functional
specs and establishing a ubiquitous language that keeps all project stakeholders
aligned.

In the Agent Manager window, select your workspace and click `+` (New
Conversation) and send the following prompt to generate the domain model for the
order management system.

```markdown
Using a Domain-Driven Design approach, generate a domain model for an e-commerce
order management system. Save the model as domain-model.md in Markdown. Use
Order Management as the core domain, and Customer (including addresses) and
Product (including categories) as supporting domains.

Apply the following Markdown structure:
- Ubiquitous Language: A table defining key domain terms, synonyms, and
  descriptions.
- Bounded Context Definition: Use headers (# Bounded Context: Name) for
  boundaries and relationships.
- Aggregate Modeling: Document Entities and Value Objects. Use bullets for
  properties and invariants.

Example:
### Order (Aggregate Root)
Domain Events and Commands:
Use list formatting to capture business actions and reactions
```

Wait for the agent to generate an Implementation Plan and review it. After you
approve the plan, the agent generates the `domain-model.md` file.

## Design database schemas and generate Data Definition Language (DDL) scripts

In this section, you translate the domain entities into a structured database
schema and generate DDL scripts to manage them.

In the same conversation, send the following prompt to have the agent review the
domain entities and generate the database schema.

```markdown
Create database schemas for customer, product, and order domains based on the
domain model (domain-model.md). Generate and syntactically verify DDL scripts
(compliant with both H2 and PostgreSQL 17) for every domain. Verify the scripts
through code analysis or by using available local tools (like `sqlite3` for
basic validation) rather than assuming a live PostgreSQL instance is available.
Ensure the following:

- Use UUID, serial, or integer for primary keys.
- Isolate database schemas that map to domains.
- Maintain cross-domain or schema references logically, not through physical
  foreign keys.
- Tie aggregate roots to related entities using foreign keys relationships.
- Name the files customer_schema.sql, product_schema.sql, and order_schema.sql.
```

Wait for the agent to generate an Implementation Plan. Review and approve the
plan before the agent generates the DDL scripts.

## Design and implement the microservices

In this section, you build the microservices across the order, customer, and
product domains.

1.  In the same conversation, send the following prompt to have the agent
    generate the source code for the order, customer, and product microservices.

    ```markdown
    Using a Domain-Driven Design (DDD) approach, build a set of Spring Boot
    microservices for an e-commerce order management system.

    - Create the project structure (pom.xml, directories, and source code)
    manually for each microservice. Do NOT use external skeletons or generator
    APIs like `start.spring.io` using `curl`.
    - Consider the entities in the domain model in domain-model.md and the
    database schemas in the customer_schema.sql, product_schema.sql, and
    order_schema.sql.
    - Create the source code for each microservice under folders named after
    their root entity. Use the package structure com.demo.ecommerce. Ensure all
    layers of DDD are generated - application, domain, infrastructure, and web.
    - **Do NOT use Lombok**. Generate standard Java getters, setters, and
    constructors to reduce environmental dependency issues.
    - Include **Spring Boot Actuator** in each microservice and expose the
    health endpoints (`/actuator/health`) to support monitoring and liveness
    checks.
    - **Port Mapping**: Explicitly configure each service to listen on its
    dedicated port in `application.yml`: `order` (8080), `customer` (8081), and
    `product` (8082).
    - **API Surface**: Implement standard RESTful Create, Read, Update, and
    Delete (CRUD) operations for each service. Ensure each service includes
    endpoints for retrieving a single record and **listing all records** (for
    example, `GET /api/customers`, `GET /api/products`) to support later
    verification steps.
    - Implement the **order creation workflow** with transactional stock
    management: The `Order` service must verify product availability and deduct
    stock from the `Product` service using **Spring Cloud OpenFeign**. Ensure
    all inter-service calls use appropriate **DTOs** and that service URLs in
    `application.yml` are parameterized (for example,
    `services.customer.url: ${CUSTOMER_SERVICE_URL:http://localhost:8081}`)
    to support both local and Docker networking.
    - **Database configuration**: Use a separate **H2 in-memory database** for
    each service (for example, `jdbc:h2:mem:testdb`) to ensure a clean state
    upon restart.
    - Establish proper **Java Persistence API (JPA) relationships**: Use
    physical foreign key constraints for **internal** relationships within the
    same service (for example, `Order` to `OrderItem`). Use logical references
    (IDs) and **Spring Cloud OpenFeign** for cross-domain relationships (for
    example, `Order` to `Customer` and `Order` to `Product`) to maintain domain
    isolation.
    - **Entity Mapping**: Explicitly map primary keys and other columns to the
    database schema using the `@Column(name="...")` annotation (for example,
    `customer_id`, `product_id`, `order_id`).
    - Include the **Maven Wrapper (`mvnw`)** for each project manually to ensure
    build consistency.
    - **Do NOT generate sample data or data.sql files** at this stage. Data
    seeding is handled in a later step.
    - Generate a standalone, multi-stage **Dockerfile** for each microservice
    using Java 21. Assume each project is independent and the Dockerfile is
    built from its own directory context.
    - **Memory Guardrails**: To prevent local Out-of-Memory (OOM) crashes when
    booting multiple contexts, explicitly configure the
    `spring-boot-maven-plugin` configuration in each `pom.xml` with
    `<jvmArguments>-Xmx512m</jvmArguments>`.
    - **SQL Initialization & Hibernate**: Configure `application.yml` to
    natively sequence SQL initialization from `data.sql` over `schema.sql` files
    by setting `spring.jpa.defer-datasource-initialization=true` and
    `spring.sql.init.mode=always`. **Crucially**, to prevent context failures
    where Hibernate validates schemas before the tables are injected, explicitly
    set `spring.jpa.hibernate.ddl-auto=none`.

    Use the following tech stack:
    - Java 21 or greater
    - Spring Boot 3.2.3 or greater
    - Spring Boot Actuator
    - Spring Data JPA
    - H2 in-memory database (for local execution)
    - PostgreSQL Driver (`org.postgresql:postgresql`)
    - Maven 3.9.3 or greater
    - Spring Cloud OpenFeign (for inter-service calls)

    After generating the artifacts, build and run the services **using Maven
    only**. If you encounter any build or runtime errors, resolve them before
    proceeding. Stop the services after verification is complete.
    **Do NOT perform a Docker build at this stage.** Docker verification and
    orchestration are handled in a later section.
    ```

1.  Follow up with the prompt to integrate OpenAPI support for each of the
    microservices.

    ```text
    Generate OpenAPI specs for order, product, and customer microservices using
    the springdoc-openapi-starter dependency. Include the URLs for the Open API
    UI in the Walkthrough.
    ```

1.  Wait for the agent to finish the updates and review the Walkthrough
    artifacts.

## Generate sample data

In this section, you generate sample data for customers, products, and orders to
test the integrated services.

1.  Start a new conversation and send the following prompt to have the agent
    generate seed and sample data for the schemas.

    ```markdown
    Generate a `data.sql` file for each microservice (`customer`, `product`,
    `order`) with the required sample data. Save the `data.sql` files to the
    `src/main/resources` directory of each service to leverage Spring Boot's
    automatic SQL initialization.

    Requirements and constraints:
    1. **Raw SQL Generation:** Do not use Python or any external scripts.
    generate the raw SQL directly.
    2. **Schema Alignment:** Carefully read the generated entity classes and
    schema files to ensure you only insert data for columns that actually exist.
    For example, do not insert `created_at` timestamps unless explicitly defined,
    and ensure enum string values match exactly.
    3. **Data Counts and Details:**
       - **Customers:** Create 50 customers with realistic profiles.
       - **Products:** Create 50 products across 3 distinct categories with
       realistic stock levels (for example, 500-1,000 units) and prices ($10.00
       to $500.00).
       - **Orders:** Create 200 orders.
    4. **Logical Dependencies:** Keep the logical dependencies between domains
    in consideration. An `Order` must reference a valid customer ID, and order
    items must reference a valid product ID.
    5. **UUIDs:** Ensure all UUIDs are valid RFC 4122 hexadecimal strings. You
    can choose a consistent format or use random valid UUIDs. Do NOT use custom
    prefixes like 'p-' or 'o-'.
    6. **No Sequences:** Do NOT include `ALTER SEQUENCE` or sequence restart
    commands, because the entities use UUIDs for primary keys.
    7. **Idempotency and Structure:** Add SQL statements at the top of each
    `data.sql` file to clear existing data before insertion (for example, use
    `DELETE FROM ...`). Ensure `DELETE` and `INSERT` statements are ordered
    correctly (parent entities before child entities) to prevent foreign key
    constraint violations. The scripts must strictly use standard SQL syntax. Do
    not use H2-specific commands like `SET REFERENTIAL_INTEGRITY`.

    After generating the scripts, ensure your local port bindings for 8080, 8081,
    and 8082 are stopped. Cleanly restart the microservices using Maven. Wait
    for the initialization to finish and verify success by calling the `/api`
    endpoints. Stop the services after verification is complete.
    ```

1.  Wait for the services to restart. Monitor the progress in the Agent Manager
    window as the agent stops and starts the microservices.

## Generate unit and integration tests

To ensure the services have robust test coverage, generate a comprehensive suite
of unit and integration tests, covering both success and error scenarios.

Antigravity supports running multiple parallel agents. This allows you to launch
separate tasks such as generating test suites for different microservices
simultaneously, to save time and isolate the context for each service.

<!-- markdownlint-disable MD046 -->

!!! note "Parallel execution"

    You can launch all three agents below at the same time. Since they run
    in parallel, you don't need to wait for one test suite to finish before
    starting the next.

<!-- markdownlint-enable MD046 -->

- Tester Agent 1:

    Start a new conversation and send the following prompt to generate tests for
    your customer microservice.

    ```markdown
    Generate unit and integration tests using JUnit 5 and Mockito for the
    customer microservice.
    After implementing the tests, follow these steps to verify the service
    locally:
    1. **Directory Setup:** The microservice might be missing the standard
    `src/test/java` directory structure. Proactively create these folders before
    writing the test files.
    2. **Build and Test:** Run `mvn clean install` to ensure the project builds
    without errors and all generated tests pass.
    3. **Resolve Port Conflicts:** Before starting the application, identify and
    terminate any existing background processes that are already bound to the
    service's port (port 8081) to avoid startup binding failures.
    4. **Prevent OOM Crashes:** Because the project relies on a large `data.sql`
    file to seed the H2 database, allocate extra memory to the JVM (for example,
    by setting `export MAVEN_OPTS="-Xmx1G"`) before starting. This prevents the
    process from crashing with an Out-of-Memory error (Exit Code 137) during
    data initialization.
    5. **Restart and Verify:** Start the microservice using `mvn spring-boot:run`.
    Monitor the startup logs closely for any trailing schema or data errors, and
    provide relevant code fixes if it fails to start. Finally, verify the
    application successfully started by checking its `/actuator/health` endpoint.
    ```

- Tester Agent 2:

    Start a new conversation and send the following prompt to generate tests for
    your product microservice.

    ```markdown
    Generate unit and integration tests using JUnit 5 and Mockito for the
    product microservice.
    After implementing the tests, follow these steps to verify the service
    locally:
    1. **Directory Setup:** The microservice might be missing the standard
    `src/test/java` directory structure. Proactively create these folders before
    writing the test files.
    2. **Build and Test:** Run `mvn clean install` to ensure the project builds
    without errors and all generated tests pass.
    3. **Resolve Port Conflicts:** Before starting the application, identify and
    terminate any existing background processes that are already bound to the
    service's port (port 8082) to avoid startup binding failures.
    4. **Prevent OOM Crashes:** Because the project relies on a large `data.sql`
    file to seed the H2 database, allocate extra memory to the JVM (for example,
    by setting `export MAVEN_OPTS="-Xmx1G"`) before starting. This prevents the
    process from crashing with an Out-of-Memory error (Exit Code 137) during
    data initialization.
    5. **Restart and Verify:** Start the microservice using `mvn spring-boot:run`.
    Monitor the startup logs closely for any trailing schema or data errors, and
    provide relevant code fixes if it fails to start. Finally, verify the
    application successfully started by checking its `/actuator/health` endpoint.
    ```

- Tester Agent 3:

    Start a new conversation and send the following prompt to generate tests for
    your order microservice.

    ```markdown
    Generate unit and integration tests using JUnit 5 and Mockito for the
    order microservice.
    After implementing the tests, follow these steps to verify the service
    locally:
    1. **Directory Setup:** The microservice might be missing the standard
    `src/test/java` directory structure. Proactively create these folders before
    writing the test files.
    2. **Build and Test:** Run `mvn clean install` to ensure the project builds
    without errors and all generated tests pass.
    3. **Resolve Port Conflicts:** Before starting the application, identify and
    terminate any existing background processes that are already bound to the
    service's port (port 8080) to avoid startup binding failures.
    4. **Prevent OOM Crashes:** Because the project relies on a large `data.sql`
    file to seed the H2 database, allocate extra memory to the JVM (for example,
    by setting `export MAVEN_OPTS="-Xmx1G"`) before starting. This prevents the
    process from crashing with an Out-of-Memory error (Exit Code 137) during
    data initialization.
    5. **Restart and Verify:** Start the microservice using `mvn spring-boot:run`.
    Monitor the startup logs closely for any trailing schema or data errors, and
    provide relevant code fixes if it fails to start. Finally, verify the
    application successfully started by checking its `/actuator/health` endpoint.
    ```

<!-- markdownlint-disable MD046 -->

!!! note "Planning mode"

    Toggle the **Sidebar** to navigate between your active
    conversations. Since you are in Planning mode, you must switch to each
    agent's respective chat and approve their individual implementation plans
    before they can begin generating the tests.

<!-- markdownlint-enable MD046 -->

1.  Wait for all three agents to finish generating the test suites.
1.  Verify that the tests execute successfully and that the agents resolved any
    build or compilation issues. You can review the agents' explanations and the
    Maven build logs directly in their respective conversations.

## Generate project documentation

In this section, you generate project documentation and design artifacts, such
as README files, UML class diagrams, and sequence diagrams. Good documentation
helps onboarding of new team members, maintenance, and future development,
promoting clarity on the system's architecture and execution.

1.  In the Agent Manager window, select the conversation you used to design and
    implement the microservices and send the following prompt to generate a
    `README.md` file for each microservice and the overall project.

    ```text
    Generate a README.md that includes project overview, prerequisites, and
    local execution instructions, such as ./mvnw spring-boot:run, for each of
    the microservices and at an overall e-commerce project level
    ```

1.  In the same conversation, send the following prompt to create design
    artifacts such as class diagrams and sequence diagrams demonstrating the
    order creation workflow, showing integrations with the product and customer
    domains.

    ```markdown
    Generate Mermaid syntax for the following diagrams and embed them directly
    into the project-level and microservice-level README.md files:
    - A UML class diagram for the overall system architecture.
    - A sequence diagram for the 'Order Creation' workflow involving the order,
    customer, and product services.
    - Entity-Relationship (ER) diagrams for each of those three services.

    Please provide these as separate Markdown code blocks labeled mermaid within
    the README files. Ensure the syntax is valid and error-free.
    ```

1.  Review the generated `README.md` files and use the Markdown previewer in
    your editor to verify that the UML diagrams render correctly.

## Run the application locally

In this section, you restart the microservices and use the Antigravity browser
agent to test them through the Swagger UI. The browser agent allows Antigravity
to autonomously open websites, interact with UI elements, and verify
functionality directly within the browser.

1.  Start a new conversation and send the following prompt to restart the
    microservices and test the APIs.

    ```text
    Restart all the microservices and test the APIs through the Swagger UI using
    Antigravity's browser agent. Verify that each service returns a successful
    response from its GET endpoints.
    ```

1.  Wait for the browser agent to finish testing the APIs. Review the agent's
    explanation and check the recording in the walkthrough to verify that each
    service returns a successful response from its GET endpoints.

<!-- markdownlint-disable MD046 -->

!!! note "Browser agent"

    If this is your first time using the browser agent, it might prompt
    you to install the Google Antigravity browser extension and its dependencies.
    Allow it to complete the setup.

<!-- markdownlint-enable MD046 -->

Now that the individual services are running correctly, you can orchestrate them
using Docker Compose to create a more robust local environment.

## Automated Docker environment orchestration

In this section, you use Antigravity to discover your microservices, create a
unified Docker Compose configuration, and orchestrate the build and startup
process. This includes automatically configuring environment variables for
inter-service communication and setting up the Docker environment.

1.  Start a new conversation and send the following prompt to orchestrate the
    Docker environment.

    ```markdown
    Create a Docker Compose file named `compose.yaml` in the root directory that
    follows the latest Compose specification, and not the legacy v2.x or v3.x
    Compose file formats. Build and run all three microservices: `customer`,
    `product`, and `order`.

    Requirements:
    1. Use the existing `Dockerfile` in each service directory.
    2. Expose the following ports: `order` (8080), `customer` (8081), and
    `product` (8082).
    3. Configure `order` to connect to other services using internal Docker
    networking (for example, set
    `CUSTOMER_SERVICE_URL=http://customer:8081`).
    4. Ensure each service uses its existing H2 in-memory database without
    mapping any local volumes.
    5. Set the **build context** for each service to its respective subdirectory
    (for example, `./customer`).

    After creating the file, find and stop any running containers or background
    processes holding ports 8080, 8081, or 8082. Then, build and start the
    services using Docker Compose, use the --rm option when starting workloads.
    After running docker compose up, utilize Docker's built-in health checks or
    actively wait 15-20 seconds before attempting to verify the
    `/actuator/health` HTTP endpoints. Monitor the startup and notify me when
    all services are healthy and ready to receive traffic.
    ```

1.  Wait for the agent to finish building and starting the containers. Review
    the agent's explanation and the Docker Compose logs to verify that all
    services are healthy.

### Verify local services

In this section, the agent performs automated checks to ensure the system is
working correctly. This includes verifying the health of each specific service
and executing a full business transaction, such as creating a customer, a
product, and an order, to confirm the integration is successful.

1.  In the same conversation, send the following prompt to verify the services.

    ```markdown
    Perform an end-to-end verification of the local microservices using `curl`.
    1. **Health Check**: Verify that the actuator health endpoints for all
    services return a "UP" status.
    2. **Setup Data**: Use `curl` to POST JSON data to create a test customer
    and a test product.
    3. **Business Logic**: Place an order for that customer and product.
    4. **Verification**: Confirm the order was successfully created and that the
    product stock was correctly deducted by analyzing the JSON responses.
    ```

1.  Wait for the agent to finish verifying the services. Review the agent's
    explanation to ensure all microservices are functioning properly.

### Stop local services

In this section, you use the agent to shut down and clean up the local
environment. This ensures that no orphaned processes remain on your host
machine, leaving it ready for your next deployment or local session.

In the same conversation, send the following prompt to stop the services.

```text
Stop all running local services and remove the containers using Docker Compose
--remove-orphans to ensure a clean state for your next session.
```

## Provision infrastructure

In this section, you provision the infrastructure for the demo using Terraform.

### Google Cloud permissions

Ensure your user account has the following IAM roles in your Google Cloud
project:

- Kubernetes Engine Admin (`roles/container.admin`): To create and manage the
  GKE cluster.
- Cloud SQL Admin (`roles/cloudsql.admin`): To provision and manage the Cloud
  SQL instance.
- Compute Network Admin (`roles/compute.networkAdmin`): To manage VPC networks
  and firewall rules.
- Artifact Registry Admin (`roles/artifactregistry.admin`): To create a
  repository for container images.
- Service Account Admin (`roles/iam.serviceAccountAdmin`): To create service
  accounts for GKE nodes and other resources.
- Project IAM Admin (`roles/resourcemanager.projectIamAdmin`): To grant IAM
  roles to service accounts.

For demonstration purposes, the basic `Owner` role (`roles/owner`) is
sufficient.

<!-- markdownlint-disable MD046 -->

!!! note "Production environment"

    In a production environment, always adhere to the principle of
    least privilege.

<!-- markdownlint-enable MD046 -->

### Execute Terraform scripts to provision GKE and database resources

1.  Open a new terminal in Antigravity (click **Open Editor** in the top-right
    corner and select **Terminal** > **New Terminal**) and clone the repository
    into your workspace root:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions && \
    cd cloud-solutions/projects/build-with-gemini-demo/agentic-development-with-antigravity/terraform
    ```

1.  Replace `YOUR_PROJECT_ID` with your Google Cloud project ID:

    ```bash
    export TF_VAR_project_id="YOUR_PROJECT_ID"
    ```

1.  Authenticate and configure your Google Cloud project for Terraform:

    ```bash
    # Authenticate to manage resources with the gcloud CLI
    gcloud auth login

    # Set the Google Cloud project and billing
    gcloud config set project $TF_VAR_project_id
    gcloud config set billing/quota_project $TF_VAR_project_id

    # Enable required APIs for Cloud Resource Manager
    gcloud services enable cloudresourcemanager.googleapis.com

    # Authenticate to manage Google Cloud resources with Terraform
    gcloud auth application-default login
    ```

1.  Provision the necessary Google Cloud infrastructure. This creates a GKE
    cluster, a Cloud SQL for PostgreSQL instance, and an Artifact Registry
    repository:

    ```bash
    # Initialize the project
    terraform init

    # Provision the resources
    terraform apply
    ```

1.  Wait for Terraform to provision the resources. This process takes
    approximately 15 minutes.

1.  Capture and display the infrastructure details:

    ```bash
    export PROJECT_ID=$(terraform output -raw project_id)
    export REGION=$(terraform output -raw region)
    export REPO_NAME=$(terraform output -raw artifact_registry_repo)
    export LB_IP=$(terraform output -raw load_balancer_ip)

    echo "Ready to build in $PROJECT_ID ($REGION) using repo: $REPO_NAME"
    ```

### Build container images

Build and push container images to Artifact Registry using Google Cloud Build.

1.  Navigate to your workspace root directory and build the container images for
    all three services:

    ```bash
    cd "$(git rev-parse --show-toplevel)/.."

    for service in customer product order; do
    gcloud builds submit --suppress-logs \
        --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${service}:latest \
        ./${service}
    done
    ```

1.  Wait for the [builds](https://console.cloud.google.com/cloud-build/builds)
    to complete. This process takes several minutes.

### Capture deployment context

1.  Collect all infrastructure details and build artifacts into a single context
    file for Antigravity to use in the next section:

    ```bash
    # 1. Retrieve values from Terraform
    export DB_USER_PWD=$(terraform -chdir=cloud-solutions/projects/build-with-gemini-demo/agentic-development-with-antigravity/terraform output -raw db_password)
    export SQL_CONNECTION=$(terraform -chdir=cloud-solutions/projects/build-with-gemini-demo/agentic-development-with-antigravity/terraform output -raw sql_instance_connection_name)

    # 2. Create the context file
    cat <<EOF > k8s-context.txt
    Google Cloud Project: $PROJECT_ID
    Region: $REGION
    Load Balancer Static IP: $LB_IP
    Artifact Registry Repo: $REPO_NAME
    Cloud SQL Connection Name: $SQL_CONNECTION
    Database User: dbuser
    Database Password: $DB_USER_PWD
    Databases: customer, product, and order
    Container Images:
    EOF

    # 3. Add the images
    gcloud artifacts docker images list ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME} \
    --format="value(package)" | sort -u | awk '{print $1":latest"}' >> k8s-context.txt
    ```

## Generate Kubernetes configuration

### Generate Kubernetes YAMLs for applications

1.  Switch back to the Agent Manager, start a new conversation, and send the
    following prompt to generate Kubernetes deployment descriptors:

    ```markdown
    Generate Kubernetes YAML descriptors to deploy three Java microservices
    (customer, product, order) using provisioned Google Cloud infrastructure.
    Save all files in the /k8s folder.

    Infrastructure Context (refer to @k8s-context.txt for dynamic values):
    - Cluster: `ecommerce-cluster` (GKE Autopilot)
    - Database: PostgreSQL 17 instance (`ecommerce-instance`)
    - Repositories: `app-repo` in Artifact Registry

    Global Requirements:
    1. Namespace: Use a dedicated `ecommerce` namespace for all resources.
    2. Security (Workload Identity): Create a Kubernetes Service Account named
    `java-backend-ksa`. IMPORTANT: Do NOT add any annotations for a Google
    Service Account (GSA). We are using direct mapping for the KSA identity.
    3. Common Config: Create a Secret (`ecommerce-db-secret`) for
    `SPRING_DATASOURCE_USERNAME`, `SPRING_DATASOURCE_PASSWORD`.
    4. Service Discovery: Create a ConfigMap (`service-discovery-config`) for
    inter-service URLs:
    - CUSTOMER_SERVICE_URL: http://customer:8081/customers
    - PRODUCT_SERVICE_URL: http://product:8082/products

    Deployment Specs (Per Service):
    - Replicas: 1.
    - Service Account: `java-backend-ksa`.
    - Image Path: Pull from app-repo using the latest tags found in the context
    file.
    - Environment Overrides:
    - Set `SPRING_PROFILES_ACTIVE=gke` and `SPRING_JPA_HIBERNATE_DDL_AUTO=update`.
    - IMPORTANT: To prevent the application defaulting to local H2 settings,
        explicitly set `SPRING_DATASOURCE_DRIVER_CLASS_NAME=org.postgresql.Driver`
        and `SPRING_JPA_DATABASE_PLATFORM=org.hibernate.dialect.PostgreSQLDialect`.
    - Set `MANAGEMENT_ENDPOINT_HEALTH_PROBES_ENABLED=true` to enable Kubernetes
        actuator endpoints.
    - Set `SERVER_SERVLET_CONTEXT_PATH` specific to each service (`/customers`
        for customer, `/products` for product, `/orders` for order).
    - Database URL (Unique per service):
    - Customer: `jdbc:postgresql://127.0.0.1:5432/customer`
    - Product: `jdbc:postgresql://127.0.0.1:5432/product`
    - Order: `jdbc:postgresql://127.0.0.1:5432/order`
    - Resources: Set conservative requests to ensure pods schedule successfully
    without hitting Google Compute Engine CPU quotas. Use `150m CPU` and `384Mi
    Memory` for the main application containers.
    - Security Context: Apply a `securityContext` to the Pod template (for
    example, `fsGroup: 1000`, `runAsUser: 1000`) to preemptively resolve any
    Kubernetes PersistentVolume or init permissions when mounting files or
    storage.
    - Deployment Strategy: Apply `maxSurge: 0` and `maxUnavailable: 1` to all
    services to prevent quota exhaustion during rolling updates.
    - Probes: Configure HTTP `livenessProbe` and `readinessProbe` targeting the
    `/actuator/health` endpoint. IMPORTANT: The probe `path` MUST be prefixed
    with the `SERVER_SERVLET_CONTEXT_PATH` for each specific service (for
    example, `/customers/actuator/health`). Also, set `initialDelaySeconds` to
    `300` to prevent premature kills while JPA initializes and seeds the
    database.

    Sidecars:
    - Add the Cloud SQL Auth Proxy sidecar
    (`gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.14.2`) to EVERY deployment,
    with resource requests set to `50m CPU` and `256Mi Memory`.
    - Arguments: `--private-ip`, `--port=5432`, and the dynamic connection name
    from k8s-context.txt.

    External Access (Ingress):
    - Create an Ingress (`ecommerce-ingress`) to expose the services publicly.
    - Ingress Class: `gce`.
    - Static IP: Use the global static IP named `ecommerce-lb-ip`
    (through `kubernetes.io/ingress.global-static-ip-name` annotation).
    - Routing Rules:
    - `/customers/*` -> `customer:8081`
    - `/products/*` -> `product:8082`
    - `/orders/*` -> `order:8080`
    - Important: Use `pathType: ImplementationSpecific` for the routing rules,
    and ensure all Services are deployed as standard ClusterIP, which
    automatically negotiates NEGs (Network Endpoint Groups) for GCE
    compatibility.
    ```

1.  Wait for Antigravity to complete the generation and create the `/k8s`
    directory with all the definitions. Review the generated YAML specs to
    ensure they look accurate before deploying them to the actual cluster.

## Deploy the application

### Prepare the environment

Switch back to the Editor and prepare for application deployments, run the
following steps in the terminal:

1.  Set environment variables:

    ```bash
    export PROJECT_ID=$(terraform -chdir=cloud-solutions/projects/build-with-gemini-demo/agentic-development-with-antigravity/terraform output -raw project_id)
    export REGION=$(terraform -chdir=cloud-solutions/projects/build-with-gemini-demo/agentic-development-with-antigravity/terraform output -raw region)
    export CLUSTER_NAME=$(terraform -chdir=cloud-solutions/projects/build-with-gemini-demo/agentic-development-with-antigravity/terraform output -raw gke_cluster_name)
    ```

1.  Install the GKE auth plugin and configure `kubectl` to connect to the
    cluster:

    ```bash
    # Install the GKE auth plugin
    gcloud components install gke-gcloud-auth-plugin

    # Connect kubectl to the GKE cluster
    gcloud container clusters get-credentials $CLUSTER_NAME \
      --region $REGION --project $PROJECT_ID

    # Verify the connection
    kubectl get nodes
    ```

### Agentic deployment with Antigravity

1.  Switch back to the Agent Manager and send a prompt in the conversation where
    you generated Kubernetes YAML files:

    ```text
    Deploy all resources in the /k8s folder. Ensure the namespace is created
    first. After you apply the resources, watch the pods in the ecommerce
    namespace and let me know when all of them (including the sidecars) are
    Running and Ready.
    ```

1.  Wait for the agent to finish deploying the resources. Review the agent's
    explanation to ensure the deployment was successful.

## Test the deployed application

You can use the Antigravity agent to verify the end-to-end flow and external
access.

### End-to-end flow through the API

1.  In the same conversation, send the following prompt to test the deployed
    application:

    ```markdown
    Test the external access to the deployed application:

    1. Retrieve the load balancer IP from Terraform (`terraform -chdir=cloud-solutions/projects/build-with-gemini-demo/agentic-development-with-antigravity/terraform output -raw load_balancer_ip`).

    2. Try reaching the `/customers/api/customers`, `/products/api/products`,
       and `/orders/api/orders` endpoints on that IP. Note: It might take 5-10
       minutes for the GKE Ingress to activate. Retry if you receive a `404` or
       `502` response.

    3. Perform an end-to-end transaction:
       - Create a customer.
       - Create a product with a stock quantity of 25.
       - Place an order for 2 units for the new customer.
       - Verify that the product's stock was deducted to 23.
       - Confirm the order is listed in the `/orders/api/orders` endpoint.
    ```

1.  Wait for the agent to finish testing the application. Review the agent's
    explanation to ensure the services are functioning through the load
    balancer.

### Test with Swagger UI using the browser agent

Use the Antigravity browser agent to test the deployed application in Swagger
UI. This specialised agent can open websites, interact with UI elements, and
verify functionality in the browser.

1.  In the same conversation, send the following prompt to test the Swagger UI:

    ```markdown
    Test the deployed application using the browser agent:
    1. Retrieve the load balancer IP from Terraform (`terraform -chdir=cloud-solutions/projects/build-with-gemini-demo/agentic-development-with-antigravity/terraform output -raw load_balancer_ip`).
    2. Open the Swagger UI for the customer service by navigating to
       `http://<LOAD_BALANCER_IP>/customers/swagger-ui/index.html`.
    3. Verify that the UI loads and use the browser agent to execute a `GET`
       request through the Swagger UI.
    ```

1.  Wait for the browser agent to finish testing. Review the agent's explanation
    and check the recording in the walkthrough to verify the interaction.

## Clean up resources

To avoid incurring charges, destroy the demo infrastructure:

```bash
terraform -chdir=cloud-solutions/projects/build-with-gemini-demo/agentic-development-with-antigravity/terraform destroy
```

<!-- markdownlint-disable MD046 -->

!!! note "Confirming resource deletion"

    Review the resources that Terraform plans to delete. When prompted, enter
    `yes` to confirm and proceed with the deletion.

<!-- markdownlint-enable MD046 -->

## What's next

- Learn more about [Google Antigravity](https://antigravity.google/).
- Explore other
  [Google Cloud solutions](https://googlecloudplatform.github.io/cloud-solutions/build-with-gemini-demo/).
