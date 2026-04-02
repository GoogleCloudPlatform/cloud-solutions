# Demo: Gemini-Powered Java Modernization

<!--
    Disabling markdownlint MD029 to provide explicit ordering to avoid confusing
    the LLM.
-->
<!-- markdownlint-disable MD029 -->

**Objective:** Write demo instructions to demonstrate how to use Gemini CLI to
modernize a legacy Struts/JSP application to a modern Spring Boot/Thymeleaf
stack while preserving business logic and data.

IMPORTANT: don't run the demo, just write the instructions.

The prompts listed in this spec are directional examples that need to be
expanded when diving deeper on design and implementation.

When writing instructions:

- Refer to "the presenter" as "you".
- Use the imperative: "do this".
- Refer to the LLM as Gemini.
- Read .gemini/GEMINI.md and follow the guidance there.

## Phase 0: Demo Setup

Write a README.md in Markdown format to guide the demo presenter. The presenter
will first use the `legacy-app-generator` skill to scaffold a dated application.

Also, explain that if the skill `legacy-app-generator` is not already available
in the context, the presenter should prompt the LLM to load it from the
`projects/gemini-powered-migrations-to-google-cloud/.agents/skills` directory,
and not to copy or move the `legacy-app-generator` skill files anywhere, just
load the skill in the current context.

Also, the README.md should include:

- A Requirements section that list the dependencies and tools needed to run the
  demo, including Docker and Docker Compose, and the versions that were used to
  build and test the demo. To get the versions, run commands to get the versions
  of the tools, and mention the version used in the demo. Example: "Docker.
  Tested with version 29.3.1".
- An introduction after the first heading that explains what the guide is about,
  and lists the steps that the reader goes through when following it.

**Prompt to Agent:**

```markdown
Generate a legacy Java 8 application for an Employee Directory. Use Struts, JSP,
Tomcat, and Maven for the tech stack. Include a legacy PostgreSQL 10
container configured via Docker Compose. Generate the application in the
`employee-dir-app` directory, after creating a new Git repository in that
directory. The app must have a dated UI, and must be seeded with sample data.

Try building and running the application using Docker, and try to fix any build
errors, but if it takes more than 3 attempts, pause and explain the  error so I
can guide you. Ensure all builds and runtimes are strictly confined to the
Docker containers.

Finally, after you verified that the application builds and runs successfully,
commit the changes to the Git repository.
```

**Expected Outcome:** The agent will scaffold the Struts app, write the legacy
Maven build file, generate a `compose.yaml` with a Postgres 10 database seeded
with sample employee data, and verify that it boots successfully.

## Phase 1: Modernize the backend and upgrade the toolchain

Extend the README.md: the presenter instructs the agent to upgrade the Java
runtime and migrate the underlying framework, without touching the UI.

Update the Requirements section and the steps section in the README.md if
necessary.

**Prompt to Agent:**

```markdown
We are going to modernize this legacy Struts application in place. First,
upgrade the runtime to Java 21 and migrate the backend framework to the latest
stable Spring Boot version.

**Critical Constraints:**

1.  Update the Maven `pom.xml` accordingly.
2.  Ensure Spring Boot is configured to connect to the existing PostgreSQL
    database.
3.  Ensure `spring.jpa.hibernate.ddl-auto` is explicitly set to `validate` or
    `none` in your `application.properties` so the existing database schema
    and sample data are preserved.
4.  Strip out the Struts actions, replace them with Spring `@RestController` or
    `@Controller` mappings.
5.  Do not add any new functionality, security layers, or complex
    architectural patterns. Map the existing functionality 1:1.
6.  Update the Dockerfile and `compose.yaml` to run the Spring Boot executable
    JAR instead of a legacy Tomcat WAR. Try to fix any build errors by running
    the container, but if it takes more than 3 attempts, pause and explain the
    error so I can guide you. Ensure all builds and runtimes are strictly
    confined to the Docker containers.
7.  After building and running the application successfully, commit the changes.
```

**Expected Outcome:** The agent strips out the Struts actions, upgrades the
`pom.xml`, and successfully builds the new executable `.jar` running inside the
updated Docker container. The legacy database remains intact.

Update the Requirements section and the steps section in the README.md if
necessary.

## Phase 2: Modernize the UI

Extend the README.md: With the backend modernized, the presenter tasks the agent
with replacing the dated JSP pages with a modern server-side templating engine
(Thymeleaf).

Update the Requirements section and the steps section in the README.md if
necessary.

**Prompt to Agent:**

```markdown
Now, let's modernize the UI. Replace the legacy JSP pages with modern
Thymeleaf templates placed in the standard `src/main/resources/templates`
directory. Make the design look modern, clean, and professional.

**Critical Constraints:**

1.  You must include standard HTML IDs on key elements for testing.
    Specifically: `id='add-employee-form'`, `id='input-name'`,
    `id='submit-btn'`, and `id='employee-list'`.
2.  Delete the old `.jsp` files and Struts `.xml` configurations to clean up
    the project.
3.  Carefully preserve any static assets (CSS, images) and migrate them to the
    appropriate Spring Boot static folder.
4.  Verify the app still compiles and runs in Docker.
5.  Commit the changes to the Git repository.
```

**Expected Outcome:** The agent removes the legacy view layer and implements a
clean, responsive Thymeleaf UI. The project structure is cleaned up, and the DOM
is prepped with the exact hooks needed for the final autonomous testing step.

## Phase 3: Test the application locally

Extend the README.md: To close the demo, the presenter asks the Agent to act as
an end-user and verify the modernization was successful by reaching to the
application.

Update the Requirements section and the steps section in the README.md if
necessary.

**Prompt to Agent:**

```markdown
Navigate to the locally running application. Find the `add-employee-form` and
add a new employee named 'Jane Doe'. Then, verify that 'Jane Doe' successfully
appears in the `employee-list`.
```

**Expected Outcome:** The audience watches the agent autonomously navigate the
newly modernized UI. The agent will read the DOM, locate the HTML IDs we
injected in Phase 2, submit the form, and confirm the database successfully
saved the new record, proving the end-to-end migration works perfectly.

## Phase 4: Provision Google Cloud infrastructure

Write the Terraform configuration files to provision the following resources to
deploy the application on Google Cloud:

1.  A Google Kubernetes Engine (GKE) cluster in Autopilot mode with Gateway API
    support enabled.
2.  A Cloud SQL for PostgreSQL instance to replace our local containerized
    database.
3.  An Artifact Registry repository for hosting the application's container
    images.
4.  Cloud Build API to build and push container images to Artifact Registry.

Extend the README.md: To prepare the landing zone on Google Cloud for the
application to run, the presenter provisions Google Cloud infrastructure using
Terraform.

Update the Requirements section and the steps section in the README.md if
necessary.

**Critical Constraints:**

1.  Place all Terraform configuration files in a new `terraform/` directory.
2.  Create a Dockerfile named `buildtest.dockerfile` using the latest stable
    Terraform image to run `terraform init` and `terraform validate`.
3.  Build and run this validation container to ensure the Terraform
    configuration is syntactically valid and properly initialized. If there are
    any validation errors, attempt to fix them. If it takes more than 3
    attempts, pause and explain the error.
4.  Use `us-central1` as the default region, and `us-central1-a` as the default
    zone.

## Phase 5: Build container images

Extend the README.md: To prepare the container images to run the application,
the presenter:

1.  Submits Cloud Build build jobs using the `gcloud` command line tool.
2.  Waits for the build jobs to complete by looking at the Cloud Build build
    summary page on Cloud Console.

Update the Requirements section and the steps section in the README.md if
necessary.

## Phase 6: Store deployment and Google Cloud infrastructure context

Extend the README.md: The presenter collects all infrastructure details from
Terraform outputs and build artifacts into a single context file in Markdown
format named `kubernetes-context.md` to use in the next sections. Details
include:

- Google Cloud project ID
- Default region
- Load balancer IP addresses
- Artifact Registry repository name and URL
- Cloud SQL connection name
- Database instance username and password
- Database names
- List of the available container images in the Artifact Registry repository

## Phase 7: Generate Kubernetes Deployment descriptors

Extend the README.md: To deploy the modernized application on GKE, the presenter
instructs the agent to write Kubernetes descriptors.

Update the Requirements section and the steps section in the README.md if
necessary.

**Prompt to Agent:**

```markdown
We are now going to prepare the modernized Spring Boot application for
deployment on Google Kubernetes Engine (GKE).

1.  Include the necessary Kubernetes Deployment and Service manifests to run the
    Spring Boot container on the GKE cluster.
2.  Ensure the Spring Boot application is appropriately configured to connect to
    the Cloud SQL instance (e.g., using the Cloud SQL Auth proxy or standard
    connection strings).
3.  Commit the changes to the Git repository.

**Critical Constraints:**

1.  Place all Kubernetes descriptor files in a new `kubernetes/` directory.
2.  Refer to `kubernetes-context.md` for information about infrastructure.
3.  Namespace: Use a dedicated namespace for all resources.
4.  Security (Workload Identity): Create a Kubernetes Service Account named
    `java-backend-ksa`. IMPORTANT: Do NOT add any annotations for a Google
    Service Account (GSA). We are using direct mapping for the KSA identity.
5.  Common Config: Create a Secret for datasource name and password.

Deployment Specs (Per Service):

- Replicas: 1
- Service Account: `java-backend-ksa`
- Image Path: Pull from app-repo using the latest tags found in the context
  file
- Environment Overrides:
   - Set `SPRING_PROFILES_ACTIVE=gke` and `SPRING_JPA_HIBERNATE_DDL_AUTO=update`.
   - IMPORTANT: To prevent the application defaulting to local H2 settings,
     explicitly set `SPRING_DATASOURCE_DRIVER_CLASS_NAME=org.postgresql.Driver`
     and `SPRING_JPA_DATABASE_PLATFORM=org.hibernate.dialect.PostgreSQLDialect`.
   - Set `MANAGEMENT_ENDPOINT_HEALTH_PROBES_ENABLED=true` to enable Kubernetes
     actuator endpoints.
- Resources: Set conservative requests to ensure pods schedule successfully
  without hitting Google Compute Engine CPU quotas.
- Security Context: Apply a `securityContext` to the Pod template
  (e.g., `fsGroup: 1000`, `runAsUser: 1000`) to preemptively resolve any
  Kubernetes PersistentVolume or init permissions when mounting files or
  storage.
- Deployment Strategy: Apply `maxSurge: 0` and `maxUnavailable: 1` to all
  services to prevent quota exhaustion during rolling updates.
- Probes: Configure HTTP `livenessProbe` and `readinessProbe` targeting the
  `/actuator/health` endpoint.
  (example: `/service-a/actuator/health`). Also, set `initialDelaySeconds` to
  `300` to prevent premature kills while JPA initializes and seeds the database.

Sidecars:

- Add the Cloud SQL Auth Proxy sidecar
  (`gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.14.2`) to EVERY deployment,
  with resource requests set to `50m CPU` and `256Mi Memory`.
- Arguments: `--private-ip`, `--port=5432`, and the dynamic connection name from
  `kubernetes-context.md`.

External Access (Gateway):

- Create a Gateway and HTTPRoutes to expose the service publicly.
- Routing Rules: configure routing routes for the service.
```

**Expected Outcome:** The agent generates valid Kubernetes configuration files
to deploy the application on GKE.

Update the Requirements section and the steps section in the README.md if
necessary.

## Phase 8: Deploy the application

Extend the README.md: To deploy the application on GKE, the presenter:

1.  Prepares the deployment environment by authenticating and configuring
    `kubectl`.
2.  Instructs the agent to deploy the application on GKE.

Update the Requirements section and the steps section in the README.md if
necessary.

**Prompt to Agent:**

```markdown
Deploy all resources in the /kubernetes folder. Ensure the namespace is created
first. After you apply the resources, watch the pods in the new namespace and
let me know when all of them (including the sidecars) are Running and Ready.

Commit the changes to the Git repository.

**Critical Constraints:**

1.  Deploy the Kubernetes descriptors in the `kubernetes/` directory.
2.  Refer to `kubernetes-context.md` for information about
    infrastructure.
```

**Expected Outcome:** The agent deploys the application on GKE.

## Phase 9: Test the application

Extend the README.md: To test the application, the presenter instructs the agent
to test the application locally.

Update the Requirements section and the steps section in the README.md if
necessary.

**Prompt to Agent:**

```markdown
Test the external access to the deployed application:

1. Try reaching the application endpoints on the load balancer IP.
   Note: It might take 5-10 minutes for the load balancer to activate. Retry if
   you receive a `404` or `502` response.

2. Perform an end-to-end transaction:

    - Create an employee.
    - Verify that the employee has been created

**Critical Constraints:**

1.  Refer to `kubernetes-context.md` for information about infrastructure.
```

**Expected Outcome:** The agent verifies that the application works.
