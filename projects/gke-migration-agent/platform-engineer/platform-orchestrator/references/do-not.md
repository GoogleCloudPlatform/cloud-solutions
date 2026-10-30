# Do not trigger when (anti-patterns)

The platform orchestrator is an end-to-end program manager for a full cluster
migration. You must **NOT** trigger this skill under the following
circumstances:

- **Isolated Tasks:** The user has already produced a migration plan and wants
  help with one specific phase (e.g., "translate these Network policies" or
  "migrate this single ECR repo"). Call the specific phase skill directly
  instead of the orchestrator.
- **Conceptual Questions:** The user wants conceptual education (e.g., "how does
  Workload Identity work" or "what is the difference between an ALB and a
  Gateway"). Answer directly without invoking a skill.
- **Unsupported Sources:** The source cluster is something other than Amazon EKS
  (e.g., AKS, on-prem Kubernetes, or GKE-to-GKE migrations). This orchestration
  graph is currently explicitly designed for EKS.
- **Stateful Database Migrations:** Do not attempt to lift-and-shift stateful
  databases (PostgreSQL, DynamoDB, Redis) into pods. You must abort the
  migration if the assessment phase detects them and prompt the user to migrate
  them to managed Google Cloud database services.
