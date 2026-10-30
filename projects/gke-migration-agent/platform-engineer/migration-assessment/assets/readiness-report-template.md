<!--
 Copyright 2026 Google LLC

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
-->

# Amazon Elastic Kubernetes Service (EKS) to Google Kubernetes Engine (GKE) migration readiness report

<!--
  Disabling markdownlint MD029 to provide explicit ordering to avoid
  confusing the LLM.
-->
<!-- markdownlint-disable MD029 -->
<!--
  Disabling markdownlint MD030 to allow the list overflowing to numbers
  >=10.
-->
<!-- markdownlint-disable MD030 -->

- **Run:** {{run_id}}
- **Generated:** {{date}}

## 1. Executive summary

Five bullets. The single most important blocker. The estimated requirements. The
recommended first move. The biggest risk.

| Cluster     | Workloads (R/T/H/B) | Effort Profile     |
| ----------- | ------------------- | ------------------ |
| {{cluster}} | {{counts}}          | {{effort_summary}} |

## 2. Scope

What was discovered: clusters, namespaces, workloads, regions, accounts.
Reference the inventory.

## 3. Scorecard

Per cluster, per workload class. Bucket distribution. The 4-axis breakdown for
any workload scoring below Tractable.

## 4. Blockers

Named, categorized, each with a resolution path. Cross-reference blockers.md.

## 5. Phased plan

Foundation and internal tools → Stateless business apps → Stateful and
mission-critical apps → Decommission. Generic sequenced table using relative
phases.

## 6. Effort profile

Workload bucket counts and qualitative complexity summary. Do not estimate days.

## 7. Risks and guardrails

Each named risk paired with a measurable guardrail.

## 8. Open questions

Decisions the user must make before the migration proceeds.
