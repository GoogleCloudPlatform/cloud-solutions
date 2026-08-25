# Phase 3: The Regulator-Grade System of Action

> _Achieving Deterministic Reasoning and Explainability through Dual-Graph
> Ontologies_ **Series:** Beyond the Chatbot: The Enterprise Architecture for
> Systems of Action

## Navigation

- **[Introduction](index.md)**
- **[Phase 1: Breaking the Probabilistic
  Wall](phase1_breaking_the_probabilistic_wall.md)**
- **[Phase 2: Anchoring Agents in Structured Business
  Reality](phase2_anchoring_agents_in_structured_business_reality.md)**
- **[Phase 3: Regulator-Grade System of
  Action](phase3_regulator_grade_system_of_action.md)**

---

## Introduction

As enterprises transition from **systems of intelligence** (AI assistants that
read and summarize) to autonomous **systems of action** (agents executing
high-stakes transactions, allocating budgets, and evaluating contractual terms),
the primary architectural constraint shifts from raw model capability to
**verifiable safety and governance**. In regulated industries—such as digital
advertising, financial services, and healthcare decision support—execution
velocity requires deterministic safety guardrails. An autonomous agent
allocating enterprise capital without verified constraints introduces
substantial operational and financial risk.

This final white paper outlines **Phase 3** of the Google Cloud Agentic Data
Cloud journey: building a regulator-grade **System of Action**, following
[Phase 1: Breaking the Probabilistic
Wall](phase1_breaking_the_probabilistic_wall.md)
and
[Phase 2: Anchoring Agents in Structured Business
Reality](phase2_anchoring_agents_in_structured_business_reality.md).
We detail the mechanics of Unstructured-to-Graph (**U2G**) policy ingestion
using **Document AI Layout Parser** to parse and compile complex regulatory
guidelines into operational graph triples. We present the production-proven
**Dual-Graph Architecture** deployed by enterprise organizations such as
Yahoo—separating operational "acting" on **Cloud Spanner Graph** from auditable
"remembering" on **BigQuery Graph** via the **BigQuery Agent Analytics SDK**.
Finally, we demonstrate how executing parallel **Graph Mining Algorithms**
directly inside standard GQL queries delivers Google-grade network intelligence
to combat fraud, manage identity, and optimize supply chains at scale.

---

### Phase 3 System & Network Architecture

The diagram below illustrates the component topology, security boundaries, and
data flow sequence across the Dual-Graph foundation, U2G policy pipeline, and
parallel GQL graph algorithms:

![Architecture
Diagram](assets/phase3_regulator_grade_system_of_action/diagram-1.svg)

---

## 1. The System of Action: Speed, Safety, and Trust

Deploying autonomous agents to execute unsupervised workflows requires a
structured representation of business operations.[^1] While relational tables
(Phase 1) and relational-to-graph mapping (Phase 2) ground the agent in
structured transaction databases, they cannot ingest the unstructured
constraints that govern a corporation—such as legal agreements, standard
operating procedures, global refund rules, or compliance policies.

To bridge this gap, enterprises must implement a **Complete Semantic Ontology**
that spans both structured and unstructured domains, structuring implicit
organizational policies and domain rules into an active, multi-layered
framework.[^2]

![Architecture
Diagram](assets/phase3_regulator_grade_system_of_action/diagram-2.svg)

1.  **The Semantic Layer (What Exists):** Models the conceptual blueprint of the
    business, defining core entities (e.g., `Customer`, `Product`, and `Order`)
    and their explicit relationships.
1.  **The Kinetic Layer (How to Act):** Defines how actions and events
    transition across state boundaries (e.g., triggering payment authorization,
    packing warehouse items, or initiating returns).
1.  **The Dynamic Layer (Why to Act):** Simulates alternative scenarios,
    evaluates risk rules in real time, and provides the logical ground truth
    explaining _why_ a specific action was selected over alternatives.

By unifying these layers, the Agentic Data Cloud eliminates ungrounded
statistical approximations, anchoring every autonomous transaction in verified
enterprise rules.

Formally, the operational Knowledge Graph
![Mathematical formula](assets/math/math_mathcal_G_99dc22fc.svg) compiled from
enterprise policies and transactions is modeled as a typed, attributed property
graph:

![Mathematical formula](assets/math/math_mathcal_G_____left_b88d2d51.svg)

where:

- ![Mathematical formula](assets/math/math_V_d4d320aa.svg) represents the set of
  entity vertices, where each node
  ![Mathematical formula](assets/math/math_v__in_V_0d25f9c9.svg) is mapped to a
  label type
  ![Mathematical formula](assets/math/math_tau_V_v___in__mathc_9bf4ea6e.svg)
  (e.g., ![Mathematical formula](assets/math/math_text_Customer_4251d5f2.svg),
  ![Mathematical formula](assets/math/math_text_Order_a6d35cb2.svg),
  ![Mathematical formula](assets/math/math_text_Policy_85fdc989.svg)).

- ![Mathematical formula](assets/math/math_E__subseteq_V__times_3b88ef1f.svg)
  represents the set of directed, typed relationship edges representing semantic
  triples:

    ![Mathematical formula](assets/math/math_tau____v_s__xright_68525a61.svg)

- ![Mathematical formula](assets/math/math_Phi_V__V__times__ma_856df39c.svg) and
  ![Mathematical formula](assets/math/math_Phi_E__E__times__ma_2d2eb755.svg) are
  property mapping functions binding key-value attributes (e.g., timestamps,
  monetary amounts, policy restrictions) to nodes and edges.

---

## 2. Unstructured-to-Graph (U2G): Policy Extraction Pipeline

While **Cloud Spanner Graph**, **BigQuery Graph**, **Document AI**, and **Vertex
AI Gemini** are managed Google Cloud infrastructure services,
**Unstructured-to-Graph (U2G)** is an enterprise architectural pattern designed,
orchestrated, and customized by customer engineering teams (using Cloud Run,
Cloud Functions, or Dataflow pipelines).

To incorporate complex business guidelines into an agent's reasoning path, raw
documents must be transformed into structured graph triples
(Entity-Relation-Entity). This is achieved through an automated **U2G Pipeline**
orchestrated over Google Cloud primitives:

![Architecture
Diagram](assets/phase3_regulator_grade_system_of_action/diagram-3.svg)

### 2.1 PDF Ingestion and Layout Parsing: Moving Beyond OCR

Traditional document parsers process text as a flat stream of characters,
stripping away hierarchical headings, multi-column tables, flowchart arrows, and
visual geometries.

Under the U2G pipeline, **Document AI Layout Parser** combined with **Gemini
Multimodal** models preserves document spatial layout and visual hierarchies:

![Architecture
Diagram](assets/phase3_regulator_grade_system_of_action/diagram-4.svg)

> [!NOTE]
>
> **Ingestion Mechanics & Pipeline Constraints**
>
> - **Beyond Basic Optical Character Recognition (OCR):** OCR merely extracts
> raw characters (`"Step 1 Return Item Step 2 Fee"`). Document AI Layout
> Parser detects **spatial bounding boxes** (`[x1, y1, x2, y2]`), associating
> text blocks with their parent headers and tabular columns.
> - **Visual Causal Chains:** Gemini Multimodal reads flowchart arrows,
> recognizing that `Step 1 (Order Placed)` branches into
> `Step 2A (Standard Delivery)` vs. `Step 2B (Express Delivery)`, and maps
> these into explicit causal graph edges.
> - **Engineering Constraint:** Document AI Layout Parser is capped at **15
> pages and 20MB per document**. Enterprise ingest pipelines must chunk large
> manuals into logical chapters prior to parsing.

---

### 2.2 Concrete U2G Scenario on `thelook`: The "Wardrobing" Penalty Policy

To understand how U2G operates in real-world e-commerce, consider the widespread
industry problem of **"wardrobing"** (customers purchasing expensive apparel,
wearing them once for events, and immediately returning them).

#### 1. Unstructured Policy Text (Excerpt from 15-page Terms of Service PDF)

> _"Customers who return three (3) or more items across distinct categories
> within a 90-day window, resulting in a return-to-purchase ratio exceeding 60%,
> shall be classified under the 'Wardrobing Abuse Policy'. Such accounts will
> incur a mandatory \$25 restocking fee per returned unit."_

#### 2. U2G Compilation into Graph Triples

The LLM Extraction Agent converts this text into structured JSON triples:

- **Nodes:** `Policy: "Wardrobing Abuse Policy"`,
  `Restriction: "Restocking Fee $25"`,
  `Condition: "Return Ratio > 0.60 & Items >= 3"`
- **Edges:** `(Policy)-[:ENFORCES]->(Restriction)`,
  `(Policy)-[:TRIGGERED_BY]->(Condition)`

Instead of estimating compliance via probabilistic language model inference, the
agent evaluates this compiled policy as a deterministic boolean predicate
![Mathematical formula](assets/math/math_mathcal_P____text_w_e6609448.svg) over
graph paths in Cloud Spanner Graph:

![Mathematical formula](assets/math/math_begin_aligned___ma_1f2a02d6.svg)

where ![Mathematical formula](assets/math/math_mathcal_O___90__u_a29fd16f.svg)
denotes all orders placed by user
![Mathematical formula](assets/math/math_u_c941d8b6.svg) within the 90-day
window, ![Mathematical formula](assets/math/math_I___text_returned_3c860086.svg)
is the set of returned inventory items for order
![Mathematical formula](assets/math/math_o_dcd2dbb4.svg), and
![Mathematical formula](assets/math/math_I___text_total___o_7a8a173f.svg) is the
total item set.

The fee execution function is computed as a strict piecewise mapping:

![Mathematical formula](assets/math/math_text_RestockingFee_e8b04755.svg)

#### 3. Deterministic GQL Evaluation in Cloud Spanner

When a customer requests a refund, the agent evaluates the live transaction
graph and policy triples deterministically:

```sql
-- Evaluates wardrobing policy and applies restocking fee deterministically
SELECT * FROM GRAPH_TABLE(KnowledgeGraph
  MATCH (u:users {id: 82105})-[:places]->(o:orders)-[:contains_item]->(ii:inventory_items),
        (pol:Policy {name: 'Wardrobing Abuse Policy'})-[:ENFORCES]->(res:Restriction)
  WHERE u.return_ratio > 0.60
    AND o.created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
  RETURN u.id AS user_id, u.email, COUNT(ii) AS returned_item_count, res.fee_amount AS restocking_fee
);

```

The agent does not guess whether a fee applies; the graph enforces the rule with
**100% mathematical certainty**.

---

### 2.3 Semantic Extraction and Schema Curation

With the structured JSON layout, the LLM-driven **Extraction Agent** compiles
plain text policies into standardized business ontologies. It isolates core
entities and relationships:

- **Nodes:** Created for `Policy` (e.g., "The Look Points System"),
  `MembershipTier` (e.g., "Gold Tier" with eligibility rules), `Restriction`
  (e.g., Wardrobing policy), and `Action` (e.g., Size Exchange).
- **Edges:** Created for relationships such as `APPLIES_TO`, `HAS_CONDITION`,
  `DEFINES`, and `INVOLVES_OBJECT`.

The output is written into clean schema definitions (`nodes.json` and
`edges.json`) and loaded directly into **Cloud Spanner Graph** as a unified
operational model.

#### Querying Parsed Policies Natively in GQL

Once loaded, resolving complex, conditional business policies (which previously
required searching across scattered documents) is simplified into a single,
high-performance GQL path traversal:

```sql
-- Evaluates exchange rules and return fees for global orders
SELECT
  T.globalOrderPolicy,
  T.exchangePolicy,
  T.returnFeePolicy
FROM GRAPH_TABLE(U2G
  MATCH (d:Delivery)-[:fulfills]->(o:`Order`)
  COLUMNS (
    o.globalOrderPolicy AS globalOrderPolicy,
    o.exchangePolicy AS exchangePolicy,
    d.returnFeePolicy AS returnFeePolicy
  )
) AS T
LIMIT 1;

```

---

### 2.4 Production Realities: Mitigating Extraction Noise, Terminology Drift, and Lifecycle Scale

Deploying an automated U2G extraction pipeline in enterprise environments (such
as Financial Services, Insurance, and Healthcare) requires addressing four
critical operational realities:

#### 1. Beyond OCR: Domain-Specific Semantic Grounding

Document AI Layout Parser extracts spatial geometry, reading orders, and table
structures. However, extracting raw text is not equivalent to understanding its
specific enterprise meaning. To ensure the LLM maps extracted text to verified
business rules rather than guessing, customer extraction pipelines ground the
Gemini prompt with **Knowledge Catalog** glossaries and explicit JSON schema
templates, eliminating unconstrained entity generation.

#### 2. Terminology Normalization & Entity Disambiguation

Disparate enterprise documents frequently refer to identical business entities
with slight naming variations (e.g., `Cymbal Card`, `cymbal_card`, and
`CymbalCard`). Loading unnormalized strings directly into Spanner Graph creates
disjoint, fragmented nodes and broken traversal paths.

Production pipelines establish naming consistency through two complementary
bootstrapping strategies before committing triples into Spanner Graph:

- **Prompt-Grounded Canonical Registry:** When an enterprise glossary exists,
  inject the canonical entity list into the Gemini system prompt, instructing
  the model to map extracted entities to predefined identifiers.
- **Two-Pass Cold-Start Bootstrapping:** When no predefined glossary exists,
  extract an initial baseline vocabulary from a sample batch (e.g., the first 50
  documents). Subsequent document extractions reference this initialized
  vocabulary, generating new entity terms only when strictly necessary.
- **Entity Resolution & Normalization Layer:** Pre-commit validation normalizes
  letter casing, strips special characters, and evaluates vector embedding
  cosine similarity to merge semantic aliases into unified canonical nodes in
  Knowledge Catalog and Spanner Graph.

#### 3. Ingestion Throughput & Batch Processing Strategy

Extracting multi-page policy manuals across hundreds of enterprise documents can
incur substantial processing latency. Enterprise architectures mitigate this
bottleneck by:

- **Asynchronous Worker Pools:** Distributing extraction tasks across scalable
  Cloud Run and Cloud Tasks worker queues.
- **Document-Level Layout Caching:** Caching parsed Document AI JSON layouts in
  Cloud Storage so re-extractions do not repeat OCR parsing.
- **Incremental Change Data Capture (CDC):** Ingesting only modified chapters
  when corporate policies change, avoiding complete corpus reprocessing.

#### 4. Policy Lifecycle, Versioning, and Temporal Validity

Corporate workflows evolve, terms of service update, and commercial products
retire. To manage knowledge drift without corrupting historical auditability,
all U2G policy nodes and edges in Spanner Graph maintain explicit temporal
properties:

- **`valid_from` & `valid_to` (TIMESTAMP):** Bounds the active lifespan of a
  policy rule (`NULL` in `valid_to` represents the current active policy).
- **`policy_version` (STRING):** Tracks the semantic revision (e.g., `"v2.4"`).
- **`status` (STRING):** Represents state (`"active"`, `"deprecated"`,
  `"draft"`).

When evaluating transactions, agents execute temporal GQL queries that filter
active rules at transaction time:

```sql
-- Evaluates policies active at the exact time the order was placed
SELECT * FROM GRAPH_TABLE(KnowledgeGraph
  MATCH (o:orders)-[:contains_item]->(ii:inventory_items),
        (pol:Policy {status: 'active'})-[:ENFORCES]->(res:Restriction)
  WHERE pol.valid_from <= o.created_at
    AND (pol.valid_to IS NULL OR pol.valid_to > o.created_at)
  RETURN o.order_id, pol.name, res.fee_amount
);

```

When a product or policy retires, updating its `valid_to` timestamp and marking
its status as `deprecated` preserves historical order evaluations while
preventing the retired rule from applying to future transactions. Full evolution
lineages remain archived in the **Context Graph** in BigQuery Graph.

---

## 3. The Dual-Graph Blueprint: Operational Truth vs. Decision Lineage

For high-stakes workflows, separating the database used to execute real-time
transactions from the system used to audit and log agent decisions is a core
security requirement. Enterprise deployments establish this strict separation of
duties using Google Cloud's **Dual-Graph Foundation**:

![Architecture
Diagram](assets/phase3_regulator_grade_system_of_action/diagram-5.svg)

### 3.1 The Knowledge Graph (Acting in Spanner Graph)

The **Knowledge Graph** models the active operational business in real time.
Powered by **Cloud Spanner Graph**, it represents all products, placements,
active contracts, and regulatory constraints as a connected model. Because
compliance policies exist as versioned graph relationships rather than static
code, the engine evaluates contract rules, user consent, and geographic
exclusions within a single transactional GQL traversal. This guarantees that
every action is fully grounded and compliant _before_ any budget is committed or
transaction executed.

### 3.2 The Context Graph (Remembering in BigQuery Graph)

The **Context Graph** acts as the agent's auditable memory. Powered by
**BigQuery Graph**, it records the lineage of every decision made. Capturing
agent execution at scale is accomplished using the **BigQuery Agent Analytics
Plugin**. It structures the agent's thinking process—every candidate option
considered, constraint evaluated, score assigned, and final outcome—into a
typed, queryable graph using a standardized **Decision-Trace Ontology**.

---

## 4. Regulator-Grade Auditability: BigQuery Agent Analytics SDK

When regulators or enterprise auditors require explanation for an automated
decision (e.g., why a specific ad package was recommended or why a fraud alert
was triggered), parsing unstructured flat text logs is computationally expensive
and error-prone.

The **BigQuery Agent Analytics SDK** solves this, structuring the complete
lineage of an execution session into an immutable BigQuery Graph. Engineers
evaluate the reasoning behind any agent action with a standard GQL query:

```sql
-- Audits the trace of a specific supervisor execution path
GRAPH bigquery.AgentTraceGraph
MATCH p=(owner:Person)-[:Owns]->(:Account)<-[login:LogIn]-(media:Media {blocked: true})
RETURN TO_JSON(p) AS full_path
ORDER BY login.time
LIMIT 20;

```

This transforms what was once an opaque, non-deterministic execution into a
transparent, auditable, and mathematically verifiable record. Furthermore, as
delivery, performance, and outcome metrics are generated, they are written back
and joined to the context graph. This creates a **closed-loop learning cycle**,
generating clean, high-quality, proprietary datasets to continually fine-tune
downstream enterprise models.

Under the hood, the BigQuery Agent Analytics SDK structures this execution
history as an immutable state-action trajectory
![Mathematical formula](assets/math/math_mathcal_T____text_a_db14edda.svg):

![Mathematical formula](assets/math/math_mathcal_T____text_845690c3.svg)

where each intermediate state
![Mathematical formula](assets/math/math_s_t____langle_G_t_d5cf5cce.svg)
captures the active grounding subgraph
![Mathematical formula](assets/math/math_G_t__subseteq__mathc_567b524a.svg) and
evaluated policy constraints
![Mathematical formula](assets/math/math_Pi_t_28d04cab.svg). Every candidate
action
![Mathematical formula](assets/math/math_a_t__sim__pi_a__mid_9a60cef1.svg) must
satisfy the safety validation constraint before state transition commit:

![Mathematical formula](assets/math/math_forall_t__in__0__T_54203135.svg)

---

## 5. Native Graph Algorithms in GQL: Parallel Graph Mining at Scale

Uncovering complex, long-term patterns across vast, connected data—such as
detecting fraud rings, resolving customer identities, or mapping supply chain
bottlenecks—requires calculating network metrics over billions of nodes and
edges. Historically, this required complex Extract, Transform, Load (**ETL**)
pipelines that extracted database records to dedicated analytical clusters,
creating latency, inflating costs, and risking data drift.

Google Cloud unifies this workflow by integrating Google Research's parallel
**Graph Mining Algorithms** directly into standard GQL.[^3] Running on separate
compute nodes with shared memory, these algorithms scale to billions of nodes
and tens of billions of edges without impacting active transactional workloads.

### 5.1 Core Graph Mining Algorithms: Technical Reference

![Architecture
Diagram](assets/phase3_regulator_grade_system_of_action/diagram-6.svg)

- **PageRank (Centrality / Influence):** Originally invented by Google to rank
  web pages, PageRank simulates random walks across graph edges. In e-commerce
  and finance, it identifies the most influential accounts, core supplier hubs,
  or central transaction dispatchers. The stationary authority score
  ![Mathematical formula](assets/math/math_PR_u_4f4fe310.svg) for node
  ![Mathematical formula](assets/math/math_u__in_V_aa862058.svg) is computed via
  distributed power iteration with damping factor
  ![Mathematical formula](assets/math/math_d__in__0__1_7a416467.svg) (typically
  ![Mathematical formula](assets/math/math_d___0_85_07c774db.svg)):

    ![Mathematical formula](assets/math/math_PR___k_1___u_____fr_784b0784.svg)

    where
    ![Mathematical formula](assets/math/math_mathcal_N____text_i_18ea09a1.svg)
    is the set of in-bound transfer nodes, and
    ![Mathematical formula](assets/math/math_mathcal_N____text_b5e17c75.svg) is
    the out-degree of node
    ![Mathematical formula](assets/math/math_v_f64861bb.svg).

- **Modularity Clustering (Community Detection):** Automatically partitions a
  massive graph into dense clusters where internal edge density is significantly
  higher than expected by chance. Partitioning graphs into modular topological
  communities forms the basis of hierarchical GraphRAG summarization and global
  multi-hop reasoning, detecting hidden rings of coordinated fraud without
  needing prior training labels.[^4] Spanner Graph identifies these clusters by
  maximizing the Newman-Girvan modularity metric
  ![Mathematical formula](assets/math/math_Q_8f52f457.svg):

    ![Mathematical formula](assets/math/math_Q____frac_1__2m___s_3c83b917.svg)

    where ![Mathematical formula](assets/math/math_A__ij_414afecb.svg) is the
    adjacency matrix weight between nodes
    ![Mathematical formula](assets/math/math_i_bcd6e42c.svg) and
    ![Mathematical formula](assets/math/math_j_9c0e56f0.svg),
    ![Mathematical formula](assets/math/math_k_i____sum_j_A__ij_aeb07f3d.svg) is
    the degree of node ![Mathematical formula](assets/math/math_i_bcd6e42c.svg),
    ![Mathematical formula](assets/math/math_m____frac_1__2___sum_8f9c73bf.svg)
    is the total network edge weight,
    ![Mathematical formula](assets/math/math_c_i_1dc60a6e.svg) is the assigned
    community cluster, and
    ![Mathematical formula](assets/math/math_delta_c_i__c_j_0fb96021.svg) is the
    Kronecker delta
    (![Mathematical formula](assets/math/math_delta_c_i__c_j____1_faebbcda.svg)
    if ![Mathematical formula](assets/math/math_c_i___c_j_b793401d.svg), and
    ![Mathematical formula](assets/math/math_0_dc126100.svg) otherwise).

---

### 5.2 Financial Fraud Detection & Return Rings Case Study

To illustrate the power of combining graph algorithms with standard GQL queries,
consider a real-time investigation across `thelook` e-commerce network to detect
organized return fraud and coordinated accounts.

#### Step 1: Detect Dense Communities (Modularity Clustering)

We execute a community detection algorithm natively in GQL to segment the
transfer network and write the resulting `community_id` directly back to the
`Account` node:

```sql
-- Runs community detection and writes cluster IDs back to the database
EXPORT DATA OPTIONS(
  format = 'CLOUD_SPANNER',
  table = 'Account',
  write_mode = 'update_ignore_all'
) AS GRAPH FinGraph
CALL ModularityClustering(
  node_labels => ['Account'],
  edge_labels => ['Transfer']
) YIELD node, cluster
RETURN node.id, cluster AS community_id;

```

#### Step 2: Query High-Risk Clusters

With community IDs stored, we execute a standard GQL query to pinpoint which
cluster exhibits the highest concentration of flagged fraud accounts:

```sql
-- Isolates the community with the highest concentration of fraud
GRAPH FinGraph
MATCH (a:Account)
WHERE a.community_id IS NOT NULL
  AND a.fraud_flag = TRUE
RETURN a.community_id AS community_id, COUNT(*) AS fraud_count
ORDER BY fraud_count DESC;

```

#### Step 3: Identify Central Coordinated Nodes (PageRank on a Subgraph)

Assuming Community 2 is identified as high-risk, we isolate that specific
community as a subgraph and run the PageRank algorithm natively to find the
central coordinating node:

```sql
-- Isolates the high-risk subgraph and executes PageRank
EXPORT DATA OPTIONS(
  format = 'CLOUD_SPANNER',
  table = 'Account',
  write_mode = 'update_ignore_all'
) AS GRAPH FinGraph
MATCH (n:Account {community_id: 2})
RETURN n
FULL UNION ALL
MATCH ()-[e:Transfer]->()
RETURN e
NEXT
CALL PageRank(max_iterations => 20)
YIELD node, score
RETURN node.id, score AS pagerank_score;

```

#### Step 4: Trace the Flow of Funds

Finally, we query the central coordinating account to trace where funds were
transferred:

```sql
-- Identifies the coordinating account and traces all fund transfers
GRAPH FinGraph
MATCH (ringleader:Account {community_id: 2})
ORDER BY ringleader.pagerank_score DESC
LIMIT 1
WITH ringleader
MATCH (ringleader)-[e:Transfer*1..5]->(receiver:Account)
WHERE e.ts > '2025-12-01'
RETURN ringleader.id AS ringleader_id, receiver.id AS receiver_id, e.amount, e.ts;

```

By unifying analytics and transactions inside a single GQL engine, Spanner Graph
removes architectural complexity, speeds up insights, and ensures that decision
loops operate on the most up-to-date data available.

---

## 6. Metadata as Code: Open Knowledge Format (OKF) & GitOps Governance

To ensure that enterprise definitions, business metrics, and domain knowledge
are consistently versioned, tested, and audited before deployment to an agent's
active memory, organizations adopt the **Open Knowledge Format (OKF)**[^5]
within a **GitOps workflow**.

![Architecture
Diagram](assets/phase3_regulator_grade_system_of_action/diagram-7.svg)

### 6.1 The Power of YAML + Markdown Separation

- **YAML Frontmatter (Machine-Readable Metadata):** Parsed computationally by
  Knowledge Catalog and LLM tool runtimes for exact schema bindings, resource
  endpoints, and filter tags.
- **Markdown Body (Human-Readable Logic):** Enables business analysts, legal
  counsel, and policy writers to author complex business rules in clean plain
  text without requiring machine learning engineering expertise.

```markdown
---
type: Metric
title: Customer Churn Rate
description: Percentage of active subscribers who cancel their plans.
resource: looker.explore.users
tags: [retention, financial]
timestamp: 2026-07-19T21:30:00Z
---

# Definition
The churn rate is calculated by dividing total cancellations during the 30-day window by starting active subscribers.

# Formula
$$\text{Churn Rate} = \frac{\text{Cancellations (30d)}}{\text{Active Subscribers (Day 0)}} \times 100$$

# Relationships
See the [customer definitions](/metrics/customer_definitions.md) for cohort filters.

```

### 6.2 Developer Safeguards for Agentic AI: `git blame` and PRs

By anchoring the agent's knowledge base in Git:

1.  **`git blame` Forensic Auditing:** If an agent executes an unexpected action
    in production, engineers run `git blame` to inspect the exact commit,
    timestamp, and author who altered the rule.
1.  **Pull Request Approval Gates:** No business rule, discount threshold, or
    policy condition can enter the agent's active memory without peer review and
    managerial sign-off.
1.  **Automated CI/CD Verification:** Automated tests validate that SQL and GQL
    formulas parse cleanly against production schemas before deploying to
    Knowledge Catalog.

---

### 6.3 OKF vs. Google Cloud Knowledge Catalog

While OKF is ideal for local prototyping and Git-integrated "Metadata-as-Code"
versioning, scaling to enterprise production requires a managed governance
layer:

| Architectural Dimension   | Open Knowledge Format (OKF)                                        | Google Cloud Knowledge Catalog                                                                                                      |
| :------------------------ | :----------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------- |
| **Core Focus**            | Git-based open-source markdown specification for local prototyping | Managed, automated enterprise context and metadata security platform                                                                |
| **Governance & Security** | Manual; relies on Git repository permissions                       | Native, cloud-secure, Identity and Access Management (**IAM**)-aware row and column-level Access Control List (**ACL**) enforcement |
| **Maintenance**           | Manual files; risks documentation drift over time                  | Continuous metadata crawler that automatically synchronizes, profiles, and validates data assets                                    |
| **Stability & SLA**       | Community-driven spec; subject to breaking version changes         | Enterprise Google Cloud service backed by strict performance Service Level Agreements (**SLAs**)                                    |

Under this reference architecture, OKF serves as the development on-ramp.
Developers version business context locally using OKF markdown, and automated
CI/CD pipelines ingest those bundles into **Knowledge Catalog**[^6] to maintain
a secure, managed production environment.

---

## Conclusion: Building Your Enterprise Data Moat

As foundation models become increasingly commoditized, deploying a standard LLM
or standard vector database no longer provides a sustainable competitive
advantage. In the agentic era, **an enterprise's true business moat is its
proprietary graph of operations and governed history**.

By progressing along this three-phase reference architecture journey,
organizations move beyond the probabilistic limits of raw text search,
establishing a robust, explainable, and regulator-grade **System of Action**.
Combining the transactional speed of Spanner Graph, the analytical depth of
BigQuery Graph, and the centralized semantics of Knowledge Catalog, the **Google
Cloud Agentic Data Cloud** provides the definitive blueprint to build, deploy,
and scale autonomous enterprise intelligence.

---

_Document Reference: Beyond the Chatbot: The Enterprise Architecture for Systems
of Action — Google Cloud._

[^1]:
    Mikul Bhatt and Bei Li, "Architecting a trusted agentic platform with graph
    technologies: A Yahoo case study," _Google Cloud Blog_, June 15, 2026.
    \[Online\]. Available:
    <https://cloud.google.com/blog/products/databases/graph-technologies-underpin-yahoo-system-of-action>

[^2]:
    "LLM-Powered Knowledge Graphs for Enterprise Intelligence and Analytics,"
    _arXiv preprint arXiv:2503.07993_, 2025. \[Online\]. Available:
    <https://arxiv.org/abs/2503.07993>

[^3]:
    Bei Li and Vahab Mirrokni, "Announcing Spanner Graph algorithms:
    Google-grade intelligence for connected data," _Google Cloud Blog_, June
    2, 2026. \[Online\]. Available:
    <https://cloud.google.com/blog/products/databases/introducing-spanner-graph-algorithms>

[^4]:
    D. Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused
    Summarization," _arXiv preprint arXiv:2404.16130_, 2024. \[Online\].
    Available: <https://arxiv.org/abs/2404.16130>

[^5]:
    Sam McVeety and Amir Hormati, "Introducing the Open Knowledge Format,"
    _Google Cloud Blog_, June 12, 2026. \[Online\]. Available:
    <https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing>

[^6]:
    Chai Pydimukkala and Sam McVeety, "Introducing the Google Cloud Knowledge
    Catalog," _Google Cloud Blog_, April 22, 2026. \[Online\]. Available:
    <https://cloud.google.com/blog/products/data-analytics/introducing-the-google-cloud-knowledge-catalog>
