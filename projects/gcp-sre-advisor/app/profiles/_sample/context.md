# Workload architecture context

## 1. Business role and user impact

Customer-facing digital commerce platform handling catalog browsing, cart
management, checkout authorization, and asynchronous order fulfillment.
Availability drops or elevated tail latency during business hours directly
affect transaction conversion.

## 2. Critical request and data flow

External HTTPS requests enter through a Global External Application Load
Balancer protected by Cloud Armor and Cloud CDN, route to stateless Cloud Run
APIs for checkout and GKE services for fulfillment orchestration, read session
state from Memorystore for Redis, persist transactional records in regional
high-availability Cloud SQL for PostgreSQL, and publish order events to Pub/Sub.

## 3. Architectural decisions and constraints

Outbound payment authorization calls traverse a dedicated Cloud NAT gateway with
static external IP addresses allowlisted by the payment processor. Internal
service-to-service traffic runs over Shared VPC subnets in
`example-prod-net-host`.

## 4. Operational conventions

Infrastructure changes are delivered through Terraform repositories built by
Cloud Build pipelines. Emergency mitigations require read-only verification
first and a corresponding declarative reconciliation change.
