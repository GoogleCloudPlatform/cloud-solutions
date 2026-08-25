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

```mermaid
flowchart TD
    subgraph Client_Layer ["Client & Interaction Layer (Google Kubernetes Engine / GKE)"]
        direction TB
        User["fa:fa-user User Natural Language Query<br>(Campaign Directive)"]
        Supervisor["fa:fa-robot Conversational / Supervisor Agent<br>(GKE Orchestrator)"]
        User --> Supervisor
    end

    subgraph Governance_Layer ["Control & Governance Layer (Knowledge Catalog (formerly Dataplex) & OKF)"]
        direction TB
        KC["fa:fa-book Knowledge Catalog<br>(Universal Context Engine)"]
        Glossary["fa:fa-tags Business Glossary<br>('VIP Customer', 'High Return Rate')"]
        Aspects["fa:fa-file-code Custom Metadata Aspects<br>(SQL_Mapping_Ruleset Contracts)"]
        GitOKF["fa:fa-code-branch Git Repository<br>(Open Knowledge Format Files)"]
        GitOKF -- "CI/CD Sync" --> KC
        KC --- Glossary
        KC --- Aspects
    end

    subgraph Unstructured_Pipeline ["Unstructured Document Ingestion Pipeline"]
        direction TB
        GCS["fa:fa-folder-open Cloud Storage (GCS)<br>(Raw Policy PDFs, Terms of Service)"]
        DocAI["fa:fa-file-alt Document AI Layout Parser<br>(Layout & Structural JSON Parsing)"]
        U2G["fa:fa-project-diagram LLM U2G Extraction Agent<br>(Semantic Triples Generation)"]
        GCS --> DocAI --> U2G
    end

    subgraph Operational_Boundary ["Operational Network Boundary (Virtual Private Cloud / High-Availability OLTP)"]
        direction TB
        AlloyDB["fa:fa-database AlloyDB AI Engine (Phase 1 Baseline)<br>- Operational PostgreSQL Data (thelook tables)<br>- Built-in pgvector & In-database Embeddings"]
        SpannerKG["fa:fa-project-diagram Cloud Spanner Graph (Knowledge Graph - Operational ACTING)<br>- Property Graph (R2G & U2G Policy Triples)<br>- Sub-10ms GQL Path Traversals<br>- Parallel Graph Mining (PageRank & Modularity Clustering)"]
        AlloyDB -- "Relational Grounding" --> SpannerKG
    end

    subgraph Analytical_Boundary ["Analytical Data Warehouse Boundary (OLAP & Audit Memory)"]
        direction TB
        BQCG["fa:fa-history BigQuery Graph (Context Graph - Auditable REMEMBERING)<br>- BigQuery Agent Analytics SDK & Plugin<br>- Decision-Trace Lineage Memory"]
        VertexVS["fa:fa-search Vertex AI Vector Search<br>(Vectorized Embedding Index)"]
    end

    subgraph AI_Foundation ["Vertex AI Foundation Layer"]
        direction TB
        Gemini["fa:fa-brain Vertex AI (Gemini Multimodal Models)"]
    end

    %% Information Flow
    Supervisor -- "1. Lookup Semantic Contract" --> KC
    KC -- "2. Validated Filter Ruleset" --> Supervisor
    Supervisor -- "3. Grounding Inference" --> Gemini
    U2G -- "Ingest Policy Triples" --> SpannerKG
    Supervisor -- "4. Operational Acting (Zero-Hallucination GQL)" --> SpannerKG
    Supervisor -- "5. Relational RAG & Vector Search" --> AlloyDB
    Supervisor -- "5b. Vector Search" --> VertexVS
    Supervisor -- "6. Log Decision Lineage (Remembering)" --> BQCG
    SpannerKG -- "Spanner Data Boost (Zero-Impact Analytics)" --> BQCG

    style User fill:#4285F4,stroke:#3c4043,color:#FFFFFF
    style Supervisor fill:#4285F4,stroke:#3c4043,color:#FFFFFF
    style KC fill:#FBBC04,stroke:#3c4043,color:#202124
    style Glossary fill:#F8F9FA,stroke:#FBBC04,color:#202124
    style Aspects fill:#F8F9FA,stroke:#FBBC04,color:#202124
    style GitOKF fill:#FBBC04,stroke:#3c4043,color:#202124
    style GCS fill:#34A853,stroke:#3c4043,color:#FFFFFF
    style DocAI fill:#EA4335,stroke:#3c4043,color:#FFFFFF
    style U2G fill:#FBBC04,stroke:#3c4043,color:#202124
    style AlloyDB fill:#34A853,stroke:#3c4043,color:#FFFFFF
    style SpannerKG fill:#34A853,stroke:#3c4043,color:#FFFFFF
    style BQCG fill:#34A853,stroke:#3c4043,color:#FFFFFF
    style VertexVS fill:#EA4335,stroke:#3c4043,color:#FFFFFF
    style Gemini fill:#EA4335,stroke:#3c4043,color:#FFFFFF

```

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
framework.[^5]

```mermaid
flowchart TD
    subgraph Framework ["ACTIVE ONTOLOGY FRAMEWORK LAYERS"]
        direction TB
        subgraph Dynamic ["DYNAMIC LAYER (Why to Act / Sim)"]
            direction TB
            D1["fa:fa-chart-line Dynamic Logic<br>- Predicts outcomes, evaluates risks<br>- Explainable AI grounding traces"]
        end
        subgraph Kinetic ["KINETIC LAYER (How to Act / Process)"]
            direction TB
            K1["fa:fa-cogs Kinetic Execution<br>- Decomposes workflows, triggers APIs<br>- Defines transition states & events"]
        end
        subgraph Semantic ["SEMANTIC LAYER (What Exists / Schema)"]
            direction TB
            S1["fa:fa-sitemap Semantic Schema<br>- Core entities: Actor, Process, Object<br>- Explicit typed relationships (edges)"]
        end
        Dynamic --> Kinetic --> Semantic
    end

    style D1 fill:#FBBC04,stroke:#3c4043,color:#202124
    style K1 fill:#4285F4,stroke:#3c4043,color:#FFFFFF
    style S1 fill:#34A853,stroke:#3c4043,color:#FFFFFF

```

1.  **The Semantic Layer (What Exists):** Models the conceptual blueprint of the
   business, defining core entities (e.g., `Customer`, `Product`, and `Order`)
   and their explicit relationships.
1.  **The Kinetic Layer (How to Act):** Defines how actions and events
    transition
   across state boundaries (e.g., triggering payment authorization, packing
   warehouse items, or initiating returns).
1.  **The Dynamic Layer (Why to Act):** Simulates alternative scenarios,
   evaluates risk rules in real time, and provides the logical ground truth
   explaining _why_ a specific action was selected over alternatives.

By unifying these layers, the Agentic Data Cloud eliminates ungrounded
statistical approximations, anchoring every autonomous transaction in verified
enterprise rules.

Formally, the operational Knowledge Graph $\mathcal{G}$ compiled from enterprise
policies and transactions is modeled as a typed, attributed property graph:

$$
\mathcal{G} = \left( V, E, \mathcal{T}_V, \mathcal{T}_E, \Phi_V, \Phi_E \right)
$$

where:

- $V$ represents the set of entity vertices, where each node $v \in V$ is mapped
  to a label type $\tau_V(v) \in \mathcal{T}_V$ (e.g., $\text{Customer}$,
  $\text{Order}$, $\text{Policy}$).
- $E \subseteq V \times \mathcal{T}_E \times V$ represents the set of
  directed, typed relationship edges representing semantic triples:

  $$
  \tau = (v_s \xrightarrow{r} v_t) \quad \text{where } v_s, v_t \in V,
  \, r \in \mathcal{T}_E
  $$

- $\Phi_V: V \times \mathcal{K}_V \to \mathcal{V}$ and
  $\Phi_E: E \times \mathcal{K}_E \to \mathcal{V}$ are property mapping
  functions binding key-value attributes (e.g., timestamps, monetary amounts,
  policy restrictions) to nodes and edges.

---

## 2. Unstructured-to-Graph (U2G): Policy Extraction Pipeline

While **Cloud Spanner Graph**, **BigQuery Graph**, **Document AI**, and
**Vertex AI Gemini** are managed Google Cloud infrastructure services,
**Unstructured-to-Graph (U2G)** is an enterprise architectural pattern designed,
orchestrated, and customized by customer engineering teams (using Cloud Run,
Cloud Functions, or Dataflow pipelines).

To incorporate complex business guidelines into an agent's reasoning path, raw
documents must be transformed into structured graph triples
(Entity-Relation-Entity). This is achieved through an automated **U2G Pipeline**
orchestrated over Google Cloud primitives:

```mermaid
flowchart LR
    Docs["fa:fa-file-pdf Unstructured PDFs / Docs<br>(Terms of Svc, Guidelines)"] --> Parser["fa:fa-file-alt Document AI Layout Parser<br>(Parses tables, hierarchies, JSON)"]
    Parser --> LLM["fa:fa-brain LLM Semantic Extraction<br>(Generates nodes/edges .json)"]
    LLM --> Spanner["fa:fa-project-diagram Cloud Spanner Graph Load<br>(Materializes as triple graph)"]

    style Docs fill:#34A853,stroke:#3c4043,color:#FFFFFF
    style Parser fill:#EA4335,stroke:#3c4043,color:#FFFFFF
    style LLM fill:#FBBC04,stroke:#3c4043,color:#202124
    style Spanner fill:#34A853,stroke:#3c4043,color:#FFFFFF

```

### 2.1 PDF Ingestion and Layout Parsing: Moving Beyond OCR

Traditional document parsers process text as a flat stream of characters,
stripping away hierarchical headings, multi-column tables, flowchart arrows, and
visual geometries.

Under the U2G pipeline, **Document AI Layout Parser** combined with **Gemini
Multimodal** models preserves document spatial layout and visual hierarchies:

```mermaid
flowchart LR
    PDF["fa:fa-file-pdf Visual Policy PDF<br>(Flowcharts, Multi-column Tables)"] --> DocAI["fa:fa-file-alt Document AI Layout Parser<br>- Bounding Polygon Detection<br>- Hierarchy & Table Extraction<br>- (Max 15 pages / 20MB)"]
    DocAI --> JSON["fa:fa-file-code Structured Layout JSON<br>- Blocks, Tables, Causal Chains"]
    JSON --> Gemini["fa:fa-brain Gemini Multimodal<br>- Interprets Flowchart Logic<br>- Generates (Node)-[Edge]->(Node)"]

    style PDF fill:#34A853,stroke:#3c4043,color:#FFFFFF
    style DocAI fill:#EA4335,stroke:#3c4043,color:#FFFFFF
    style JSON fill:#FBBC04,stroke:#3c4043,color:#202124
    style Gemini fill:#4285F4,stroke:#3c4043,color:#FFFFFF

```

> [!NOTE]
>
> **Ingestion Mechanics & Pipeline Constraints**
>
> - **Beyond Basic Optical Character Recognition (OCR):** OCR merely extracts
>   raw characters (`"Step 1 Return Item Step 2 Fee"`). Document AI Layout
>   Parser detects **spatial bounding boxes** (`[x1, y1, x2, y2]`), associating
>   text blocks with their parent headers and tabular columns.
> - **Visual Causal Chains:** Gemini Multimodal reads flowchart arrows,
>   recognizing that `Step 1 (Order Placed)` branches into
>   `Step 2A (Standard Delivery)` vs. `Step 2B (Express Delivery)`, and maps
>   these into explicit causal graph edges.
> - **Engineering Constraint:** Document AI Layout Parser is capped at **15
>   pages and 20MB per document**. Enterprise ingest pipelines must chunk large
>   manuals into logical chapters prior to parsing.

---

### 2.2 Concrete U2G Scenario on `thelook`: The "Wardrobing" Penalty Policy

To understand how U2G operates in real-world e-commerce, consider the widespread
industry problem of **"wardrobing"** (customers purchasing expensive apparel,
wearing them once for events, and immediately returning them).

#### 1. Unstructured Policy Text (Excerpt from 15-page Terms of Service PDF)

> _"Customers who return three (3) or more items across distinct categories
> within a 90-day window, resulting in a return-to-purchase ratio exceeding 60%,
> shall be classified under the 'Wardrobing Abuse Policy'. Such accounts will
> incur a mandatory $25 restocking fee per returned unit."_

#### 2. U2G Compilation into Graph Triples

The LLM Extraction Agent converts this text into structured JSON triples:

- **Nodes:** `Policy: "Wardrobing Abuse Policy"`,
  `Restriction: "Restocking Fee $25"`,
  `Condition: "Return Ratio > 0.60 & Items >= 3"`
- **Edges:** `(Policy)-[:ENFORCES]->(Restriction)`,
  `(Policy)-[:TRIGGERED_BY]->(Condition)`

Instead of estimating compliance via probabilistic language model inference, the
agent evaluates this compiled policy as a deterministic boolean predicate
$\mathcal{P}_{\text{wardrobing}}(u, o)$ over graph paths in Cloud Spanner Graph:

$$
\begin{aligned}
\mathcal{P}_{\text{wardrobing}}(u, o) \iff
&\left( \frac{\sum_{o' \in \mathcal{O}_{90}(u)}
|I_{\text{returned}}(o')|}{\sum_{o' \in \mathcal{O}_{90}(u)}
|I_{\text{total}}(o')|} > 0.60 \right) \\
&\land \left( |I_{\text{returned}}(o)| \ge 3 \right)
\end{aligned}
$$

where $\mathcal{O}_{90}(u)$ denotes all orders placed by user $u$ within the
90-day window, $I_{\text{returned}}(o)$ is the set of returned inventory items
for order $o$, and $I_{\text{total}}(o)$ is the total item set.

The fee execution function is computed as a strict piecewise mapping:

$$
\text{RestockingFee}(u, o) = \begin{cases}
\$25 \times |I_{\text{returned}}(o)|, & \text{if }
\mathcal{P}_{\text{wardrobing}}(u, o) = \text{True} \\
0, & \text{otherwise}
\end{cases}
$$

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
Gemini prompt with **Knowledge Catalog** glossaries and explicit JSON
schema templates, eliminating unconstrained entity generation.

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
  extract an initial baseline vocabulary from a sample batch (e.g., the first
  50 documents). Subsequent document extractions reference this initialized
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
retire. To manage knowledge drift without corrupting historical auditability, all
U2G policy nodes and edges in Spanner Graph maintain explicit temporal
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

```mermaid
flowchart TD
    Brief["fa:fa-file-alt Campaign Brief (NL)"] --> Agent["fa:fa-robot Supervisor Agent (Google Kubernetes Engine / GKE)"]
    Agent --> KG["fa:fa-project-diagram KNOWLEDGE GRAPH (KG)<br>- Cloud Spanner Graph<br>- Low-latency ACTING"]
    Agent --> CG["fa:fa-history CONTEXT GRAPH (CG)<br>- BigQuery Graph<br>- Audit REMEMBERING"]

    subgraph KG_Tasks ["KG Actions"]
        direction TB
        KGT["fa:fa-tasks (1) Inventory & contract discovery<br>(2) Multi-hop policy evaluation<br>(3) Financial budget transaction"]
    end

    subgraph CG_Tasks ["CG Actions"]
        direction TB
        CGT["fa:fa-stream (1) Log intermediate thought trace<br>(2) Link outcome & delivery metrics<br>(3) Simple GQL explainability query"]
    end

    KG --- KG_Tasks
    CG --- CG_Tasks

    style Brief fill:#4285F4,stroke:#3c4043,color:#FFFFFF
    style Agent fill:#4285F4,stroke:#3c4043,color:#FFFFFF
    style KG fill:#34A853,stroke:#3c4043,color:#FFFFFF
    style CG fill:#34A853,stroke:#3c4043,color:#FFFFFF
    style KGT fill:#F8F9FA,stroke:#34A853,color:#202124
    style CGT fill:#F8F9FA,stroke:#34A853,color:#202124

```

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
history as an immutable state-action trajectory $\mathcal{T}_{\text{agent}}$:

$$
\mathcal{T}_{\text{agent}} = \left(
s_0 \xrightarrow{a_0, r_0} s_1 \xrightarrow{a_1, r_1} \dots
\xrightarrow{a_{T-1}, r_{T-1}} s_T \right)
$$

where each intermediate state $s_t = \langle G_t, \Pi_t \rangle$ captures the
active grounding subgraph $G_t \subseteq \mathcal{G}_{\text{KG}}$ and
evaluated policy constraints $\Pi_t$. Every candidate action $a_t \sim \pi(a
\mid s_t)$ must satisfy the safety validation constraint before state
transition commit:

$$
\forall t \in [0, T-1], \quad \mathcal{C}\left( a_t, \mathcal{G}_{\text{KG}}
\right) = \text{PASS} \implies \text{Commit}(s_{t+1})
$$

---

## 5. Native Graph Algorithms in GQL: Parallel Graph Mining at Scale

Uncovering complex, long-term patterns across vast, connected data—such as
detecting fraud rings, resolving customer identities, or mapping supply chain
bottlenecks—requires calculating network metrics over billions of nodes and
edges. Historically, this required complex Extract, Transform, Load (**ETL**)
pipelines that extracted database records to dedicated analytical clusters,
creating latency, inflating costs, and risking data drift.

Google Cloud unifies this workflow by integrating Google Research's parallel
**Graph Mining Algorithms** directly into standard GQL.[^2] Running on separate
compute nodes with shared memory, these algorithms scale to billions of nodes
and tens of billions of edges without impacting active transactional workloads.

### 5.1 Core Graph Mining Algorithms: Technical Reference

```mermaid
flowchart LR
    subgraph Algorithms ["CORE GRAPH ALGORITHMS IN GQL"]
        direction TB
        PR["fa:fa-bullseye PageRank (Centrality)<br>- Measures node authority & influence<br>- Finds network hubs & ringleaders"]
        MC["fa:fa-users Modularity Clustering (Communities)<br>- Maximizes internal connection density<br>- Automatically groups fraud rings / cohorts"]
        SP["fa:fa-route Shortest Path (Navigation)<br>- Calculates lowest hop-count & cost<br>- Optimizes supply chain routing"]
    end

    style PR fill:#4285F4,stroke:#3c4043,color:#FFFFFF
    style MC fill:#FBBC04,stroke:#3c4043,color:#202124
    style SP fill:#34A853,stroke:#3c4043,color:#FFFFFF

```

- **PageRank (Centrality / Influence):** Originally invented by Google to rank
  web pages, PageRank simulates random walks across graph edges. In e-commerce
  and finance, it identifies the most influential accounts, core supplier hubs,
  or central transaction dispatchers. The stationary authority score $PR(u)$
  for node $u \in V$ is computed via distributed power iteration with damping
  factor $d \in (0, 1)$ (typically $d = 0.85$):

  $$
  PR^{(k+1)}(u) = \frac{1 - d}{|V|} + d \sum_{v \in \mathcal{N}_{\text{in}}(u)}
  \frac{PR^{(k)}(v)}{|\mathcal{N}_{\text{out}}(v)|}
  $$

  where $\mathcal{N}_{\text{in}}(u) = \{ v \in V \mid (v, u) \in E \}$ is
  the set of in-bound transfer nodes, and $|\mathcal{N}_{\text{out}}(v)|$ is
  the out-degree of node $v$.
- **Modularity Clustering (Community Detection):** Automatically partitions a
  massive graph into dense clusters where internal edge density is significantly
  higher than expected by chance. Partitioning graphs into modular topological
  communities forms the basis of hierarchical GraphRAG summarization and global
  multi-hop reasoning, detecting hidden rings of coordinated fraud without
  needing prior training labels.[^6] Spanner Graph identifies these clusters by
  maximizing the Newman-Girvan modularity metric $Q$:

  $$
  Q = \frac{1}{2m} \sum_{i, j \in V} \left[ A_{ij} - \frac{k_i k_j}{2m} \right]
  \delta(c_i, c_j)
  $$

  where $A_{ij}$ is the adjacency matrix weight between nodes $i$ and $j$, $k_i
  = \sum_j A_{ij}$ is the degree of node $i$, $m = \frac{1}{2} \sum_{i, j}
  A_{ij}$ is the total network edge weight, $c_i$ is the assigned community
  cluster, and $\delta(c_i, c_j)$ is the Kronecker delta ($\delta(c_i, c_j) = 1$
  if $c_i = c_j$, and $0$ otherwise).

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
active memory, organizations adopt the **Open Knowledge Format (OKF)**[^3]
within a **GitOps workflow**.

```mermaid
flowchart LR
    Dev["fa:fa-user-edit Data Steward / Policy Writer"] --> PR["fa:fa-code-branch Git Pull Request<br>(Edit revenue.md / policy.md)"]
    PR --> CI["fa:fa-vial CI/CD Automated Validation<br>- Lints YAML frontmatter<br>- Verifies SQL contracts"]
    CI --> Review["fa:fa-user-check Human Manager Review<br>(Peer Approval)"]
    Review --> Merge["fa:fa-check-double Merge to Main<br>(Knowledge Catalog Sync)"]
    Merge --> Agent["fa:fa-robot Agent Active Memory<br>(Spanner Graph)"]

    style Dev fill:#4285F4,stroke:#3c4043,color:#FFFFFF
    style PR fill:#FBBC04,stroke:#3c4043,color:#202124
    style CI fill:#EA4335,stroke:#3c4043,color:#FFFFFF
    style Review fill:#4285F4,stroke:#3c4043,color:#FFFFFF
    style Merge fill:#34A853,stroke:#3c4043,color:#FFFFFF
    style Agent fill:#34A853,stroke:#3c4043,color:#FFFFFF

```

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
CI/CD pipelines ingest those bundles into **Knowledge Catalog**[^4] to maintain
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
BigQuery Graph, and the centralized semantics of Knowledge Catalog, the
**Google Cloud Agentic Data Cloud** provides the definitive blueprint to build,
deploy, and scale autonomous enterprise intelligence.

---

_Document Reference: Beyond the Chatbot: The Enterprise Architecture for Systems
of Action — Google Cloud._

[^1]:
    Mikul Bhatt and Bei Li, "Architecting a trusted agentic platform with graph
    technologies: A Yahoo case study," _Google Cloud Blog_, June 15, 2026.
    [Online]. Available:
    https://cloud.google.com/blog/products/databases/graph-technologies-underpin-yahoo-system-of-action

[^2]:
    Bei Li and Vahab Mirrokni, "Announcing Spanner Graph algorithms:
    Google-grade intelligence for connected data," _Google Cloud Blog_, June
    2, 2026. [Online]. Available:
    https://cloud.google.com/blog/products/databases/introducing-spanner-graph-algorithms

[^3]:
    Sam McVeety and Amir Hormati, "Introducing the Open Knowledge Format,"
    _Google Cloud Blog_, June 12, 2026. [Online]. Available:
    https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing

[^4]:
    Chai Pydimukkala and Sam McVeety, "Introducing the Google Cloud Knowledge
    Catalog," _Google Cloud Blog_, April 22, 2026. [Online]. Available:
    https://cloud.google.com/blog/products/data-analytics/introducing-the-google-cloud-knowledge-catalog

[^5]:
    "LLM-Powered Knowledge Graphs for Enterprise Intelligence and Analytics,"
    _arXiv preprint arXiv:2503.07993_, 2025. [Online]. Available:
    https://arxiv.org/abs/2503.07993

[^6]:
    D. Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused
    Summarization," _arXiv preprint arXiv:2404.16130_, 2024. [Online].
    Available: https://arxiv.org/abs/2404.16130
