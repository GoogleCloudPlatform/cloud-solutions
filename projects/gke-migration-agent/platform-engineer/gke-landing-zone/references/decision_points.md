# Decision points

You must confirm these defaults or log deviations with the user during Step 1:

| Decision                                        | Default (Enterprise Best Practice)                       | When to deviate (Downgrade/Alternative)                                                     |
| ----------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Autopilot vs Standard                           | Autopilot                                                | Readiness report flags privileged DaemonSets, custom OS/kernels, or node-level access       |
| Release channel                                 | Stable for prod, Regular elsewhere                       | Rapid only for disposable test clusters                                                     |
| Regional vs zonal                               | Regional                                                 | Zonal only for ephemeral test clusters                                                      |
| Network scope                                   | Shared VPC                                               | Ask user if the supplied project should host the Shared VPC, or request a host project      |
| Control plane access                            | Domain Name System (DNS) endpoint, IP endpoints disabled | External endpoint with authorized networks when no Virtual Private Network (VPN) exists yet |
| Master Authorized Networks                      | Restricted to VPN/Proxy CIDRs                            | Open temporarily if no VPN exists and public access is required                             |
| Pods range size                                 | /16 per env and region                                   | Larger when discovery signals exceed roughly 60 nodes                                       |
| Fleet Registration                              | Registered to Fleet by Default                           | Only for disposable, ephemeral Proof of Concept (POC) clusters                              |
| One fleet vs many                               | Per-environment fleet                                    | Single fleet only for very small estates                                                    |
| CMEK on cluster Database (DB)                   | Yes                                                      | No CMEK only if no compliance requirement and the cost is unjustified                       |
| Binary Authorization                            | Enabled (Audit mode initially)                           | Disabled only if images are pulled from unverified 3rd party repos with no pipeline         |
| Maintenance Windows                             | Configured (Off-peak hours)                              | Ephemeral clusters where uptime is not critical                                             |
| Fleet features (Config Sync, Policy Controller) | Off                                                      | Only when a confirmed decision or the readiness report names them                           |
