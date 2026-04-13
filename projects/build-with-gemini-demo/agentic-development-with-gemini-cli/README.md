# Agentic development with Gemini CLI

This guide shows you how to use Gemini CLI to build and deploy microservices on
Google Cloud using [subagents](https://geminicli.com/docs/core/subagents/).

The guide includes the following steps:

1.  **Set up your environment and workspace:** Install Gemini CLI, configure a
    workspace.
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

## Subagent strategy

To handle the complexity of building a full microservices stack, this demo
leverages **subagents** to delegate specialized tasks like testing, data
generation, and deployment. This strategy prevents context bloat in your main
conversation, allows each agent to focus on a specific persona, and ensures
consistent application of architectural standards. We implement this using a
split-prompting approach:

- **Agent Config (The "How"):** Methodology, output structures, and formatting
  rules are defined in the agent's system files located in `.gemini/agents/`.
  This keeps base behavior consistent and avoids repeating instructions.
- **User Prompt (The "What"):** Focus your inputs purely on the specific
  business requirements or tasks you want the agent to execute.

This keeps your prompts concise and focused on the actual work.

- **The Builder Agent (`builder_agent`)**
    - Purpose: Handles Domain-Driven Design (DDD) modeling, Spring Boot
      implementation, and OpenAPI/README documentation.
    - Benefit: Isolates the high-level architectural context from the
      implementation details of tests or infrastructure.

- **The DB Initializer Agent (`db_initializer_agent`)**
    - Purpose: Generates `data.sql` files with realistic sample data, such as 50
      customers and 200 orders.
    - Benefit: Prevents context bloat in your main development session caused by
      large SQL scripts.

- **The Tester Agent (`tester_agent`)**
    - Purpose: Generates unit and integration tests for each microservice.
    - Benefit: Prevents your main conversation history from being flooded with
      verbose unit test code and test execution logs.

- **The Browser Agent (`browser_agent`)**
    - Purpose: Automatically interacts with web applications (like Swagger UI)
      to verify functionality.
    - Benefit: Automates manual verification steps by reading the page state and
      performing actions.

- **The DevOps Engineer Agent (`devops_engineer_agent`)**
    - Purpose: Manages `compose.yaml`, Terraform provisioning, and K8s YAML
      descriptor generation.
    - Benefit: Can be granted specific tools to perform environment checks and
      deployments securely.

## Requirements

To run this demo, you need the following:

- Java Development Kit (JDK): Version 21 or higher
- Apache Maven: Version 3.9.3 or higher
- Docker: Version 29.3.0 or higher
- Chrome version 144 or higher
- Node.js version 20.19 or higher
- For infrastructure provisioning and deployment:
    - Google Cloud SDK version 562.0.0 or higher
    - Terraform >= 1.11.1
    - `kubectl`, configured for your GKE cluster
    - `jq` for testing

<!-- markdownlint-disable MD046 -->

!!! note "Gemini Pro model"

    This demo uses the latest Gemini Pro model.

<!-- markdownlint-enable MD046 -->

## Set up your environment and workspace

In this demo guide, you use [Gemini CLI](https://geminicli.com/) for building
microservices.

1.  Install and configure [Gemini CLI](https://geminicli.com/docs/get-started/).
1.  Clone the `cloud-solutions` repository:

    ```bash
    git clone --filter=blob:none --no-checkout https://github.com/GoogleCloudPlatform/cloud-solutions
    cd cloud-solutions
    git sparse-checkout init --cone
    git sparse-checkout set projects/build-with-gemini-demo/agentic-development-with-gemini-cli
    git checkout
    cd projects/build-with-gemini-demo/agentic-development-with-gemini-cli
    ```

## Generate the domain model

In this section, you use Domain-Driven Design (DDD) to model the e-commerce
order management system. This architectural step is key to defining functional
specs and establishing a ubiquitous language that keeps all project stakeholders
aligned.

In your shell:

1.  Start Gemini CLI (you will be prompted to enable subagents on first
    startup):

    ```bash
    gemini
    ```

1.  List the available agents to verify the setup:

    ```text
    /agents list
    ```

1.  Send the following prompt to the Builder Agent to generate the domain model
    for the order management system. We use the `@builder_agent` handle to
    explicitly direct the task to a specific subagent for predictability and
    clarity, rather than letting Gemini CLI infer the target agent
    automatically.

    ```markdown
    @builder_agent Generate a domain model for an e-commerce order management
    system. Save the model as `domain-model.md`.

    Use:
    - Core Domain: Order Management
    - Supporting Domains: Customer (including addresses) and Product
      (including categories)
    ```

    Sample output:

    ```markdown
    ✦ The builder_agent has successfully generated the domain model for the
      e-commerce order management system and saved it as domain-model.md.

      The model includes the specified Core Domain (Order Management) and
      Supporting Domains (Customer and Product).
    ```

Wait for the Builder Agent to generate the `domain-model.md` file.

## Design database schemas and generate Data Definition Language (DDL) scripts

In this section, you translate the domain entities into a structured database
schema and generate DDL scripts to manage them.

Send the following prompt to have the Builder Agent review the domain entities
and generate the database schema.

```markdown
@builder_agent Create database schemas for customer, product, and order domains
based on the domain model in `domain-model.md`.

Name the files:
- customer_schema.sql
- product_schema.sql
- order_schema.sql
```

Sample output:

```markdown
✦ The builder_agent has successfully created the database schemas for the
customer, product, and order domains.

The following files were created:
- customer_schema.sql
- product_schema.sql
- order_schema.sql

The schemas use UUIDs for primary keys, isolate domains logically without
physical foreign keys across boundaries (as per DDD), and include CHECK
constraints to enforce data invariants.
```

Wait for the Builder Agent to generate the DDL scripts.

## Design and implement the microservices

In this section, you build the microservices across the order, customer, and
product domains.

1.  Send the following prompt to the Builder Agent to generate the source code
    for the order, customer, and product microservices.

    ```markdown
    @builder_agent Build a set of Spring Boot microservices for the e-commerce
    order management system based on `domain-model.md` and the generated `.sql`
    schemas.

    Specific Requirements:
    - **Services**: Create services for `order`, `customer`, and `product` under
    the package `com.demo.ecommerce`. Name the project folders `order-service`,
    `customer-service`, and `product-service` respectively, and place them
    directly in the project root directory. Do not nest them in a `services`
    folder.
    - **Ports**: `order` (8080), `customer` (8081), and `product` (8082).
    - **API Surface**: Standard CRUD operations. Include endpoints to list all
    records (e.g., `GET /api/customers`).
    - **Workflow**: Implement the order creation workflow. The `Order` service
    must verify product availability and deduct stock from the `Product`
    service using OpenFeign.
    - **Data**: Do NOT generate sample data or `data.sql` files yet.

    After generating, build and run the services using Maven only to verify. Do
    NOT perform a Docker build at this stage.
    ```

    Sample output:

    ```markdown
    ✦ The microservices have been successfully generated based on
    domain-model.md and the SQL schemas.

    Here's a summary of the generated services:
    1. Customer Service (com.demo.ecommerce, Port 8081): Provides standard CRUD
        and list operations for Customers and Addresses.
    2. Product Service (com.demo.ecommerce, Port 8082): Provides standard CRUD
        and list operations for Products and Categories, plus a stock deduction
        endpoint (/api/products/{id}/deduct-stock).
    3. Order Service (com.demo.ecommerce, Port 8080): Manages Orders and
        implements the order creation workflow with OpenFeign to deduct stock
        from the Product Service.

    As requested, I have successfully built the services using Maven (mvn clean
    package) and have started them as background processes using
    mvn spring-boot:run.

    You can interact with them locally on their respective ports: 8080, 8081,
    and 8082.
    ```

1.  Follow up with the prompt to integrate OpenAPI support for each of the
    microservices.

    ```markdown
    @builder_agent Generate OpenAPI specs for order, product, and customer
    microservices. Include the URLs for the UI in the output.

    **Ensure you restart the services after applying the changes so the Swagger
    UI becomes accessible.**
    ```

    Sample output:

    ```markdown
    ✦ The builder_agent has successfully generated the OpenAPI specifications
    for the microservices.

    Here is a summary of the changes:
    1. Dependencies: Added springdoc-openapi-starter-webmvc-ui to the pom.xml of
        the Customer, Product, and Order services.
    2. Static Specs: Generated static openapi.yaml files within each service
    directory (customer-service/openapi.yaml, product-service/openapi.yaml,
    order-service/openapi.yaml).

    You can access the interactive Swagger UI for each service using the
    following URLs:
    * Order Service: http://localhost:8080/swagger-ui/index.html
    * Customer Service: http://localhost:8081/swagger-ui/index.html
    * Product Service: http://localhost:8082/swagger-ui/index.html
    ```

1.  Wait for the Builder Agent to finish the updates. Verify that the Swagger UI
    is accessible at the provided URLs.

## Generate sample data

In this section, you generate sample data for customers, products, and orders to
test the integrated services.

1.  Send the following prompt to the DB Initializer Agent to generate seed and
    sample data for the schemas.

    ```markdown
    @db_initializer_agent Generate a `data.sql` file for each microservice
    (`customer`, `product`, `order`) with the required sample data. Save the
    files to the `src/main/resources` directory of each service.

    Data Requirements:
    - **Customers**: Create 50 customers with realistic profiles.
    - **Products**: Create 50 products across 3 distinct categories with
    realistic stock levels (500-1,000 units) and prices ($10.00 to $500.00).
    - **Orders**: Create 200 orders.
    ```

    Sample output:

    ```markdown
    ✦ The sample data has been successfully generated across all three
    microservices using the schemas provided.

    - Customers: 50 realistic records added.
    - Products: 50 records spread across 3 categories with prices ranging from
      $10 to $500 and stock from 500-1000 units.
    - Orders: 200 order records with 1-3 items each.
    ```

1.  Wait for the services to restart. Verify that the sample data is accessible
    through the Swagger UI for each service:
    - **Order Service**: http://localhost:8080/swagger-ui/index.html
    - **Customer Service**: http://localhost:8081/swagger-ui/index.html
    - **Product Service**: http://localhost:8082/swagger-ui/index.html

## Generate unit and integration tests

To ensure the services have robust test coverage, have the Tester Agent generate
tests for all services.

1.  Send the following prompt to the Tester Agent:

    ```markdown
    @tester_agent Generate unit and integration tests for the customer, product,
    and order microservices.

    Verify that the tests pass and the services can still start up successfully.
    ```

    Sample output:

    ```markdown
    ✦ The tester_agent has successfully generated and verified the test suite
    for all three microservices.

    Here is a summary of the changes:
    1. Dependencies: Added spring-boot-starter-test to the pom.xml of the
        Customer, Product, and Order services.
    2. Unit Tests: Created service layer tests (CustomerServiceTest,
        ProductServiceTest, OrderServiceTest) using JUnit 5 and Mockito to
        verify business logic.
    3. Web Layer Tests: Created controller layer tests (CustomerControllerTest,
        ProductControllerTest, OrderControllerTest) using @WebMvcTest and
        MockMvc to verify API routing and responses.
    4. Integration Tests: Created @SpringBootTest application context load tests
        to verify the Spring contexts boot up correctly with the H2 test
        databases.

    All tests passed successfully during execution via Maven.

    Additionally, I have restarted the services in the background and verified
    that all three (Ports 8080, 8081, and 8082) start up successfully and are
    currently running without any errors!
    ```

1.  Wait for the Tester Agent to finish generating and verifying the test suites
    for all services.

## Generate project documentation

In this section, you generate project documentation and design artifacts.
High-quality documentation ensures clarity on the system's architecture and
execution, facilitating onboarding and future maintenance.

1.  Send the following prompt to the Builder Agent to generate project-level and
    microservice-level `README.md` files with embedded diagrams.

    ```markdown
    @builder_agent Generate a project-level `README.md` and a `README.md` for
    each microservice.

    Include the following Mermaid diagrams in the appropriate files:
    - System architecture (UML class diagram).
    - 'Order Creation' workflow (Sequence diagram).
    - ER diagrams for the data models.
    ```

    Sample output:

    ```markdown
    ✦ The builder_agent has successfully generated the documentation for the
    project.

    Here is a summary of the generated files and their contents:

    1. Project-level README.md:
        - Contains a comprehensive overview of the E-Commerce Order Management
          System.
        - Includes a System Architecture (UML class diagram) rendered with
          Mermaid, showing the microservices and their boundaries.
        - Includes an 'Order Creation' workflow (Sequence diagram) detailing the
          interaction between the Order, Customer, and Product services.
        - Provides instructions on how to build and run the system locally.

    2. customer-service/README.md:
        - Focuses on the Customer Management domain.
        - Includes an ER Diagram visualizing the customers and addresses tables.
        - Documents the available API endpoints.

    3. product-service/README.md:
        - Focuses on the Product Catalog domain.
        - Includes an ER Diagram visualizing the products and categories tables,
          including self-referencing relationships.
        - Documents the available API endpoints.

    4. order-service/README.md:
        - Focuses on the Order Management domain and orchestration.
        - Includes an ER Diagram visualizing the orders and order_items tables.
        - Includes the 'Order Creation' workflow (Sequence diagram).
        - Documents the available API endpoints.

    All Mermaid diagrams are enclosed in proper markdown blocks so they will
    render automatically on platforms like GitHub, GitLab, or compatible
    markdown viewers.
    ```

1.  Review the generated `README.md` files and use the Markdown previewer in
    your editor to verify that the UML diagrams render correctly.

## Run the application locally

In this section, you use the
[Browser Agent](https://geminicli.com/docs/core/subagents/#browser-agent-experimental)
to automatically test the microservices through the Swagger UI. The agent opens
the browser, clicks the endpoints, and verifies the responses.

<!-- markdownlint-disable MD046 -->

!!! note "Prerequisite: Enable the Browser Agent"

    The Browser Agent is experimental and disabled by default. Ensure it is
    enabled in your `settings.json` before proceeding:
    ```json
    {
      "agents": {
        "overrides": {
          "browser_agent": {
            "enabled": true
          }
        }
      }
    }
    ```

<!-- markdownlint-enable MD046 -->

1.  Send the following prompt to the Browser Agent:

    ```markdown
    @browser_agent Open the browser to verify services through Swagger UI for
    the customer, product, and order services and verify that each service
    returns a successful response from its listing (GET) endpoints.

    URLs:
    - Order Service: http://localhost:8080/swagger-ui/index.html
    - Customer Service: http://localhost:8081/swagger-ui/index.html
    - Product Service: http://localhost:8082/swagger-ui/index.html
    ```

1.  If prompted, accept the privacy notice. Wait for the Browser Agent to
    complete the testing and report back.

Now that the individual services are running correctly, you can orchestrate them
using Docker Compose to create a more robust local environment.

## Automated Docker environment orchestration

In this section, you use the Gemini CLI to automatically discover the
microservices and generate a unified Docker Compose configuration. The agent
handles environment variables and service networking for you.

1.  Send the following prompt to the DevOps Agent to orchestrate the Docker
    environment.

    ```markdown
    @devops_engineer_agent Create a Docker Compose file named `compose.yaml` in
    the root directory to build and run the `customer`, `product`, and `order`
    services.

    Enable inter-service communication and verify that all services start up
    successfully.
    ```

    Sample output:

    ```markdown
    ✦ The devops_engineer_agent has successfully created the Docker Compose
    setup and verified that all services are communicating.

    Here is a summary of the changes:
    1. Dockerfiles: Created multi-stage Dockerfiles for customer-service,
        product-service, and order-service (using Maven for the build stage and
        a lightweight JRE for the runtime).
    2. Docker Compose (compose.yaml):
        - Configured all three services to build from their respective
          directories.
        - Mapped ports: order (8080), customer (8081), and product (8082).
        - Configured the internal Docker network for inter-service
          communication.
        - Injected the environment variable
          PRODUCT_SERVICE_URL=http://product:8082 into the order service so its
          Feign client can resolve the product service internally.
        - Added Docker health checks that query the /actuator/health endpoints
            to ensure proper startup sequencing (Order waits for Customer and
            Product).

    The agent ran docker compose up -d --build and verified via the health
    endpoints that all three microservices started up successfully within the
    Docker network!
    ```

1.  Wait for the DevOps Agent to finish building and testing the containers.

### Verify local services

In this section, the agent performs automated checks to ensure the system is
working correctly. This includes verifying the health of each specific service
and executing a full business transaction, such as creating a customer, a
product, and an order, to confirm the integration is successful.

1.  Send the following prompt to the DevOps Agent to verify the services through
    curl smoke tests.

    ```markdown
    @devops_engineer_agent Perform a smoke test on the running containers using
    `curl`.

    Verify the health endpoints are "UP", create a test customer and product,
    place an order, and confirm that the stock was correctly deducted.
    ```

    Sample output:

    ```markdown
    ✦ The devops_engineer_agent has successfully performed the smoke tests.

    Here are the results:
    - Service Health: All three services (Customer, Product, Order) returned an
        UP status from their /actuator/health endpoints.
    - Workflow Verification:
        - A test customer and product were created successfully. The product
        initially had a stock of 50.
        - An order was successfully placed for 2 units of the test product.
        - The product stock was correctly deducted, with the final stock
        confirming a balance of 48.

    Everything is functioning perfectly within the Docker environment!
    ```

1.  Wait for the DevOps Agent to complete the smoke tests and review the
    results.

### Stop local services

In this section, you use the agent to shut down and clean up the local
environment. This ensures that no orphaned processes remain on your host
machine, leaving it ready for your next deployment or local session.

1.  Send the following prompt to the DevOps Agent to stop the services.

    ```markdown
    @devops_engineer_agent Stop all running local services and clean up the
    environment.
    ```

    Sample output:

    ```markdown
    ✦ The devops_engineer_agent has successfully cleaned up the environment.

    Here is a summary of the cleanup:
    1. Docker: Executed docker compose down --remove-orphans to stop and remove
        all containers, networks, and images.
    2. Local Processes: Verified that all background Spring Boot
        (mvn spring-boot:run) processes were terminated.
    3. Ports: Confirmed that ports 8080, 8081, and 8082 are now clear and no
        longer in use.

    The workspace is now clean.
    ```

1.  Wait for the DevOps Agent to complete the cleanup and review the results.

## Provision infrastructure

In this section, you provision the infrastructure for the demo using Terraform.

### Google Cloud permissions

Ensure your user account has the following Identity and Access Management (IAM)
roles in your Google Cloud project:

- Kubernetes Engine Admin (`roles/container.admin`): To create and manage the
  GKE cluster.
- Cloud SQL Admin (`roles/cloudsql.admin`): To provision and manage the Cloud
  SQL instance.
- Compute Network Admin (`roles/compute.networkAdmin`): To manage Virtual
  Private Cloud (VPC) networks and firewall rules.
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

Leave the Gemini CLI terminal running, and open a new terminal in your shell:

1.  Change the working directory to the
    `cloud-solutions/projects/build-with-gemini-demo/agentic-development-with-gemini-cli`
    directory:

    ```bash
    cd cloud-solutions/projects/build-with-gemini-demo/agentic-development-with-gemini-cli
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
    terraform -chdir=terraform init

    # Provision the resources
    terraform -chdir=terraform apply
    ```

1.  Wait for Terraform to provision the resources. This process takes
    approximately 15 minutes.

1.  Capture and display the infrastructure details:

    ```bash
    export PROJECT_ID=$(terraform -chdir=terraform output -raw project_id)
    export REGION=$(terraform -chdir=terraform output -raw region)
    export REPO_NAME=$(terraform -chdir=terraform output -raw artifact_registry_repo)
    export LB_IP=$(terraform -chdir=terraform output -raw load_balancer_ip)
    export CLUSTER_NAME=$(terraform -chdir=terraform output -raw gke_cluster_name)

    echo "Ready to build in $PROJECT_ID ($REGION) using repo: $REPO_NAME"
    ```

### Build container images

Build and push container images to Artifact Registry using Google Cloud Build.

1.  Build the container images for all three services:

    ```bash
    for service in customer-service product-service order-service; do
    gcloud builds submit --suppress-logs \
        --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${service}:latest \
        ./${service}
    done
    ```

1.  Wait for the [builds](https://console.cloud.google.com/cloud-build/builds)
    to complete. This process takes several minutes.

### Create deployment context

In this section, you collect all infrastructure details from Terraform outputs
and build artifacts into a single context file named `k8s-context.md`. Gemini
CLI uses this file to get the necessary context to interact with the Google
Cloud infrastructure.

1.  Send the following prompt to the DevOps Agent to create the context file:

    ```markdown
    @devops_engineer_agent Create the `k8s-context.md` file with the required
    information from Terraform outputs and Artifact Registry.
    ```

    Sample output:

    ```markdown
    ✦ Okay, the k8s-context.md file has been created.
    ```

## Generate Kubernetes configuration

1.  Send the following prompt to the DevOps Agent to generate Kubernetes
    deployment descriptors:

    ```markdown
    @devops_engineer_agent Generate Kubernetes YAML descriptors in the `/k8s`
    folder to deploy the `customer`, `product`, and `order` services to GKE.

    Refer to `@k8s-context.md` for the cluster name, SQL connection string,
    and build artifact tags.
    ```

    Sample output:

    ```markdown
    ✦ The Kubernetes YAML descriptors have been generated in the /k8s directory.
    ```

1.  Wait for the DevOps Agent to finish generating the Kubernetes descriptors.

## Deploy the application

In this section, you deploy the microservices to the GKE cluster. You first
prepare your local environment by setting credentials and then use the DevOps
Agent to perform the deployment.

### Prepare the environment

Run the following steps in the terminal to prepare for application deployments:

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

### Agentic deployment with Gemini CLI

1.  Switch back to the Gemini CLI and send a prompt to the DevOps Agent to
    deploy the application:

    ```markdown
    @devops_engineer_agent Deploy all resources in the `/k8s` folder and ensure
    all pods in the `ecommerce` namespace are running and ready.
    ```

    Sample output:

    ```markdown
    ✦ The devops_engineer_agent has successfully deployed all resources to the
        GKE cluster.

    Here is a summary of the actions taken:
    1. Namespace & Resources: Created the ecommerce namespace and deployed all
        manifests from the /k8s folder.
    2. Pod Verification: Waited for the pods to initialize and verified that
        they have reached the Ready state. All pods (customer-service,
        product-service, and order-service) are currently Running with 2/2
        containers ready, which indicates that both the Spring Boot applications
        and the Cloud SQL Auth Proxy sidecars are healthy and connected.

    The services are now live on the GKE cluster!
    ```

1.  Wait for the DevOps Agent to finish deploying the resources.

## Test the deployed application

You can use the Gemini CLI agent to verify the end-to-end flow and external
access.

### End-to-end flow through the API

1.  Send the following prompt to test the deployed application:

    ```markdown
    @devops_engineer_agent Perform a smoke test on the deployed application
    using the Load Balancer IP from `@k8s-context.md`.

    1. Verify external access to the `/customers`, `/products`, and `/orders`
        endpoints. (Note: GKE Gateway may take 5–10 mins to activate; retry if
        you get 404/502).
    2. Run an end-to-end transaction (create customer, create product with stock
        25, place order for 2, and verify stock drops to 23).
    ```

    Sample output:

    ```markdown
    ✦ The devops_engineer_agent has successfully performed a smoke test on the
    deployed application.

    Here is a summary of the actions taken:
    1. External Access Verification:
        - Verified external access to the `/customers`, `/products`, and
            `/orders` endpoints.
    2. End-to-End Transaction:
        - Created a customer.
        - Created a product with stock 25.
        - Placed an order for 2 units of the product.
        - Verified that the stock dropped to 23.
    ```

1.  Wait for the DevOps Agent to finish testing the application. Review the
    agent's explanation to ensure the services are functioning through the load
    balancer.

### Test with Swagger UI using the browser agent

Use the Gemini CLI Browser Agent to test the deployed application in Swagger UI.
This specialized agent can open websites, interact with UI elements, and verify
functionality in the browser.

1.  Send the following prompt to the Browser Agent to test the Swagger UI:

    ```markdown
    Using the @browser_agent, verify external access to the Swagger UI:
    1. Read the Load Balancer IP from `@k8s-context.md`.
    2. Open the Swagger UI for the order service at
        `http://<LOAD_BALANCER_IP>/swagger-ui/index.html`.
    3. Verify that the UI loads and execute a `GET` request through it to
        confirm it is interactive.
    ```

1.  Wait for the Browser Agent to finish testing.

## Clean up resources

To avoid incurring charges, destroy the demo infrastructure:

```bash
terraform -chdir=terraform destroy
```

<!-- markdownlint-disable MD046 -->

!!! note "Confirming resource deletion"

    Review the resources that Terraform plans to delete. When prompted, enter
    `yes` to confirm and proceed with the deletion.

<!-- markdownlint-enable MD046 -->

## What's next

- Learn more about [Gemini CLI](https://geminicli.com).
- Explore other
  [Google Cloud solutions](https://googlecloudplatform.github.io/cloud-solutions/build-with-gemini-demo/).
