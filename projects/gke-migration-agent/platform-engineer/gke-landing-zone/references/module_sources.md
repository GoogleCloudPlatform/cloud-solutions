# Module sources

Check each module's registry page for the current release and pin it. The
constraints below were current when this skill was written. Bump them, do not
pin lower.

| Purpose                                                                 | Module                                                                                      | Constraint         |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------ |
| API enablement on existing projects                                     | `terraform-google-modules/project-factory/google//modules/project_services`                 | latest on registry |
| Virtual Private Cloud (VPC), subnets, Network Address Translation (NAT) | `terraform-google-modules/network/google`                                                   | `~> 18.1`          |
| GKE Standard, hardened                                                  | `terraform-google-modules/kubernetes-engine/google//modules/safer-cluster`                  | `~> 44.0`          |
| GKE Autopilot, private                                                  | `terraform-google-modules/kubernetes-engine/google//modules/beta-autopilot-private-cluster` | `~> 44.0`          |
