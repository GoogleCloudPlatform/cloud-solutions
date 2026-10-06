# Java application modernization with Antigravity

This guide demonstrates how to use Antigravity to modernize a legacy Struts and
JavaServer Pages (JSP) application to a modern Spring Boot and Thymeleaf stack.
It preserves business logic and data while upgrading the tech stack.

Follow these steps to run the demo:

1.  **Set up your environment and workspace** - Configure the environment to
    follow this guide.
1.  **Scaffold the legacy application** - Generate a legacy application to
    modernize.
1.  **Modernize the backend and upgrade the toolchain** - Upgrade the Java
    runtime and framework to Spring Boot.
1.  **Modernize the user interface (UI)** - Replace JSP with Thymeleaf.
1.  **Test the application locally** - Verify the local application.
1.  **Provision Google Cloud infrastructure** - Use Terraform to provision
    resources.
1.  **Build container images** - Build container images using Cloud Build.
1.  **Create deployment and Google Cloud infrastructure context** - Capture
    Google Cloud context in a file for reuse.
1.  **Generate Kubernetes deployment descriptors** - Create Kubernetes
    manifests.
1.  **Deploy the application** - Deploy to Google Kubernetes Engine (GKE).
1.  **Test the application** - Verify the application on GKE.

> [!NOTE]
>
> **Gemini Flash model**: This demo uses the latest Gemini Flash model.

## Requirements

You need the following dependencies and tools to run the demo:

- **Docker:** Tested with version 29.8.2
- **Docker Compose:** Tested with version v5.1.1
- **Google Cloud CLI (gcloud):** Tested with version 587.0.0
- **kubectl:** Tested with version 1.34.5
- **GKE Kubectl auth plugin:** Tested with version v1.34.2
- **Terraform:** Tested with version 1.14.8
- **A Linux shell**. Tested with Bash version 5.3 and ZSH version 5.9

For infrastructure provisioning and deployment:

- A Google Cloud project with the `Owner` role, or with the following roles:
    - Kubernetes Engine Admin (`roles/container.admin`): To create and manage
      the GKE cluster.
    - Cloud SQL Admin (`roles/cloudsql.admin`): To provision and manage the
      Cloud SQL instance.
    - Compute Network Admin (`roles/compute.networkAdmin`): To manage Virtual
      Private Cloud (VPC) networks and firewall rules.
    - Artifact Registry Admin (`roles/artifactregistry.admin`): To create a
      repository for container images.
    - Service Account Admin (`roles/iam.serviceAccountAdmin`): To create service
      accounts for GKE nodes and other resources.
    - Project IAM Admin (`roles/resourcemanager.projectIamAdmin`): To grant
      Identity and Access Management (IAM) roles to service accounts.

> [!NOTE]
>
> **Production environment**: In a production environment, always adhere to the
> principle of least privilege.

## Set up your environment and workspace

In this demo guide, you use
[Antigravity CLI](https://antigravity.google/docs/cli/overview/) to modernize a
legacy Java application.

1.  Install and configure
    [Antigravity CLI](https://antigravity.google/docs/cli/install/).
1.  Install and configure the
    [GKE Kubectl auth plugin](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/cluster-access-for-kubectl#install_plugin).
1.  Clone the `cloud-solutions` repository:

    ```bash
    git clone https://github.com/GoogleCloudPlatform/cloud-solutions
    ```

1.  Create a workspace folder on your machine named `java-modernization-demo`:

    ```bash
    mkdir java-modernization-demo
    ```

1.  Configure Antigravity CLI to load the
    [`legacy-app-generator` skill](../gemini-powered-migrations-to-google-cloud/README.md#create-legacy-applications-for-demos).
    For more information about where to store Agent Skills to load them with
    Antigravity CLI, see
    [CLI skill locations](https://antigravity.google/docs/skills/#skills-by-surface).
    Copy the `legacy-app-generator` skill to the `java-modernization-demo`
    directory:

    ```bash
    mkdir -p java-modernization-demo/.agents/skills
    cp -R \
      cloud-solutions/projects/gemini-powered-migrations-to-google-cloud/.agents/skills/legacy-app-generator \
      java-modernization-demo/.agents/skills/
    ```

1.  Copy the Terraform configuration files to deploy the modernized application
    on Google Cloud:

    ```bash
    cp -R \
      cloud-solutions/projects/java-modernization-demo/terraform \
      java-modernization-demo/
    ```

## Scaffold the legacy application

In this section, you generate a demo application.

From your shell:

1.  Change the working directory to the `java-modernization-demo` directory:

    ```shell
    cd java-modernization-demo
    ```

1.  Launch Antigravity CLI:

    ```bash
    agy
    ```

1.  Enter the following prompt in the Antigravity CLI interface and press Enter:

    ```markdown
    Generate a legacy Java 8 application for an Employee Directory. Use Struts
    2, JSP, Tomcat, and Maven for the tech stack. The application must support
    the following operations: list employees, add a new employee, remove an
    employee.

    Include a legacy PostgreSQL 10 container configured using Docker Compose.
    Generate the application in the current directory, after creating a new Git
    repository in that directory, if it's not already a Git repository. The app
    must have a dated User interface (UI), and must be seeded with sample data.

    Configure the Docker Compose file so the application container waits for the
    PostgreSQL database to be healthy before starting.

    For the Struts configuration, keep routing simple: have the root index.jsp
    redirect to a dedicated Struts Action (e.g., employees.action), which then
    forwards to the main UI JavaServer Pages (JSP).

    When creating the Dockerfile, ensure the base image uses a recent Java 8
    build that supports cgroups v2 (such as Eclipse Temurin) to prevent startup
    crashes on modern Docker hosts.

    Ensure files intended for Docker volume mounts, such as database
    initialization scripts, are created with open read permissions
    (e.g., chmod 644) so the container user can read them.

    Expose the application on host port 8090 (or another non-standard port) to
    avoid conflicts with existing local services.

    Try building and running the application using Docker, and try to fix any
    build errors, but if it takes more than 3 attempts, pause and explain the
    error so I can guide you. Ensure all builds and runtimes are strictly
    confined to the Docker containers.

    Verify the application is running by executing a curl request to the
    application's root URL and ensuring it returns a successful HTTP response
    (e.g., a 302 redirect or 200 OK).

    Finally, after you verified that the application builds and runs
    successfully, commit the changes to the Git repository.
    ```

    Depending on your configuration, Antigravity CLI might prompt you to
    activate the `legacy-app-generator` skill. Proceed by selecting "Allow
    once".

Wait for Antigravity CLI to:

- Scaffold the legacy application
- Write the Maven build file
- Generate a `compose.yaml` with a Postgres database seeded with sample employee
  data
- Verify that the legacy application starts successfully.

Sample output:

```markdown
### Summary of Implementation

1. Git Repository Initialization:
    • Initialized Git repository in the current directory.
    • Configured .gitignore to exclude build artifacts.
2. Tech Stack & Architecture:
    • Framework: Apache Struts 2 (EmployeeAction.java, struts.xml, web.xml).
    • View: JSP & JSTL with Struts 2 tags (employees.jsp).
    • Root Routing: index.jsp performs an HTTP redirect (302) to employees.action, which forwards to employees.jsp.
    • Persistence: Plain JDBC DAO (EmployeeDAO.java, DatabaseUtil.java, Employee.java) connecting to PostgreSQL.
    • Operations: List employees, Add new employee, and Remove employee.
    • Dated UI Styling: Styled with Windows 95/Web 1.0 aesthetics (style.css), bevel tables, scrolling marquee banner, visitor counter,
    and a retro intranet header logo (retro_banner.jpg).
3. Database & Seeding:
    • PostgreSQL 10 Alpine configured with compose.yaml.
    • Database schema and 8 sample seed records provided in init.sql with read permissions (644).
    • PostgreSQL container includes a health check using pg_isready.
4. Containerization & Cgroups v2 Compatibility:
    • Multi-stage Dockerfile using maven:3.8-eclipse-temurin-8 for builds and tomcat:9.0-jdk8-temurin for runtime, ensuring cgroups v2
    compatibility on modern Docker hosts.
    • All builds and runtimes confined to Docker containers.
    • Web application exposed on host port 8090 (mapped to container port 8080).
    • compose.yaml configured with depends_on: postgres: condition: service_healthy.
5. Verification:
    • Docker build succeeded on the first attempt.
    • curl -i http://localhost:8090/ returned HTTP/1.1 302 redirecting to /employees.action.
    • curl -L http://localhost:8090/ returned HTTP/1.1 200 OK with the rendered employee table.
    • End-to-end tests verified adding and deleting records through the Struts Actions.
    • Containers stopped cleanly with docker compose down -v.
6. Git Commit:
    • All files staged and committed to branch main (commit 763cf75).
```

## Modernize the backend and upgrade the toolchain

In this section, you upgrade the Java runtime to Java 21 and migrate the backend
framework from Struts to Spring Boot, without modifying the UI.

In the same Antigravity CLI session, enter the following prompt and press Enter:

```markdown
We are going to modernize this legacy Struts application in place. First,
upgrade the runtime to Java 21 and migrate the backend framework to the latest
stable Spring Boot version.

**Critical constraints:**

1.  Update the Maven `pom.xml` accordingly.
2.  Ensure Spring Boot is configured to connect to the existing PostgreSQL
    database.
3.  Ensure `spring.jpa.hibernate.ddl-auto` is explicitly set to `validate` or
    `none` in your `application.properties` so the existing database schema
    and sample data are preserved.
4.  Strip out the Struts actions, replace them with Spring `@RestController` or
    `@Controller` mappings.
5.  Don't modernize the UI. Keep the old JSPs, but replace any Struts-specific
    tags (e.g., `<s:iterator>`) with standard JSTL tags. Do not alter the CSS,
    layout, or HTML structure.
6.  Change the Maven packaging to war. Relocate the JSPs to the standard
    `src/main/webapp/WEB-INF/jsp/` directory. Update the Dockerfile to build and
    run the Spring Boot executable WAR (`java -jar app.war`), which provides
    native support for embedded Tomcat JSP compilation.
7.  Ensure root requests (`/`) are properly redirected to the main controller.
8.  Do not add any new functionality, security layers, or complex
    architectural patterns. Map the existing functionality 1:1.
9.  Ensure all JPA and Servlet imports use the modern `jakarta.` namespace
    required by Spring Boot 3, removing any `legacy javax.*` imports.
10. Ensure your JPA `@Entity` rigorously uses `@Table` and `@Column` annotations
    to map exactly to the existing snake_case database schema so that the
    validation succeeds.
11. Ensure the `spring-boot-starter-actuator` dependency is added to the
    `pom.xml` so the health endpoints are actually served.
12. Update the Dockerfile and `compose.yaml` to run the Spring Boot executable
    WAR (`app.war`) instead of a legacy Tomcat WAR. Try to fix any build errors
    by running the container, but if it takes more than 3 attempts, pause and
    explain the error so I can guide you. Ensure all builds and runtimes are
    strictly confined to the Docker containers.
13. Verify the modernization is successful by running
    `docker compose up --build -d`, waiting for the application to start, and
    executing `curl -v http://localhost:8090/employees` to ensure it returns an
    HTTP 200 with the HTML content.
14. Ensure the application continues to run on port `8080` internally so the
    existing `compose.yaml` mapping to host port `8090` remains valid.
15. After building and running the application successfully, commit the changes.
```

Wait for Antigravity CLI to modernize the application backend, and successfully
build the new executable running inside the updated Docker container. The legacy
database remains intact.

Sample output:

```markdown
### Key Modernization Highlights

1. Java 21 & Spring Boot 3 Upgrade:
    • Modernized pom.xml with spring-boot-starter-parent (3.3.4), targeting Java 21.
    • Added spring-boot-starter-web, spring-boot-starter-data-jpa, and spring-boot-starter-actuator.
    • Included tomcat-embed-jasper and jakarta.servlet.jsp.jstl for native embedded Tomcat JSP compilation.
    • Preserved war packaging for the executable archive (app.war).
2. Persistence Migration (Jakarta JPA & PostgreSQL):
    • Updated Employee.java using the modern jakarta.persistence.* namespace.
    • Configured exact snake_case schema mappings with @Table(name = "employees") and @Column annotations (first_name, last_name,
    job_title, hire_date, etc.).
    • Explicitly configured spring.jpa.hibernate.ddl-auto=validate in application.properties to ensure schema validation passes without
    altering existing tables or sample records.
    • Created EmployeeRepository.java extending JpaRepository.
3. Controller & Routing (Replacing Struts 2):
    • Stripped out Struts Actions, struts.xml, and legacy web.xml.
    • Implemented EmployeeController.java providing 1:1 functional mappings:
        • Root redirect: @GetMapping("/") -> redirect:/employees
        • Directory listing: @GetMapping("/employees")
        • Add employee: @PostMapping({"/employees/add", "/addEmployee"})
        • Remove employee: @GetMapping("/deleteEmployee")
    • Added Application.java extending SpringBootServletInitializer.
4. UI & JSP Preservation:
    • Relocated JSP to the standard directory: employees.jsp.
    • Configured Spring MVC view prefix (/WEB-INF/jsp/) and suffix (.jsp).
    • Replaced all legacy <s:*> Struts tags with standard JSTL tags (<c:forEach>, <c:if>, <c:out>) using jakarta.tags.core.
    • Maintained the exact retro HTML layout, Windows 95 table styling, CSS, and corporate banner.
5. Containerization & Build:
    • Updated Dockerfile to multi-stage:
        • Builder: maven:3.9-eclipse-temurin-21
        • Runtime: eclipse-temurin:21-jre running java -jar /app/app.war
    • Kept internal container port on 8080 mapped to host port 8090 in compose.yaml.

──────
### Verification Results

• Build & Launch: Built and started cleanly on the first attempt with docker compose up --build -d.
• Root Redirect:
curl -i http://localhost:8090/
# HTTP/1.1 302 Found -> Location: http://localhost:8090/employees

• Employee Directory:
curl -v http://localhost:8090/employees
# HTTP/1.1 200 OK with rendered HTML content and 8 seeded records

• Actuator Health:
curl -i http://localhost:8090/actuator/health
# HTTP/1.1 200 OK -> {"status":"UP","components":{"db":{"status":"UP",...}}}

• CRUD Operations: Verified adding new employees and removing records.
──────
### Git Commit

All changes have been committed:

• Commit: 31e2964 (Modernize backend to Java 21 and Spring Boot 3 with Spring Data JPA and Actuator)
```

## Modernize the UI

In this section, you replace the legacy JSP pages with modern Thymeleaf
templates placed in the standard `src/main/resources/templates` directory.

Enter the following prompt in the Antigravity CLI interface and press Enter:

```markdown
Now, let's modernize the UI. Replace the legacy JSP pages with modern
Thymeleaf templates placed in the standard `src/main/resources/templates`
directory. Make the design look modern, clean, and professional.

**Critical constraints:**

1.  You must include standard HTML IDs on key elements for testing (e.g.
    `id='employee-list'`).
2.  Delete the old `.jsp` files, and remove the legacy `spring.mvc.view.`
    configurations from `application.properties` to clean up the project.
3.  Update the build file (e.g., `pom.xml`) to remove legacy JSP/JSTL
    dependencies and add `spring-boot-starter-thymeleaf`, and change the
    `<packaging>` from `war` back to `jar`.
4.  Extract any inline CSS from the legacy JSPs into a dedicated external
    stylesheet located in `src/main/resources/static/css/main.css` and link it in
    the Thymeleaf template.
5.  Carefully preserve any static assets (CSS, images) and migrate them to the
    appropriate Spring Boot static folder.
6.  Verify and update any Spring MVC Controllers to ensure they correctly map to
    the new Thymeleaf template names.
7.  Verify the application builds successfully. Use Docker Compose to build and
    verify the application, not local tools. Verify the app compiles, then use
    `docker compose up --build -d` to ensure the container starts without
    crashing, curling `http://localhost:8090/employees`. Then tear it down using
    `docker compose down -v`.
8.  Commit the changes to the Git repository.
```

Wait for Antigravity CLI to remove the legacy view layer and implement a clean,
responsive Thymeleaf UI.

Sample output:

```markdown
### Summary of Changes

1. Thymeleaf Template:
    • Created employees.html replacing the legacy JSP pages.
    • Designed a modern, clean, and professional layout with metrics cards, responsive table styling, status pills, and accessible form
    controls.
    • Added standard HTML IDs on key elements for testing:
        • id="employee-list" (Directory table)
        • id="employee-count" (Total employee metric badge)
        • id="add-employee-form" (Enrollment form)
        • id="first-name", id="last-name", id="email", id="department", id="job-title", id="extension", id="hire-date" (Input fields)
        • id="submit-btn" (Submit button)
        • id="success-message" and id="error-message" (Alert notifications)
        • id="delete-employee-${emp.id}" (Action buttons)

2. Cleaned Up Legacy JSP & View Configuration:
    • Deleted all legacy JSP files and the src/main/webapp hierarchy.
    • Removed legacy spring.mvc.view.prefix and spring.mvc.view.suffix settings from application.properties.
3. Maven & Packaging Update:
    • Updated pom.xml:
        • Added spring-boot-starter-thymeleaf.
        • Removed legacy tomcat-embed-jasper and Jakarta JSTL dependencies.
        • Changed <packaging> from war back to jar.

4. Styling & Asset Migration:
    • Created dedicated external stylesheet main.css linked via th:href="@{/css/main.css}".
    • Preserved all static assets in src/main/resources/static/.
5. Controller & Main Class:
    • Verified EmployeeController.java maps cleanly to template employees and supports flash messages/parameters.
    • Cleaned up Application.java for executable JAR packaging.
6. Containerization:
    • Updated Dockerfile to build and run the executable JAR: java -jar /app/app.jar.

──────
### Verification & Testing

• Built and ran with docker compose up --build -d.
• Executed curl -v http://localhost:8090/employees, verifying HTTP/1.1 200 OK and modern HTML markup containing all designated testing
IDs.
• Tore down containers and volumes with docker compose down -v.
──────
### Git Commit

• Commit: 4dc6a2f (Modernize UI: Replace legacy JSP with modern Thymeleaf templates, clean CSS, and JAR packaging)
```

## Test the application locally

In this section, you instruct Antigravity to act as an end-user and verify the
modernization was successful.

Enter the following prompt in the Antigravity CLI interface and press Enter:

```markdown
1. Start the application with `docker compose up --build -d`.
2. Interact with the application running at `http://localhost:8090`.
3. Use curl to send a POST request to `/employees/add` with the form data:
   `firstName=Jane, lastName=Doe, department=Engineering, and email=jane.doe@example.com`.
4. Verify the addition was successful by curling the `GET /employees` endpoint
   and checking that 'Jane Doe' is present in the returned HTML.

After verifying, tear down the application and its database volume using
`docker compose down -v`.
```

Wait for Antigravity CLI to finish verifying the application.

Sample output:

```markdown
### Step-by-Step Execution & Results

#### 1. Start Application
docker compose up --build -d
• Both employee-directory-db (healthy) and employee-directory-app started up in ~6 seconds.
#### 2. Interact with Application

curl -i http://localhost:8090/
Response:
HTTP/1.1 302
Location: http://localhost:8090/employees
Content-Length: 0
#### 3. Send POST Request to Add Jane Doe

curl -i -X POST http://localhost:8090/employees/add \
    -d "firstName=Jane" \
    -d "lastName=Doe" \
    -d "department=Engineering" \
    -d "email=jane.doe@example.com"

Response:

HTTP/1.1 302
Location: http://localhost:8090/employees;jsessionid=...?...
Content-Length: 0

#### 4. Verify 'Jane Doe' in Returned HTML

curl -s http://localhost:8090/employees | grep -C 3 "Jane Doe"

Returned HTML Snippet:

<tr>
    <td><span class="badge-id">#9</span></td>
    <td class="emp-name">Jane Doe</td>
    <td>
        <a href="mailto:jane.doe@example.com" class="emp-email">jane.doe@example.com</a>
    </td>
    <td>
        <span class="department-pill">Engineering</span>
    </td>
    <td>Staff Member</td>
    <td><span class="ext-badge">x1000</span></td>
    <td>2026-10-06</td>
    <td style="text-align: center;">
        <a id="delete-employee-9"
            href="/deleteEmployee?id=9"
            class="delete-btn" onclick="return confirmDeletion(9, 'Jane Doe');">
            &#128465; Delete
        </a>
    </td>
</tr>

#### 5. Teardown

docker compose down -v

All containers, volumes, and network resources were stopped and removed.
```

## Provision Google Cloud infrastructure

To prepare the landing zone on Google Cloud for the application to run, you
provision the Google Cloud infrastructure using Terraform.

The Terraform configuration in the `terraform` directory provisions:

- A Google Kubernetes Engine (GKE) cluster in Autopilot mode with Gateway API
  support enabled.
- A Cloud SQL for PostgreSQL instance to replace our local containerized
  database.
- An Artifact Registry repository for hosting the application's container
  images.
- Cloud Build API to build and push container images to Artifact Registry.

### Execute Terraform scripts to provision GKE and database resources

Leave the Antigravity CLI terminal running, and open a new terminal in your
shell:

1.  Change the working directory to the `java-modernization-demo` directory:

    ```shell
    cd java-modernization-demo
    ```

1.  Replace `YOUR_PROJECT_ID` with your Google Cloud project ID:

    ```bash
    export TF_VAR_project_id="YOUR_PROJECT_ID"
    ```

    Where:
    - `YOUR_PROJECT_ID` is the ID of the Google Cloud project where you want to
      provision resources for this demo.

1.  Authenticate and configure your Google Cloud project for Terraform:

    ```bash
    # Authenticate to manage resources with the gcloud CLI
    gcloud auth login

    # Set the Google Cloud project and billing
    gcloud config set project $TF_VAR_project_id
    gcloud config set billing/quota_project $TF_VAR_project_id

    # Enable required APIs for Cloud Resource Manager and Compute Engine
    gcloud services enable cloudresourcemanager.googleapis.com compute.googleapis.com

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

    Review the proposed plan, and answer `yes` to proceed with the provisioning
    process.

1.  Wait for Terraform to provision the resources. This process takes
    approximately 15 minutes.

1.  Capture and display the infrastructure details:

    ```bash
    export PROJECT_ID=$(terraform -chdir=terraform output -raw project_id)
    export REGION=$(terraform -chdir=terraform output -raw region)
    export REPO_NAME=$(terraform -chdir=terraform output -raw artifact_registry_repo)
    export LB_IP=$(terraform -chdir=terraform output -raw load_balancer_ip)
    ```

> [!NOTE]
>
> **Terraform backend**: This demo uses a local Terraform backend. In a
> production environment, we recommend that you configure a
> [remote backend on Cloud Storage](https://docs.cloud.google.com/docs/terraform/resource-management/store-state).

## Build container images

Build and push container images to Artifact Registry using Google Cloud Build.

In your terminal:

1.  Build the container image for the application:

    ```bash
    gcloud builds submit --suppress-logs \
      --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/java-modernization-demo:latest \
      .
    ```

1.  Wait for the [build](https://console.cloud.google.com/cloud-build/builds) to
    complete. This process takes several minutes.

## Create deployment and Google Cloud infrastructure context

In this section, you collect all infrastructure details from Terraform outputs
and build artifacts into a single context file named `kubernetes-context.md` in
Markdown format. Antigravity CLI uses this file to get the necessary context to
interact with the Google Cloud infrastructure.

Go back to the Antigravity CLI interface, enter the following prompt and press
Enter:

```markdown
Create a file named `kubernetes-context.md` in Markdown format with the
following details:

- Google Cloud project ID
- Default region
- Load balancer IP address
- Load balancer IP address name
- Artifact Registry repository name and URL. Construct the Artifact Registry URL
  using the format: [region]-docker.pkg.dev/[project_id]/[repository_name]
- Cloud SQL connection name
- Database instance username and password.
- Database names
- Name and tag of the container image: `java-modernization-demo:latest`

Get the details using Terraform outputs:
`terraform -chdir=terraform output -json`

The outputs are defined in
`terraform/output.tf`.
```

Wait for Antigravity CLI to create the `kubernetes-context.md` file.

## Generate Kubernetes deployment descriptors

In this section, you generate the Kubernetes Deployment and Service manifests
for running the application on GKE.

Enter the following prompt in the Antigravity CLI interface and press Enter:

```markdown
We are now going to prepare the modernized Spring Boot application for
deployment on Google Kubernetes Engine (GKE).

1.  Include the necessary Kubernetes Deployment and Service manifests to run the
    Spring Boot container on the GKE cluster.
2.  Ensure the Spring Boot application is appropriately configured to connect to
    the Cloud SQL instance (e.g., using the Cloud SQL Auth proxy or standard
    connection strings).
3.  Commit the changes to the Git repository.

**Critical constraints:**

1.  Place all Kubernetes descriptor files in a new `kubernetes/` directory.
    Do not create a `kustomization.yaml` file; use standalone Kubernetes manifests
    so they can be applied directly with `kubectl apply -f kubernetes/`.
2.  Refer to `kubernetes-context.md` for information about infrastructure.
3.  Namespace: Use a dedicated namespace named `java-modernization-demo` for all
    resources.
4.  Security (Workload Identity): Create a Kubernetes Service Account named
    `java-backend-ksa`. IMPORTANT: Do NOT add any annotations for a Google
    Service Account (GSA). We are using direct mapping for the KSA identity.
5.  Common Config: Create a Secret containing the database username, password,
    and a `SPRING_DATASOURCE_URL` formatted to connect to the sidecar at
    `jdbc:postgresql://127.0.0.1:5432/[database_name]`.

Deployment Specs:

-   Replicas: 1
-   Service Account: `java-backend-ksa`
-   Image Path: Pull from app-repo using the latest tags found in the context
    file
-   Environment Overrides:
    -   Set `SPRING_PROFILES_ACTIVE=gke` and
        `SPRING_JPA_HIBERNATE_DDL_AUTO=update`.
    -   IMPORTANT: To prevent the application defaulting to local H2 settings,
        explicitly set
        `SPRING_DATASOURCE_DRIVER_CLASS_NAME=org.postgresql.Driver`
        and
        `SPRING_JPA_DATABASE_PLATFORM=org.hibernate.dialect.PostgreSQLDialect`.
    -   Set `MANAGEMENT_ENDPOINT_HEALTH_PROBES_ENABLED=true` to enable
        Kubernetes actuator endpoints.
    -   Set `MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE=health` (or `*`) to
        ensure the actuator endpoints are accessible over HTTP for the probes.
-   Resources: Set conservative requests to ensure pods schedule successfully
    without hitting Google Compute Engine CPU quotas.
-   Security Context: Apply a `securityContext` to the Pod template (e.g.,
    `fsGroup: 1000`, `runAsUser: 1000`) to preemptively resolve any Kubernetes
    PersistentVolume or init permissions when mounting files or storage.
-   Deployment Strategy: Apply `maxSurge: 0` and `maxUnavailable: 1` to prevent
    quota exhaustion during rolling updates.
-   Probes: Configure HTTP `livenessProbe` and `readinessProbe` targeting the
    `/actuator/health` endpoint. Also, set `initialDelaySeconds` to `60` to
    prevent premature kills while JPA initializes and seeds the database.

Sidecars:

-   Add the Cloud SQL Auth Proxy sidecar
    (`gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.14.2`) to EVERY deployment,
    with resource requests set to `50m CPU` and `256Mi Memory`.
-   Arguments: `--private-ip`, `--port=5432`, and the dynamic connection name
    from `kubernetes-context.md`.

Service:

-   Container Ports: Ensure the Java application container exposes port 8080.
-   Service: Create a Service exposing port 80 targeting the container's port
    8080.

External Access (Gateway):

-   IP Name Resolution: Use
    `gcloud compute addresses list --filter="address=[IP_FROM_CONTEXT]"` to find
    the actual reserved Google Cloud IP Name for the Load Balancer IP provided
    in `kubernetes-context.md`.
-   Create a Gateway using the `gke-l7-global-external-managed` GatewayClass.
    Bind it to the external IP by using `type: NamedAddress` and specifying the
    reserved Google Cloud IP Name (e.g., `java-modernization-demo-lb-ip`) found
    in the context file, NOT the raw IP address string.
-   Routing Rules: Configure HTTPRoute rules to direct traffic arriving on
    Gateway port 80 to the Service on port 80.
-   Load Balancer Health Check: Create a `HealthCheckPolicy`
    (`networking.gke.io/v1`) targeting your `Service`. Configure it to use
    `type: HTTP` and override the `requestPath` to `/actuator/health` so the
    Google Cloud Load Balancer doesn't fail by checking the root `/` path.
```

Wait for Antigravity CLI to generate Kubernetes configuration files to deploy
the application on GKE.

## Deploy the application

In this section, you authenticate and configure `kubectl` to deploy the
application to the GKE cluster.

Enter the following prompt in the Antigravity CLI interface and press Enter:

```markdown
Deploy all resources in the /kubernetes folder. Ensure the namespace is created
first. After you apply the resources, watch the pods in the new namespace and
let me know when all of them (including the sidecars) are Running and Ready.

**Critical constraints:**

1.  Deploy the Kubernetes descriptors in the `kubernetes/` directory.
2.  Refer to `kubernetes-context.md` for information about infrastructure.
3.  Configure `kubectl` to authenticate with the GKE cluster with the
    `gcloud container clusters get-credentials` command.
4.  Don't build and push container images locally because they are already
    available in the Artifact Registry repository.
5.  Prefer using the pre-built container images in the Artifact Registry
    repository. However, if the deployment fails because the pre-built image is
    outdated or missing required dependencies (like Actuator), you MUST tell the
    user, suggesting to rebuild and push the images using Cloud Build.
6.  After you apply the resources, wait for the pods in the new namespace to be
    Running and Ready. Use a timeout of at least 5 minutes (--timeout=300s) to
    account for the 60-second initialDelaySeconds configured in the probes.
7.  In addition to the pods, verify that the Gateway resource has successfully
    acquired an IP and reached the Programmed: True status, and ensure the
    HTTPRoute is accepted. (Note: Reaching Programmed: True may take 3-5 minutes
    while Google Cloud provisions the load balancer; you can use
    `kubectl wait --for=condition=Programmed gateway/employee-gateway -n java-modernization-demo --timeout=5m`).
```

Wait for Antigravity CLI to deploy the application on GKE.

## Test the application

In this section, you verify that the application works as expected when deployed
to Google Cloud.

Enter the following prompt in the Antigravity CLI interface and press Enter:

```markdown
Test the application deployed on GKE:

1. Try reaching the application endpoints on the load balancer IP.
   Note: It might take 5-10 minutes for the load balancer to activate.

    - Poll the endpoints using `curl` (e.g., using a `while` loop and
      `sleep 10`) to continuously check the root URL until it receives a
      `200 OK` or `302 Found` status.
    - Build the `curl` command so that it handles the waiting for `503`, `502`,
      `404`, and other errors.

2. Perform an end-to-end transaction:

    - Create an employee: Send an HTTP POST request to `/employees/add` with
      form data (e.g., `firstName`, `lastName`, `department`, and `email`).
    - Verify: Fetch the `/employees` list and verify the newly created
      employee's name appears in the HTML response.

**Critical constraints:**

1.  Refer to `kubernetes-context.md` for information about infrastructure.
```

Wait for the Antigravity CLI to finish testing.

## Clean up resources

To avoid incurring charges, delete the demo infrastructure.

Go back to your terminal and run the following command:

```bash
terraform -chdir=terraform destroy
```

> [!NOTE]
>
> **Confirming resource deletion**: Review the resources that Terraform plans to
> delete. When prompted, enter `yes` to confirm and proceed with the deletion.

## What's next

- Learn more about
  [Antigravity CLI](https://antigravity.google/docs/cli/overview/).
- Discover how you can use
  [Gemini to accelerate your migrations and modernization efforts](../gemini-powered-migrations-to-google-cloud/README.md).
