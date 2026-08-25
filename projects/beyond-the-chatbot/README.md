# Beyond the Chatbot: The Enterprise Architecture for Systems of Action

This project provides a comprehensive reference architecture series and
technical blueprint for building autonomous, deterministic, and regulator-grade
**Systems of Action** on Google Cloud. It establishes a multi-phase evolutionary
pathway from probabilistic conversational chatbots to auditable operational
agents anchored in property graphs and active semantic metadata.

## Document Series Overview

The white paper series consists of four technical architectural guides:

| Document                                                                                                                    | Focus & Key Technologies                                                                                                                                                                                          |
| :-------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **[Architecture Blueprint (Index)](./index.md)**                                                                            | Architectural executive summary, 3-phase comparative matrix, core concept primers, and technical FAQ.                                                                                                             |
| **[Phase 1: Breaking the Probabilistic Wall](./phase1_breaking_the_probabilistic_wall.md)**                                 | Peak Relational-AI with **AlloyDB AI**, standard Vector RAG mechanics, and the operational boundaries of probabilistic retrieval.                                                                                 |
| **[Phase 2: Anchoring Agents in Structured Business Reality](./phase2_anchoring_agents_in_structured_business_reality.md)** | Relational-to-Graph (**R2G**) transition, **Cloud Spanner Graph**, **BigQuery Graph**, and **Knowledge Catalog (formerly Dataplex)** active business glossaries.                                                  |
| **[Phase 3: The Regulator-Grade System of Action](./phase3_regulator_grade_system_of_action.md)**                           | Dual-Graph architecture (**Knowledge Graph + Context Graph**), Unstructured-to-Graph (**U2G**) policy parsing, native GQL graph mining algorithms, and GitOps governance via the **Open Knowledge Format (OKF)**. |

## Google Cloud Core Stack

- **Cloud Spanner Graph:** Sub-10ms operational property graph traversal for
  real-time transactional policy evaluation and execution.
- **BigQuery Graph & Agent Analytics SDK:** Immutable context graph warehouse
  for decision lineage tracking and closed-loop model tuning.
- **AlloyDB AI:** Columnar vector search and in-database embeddings for
  high-throughput relational retrieval.
- **Knowledge Catalog:** Governed business glossaries and metadata aspect
  rulesets enforcing deterministic query generation.
- **Document AI & Gemini:** Multi-page layout parsing and unstructured policy
  compilation into graph triples.
- **Open Knowledge Format (OKF):** Metadata-as-Code specification for Git-driven
  business policy version control.
